"""NovelOS 广播系统
提供事件发布/订阅功能，用于模块间松散耦合通信。
可插拔设计，支持替换为不同实现（如 Redis, RabbitMQ）。
"""
import logging
import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

class BroadcastConfig:
    """广播系统配置，支持热更新"""
    MAX_QUEUE_SIZE: int = 1000
    THREAD_SAFE: bool = True
    LOG_LEVEL: int = logging.INFO

logger = logging.getLogger("BroadcastSystem")
logger.setLevel(BroadcastConfig.LOG_LEVEL)

class BroadcastSystem(ABC):
    """广播系统抽象接口"""

    @abstractmethod
    def subscribe(self, event_type: str, callback: Callable, **kwargs) -> bool:
        """订阅事件

        :param event_type: 事件类型标识符
        :param callback: 回调函数，接收 data 和 **kwargs
        :return: 是否成功
        """
        ...

    @abstractmethod
    def unsubscribe(self, event_type: str, callback: Callable) -> bool:
        """取消订阅

        :param event_type: 事件类型标识符
        :param callback: 已订阅的回调函数
        :return: 是否成功
        """
        ...

    @abstractmethod
    def publish(self, event_type: str, data: Any, **kwargs) -> None:
        """发布事件

        :param event_type: 事件类型标识符
        :param data: 事件负载数据
        """
        ...

    @abstractmethod
    def get_subscribers(self, event_type: str) -> List[Callable]:
        """获取某事件的所有订阅者

        :param event_type: 事件类型标识符
        :return: 回调函数列表
        """
        ...

class SimpleBroadcastSystem(BroadcastSystem):
    """基于内存的默认广播系统，线程安全，支持后续替换"""

    def __init__(self, config: Optional[BroadcastConfig] = None) -> None:
        self.config = config or BroadcastConfig()
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.Lock() if self.config.THREAD_SAFE else None
        logger.info("广播系统初始化完成")

    def subscribe(self, event_type: str, callback: Callable, **kwargs) -> bool:
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)
                logger.debug(f"订阅事件: {event_type}, 回调: {callback.__name__}")
                return True
            else:
                logger.warning(f"重复订阅同一回调: {event_type}, {callback.__name__}")
                return False

    def unsubscribe(self, event_type: str, callback: Callable) -> bool:
        with self._lock:
            if event_type in self._subscribers and callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                logger.debug(f"取消订阅: {event_type}, {callback.__name__}")
                if not self._subscribers[event_type]:
                    del self._subscribers[event_type]
                return True
            else:
                logger.warning(f"未找到订阅: {event_type}, {callback.__name__}")
                return False

    def publish(self, event_type: str, data: Any, **kwargs) -> None:
        with self._lock:
            subscribers = self._subscribers.get(event_type, [])
            # 快照防止回调中修改订阅列表
            callbacks = list(subscribers)
        logger.info(f"发布事件: {event_type}, 数据: {data}")
        for callback in callbacks:
            try:
                callback(data, **kwargs)
            except Exception as e:
                logger.error(f"执行回调 {callback.__name__} 时出错: {e}", exc_info=True)

    def get_subscribers(self, event_type: str) -> List[Callable]:
        with self._lock:
            return list(self._subscribers.get(event_type, []))

# 自测代码
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    def on_test_event(data):
        print(f"收到测试事件数据: {data}")

    bus = SimpleBroadcastSystem()
    bus.subscribe("test", on_test_event)
    bus.publish("test", "Hello World!")
    bus.unsubscribe("test", on_test_event)
    bus.publish("test", "No one should hear this")
    print("自测完成")