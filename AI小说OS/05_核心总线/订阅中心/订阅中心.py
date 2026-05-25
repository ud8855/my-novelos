from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Callable, Dict, List, Optional, Set
import threading

# 配置部分示例，实际可从文件或环境加载
DEFAULT_CONFIG = {
    "subscription_center": {
        "backend": "memory",   # 可选: memory, redis, ...
        "redis_host": "localhost",
        "redis_port": 6379,
        "max_subscribers_per_topic": 100,
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    }
}

# 日志配置
def setup_logging(config: Dict = None):
    if config is None:
        config = DEFAULT_CONFIG.get("logging", {})
    level = getattr(logging, config.get("level", "INFO").upper(), logging.INFO)
    fmt = config.get("format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    logging.basicConfig(level=level, format=fmt)

setup_logging()
logger = logging.getLogger("SubscriptionCenter")


class SubscriptionCenter(ABC):
    """
    事件订阅中心抽象基类。
    所有具体的订阅中心实现必须继承此类并实现以下方法。
    实现可插拔，由工厂函数根据配置选择具体实现。
    """

    @abstractmethod
    def subscribe(self, topic: str, callback: Callable, subscriber_id: str = None) -> str:
        """
        订阅某个主题。

        Args:
            topic: 事件主题
            callback: 收到事件时的回调函数，回调参数为 (topic, data)
            subscriber_id: 可选，订阅者唯一 ID，若不提供则自动生成

        Returns:
            订阅者 ID (用于取消订阅)
        """
        pass

    @abstractmethod
    def unsubscribe(self, topic: str, subscriber_id: str) -> bool:
        """
        取消订阅。

        Args:
            topic: 主题
            subscriber_id: 订阅时返回的 ID

        Returns:
            是否成功取消
        """
        pass

    @abstractmethod
    def publish(self, topic: str, data=None) -> int:
        """
        向主题发布消息。

        Args:
            topic: 主题
            data: 事件数据，任意类型

        Returns:
            收到通知的订阅者数量
        """
        pass

    @abstractmethod
    def clear(self):
        """清除所有订阅信息（主要用于测试或重置）"""
        pass

    @abstractmethod
    def list_topics(self) -> List[str]:
        """返回当前所有已注册主题"""
        pass

    @abstractmethod
    def list_subscribers(self, topic: str) -> List[str]:
        """返回指定主题的所有订阅者 ID"""
        pass


class MemorySubscriptionCenter(SubscriptionCenter):
    """
    基于内存的发布/订阅实现。
    线程安全，支持并发。
    """

    def __init__(self, config: Dict = None):
        """
        初始化内存订阅中心。

        Args:
            config: 配置字典，当前版本仅用于记录，可包含 max_subscribers_per_topic 等。
        """
        self.config = config or DEFAULT_CONFIG.get("subscription_center", {})
        max_per_topic = self.config.get("max_subscribers_per_topic", 100)
        if max_per_topic <= 0:
            raise ValueError("max_subscribers_per_topic 必须为正整数")
        self.max_per_topic = max_per_topic
        self._topics: Dict[str, Dict[str, Callable]] = {}   # topic -> {subscriber_id: callback}
        self._lock = threading.RLock()  # 可重入锁保护数据结构
        logger.info("MemorySubscriptionCenter 已初始化，每个主题最大订阅数: %d", self.max_per_topic)

    def subscribe(self, topic: str, callback: Callable, subscriber_id: str = None) -> str:
        if not callable(callback):
            raise TypeError("callback 必须是一个可调用对象")

        with self._lock:
            if topic not in self._topics:
                self._topics[topic] = {}

            if subscriber_id is None:
                # 自动生成唯一 ID
                import uuid
                subscriber_id = f"sub_{uuid.uuid4().hex[:8]}"
            elif subscriber_id in self._topics[topic]:
                raise ValueError(f"订阅者 ID '{subscriber_id}' 在主题 '{topic}' 中已存在")

            if len(self._topics[topic]) >= self.max_per_topic:
                raise RuntimeError(f"主题 '{topic}' 的订阅者数量已达上限 {self.max_per_topic}")

            self._topics[topic][subscriber_id] = callback
            logger.info("订阅成功: topic='%s', subscriber='%s', 当前订阅数=%d", topic, subscriber_id, len(self._topics[topic]))
            return subscriber_id

    def unsubscribe(self, topic: str, subscriber_id: str) -> bool:
        with self._lock:
            if topic in self._topics and subscriber_id in self._topics[topic]:
                del self._topics[topic][subscriber_id]
                # 如果主题下没有订阅者，清理主题入口
                if not self._topics[topic]:
                    del self._topics[topic]
                logger.info("取消订阅成功: topic='%s', subscriber='%s'", topic, subscriber_id)
                return True
            logger.warning("取消订阅失败: 未找到 topic='%s', subscriber='%s'", topic, subscriber_id)
            return False

    def publish(self, topic: str, data=None) -> int:
        with self._lock:
            # 获取当前主题的快照（回调可能修改订阅）
            subscribers = self._topics.get(topic, {}).copy()
            if not subscribers:
                logger.debug("主题 '%s' 无订阅者，消息被丢弃", topic)
                return 0

        count = 0
        for sub_id, callback in subscribers.items():
            try:
                # 在不同线程中调用回调，注意异常处理，防止单个回调错误影响其他订阅者
                callback(topic, data)
                count += 1
            except Exception as e:
                logger.exception("执行订阅者 '%s' 的回调时发生异常: %s", sub_id, e)
        logger.info("主题 '%s' 发布成功，通知了 %d 个订阅者", topic, count)
        return count

    def clear(self):
        with self._lock:
            self._topics.clear()
            logger.info("已清除所有订阅信息")

    def list_topics(self) -> List[str]:
        with self._lock:
            return list(self._topics.keys())

    def list_subscribers(self, topic: str) -> List[str]:
        with self._lock:
            return list(self._topics.get(topic, {}).keys())


def create_subscription_center(config: Dict = None) -> SubscriptionCenter:
    """
    工厂函数：根据配置创建可插拔的订阅中心实例。

    Args:
        config: 完整配置字典，若未提供则使用 DEFAULT_CONFIG

    Returns:
        SubscriptionCenter 具体实现实例
    """
    if config is None:
        config = DEFAULT_CONFIG
    sub_conf = config.get("subscription_center", {})
    backend = sub_conf.get("backend", "memory")
    if backend == "memory":
        return MemorySubscriptionCenter(config=sub_conf)
    else:
        raise ValueError(f"不支持的订阅中心后端: {backend}")


# 自测代码
if __name__ == "__main__":
    # 配置日志级别便于观察
    setup_logging({"level": "DEBUG"})

    print("=== 订阅中心自测开始 ===")

    # 创建订阅中心（可插拔：此处使用 memory 后端）
    center = create_subscription_center()

    # 提示订阅数上限配置
    print(f"当前每个主题最大订阅数: {center.max_per_topic}")

    # 测试回调函数
    def callback1(topic, data):
        print(f"[回调1] 收到主题 '{topic}' 的消息: {data}")

    def callback2(topic, data):
        print(f"[回调2] 收到主题 '{topic}' 的消息: {data}")

    # 订阅主题
    sub_id1 = center.subscribe("order.created", callback1)
    sub_id2 = center.subscribe("order.created", callback2, "my_custom_id")
    sub_id3 = center.subscribe("user.registered", callback1)

    print(f"\n已订阅主题列表: {center.list_topics()}")
    print(f"主题 'order.created' 订阅者: {center.list_subscribers('order.created')}")

    # 发布消息
    print("\n--- 发布 'order.created' 事件 ---")
    notified = center.publish("order.created", {"order_id": 123, "amount": 45.6})
    print(f"通知订阅者数量: {notified}")

    # 发布不存在订阅的主题
    print("\n--- 发布 'nonexistent' 事件 ---")
    notified = center.publish("nonexistent", "data")
    print(f"通知订阅者数量: {notified}")

    # 取消订阅
    print("\n--- 取消订阅 ---")
    cancel_ok = center.unsubscribe("order.created", sub_id1)
    print(f"取消 sub_id1 结果: {cancel_ok}")
    cancel_ok = center.unsubscribe("order.created", "not_exist")
    print(f"取消不存在的 ID 结果: {cancel_ok}")

    print(f"取消后 'order.created' 订阅者: {center.list_subscribers('order.created')}")

    # 再次发布，只剩 callback2
    print("\n--- 再次发布 'order.created' 事件 ---")
    notified = center.publish("order.created", {"order_id": 456})
    print(f"通知订阅者数量: {notified}")

    # 清除所有订阅
    center.clear()
    print("\n清除后主题列表:", center.list_topics())

    print("\n=== 自测完成 ===")