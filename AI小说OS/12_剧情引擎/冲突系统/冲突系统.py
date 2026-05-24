import logging
import json
import os
from typing import Any, Dict, List, Optional, Tuple

# -------------------------------
# 冲突系统 - 剧情引擎子模块
# 负责管理小说叙事中的各类冲突
# 可插拔、配置化、日志记录
# -------------------------------

# 模块日志
logger = logging.getLogger("NovelOS.PlotEngine.ConflictSystem")

class Conflict:
    """冲突实体"""
    def __init__(self, name: str, conflict_type: str, participants: List[str], intensity: float = 0.5, description: str = ""):
        self.name = name
        self.conflict_type = conflict_type
        self.participants = participants
        self.intensity = intensity  # 0.0 ~ 1.0
        self.description = description
        self.status = "active"  # active, resolved, escalating, deescalating

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "conflict_type": self.conflict_type,
            "participants": self.participants,
            "intensity": self.intensity,
            "description": self.description,
            "status": self.status
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Conflict":
        return cls(
            name=data["name"],
            conflict_type=data["conflict_type"],
            participants=data["participants"],
            intensity=data.get("intensity", 0.5),
            description=data.get("description", ""),
        )

class ConflictSystem:
    """冲突系统骨架 —— 可插拔、配置化、日志记录"""

    CONFIG_PATH = "config/conflict_system.json"  # 默认配置文件路径

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化冲突系统。
        参数 config 若提供则使用，否则尝试从默认路径加载，最后使用硬编码默认配置。
        """
        self.config = self._load_config(config)
        self.conflicts: List[Conflict] = []
        self.resolution_history: List[Dict[str, Any]] = []
        logger.info("冲突系统初始化完成，配置：%s", self.config)

    def _load_config(self, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """加载配置（优先传入，再文件，最后默认）"""
        if config is not None:
            return config
        if os.path.exists(self.CONFIG_PATH):
            try:
                with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                logger.info("从 %s 加载配置", self.CONFIG_PATH)
                return loaded
            except Exception as e:
                logger.warning("加载配置文件失败，使用默认配置。错误：%s", e)
        # 默认配置
        default_config = {
            "auto_resolve": False,
            "max_intensity": 1.0,
            "conflict_types": ["character", "plot", "ideology", "resource", "internal"],
            "log_level": "INFO"
        }
        logger.info("使用默认配置")
        return default_config

    def add_conflict(self, conflict: Conflict) -> None:
        """添加新冲突"""
        self.conflicts.append(conflict)
        logger.info("添加冲突：%s (类型: %s, 强度: %.2f)", conflict.name, conflict.conflict_type, conflict.intensity)

    def remove_conflict(self, conflict_name: str) -> bool:
        """按名称移除冲突"""
        initial_len = len(self.conflicts)
        self.conflicts = [c for c in self.conflicts if c.name != conflict_name]
        removed = len(self.conflicts) < initial_len
        if removed:
            logger.info("已移除冲突：%s", conflict_name)
        else:
            logger.warning("未找到冲突：%s，移除失败", conflict_name)
        return removed

    def get_active_conflicts(self) -> List[Conflict]:
        """获取所有活跃的冲突"""
        active = [c for c in self.conflicts if c.status == "active"]
        logger.debug("当前活跃冲突数量：%d", len(active))
        return active

    def escalate_conflict(self, conflict_name: str, amount: float = 0.1) -> bool:
        """加剧指定冲突的强度"""
        for conflict in self.conflicts:
            if conflict.name == conflict_name:
                conflict.intensity = min(self.config.get("max_intensity", 1.0), conflict.intensity + amount)
                conflict.status = "escalating"
                logger.info("冲突 %s 加剧，当前强度 %.2f，状态变为 escalating", conflict.name, conflict.intensity)
                return True
        logger.warning("未找到冲突：%s，无法加剧", conflict_name)
        return False

    def deescalate_conflict(self, conflict_name: str, amount: float = 0.1) -> bool:
        """缓和指定冲突的强度"""
        for conflict in self.conflicts:
            if conflict.name == conflict_name:
                conflict.intensity = max(0.0, conflict.intensity - amount)
                conflict.status = "deescalating"
                logger.info("冲突 %s 缓和，当前强度 %.2f，状态变为 deescalating", conflict.name, conflict.intensity)
                return True
        logger.warning("未找到冲突：%s，无法缓和", conflict_name)
        return False

    def resolve_conflict(self, conflict_name: str, resolution: str = "") -> bool:
        """解决冲突（标记为已解决）"""
        for conflict in self.conflicts:
            if conflict.name == conflict_name:
                conflict.status = "resolved"
                conflict.description += f" [解决方式: {resolution}]" if resolution else ""
                self.resolution_history.append({
                    "conflict": conflict.to_dict(),
                    "resolution": resolution,
                    "timestamp": None  # 可扩展时间戳
                })
                logger.info("冲突 %s 已解决。", conflict_name)
                # 如果配置自动移除，也可以在此移除
                return True
        logger.warning("未找到冲突：%s，无法解决", conflict_name)
        return False

    def list_conflicts(self) -> List[Dict[str, Any]]:
        """返回所有冲突的摘要信息"""
        summary = []
        for c in self.conflicts:
            summary.append(c.to_dict())
        return summary

    def update_from_plot_state(self, plot_data: Dict[str, Any]) -> None:
        """
        外部剧情状态更新时调用（占位）
        根据最新剧情数据自动检测新冲突、更新现有冲突状态。
        """
        # 未来实现：分析plot_data中的事件、角色关系等，生成或修改冲突
        logger.debug("从剧情状态更新冲突（当前仅为占位）")

    # -------------------------------------------------
    # 可插拔扩展接口 (预留)
    # -------------------------------------------------
    def register_plugin(self, plugin: Any) -> None:
        """注册外部插件以扩展冲突处理能力"""
        logger.info("注册冲突系统插件: %s", type(plugin).__name__)
        # 插件可以挂载到检测、解决钩子等

    def health_check(self) -> Dict[str, Any]:
        """健康检查 / 自检方法"""
        return {
            "module": "ConflictSystem",
            "config_loaded": bool(self.config),
            "active_conflicts": len(self.get_active_conflicts()),
            "total_conflicts": len(self.conflicts)
        }

# -------------------------------
# 自测部分
# -------------------------------
if __name__ == "__main__":
    # 配置日志输出便于观察
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("===== 冲突系统骨架自测 =====")
    cs = ConflictSystem()
    # 添加几个测试冲突
    cs.add_conflict(Conflict("主角内心挣扎", "internal", ["主角"], intensity=0.7, description="主角犹豫是否复仇"))
    cs.add_conflict(Conflict("阵营对立", "ideology", ["阵营A", "阵营B"], intensity=0.9))
    print("当前冲突列表：")
    for c in cs.list_conflicts():
        print(c)
    cs.escalate_conflict("主角内心挣扎", 0.2)
    cs.deescalate_conflict("阵营对立", 0.3)
    cs.resolve_conflict("主角内心挣扎", "主角选择放下")
    print("解决后列表：")
    for c in cs.list_conflicts():
        print(c)
    print("健康检查：", cs.health_check())