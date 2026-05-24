"""
角色记忆模块 (Character Memory Module)
所属层: 08_记忆系统
依赖: 无直接业务依赖，可配置存储后端
被调用: 代理层 (Agent) 或 规划层 (Planner)
解决: 为小说中的每个角色维护独立的记忆系统，支持记忆的记录、检索、遗忘与总结。
"""

import logging
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

# ---------- 配置管理 ----------
class CharacterMemoryConfig:
    """
    角色记忆配置
    支持从字典、JSON文件或环境变量加载，实现配置化
    """
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        default_config = {
            "storage_backend": "memory",   # 默认内存存储，可替换为 'file'、'redis' 等
            "log_level": "INFO",
            "enable_compression": False,
        }
        self._config = default_config.copy()
        if config_dict:
            self._config.update(config_dict)

    def __getattr__(self, name: str) -> Any:
        if name in self._config:
            return self._config[name]
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

    def load_from_file(self, file_path: str):
        """从 JSON 文件加载配置"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self._config.update(data)

# ---------- 存储后端抽象接口 ----------
class StorageBackend(ABC):
    """存储后端抽象基类，实现可插拔架构"""
    @abstractmethod
    def get(self, character_id: str, key: str) -> Optional[Any]:
        """获取指定角色的某个记忆"""

    @abstractmethod
    def set(self, character_id: str, key: str, value: Any):
        """设置指定角色的某个记忆"""

    @abstractmethod
    def delete(self, character_id: str, key: str):
        """删除指定角色的某个记忆"""

    @abstractmethod
    def get_all(self, character_id: str) -> Dict[str, Any]:
        """获取指定角色的全部记忆"""

    def __repr__(self):
        return f"<{self.__class__.__name__}>"

# ---------- 内存存储实现 ----------
class MemoryStorage(StorageBackend):
    """基于内存的存储实现 (用于测试或轻量场景)"""
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def get(self, character_id: str, key: str) -> Optional[Any]:
        char_dict = self._store.get(character_id, {})
        return char_dict.get(key)

    def set(self, character_id: str, key: str, value: Any):
        if character_id not in self._store:
            self._store[character_id] = {}
        self._store[character_id][key] = value

    def delete(self, character_id: str, key: str):
        if character_id in self._store and key in self._store[character_id]:
            del self._store[character_id][key]

    def get_all(self, character_id: str) -> Dict[str, Any]:
        return self._store.get(character_id, {})

# ---------- Json文件存储实现 (示例可插拔) ----------
class JsonFileStorage(StorageBackend):
    """基于 JSON 文件的存储实现 (扩展示例)"""
    def __init__(self, storage_dir: str = "./character_memory"):
        self.storage_dir = storage_dir
        import os
        os.makedirs(self.storage_dir, exist_ok=True)

    def _file_path(self, character_id: str) -> str:
        return f"{self.storage_dir}/{character_id}.json"

    def _load(self, character_id: str) -> Dict[str, Any]:
        try:
            with open(self._file_path(character_id), 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def _save(self, character_id: str, data: Dict[str, Any]):
        with open(self._file_path(character_id), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get(self, character_id: str, key: str) -> Optional[Any]:
        data = self._load(character_id)
        return data.get(key)

    def set(self, character_id: str, key: str, value: Any):
        data = self._load(character_id)
        data[key] = value
        self._save(character_id, data)

    def delete(self, character_id: str, key: str):
        data = self._load(character_id)
        if key in data:
            del data[key]
            self._save(character_id, data)

    def get_all(self, character_id: str) -> Dict[str, Any]:
        return self._load(character_id)

# ---------- 角色记忆主类 ----------
class CharacterMemory:
    """
    角色记忆管理器
    负责与存储后端交互，提供统一接口，记录操作日志，并预留模型调用接口
    """
    def __init__(self, config: Optional[CharacterMemoryConfig] = None):
        self.config = config or CharacterMemoryConfig()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, self.config.log_level))
        self.storage = self._init_storage()
        self.logger.info(f"CharacterMemory initialized with {self.storage}")

    def _init_storage(self) -> StorageBackend:
        backend_type = self.config.storage_backend
        if backend_type == "memory":
            return MemoryStorage()
        elif backend_type == "json_file":
            # 可配置目录，此处简化
            return JsonFileStorage()
        else:
            self.logger.warning(f"Unknown storage backend '{backend_type}', fallback to memory.")
            return MemoryStorage()

    # ---------- 基础 CRUD ----------
    def remember(self, character_id: str, key: str, value: Any):
        """记录记忆 (Remember)"""
        self.logger.info(f"Remember: {character_id}.{key} = {value}")
        self.storage.set(character_id, key, value)

    def recall(self, character_id: str, key: str) -> Optional[Any]:
        """检索记忆 (Recall)"""
        result = self.storage.get(character_id, key)
        self.logger.debug(f"Recall: {character_id}.{key} -> {result}")
        return result

    def forget(self, character_id: str, key: str):
        """遗忘记忆 (Forget)"""
        self.logger.info(f"Forget: {character_id}.{key}")
        self.storage.delete(character_id, key)

    def recall_all(self, character_id: str) -> Dict[str, Any]:
        """获取角色全部记忆"""
        return self.storage.get_all(character_id)

    # ---------- 高级操作 (预留模型调用) ----------
    def summarize(self, character_id: str) -> str:
        """
        总结角色记忆 (需要调用模型，当前返回原始记忆的JSON字符串作为占位)
        实际实现应通过 20_模型协同/ 和 21_API模型/ 进行调用
        """
        all_mem = self.recall_all(character_id)
        # TODO: 构造专门的角色总结 Prompt，并调用模型
        self.logger.info(f"Generate summary for {character_id}")
        return json.dumps(all_mem, ensure_ascii=False)

    def update_from_model_output(self, character_id: str, key: str, model_output: Any):
        """
        将模型输出的结果更新到记忆 (预留)
        """
        self.remember(character_id, key, model_output)

# ---------- 自测 ----------
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 测试内存存储
    config = CharacterMemoryConfig()
    cm = CharacterMemory(config)