"""势力数据模块
负责势力数据的持久化、查询与更新。
遵循数据层规范：只与数据存储交互，不包含业务逻辑。
"""

import logging
import json
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

# -------------------------- 配置 --------------------------
class ForceDataConfig:
    """势力数据配置，支持自定义数据文件路径，可从环境变量加载"""
    def __init__(self, data_path: str = None):
        self.data_path = data_path or os.path.join(
            os.path.dirname(__file__), "force_data.json"
        )

    @classmethod
    def from_env(cls):
        """从环境变量 FORCE_DATA_PATH 读取配置"""
        data_path = os.getenv("FORCE_DATA_PATH")
        return cls(data_path)

    def __repr__(self):
        return f"ForceDataConfig(data_path={self.data_path})"


# -------------------------- 数据提供者接口 --------------------------
class IForceDataProvider(ABC):
    """势力数据提供者抽象接口，所有具体实现必须遵循此契约"""

    @abstractmethod
    def load(self) -> None:
        """从持久化介质加载数据到内存"""

    @abstractmethod
    def save(self) -> None:
        """将内存中的数据持久化"""

    @