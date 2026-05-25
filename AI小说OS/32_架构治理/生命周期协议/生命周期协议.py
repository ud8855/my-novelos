"""
32_架构治理/生命周期协议/lifecycle_protocol.py
定义系统核心组件的生命周期管理协议，确保所有组件遵循统一的生命周期状态机。
实现可插拔的生命周期钩子、事件通知、状态转换约束，并提供日志与配置化支持。
"""
import logging
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Dict, Any, Optional, List, Callable
from threading import Lock


class LifecycleState(Enum):
    """
    生命周期状态枚举
    """
    UNINITIALIZED = auto()   # 未初始化
    INITIALIZING = auto()    # 初始化中
    INITIALIZED = auto()     # 已初始化
    STARTING = auto()        # 启动中
    RUNNING = auto()         # 运行中
    PAUSING = auto()         # 暂停中
    PAUSED = auto()          # 已暂停
    RESUMING = auto()        # 恢复中
    STOPPING = auto()        # 停止中
    STOPPED = auto()         # 已停止
    DESTROYING = auto()      # 销毁中
    DESTROYED = auto()       # 已销毁
    ERROR = auto()           # 错误状态


# 合法的状态转换表，用于校验
VALID_TRANSITIONS: Dict[LifecycleState, List[LifecycleState]] = {
    LifecycleState.UNINITIALIZED: [LifecycleState.INITIALIZING],
    LifecycleState.INITIALIZING: [LifecycleState.INITIALIZED, LifecycleState.ERROR],
    LifecycleState.INITIALIZED: [LifecycleState.STARTING, LifecycleState.DESTROYING],
    LifecycleState.STARTING: [LifecycleState.RUNNING, LifecycleState.ERROR],
    LifecycleState.RUNNING: [LifecycleState.PAUSING, LifecycleState.STOPPING, LifecycleState.ERROR],
    LifecycleState.PAUSING: [LifecycleState.PAUSED, LifecycleState.ERROR],
    LifecycleState.PAUSED: [LifecycleState.RESUMING, LifecycleState.STOPPING, LifecycleState.DESTROYING],
    LifecycleState.RESUMING: [LifecycleState.RUNNING, LifecycleState.ERROR],
    LifecycleState.STOPPING: [LifecycleState.STOPPED, LifecycleState.ERROR],
    LifecycleState.STOPPED: [LifecycleState.DESTROYING, LifecycleState.STARTING],  # 允许从停止再启动
    LifecycleState.DESTROYING: [LifecycleState.DESTROYED, LifecycleState.ERROR],
    LifecycleState.DESTROYED: [],  # 终态，不可转换
    LifecycleState.ERROR: [LifecycleState.DESTROYING]  # 通常需要安全销毁
}


class LifecycleListener(ABC):
    """
    生命周期事件监听器接口。
    其他组件可实现此接口以接收生命周期状态变更通知。
    """
    
    @abstractmethod
    def on_state_change(self, component_id: str, old_state: LifecycleState, new_state: LifecycleState) -> None:
        """
        当组件生命周期状态发生变更时调用。
        
        Args:
            component_id: 组件标识
            old_state: 旧状态
            new_state: 新状态
        """
        ...


class LifecycleProtocol(ABC):
    """
    生命周期协议抽象基类。
    所有需要统一生命周期管理的核心组件必须实现此协议。
    定义了标准的状态机流转方法和钩子，确保组件的初始化、启动、暂停、恢复、停止、销毁行为一致。
    """
    
    def __init__(self, component_id: str, config: Optional[Dict[str, Any]] = None):
        """
        初始化生命周期协议实例。
        
        Args:
            component_id: 组件唯一标识
            config: 配置字典，用于控制生命周期行为（如超时、重试等）
        """
        self.component_id: str = component_id
        self.state: LifecycleState = LifecycleState.UNINITIALIZED
        self.config: Dict[str, Any] = config or {}
        self.logger: logging.Logger = logging.getLogger(f"Lifecycle.{component_id}")
        self._lock: Lock = Lock()  # 状态变更线程安全
        
        # 事件监听器集合
        self._listeners: List[LifecycleListener] = []
        
        # 从配置中读取可选参数
        self.auto_start: bool = self.config.get("auto_start", False)
        self.init_timeout: int = self.config.get("init_timeout", 30)
    
    def add_listener(self, listener: LifecycleListener) -> None:
        """注册生命周期事件监听器"""
        if listener not in self._listeners:
            self._listeners.append(listener)
    
    def remove_listener(self, listener: LifecycleListener) -> None:
        """移除生命周期事件监听器"""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    def _notify_listeners(self, old_state: LifecycleState, new_state: LifecycleState) -> None:
        """通知所有监听器状态变更"""
        for listener in self._listeners:
            try:
                listener.on_state_change(self.component_id, old_state, new_state)
            except Exception as e:
                self.logger.error(f"Notifying listener {listener} failed: {e}")
    
    def _transition_to(self, target_state: LifecycleState) -> bool:
        """
        执行状态转换（受锁保护），并校验合法性，成功后通知监听器。
        
        Args:
            target_state: 目标状态
        
        Returns:
            转换成功返回True，否则False
        """
        with self._lock:
            old_state = self.state
            # 校验转换合法性
            allowed = VALID_TRANSITIONS.get(old_state, [])
            if target_state not in allowed:
                self.logger.error(
                    f"Invalid state transition from {old_state.name} to {target_state.name}. "
                    f"Allowed: {[s.name for s in allowed]}"
                )
                return False
            
            self.state = target_state
            self.logger.info(f"State transition: {old_state.name} -> {target_state.name}")
        
        # 通知监听器（在锁外处理，避免死锁）
        try:
            self._notify_listeners(old_state, target_state)
        except Exception as e:
            self.logger.warning(f"Listener notification failed: {e}")
        
        return True
    
    # --------------------------------------------------------------------------
    # 抽象钩子方法，子类必须实现具体的业务逻辑
    # --------------------------------------------------------------------------
    
    @abstractmethod
    def _do_initialize(self) -> Optional[Any]:
        """
        执行具体的初始化逻辑（加载资源、建立连接等）。
        
        Returns:
            初始化结果或资源标识，若抛出异常则视为失败
        """
        ...
    
    @abstractmethod
    def _do_start(self) -> None:
        """开始实际工作（线程/进程启动，开始接收请求等）"""
        ...
    
    @abstractmethod
    def _do_pause(self) -> None:
        """暂停工作流程（保留状态，但停止处理新请求）"""
        ...
    
    @abstractmethod
    def _do_resume(self) -> None:
        """从暂停状态恢复"""
        ...
    
    @abstractmethod
    def _do_stop(self) -> None:
        """停止工作（持久化状态，关闭资源，退出线程等）"""
        ...
    
    @abstractmethod
    def _do_destroy(self) -> None:
        """彻底销毁，释放所有资源"""
        ...
    
    # --------------------------------------------------------------------------
    # 公共控制方法，这些方法不可被子类覆盖，确保状态机正确流转
    # --------------------------------------------------------------------------
    
    def initialize(self) -> bool:
        """
        初始化组件：从 UNINITIALIZED -> INITIALIZING -> INITIALIZED
        会调用 _do_initialize()，成功则转换到 INITIALIZED。
        
        Returns:
            初始化成功返回True，否则False
        """
        if not self._transition_to(LifecycleState.INITIALIZING):
            return False
        
        try:
            # 调用具体初始化
            res = self._do_initialize()
            self.logger.info(f"Initialize succeeded, resource: {res}")
        except Exception as e:
            self.logger.error(f"Initialize failed: {e}", exc_info=True)
            self._transition_to(LifecycleState.ERROR)
            return False
        
        return self._transition_to(LifecycleState.INITIALIZED)
    
    def start(self) -> bool:
        """
        启动组件：从 INITIALIZED -> STARTING -> RUNNING 或从 STOPPED -> STARTING -> RUNNING
        """
        with self._lock:
            current = self.state
        if current not in (LifecycleState.INITIALIZED, LifecycleState.STOPPED):
            self.logger.error(f"Cannot start from state {current.name}")
            return False
        
        if not self._transition_to(LifecycleState.STARTING):
            return False
        
        try:
            self._do_start()
        except Exception as e:
            self.logger.error(f"Start failed: {e}", exc_info=True)
            self._transition_to(LifecycleState.ERROR)
            return False
        
        return self._transition_to(LifecycleState.RUNNING)
    
    def pause(self) -> bool:
        """暂停组件：RUNNING -> PAUSING -> PAUSED"""
        if self.state != LifecycleState.RUNNING:
            self.logger.error(f"Cannot pause from state {self.state.name}")
            return False
        
        if not self._transition_to(LifecycleState.PAUSING):
            return False
        
        try:
            self._do_pause()
        except Exception as e:
            self.logger.error(f"Pause failed: {e}", exc_info=True)
            self._transition_to(LifecycleState.ERROR)
            return False
        
        return self._transition_to(LifecycleState.PAUSED)
    
    def resume(self) -> bool:
        """恢复组件：PAUSED -> RESUMING -> RUNNING"""
        if self.state != LifecycleState.PAUSED:
            self.logger.error(f"Cannot resume from state {self.state.name}")
            return False
        
        if not self._transition_to(LifecycleState.RESUMING):
            return False
        
        try:
            self._do_resume()
        except Exception as e:
            self.logger.error(f"Resume failed: {e}", exc_info=True)
            self._transition_to(LifecycleState.ERROR)
            return False
        
        return self._transition_to(LifecycleState.RUNNING)
    
    def stop(self) -> bool:
        """停止组件：RUNNING/PAUSED -> STOPPING -> STOPPED"""
        with self._lock:
            current = self.state
        if current not in (LifecycleState.RUNNING, LifecycleState.PAUSED):
            self.logger.error(f"Cannot stop from state {current.name}")
            return False
        
        if not self._transition_to(LifecycleState.STOPPING):
            return False
        
        try:
            self._do_stop()
        except Exception as e:
            self.logger.error(f"Stop failed: {e}", exc_info=True)
            self._transition_to(LifecycleState.ERROR)
            return False
        
        return self._transition_to(LifecycleState.STOPPED)
    
    def destroy(self) -> bool:
        """销毁组件：从任何非终态安全转为DESTROYING -> DESTROYED"""
        with self._lock:
            current = self.state
        # 允许从多个状态销毁，排除终态
        if current == LifecycleState.DESTROYED:
            self.logger.warning("Already destroyed")
            return True
        if current == LifecycleState.DESTROYING:
            self.logger.warning("Destroy already in progress")
            return False
        
        # 强行进入 DESTROYING（不通过标准转换表，这是一种强制路径，但我们仍使用_transition_to以保持日志和通知）
        # 但我们也可以允许用于紧急处理。这里为了遵循架构，仍通过_transition_to，但由于转换表可能不允许，我们需临时允许？
        # 根据设计，ERROR状态可转为DESTROYING，其他状态可能需要先停止？但为了安全销毁，我们可定义：如果不在表中，直接设置状态并记录。
        allowed = VALID_TRANSITIONS.get(current, [])
        if LifecycleState.DESTROYING not in allowed: