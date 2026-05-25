"""
事件派发模块（Event Dispatcher）
所属层级：05_核心总线
依赖：无外部模块依赖（自含）
被调用：任何需要发布/订阅事件的模块（如Agent管理器、模型协同层等）
解决的问题：提供全局统一的事件发布与订阅机制，支持动态注册/注销处理器，解耦模块间通信，
         并内建异常隔离、日志记录和配置化加载的能力。
"""
import logging
import traceback
from typing import Any, Callable, Dict, List, Optional

# 配置化日志
logger = logging.getLogger(__name__)

# 事件处理器类型定义
EventHandler = Callable[[Dict[str, Any]], None]


class EventDispatcher:
    """
    事件派发器核心
    采用观察者模式，单一职责：管理事件类型与处理器的映射关系，并负责派发。
    可插拔：不同模块可直接实例化或继承扩展。
    支持配置化加载初始映射。
    所有对处理器的调用均被异常边界包裹，确保一个处理器失败不影响后续。
    """

    def __init__(self, config: Optional[Dict[str, List[EventHandler]]] = None):
        """
        初始化派发器
        :param config: 可选配置字典，格式: { "event_type": [handler1, handler2, ...] }
        """
        # 事件订阅表：{ event_type: [handler, ...] }
        self._subscriptions: Dict[str, List[EventHandler]] = {}
        # 从配置热加载订阅关系
        if config:
            self.load_config(config)
        logger.info("EventDispatcher initialized with %d event types", len(self._subscriptions))

    def load_config(self, config: Dict[str, List[EventHandler]]):
        """
        从配置字典批量加载事件订阅关系（可热更新）
        不覆盖已有订阅，只追加新处理器。
        """
        for event_type, handlers in config.items():
            for handler in handlers:
                self.subscribe(event_type, handler)

    def subscribe(self, event_type: str, handler: EventHandler):
        """
        订阅事件
        :param event_type: 事件类型（字符串标识）
        :param handler: 回调函数，接收一个字典作为事件数据
        """
        if event_type not in self._subscriptions:
            self._subscriptions[event_type] = []
        # 避免重复注册同一个处理函数（引用比较）
        if handler not in self._subscriptions[event_type]:
            self._subscriptions[event_type].append(handler)
            logger.debug("Subscribed handler to event '%s'", event_type)
        else:
            logger.debug("Handler already subscribed to event '%s'", event_type)

    def unsubscribe(self, event_type: str, handler: EventHandler):
        """
        取消订阅事件
        :param event_type: 事件类型
        :param handler: 要移除的回调函数
        """
        if event_type in self._subscriptions:
            try:
                self._subscriptions[event_type].remove(handler)
                logger.debug("Unsubscribed handler from event '%s'", event_type)
                # 如果该事件类型下无处理器，可选择删除键，但不强制
            except ValueError:
                logger.debug("Handler not found for event '%s', ignore unsubscribe", event_type)

    def dispatch(self, event_type: str, event_data: Optional[Dict[str, Any]] = None) -> int:
        """
        派发事件给所有订阅该类型的处理器
        :param event_type: 事件类型
        :param event_data: 事件携带的数据，默认为空字典
        :return: 成功调用的处理器数量
        """
        if event_data is None:
            event_data = {}

        handlers = self._subscriptions.get(event_type, [])
        success_count = 0
        for handler in handlers:
            try:
                handler(event_data)
                success_count += 1
            except Exception:
                # 异常恢复：记录错误但继续派发其他处理器
                logger.error(
                    "Error dispatching event '%s' to handler %s: %s",
                    event_type,
                    handler.__name__,
                    traceback.format_exc(),
                )
        logger.debug("Dispatched event '%s' to %d/%d handlers successfully",
                     event_type, success_count, len(handlers))
        return success_count

    def list_events(self) -> List[str]:
        """
        列出当前已注册的所有事件类型（用于调试和管理）
        """
        return list(self._subscriptions.keys())

    def clear(self):
        """
        清空所有订阅（用于测试或重置）
        """
        self._subscriptions.clear()
        logger.info("EventDispatcher cleared all subscriptions")

    def __repr__(self):
        return f"<EventDispatcher(events={len(self._subscriptions)})>"


# ----- 自测代码 -----
if __name__ == "__main__":
    # 配置日志输出格式
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 示例事件处理器
    def on_user_login(data: Dict[str, Any]):
        print(f"[处理器] 用户登录: {data.get('username')}")

    def on_user_logout(data: Dict[str, Any]):
        print(f"[处理器] 用户登出: {data.get('username')}")

    def faulty_handler(data: Dict[str, Any]):
        raise RuntimeError("模拟处理器异常")

    # 初始化派发器（可选从配置加载）
    initial_config = {
        "user.login": [on_user_login],
        "user.logout": [on_user_logout],
    }
    dispatcher = EventDispatcher(config=initial_config)

    # 动态订阅
    dispatcher.subscribe("user.login", faulty_handler)

    # 派发事件
    print("--- 派发 user.login 事件 ---")
    dispatched = dispatcher.dispatch("user.login", {"username": "Alice"})
    print(f"成功处理数: {dispatched}")

    print("\n--- 派发 user.logout 事件 ---")
    dispatcher.dispatch("user.logout", {"username": "Bob"})

    # 取消订阅并再次派发
    dispatcher.unsubscribe("user.login", faulty_handler)
    print("\n--- 移除异常处理器后，再次派发 user.login ---")
    dispatcher.dispatch("user.login", {"username": "Charlie"})

    # 列出事件类型
    print("\n当前注册事件类型:", dispatcher.list_events())

    # 清空测试
    dispatcher.clear()
    print("清空后事件类型:", dispatcher.list_events())