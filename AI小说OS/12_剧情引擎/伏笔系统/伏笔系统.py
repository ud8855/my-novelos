# 12_剧情引擎/伏笔系统.py
# 伏笔系统骨架：负责小说中伏笔的植入、追踪、揭示与状态管理

import logging
import json
from typing import Dict, List, Optional, Any, Set
from enum import Enum

# 基础配置 (可通过外部配置覆盖)
DEFAULT_CONFIG = {
    "max_foreshadowing": 100,           # 最大伏笔数
    "auto_reveal_check": True,          # 自动检查揭示条件
    "default_importance": 5,            # 默认重要度 1-10
    "log_level": "INFO",               # 日志级别
}

class ForeshadowStatus(Enum):
    """伏笔状态枚举"""
    DORMANT = "dormant"         # 休眠：已埋设但未出现任何线索
    ACTIVE = "active"           # 活跃：已有相关线索，等待揭示
    REVEALED = "revealed"       # 已揭示
    ABANDONED = "abandoned"     # 已放弃（伏笔作废）
    CONFLICT = "conflict"       # 冲突（与其他伏笔逻辑不一致）

class ForeshadowItem:
    """单个伏笔条目"""
    def __init__(self, name: str, description: str, importance: int = 5):
        self.id = -1  # 由系统分配
        self.name = name
        self.description = description
        self.importance = importance
        self.status = ForeshadowStatus.DORMANT
        self.related_foreshadows: Set[int] = set()   # 关联伏笔ID
        self.plant_chapter: Optional[int] = None     # 埋设章节
        self.reveal_chapter: Optional[int] = None    # 揭示章节
        self.notes: str = ""
        self.extra: Dict[str, Any] = {}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "importance": self.importance,
            "status": self.status.value,
            "related": list(self.related_foreshadows),
            "plant_chapter": self.plant_chapter,
            "reveal_chapter": self.reveal_chapter,
            "notes": self.notes,
            "extra": self.extra
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ForeshadowItem":
        item = cls(data["name"], data["description"], data.get("importance", 5))
        item.id = data["id"]
        item.status = ForeshadowStatus(data["status"])
        item.related_foreshadows = set(data.get("related", []))
        item.plant_chapter = data.get("plant_chapter")
        item.reveal_chapter = data.get("reveal_chapter")
        item.notes = data.get("notes", "")
        item.extra = data.get("extra", {})
        return item


class ForeshadowingSystem:
    """
    伏笔系统
    负责管理所有伏笔的生命周期，支持热插拔、日志、配置化。
    通过统一接口与其他系统（如大纲、场景、角色）交互。
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化伏笔系统
        :param config: 自定义配置字典，会合并到默认配置
        """
        self._config = DEFAULT_CONFIG.copy()
        if config:
            self._config.update(config)

        # 配置日志
        self.logger = logging.getLogger("NovelOS.ForeshadowingSystem")
        self._setup_logging()

        # 伏笔数据存储
        self._foreshadows: Dict[int, ForeshadowItem] = {}
        self._next_id = 1
        self._status_hooks = []  # 状态变化钩子函数列表 (callbacks)

        self.logger.info("伏笔系统初始化完成")

    def _setup_logging(self):
        """配置日志格式与级别"""
        level = getattr(logging, self._config.get("log_level", "INFO").upper(), logging.INFO)
        self.logger.setLevel(level)
        if not self.logger.handlers:
            ch = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)

    # ---------- 配置接口 ----------
    def get_config(self, key: str, default=None):
        return self._config.get(key, default)

    def update_config(self, updates: dict):
        """运行时更新配置（热更新）"""
        self._config.update(updates)
        self._setup_logging()  # 重新应用日志级别
        self.logger.debug(f"配置已更新: {updates}")

    # ---------- 状态变更回调机制 ----------
    def register_status_hook(self, hook: callable):
        """
        注册状态变更钩子，当任何伏笔状态改变时调用
        hook签名: hook(foreshadow_id, old_status, new_status)
        """
        self._status_hooks.append(hook)
        self.logger.debug(f"注册状态钩子: {hook}")

    def remove_status_hook(self, hook: callable):
        if hook in self._status_hooks:
            self._status_hooks.remove(hook)

    # ---------- 核心功能 ----------
    def plant_foreshadow(
        self,
        name: str,
        description: str,
        importance: int = None,
        chapter: int = None,
        notes: str = "",
        extra: dict = None
    ) -> Optional[int]:
        """
        埋设一个新伏笔，返回伏笔ID
        :param name: 伏笔名称
        :param description: 伏笔内容描述
        :param importance: 重要度 1-10，不传使用默认
        :param chapter: 埋设所在章节
        :param notes: 备注
        :param extra: 额外扩展信息
        :return: 新伏笔的ID，失败返回None
        """
        if len(self._foreshadows) >= self._config["max_foreshadowing"]:
            self.logger.error("达到最大伏笔数量限制，无法新增")
            return None

        imp = importance if importance is not None else self._config["default_importance"]
        imp = max(1, min(10, imp))

        item = ForeshadowItem(name, description, imp)
        item.id = self._next_id
        item.plant_chapter = chapter
        item.notes = notes
        if extra:
            item.extra = extra

        self._foreshadows[item.id] = item
        self._next_id += 1
        self.logger.info(f"埋设伏笔 #{item.id}: {name} (重要度:{imp})")
        return item.id

    def reveal_foreshadow(self, foreshadow_id: int, chapter: int = None) -> bool:
        """
        揭示指定的伏笔
        :param foreshadow_id: 伏笔ID
        :param chapter: 揭示所在章节
        :return: 是否成功
        """
        item = self._foreshadows.get(foreshadow_id)
        if not item:
            self.logger.warning(f"未找到伏笔 #{foreshadow_id}")
            return False
        if item.status == ForeshadowStatus.REVEALED:
            self.logger.warning(f"伏笔 #{foreshadow_id} 已经是揭示状态")
            return False

        old_status = item.status
        item.status = ForeshadowStatus.REVEALED
        item.reveal_chapter = chapter
        self.logger.info(f"伏笔 #{foreshadow_id} 状态变更: {old_status.value} -> revealed")
        self._trigger_status_hooks(foreshadow_id, old_status, ForeshadowStatus.REVEALED)
        return True

    def abandon_foreshadow(self, foreshadow_id: int, reason: str = "") -> bool:
        """
        放弃（废弃）某个伏笔
        :param foreshadow_id: 伏笔ID
        :param reason: 放弃原因
        :return: 是否成功
        """
        item = self._foreshadows.get(foreshadow_id)
        if not item:
            self.logger.warning(f"未找到伏笔 #{foreshadow_id}")
            return False
        if item.status == ForeshadowStatus.ABANDONED:
            return True

        old_status = item.status
        item.status = ForeshadowStatus.ABANDONED
        item.notes += f"\n[放弃原因] {reason}" if reason else ""
        self.logger.info(f"伏笔 #{foreshadow_id} 状态变更: {old_status.value} -> abandoned")
        self._trigger_status_hooks(foreshadow_id, old_status, ForeshadowStatus.ABANDONED)
        return True

    def update_foreshadow_status(self, foreshadow_id: int, new_status: ForeshadowStatus) -> bool:
        """通用状态更新"""
        item = self._foreshadows.get(foreshadow_id)
        if not item:
            return False
        if item.status == new_status:
            return True
        old = item.status
        item.status = new_status
        self.logger.info(f"伏笔 #{foreshadow_id} 状态变更: {old.value} -> {new_status.value}")
        self._trigger_status_hooks(foreshadow_id, old, new_status)
        return True

    def add_relation(self, foreshadow_id1: int, foreshadow_id2: int, bidirectional: bool = True):
        """添加两个伏笔之间的关联"""
        item1 = self._foreshadows.get(foreshadow_id1)
        item2 = self._foreshadows.get(foreshadow_id2)
        if not item1 or not item2:
            self.logger.warning("关联伏笔时未找到指定的伏笔")
            return
        item1.related_foreshadows.add(foreshadow_id2)
        if bidirectional:
            item2.related_foreshadows.add(foreshadow_id1)
        self.logger.debug(f"伏笔 #{foreshadow_id1} 与 #{foreshadow_id2} 建立关联")

    def remove_relation(self, foreshadow_id1: int, foreshadow_id2: int, bidirectional: bool = True):
        item1 = self._foreshadows.get(foreshadow_id1)
        item2 = self._foreshadows.get(foreshadow_id2)
        if item1:
            item1.related_foreshadows.discard(foreshadow_id2)
        if bidirectional and item2:
            item2.related_foreshadows.discard(foreshadow_id1)

    def get_foreshadow(self, foreshadow_id: int) -> Optional[ForeshadowItem]:
        return self._foreshadows.get(foreshadow_id)

    def list_foreshadows(self, status: ForeshadowStatus = None) -> List[ForeshadowItem]:
        """列出伏笔，可按状态筛选"""
        if status is None:
            return list(self._foreshadows.values())
        return [item for item in self._foreshadows.values() if item.status == status]

    def get_active_foreshadows(self) -> List[ForeshadowItem]:
        """获取所有尚未揭示且未放弃的伏笔"""
        return [item for item in self._foreshadows.values() if item.status in (ForeshadowStatus.DORMANT, ForeshadowStatus.ACTIVE)]

    def get_unrevealed_count(self) -> int:
        return len(self.get_active_foreshadows())

    def check_auto_reveal(self, current_chapter: int = None):
        """
        自动检查可揭示的伏笔（占位方法）
        高级实现可基于条件规则，目前仅记录调用
        """
        if not self._config.get("auto_reveal_check"):
            return
        self.logger.debug("执行自动揭示检查...")
        # TODO: 实现基于条件的自动揭示逻辑
        pass

    # ---------