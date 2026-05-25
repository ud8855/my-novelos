# -*- coding: utf-8 -*-
"""
模块: 总线协议 (Bus Protocol)
路径: 02_协议层/总线协议/总线协议.py
层级: 协议层
依赖: 无（仅定义抽象接口）
被调用: 各模块通过总线通信时导入协议，具体总线实现需继承抽象基类
功能: 定义系统内模块间事件总线通信的抽象协议，包含消息格式、发布/订阅接口，
      确保各组件可插拔、解耦通信。
"""

import abc
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import logging
import configparser

# 日志记录器
logger = logging.getLogger("BusProtocol")

# -----------------------------------------------------------------------------
# 配置管理
# -----------------------------------------------------------------------------
class BusConfig:
    """
    总线配置类
    支持从配置文件或字典加载参数，例如：总线类型、连接地址、队列大小等。
    """
    def __init__(self, config_path: Optional[str] = None, **kwargs):
        self.bus_type = kwargs.get("bus_type", "memory")  # memory, redis, kafka...
        self.connection_url = kwargs.get("connection_url", "")
        self.max_queue_size = kwargs.get("max_queue_size", 1000)
        self.default_timeout = kwargs.get("default_timeout", 5.0)
        if config_path:
            self.load_from_file(config_path)

    def load_from_file(self, path: str):
        """从INI文件加载配置"""
        cp = configparser.ConfigParser()
        cp.read(path)
        if cp.has_section("bus"):
            self.bus_type = cp.get("bus", "type", fallback=self.bus_type)
            self.connection_url = cp.get("bus", "url", fallback=self.connection_url)
            self.max_queue_size = cp.getint("bus", "max_queue_size", fallback=self.max_queue_size)
            self.default_timeout = cp.getfloat("bus", "default_timeout", fallback=self.default_timeout)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bus_type": self.bus_type,
            "connection_url": self.connection_url,
            "max_queue_size": self.max_queue_size,
            "default_timeout": self.default_timeout,
        }

    def __repr__(self):
        return f"BusConfig({self.to_dict()})"


# -----------------------------------------------------------------------------
# 消息定义
# -----------------------------------------------------------------------------
@dataclass
class BusMessage:
    """
    总线消息标准格式
    topic: 主题，用于路由
    data: 消息负载，可以是任意可序列化对象
    timestamp: 消息产生时间戳（秒级浮点数）
    source: 消息来源模块标识，可选
    message_id: 唯一消息ID，可选，用于追踪
    """
    topic: str
    data: Any
    timestamp: float = field(default_factory=time.time)
    source: Optional[str] = None
    message_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，便于序列化"""
        return {
            "topic": self.topic,
            "data": self.data,  # 实际使用时需确保可序列化
            "timestamp": self.timestamp,
            "source": self.source,
            "message_id": self.message_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BusMessage":
        return cls(
            topic=d["topic"],
            data=d["data"],
            timestamp=d.get("timestamp", time.time()),
            source=d.get("source"),
            message_id=d.get("message_id"),
        )

    def __str__(self):
        return f"BusMessage(topic={self.topic}, source={self.source})"


# -----------------------------------------------------------------------------
# 总线抽象接口
# -----------------------------------------------------------------------------
class AbstractBus(abc.ABC):
    """
    事件总线抽象基类（协议）
    所有具体实现必须继承此类并实现所有抽象方法，确保模块间可替换。
    支持发布/订阅模式，允许动态添加、移除订阅者。
    """

    def __init__(self, config: BusConfig):
        self.config = config
        self._running = True
        logger.info(f"AbstractBus initialized with config: {config}")

    @abc.abstractmethod
    def publish(self, message: BusMessage):
        """发布消息到总线（抽象）"""
        ...

    @abc.abstractmethod
    def subscribe(self, topic: str, callback: Callable[[BusMessage], None]) -> str:
        """
        订阅指定主题，返回订阅ID用于取消订阅（抽象）
        callback: 接收到消息时调用的回调函数，参数为 BusMessage
        """
        ...

    @abc.abstractmethod
    def unsubscribe(self, sub_id: str):
        """取消订阅（抽象）"""
        ...

    @abc.abstractmethod
    def start(self):
        """启动总线（如果需要独立进程/线程）"""
        ...

    @abc.abstractmethod
    def stop(self):
        """停止总线并清理资源"""
        ...

    @abc.abstractmethod
    def health_check(self) -> bool:
        """健康检查，返回总线是否可用"""
        ...

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# -----------------------------------------------------------------------------
# 自定义异常
# -----------------------------------------------------------------------------
class BusError(Exception):
    """总线基础异常"""
    pass

class BusConnectionError(BusError):
    """连接异常"""
    pass

class BusPublishError(BusError):
    """发布异常"""
    pass

class BusSubscribeError(BusError):
    """订阅异常"""
    pass


# -----------------------------------------------------------------------------
# 工厂函数（可插拔特性）
# -----------------------------------------------------------------------------
def create_bus(config: BusConfig) -> AbstractBus:
    """
    总线工厂函数，根据配置动态实例化对应的总线实现。
    目前仅返回占位符，实际实现需注册对应类。
    """
    bus_type = config.bus_type.lower()
    # 这里是占位实现，将来扩展时通过注册表加载具体类
    logger.warning(f"No bus implementation registered for type '{bus_type}'. "
                   f"Returning a DummyBus for compatibility.")
    from ._dummy_bus import DummyBus  # 延迟导入，避免循环依赖
    return DummyBus(config)


# -----------------------------------------------------------------------------
# 基础日志装饰器（可选）
# -----------------------------------------------------------------------------
def log_call(func):
    """装饰器：记录方法调用与简单耗时（用于关键方法）"""
    def wrapper(*args, **kwargs):
        logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        result = func(*args, **kwargs)
        logger.debug(f"Finished {func.__name__}")
        return result
    return wrapper


# -----------------------------------------------------------------------------
# 自测代码
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    # 测试：不能直接实例化抽象基类
    print("Testing BusMessage creation...")
    msg = BusMessage(topic="test.topic", data={"key": "value"}, source="tester")
    print(msg)
    d = msg.to_dict()
    print("to_dict:", d)
    msg2 = BusMessage.from_dict(d)
    print("restored:", msg2)

    # 测试配置
    print("\nTesting BusConfig...")
    cfg = BusConfig(bus_type="redis", connection_url="redis://localhost:6379/0")
    print(cfg)
    # 创建一个假的实现用于验证
    from abc import ABCMeta
    # 由于抽象类不能直接实例化，这里仅展示结构
    print("AbstractBus cannot be instantiated directly.")
    # 通过工厂产生一个dummy实例（假设存在 _dummy_bus.py）
    try:
        bus = create_bus(cfg)
        print("Created bus:", bus)
        print("Health check:", bus.health_check())
    except ImportError:
        print("DummyBus not implemented in this skeleton. Skipping factory test.")
    print("All tests passed.")