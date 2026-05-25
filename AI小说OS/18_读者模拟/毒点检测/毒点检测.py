import logging
import json
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import importlib
import traceback
import os

# ------------------------------------------------------------
# 毒点数据模型
# ------------------------------------------------------------
@dataclass
class PoisonPoint:
    """检测到的毒点实体"""
    type: str                    # 毒点类型标识，如 "logic_flaw", "character_ooc"
    location: Optional[str] = None   # 毒点出现的位置（例如章节、段落索引）
    description: str = ""        # 人类可读的描述
    severity: float = 0.5        # 严重程度 0~1
    meta: Dict[str, Any] = field(default_factory=dict)  # 附加元数据

# ------------------------------------------------------------
# 毒点检测器接口 (可插拔)
# ------------------------------------------------------------
class PoisonDetectorPlugin(ABC):
    """所有毒点检测器的抽象基类"""
    @abstractmethod
    def detect(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[PoisonPoint]:
        """
        从给定文本中检测毒点
        :param text: 待检测文本内容
        :param context: 可选上下文信息（如前文摘要、角色设定等）
        :return: 检测到的毒点列表
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """检测器唯一名称"""
        pass

# ------------------------------------------------------------
# 内置示例毒点检测器 (基于规则的简单实现，供测试)
# ------------------------------------------------------------
class SimpleRepetitionDetector(PoisonDetectorPlugin):
    """检测明显的重复内容 (示例)"""
    def __init__(self, threshold: int = 3):
        self.threshold = threshold

    @property
    def name(self) -> str:
        return "simple_repetition"

    def detect(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[PoisonPoint]:
        results = []
        # 简单的句子重复检测 (伪实现)
        sentences = text.split('。')
        seen = {}
        for idx, sent in enumerate(sentences):
            stripped = sent.strip()
            if not stripped:
                continue
            seen.setdefault(stripped, []).append(idx)
        for sent, indices in seen.items():
            if len(indices) >= self.threshold:
                results.append(PoisonPoint(
                    type="repetition",
                    location=f"sentences {indices}",
                    description=f"重复句子: '{sent}' 出现 {len(indices)} 次",
                    severity=min(0.3 + 0.1 * (len(indices) - self.threshold), 1.0)
                ))
        return results

# ------------------------------------------------------------
# 毒点检测主引擎
# ------------------------------------------------------------
class PoisonDetector:
    """
    毒点检测主控模块
    职责：
        1. 加载/管理多个检测器插件
        2. 提供统一的检测入口
        3. 记录检测过程与日志
        4. 基于配置启停检测器及调整参数
    可插拔：通过 register_plugin / load_plugins_from_config 动态增减检测器
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self._plugins: Dict[str, PoisonDetectorPlugin] = {}
        self._disabled = set()        # 禁用的检测器名称集合
        self._init_default_config()
        self._setup_from_config()

    def _init_default_config(self):
        """初始化默认配置，可被子类或外部覆盖"""
        defaults = {
            "enable_logging": True,
            "log_level": "INFO",
            "plugins": {
                "simple_repetition": {
                    "enabled": True,
                    "config": {"threshold": 3}
                }
            },
            "disable_all": False       # 如果为True，则不加载任何检测器
        }
        # 仅当用户未提供时使用默认值，不覆盖已有key
        for k, v in defaults.items():
            if k not in self.config:
                self.config[k] = v
        # 设置日志级别
        if self.config.get("enable_logging", False):
            log_level = self.config.get("log_level", "INFO").upper()
            self.logger.setLevel(getattr(logging, log_level, logging.INFO))
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)

    def _setup_from_config(self):
        """根据配置加载内置和外部插件"""
        if self.config.get("disable_all", False):
            self.logger.info("配置 disable_all=True，跳过所有检测器加载")
            return
        # 加载内置示例检测器
        try:
            self._load_builtin_plugins()
        except Exception as e:
            self.logger.error(f"加载内置检测器失败: {e}")

        # 从配置加载额外的检测器路径 (可插拔扩展)
        external_plugins = self.config.get("external_plugins", [])
        for plugin_spec in external_plugins:
            try:
                self._load_plugin_from_spec(plugin_spec)
            except Exception as e:
                self.logger.error(f"加载外部插件失败 {plugin_spec}: {e}")

    def _load_builtin_plugins(self):
        """注册内置检测器（示例）"""
        plugins_config = self.config.get("plugins", {})
        # SimpleRepetitionDetector
        rep_config = plugins_config.get("simple_repetition", {})
        if rep_config.get("enabled", True):
            detector = SimpleRepetitionDetector(threshold=rep_config.get("config", {}).get("threshold", 3))
            self.register_plugin(detector)

    def _load_plugin_from_spec(self, spec: Dict[str, Any]):
        """
        根据规格动态加载插件
        spec 示例: {"path": "my_plugins.custom_detector.CustomDetector", "config": {...}, "name": "custom"}
        """
        path = spec.get("path")
        if not path:
            self.logger.error("插件规格缺少 path 字段")
            return
        module_name, class_name = path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        plugin_class = getattr(module, class_name)
        config = spec.get("config", {})
        instance = plugin_class(**config) if config else plugin_class()
        # 允许覆盖名称
        if "name" in spec:
            instance._name = spec["name"]
        self.register_plugin(instance)

    def register_plugin(self, plugin: PoisonDetectorPlugin):
        """注册一个检测器插件"""
        name = plugin.name
        if name in self._plugins:
            self.logger.warning(f"检测器 {name} 已存在，将被覆盖")
        self._plugins[name] = plugin
        # 检查是否在配置中被显式禁用
        plugins_config = self.config.get("plugins", {})
        if name in plugins_config and not plugins_config[name].get("enabled", True):
            self._disabled.add(name)
            self.logger.info(f"检测器 {name} 已在配置中禁用")
        else:
            self._disabled.discard(name)

    def unregister_plugin(self, name: str):
        """移除检测器"""
        self._plugins.pop(name, None)
        self._disabled.discard(name)

    def enable_plugin(self, name: str):
        """启用检测器"""
        if name in self._plugins:
            self._disabled.discard(name)
            # 更新配置
            self.config.setdefault("plugins", {}).setdefault(name, {})["enabled"] = True
        else:
            self.logger.warning(f"检测器 {name} 未注册，无法启用")

    def disable_plugin(self, name: str):
        """禁用检测器（不清除已注册实例）"""
        if name in self._plugins:
            self._disabled.add(name)
            self.config.setdefault("plugins", {}).setdefault(name, {})["enabled"] = False
        else:
            self.logger.warning(f"检测器 {name} 未注册，无法禁用")

    def detect(self, text: str, context: Optional[Dict[str, Any]] = None) -> List[PoisonPoint]:
        """
        主检测入口：遍历所有启用的检测器，收集毒点
        :param text: 待检测文本
        :param context: 可选上下文
        :return: 合并后的毒点列表
        """
        all_points = []
        active_plugins = [(name, plugin) for name, plugin in self._plugins.items() if name not in self._disabled]
        if not active_plugins:
            self.logger.warning("没有启用的毒点检测器")
            return all_points

        for name, plugin in active_plugins:
            try:
                self.logger.debug(f"执行检测器: {name}")
                points = plugin.detect(text, context)
                if points:
                    self.logger.info(f"检测器 {name} 发现 {len(points)} 个毒点")
                    all_points.extend(points)
            except Exception as e:
                self.logger.error(f"检测器 {name} 执行异常: {e}\n{traceback.format_exc()}")
                # 热更新异常恢复: 记录错误但继续运行其他检测器
        return all_points

    def summary(self) -> Dict[str, Any]:
        """返回当前检测器状态摘要"""
        return {
            "total_plugins": len(self._plugins),
            "enabled_plugins": [name for name in self._plugins if name not in self._disabled],
            "disabled_plugins": list(self._disabled),
            "config_summary": {k: v for k, v in self.config.items() if k != "plugins"}
        }

# ------------------------------------------------------------
# 自测 (if __name__ == "__main__")
# ------------------------------------------------------------
if __name__ == "__main__":
    # 使用默认配置创建检测器
    config = {
        "enable_logging": True,
        "log_level": "DEBUG",
        "plugins": {
            "simple_repetition": {
                "enabled": True,
                "config": {"threshold": 2}
            }
        }
    }
    detector = PoisonDetector(config)
    print("=== 毒点检测模块自测 ===")
    print(f"检测器状态: {detector.summary()}")

    # 测试文本
    test_text = "今天天气真好。今天天气真好。我们去散步吧。今天天气真好。不会有重复吗。不会有重复吗。"
    print(f"\n待检测文本: {test_text[:50]}...")
    results = detector.detect(test_text, context={"chapter": 1})
    print(f"检测到 {len(results)} 个毒点:")
    for point in results:
        print(f"  - 类型: {point.type}, 位置: {point.location}, 描述: {point.description}, 严重程度: {point.severity}")

    # 测试禁用检测器