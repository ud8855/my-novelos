"""元数据.py - 元数据管理核心模块

所属层级：06_数据层/元数据
依赖模块：基础存储驱动（文件系统/数据库，通过配置获取）
被调用方：上层管理器、运行时模块、版本控制
功能职责：
    1. 加载/保存小说元数据（标题、作者、简介等）
    2. 记录版本历史与修改时间线
    3. 支持可插拔存储后端（通过配置文件切换）
    4. 配置化日志输出，异常恢复提示
    5. 提供自测桩程序
设计原则：单一职责、可插拔、配置驱动、异常安全
"""

import logging
import json
import os
import datetime
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

# 配置管理（最小化，后续可替换为统一配置中心）
CONFIG = {
    "storage_backend": "json_file",  # 支持 json_file, sqlite, redis 等
    "metadata_dir": "./data/metadata",
    "log_level": "INFO",
    "auto_backup": True,
    "backup_count": 5,
}

# 日志配置
logging.basicConfig(level=CONFIG["log_level"],
                    format='[%(asctime)s][%(levelname)s][%(name)s] %(message)s')
logger = logging.getLogger("MetadataManager")


class StorageBackend(ABC):
    """存储后端抽象基类，所有具体存储必须实现"""
    @abstractmethod
    def load(self, path: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def save(self, path: str, data: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        pass


class JsonFileBackend(StorageBackend):
    """JSON 文件存储后端"""
    def load(self, path: str) -> Dict[str, Any]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"元数据文件不存在: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save(self, path: str, data: Dict[str, Any]) -> bool:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # 简单备份策略
        if CONFIG.get("auto_backup") and os.path.exists(path):
            backup_dir = os.path.join(os.path.dirname(path), "backup")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
            backup_path = os.path.join(backup_dir, f"{os.path.basename(path)}.{timestamp}.bak")
            os.replace(path, backup_path)
            # 清理旧备份（保留最近 N 个）
            backups = sorted(
                [f for f in os.listdir(backup_dir) if f.startswith(os.path.basename(path))],
                reverse=True
            )
            for old in backups[CONFIG.get("backup_count", 5):]:
                os.remove(os.path.join(backup_dir, old))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True

    def exists(self, path: str) -> bool:
        return os.path.exists(path)


# 存储后端注册表
BACKENDS = {
    "json_file": JsonFileBackend,
    # 后续可扩展 "sqlite": SqliteBackend, "redis": RedisBackend
}


class MetadataManager:
    """元数据管理器

    负责小说基本元数据的存取与版本记录。
    通过配置切换存储后端，支持异常恢复。
    """
    def __init__(self, novel_id: str, backend: str = None, metadata_dir: str = None):
        self.novel_id = novel_id
        self.backend_name = backend or CONFIG["storage_backend"]
        self.metadata_dir = metadata_dir or CONFIG["metadata_dir"]
        self.metadata_file = os.path.join(self.metadata_dir, f"{novel_id}_meta.json")

        backend_cls = BACKENDS.get(self.backend_name)
        if backend_cls is None:
            logger.error(f"不支持的存储后端: {self.backend_name}, 回退到 json_file")
            backend_cls = JsonFileBackend
        self.storage: StorageBackend = backend_cls()
        logger.debug(f"元数据管理器初始化完成，小说ID={novel_id}, 后端={self.backend_name}")

        self._metadata_cache: Optional[Dict[str, Any]] = None

    def load_metadata(self) -> Dict[str, Any]:
        """加载小说元数据字典"""
        try:
            raw = self.storage.load(self.metadata_file)
            # 校验基本结构（后续可严格 schema 验证）
            if "novel_id" not in raw or "title" not in raw:
                raise ValueError("元数据结构不完整，缺少必要字段")
            self._metadata_cache = raw
            logger.info(f"成功加载小说 {self.novel_id} 的元数据")
            return raw
        except FileNotFoundError:
            logger.warning(f"元数据文件不存在，将创建默认元数据")
            return self._create_default_metadata()
        except Exception as e:
            logger.error(f"加载元数据时出错: {e}")
            # 尝试加载最近备份或返回默认值
            try:
                backup_data = self._load_latest_backup()
                logger.info("成功从备份恢复元数据")
                return backup_data
            except Exception as be:
                logger.error(f"备份恢复失败: {be}，返回默认元数据")
                return self._create_default_metadata()

    def save_metadata(self, data: Dict[str, Any]) -> bool:
        """保存元数据到存储"""
        # 更新修改时间
        data["last_modified"] = datetime.datetime.now().isoformat()
        # 版本记录
        if "version_history" not in data:
            data["version_history"] = []
        version_entry = {
            "timestamp": data["last_modified"],
            "version": data.get("version", "1.0"),
            "description": "元数据更新"
        }
        data["version_history"].append(version_entry)
        # 保持版本历史大小（可选，防止无限增长）
        if len(data["version_history"]) > 100:
            data["version_history"] = data["version_history"][-50:]

        try:
            success = self.storage.save(self.metadata_file, data)
            if success:
                self._metadata_cache = data
                logger.debug(f"元数据保存成功")
            return success
        except Exception as e:
            logger.error(f"保存元数据失败: {e}")
            return False

    def update_metadata(self, updates: Dict[str, Any]) -> bool:
        """部分更新元数据字段"""
        current = self.load_metadata()
        current.update(updates)
        return self.save_metadata(current)

    def get_chapter_list(self) -> List[str]:
        """获取章节ID列表（从元数据中）"""
        meta = self.load_metadata()
        return meta.get("chapter_ids", [])

    def set_chapter_list(self, chapter_ids: List[str]) -> bool:
        """设置章节ID列表"""
        return self.update_metadata({"chapter_ids": chapter_ids})

    def _create_default_metadata(self) -> Dict[str, Any]:
        """创建默认元数据模板"""
        default = {
            "novel_id": self.novel_id,
            "title": "未命名小说",
            "author": "未知",
            "description": "",
            "created_time": datetime.datetime.now().isoformat(),
            "last_modified": datetime.datetime.now().isoformat(),
            "version": "0.1",
            "chapter_ids": [],
            "version_history": [],
            "tags": [],
            "custom_meta": {}
        }
        self.storage.save(self.metadata_file, default)
        self._metadata_cache = default
        logger.info(f"已创建默认元数据并保存")
        return default

    def _load_latest_backup(self) -> Dict[str, Any]:
        """从备份目录加载最近一次备份"""
        backup_dir = os.path.join(self.metadata_dir, "backup")
        if not os.path.exists(backup_dir):
            raise FileNotFoundError("备份目录不存在")
        candidates = sorted(
            [f for f in os.listdir(backup_dir) if f.startswith(f"{self.novel_id}_meta.json")],
            reverse=True
        )
        if not candidates:
            raise FileNotFoundError("没有可用的备份")
        latest = candidates[0]
        backup_path = os.path.join(backup_dir, latest)
        # 使用 json 直接加载（因为 backend 可能不同，这里简单处理）
        with open(backup_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"从备份恢复: {backup_path}")
        return data

    def validate_metadata(self) -> bool:
        """简单校验元数据完整性"""
        required_fields = ["novel_id", "title", "version"]
        meta = self.load_metadata()
        for field in required_fields:
            if field not in meta:
                logger.error(f"缺少必要字段: {field}")
                return False
        return True


# 自测桩
if __name__ == "__main__":
    print("=== 元数据模块自测 ===")
    # 使用临时目录测试
    test_novel_id = "test_novel_001"
    CONFIG["metadata_dir"] = "./test_metadata"
    mgr = MetadataManager(novel_id=test_novel_id, backend="json_file")

    # 测试创建默认元数据
    meta = mgr.load_metadata()
    print(f"默认元数据: {json.dumps(meta, ensure_ascii=False, indent=2)}")

    # 测试更新
    mgr.update_metadata({"title": "测试小说", "author": "测试作者"})
    print("更新后元数据:", mgr.load_metadata()["title"])

    # 测试章节列表
    mgr.set_chapter_list(["ch1", "ch2", "ch3"])
    print("章节列表:", mgr.get_chapter_list())

    # 测试版本历史
    print("版本历史条目数:", len(mgr.load_metadata()["version_history"]))

    # 测试验证
    print("元数据有效性:", mgr.validate_metadata())

    # 清理测试文件
    import shutil
    shutil.rmtree("./test_metadata", ignore_errors=True)
    print("=== 自测完成 ===")