"""
技能数据模块 - 数据层
功能：管理小说创作中的技能数据（如角色技能、世界技能等），提供数据的存储、查询、更新和删除接口。
所属层级：06_数据层
依赖：基础数据接口（如 数据层/基础数据接口.py 定义的数据存储协议）
被调用：技能相关功能模块（如 05_运行时/技能系统.py、06_数据层/世界数据.py 等）
解决：技能数据的持久化、一致性访问和扩展支持。
"""
import logging
import os
from typing import Dict, Any, List, Optional, Type, TypeVar

# 配置化：使用环境变量或配置文件，这里给出默认值
SKILL_DATA_CONFIG = {
    "storage_backend": os.environ.get("SKILL_STORAGE_BACKEND", "json"),  # 支持json, sqlite等
    "data_dir": os.environ.get("SKILL_DATA_DIR", "data/skills"),
    "auto_index": os.environ.get("SKILL_AUTO_INDEX", "true").lower() == "true",
    "cache_size": int(os.environ.get("SKILL_CACHE_SIZE", 100)),
}

# 日志
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# 定义技能数据的类型泛型
T = TypeVar('T', bound='SkillRecord')

class SkillRecord:
    """技能记录基类，所有技能实体都应继承此类"""
    def __init__(self,
                 skill_id: str,
                 name: str,
                 description: str = "",
                 level: int = 1,
                 effects: Optional[Dict[str, Any]] = None,
                 metadata: Optional[Dict[str, Any]] = None):
        self.skill_id = skill_id
        self.name = name
        self.description = description
        self.level = level
        self.effects = effects or {}
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "level": self.level,
            "effects": self.effects,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        return cls(**data)

class SkillDataInterface:
    """技能数据接口定义，所有具体实现需遵循此协议（可插拔）"""
    def connect(self) -> bool:
        """建立与存储后端的连接，返回是否成功"""
        raise NotImplementedError

    def disconnect(self) -> bool:
        """断开连接并清理资源"""
        raise NotImplementedError

    def add_skill(self, skill: SkillRecord) -> bool:
        """添加新技能，返回是否成功"""
        raise NotImplementedError

    def update_skill(self, skill_id: str, updates: Dict[str, Any]) -> bool:
        """更新技能属性，返回是否成功"""
        raise NotImplementedError

    def remove_skill(self, skill_id: str) -> bool:
        """删除技能，返回是否成功"""
        raise NotImplementedError

    def get_skill(self, skill_id: str) -> Optional[SkillRecord]:
        """根据ID获取技能记录，不存在返回None"""
        raise NotImplementedError

    def list_skills(self, filters: Optional[Dict[str, Any]] = None, limit: int = 100) -> List[SkillRecord]:
        """列出满足条件的技能列表，支持分页和过滤"""
        raise NotImplementedError

    def exists(self, skill_id: str) -> bool:
        """检查技能是否存在"""
        raise NotImplementedError

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """返回符合条件的技能数量"""
        raise NotImplementedError

    def backup(self, path: Optional[str] = None) -> str:
        """备份当前技能数据，返回备份文件路径"""
        raise NotImplementedError

    def restore(self, path: str) -> bool:
        """从备份文件恢复技能数据"""
        raise NotImplementedError

    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        raise NotImplementedError

class JSONSkillData(SkillDataInterface):
    """基于JSON文件的技能数据存储实现（默认后端）"""
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or SKILL_DATA_CONFIG
        self._data: Dict[str, SkillRecord] = {}
        self._file_path = os.path.join(self.config["data_dir"], "skills.json")
        self._connected = False
        logger.info("JSONSkillData initialized with config: %s", self.config)

    def connect(self) -> bool:
        """从JSON文件加载数据到内存"""
        try:
            os.makedirs(self.config["data_dir"], exist_ok=True)
            if os.path.exists(self._file_path):
                import json
                with open(self._file_path, 'r', encoding='utf-8') as f:
                    raw_data = json.load(f)
                    for item in raw_data:
                        record = SkillRecord.from_dict(item)
                        self._data[record.skill_id] = record
                logger.info("Loaded %d skills from %s", len(self._data), self._file_path)
            else:
                self._save()  # 创建空文件
                logger.info("Created new skills.json at %s", self._file_path)
            self._connected = True
            return True
        except Exception as e:
            logger.error("Failed to connect to JSON skill storage: %s", e)
            self._connected = False
            return False

    def disconnect(self) -> bool:
        """保存数据并清空内存"""
        if self._connected:
            try:
                self._save()
                self._data.clear()
                self._connected = False
                logger.info("Disconnected from JSON skill storage")
                return True
            except Exception as e:
                logger.error("Error disconnecting: %s", e)
                return False
        return True

    def _save(self):
        """内部方法：将内存数据保存到JSON文件"""
        import json
        os.makedirs(os.path.dirname(self._file_path), exist_ok=True)
        data_to_save = [record.to_dict() for record in self._data.values()]
        with open(self._file_path, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        logger.debug("Saved %d skills to %s", len(self._data), self._file_path)

    def add_skill(self, skill: SkillRecord) -> bool:
        if not self._connected:
            logger.error("Storage not connected")
            return False
        if skill.skill_id in self._data:
            logger.warning("Skill %s already exists", skill.skill_id)
            return False
        self._data[skill.skill_id] = skill
        self._save()
        logger.info("Added skill: %s", skill.skill_id)
        return True

    def update_skill(self, skill_id: str, updates: Dict[str, Any]) -> bool:
        if not self._connected:
            logger.error("Storage not connected")
            return False
        if skill_id not in self._data:
            logger.warning("Skill %s not found for update", skill_id)
            return False
        record = self._data[skill_id]
        for key, value in updates.items():
            if hasattr(record, key):
                setattr(record, key, value)
        self._save()
        logger.info("Updated skill: %s", skill_id)
        return True

    def remove_skill(self, skill_id: str) -> bool:
        if not self._connected:
            logger.error("Storage not connected")
            return False
        if skill_id not in self._data:
            logger.warning("Skill %s not found for removal", skill_id)
            return False
        del self._data[skill_id]
        self._save()
        logger.info("Removed skill: %s", skill_id)
        return True

    def get_skill(self, skill_id: str) -> Optional[SkillRecord]:
        if not self._connected:
            logger.error("Storage not connected")
            return None
        return self._data.get(skill_id)

    def list_skills(self, filters: Optional[Dict[str, Any]] = None, limit: int = 100) -> List[SkillRecord]:
        if not self._connected:
            logger.error("Storage not connected")
            return []
        result = list(self._data.values())[:limit]
        if filters:
            # 简单的过滤示例：可扩展为高级查询
            filtered = []
            for record in result:
                match = True
                for k, v in filters.items():
                    attr_val = getattr(record, k, None)
                    if attr_val != v:
                        match = False
                        break
                if match:
                    filtered.append(record)
            result = filtered
        return result

    def exists(self, skill_id: str) -> bool:
        if not self._connected:
            logger.error("Storage not connected")
            return False
        return skill_id in self._data

    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        return len(self.list_skills(filters, limit=999999))

    def backup(self, path: Optional[str] = None) -> str:
        if not self._connected:
            logger.error("Storage not connected")
            return ""
        import shutil
        from datetime import datetime
        if not path:
            path = os.path.join(self.config["data_dir"], f"skills_backup_{datetime.now().strftime('%Y%m%d%H%M%S')}.json")
        try:
            shutil.copy2(self._file_path, path)
            logger.info("Backup created at %s", path)
            return path
        except Exception as e:
            logger.error("Backup failed: %s", e)
            return ""

    def restore(self, path: str) -> bool:
        if not self._connected:
            logger.error("Storage not connected")
            return False
        try:
            import shutil
            shutil.copy2(path, self._file_path)
            self.disconnect()
            self._data.clear()
            self.connect()
            logger.info("Restored from %s", path)
            return True
        except Exception as e:
            logger.error("Restore failed: %s", e)
            return False

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_skills": len(self._data),
            "storage_backend": "json",
            "file_path": self._file_path,
            "connected": self._connected,
        }

# 工厂函数：根据配置动态选择存储后端（可插拔）
def get_skill_data_interface(config: Optional[Dict[str, Any]] = None) -> SkillDataInterface:
    """
    获取技能数据接口实例，支持通过配置切换后端。
    """
    config = config or SKILL_DATA_CONFIG
    backend = config.get("storage_backend", "json")
    if backend == "json":
        return JSONSkillData(config)
    else:
        raise ValueError(f"Unsupported storage backend: {backend}")

# 自测代码块（仅在直接运行此模块时执行）
if __name__ == "__main__":
    print("=== 开始技能数据模块自测 ===")
    # 使用默认配置初始化接口
    skill_data = get_skill_data_interface()

    # 连接存储
    assert skill_data.connect(), "连接失败"
    print("✓ 连接存储成功")

    # 添加技能
    skill1 = SkillRecord(skill_id="fireball", name="火球术", description="发射一团火球", level=1)
    assert skill_data.add_skill(skill1), "添加技能失败"
    print("✓ 添加技能成功")

    # 检查存在
    assert skill_data.exists("fireball"), "技能应该存在"
    print("✓ 存在性检查通过")

    # 获取技能
    fetched = skill_data.get_skill("fireball")
    assert fetched is not None and fetched.name == "火球术", "获取技能失败"
    print("✓ 获取技能成功")

    # 更新技能
    assert skill_data.update_skill("fireball", {"level": 2, "description": "强力火球"}), "更新技能失败"
    updated = skill_data.get_skill("fireball")
    assert updated.level == 2 and updated.description == "强力火球", "更新未生效"
    print("✓ 更新技能成功")

    # 列出所有技能
    skills = skill_data.list_skills()
    assert len(skills) == 1, "列表技能数量错误"
    print("✓ 技能列表正确")

    # 备份
    backup_path = skill_data.backup()
    assert backup_path, "备份失败"
    print(f"✓ 备份成功，路径: {backup_path}")

    # 统计信息
    stats = skill_data.get_stats()
    assert stats['total_skills'] == 1, "统计信息错误"
    print(f"✓ 统计信息: {stats}")

    # 删除技能
    assert skill_data.remove_skill("fireball"),