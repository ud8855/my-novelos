"""
上下文裁剪模块
属于：09_上下文系统
职责：根据配置策略裁剪对话上下文，以适应模型上下文窗口限制。
依赖：无其他业务模块依赖，只依赖标准库 logging 及配置。
被调用：由上下文管理器在发送模型请求前调用，提供裁剪后的上下文。
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

# 模块日志记录器
logger = logging.getLogger(__name__)

# 裁剪策略注册表，支持可插拔扩展
_TRIMMER_REGISTRY: Dict[str, type] = {}

def register_trimmer(name: str):
    """装饰器，用于注册自定义裁剪策略"""
    def decorator(cls):
        _TRIMMER_REGISTRY[name] = cls
        logger.info(f"注册裁剪策略: {name}")
        return cls
    return decorator

class BaseContextTrimmer(ABC):
    """上下文裁剪器基类，定义裁剪接口"""
    
    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.logger.debug(f"初始化裁剪器，配置: {self.config}")
    
    @abstractmethod
    def trim(self, context: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """
        裁剪上下文
        :param context: 原始上下文，为消息列表，每条消息为dict，例如 {'role': 'user',