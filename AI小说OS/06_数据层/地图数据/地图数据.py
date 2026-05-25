"""地图数据模块

层级: 06_数据层
功能: 提供地图数据的存储、读取、更新等基础操作
依赖: 日志系统、配置系统
被调用: 被上层服务调用(如场景构建、地图展示等)
解决: 地图数据的标准化存储与访问
"""

import logging
import json
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import configparser
import os

# -------------------- 日志配置 --------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)


class MapDataManager:
    """地图数据管理器，支持可插拔的存储后端和配置化加载"""

    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None):
        """
        初始化地图数据管理器
        :param config: 直接传入配置字典，优先级高于配置文件
        :param config_path: 配置文件路径
        """
        self.config = self._load_config(config, config_path)
        self.backend = self._initialize_backend()
        self.cache = {}  # 简单的内存缓存，后续可替换为专用缓存模块
        logger.info("MapDataManager 初始化完成，后端类型: %s", type(self.backend).__name__)

    def _load_config(self, config: Optional[Dict[str, Any]], config_path: Optional[str]) -> Dict[str, Any]:
        """加载配置，支持字典和配置文件两种方式"""
        default_config = {
            "backend": "json_file",          # 默认后端为json文件存储
            "json_file_path": "data/maps.json",
            "cache_enabled": True,
            "cache_max_size": 100,
            "db_config": {}                  # 数据库配置，为未来扩展预留
        }
        if config_path and os.path.exists(config_path):
            parser = configparser.ConfigParser()
            parser.read(config_path, encoding='utf-8')
            for section in parser.sections():
                for key, value in parser.items(section):
                    default_config[key] = value
        if config:
            default_config.update(config)
        # 处理相对路径：确保文件存储路径是绝对路径或相对于工作目录
        if "json_file_path" in default_config:
            p = Path(default_config["json_file_path"])
            if not p.is_absolute():
                default_config["json_file_path"] = str(Path.cwd() / p)
        logger.debug("地图模块配置: %s", default_config)
        return default_config

    def _initialize_backend(self):
        """根据配置初始化存储后端（可插拔设计）"""
        backend_type = self.config.get("backend", "json_file")
        if backend_type == "json_file":
            return _JsonFileBackend(self.config.get("json_file_path", "data/maps.json"))
        elif backend_type == "sqlite":
            return _SqliteBackend(self.config.get("db_config", {}))
        else:
            logger.warning("未知后端类型 %s，使用默认json_file后端", backend_type)
            return _JsonFileBackend(self.config.get("json_file_path", "data/maps.json"))

    # ==================== 核心接口 ====================
    def get_map(self, map_id: str) -> Optional[Dict[str, Any]]:
        """获取指定ID的地图数据"""
        if not map_id:
            return None
        # 尝试从缓存获取
        if self.config.get("cache_enabled") and map_id in self.cache:
            logger.debug("从缓存获取地图 %s", map_id)
            return self.cache[map_id]
        try:
            data = self.backend.read(map_id)
            if data and self.config.get("cache_enabled"):
                self.cache[map_id] = data
            return data
        except Exception as e:
            logger.error("获取地图 %s 失败: %s", map_id, e)
            return None

    def save_map(self, map_id: str, map_data: Dict[str, Any]) -> bool:
        """保存或更新地图数据"""
        if not map_id or not map_data:
            return False
        try:
            success = self.backend.write(map_id, map_data)
            if success and self.config.get("cache_enabled"):
                self.cache[map_id] = map_data
            return success
        except Exception as e:
            logger.error("保存地图 %s 失败: %s", map_id, e)
            return False

    def delete_map(self, map_id: str) -> bool:
        """删除地图数据"""
        if not map_id:
            return False
        try:
            success = self.backend.delete(map_id)
            if success:
                self.cache.pop(map_id, None)
            return success
        except Exception as e:
            logger.error("删除地图 %s 失败: %s", map_id, e)
            return False

    def list_maps(self, filter_func=None) -> List[Dict[str, Any]]:
        """列出所有地图数据，可选过滤"""
        try:
            all_data = self.backend.list_all()
            if filter_func:
                return [m for m in all_data if filter_func(m)]
            return all_data
        except Exception as e:
            logger.error("列出地图失败: %s", e)
            return []

    def search_maps_by_name(self, name: str) -> List[Dict[str, Any]]:
        """按名称模糊搜索地图（简单实现，实际可由后端优化）"""
        if not name:
            return []
        return [m for m in self.list_maps() if name.lower() in m.get("name", "").lower()]

    # ==================== 扩展预留接口 ====================
    def reload_backend(self, backend_config: Dict[str, Any]) -> None:
        """热替换存储后端（热插拔）"""
        old_backend = self.backend
        self.config["backend"] = backend_config.get("backend", "json_file")
        self.config.update(backend_config)
        self.backend = self._initialize_backend()
        logger.info("存储后端已从 %s 切换至 %s", type(old_backend).__name__, type(self.backend).__name__)

    def clear_cache(self):
        """清空内存缓存"""
        self.cache.clear()
        logger.info("地图数据缓存已清空")

    # ==================== 自测 ====================
    @staticmethod
    def self_test():
        """模块自测，验证基本功能"""
        print("开始地图数据模块自测...")
        # 使用临时配置
        config = {
            "backend": "memory",  # 使用内存后端，方便测试
            "cache_enabled": False
        }
        mgr = MapDataManager(config=config)
        # 保存地图
        test_map = {"id": "map_001", "name": "测试地图", "type": "world", "data": {"size": [100, 100]}}
        assert mgr.save_map("map_001", test_map)
        # 读取地图
        loaded = mgr.get_map("map_001")
        assert loaded is not None
        assert loaded["name"] == "测试地图"
        # 列表
        maps = mgr.list_maps()
        assert len(maps) == 1
        # 删除
        assert mgr.delete_map("map_001")
        assert mgr.get_map("map_001") is None
        print("自测通过！")


# ==================== 可插拔存储后端基类及实现 ====================
class _MapBackendBase:
    """存储后端抽象基类，定义统一接口"""

    def read(self, map_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def write(self, map_id: str, map_data: Dict[str, Any]) -> bool:
        raise NotImplementedError

    def delete(self, map_id: str) -> bool:
        raise NotImplementedError

    def list_all(self) -> List[Dict[str, Any]]:
        raise NotImplementedError


class _MemoryBackend(_MapBackendBase):
    """内存存储后端，用于测试和轻量使用"""

    def __init__(self):
        self._store = {}

    def read(self, map_id):
        return self._store.get(map_id)

    def write(self, map_id, map_data):
        self._store[map_id] = map_data
        return True

    def delete(self, map_id):
        return self._store.pop(map_id, None) is not None

    def list_all(self):
        return list(self._store.values())


class _JsonFileBackend(_MapBackendBase):
    """JSON文件存储后端"""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self._data = self._load_file()

    def _load_file(self) -> Dict:
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                logger.error("JSON文件解析失败，将初始化空数据")
                return {}
        else:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            return {}

    def _save_file(self):
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def read(self, map_id):
        return self._data.get(map_id)

    def write(self, map_id, map_data):
        self._data[map_id] = map_data
        self._save_file()
        return True

    def delete(self, map_id):
        if map_id in self._data:
            del self._data[map_id]
            self._save_file()
            return True
        return False

    def list_all(self):
        return list(self._data.values())


class _SqliteBackend(_MapBackendBase):
    """SQLite后端预留实现（骨架）"""

    def __init__(self, db_config: Dict):
        self.conn = None
        logger.info("SqliteBackend 初始化，但未完全实现，仅作示例")

    def read(self, map_id):
        pass

    def write(self, map_id, map_data):
        pass

    def delete(self, map_id):
        pass

    def list_all(self):
        pass


# 注册可用后端
BACKEND_MAP = {
    "json_file": _JsonFileBackend,
    "sqlite": _SqliteBackend,
    "memory": _MemoryBackend
}

# 扩展初始化逻辑：支持通过字符串注册自定义后端
def register_backend(name: str, backend_cls):
    BACKEND_MAP[name] = backend_cls


# 修正 MapDataManager._initialize_backend 使用注册表
def _patched_initialize_backend(self):
    backend_type = self.config.get("backend", "json_file")
    cls = BACKEND_MAP.get(backend_type)
    if cls is None:
        logger.warning("未知后端类型 %s，使用memory后端", backend_type)
        cls = _MemoryBackend
    if backend_type == "json_file":
        return cls(self.config.get("json_file_path", "data/maps.json"))
    elif backend_type == "sqlite":
        return cls(self.config.get("db_config", {}))
    else:
        return cls()


# 替换原方法
MapDataManager._initialize_backend = _patched_initialize_backend


if __name__ == "__main__":
    MapDataManager.self_test()