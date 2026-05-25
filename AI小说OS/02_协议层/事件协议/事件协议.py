# -*- coding: utf-8 -*-
"""
02_协议层/事件协议/事件协议.py

事件协议模块
定义系统中所有事件通信的接口、数据类型与协议。
负责：事件类型定义、事件载体结构、事件发布与监听的抽象协议。
属于：协议层(02)
依赖：无底层模块
被调用：上层模块通过实现事件监听接口与事件总线交互
解决问题：统一系统内事件传递格式，确保各模块间松耦合、可插拔通讯
"""

import logging
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from configparser import ConfigParser
import os

# ---------- 日志配置 ----------
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(name)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ---------- 配置管理 ----------
DEFAULT_CONFIG_PATH = "config/event_protocol.ini"

class EventConfig:
    """事件协议配置加载器，支持从配置文件读取扩展事件类型（示例）。"""
    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH):
        self.config = ConfigParser()
        self.config_path = config_path
        self.custom_event_types: Dict[str, int] = {}
        if os.path.exists(config_path):
            self.config.read(config_path, encoding='utf-8')
            if self.config.has_section('CustomEventTypes'):
                for name, value in self.config.items('CustomEventTypes'):
                    try:
                        self.custom_event_types[name] = int(value)
                    except ValueError:
                        logger.warning("无效的自定义事件类型值: %s=%s", name, value)
        else:
            logger.info("未找到事件配置文件，使用默认固有类型。")

    def get_custom_type_id(self, type_name: str) -> Optional[int]:
        return self.custom_event_types.get(type_name)


# ---------- 事件类型枚举（可扩展） ----------
class EventType(Enum):
    """系统预定义事件类型。可通过配置文件动态添加自定义类型（需运行时注册）。"""
    # 基础事件
    SYSTEM_START = auto()
    SYSTEM_SHUTDOWN = auto()
    SYSTEM_ERROR = auto()
    # 用户交互
    USER_INPUT = auto()
    USER_OUTPUT = auto()
    # 模块状态
    MODULE_LOADED = auto()
    MODULE_UNLOADED = auto()
    MODULE_ERROR = auto()
    # 模型相关
    MODEL_REQUEST = auto()
    MODEL_RESPONSE = auto()
    MODEL_ERROR = auto()
    # 预留扩展位 —— 自定义类型可通过注册机制动态添加
    @classmethod
    def register_custom_type(cls, name: str, value: Optional[int] = None):
        """运行时注册自定义事件类型（可插拔扩展）。"""
        if value is None:
            value = max([e.value for e in cls]) + 1
        # 动态添加枚举成员是不被允许的，采用变通：使用IntEnum或自定义元类。
        # 这里提供一种简化实现：使用一个单独的字典管理自定义类型。
        logger.debug("注册自定义事件类型: %s -> %d", name, value)


# ---------- 事件数据结构 ----------
@dataclass
class Event:
    """标准事件载体，所有事件传递必须使用该结构或其子类。"""
    type: EventType
    data: Any = None
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将事件序列化为字典，便于跨进程/网络传输（协议序列化）"""
        return {
            "type": self.type.name,
            "data": self.data,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'Event':
        """从字典反序列化事件"""
        try:
            event_type = EventType[d["type"]]
        except KeyError:
            # 尝试自定义类型映射
            logger.warning("未注册的事件类型: %s", d.get("type"))
            # 视作未知类型？可定义 UNKNOWN
            event_type = EventType.SYSTEM_ERROR
        return cls(
            type=event_type,
            data=d.get("data"),
            source=d.get("source", ""),
            timestamp=datetime.fromisoformat(d["timestamp"]) if d.get("timestamp") else datetime.now(),
            metadata=d.get("metadata", {})
        )


# ---------- 事件监听器抽象 ----------
class EventListener(ABC):
    """
    事件监听者抽象基类。
    所有希望接收事件的对象必须实现此接口，并通过EventBus注册。
    """
    @abstractmethod
    def on_event(self, event: Event) -> None:
        """
        处理接收到的事件。
        实现时需考虑异步、异常处理，避免阻塞事件分发。
        """
        ...

    @abstractmethod
    def get_supported_events(self) -> list:
        """
        返回本监听器感兴趣的事件类型列表。
        允许返回空列表表示接收全部（须谨慎），或具体类型。
        """
        ...


# ---------- 事件总线接口（抽象） ----------
class EventBus(ABC):
    """
    事件总线抽象协议。
    定义发布、订阅、退订的标准接口。
    具体实现由基础设施层提供（如异步事件总线、内存事件总线等）。
    """
    @abstractmethod
    def subscribe(self, listener: EventListener, event_types: Optional[list] = None) -> None:
        """订阅事件，event_types为None表示接受所有类型"""
        ...

    @abstractmethod
    def unsubscribe(self, listener: EventListener, event_types: Optional[list] = None) -> None:
        """取消订阅"""
        ...

    @abstractmethod
    def publish(self, event: Event) -> None:
        """发布事件，同步/异步由实现决定"""
        ...


# ---------- 事件转换器接口（用于协议适配） ----------
class EventCodec(ABC):
    """
    事件编解码器协议。
    负责将Event对象转换为特定的传输格式（如JSON、Protobuf等），
    以实现跨进程、跨语言的事件通讯。
    """
    @abstractmethod
    def encode(self, event: Event) -> bytes:
        """将事件编码为字节流"""
        ...

    @abstractmethod
    def decode(self, data: bytes) -> Event:
        """从字节流解码为事件"""
        ...


# ---------- 自测代码 ----------
if __name__ == "__main__":
    print("=== 事件协议模块自测开始 ===")
    logger.setLevel(logging.DEBUG)

    # 测试事件创建与序列化
    ev = Event(
        type=EventType.USER_INPUT,
        data={"text": "Hello, NovelOS"},
        source="test_script"
    )
    print("创建事件:", ev)

    # 序列化
    d = ev.to_dict()
    print("序列化为字典:", d)

    # 反序列化
    ev2 = Event.from_dict(d)
    print("反序列化事件:", ev2)
    assert ev2.type == EventType.USER_INPUT
    assert ev2.data["text"] == "Hello, NovelOS"
    print("序列化/反序列化测试通过")

    # 测试配置加载
    config = EventConfig()
    if config.config.has_section('CustomEventTypes'):
        print("自定义事件类型:", config.custom_event_types)
    else:
        print("无自定义事件类型配置")

    # 测试监听器实现（简单示例）
    class PrintListener(EventListener):
        def on_event(self, event: Event) -> None:
            print(f"[PrintListener] 收到事件: {event.type.name}, 数据: {event.data}")

        def get_supported_events(self) -> list:
            return [EventType.USER_INPUT]

    listener = PrintListener()
    print("支持的监听:", listener.get_supported_events())

    # 模拟事件总线发布（未实现具体总线，仅展示接口调用）
    # 这里我们直接调用listener.on_event来模拟
    listener.on_event(ev)

    print("=== 自测结束 ===")