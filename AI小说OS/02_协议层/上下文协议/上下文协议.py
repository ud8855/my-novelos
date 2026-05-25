"""
NovelOS - 02_协议层/上下文协议/上下文协议.py
上下文协议模块：定义Agent间上下文传递的标准接口与数据结构。
属于：02_协议层
依赖：标准库（序列化、日志、配置）
被调用：上层Agent模块、运行环境等，用于统一上下文交互格式。
解决：上下文序列化/反序列化、校验、版本兼容，保证多Agent协同时可插拔、可演化。
"""

import abc
import json
import logging
import os
from configparser import ConfigParser
from typing import Any, Dict, Optional, Type

# --- 日志配置 ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
    ))
    logger.addHandler(_handler)

# --- 配置管理（可插拔） ---
def _load_protocol_config() -> ConfigParser:
    """加载上下文协议的配置文件，支持热加载"""
    config = ConfigParser()
    config_path = os.environ.get(
        "CONTEXT_PROTOCOL_CONFIG",
        os.path.join(os.path.dirname(__file__), "context_protocol.ini")
    )
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
        logger.info("上下文协议配置加载自: %s", config_path)
    else:
        logger.warning("未找到上下文协议配置文件: %s，使用默认值", config_path)
    return config

_config = _load_protocol_config()

# 从配置获取默认协议实现类名，若没有则使用 JsonContextProtocol
DEFAULT_PROTOCOL_CLASS = _config.get(
    "protocol", "default_class", fallback="JsonContextProtocol"
)
# 协议版本，用于兼容性检查
PROTOCOL_VERSION = _config.get("protocol", "version", fallback="1.0.0")

# --- 数据结构定义 ---
class ContextData:
    """
    上下文载体，包含通用字段和扩展字段。
    字段使用英文标识符，注释使用中文。
    """
    def __init__(
        self,
        agent_id: str,
        session_id: str,
        timestamp: float,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        version: str = PROTOCOL_VERSION
    ):
        self.agent_id = agent_id          # 来源Agent标识
        self.session_id = session_id      # 会话标识
        self.timestamp = timestamp        # 时间戳（秒）
        self.payload = payload            # 核心业务数据
        self.metadata = metadata or {}    # 附加元数据（可插拔扩展）
        self.version = version            # 协议版本，用于兼容

    def to_dict(self) -> Dict[str, Any]:
        """将上下文数据转换为字典，便于序列化"""
        return {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "metadata": self.metadata,
            "version": self.version
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContextData':
        """从字典重建上下文对象"""
        return cls(
            agent_id=data["agent_id"],
            session_id=data["session_id"],
            timestamp=data["timestamp"],
            payload=data["payload"],
            metadata=data.get("metadata"),
            version=data.get("version", PROTOCOL_VERSION)
        )

    def __repr__(self):
        return (f"ContextData(agent={self.agent_id}, session={self.session_id}, "
                f"version={self.version}, payload_keys={list(self.payload.keys())})")


# --- 上下文协议抽象基类 ---
class ContextProtocol(abc.ABC):
    """
    上下文协议抽象基类，定义了上下文数据的编码、解码与校验标准接口。
    不同序列化实现（JSON, msgpack, protobuf）继承此类即可插拔接入系统。
    """
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abc.abstractmethod
    def encode(self, context: ContextData) -> bytes:
        """
        将上下文对象编码为字节流
        :param context: 上下文数据实例
        :return: 字节流
        """
        ...

    @abc.abstractmethod
    def decode(self, data: bytes) -> ContextData:
        """
        从字节流解码为上下文对象
        :param data: 编码后的字节流
        :return: 上下文数据实例
        """
        ...

    def validate(self, context: ContextData) -> bool:
        """
        校验上下文数据完整性（默认检查基本字段存在性）
        子类可覆盖实现更严格的校验规则
        """
        if not context.agent_id or not context.session_id:
            self.logger.warning("上下文缺少 agent_id 或 session_id")
            return False
        if not isinstance(context.payload, dict):
            self.logger.warning("payload 不是字典类型")
            return False
        return True

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """返回当前协议的配置信息（可被子类覆盖）"""
        return {"version": PROTOCOL_VERSION}

# --- 默认JSON协议实现 ---
class JsonContextProtocol(ContextProtocol):
    """
    基于JSON的上下文协议实现。
    适用于调试、简单场景，具备可插拔性。
    """
    def encode(self, context: ContextData) -> bytes:
        """将上下文转为JSON字节流"""
        self.logger.debug("编码上下文: %s", context)
        try:
            return json.dumps(context.to_dict(), ensure_ascii=False).encode('utf-8')
        except Exception as e:
            self.logger.error("上下文JSON编码失败: %s", e)
            raise

    def decode(self, data: bytes) -> ContextData:
        """从JSON字节流解码为上下文对象"""
        try:
            obj = json.loads(data.decode('utf-8'))
            self.logger.debug("解码上下文: %s", obj.get("agent_id"))
            return ContextData.from_dict(obj)
        except Exception as e:
            self.logger.error("上下文JSON解码失败: %s", e)
            raise

    def validate(self, context: ContextData) -> bool:
        """JSON协议校验：除了基类校验外，检查版本兼容性"""
        if not super().validate(context):
            return False
        # 简单的版本检查示例：要求主版本一致
        if context.version.split('.')[0] != PROTOCOL_VERSION.split('.')[0]:
            self.logger.warning("上下文版本 %s 与协议版本 %s 可能不兼容",
                                context.version, PROTOCOL_VERSION)
            # 这里根据策略决定是否拒绝，当前暂时只警告
            return True
        return True


# --- 协议工厂（可插拔加载） ---
class ContextProtocolFactory:
    """
    协议工厂，根据配置或参数创建上下文协议实例。
    实现运行时动态切换协议，支持热更新。
    """
    _registry: Dict[str, Type[ContextProtocol]] = {}

    @classmethod
    def register(cls, name: str, protocol_cls: Type[ContextProtocol]):
        """注册协议实现类"""
        cls._registry[name] = protocol_cls
        logger.info("注册上下文协议: %s -> %s", name, protocol_cls.__name__)

    @classmethod
    def get_protocol(cls, name: str = None) -> ContextProtocol:
        """获取协议实例，若不指定名称则使用配置默认值"""
        if name is None:
            name = DEFAULT_PROTOCOL_CLASS
        if name not in cls._registry:
            logger.error("未找到协议: %s", name)
            raise ValueError(f"未知上下文协议: {name}")
        protocol_cls = cls._registry[name]
        return protocol_cls()

    @classmethod
    def list_registered(cls) -> list:
        """列出所有已注册的协议名称"""
        return list(cls._registry.keys())

# 默认注册JSON协议
ContextProtocolFactory.register("JsonContextProtocol", JsonContextProtocol)

# --- 自测逻辑 ---
if __name__ == "__main__":
    print("=== 上下文协议自测 ===")
    # 创建测试上下文
    ctx = ContextData(
        agent_id="agent_01",
        session_id="sess_123",
        timestamp=1234567890.0,
        payload={"chapter": 3, "content": "主角推开了门..."},
        metadata={"emotion": "surprise"}
    )

    # 获取默认协议（JSON）
    protocol = ContextProtocolFactory.get_protocol()
    print(f"使用协议: {protocol.__class__.__name__}")

    # 编码
    encoded = protocol.encode(ctx)
    print(f"编码后字节长度: {len(encoded)}")
    print(f"编码内容(前100字节): {encoded[:100]}")

    # 解码
    decoded_ctx = protocol.decode(encoded)
    print(f"解码后上下文: {decoded_ctx}")

    # 校验
    valid = protocol.validate(decoded_ctx)
    print(f"校验结果: {valid}")

    # 测试注册表
    print(f"已注册协议: {ContextProtocolFactory.list_registered()}")

    # 测试不存在的协议
    try:
        ContextProtocolFactory.get_protocol("NonExist")
    except ValueError as e:
        print(f"捕获预期异常: {e}")

    print("自测完成。")