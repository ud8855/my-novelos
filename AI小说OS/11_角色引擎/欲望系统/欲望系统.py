"""欲望系统骨架

属于层级：11_角色引擎
依赖：无外部依赖，使用内置logging和配置字典
被调用者：角色引擎中的其他模块（如行为选择、对话生成），通过接口调用
解决问题：管理角色的欲望数据，支持增删改查和动态更新，为后续欲望推理提供基础数据。
"""

import logging
import json
from typing import Dict, List, Optional, Any


class DesireSystem:
    """角色欲望管理系统（骨架）

    设计原则：
    - 可插拔：通过统一接口访问，其他模块依赖抽象，不依赖具体实现
    - 配置化：构造函数接收配置字典，支持运行时重载
    - 日志记录：关键操作均记录日志，便于追踪和调试
    - 唯一职责：只管理欲望数据，不涉及欲望如何影响行为（由其他模块处理）
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化欲望系统

        Args:
            config: 配置字典，可包含：
                - log_level: 日志级别，默认INFO
                - default_desires: 初始欲望列表
                - decay_rate: 欲望衰减率
                - max_desires: 最大欲望数量
        """
        self.config = config if config else {}
        self._desires: Dict[str, Dict] = {}  # 欲望存储：key为欲望名称，value为属性字典
        self._setup_logging()
        self._load_config()

    def _setup_logging(self):
        """配置日志记录器"""
        self.logger = logging.getLogger("DesireSystem")
        self.logger.setLevel(self.config.get("log_level", logging.INFO))
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def _load_config(self):
        """从配置中加载初始欲望和参数"""
        self.logger.info("加载欲望系统配置...")
        self.decay_rate = self.config.get("decay_rate", 0.1)
        self.max_desires = self.config.get("max_desires", 10)

        # 加载默认欲望列表
        default_desires = self.config.get("default_desires", [])
        for desire in default_desires:
            self.add_desire(
                name=desire.get("name", "unknown"),
                intensity=desire.get("intensity", 0.5),
                priority=desire.get("priority", 1),
                meta=desire.get("meta", {})
            )
        self.logger.info(f"欲望系统初始化完成，当前欲望数量: {len(self._desires)}")

    def add_desire(self, name: str, intensity: float = 0.5, priority: int = 1, meta: Optional[Dict] = None) -> bool:
        """
        添加一个新欲望

        Args:
            name: 欲望名称（英文标识符，如 "hunger", "thirst"）
            intensity: 欲望强度 [0,1]
            priority: 优先级（整数，越大越优先）
            meta: 附加元数据

        Returns:
            是否添加成功
        """
        if name in self._desires:
            self.logger.warning(f"欲望 '{name}' 已存在，添加失败")
            return False

        if len(self._desires) >= self.max_desires:
            self.logger.warning(f"欲望数量已达上限 {self.max_desires}，无法添加 '{name}'")
            return False

        self._desires[name] = {
            "name": name,
            "intensity": min(1.0, max(0.0, intensity)),
            "priority": priority,
            "meta": meta if meta else {}
        }
        self.logger.info(f"添加欲望 '{name}'，强度 {intensity}，优先级 {priority}")
        return True

    def remove_desire(self, name: str) -> bool:
        """
        移除指定欲望

        Args:
            name: 欲望名称

        Returns:
            是否成功移除
        """
        if name in self._desires:
            del self._desires[name]
            self.logger.info(f"移除欲望 '{name}'")
            return True
        else:
            self.logger.warning(f"尝试移除不存在的欲望 '{name}'")
            return False

    def update_desire(self, name: str, intensity: Optional[float] = None, priority: Optional[int] = None, meta: Optional[Dict] = None) -> bool:
        """
        更新欲望属性

        Args:
            name: 欲望名称
            intensity: 新强度（None表示不变）
            priority: 新优先级（None表示不变）
            meta: 新元数据（None表示不变）

        Returns:
            是否成功更新
        """
        if name not in self._desires:
            self.logger.warning(f"无法更新不存在的欲望 '{name}'")
            return False

        desire = self._desires[name]
        if intensity is not None:
            desire["intensity"] = min(1.0, max(0.0, intensity))
        if priority is not None:
            desire["priority"] = priority
        if meta is not None:
            desire["meta"].update(meta)

        self.logger.debug(f"更新欲望 '{name}' -> 强度 {desire['intensity']}, 优先级 {desire['priority']}")
        return True

    def decay_all(self):
        """对所有欲望进行强度衰减（按衰减率）"""
        self.logger.debug("开始全局欲望衰减")
        for name in list(self._desires.keys()):
            old_intensity = self._desires[name]["intensity"]
            new_intensity = max(0.0, old_intensity - self.decay_rate)
            self._desires[name]["intensity"] = new_intensity
            if new_intensity <= 0.0:
                self.remove_desire(name)
                self.logger.debug(f"欲望 '{name}' 衰减至零，自动移除")
            else:
                self.logger.debug(f"欲望 '{name}' 衰减: {old_intensity:.2f} -> {new_intensity:.2f}")

    def get_active_desires(self, min_intensity: float = 0.1, min_priority: int = 0) -> List[Dict]:
        """
        获取当前激活的欲望（强度高于阈值）

        Args:
            min_intensity: 最低强度阈值
            min_priority: 最低优先级阈值

        Returns:
            满足条件的欲望列表，按优先级降序、强度降序排列
        """
        active = [
            desire for desire in self._desires.values()
            if desire["intensity"] >= min_intensity and desire["priority"] >= min_priority
        ]
        active.sort(key=lambda x: (x["priority"], x["intensity"]), reverse=True)
        self.logger.debug(f"获取激活欲望，共 {len(active)} 个（阈值: I>{min_intensity}, P>{min_priority}）")
        return active

    def get_desire(self, name: str) -> Optional[Dict]:
        """获取单个欲望的详细信息"""
        return self._desires.get(name)

    def to_dict(self) -> Dict:
        """导出当前欲望状态为字典，用于序列化/配置保存"""
        return {
            "config": self.config,
            "desires": list(self._desires.values()),
            "decay_rate": self.decay_rate,
            "max_desires": self.max_desires
        }

    def from_dict(self, state: Dict):
        """从字典状态恢复系统（用于热更新/读档）"""
        self.config = state.get("config", {})
        self.decay_rate = state.get("decay_rate", 0.1)
        self.max_desires = state.get("max_desires", 10)
        self._desires = {}
        for desire in state.get("desires", []):
            self._desires[desire["name"]] = desire
        self.logger.info(f"从状态恢复欲望系统，当前欲望: {list(self._desires.keys())}")


# ==================== 自测与示例 ====================
if __name__ == "__main__":
    # 简单测试
    print("=== 欲望系统骨架自测 ===")
    config = {
        "log_level": logging.DEBUG,
        "default_desires": [
            {"name": "hunger", "intensity": 0.8, "priority": 2},
            {"name": "thirst", "intensity": 0.6, "priority": 1}
        ],
        "decay_rate": 0.2,
        "max_desires": 5
    }
    ds = DesireSystem(config)
    print("初始欲望:", ds.get_active_desires(min_intensity=0.05))

    # 添加新欲望
    ds.add_desire("curiosity", intensity=0.9, priority=3, meta={"object": "strange noise"})
    print("添加curiosity后:", [d["name"] for d in ds.get_active_desires()])

    # 更新欲望
    ds.update_desire("hunger", intensity=0.3)
    print("降低饥饿后:", ds.get_desire("hunger"))

    # 衰减
    ds.decay_all()
    print("衰减后所有欲望:", ds.get_active_desires(min_intensity=0.05))

    # 序列化
    state = ds.to_dict()
    print("序列化状态:", json.dumps(state, indent=2, ensure_ascii=False))

    # 恢复
    ds2 = DesireSystem()
    ds2.from_dict(state)
    print("从状态恢复后:", ds2.get_active_desires())
    print("=== 自测完成 ===")