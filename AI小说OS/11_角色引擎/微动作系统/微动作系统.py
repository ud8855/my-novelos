"""微动作系统骨架代码
层级：11_角色引擎/微动作系统
职责：管理角色在特定上下文中的微动作（眼神、手势、小动作等）的生成、触发与调度。
依赖：角色状态上下文（由上层传入），配置模块（本层内）
被调用：角色行为引擎、对话系统等需要展现角色细节时调用。
设计原则：可插拔提供者、配置化、日志记录、异常保护、热更新支持
"""

import logging
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import yaml  # 需要安装PyYAML，实际骨架依赖轻量
import importlib
import time

# ------------------------------
# 日志系统配置
# ------------------------------
logger = logging.getLogger("MicroActionSystem")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.DEBUG)

# ------------------------------
# 配置管理
# ------------------------------
class MicroActionConfig:
    """微动作系统配置容器，支持从外部文件或字典加载，支持热更新"""
    def __init__(self, config_source: Optional[str] = None):
        self._config: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._last_load_time: float = 0.0
        if config_source:
            self.load(config_source)

    def load(self, source: str):
        """从YAML/JSON文件或字典加载配置。source可以是文件路径或字典对象"""
        with self._lock:
            try:
                if isinstance(source, str):
                    with open(source, 'r', encoding='utf-8') as f:
                        self._config = yaml.safe_load(f) or {}
                elif isinstance(source, dict):
                    self._config = source.copy()
                else:
                    raise TypeError("Config source must be a file path or dict")
                self._last_load_time = time.time()
                logger.info("Configuration loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}", exc_info=True)
                # 保留旧配置，不崩溃
                raise

    def reload(self) -> bool:
        """尝试从同一来源重新加载配置（如果已知来源）"""
        # 此处简化处理，实际需保存源路径
        logger.warning("Reload not fully implemented in skeleton.")
        return False

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._config.get(key, default)

    def set(self, key: str, value: Any):
        with self._lock:
            self._config[key] = value
            logger.debug(f"Config updated: {key} = {value}")

    @property
    def last_load_time(self) -> float:
        return self._last_load_time

# ------------------------------
# 微动作提供者抽象
# ------------------------------
class BaseMicroActionProvider(ABC):
    """微动作提供者抽象基类。所有自定义提供者必须继承此类并实现generate方法"""
    def __init__(self, name: str, priority: int = 100):
        self.name = name
        self.priority = priority  # 值越小优先级越高
        logger.debug(f"Provider '{self.name}' initialized with priority {self.priority}")

    @abstractmethod
    def generate(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        根据上下文生成一个微动作描述。
        返回：{'type': 'gesture', 'description': '握拳', 'intensity': 0.8} 或 None
        """
        pass

    def pre_check(self, context: Dict[str, Any]) -> bool:
        """可选：检查上下文是否满足该提供者的条件，默认返回True"""
        return True

    def post_process(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """可选：对动作进行后处理"""
        return action

# ------------------------------
# 微动作系统主引擎
# ------------------------------
class MicroActionSystem:
    """微动作系统：管理提供者、协调调用、记录日志、提供热插拔"""
    def __init__(self, config: Optional[MicroActionConfig] = None):
        self.config = config if config else MicroActionConfig()
        self._providers: List[BaseMicroActionProvider] = []
        self._lock = threading.RLock()
        self._initialized = False
        self._active = False

    def initialize(self, providers_config: Optional[List[Dict[str, Any]]] = None):
        """根据配置加载提供者。providers_config: [{'name':..., 'module':..., 'class':..., 'priority':...}]"""
        with self._lock:
            try:
                if providers_config is None:
                    # 从配置文件获取提供者列表
                    providers_config = self.config.get('providers', [])
                for p_cfg in providers_config:
                    self._load_provider(p_cfg)
                self._initialized = True
                self._active = True
                logger.info(f"MicroActionSystem initialized with {len(self._providers)} providers.")
            except Exception as e:
                logger.error(f"Initialization failed: {e}", exc_info=True)
                raise RuntimeError("MicroActionSystem initialization failure") from e

    def _load_provider(self, provider_cfg: Dict[str, Any]):
        """动态加载一个提供者插件"""
        module_name = provider_cfg.get('module')
        class_name = provider_cfg.get('class')
        if not module_name or not class_name:
            logger.warning(f"Invalid provider config: {provider_cfg}")
            return
        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, class_name)
            instance = cls(name=provider_cfg.get('name', class_name),
                           priority=provider_cfg.get('priority', 100))
            self.register_provider(instance)
        except Exception as e:
            logger.error(f"Failed to load provider {class_name}: {e}", exc_info=True)

    def register_provider(self, provider: BaseMicroActionProvider):
        """手动注册一个提供者"""
        with self._lock:
            if not isinstance(provider, BaseMicroActionProvider):
                raise TypeError("Provider must be an instance of BaseMicroActionProvider")
            # 保持按优先级排序
            self._providers.append(provider)
            self._providers.sort(key=lambda p: p.priority)
            logger.info(f"Provider '{provider.name}' registered.")

    def unregister_provider(self, provider_name: str):
        """移除一个提供者"""
        with self._lock:
            removed = [p for p in self._providers if p.name == provider_name]
            for p in removed:
                self._providers.remove(p)
                logger.info(f"Provider '{p.name}' unregistered.")

    def get_micro_action(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        根据上下文获取最合适的微动作。
        遍历所有提供者，返回第一个通过pre_check且generate非空的提供者结果。
        支持异常恢复：单个提供者失败不影响整体。
        """
        if not self._active:
            logger.warning("MicroActionSystem is not active, returning None.")
            return None

        with self._lock:
            # 快照提供者列表，避免遍历时修改
            providers = self._providers.copy()

        for provider in providers:
            try:
                if not provider.pre_check(context):
                    continue
                action = provider.generate(context)
                if action is not None:
                    action = provider.post_process(action)
                    logger.debug(f"Micro action generated by '{provider.name}': {action.get('type')}")
                    return action
            except Exception as e:
                logger.error(f"Provider '{provider.name}' encountered error: {e}", exc_info=True)
                # 继续下一个提供者
                continue

        logger.debug("No micro action generated for context.")
        return None

    def hot_swap_config(self, new_config_source: Any):
        """热更新配置（保留提供者，仅更新配置值）"""
        try:
            self.config.load(new_config_source)
            logger.info("Configuration hot swapped.")
        except Exception as e:
            logger.error(f"Hot swap failed: {e}")

    def shutdown(self):
        """关闭系统，清理资源"""
        with self._lock:
            self._active = False
            self._providers.clear()
        logger.info("MicroActionSystem shut down.")

# ------------------------------
# 自测模块（当直接运行此脚本时执行）
# ------------------------------
if __name__ == "__main__":
    print("=== 微动作系统自检开始 ===")
    # 1. 准备测试配置（内存字典）
    test_config = {
        'providers': [
            {
                'name': 'test_provider',
                'module': '微动作系统',  # 指向自身，用于演示
                'class': 'SimpleTestProvider',
                'priority': 10
            }
        ]
    }

    # 2. 定义一个简单的测试提供者（内嵌）
    class SimpleTestProvider(BaseMicroActionProvider):
        def generate(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            if context.get("mood") == "angry":
                return {"type": "gesture", "description": "握拳", "intensity": 0.9}
            elif context.get("mood") == "happy":
                return {"type": "expression", "description": "微笑", "intensity": 0.5}
            return None

    # 3. 手动将测试提供者注册到系统中，跳过动态加载
    system = MicroActionSystem()
    system.register_provider(SimpleTestProvider(name="test_provider", priority=10))
    system._active = True  # 模拟初始化完成

    # 4. 测试场景
    context1 = {"mood": "angry", "personality": "aggressive"}
    action1 = system.get_micro_action(context1)
    print(f"上下文1（愤怒）-> 微动作: {action1}")

    context2 = {"mood": "happy", "personality": "friendly"}
    action2 = system.get_micro_action(context2)
    print(f"上下文2（开心）-> 微动作: {action2}")

    context3 = {"mood": "neutral"}
    action3 = system.get_micro_action(context3)
    print(f"上下文3（中性）-> 微动作: {action3}")

    # 5. 异常恢复测试：注册一个会抛出异常的提供者
    class FaultyProvider(BaseMicroActionProvider):
        def generate(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            raise RuntimeError("故意抛出异常")
    system.register_provider(FaultyProvider(name="faulty", priority=5))
    action_ex = system.get_micro_action({"mood": "sad"})
    print