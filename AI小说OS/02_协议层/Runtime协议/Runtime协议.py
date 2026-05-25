# 02_协议层/Runtime协议
# Runtime协议定义：Runtime模块与外部交互的接口、消息格式、配置规范
# 遵循可插拔、日志、配置化原则

import logging
import json
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any, Dict, Optional
import yaml  # 假设使用YAML配置

# 配置默认日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# -------------------- 枚举定义 --------------------
class RuntimeStatus(Enum):
    """Runtime运行状态"""
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    ERROR = auto()

class EventType(Enum):
    """Runtime事件类型"""
    RUNTIME_START = "runtime.start"
    RUNTIME_STOP = "runtime.stop"
    RUNTIME_ERROR = "runtime.error"
    TASK_QUEUED = "task.queued"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    AGENT_MESSAGE = "agent.message"
    SYSTEM_NOTIFICATION = "system.notification"

# -------------------- 消息协议定义 --------------------
class Message(ABC):
    """消息基类，所有消息必须继承此类"""
    def __init__(self, event_type: EventType, payload: Dict[str, Any] = None):
        self.event_type = event_type
        self.payload = payload if payload else {}
    
    def to_dict(self) -> dict:
        """转换为字典用于序列化"""
        return {
            "event_type": self.event_type.value,
            "payload": self.payload
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Message':
        """从字典反序列化，子类需重写或直接返回基类实例"""
        return cls(event_type=EventType(data["event_type"]), payload=data["payload"])

class RuntimeMessage(Message):
    """Runtime相关消息，可扩展更多字段"""
    def __init__(self, event_type: EventType, runtime_id: str, payload: Dict[str, Any] = None):
        super().__init__(event_type, payload)
        self.runtime_id = runtime_id
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base["runtime_id"] = self.runtime_id
        return base

# -------------------- 配置协议定义 --------------------
class RuntimeConfigProtocol(ABC):
    """Runtime配置接口，用于获取Runtime运行所需配置"""
    @abstractmethod
    def get_config(self) -> Dict[str, Any]:
        """返回完整配置字典"""
        pass

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """获取单个配置项"""
        pass

class YAMLRuntimeConfig(RuntimeConfigProtocol):
    """基于YAML的Runtime配置实现（示例，正式实现应在07_Runtime层）"""
    def __init__(self, config_path: str):
        self.config_path = config_path
        self._config = {}
        self.load()
    
    def load(self):
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
            logger.info(f"配置文件加载成功: {self.config_path}")
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            self._config = {}
    
    def get_config(self) -> Dict[str, Any]:
        return self._config
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

# -------------------- Runtime抽象协议（插拔接口） --------------------
class RuntimeProtocol(ABC):
    """Runtime抽象协议，所有Runtime实现必须遵循此接口"""
    @abstractmethod
    def initialize(self, config: RuntimeConfigProtocol) -> bool:
        """使用给定配置初始化Runtime，返回是否成功"""
        pass

    @abstractmethod
    def start(self) -> bool:
        """启动Runtime，返回是否成功"""
        pass

    @abstractmethod
    def stop(self) -> bool:
        """停止Runtime，返回是否成功"""
        pass

    @abstractmethod
    def get_status(self) -> RuntimeStatus:
        """获取当前Runtime状态"""
        pass

    @abstractmethod
    def send_message(self, message: Message) -> bool:
        """发送消息至Runtime（如任务指令）"""
        pass

    @abstractmethod
    def register_handler(self, event_type: EventType, handler: callable) -> bool:
        """注册事件处理器，当指定事件发生时回调"""
        pass

    @abstractmethod
    def unregister_handler(self, event_type: EventType, handler: callable) -> bool:
        """注销事件处理器"""
        pass

# -------------------- 日志与异常 --------------------
class RuntimeError(Exception):
    """Runtime自定义异常"""
    pass

def log_exception(func):
    """装饰器，自动记录异常"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"方法 {func.__name__} 执行异常: {e}")
            raise
    return wrapper

# -------------------- 自测 --------------------
if __name__ == "__main__":
    #