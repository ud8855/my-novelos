# 事件协议模块
# 位于 NovelOS/32_架构治理/事件协议
# 职责：定义系统内统一的事件消息格式、发布订阅协议、事件总线接口，
# 提供可插拔的事件总线实现（如SimpleEventBus），支持配置化日志和热插拔。

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Type

# ---- 配置数据类 ----
@dataclass
class EventBusConfig:
    """事件总线配置项（可被外部配置覆盖）"""
    bus_class: str = "SimpleEventBus"          # 事件总线实现类名
    max_event_history: int = 1000              # 历史事件最大保留数量
    enable_logging: bool = True                # 是否启用事件日志
    log_level: int = logging.INFO              # 日志级别
    async_mode: bool = False                   # 未来预留：是否使用异步分发
    extra_options: Dict[str, Any] = field(default_factory=dict)

# ---- 事件类型枚举 ----
class EventType(Enum):
    """系统预定义事件类型"""
    SYSTEM = auto()    # 系统级事件（启动、关闭、错误等）
    AGENT = auto()     # Agent 相关事件（任务开始、完成等）
    MODEL = auto()     # 模型调用相关
    UI = auto()        # 用户界面交互事件
    STORAGE = auto()   # 存储操作事件
    USER = auto()      # 用户自定义事件（扩展用）

# ---- 事件基础类 ----
@dataclass
class EventBase:
    """
    事件数据基类，所有事件应继承此类或直接使用。
    包含通用字段，支持自定义事件携带额外数据。
    """
    event_type: EventType              # 事件类型
    source: str                        # 事件来源模块标识
    payload: Any = None                # 事件携带的具体数据（可序列化）
    event_id: str = field(default_factory=lambda: f"evt_{int(time.time()*1000)}")
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转为可序列化字典"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.name,
            "source": self.source,
            "timestamp": self.timestamp,
            "payload": str(self.payload) if self.payload else None,
            "metadata": self.metadata,
        }

# ---- 事件处理函数类型 ----
EventHandler = Callable[[EventBase], None]

# ---- 事件总线抽象接口 ----
class EventBus(ABC):
    """
    事件总线抽象基类，定义发布/订阅协议。
    所有具体实现必须继承此类，保证可插拔。
    """
    @abstractmethod
    def publish(self, event: EventBase) -> None:
        """发布事件"""
        ...

    @abstractmethod
    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """订阅指定类型的事件"""
        ...

    @abstractmethod
    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """取消订阅"""
        ...

    @abstractmethod
    def get_history(self, event_type: Optional[EventType] = None) -> List[EventBase]:
        """获取历史事件（用于异常恢复或状态回放）"""
        ...

# ---- 简单事件总线实现 ----
class SimpleEventBus(EventBus):
    """
    默认事件总线实现，基于内存同步分发。
    支持多线程安全，但事件处理在发布线程内同步执行，
    async_mode 预留（当前默认False同步执行）。
    """

    def __init__(self, config: EventBusConfig = EventBusConfig()):
        self._config = config
        self._lock = threading.RLock()
        # 订阅表：{event_type: [handler1, handler2]}
        self._subscribers: Dict[EventType, List[EventHandler]] = {et: [] for et in EventType}
        # 通用订阅：订阅所有事件
        self._general_subscribers: List[EventHandler] = []
        # 事件历史
        self._history: List[EventBase] = []
        self._logger = logging.getLogger(__name__)
        if self._config.enable_logging:
            self._logger.setLevel(self._config.log_level)

    def _log(self, msg: str, level: int = logging.INFO):
        if self._config.enable_logging:
            self._logger.log(level, msg)

    def publish(self, event: EventBase) -> None:
        """发布事件：记录日志 -> 分发 -> 保存历史"""
        self._log(f"事件发布 [{event.event_type.name}] 来源:{event.source} ID:{event.event_id}")
        with self._lock:
            self._history.append(event)
            # 保留最近 max_event_history 条
            while len(self._history) > self._config.max_event_history:
                self._history.pop(0)

            # 通知通用订阅
            handlers = list(self._general_subscribers)
            # 通知特定类型订阅
            if event.event_type in self._subscribers:
                handlers.extend(self._subscribers[event.event_type])

        # 在锁外执行处理，避免死锁（处理函数可能再次调用 publish 等）
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                self._log(f"事件处理异常: {e} for event {event.event_id}", logging.ERROR)

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """订阅特定事件类型"""
        with self._lock:
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)
        self._log(f"订阅事件 {event_type.name} 处理器:{handler.__name__}")

    def unsubscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """取消订阅"""
        with self._lock:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)
        self._log(f"取消订阅 {event_type.name} 处理器:{handler.__name__}")

    def subscribe_all(self, handler: EventHandler) -> None:
        """订阅所有事件（通用监听）"""
        with self._lock:
            if handler not in self._general_subscribers:
                self._general_subscribers.append(handler)
        self._log(f"全局订阅处理器:{handler.__name__}")

    def unsubscribe_all(self, handler: EventHandler) -> None:
        """取消全局订阅"""
        with self._lock:
            if handler in self._general_subscribers:
                self._general_subscribers.remove(handler)
        self._log(f"取消全局订阅处理器:{handler.__name__}")

    def get_history(self, event_type: Optional[EventType] = None) -> List[EventBase]:
        """获取历史事件，可按类型过滤"""
        with self._lock:
            if event_type is None:
                return list(self._history)
            return [e for e in self._history if e.event_type == event_type]

# ---- 事件总线工厂（支持动态加载实现） ----
def create_event_bus(config: EventBusConfig = EventBusConfig()) -> EventBus:
    """
    根据配置创建事件总线实例。
    如果配置指定了其他类名，可通过 importlib 动态加载，
    当前默认返回 SimpleEventBus。
    """
    bus_class_name = config.bus_class
    if bus_class_name == "SimpleEventBus":
        return SimpleEventBus(config)
    else:
        # 预留动态加载逻辑，例如：
        # module, classname = bus_class_name.rsplit(".", 1)
        # mod = importlib.import_module(module)
        # bus_class = getattr(mod, classname)
        # return bus_class(config)
        raise ValueError(f"不支持的事件总线类: {bus_class_name}")

# ---- 模块自测 ----
if __name__ == "__main__":
    import sys

    # 配置控制台日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("========== 事件协议模块自测 ==========")

    # 1. 创建事件总线实例
    bus = create_event_bus()  # 使用默认配置

    # 2. 定义事件处理器
    def handler_agent(event: EventBase):
        print(f"[处理器1] 收到Agent事件: {event.payload}")

    def handler_general(event: EventBase):
        print(f"[全局处理器] 收到事件: {event.event_type.name} from {event.source}")

    # 3. 订阅事件
    bus.subscribe(EventType.AGENT, handler_agent)
    bus.subscribe_all(handler_general)

    # 4. 发布事件
    bus.publish(EventBase(EventType.SYSTEM, source="TestModule", payload="系统启动完成"))
    bus.publish(EventBase(EventType.AGENT, source="Agent1", payload="开始创作大纲"))
    bus.publish(EventBase(EventType.AGENT, source="Agent2", payload="生成章节一"))

    # 5. 查看历史事件
    history = bus.get_history(EventType.AGENT)
    print(f"\n历史Agent事件数量: {len(history)}")
    for evt in history:
        print(f"  {evt.event_id} - {evt.payload}")

    # 6. 取消订阅
    bus.unsubscribe(EventType.AGENT, handler_agent)
    print("\n取消Agent订阅后，再发布Agent事件...")
    bus.publish(EventBase(EventType.AGENT, source="Agent3", payload="后续任务"))

    # 7. 全局处理器仍会收到
    print("\n========== 自测完成 ==========")
    sys.exit(0)