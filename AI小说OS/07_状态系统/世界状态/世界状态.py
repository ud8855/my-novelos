# 07_状态系统/世界状态/世界状态.py
# 功能：世界状态管理接口和基础实现，提供可插拔的世界状态存储与更新能力
# 层级：07_状态系统层，依赖无（标准库），被上层模块调用（如11_剧情引擎层、12_事件系统层）
# 约束：仅提供接口定义和简单内存实现，禁止包含业务逻辑

import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

# -------------------------- 配置与日志初始化 -------------------------- #
class WorldStateConfig:
    """世界状态模块配置，所有参数可通过环境变量覆盖。"""
    def __init__(self):
        self.log_level = os.getenv("WORLD_STATE_LOG_LEVEL", "INFO")
        self.default_initial_state: Dict[str, Any] = {
            "timeline": "before_story",
            "locations": {},
            "characters": {},
            "events": [],
            "metaphysics": {"magic_system": None, "laws_of_physics": "realistic"},
            "relationships": {}
        }

def setup_logging(config: WorldStateConfig) -> logging.Logger:
    """初始化日志记录器，为模块提供统一的日志出口。"""
    logger = logging.getLogger("WorldState")
    logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s] %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

# 加载默认配置并初始化日志
_default_config = WorldStateConfig()
_logger = setup_logging(_default_config)

# -------------------------- 抽象接口定义 -------------------------- #
class WorldStateInterface(ABC):
    """世界状态抽象接口，所有具体实现必须继承此类。"""

    @abstractmethod
    def get_state(self) -> Dict[str, Any]:
        """获取完整的世界状态快照。"""
        pass

    @abstractmethod
    def get_field(self, key: str, default: Any = None) -> Any:
        """获取状态中的某个字段值。"""
        pass

    @abstractmethod
    def set_field(self, key: str, value: Any) -> None:
        """设置或更新状态中的某个字段。"""
        pass

    @abstractmethod
    def update_state(self, patch: Dict[str, Any]) -> None:
        """通过补丁字典批量更新状态。"""
        pass

    @abstractmethod
    def reset_state(self) -> None:
        """将世界状态重置为初始值。"""
        pass

# -------------------------- 基础内存实现 -------------------------- #
class SimpleWorldState(WorldStateInterface):
    """基于内存字典的简单世界状态实现，支持热插拔替换。"""

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        self._state = initial_state.copy() if initial_state else _default_config.default_initial_state.copy()
        _logger.info("SimpleWorldState 初始化完成，状态键数: %d", len(self._state))

    def get_state(self) -> Dict[str, Any]:
        _logger.debug("获取完整世界状态")
        return self._state.copy()  # 返回副本防止外部意外修改

    def get_field(self, key: str, default: Any = None) -> Any:
        _logger.debug("获取字段: %s", key)
        return self._state.get(key, default)

    def set_field(self, key: str, value: Any) -> None:
        _logger.info("设置字段: %s = %s", key, str(value)[:100])
        self._state[key] = value

    def update_state(self, patch: Dict[str, Any]) -> None:
        _logger.info("批量更新状态，键: %s", list(patch.keys()))
        self._state.update(patch)

    def reset_state(self) -> None:
        _logger.warning("重置世界状态为默认值")
        self._state = _default_config.default_initial_state.copy()

# -------------------------- 工厂函数（可插拔入口） -------------------------- #
_global_world_state: Optional[WorldStateInterface] = None

def get_world_state(implementation_class: Optional[type] = None,
                    **kwargs) -> WorldStateInterface:
    """
    获取世界状态实例（单例模式支持），可动态指定实现类。
    如果未指定，默认使用 SimpleWorldState。
    """
    global _global_world_state
    if _global_world_state is not None and implementation_class is None:
        return _global_world_state

    if implementation_class is None:
        implementation_class = SimpleWorldState

    if not issubclass(implementation_class, WorldStateInterface):
        raise TypeError(f"{implementation_class} 必须实现 WorldStateInterface")

    _global_world_state = implementation_class(**kwargs)
    _logger.info("世界状态实例已创建: %s", implementation_class.__name__)
    return _global_world_state

def reset_global_instance() -> None:
    """重置全局实例（用于测试或热更新）。"""
    global _global_world_state
    _global_world_state = None
    _logger.info("全局世界状态实例已重置")

# -------------------------- 自测代码 -------------------------- #
if __name__ == "__main__":
    print("=== 世界状态模块自检开始 ===")
    # 手动开启调试日志以观察过程
    _logger.setLevel(logging.DEBUG)

    # 测试默认实现
    ws = get_world_state()
    assert isinstance(ws, SimpleWorldState), "默认应为 SimpleWorldState"
    print("初始状态字段:", list(ws.get_state().keys()))

    # 更新字段
    ws.set_field("timeline", "chapter_1")
    assert ws.get_field("timeline") == "chapter_1", "设置字段失败"
    print("时间线已更新:", ws.get_field("timeline"))

    # 批量更新
    ws.update_state({"locations": {"castle": "dark and gloomy"}})
    assert ws.get_field("locations")["castle"] == "dark and gloomy"
    print("地点更新成功:", ws.get_field("locations"))

    # 重置
    ws.reset_state()
    assert ws.get_field("timeline") == "before_story", "重置失败"
    print("重置后的时间线:", ws.get_field("timeline"))

    # 测试插拔：定义一个模拟的其它实现（这里简单继承 SimpleWorldState 以通过检查）
    class CustomWorldState(SimpleWorldState):
        pass

    reset_global_instance()
    ws2 = get_world_state(implementation_class=CustomWorldState)
    assert isinstance(ws2, CustomWorldState), "动态实现更换失败"
    print("动态实现更换成功")

    print("=== 世界状态模块自检通过 ===")