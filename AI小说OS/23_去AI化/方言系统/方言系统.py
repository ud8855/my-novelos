"""
方言系统模块 (Dialect System)
位于：23_去AI化/方言系统
职责：提供多方言文本生成能力，降低AI痕迹，增强文本自然度。
可插拔：支持热加载方言模块。
配置化：方言库可通过配置文件管理。
日志化：记录方言加载、使用情况。
接口：DialectManager为上层提供统一调用接口。
依赖：基础日志与配置模块（假设为utils.logger, utils.config_manager）。
被谁调用：文本生成管线中的风格化步骤。
"""

import logging
import importlib
import os
import sys
from typing import Dict, Any, Optional, List, Type
from pathlib import Path

# 尝试导入基本日志/配置，如果不存在则使用默认行为
try:
    from utils.logger import get_logger
    logger = get_logger(__name__)
except ImportError:
    # 简易替补日志
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

try:
    from utils.config_manager import ConfigMixin
except ImportError:
    class ConfigMixin:
        """简易配置混合类，避免依赖缺失"""
        @classmethod
        def get_default_config(cls):
            return {}

# ------------------- 方言模块基类 -------------------
class DialectModule(ConfigMixin):
    """
    方言模块抽象基类，所有具体方言必须实现。
    可插拔设计：每个方言是一个独立模块文件，动态加载。
    """
    # 方言标识符
    dialect_id: str = "base"
    # 方言名称
    dialect_name: str = "基础方言"
    # 方言描述
    dialect_description: str = ""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化方言模块
        :param config: 模块配置字典，覆盖默认配置
        """
        self.config = self.get_default_config()
        if config:
            self.config.update(config)
        logger.info(f"初始化方言模块: {self.dialect_id} ({self.dialect_name})")

    def transform(self, text: str, intensity: float = 0.5, **kwargs) -> str:
        """
        将输入文本转换为方言风格
        :param text: 输入文本
        :param intensity: 方言转换强度，0-1，0为微弱，1为强方言
        :param kwargs: 其他参数
        :return: 方言化后的文本
        """
        raise NotImplementedError("子类必须实现transform方法")

    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """返回默认配置字典"""
        return {
            "enable": True,
            "default_intensity": 0.5,
            "word_replace_prob": 0.3,  # 词语替换概率
            "sentence_pattern_prob": 0.2,  # 句式调整概率
        }

    def describe(self) -> Dict[str, Any]:
        """返回模块元数据"""
        return {
            "id": self.dialect_id,
            "name": self.dialect_name,
            "description": self.dialect_description,
            "config": self.config,
        }

# ------------------- 方言管理系统 -------------------
class DialectManager(ConfigMixin):
    """
    方言管理器，负责方言模块的注册、加载、调用。
    提供统一接口：apply_dialect(text, dialect_id, intensity, **kwargs)
    支持热更新：动态加载模块目录下的.py文件
    """
    # 内置方言存储库
    _dialect_registry: Dict[str, Type[DialectModule]] = {}
    # 已实例化的方言对象缓存
    _dialect_instances: Dict[str, DialectModule] = {}

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = self.get_default_config()
        if config:
            self.config.update(config)
        self.modules_dir = self.config.get("modules_dir", "dialects")
        logger.info("方言管理器初始化完成")
        # 启动时自动加载内置方言目录
        self._auto_discover_modules()

    def _auto_discover_modules(self):
        """自动发现并加载方言模块目录下的有效方言"""
        modules_path = Path(self.modules_dir)
        if not modules_path.exists():
            logger.warning(f"方言模块目录不存在: {modules_path.absolute()}, 跳过自动发现")
            return
        sys.path.insert(0, str(modules_path.parent))  # 确保包能导
        for file in modules_path.glob("*.py"):
            if file.name.startswith("_"):
                continue
            module_name = file.stem
            try:
                # 动态导入模块
                module = importlib.import_module(f"{self.modules_dir}.{module_name}")
                # 查找继承自DialectModule的子类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, DialectModule) and attr is not DialectModule:
                        self.register_dialect_class(attr)
                        logger.info(f"自动发现并注册方言: {attr.dialect_id}")
            except Exception as e:
                logger.error(f"加载方言模块 {module_name} 失败: {e}")

    def register_dialect_class(self, dialect_cls: Type[DialectModule]):
        """注册方言类"""
        if not issubclass(dialect_cls, DialectModule):
            raise TypeError(f"{dialect_cls} 不是 DialectModule 的子类")
        dialect_id = dialect_cls.dialect_id
        self._dialect_registry[dialect_id] = dialect_cls
        logger.info(f"注册方言类: {dialect_id}")

    def get_dialect(self, dialect_id: str) -> Optional[DialectModule]:
        """
        获取或实例化一个方言对象（带缓存）
        :param dialect_id: 方言标识
        :return: 方言对象实例，若不存在返回None
        """
        if dialect_id in self._dialect_instances:
            return self._dialect_instances[dialect_id]
        if dialect_id not in self._dialect_registry:
            logger.error(f"未找到方言: {dialect_id}")
            return None
        cls = self._dialect_registry[dialect_id]
        # 从全局配置中获取该方言的特定配置（可选）
        dialect_config = self.config.get("dialect_configs", {}).get(dialect_id, {})
        instance = cls(config=dialect_config)
        self._dialect_instances[dialect_id] = instance
        logger.info(f"创建方言实例: {dialect_id}")
        return instance

    def apply_dialect(self, text: str, dialect_id: str, intensity: Optional[float] = None, **kwargs) -> str:
        """
        应用方言转换
        :param text: 输入文本
        :param dialect_id: 方言ID
        :param intensity: 强度，若为None则使用配置或默认
        :return: 转换后文本
        """
        dialect = self.get_dialect(dialect_id)
        if dialect is None:
            logger.warning(f"方言{dialect_id}不可用，返回原文")
            return text
        if intensity is None:
            intensity = dialect.config.get("default_intensity", 0.5)
        try:
            result = dialect.transform(text, intensity=intensity, **kwargs)
            logger.debug(f"应用方言{dialect_id}强度{intensity}成功")
            return result
        except Exception as e:
            logger.error(f"方言{dialect_id}转换失败: {e}")
            return text  # 故障回退原文

    def list_dialects(self) -> List[Dict[str, Any]]:
        """列出所有已注册方言的描述"""
        return [self.get_dialect(did).describe() for did in self._dialect_registry if self.get_dialect(did)]

    def get_default_config(cls) -> Dict[str, Any]:
        return {
            "modules_dir": "dialects",
            "dialect_configs": {},
        }

# ------------------- 示例方言模块（最小实现） -------------------
class NorthEasternDialect(DialectModule):
    """东北方言示例模块"""
    dialect_id = "northeastern"
    dialect_name = "东北话"
    dialect_description = "带有浓厚的东北地域特色，词汇诙谐"

    def transform(self, text: str, intensity: float = 0.5, **kwargs) -> str:
        # 此处为骨架，实际逻辑将在后期填充
        # 目前仅做简单示意：根据强度随机替换几个典型词汇
        import random
        # 北方词汇库
        replacements = [
            ("什么", "啥"),
            ("你", "恁"),
            ("我", "俺"),
            ("很", "贼"),
            ("没有", "没得"),
        ]
        result = text
        for orig, replacement in replacements:
            if random.random() < intensity * 0.3:  # 概率替换
                result = result.replace(orig, replacement)
        return result

# ------------------- 自测部分 -------------------
def self_test():
    """方言系统自测函数，验证基本功能和可插拔性"""
    print("=== 方言系统自测开始 ===")
    # 创建管理器实例
    manager = DialectManager()
    # 注册示例方言
    manager.register_dialect_class(NorthEasternDialect)

    # 测试方言列表
    dialects = manager.list_dialects()
    print(f"已注册方言: {[d['id'] for d in dialects]}")

    # 测试方言转换
    test_text = "我觉得你真的很厉害，什么都会。"
    result_none = manager.apply_dialect(test_text, "northeastern", intensity=0.0)
    result_high = manager.apply_dialect(test_text, "northeastern", intensity=0.9)
    print(f"原文: {test_text}")
    print(f"强度0: {result_none}")
    print(f"强度0.9: {result_high}")

    # 测试未注册方言返回原文
    result_unknown = manager.apply_dialect(test_text, "unknown")
    print(f"未知方言: {result_unknown}")

    print("=== 方言系统自测通过 ===")
    return True

if __name__ == "__main__":
    self_test()