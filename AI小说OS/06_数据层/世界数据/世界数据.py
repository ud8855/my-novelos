from __future__ import annotations
import logging
import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

# 配置化：世界数据存储配置
DEFAULT_CONFIG = {
    "storage_type": "memory",  # 可选: memory, file
    "file_path": "data/world_data.json",
}

# 日志
logger = logging.getLogger("WorldData")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

class WorldDataStorage(ABC):
    """
    世界数据存储抽象基类。
    定义统一接口，支持可插拔存储后端（内存、文件、数据库等）。
    """
    @abstractmethod
    def load_world(self, world_id: str) -> Optional[Dict[str, Any]]:
        """加载指定世界的数据，返回字典或None"""
        pass

    @abstractmethod
    def save_world(self, world_id: str, data: Dict[str, Any]) -> bool:
        """保存世界数据，成功返回True"""
        pass

    @abstractmethod
    def list_worlds(self) -> List[str]:
        """列出所有世界ID"""
        pass

    @abstractmethod
    def delete_world(self, world_id: str) -> bool:
        """删除世界数据"""
        pass

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or DEFAULT_CONFIG.copy()
        logger.info(f"{self.__class__.__name__} 初始化完成，配置: {self.config}")

class InMemoryWorldDataStorage(WorldDataStorage):
    """内存存储实现，用于测试和开发"""
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._storage: Dict[str, Dict[str, Any]] = {}

    def load_world(self, world_id: str) -> Optional[Dict[str, Any]]:
        logger.info(f"从内存加载世界: {world_id}")
        return self._storage.get(world_id)

    def save_world(self, world_id: str, data: Dict[str, Any]) -> bool:
        logger.info(f"保存世界到内存: {world_id}")
        self._storage[world_id] = data.copy()
        return True

    def list_worlds(self) -> List[str]:
        worlds = list(self._storage.keys())
        logger.info(f"返回世界列表: {worlds}")
        return worlds

    def delete_world(self, world_id: str) -> bool:
        if world_id in self._storage:
            del self._storage[world_id]
            logger.info(f"删除世界: {world_id}")
            return True
        logger.warning(f"尝试删除不存在的世界: {world_id}")
        return False

class FileWorldDataStorage(WorldDataStorage):
    """文件存储实现"""
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.file_path = self.config.get("file_path", "data/world_data.json")
        # 确保目录存在
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        # 初始化文件（如果不存在）
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)
            logger.info(f"创建世界数据文件: {self.file_path}")
        self._ensure_file()

    def _ensure_file(self):
        """确保文件合法"""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            logger.warning(f"世界数据文件损坏或不存在，重建: {self.file_path}")
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    def _read_all(self) -> Dict[str, Any]:
        with open(self.file_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _write_all(self, data: Dict[str, Any]):
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_world(self, world_id: str) -> Optional[Dict[str, Any]]:
        logger.info(f"从文件加载世界: {world_id}")
        all_data = self._read_all()
        return all_data.get(world_id)

    def save_world(self, world_id: str, data: Dict[str, Any]) -> bool:
        logger.info(f"保存世界到文件: {world_id}")
        all_data = self._read_all()
        all_data[world_id] = data
        self._write_all(all_data)
        return True

    def list_worlds(self) -> List[str]:
        all_data = self._read_all()
        worlds = list(all_data.keys())
        logger.info(f"文件中的世界列表: {worlds}")
        return worlds

    def delete_world(self, world_id: str) -> bool:
        all_data = self._read_all()
        if world_id in all_data:
            del all_data[world_id]
            self._write_all(all_data)
            logger.info(f"从文件删除世界: {world_id}")
            return True
        logger.warning(f"文件世界中不存在: {world_id}")
        return False

def get_world_data_storage(config: Dict[str, Any] = None) -> WorldDataStorage:
    """
    工厂函数：根据配置返回合适的存储实例。
    可插拔：只需扩展WorldDataStorage并在此注册即可。
    """
    cfg = config or DEFAULT_CONFIG
    storage_type = cfg.get("storage_type", "memory")
    logger.info(f"创建世界数据存储，类型: {storage_type}")
    if storage_type == "memory":
        return InMemoryWorldDataStorage(cfg)
    elif storage_type == "file":
        return FileWorldDataStorage(cfg)
    else:
        logger.error(f"未知的存储类型: {storage_type}，回退到内存存储")
        return InMemoryWorldDataStorage(cfg)

# ===================== 自测代码 =====================
if __name__ == "__main__":
    print("=== 世界数据模块自测 ===")
    # 测试内存存储
    config = {"storage_type": "memory"}
    storage = get_world_data_storage(config)
    world_id = "test_world"
    world_data = {
        "name": "诺维兰",
        "history": "一场大灾变后...",
        "locations": ["风暴城", "黑森林"],
    }
    # 保存
    assert storage.save_world(world_id, world_data), "保存失败"
    # 加载
    loaded = storage.load_world(world_id)
    assert loaded == world_data, "加载数据不匹配"
    print(f"内存存储测试通过: 加载数据 {loaded['name']}")
    # 列表
    worlds = storage.list_worlds()
    assert world_id in worlds, "世界列表缺失"
    # 删除
    assert storage.delete_world(world_id), "删除失败"
    assert storage.load_world(world_id) is None, "删除后仍能加载"
    print("内存存储基本功能测试通过")

    # 测试文件存储
    file_config = {"storage_type": "file", "file_path": "test_world_data.json"}
    file_storage = get_world_data_storage(file_config)
    # 避免残留文件
    try:
        file_storage.delete_world(world_id)
    except:
        pass
    assert file_storage.save_world(world_id, world_data), "文件保存失败"
    loaded_file = file_storage.load_world(world_id)
    assert loaded_file == world_data, "文件加载数据不匹配"
    print(f"文件存储测试通过: 加载数据 {loaded_file['name']}")
    assert file_storage.delete_world(world_id), "文件删除失败"
    # 清理测试文件
    if os.path.exists(file_config["file_path"]):
        os.remove(file_config["file_path"])
        # 如果仅有该文件，可删除空目录
        dir_path = os.path.dirname(file_config["file_path"])
        if os.path.exists(dir_path) and not os.listdir(dir_path):
            os.rmdir(dir_path)
    print("文件存储基本功能测试通过")
    print("=== 世界数据模块自测完成 ===")