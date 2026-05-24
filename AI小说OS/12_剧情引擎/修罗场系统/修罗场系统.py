"""  
修罗场系统.py  
所属层级: 12_剧情引擎/修罗场系统  
依赖: 角色系统(16_角色系统), 情感系统(13_情感引擎), 事件系统(11_事件系统)  
被调用: 剧情调度器(10_剧情调度)  
职责: 生成和管理多角色之间的情感冲突场景，控制剧情张力  
"""

import logging
import threading
from typing import Any, Dict, List, Optional, Callable
from abc import ABC, abstractmethod

# ---------- 配置 ----------
class LoveTriangleConfig:
    """修罗场系统配置（可插拔配置源）"""
    def __init__(self, config_dict: Optional[Dict] = None):
        self.conflict_threshold = 0.7          # 冲突触发阈值
        self.max_participants = 4              # 最大参与人数
        self.default_tension_increase = 0.1    # 默认紧张度增量
        self.enable_auto_resolve = False       # 是否自动化解修罗场
        self.custom_rules: List[Callable] = [] # 自定义规则钩子
        if config_dict:
            self.__dict__.update(config_dict)
    
    def from_json(self, path: str):
        """从JSON加载配置 (预留)"""
        pass

    def to_dict(self) -> Dict:
        return self.__dict__

# ---------- 日志 ----------
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ---------- 修罗场场景接口 (可插拔基础) ----------
class LoveTriangleScenario(ABC):
    """修罗场场景抽象接口 - 所有具体修罗场必须实现此接口"""
    @abstractmethod
    def initialize(self, context: Dict) -> bool:
        """场景初始化，返回是否成功"""
        pass

    @abstractmethod
    def step(self, delta_time: float) -> Dict:
        """推进场景一步，返回产生的叙事片段"""
        pass

    @abstractmethod
    def resolve(self) -> Dict:
        """解决修罗场，返回结局描述"""
        pass

    @abstractmethod
    def get_participants(self) -> List[str]:
        """获取当前参与的角色ID列表"""
        pass

    @abstractmethod
    def get_tension(self) -> float:
        """获取当前紧张度"""
        pass

# ---------- 修罗场系统核心 ----------
class LoveTriangleSystem:
    """
    修罗场系统主控
    职责：根据情感状态和事件触发修罗场场景，管理冲突生成与解决
    """
    def __init__(self, config: Optional[LoveTriangleConfig] = None):
        self.config = config if config else LoveTriangleConfig()
        self.active_scenario: Optional[LoveTriangleScenario] = None
        self.scenario_registry: Dict[str, LoveTriangleScenario] = {}
        self.history: List[Dict] = []  # 记录触发的修罗场历史
        self._lock = threading.Lock()
        logger.info("修罗场系统初始化完成")

    def register_scenario(self, name: str, scenario: LoveTriangleScenario):
        """注册修罗场场景插件（可插拔）"""
        with self._lock:
            if name in self.scenario_registry:
                logger.warning(f"场景 '{name}' 已存在，将被覆盖")
            self.scenario_registry[name] = scenario
            logger.info(f"注册修罗场场景: {name}")

    def unregister_scenario(self, name: str):
        """注销场景"""
        with self._lock:
            if name in self.scenario_registry:
                del self.scenario_registry[name]
                logger.info(f"注销场景: {name}")

    def can_trigger(self, participants: List[str], emotional_state: Dict) -> bool:
        """
        判断是否满足修罗场触发条件
        参数:
            participants: 涉及角色ID列表
            emotional_state: 角色间情感状态快照
        返回: 是否触发
        """
        if len(participants) < 2:
            return False
        if len(participants) > self.config.max_participants:
            return False
        # 检查情感冲突指数
        conflict_index = self._calculate_conflict(participants, emotional_state)
        logger.debug(f"参与角色: {participants}, 冲突指数: {conflict_index:.2f}, 阈值: {self.config.conflict_threshold}")
        if conflict_index >= self.config.conflict_threshold:
            return True
        # 允许用户自定义规则
        for rule in self.config.custom_rules:
            if rule(participants, emotional_state, self.config):
                return True
        return False

    def trigger(self, scenario_name: str, context: Dict) -> Optional[str]:
        """
        触发一个修罗场场景
        参数:
            scenario_name: 注册的场景名称
            context: 场景初始化所需的上下文数据
        返回: 场景实例标识（名称），失败返回None
        """
        with self._lock:
            if self.active_scenario is not None:
                logger.warning("已有活跃修罗场，无法触发新场景")
                return None
            scenario = self.scenario_registry.get(scenario_name)
            if not scenario:
                logger.error(f"未找到修罗场场景: {scenario_name}")
                return None
            if not scenario.initialize(context):
                logger.error(f"场景 '{scenario_name}' 初始化失败")
                return None
            self.active_scenario = scenario
            record = {
                "scenario": scenario_name,
                "participants": scenario.get_participants(),
                "start_time": threading.get_ident(),  # 可以用时间戳代替，这里用线程ID示意
                "status": "active"
            }
            self.history.append(record)
            logger.info(f"触发修罗场: {scenario_name}, 参与角色: {record['participants']}")
            return scenario_name

    def step(self, delta_time: float) -> Optional[Dict]:
        """推进当前修罗场一步，返回叙事片段字典"""
        if not self.active_scenario:
            logger.debug("无活跃修罗场")
            return None
        result = self.active_scenario.step(delta_time)
        logger.debug(f"修罗场推进: {result}")
        return result

    def resolve_current(self) -> Optional[Dict]:
        """手动解决当前修罗场"""
        if not self.active_scenario:
            logger.warning("无活跃修罗场需要解决")
            return None
        result = self.active_scenario.resolve()
        self._end_active_scenario("resolved")
        return result

    def abort_current(self, reason: str = "aborted"):
        """强制中止当前修罗场"""
        if self.active_scenario:
            logger.warning(f"强制中止修罗场，原因: {reason}")
            self._end_active_scenario(reason)

    def _end_active_scenario(self, status: str):
        """结束当前活跃场景，更新历史记录"""
        if self.active_scenario:
            # 更新历史记录状态
            if self.history and self.history[-1]["status"] == "active":
                self.history[-1]["status"] = status
            self.active_scenario = None
            logger.info(f"修罗场结束，状态: {status}")

    def _calculate_conflict(self, participants: List[str], emotional_state: Dict) -> float:
        """
        计算角色间情感冲突指数 (0-1)
        此方法可后续与情感引擎(13_情感引擎)集成
        """
        # 简单示例：角色间好感度差异的加权平均
        if len(participants) < 2:
            return 0.0
        # 假设情感状态包含角色两两之间的“attraction”值
        pairs = [(participants[i], participants[j]) for i in range(len(participants)) for j in range(i+1, len(participants))]
        diffs = []
        for a, b in pairs:
            val_a = emotional_state.get((a,b), {}).get("attraction", 0.5)
            val_b = emotional_state.get((b,a), {}).get("attraction", 0.5)
            diffs.append(abs(val_a - val_b))
        if not diffs:
            return 0.0
        avg_diff = sum(diffs) / len(diffs)
        return min(1.0, avg_diff * 2)  # 示例映射

    def get_active_participants(self) -> List[str]:
        """获取当前活跃修罗场的参与角色ID
        解决什么问题: 让UI或调度器知道当前场景涉及哪些角色"""
        if self.active_scenario:
            return self.active_scenario.get_participants()
        return []

    def get_tension(self) -> float:
        """获取当前修罗场紧张度"""
        if self.active_scenario:
            return self.active_scenario.get_tension()
        return 0.0

# ---------- 自测 ----------
if __name__ == "__main__":
    print("===== 修罗场系统自测 =====")
    # 创建一个简单的场景实现（用于测试）
    class MockScenario(LoveTriangleScenario):
        def __init__(self):
            self.tension = 0.0
            self.parts = []
        def initialize(self, context):
            self.parts = context.get("participants", [])
            self.tension = 0.5
            print(f"MockScenario初始化: {self.parts}")
            return True
        def step(self, dt):
            self.tension += 0.05
            return {"narrative": f"张力上升至{self.tension:.2f}"}
        def resolve(self):
            return {"result": "关系微妙地平衡了"}
        def get_participants(self):
            return self.parts
        def get_tension(self):
            return self.tension

    # 创建系统
    system = LoveTriangleSystem(LoveTriangleConfig(conflict_threshold=0.5))
    system.register_scenario("cafe_showdown", MockScenario())
    
    # 模拟情感状态
    emo_state = {
        ("A", "B"): {"attraction": 0.8},
        ("B", "A"): {"attraction": 0.2},
    }
    if system.can_trigger(["A", "B"], emo_state):
        system.trigger("cafe_showdown", {"participants": ["A", "B"]})
    else:
        print("条件不满足，无法触发")
    
    for _ in range(3):
        step_result = system.step(0.1)
        if step_result:
            print(f"步进结果: {step_result}")

    resolution = system.resolve_current()
    if resolution:
        print(f"结局: {resolution}")
    
    print("历史记录:", system.history)
    print("自测完成")