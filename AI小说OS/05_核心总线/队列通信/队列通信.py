"""
05_核心总线/队列通信

职责：提供可插拔的异步消息队列抽象，支持发布/订阅与点对点通信。
依赖：无（仅依赖标准库及可选后端驱动）
被调用者：任何需要跨模块异步通信的组件（Agent、Runtime、UI等）
解决：解耦模块通信，支撑热更新与扩展，统一日志与配置管理。
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Union

# ---------- 日志 ----------
logger = logging.getLogger("NovelOS.核心总线.队列通信")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ---------- 配置 ----------
@dataclass
class QueueConfig:
    """队列通信全局配置"""
    backend: str = "memory"          # 后端类型：memory, redis, rabbitmq
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    max_retries: int = 3
    retry_delay: float = 1.0
    publish_timeout: float = 5.0
    subscribe_timeout: float = 30.0


# ---------- 消息基类 ----------
@dataclass
class Message:
    """标准消息体"""
    topic: str
    payload: Any
    message_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    headers: Dict[str, Any] = field(default_factory=dict)


# ---------- 抽象后端 ----------
class QueueBackend(ABC):
    """消息队列后端抽象接口，所有具体后端必须实现此接口"""

    def __init__(self, config: QueueConfig):
        self.config = config
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @abstractmethod
    async def connect(self) -> None:
        """建立连接（如需要）"""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """断开连接并清理资源"""
        ...

    @abstractmethod
    async def publish(self, message: Message) -> bool:
        """发布消息，返回是否成功"""
        ...

    @abstractmethod
    async def subscribe(self, topic: str, callback: Callable[[Message], Any]) -> None:
        """订阅主题，收到消息时调用 callback(message)"""
        ...

    @abstractmethod
    async def unsubscribe(self, topic: str, callback: Callable[[Message], Any]) -> None:
        """取消订阅"""
        ...


# ---------- 内存实现（默认） ----------
class MemoryQueueBackend(QueueBackend):
    """基于 asyncio.Queue 的内存队列后端，适用于开发与测试"""

    def __init__(self, config: QueueConfig):
        super().__init__(config)
        self._topics: Dict[str, List[asyncio.Queue]] = {}  # topic -> [queues for each subscriber]

    async def connect(self) -> None:
        self._connected = True
        logger.info("内存队列后端已就绪")

    async def disconnect(self) -> None:
        self._connected = False
        self._topics.clear()
        logger.info("内存队列后端已关闭")

    async def publish(self, message: Message) -> bool:
        if not self.is_connected:
            logger.warning("后端未连接，无法发布消息")
            return False
        queues = self._topics.get(message.topic, [])
        if not queues:
            logger.debug(f"无订阅者订阅主题 {message.topic}，消息被丢弃")
            return False
        # 同时推送给所有订阅者
        for q in queues:
            await q.put(message)
        logger.debug(f"消息已发布到主题 {message.topic}")
        return True

    async def subscribe(self, topic: str, callback: Callable[[Message], Any]) -> None:
        if not self.is_connected:
            await self.connect()
        # 每个订阅者分配一个独立队列，以便独立消费
        queue: asyncio.Queue = asyncio.Queue()
        self._topics.setdefault(topic, []).append(queue)
        # 启动消费者任务
        async def _consumer() -> None:
            while self.is_connected:
                try:
                    msg = await queue.get()
                    await callback(msg)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"处理消息时异常: {e}", exc_info=True)
        # 为每个订阅创建独立任务，并保存引用以便取消
        task = asyncio.create_task(_consumer())
        # 简单管理：将任务与（topic, callback）绑定，用于取消订阅
        # 这里用一个辅助存储
        if not hasattr(self, "_tasks"):
            self._tasks: Dict[str, List[asyncio.Task]] = {}
        self._tasks.setdefault(topic, []).append(task)
        logger.info(f"已订阅主题 {topic}")

    async def unsubscribe(self, topic: str, callback: Callable[[Message], Any]) -> None:
        # 略：实际需要找到对应任务并取消，简单起见仅注销队列
        # 完整实现保留接口
        logger.info(f"取消订阅主题 {topic} (简化实现)")
        # 实际实现需匹配callback，此处略
        pass


# ---------- 消息总线（统一接口） ----------
class MessageBus:
    """消息总线，封装队列后端并提供统一的发布/订阅API"""

    def __init__(self, config: Optional[QueueConfig] = None):
        self.config = config or QueueConfig()
        self._backend: Optional[QueueBackend] = None

    async def start(self) -> None:
        """根据配置启动后端"""
        if self._backend is not None:
            logger.warning("消息总线已启动，忽略重复启动")
            return
        backend_type = self.config.backend.lower()
        if backend_type == "memory":
            self._backend = MemoryQueueBackend(self.config)
        elif backend_type == "redis":
            # 预留接口
            raise NotImplementedError("Redis后端尚未实现")
        elif backend_type == "rabbitmq":
            raise NotImplementedError("RabbitMQ后端尚未实现")
        else:
            raise ValueError(f"不支持的后端类型: {backend_type}")
        await self._backend.connect()
        logger.info(f"消息总线启动，后端类型: {backend_type}")

    async def stop(self) -> None:
        """停止后端并清理资源"""
        if self._backend is None:
            return
        await self._backend.disconnect()
        self._backend = None
        logger.info("消息总线已停止")

    async def publish(self, topic: str, payload: Any, **kwargs) -> bool:
        """发布一条消息到指定主题"""
        if self._backend is None:
            logger.error("消息总线未启动，无法发布")
            return False
        message = Message(topic=topic, payload=payload, headers=kwargs)
        return await self._backend.publish(message)

    async def subscribe(self, topic: str, callback: Callable[[Message], Any]) -> None:
        """订阅主题，收到消息时触发回调"""
        if self._backend is None:
            logger.error("消息总线未启动，无法订阅")
            return
        await self._backend.subscribe(topic, callback)

    async def unsubscribe(self, topic: str, callback: Callable[[Message], Any]) -> None:
        """取消订阅"""
        if self._backend is None:
            return
        await self._backend.unsubscribe(topic, callback)


# ---------- 自测 ----------
async def _self_test():
    """基本功能验证"""
    print("====== 自测：内存队列通信 ======")
    bus = MessageBus(QueueConfig(backend="memory"))
    await bus.start()

    received_messages = []

    async def dummy_callback(msg: Message):
        print(f"收到消息：{msg.topic} -> {msg.payload}")
        received_messages.append(msg)

    # 订阅
    await bus.subscribe("test.topic", dummy_callback)

    # 发布
    await bus.publish("test.topic", {"data": "hello"})
    await asyncio.sleep(0.2)  # 等待异步消费

    # 验证
    assert len(received_messages) == 1
    assert received_messages[0].payload == {"data": "hello"}

    # 停止
    await bus.stop()
    print("自测通过！")


if __name__ == "__main__":
    asyncio.run(_self_test())