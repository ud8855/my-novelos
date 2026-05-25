# 文件：10_世界引擎/朝堂系统/朝堂系统.py
# 层级：世界引擎层 - 社会政治子系统
# 功能：模拟朝廷内部政治生态、官员任免、政策辩论、势力平衡
# 依赖：配置管理、日志系统（弱依赖，可独立运行）
# 被谁调用：世界引擎核心调度器，或更上层的叙事管理模块
# 可插拔性：通过标准接口 (initialize/update/shutdown) 集成，可替换实现

import logging
import random
from typing import Dict, List, Any, Optional

# 假设存在全局配置与工具，若无则提供降级方案
try:
    from utils.config import load_config
    from utils.logger import get_logger
except ImportError:
    # 独立运行时降级
    def load_config(section: str) -> Dict:
        return {}
    def get_logger(name: str) -> logging.Logger:
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(name)s: %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
        return logger

class CourtSystem:
    """朝堂系统核心类，负责管理官员、政策与政治事件。"""

    def __init__(self, config: Optional[Dict] = None):
        """初始化朝堂系统

        Args:
            config: 可选配置字典，若未提供则从全局配置加载或使用默认值
        """
        # 加载配置
        if config is None:
            self.config = load_config("court_system") or self._default_config()
        else:
            self.config = {**self._default_config(), **config}

        # 日志记录器
        self.logger = get_logger("CourtSystem")
        self.logger.info("朝堂系统实例化")

        # 内部状态容器
        self.officials: List[Dict] = []          # 官员列表
        self.policies: List[Dict] = []           # 政策提案列表
        self.faction_power: Dict[str, float] = {}  # 派系势力值

        # 状态标志
        self.initialized = False

    def _default_config(self) -> Dict:
        """默认配置"""
        return {
            "max_officials": 50,
            "debate_rounds": 3,
            "policy_pass_threshold": 0.6,  # 60%支持率通过
            "faction_decay_rate": 0.01,    # 势力自然衰减
            "random_seed": None
        }

    def initialize(self) -> None:
        """初始化朝堂数据，如生成初始官员、派系。从配置中读取种子。"""
        if self.initialized:
            self.logger.warning("朝堂系统已初始化，跳过重复初始化")
            return

        # 设置随机种子（可复现）
        seed = self.config.get("random_seed", None)
        if seed is not None:
            random.seed(seed)

        self.logger.info("开始初始化朝堂系统")

        # 生成初始派系
        factions = self.config.get("initial_factions", ["文官集团", "武将集团", "宦官集团"])
        for faction in factions:
            self.faction_power[faction] = 50.0  # 初始势力均衡

        # 生成初始官员（示例）
        initial_officials = self.config.get("initial_officials", [])
        for off_dict in initial_officials:
            self._add_official(off_dict)

        self.initialized = True
        self.logger.info(f"朝堂系统初始化完成，现有官员 {len(self.officials)} 人，派系 {len(self.faction_power)} 个")

    def update(self, world_state: Dict[str, Any]) -> Dict[str, Any]:
        """每帧/每回合更新朝堂状态，处理政治事件。

        Args:
            world_state: 世界状态快照，包含经济、军事、人口等外部数据

        Returns:
            朝堂系统的状态变化摘要
        """
        if not self.initialized:
            raise RuntimeError("朝堂系统未初始化，请先调用 initialize()")

        self.logger.debug(f"朝堂系统更新，接收世界状态键: {list(world_state.keys())}")

        # 势力自然衰减（模拟政治疲劳）
        for faction in self.faction_power:
            decay = self.faction_power[faction] * self.config["faction_decay_rate"]
            self.faction_power[faction] -= decay
            self.faction_power[faction] = max(0, self.faction_power[faction])

        # 模拟一次简单的政治交流（可扩展）
        events = []
        if self.officials:
            # 随机一名官员失势或得势（仅作示例）
            actor = random.choice(self.officials)
            change = random.randint(-5, 5)
            actor["influence"] = actor.get("influence", 50) + change
            events.append({
                "type": "influence_change",
                "official": actor["name"],
                "change": change
            })

        self.logger.debug(f"朝堂更新产生 {len(events)} 个事件")

        return {
            "faction_power": dict(self.faction_power),
            "events": events
        }

    def shutdown(self) -> None:
        """清理资源，保存状态（此处仅记录日志）"""
        self.logger.info("朝堂系统关闭，保存当前状态")
        # 可在此处实现持久化逻辑
        self.initialized = False

    def add_official(self, name: str, faction: str, rank: int = 1) -> bool:
        """添加一名新官员

        Args:
            name: 官员姓名
            faction: 所属派系
            rank: 品级

        Returns:
            是否添加成功
        """
        if len(self.officials) >= self.config["max_officials"]:
            self.logger.warning("官员数量已达上限，无法添加")
            return False

        if faction not in self.faction_power:
            self.logger.warning(f"派系 {faction} 不存在，自动创建")
            self.faction_power[faction] = 30.0

        official = {
            "name": name,
            "faction": faction,
            "rank": rank,
            "influence": 50,
            "loyalty": 50,
            "active": True
        }
        self._add_official(official)
        return True

    def _add_official(self, data: Dict) -> None:
        """内部添加官员实现"""
        self.officials.append(data)
        self.logger.info(f"添加官员: {data.get('name')}")

    def remove_official(self, name: str, reason: str = "调离") -> bool:
        """移除一名官员（软删除）"""
        for off in self.officials:
            if off["name"] == name and off.get("active", False):
                off["active"] = False
                self.logger.info(f"官员 {name} 因 {reason} 被移除（停用）")
                return True
        self.logger.warning(f"未找到活跃官员 {name}")
        return False

    def propose_policy(self, title: str, content: str, faction: str) -> bool:
        """提出一项政策提案"""
        if faction not in self.faction_power:
            self.logger.error(f"派系 {faction} 不存在")
            return False

        policy = {
            "title": title,
            "content": content,
            "faction": faction,
            "supporters": 0,
            "opposers": 0,
            "passed": False
        }
        self.policies.append(policy)
        self.logger.info(f"政策提案: {title}")
        return True

    def debate_policy(self, policy_index: int) -> Dict:
        """模拟一场政策辩论，返回结果

        Args:
            policy_index: 政策在列表中的索引

        Returns:
            辩论结果摘要
        """
        if policy_index < 0 or policy_index >= len(self.policies):
            raise IndexError("无效的政策索引")
        policy = self.policies[policy_index]

        rounds = self.config["debate_rounds"]
        threshold = self.config["policy_pass_threshold"]
        total_officials = len([o for o in self.officials if o["active"]])

        supporters = 0
        for _ in range(rounds):
            # 每位官员随机支持或反对，受派系影响（简化）
            for off in self.officials:
                if not off["active"]:
                    continue
                if off["faction"] == policy["faction"]:
                    supporters += 1  # 本派系肯定支持
                else:
                    if random.random() < 0.3:  # 30%概率支持
                        supporters += 1

        if total_officials > 0:
            support_rate = supporters / (total_officials * rounds)
        else:
            support_rate = 0

        passed = support_rate >= threshold
        policy["passed"] = passed
        policy["supporters"] = supporters
        policy["opposers"] = total_officials * rounds - supporters

        self.logger.info(f"政策 {policy['title']} 辩论结果: {'通过' if passed else '未通过'}, 支持率 {support_rate:.2%}")

        return {
            "policy_title": policy["title"],
            "passed": passed,
            "support_rate": support_rate,
            "supporters": supporters,
            "opposers": policy["opposers"]
        }

    def get_status(self) -> Dict:
        """获取当前朝堂状态快照，供外部查询"""
        return {
            "officials_count": len([o for o in self.officials if o["active"]]),
            "faction_power": dict(self.faction_power),
            "pending_policies": len(self.policies)
        }


# 自测区域
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 实例化朝堂系统
    config = {
        "max_officials": 10,
        "initial_factions": ["清流党", "后党"],
        "initial_officials": [
            {"name": "张居正", "faction": "清流党", "rank": 1, "influence": 80},
            {"name": "魏忠贤", "faction": "后党", "rank": 2, "influence": 70}
        ]
    }
    court = CourtSystem(config)
    court.initialize()

    # 模拟一次更新
    world_state = {"population": 5000000, "treasury": 100000}
    result = court.update(world_state)
    print("更新结果:", result)

    # 添加官员
    court.add_official("海瑞", "清流党", 3)

    # 提出并辩论一项政策