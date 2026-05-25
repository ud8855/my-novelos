"""
战斗状态模块

职责：
    - 管理战斗中所有动态状态（角色状态、回合阶段、技能冷却、buff/debuff等）
    - 提供状态变更、查询、事件触发接口
    - 支持状态处理器的热插拔注册
    - 所有状态变更记录日志，支持配置化调整行为

依赖：
    - 基础日志模块（logging内置，遵循系统日志规范）
    - 配置模块（可从 `config` 或 `os.environ` 读取）
    - 状态协议接口（本模块定义抽象基类 `BaseCombatState`）

被调用者：
    - 战斗引擎（`08_战斗引擎/`）
    - AI决策模块（`12_决策系统/`）
    - UI渲染层（`30_前端展示/` 通过事件管道间接通知）

设计原则：
    - 单一职责：只负责战斗维度的状态存储与生命周期管理
    - 可插拔：通过 `register_state` 动态加载具体状态实现
    - 配置化：关键参数从外部配置注入，允许运行时调整
    - 可观测：所有操作带结构化日志
"""

import logging
import inspect
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

# ------------------------------
# 配置读取（可替换为统一配置中心）
# ------------------------------
def _load_config() -> Dict[str, Any]:
    """从环境变量或本地配置文件加载战斗状态相关配置"""
    return {
        "tick_rate": float(os.getenv("COMBAT_TICK_RATE", 0.1)),
        "max_states_history": int(os.getenv("COMBAT_MAX_HISTORY", 100)),
        "log_level": os.getenv("COMBAT_LOG_LEVEL", "INFO"),
        "enable_mutation_tracking": os.getenv("COMBAT_TRACK_MUTATIONS", "true").lower() == "true",
    }

# ------------------------------
# 日志初始化（遵循系统统一日志格式）
# ------------------------------
def _init_logger() -> logging.Logger:
    logger = logging.getLogger("CombatState")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s | %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    config = _load_config()
    logger.setLevel(getattr(logging, config["log_level"].upper(), logging.INFO))
    return logger

logger = _init_logger()

# ------------------------------
# 状态抽象基类（协议）
# ------------------------------
class BaseCombatState(ABC):
    """所有战斗子状态的基类，定义统一接口"""
    state_name: str = "base"   # 状态类型标识

    @abstractmethod
    def on_enter(self, context: "CombatStateManager") -> None:
        """进入状态时调用"""
        ...

    @abstractmethod
    def on_exit(self, context: "CombatStateManager") -> None:
        """退出状态时调用"""
        ...

    @abstractmethod
    def update(self, delta_time: float, context: "CombatStateManager") -> None:
        """每逻辑帧更新"""
        ...

    def serialize(self) -> Dict[str, Any]:
        """序列化为可持久化字典（子类可选覆盖）"""
        return {"state_name": self.state_name}

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "BaseCombatState":
        """从字典反序列化，子类必须实现"""
        raise NotImplementedError("deserialize must be implemented by subclass")

# ------------------------------
# 战斗状态管理器
# ------------------------------
class CombatStateManager:
    """
    战斗状态管理核心

    特性：
    - 维护一个当前激活的主状态，以及多个平行子状态（如buff系统）
    - 所有状态变更通过事件钩子通知外部
    - 支持历史记录与回滚（预览功能）
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or _load_config()
        self.tick_rate = self.config["tick_rate"]
        self.max_history = self.config["max_states_history"]
        self.enable_mutation_tracking = self.config["enable_mutation_tracking"]

        self._current_main_state: Optional[BaseCombatState] = None
        self._sub_states: Dict[str, BaseCombatState] = {}
        self._state_registry: Dict[str, Type[BaseCombatState]] = {}
        self._history: List[Dict[str, Any]] = []   # 简单的变更日志

        # 外部监听器列表（可注入UI、AI等）
        self.on_state_changed_callbacks: List[callable] = []

        logger.info("CombatStateManager initialized (tick_rate=%.2f, max_history=%d)",
                     self.tick_rate, self.max_history)

    # --- 注册与发现 ---
    def register_state(self, state_name: str, state_cls: Type[BaseCombatState], override: bool = False) -> None:
        """
        注册一个状态类型
        :param state_name: 状态唯一标识
        :param state_cls: 状态实现类
        :param override: 是否允许覆盖已存在注册
        """
        if not issubclass(state_cls, BaseCombatState):
            raise TypeError(f"{state_cls} must be a subclass of BaseCombatState")
        if state_name in self._state_registry and not override:
            raise ValueError(f"State '{state_name}' already registered. Use override=True to force.")
        self._state_registry[state_name] = state_cls
        logger.debug("Registered combat state: %s -> %s", state_name, state_cls.__name__)

    def unregister_state(self, state_name: str) -> None:
        """移除状态类型注册"""
        if state_name in self._state_registry:
            del self._state_registry[state_name]
            logger.debug("Unregistered combat state: %s", state_name)

    def list_registered_states(self) -> List[str]:
        return list(self._state_registry.keys())

    def _instantiate_state(self, state_name: str, **kwargs) -> BaseCombatState:
        """根据注册名创建状态实例"""
        cls = self._state_registry.get(state_name)
        if not cls:
            raise KeyError(f"Unknown state name: {state_name}")
        return cls(**kwargs)

    # --- 主状态控制 ---
    @property
    def current_state(self) -> Optional[BaseCombatState]:
        return self._current_main_state

    def transition_to(self, new_state_name: str, **state_kwargs) -> None:
        """
        切换到新主状态（安全转换）
        流程：旧状态 on_exit -> 新状态实例化 -> 新状态 on_enter -> 触发回调
        """
        if self._current_main_state is not None:
            old_state_name = self._current_main_state.state_name
            logger.info("Transitioning main state: %s -> %s", old_state_name, new_state_name)
            self._current_main_state.on_exit(self)
            self._record_history("exit", old_state_name)
        else:
            logger.info("Entering initial main state: %s", new_state_name)

        new_state = self._instantiate_state(new_state_name, **state_kwargs)
        new_state.on_enter(self)
        self._current_main_state = new_state
        self._record_history("enter", new_state_name)
        self._notify_state_changed(old_state=old_state_name if self._current_main_state else None,
                                   new_state=new_state_name)

    def end_current_state(self) -> None:
        """结束当前主状态但不进入新状态（例如战斗结束）"""
        if self._current_main_state:
            logger.info("Ending main state: %s", self._current_main_state.state_name)
            self._current_main_state.on_exit(self)
            self._record_history("exit", self._current_main_state.state_name)
            old = self._current_main_state.state_name
            self._current_main_state = None
            self._notify_state_changed(old_state=old, new_state=None)

    # --- 子状态（平行系统，如全局buff）---
    def add_sub_state(self, unique_id: str, state_name: str, **kwargs) -> None:
        if unique_id in self._sub_states:
            logger.warning("Sub-state '%s' already exists, replacing.", unique_id)
            self.remove_sub_state(unique_id)
        state = self._instantiate_state(state_name, **kwargs)
        state.on_enter(self)
        self._sub_states[unique_id] = state
        logger.info("Added sub-state: %s (%s)", unique_id, state_name)

    def remove_sub_state(self, unique_id: str) -> None:
        if unique_id in self._sub_states:
            logger.info("Removing sub-state: %s", unique_id)
            self._sub_states[unique_id].on_exit(self)
            del self._sub_states[unique_id]

    def get_sub_state(self, unique_id: str) -> Optional[BaseCombatState]:
        return self._sub_states.get(unique_id)

    def update_all(self, delta_time: float) -> None:
        """驱动所有状态的 update 方法"""
        if self._current_main_state:
            self._current_main_state.update(delta_time, self)
        for sub in list(self._sub_states.values()):
            sub.update(delta_time, self)

    # --- 历史与监听 ---
    def _record_history(self, event_type: str, state_name: str) -> None:
        if not self.enable_mutation_tracking:
            return
        entry = {
            "time_step": len(self._history),
            "event": event_type,
            "state": state_name,
        }
        self._history.append(entry)
        if len(self._history) > self.max_history:
            self._history.pop(0)

    def get_history(self) -> List[Dict[str, Any]]:
        return self._history.copy()

    def subscribe_state_change(self, callback: callable) -> None:
        """注册状态变更监听器"""
        if not callable(callback):
            raise ValueError("Listener must be callable")
        self.on_state_changed_callbacks.append(callback)

    def unsubscribe_state_change(self, callback: callable) -> None:
        if callback in self.on_state_changed_callbacks:
            self.on_state_changed_callbacks.remove(callback)

    def _notify_state_changed(self, old_state: Optional[str], new_state: Optional[str]) -> None:
        for cb in self.on_state_changed_callbacks:
            try:
                cb(old_state, new_state, self)
            except Exception as e:
                logger.error("Error in state change callback %s: %s", cb.__name__, e, exc_info=True)

    # --- 序列化（快照）---
    def snapshot(self) -> Dict[str, Any]:
        """生成当前状态快照（用于存档/调试）"""
        snap = {
            "main_state": self._current_main_state.serialize() if self._current_main_state else None,
            "sub_states": {uid: st.serialize() for uid, st in self._sub_states.items()},
            "history_length": len(self._history),
        }
        return snap

    def restore_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """从快照恢复状态（注意：仅骨架，具体依赖子类实现）"""
        # 此功能需要更复杂的工厂反序列化，骨架阶段仅记录意图
        logger.warning("Snapshot restore is not fully implemented in skeleton.")

# ------------------------------------------------------------
# 自测部分（直接运行此文件即执行）
# ------------------------------------------------------------
if __name__ == "__main__":
    print("=== CombatState Skeleton Self-Test ===")

    # 示例具体状态类（用于测试插拔能力）
    class IdleState(BaseCombatState):
        state_name = "idle"
        def on_enter(self, ctx):
            print("Entering idle state")
        def on_exit(self, ctx):
            print("Exiting idle state")
        def update(self, dt, ctx):
            pass

    class BattleActiveState(BaseCombatState):
        state_name = "battle_active"
        def __init__(self, turn=1, **kwargs):
            super().__init