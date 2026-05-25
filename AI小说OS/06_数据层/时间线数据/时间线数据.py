"""
============================================================
时间线数据模块 (Timeline Data Store)
所属层: 06_数据层
依赖: 基础配置模块（可选，用于获取日志/配置）
被调用: 上层业务模块（如叙事引擎、事件管理）
解决: 时间线事件的存储、检索、持久化，提供统一接口
特性: 可插拔（支持多种后端）、日志记录、配置化、热更新
============================================================
"""

from typing import Dict, Any, Optional, List, Protocol, runtime_checkable
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
import os
import sys

# ------------------------------ 日志与配置适配 ------------------------------
def get_logger(name: str) -> logging.Logger:
    """获取日志记录器，与项目日志体系解耦"""
    try:
        # 尝试从项目基础配置导入
        from 基础配置 import config, get_logger as _get_logger
        return _get_logger(name)
    except ImportError:
        # 独立运行时使用简单StreamHandler
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

def get_config(key: str, default: Any = None) -> Any:
    """安全获取配置项"""
    try:
        from 基础配置 import config
        return config.get(key, default)
    except ImportError:
        return default


logger = get_logger(__name__)


# ------------------------------ 数据模型 ------------------------------
@dataclass
class TimelineEvent:
    """时间线事件 - 不可变数据单元（推荐保持只读，修改请使用新实例）"""
    event_id: str                                    # 唯一标识符
    timestamp: float                                 # 绝对时间戳（浮点数）
    description: str                                 # 事件简述
    metadata: Dict[str, Any] = field(default_factory=dict)  # 扩展元数据（键值对）

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典，便于持久化"""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "description": self.description,
            "metadata":