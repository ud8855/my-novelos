# 数据结构协议.py
# 位于: NovelOS/32_架构治理/数据结构协议/
# 职责: 定义系统中所有模块统一使用的数据序列化/反序列化协议，确保数据可插拔、可配置、跨模块通用
# 依赖: 配置模块(24_配置中心), 日志模块(23_日志系统)
# 被调: 所有需要进行数据持久化、通信、缓存的模块

import logging
import importlib
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type, List

# ---------- 配置占位 ----------
# 未来接入 24_配置中心/配置管理.py 统一管理，当前通过环境变量或直接常量
DEFAULT_PROTOCOL = "json"  # 可选: json, pickle, custom
ENCODING = "utf-8"

# ---------- 日志初始化 ----------
# 未来接入 23_日志系统/日志管理器.py，当前使用标准logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s [%(name)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class DataSerializationProtocol(ABC):
    """数据序列化协议抽象基类，所有具体协议必须实现此接口"""
    
    @abstractmethod
    def serialize(self, data: Any) -> bytes:
        """将数据对象序列化为字节流"""
        ...
    
    @abstractmethod
    def deserialize(self, raw: bytes, target_type: Optional[Type] = None) -> Any:
        """将字节流反序列化为原始数据对象"""
        ...
    
    @property
    @abstractmethod
    def content_type(self) -> str:
        """返回协议对应的MIME类型或标识"""
        ...
    
    def dumps(self, data: Any) -> bytes:
        """序列化便捷方法，可添加通用日志或包装"""
        try:
            result = self.serialize(data)
            logger.debug(f"Serialized data of type {type(data).__name__}")
            return result
        except Exception as e:
            logger.error(f"Serialization failed: {e}")
            raise
    
    def loads(self, raw: bytes, target_type: Optional[Type] = None) -> Any:
        """反序列化便捷方法"""
        try:
            data = self.deserialize(raw, target_type)
            logger.debug(f"Deserialized data of type {type(data).__name__}")
            return data
        except Exception as e:
            logger.error(f"Deserialization failed: {e}")
            raise


class JsonProtocol(DataSerializationProtocol):
    """JSON 协议实现"""
    
    def __init__(self):
        self._content_type = "application/json"
    
    @property
    def content_type(self) -> str:
        return self._content_type
    
    def serialize(self, data: Any) -> bytes:
        import json
        # 默认支持中文不转义，ensure_ascii=False
        return json.dumps(data, ensure_ascii=False, default=str).encode(ENCODING)
    
    def deserialize(self, raw: bytes, target_type: Optional[Type] = None) -> Any:
        import json
        return json.loads(raw.decode(ENCODING))


class PickleProtocol(DataSerializationProtocol):
    """Pickle 协议实现（注意安全性，仅在可信环境使用）"""
    
    def __init__(self):
        self._content_type = "application/python-pickle"
    
    @property
    def content_type(self) -> str:
        return self._content_type
    
    def serialize(self, data: Any) -> bytes:
        import pickle
        return pickle.dumps(data)
    
    def deserialize(self, raw: bytes, target_type: Optional[Type] = None) -> Any:
        import pickle
        return pickle.loads(raw)


class CustomProtocol(DataSerializationProtocol):
    """自定义协议占位，未来扩展其他序列化方式（如MessagePack, YAML等）"""
    
    def __init__(self):
        self._content_type = "application/octet-stream"
    
    @property
    def content_type(self) -> str:
        return self._content_type
    
    def serialize(self, data: Any) -> bytes:
        # 占位：实际实现待后续扩展
        raise NotImplementedError("CustomProtocol serialize not implemented")
    
    def deserialize(self, raw: bytes, target_type: Optional[Type] = None) -> Any:
        raise NotImplementedError("CustomProtocol deserialize not implemented")


# ---------- 协议注册表（可插拔）----------
_PROTOCOL_REGISTRY: Dict[str, Type[DataSerializationProtocol]] = {}
_DEFAULT_INSTANCE: Optional[DataSerializationProtocol] = None


def register_protocol(name: str, protocol_class: Type[DataSerializationProtocol]):
    """注册一个新的协议实现"""
    if not issubclass(protocol_class, DataSerializationProtocol):
        raise TypeError(f"{protocol_class} must be a subclass of DataSerializationProtocol")
    _PROTOCOL_REGISTRY[name] = protocol_class
    logger.info(f"Registered protocol: {name} -> {protocol_class.__name__}")


def get_protocol() -> DataSerializationProtocol:
    """根据配置获取当前使用的协议实例（单例模式）"""
    global _DEFAULT_INSTANCE
    if _DEFAULT_INSTANCE is not None:
        return _DEFAULT_INSTANCE
    
    # 配置化选项，未来从 配置中心 读取
    protocol_name = DEFAULT_PROTOCOL
    # 支持环境变量覆盖（临时方案）
    import os
    protocol_name = os.environ.get("NOVELOS_DATA_PROTOCOL", protocol_name)
    
    if protocol_name not in _PROTOCOL_REGISTRY:
        logger.warning(f"Protocol '{protocol_name}' not registered, falling back to json")
        protocol_name = "json"
    
    protocol_class = _PROTOCOL_REGISTRY[protocol_name]
    _DEFAULT_INSTANCE = protocol_class()
    logger.info(f"Using data protocol: {protocol_name} ({protocol_class.__name__})")
    return _DEFAULT_INSTANCE


def reset_protocol():
    """重置协议单例（用于热更新或测试）"""
    global _DEFAULT_INSTANCE
    _DEFAULT_INSTANCE = None
    logger.info("Protocol instance reset.")


# ---------- 默认注册常见协议 ----------
register_protocol("json", JsonProtocol)
register_protocol("pickle", PickleProtocol)
register_protocol("custom", CustomProtocol)


# ---------- 自检与单元测试 ----------
if __name__ == "__main__":
    print("=== 数据结构协议 自测 ===")
    # 设置日志级别为DEBUG以观察细节
    logging.getLogger(__name__).setLevel(logging.DEBUG)
    
    # 测试获取协议
    proto = get_protocol()
    assert isinstance(proto, DataSerializationProtocol)
    print(f"当前协议: {proto.__class__.__name__}, content_type: {proto.content_type}")
    
    # 测试序列化/反序列化
    test_data = {"novel": "起源之书", "chapter": 1, "labels": ["AI", "哲学"]}
    raw = proto.serialize(test_data)
    print(f"序列化字节: {raw[:50]}...")
    
    restored = proto.deserialize(raw)
    assert restored == test_data, "序列化/反序列化不一致"
    print("基础测试通过")
    
    # 测试pickle协议
    reset_protocol()
    import os
    os.environ["NOVELOS_DATA_PROTOCOL"] = "pickle"
    proto2 = get_protocol()
    print(f"切换到协议: {proto2.__class__.__name__}")
    raw2 = proto2.serialize(test_data)
    restored2 = proto2.deserialize(raw2)
    assert restored2 == test_data
    print("Pickle协议测试通过")
    
    # 测试未注册协议回退
    os.environ["NOVELOS_DATA_PROTOCOL"] = "msgpack"
    reset_protocol()
    proto3 = get_protocol()
    print(f"回退后协议: {proto3.__class__.__name__}")
    assert isinstance(proto3, JsonProtocol)  # 默认回退到json
    print("协议回退测试通过")
    
    # 测试custom协议未实现
    os.environ["NOVELOS_DATA_PROTOCOL"] = "custom"
    reset_protocol()
    proto4 = get_protocol()
    try:
        proto4.serialize(test_data)
    except NotImplementedError:
        print("Custom协议正确触发未实现错误")
    
    # 清理环境变量
    del os.environ["NOVELOS_DATA_PROTOCOL"]
    reset_protocol()
    print("自测完成")