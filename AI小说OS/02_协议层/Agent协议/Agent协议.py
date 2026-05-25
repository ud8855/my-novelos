"""
Agent协议: 定义Agent间通信的核心消息格式、序列化/反序列化接口和配置。
属于协议层，不涉及具体传输实现，仅定义数据结构和编解码契约。
可插拔: 通过抽象基类定义协议，具体编解码实现可替换。
日志: 使用标准logging记录关键操作。
配置化: 通过AgentProtocolConfig集中管理协议参数。
"""

import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional
from enum import Enum

# ----- 日志配置 -----
logger = logging.getLogger("AgentProtocol")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


# ----- 配置类 -----
@dataclass
class AgentProtocolConfig:
    """Agent协议配置，可热更新"""
    # 消息格式版本，便于兼容
    version: str = "1.0"
    # 默认编码方式: json 或 msgpack 等，可扩展
    default_encoding: str = "json"
    # 是否在消息中附带时间戳
    include_timestamp: bool = True
    # 日志级别
    log_level: int = logging.INFO

    def update(self, **kwargs):
        """热更新配置，仅允许更新已知属性"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.debug(f"配置更新: {key} = {value}")
            else:
                logger.warning(f"未知配置项: {key}")

# 全局配置实例
config = AgentProtocolConfig()
logger.setLevel(config.log_level)


# ----- 消息类型枚举 -----
class MessageType(Enum):
    """标准消息类型，可扩展"""
    TEXT = "text"
    COMMAND = "command"
    STATUS = "status"
    DATA = "data"
    CONTROL = "control"
    CUSTOM = "custom"


# ----- 消息结构 -----
@dataclass
class AgentMessage:
    """Agent间通信的标准消息格式"""
    sender_id: str
    receiver_id: str
    message_type: MessageType = MessageType.TEXT
    content: Any = ""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.message_type, str):
            try:
                self.message_type = MessageType(self.message_type)
            except ValueError:
                logger.warning(f"无效消息类型字符串 '{self.message_type}', 设为CUSTOM")
                self.message_type = MessageType.CUSTOM


# ----- 抽象编解码器 -----
class MessageEncoder(ABC):
    """消息编码器抽象基类，可插拔"""
    @abstractmethod
    def encode(self, message: AgentMessage) -> bytes:
        """将消息编码为字节流"""
        pass

    @abstractmethod
    def decode(self, data: bytes) -> AgentMessage:
        """从字节流解码为消息对象"""
        pass


class JSONMessageEncoder(MessageEncoder):
    """基于JSON的编解码器，纯Python实现，零依赖"""
    def encode(self, message: AgentMessage) -> bytes:
        try:
            msg_dict = asdict(message)
            # 将枚举转为字符串值
            msg_dict['message_type'] = message.message_type.value
            json_str = json.dumps(msg_dict, ensure_ascii=False)
            logger.debug(f"消息编码成功: {message.message_id}")
            return json_str.encode('utf-8')
        except Exception as e:
            logger.error(f"消息编码失败: {e}")
            raise

    def decode(self, data: bytes) -> AgentMessage:
        try:
            msg_dict = json.loads(data.decode('utf-8'))
            # 还原枚举
            message = AgentMessage(
                sender_id=msg_dict['sender_id'],
                receiver_id=msg_dict['receiver_id'],
                message_type=msg_dict.get('message_type', 'text'),
                content=msg_dict.get('content', ''),
                message_id=msg_dict.get('message_id', str(uuid.uuid4())),
                timestamp=msg_dict.get('timestamp', time.time()),
                metadata=msg_dict.get('metadata', {})
            )
            logger.debug(f"消息解码成功: {message.message_id}")
            return message
        except Exception as e:
            logger.error(f"消息解码失败: {e}")
            raise


# ----- 编码器工厂 -----
class EncoderFactory:
    """根据配置创建对应的编码器实例，方便热插拔"""
    _encoders = {
        "json": JSONMessageEncoder,
    }

    @classmethod
    def get_encoder(cls, encoding: Optional[str] = None) -> MessageEncoder:
        encoding = encoding or config.default_encoding
        encoder_class = cls._encoders.get(encoding)
        if encoder_class is None:
            logger.warning(f"不支持的编码 '{encoding}', 回退到 JSON")
            encoder_class = JSONMessageEncoder
        return encoder_class()

    @classmethod
    def register_encoder(cls, name: str, encoder_class: type):
        """动态注册新的编码器，实现热插拔"""
        if not issubclass(encoder_class, MessageEncoder):
            raise TypeError("编码器必须继承 MessageEncoder")
        cls._encoders[name] = encoder_class
        logger.info(f"注册新编码器: {name}")


# ----- 协议主接口 (简化，用于上层调用) -----
class AgentProtocol:
    """
    Agent协议主类，封装编解码逻辑，提供统一接口。
    上层模块通过此类进行消息的序列化与反序列化，无需关心具体编码实现。
    """
    def __init__(self, encoding: Optional[str] = None):
        self.encoder = EncoderFactory.get_encoder(encoding)
        logger.info(f"AgentProtocol 初始化，使用编码: {type(self.encoder).__name__}")

    def pack(self, message: AgentMessage) -> bytes:
        """将消息打包为字节流"""
        return self.encoder.encode(message)

    def unpack(self, data: bytes) -> AgentMessage:
        """将字节流解包为消息对象"""
        return self.encoder.decode(data)


# ----- 自测 -----
if __name__ == "__main__":
    print("===== Agent协议自测开始 =====")
    # 测试配置
    config.update(log_level=logging.DEBUG)
    logger.info("当前配置: %s", asdict(config))

    # 创建消息
    msg = AgentMessage(
        sender_id="agent_1",
        receiver_id="agent_2",
        message_type=MessageType.COMMAND,
        content={"action": "generate", "params": {"length": 1000}},
        metadata={"priority": "high"}
    )
    print(f"原始消息: {msg}")

    # 使用默认协议（JSON）
    protocol = AgentProtocol()
    # 编码
    packed = protocol.pack(msg)
    print(f"编码后字节长度: {len(packed)}")
    # 解码
    unpacked = protocol.unpack(packed)
    print(f"解码后消息: {unpacked}")
    # 验证一致性
    assert unpacked.sender_id == msg.sender_id
    assert unpacked.receiver_id == msg.receiver_id
    assert unpacked.message_type == msg.message_type
    assert unpacked.content == msg.content
    assert unpacked.metadata == msg.metadata
    print("消息一致性验证通过")

    # 测试热注册新编码器 (模拟)
    class MockEncoder(MessageEncoder):
        def encode(self, message): return b"mock"
        def decode(self, data): return AgentMessage("mock", "mock")
    EncoderFactory.register_encoder("mock", MockEncoder)
    protocol2 = AgentProtocol(encoding="mock")
    assert protocol2.pack(msg) == b"mock"
    print("热注册编码器测试通过")

    print("===== 所有自测通过 =====")