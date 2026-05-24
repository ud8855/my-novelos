import os
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

# 默认配置（将逐步由框架配置管理器接管）
DEFAULT_CONFIG = {
    "backend": "json",          # 存储后端：json, sqlite（待扩展）
    "data_dir": "data/long_term_memory",
    "log_level": "INFO"
}

# 模块日志
logger = logging.getLogger("LongTermMemory")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class MemoryBackend(ABC):
    """存储后端抽象基类，所有具体实现需继承此类"""
    @abstractmethod
    def store(self, key: str, data: Dict[str, Any]) -> None:
        """存储一条记忆"""
        pass

    @abstractmethod
    def retrieve(self, key: str) -> Optional[Dict[str, Any]]:
        """检索一条记忆"""
        pass

    @abstractmethod
    def update(self, key: str, data: Dict[str, Any]) -> None:
        """更新一条记忆"""
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """删除一条记忆"""
        pass

    @abstractmethod
    def list_all(self) -> List[str]:
        """列出所有记忆的键"""
        pass


class JSONMemoryBackend(MemoryBackend):
    """基于JSON文件的简单存储后端（用于开发和测试）"""
    def __init__(self, data_dir: str = "data/long_term_memory"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._memory_file = self.data_dir / "memory.json"
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self):
        if self._memory_file.exists():
            try:
                with open(self._memory_file, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
            except Exception as e:
                logger.error(f"加载记忆文件失败: {e}")
                self._data = {}
        else:
            self._data = {}

    def _save(self):
        try:
            with open(self._memory_file, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存记忆文件失败: {e}")

    def store(self, key: str, data: Dict[str, Any]) -> None:
        logger.info(f"存储记忆: {key}")
        self._data[key] = data
        self._save()

    def retrieve(self, key: str) -> Optional[Dict[str, Any]]:
        logger.info(f"检索记忆: {key}")
        return self._data.get(key)

    def update(self, key: str, data: Dict[str, Any]) -> None:
        logger.info(f"更新记忆: {key}")
        if key in self._data:
            self._data[key].update(data)
        else:
            self._data[key] = data
        self._save()

    def delete(self, key: str) -> None:
        logger.info(f"删除记忆: {key}")
        if key in self._data:
            del self._data[key]
            self._save()

    def list_all(self) -> List[str]:
        return list(self._data.keys())


class LongTermMemory:
    """
    长期记忆系统
    提供统一接口，可插拔后端（通过配置切换）
    """
    def __init__(self, config: Dict[str, Any] = None):
        if config is None:
            config = DEFAULT_CONFIG
        
        self.config = config
        backend_type = config.get("backend", "json")
        data_dir = config.get("data_dir", "data/long_term_memory")
        
        # 可插拔后端选择
        if backend_type == "json":
            self.backend = JSONMemoryBackend(data_dir=data_dir)
        # 未来可扩展：elif backend_type == "sqlite": ...
        else:
            logger.warning(f"未知后端类型 {backend_type}，回退到JSON")
            self.backend = JSONMemoryBackend(data_dir=data_dir)
        
        logger.info(f"长期记忆系统初始化完成，后端类型: {backend_type}")

    def remember(self, key: str, data: Dict[str, Any]) -> None:
        """存储记忆"""
        self.backend.store(key, data)

    def recall(self, key: