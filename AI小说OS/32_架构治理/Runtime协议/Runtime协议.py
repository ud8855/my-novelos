"""
模块：Runtime协议
路径：32_架构治理/Runtime协议/Runtime协议.py
功能：定义NovelOS运行时通信协议接口，包括消息传递、Agent注册、心跳检测等。
     本模块仅定义协议抽象，具体实现由20_模型协同、21_API模型等模块注入。
依赖：标准库abc, typing, logging, dataclasses, json/yaml
被调用：20_模型协同、30_调度路由、31_系统监控、33_配置中心等
设计原则：插拔、日志、配置化
"""

import logging
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from enum import Enum

# 配置日志
logger = logging.getLogger(__name__)

class MessageType(str, Enum):
    """消息类型枚举"""
    HEARTBEAT = "heartbeat"
    REGISTER = "register"
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"

@dataclass
class Message:
    """基础消息结构"""
    msg_id: str
    msg_type: MessageType
    sender_id: str
    receiver_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

@dataclass
class RuntimeConfig:
    """运行时协议配置"""
    heartbeat_interval: float = 5.0  # 心跳间隔秒
    max_retries: int = 3
    timeout: float = 10.0
    protocol_version: str = "1.0"
    enable_health_check: bool = True
    custom: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, config_dict: dict) -> 'RuntimeConfig':
        """从字典加载配置"""
        return cls(**config_dict)

    @classmethod
    def from_file(cls, filepath: str) -> 'RuntimeConfig':
        """从JSON/YAML文件加载配置"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls.from_dict(data.get('runtime_protocol', {}))

class RuntimeProtocol(ABC):
    """运行时协议抽象基类
    所有具体通信协议必须实现此接口。
    """
    def __init__(self, config: RuntimeConfig):
        self.config = config
        self._agents: Dict[str, Any] = {}  # 注册的Agent信息
        logger.info(f"RuntimeProtocol initialized with config: {config}")

    @abstractmethod
    async def send_message(self, message: Message) -> bool:
        """发送消息到指定接收者"""
        ...

    @abstractmethod
    async def receive_message(self) -> Optional[Message]:
        """接收消息（非阻塞）"""
        ...

    @abstractmethod
    async def register_agent(self, agent_id: str, agent_info: Dict[str, Any]) -> bool:
        """注册Agent到运行时"""
        ...

    @abstractmethod
    async def unregister_agent(self, agent_id: str) -> bool:
        """注销Agent"""
        ...

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """执行健康检查，返回状态信息"""
        ...

    def get_config(self) -> RuntimeConfig:
        """获取当前配置"""
        return self.config

    def update_config(self, new_config: RuntimeConfig) -> None:
        """更新配置"""
        self.config = new_config
        logger.info("Runtime config updated")

# 可插拔协议工厂
class ProtocolFactory:
    """协议工厂，根据配置创建具体协议实例"""
    _protocols: Dict[str, type] = {}

    @classmethod
    def register_protocol(cls, name: str, protocol_cls: type) -> None:
        """注册协议实现类"""
        if not issubclass(protocol_cls, RuntimeProtocol):
            raise TypeError("protocol_cls must be a subclass of RuntimeProtocol")
        cls._protocols[name] = protocol_cls
        logger.info(f"Protocol '{name}' registered.")

    @classmethod
    def create_protocol(cls, name: str, config: RuntimeConfig) -> RuntimeProtocol:
        """创建协议实例"""
        if name not in cls._protocols:
            raise ValueError(f"Unknown protocol: {name}")
        return cls._protocols[name](config)

# 自测代码
if __name__ == "__main__":
    # 配置日志输出
    logging.basicConfig(level=logging.INFO)
    logger.info("Testing Runtime Protocol Module")

    # 1. 测试配置加载
    test_config = {
        "heartbeat_interval": 10.0,
        "max_retries": 5,
        "timeout": 20.0,
        "protocol_version": "1.0",
        "enable_health_check": True
    }
    config = RuntimeConfig.from_dict(test_config)
    print("Config loaded:", config)

    # 2. 测试协议工厂
    class MockProtocol(RuntimeProtocol):
        """模拟协议，用于测试"""
        async def send_message(self