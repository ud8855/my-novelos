# 角色数据.py - 角色数据层接口与基础实现
# 所属层：06_数据层/角色数据
# 依赖：标准库 (abc, logging, typing)
# 被调用：业务层、Agent层或其他数据访问组件
# 功能：为角色数据提供统一的存取接口，支持可插拔存储后端，配置化，带日志

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import configparser  # 用于读取简单配置文件，实际项目可替换为 yaml/json

# --------------------------- 日志配置（可插拔）---------------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    # 默认输出到控制台，实际环境可配置为文件或远程
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    logger.setLevel(logging.DEBUG)

# --------------------------- 配置管理（极简可扩展）-----------------------
class RoleDataConfig:
    """角色数据模块配置容器。实际使用时可通过配置文件或环境变量加载。"""
    def __init__(self):
        # 默认存储后端：memory
        self.backend = "memory"
        # 内存存储时的初始数据文件路径（可选）
        self.memory_init_file = None
        # 可扩展其他后端参数，如数据库连接等
        self.db_connection_string = None

    @classmethod
    def from_file(cls, filepath: str) -> "RoleDataConfig":
        """从配置文件加载（示例使用 configparser）"""
        config = cls()
        parser = configparser.ConfigParser()
        parser.read(filepath)
        if "role_data" in parser:
            section = parser["role_data"]
            config.backend = section.get("backend", "memory")
            config.memory_init_file = section.get("memory_init_file")
            config.db_connection_string = section.get("db_connection_string")
        return config

# --------------------------- 抽象接口 ---------------------------
class CharacterDataInterface(ABC):
    """角色数据操作的统一接口，所有存储后端必须实现此接口。"""

    @abstractmethod
    def get_character(self, character_id: str) -> Optional[Dict[str, Any]]:
        """根据角色ID获取角色完整信息。"""
        pass

    @abstractmethod
    def save_character(self, character: Dict[str, Any]) -> bool:
        """保存或更新一个角色信息，角色字典必须包含 'id' 字段。"""
        pass

    @abstractmethod
    def delete_character(self, character_id: str) -> bool:
        """删除指定角色。"""
        pass

    @abstractmethod
    def list_characters(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """列出所有角色，支持简单过滤条件。"""
        pass

    @abstractmethod
    def exists(self, character_id: str) -> bool:
        """检查角色是否存在。"""
        pass

# --------------------------- 内存实现（用于测试和快速原型）--------------
class CharacterDataMemory(CharacterDataInterface):
    """基于内存字典的角色数据存储，支持可选从文件加载初始数据。"""

    def __init__(self, config: Optional[RoleDataConfig] = None):
        self._storage: Dict[str, Dict[str, Any]] = {}
        if config and config.memory_init_file:
            self._load_from_file(config.memory_init_file)
        logger.info("CharacterDataMemory 初始化完成，当前角色数量: %d", len(self._storage))

    def _load_from_file(self, filepath: str):
        """从JSON文件加载初始角色数据。"""
        import json
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    for char in data:
                        if 'id' in char:
                            self._storage[char['id']] = char
                elif isinstance(data, dict):
                    for cid, char in data.items():
                        if 'id' not in char:
                            char['id'] = cid
                        self._storage[char['id']] = char
            logger.info("从文件 %s 加载了 %d 个角色", filepath, len(self._storage))
        except Exception as e:
            logger.error("加载角色文件失败: %s", e, exc_info=True)

    def get_character(self, character_id: str) -> Optional[Dict[str, Any]]:
        logger.debug("获取角色: %s", character_id)
        return self._storage.get(character_id)

    def save_character(self, character: Dict[str, Any]) -> bool:
        if 'id' not in character:
            logger.error("保存角色失败，缺少 'id' 字段")
            return False
        cid = character['id']
        self._storage[cid] = character
        logger.info("角色 %s 已保存", cid)
        return True

    def delete_character(self, character_id: str) -> bool:
        if character_id in self._storage:
            del self._storage[character_id]
            logger.info("角色 %s 已删除", character_id)
            return True
        logger.warning("尝试删除不存在的角色: %s", character_id)
        return False

    def list_characters(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        all_chars = list(self._storage.values())
        if not filters:
            return all_chars
        # 简单的字段等值过滤
        result = []
        for char in all_chars:
            match = True
            for key, value in filters.items():
                if char.get(key) != value:
                    match = False
                    break
            if match:
                result.append(char)
        logger.debug("列出角色，总数 %d，过滤后 %d", len(all_chars), len(result))
        return result

    def exists(self, character_id: str) -> bool:
        return character_id in self._storage

# --------------------------- 工厂函数（插拔式入口）----------------------
def create_character_data_backend(config: Optional[RoleDataConfig] = None) -> CharacterDataInterface:
    """根据配置创建角色数据存储实例。"""
    if config is None:
        config = RoleDataConfig()  # 使用默认配置

    backend = config.backend.lower()
    logger.info("创建角色数据后端: %s", backend)

    if backend == "memory":
        return CharacterDataMemory(config)
    # 可扩展其他后端，如 "sqlite", "postgres" 等
    # elif backend == "sqlite":
    #     return CharacterDataSQLite(config)
    else:
        logger.warning("不支持的存储后端 %s，回退到内存实现", backend)
        return CharacterDataMemory(config)

# --------------------------- 自测部分 ------------------------------
if __name__ == "__main__":
    print("开始角色数据模块自测...")
    # 1. 使用默认内存后端
    data_store = create_character_data_backend()
    assert data_store is not None

    # 2. 保存角色
    char1 = {"id": "ch001", "name": "主角", "description": "一个勇敢的冒险者", "attributes": {"hp": 100, "mp": 50}}
    assert data_store.save_character(char1) == True

    char2 = {"id": "ch002", "name": "助手", "description": "聪明的魔法师", "attributes": {"hp": 80, "mp": 120}}
    data_store.save_character(char2)

    # 3. 获取角色
    loaded = data_store.get_character("ch001")
    assert loaded is not None
    assert loaded["name"] == "主角"
    logger.info("获取角色测试通过: %s", loaded["name"])

    # 4. 检查存在
    assert data_store.exists("ch001") == True
    assert data_store.exists("ch999") == False

    # 5. 列出所有角色
    all_chars = data_store.list_characters()
    assert len(all_chars) == 2
    logger.info("列出角色数量: %d", len(all_chars))

    # 6. 过滤
    filtered = data_store.list_characters({"name": "助手"})
    assert len(filtered) == 1 and filtered[0]["id"] == "ch002"
    logger.info("过滤测试通过")

    # 7. 删除角色
    assert data_store.delete_character("ch001") == True
    assert data_store.get_character("ch001") is None
    logger.info("删除测试通过")

    # 8. 尝试删除不存在的角色
    assert data_store.delete_character("ch001") == False
    logger.info("删除不存在角色测试通过")

    # 9. 再次保存（更新）
    char1_updated = {"id": "ch001", "name": "进化主角", "description": "更强大", "attributes": {"hp": 200}}
    data_store.save_character(char1_updated)
    updated = data_store.get_character("ch001")
    assert updated["attributes"]["hp"] == 200
    logger.info("更新角色测试通过")

    print("自测全部通过！")