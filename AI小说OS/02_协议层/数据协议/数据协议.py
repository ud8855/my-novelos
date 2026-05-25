# 数据协议.py
# 模块路径: 02_协议层/数据协议
# 职责: 定义系统中各模块间数据交换的通用协议结构，提供序列化/反序列化、校验等基础能力。
# 依赖: 标准库 logging, json, typing, abc, dataclasses (可选，用于结构化基类)
# 被调用: 本层其它协议模块、上层业务模块、Agent间通信、存储层适配等

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional, Type, Union
from enum import Enum
from datetime import datetime

# 日志配置：本模块独立日志器，支持外部注入配置
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())  # 默认无输出，由调用方配置

# ==================== 协议核心 ====================

class DataProtocol(ABC):
    """
    数据协议基类，所有自定义协议需继承此类。
    提供统一的序列化/反序列化、校验接口，支持可插拔扩展。
    """
    
    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """将协议实例转换为字典"""
        pass
    
    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataProtocol":
        """从字典构建协议实例"""
        pass
    
    def to_json(self, ensure_ascii: bool = False) -> str:
        """序列化为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, default=str)
    
    @classmethod
    def from_json(cls, json_str: str) -> "DataProtocol":
        """从JSON字符串反序列化"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def validate(self) -> bool:
        """
        校验协议数据是否合法，默认返回True。
        子类可重写以实现自定义校验逻辑。
        """
        logger.debug(f"Validating protocol data: {self.__class__.__name__}")
        return True

# ==================== 基础数据类型支持 ====================

class DataType(Enum):
    """基础数据类型枚举"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    NULL = "null"
    ANY = "any"

@dataclass
class FieldDescriptor:
    """
    字段描述符，用于动态定义协议字段的元信息。
    支持可插拔的字段定义与校验。
    """
    name: str
    type: DataType = DataType.ANY
    required: bool = False
    default: Any = None
    description: str = ""

    def validate_value(self, value: Any) -> bool:
        """校验给定值是否符合字段定义"""
        if value is None and not self.required:
            return True
        if self.type == DataType.ANY:
            return True
        try:
            if self.type == DataType.STRING:
                return isinstance(value, str)
            elif self.type == DataType.INTEGER:
                return isinstance(value, int) and not isinstance(value, bool)
            elif self.type == DataType.FLOAT:
                return isinstance(value, (int, float)) and not isinstance(value, bool)
            elif self.type == DataType.BOOLEAN:
                return isinstance(value, bool)
            elif self.type == DataType.LIST:
                return isinstance(value, list)
            elif self.type == DataType.DICT:
                return isinstance(value, dict)
            elif self.type == DataType.NULL:
                return value is None
        except Exception:
            return False
        return False

# ==================== 通用消息协议 ====================

@dataclass
class MessageHeader(DataProtocol):
    """
    消息头协议，包含消息元数据。
    """
    message_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = ""        # 发送方标识
    target: str = ""        # 接收方标识
    message_type: str = ""  # 消息类型，用于路由
    version: str = "1.0"    # 协议版本

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessageHeader":
        # 仅保留已知字段
        known_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered)

@dataclass
class MessagePayload(DataProtocol):
    """
    消息体协议，承载实际业务数据。
    使用字典存储任意结构，保证灵活性。
    """
    content: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"content": self.content, "metadata": self.metadata}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessagePayload":
        return cls(
            content=data.get("content"),
            metadata=data.get("metadata", {})
        )

@dataclass
class Message(DataProtocol):
    """
    通用消息协议，组合Header和Payload。
    是系统内部通信的标准数据包。
    """
    header: MessageHeader = field(default_factory=MessageHeader)
    payload: MessagePayload = field(default_factory=MessagePayload)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "header": self.header.to_dict(),
            "payload": self.payload.to_dict()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        header_data = data.get("header", {})
        payload_data = data.get("payload", {})
        return cls(
            header=MessageHeader.from_dict(header_data),
            payload=MessagePayload.from_dict(payload_data)
        )
    
    def validate(self) -> bool:
        # 校验header和payload基本合法性
        if not self.header.message_id:
            logger.warning("Message missing message_id")
            return False
        if self.header.source == "" or self.header.target == "":
            logger.warning("Message missing source or target")
            return False
        return True

# ==================== 可插拔协议注册表 ====================

class ProtocolRegistry:
    """
    协议注册表，实现可插拔的协议类型映射。
    支持动态注册/注销，便于热更新。
    """
    _registry: Dict[str, Type[DataProtocol]] = {}

    @classmethod
    def register(cls, protocol_type: str, protocol_class: Type[DataProtocol]) -> None:
        """注册一个新的协议类型"""
        if protocol_type in cls._registry:
            logger.warning(f"Protocol type '{protocol_type}' already registered, will be overwritten.")
        cls._registry[protocol_type] = protocol_class
        logger.info(f"Protocol type '{protocol_type}' registered with class {protocol_class.__name__}")

    @classmethod
    def unregister(cls, protocol_type: str) -> None:
        """注销一个协议类型"""
        if protocol_type in cls._registry:
            del cls._registry[protocol_type]
            logger.info(f"Protocol type '{protocol_type}' unregistered.")
        else:
            logger.warning(f"Attempt to unregister unknown protocol type '{protocol_type}'.")

    @classmethod
    def get_protocol_class(cls, protocol_type: str) -> Optional[Type[DataProtocol]]:
        """根据类型获取协议类，用于反序列化等场景"""
        return cls._registry.get(protocol_type)

    @classmethod
    def list_protocols(cls) -> Dict[str, Type[DataProtocol]]:
        """列出所有已注册协议"""
        return dict(cls._registry)

# 默认将通用消息协议注册到注册表
ProtocolRegistry.register("message", Message)
ProtocolRegistry.register("header", MessageHeader)
ProtocolRegistry.register("payload", MessagePayload)

# ==================== 配置化示例 ====================

def load_protocol_config(config: Dict[str, str]) -> None:
    """
    从配置字典加载并注册协议类。
    配置格式：{"type_name": "module.path.ClassName"}
    实现可配置化：根据配置动态导入并注册新的协议。
    """
    for ptype, class_path in config.items():
        try:
            module_name, class_name = class_path.rsplit('.', 1)
            mod = __import__(module_name, fromlist=[class_name])
            cls = getattr(mod, class_name)
            if issubclass(cls, DataProtocol):
                ProtocolRegistry.register(ptype, cls)
            else:
                logger.error(f"Class {class_name} is not a DataProtocol subclass, skipping.")
        except Exception as e:
            logger.error(f"Failed to load protocol '{ptype}' from {class_path}: {e}")

# ==================== 自测模块 ====================

def _self_test():
    """本模块自测函数，验证基本功能"""
    print("=== 数据协议自测开始 ===")
    # 测试 Message 序列化/反序列化
    msg = Message(
        header=MessageHeader(
            message_id="test_001",
            source="agent1",
            target="agent2",
            message_type="request"
        ),
        payload=MessagePayload(
            content={"key": "value"},
            metadata={"encoding": "utf-8"}
        )
    )
    json_str = msg.to_json()
    print("序列化结果:", json_str)

    # 反序列化
    msg2 = Message.from_json(json_str)
    print("反序列化后header:", msg2.header.to_dict())
    print("校验通过:", msg2.validate())

    # 测试协议注册表
    print("已注册协议:", ProtocolRegistry.list_protocols().keys())
    
    # 测试动态注册新协议
    @dataclass
    class CustomMessage(DataProtocol):
        custom_field: str = ""
        def to_dict(self): return asdict(self)
        @classmethod
        def from_dict(cls, data): return cls(**data)
    
    ProtocolRegistry.register("custom", CustomMessage)
    custom_cls = ProtocolRegistry.get_protocol_class("custom")
    if custom_cls:
        obj = custom_cls(custom_field="hello")
        print("动态注册协议测试:", obj.to_dict())
    print("=== 自测通过 ===")

if __name__ == "__main__":
    # 默认日志输出到控制台，方便自测
    logging.basicConfig(level=logging.DEBUG)
    _self_test()