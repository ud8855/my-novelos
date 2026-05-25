import logging
import json
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

# ---------- 配置处理 ----------
class NPCAutonomyConfig:
    """NPC自治配置"""
    def __init__(self, config_path: Optional[str] = None, **kwargs):
        self.log_level = kwargs.get("log_level", "INFO")
        self.engine_type = kwargs.get("engine_type", "default")  # 可插拔引擎标识
        self.engine_params = kwargs.get("engine_params", {})
        self.update_interval = kwargs.get("update_interval", 1.0)
        self.max_active_npcs = kwargs.get("max_active_npcs", 100)
        self.data_dir = kwargs.get("data_dir", "./npc_data")
        if config_path and os.path.exists(config_path):
            self._load_from_file(config_path)

    def _load_from_file(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for k, v in data.items():
                if hasattr(self, k):
                    setattr(self, k, v)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "log_level": self.log_level,
            "engine_type": self.engine_type,
            "engine_params": self.engine_params,
            "update_interval": self.update_interval,
            "max_active_npcs": self.max_active_npcs,
            "data_dir": self.data_dir,
        }

# ---------- 抽象决策引擎 ----------
class NPCDecisionEngine(ABC):
    """NPC决策引擎抽象基类，用于可插拔行为决策"""
    @abstractmethod
    def decide(self, npc_state: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据NPC当前状态和世界上下文，返回决策动作。
        :param npc_state: NPC状态字典（位置、需求、情绪等）
        :param context:   世界环境上下文（时间、地点、其他实体等）
        :return: 决策动作字典，格式如 {"action": "move", "params": {...}}
        """
        pass

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """初始化引擎，传入特定配置"""
        pass

# ---------- 默认简单引擎 ----------
class DefaultDecisionEngine(NPCDecisionEngine):
    """默认决策引擎：基于简单规则"""
    def __init__(self):
        self.logger = logging.getLogger("NPCAutonomy.DefaultEngine")
        self.rules = []

    def initialize(self, config: Dict[str, Any]) -> None:
        self.rules = config.get("rules", [])

    def decide(self, npc_state: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        # 简单示例：若有“饥饿”需求，则选择“觅食”动作
        needs = npc_state.get("needs", {})
        if needs.get("hunger", 0) > 50:
            return {"action": "find_food", "params": {}}
        # 否则随机漫游
        return {"action": "wander", "params": {}}

# ---------- 引擎工厂 ----------
class DecisionEngineFactory:
    """决策引擎工厂，支持热插拔"""
    _registry: Dict[str, type] = {
        "default": DefaultDecisionEngine,
    }

    @classmethod
    def register_engine(cls, name: str, engine_cls: type):
        if not issubclass(engine_cls, NPCDecisionEngine):
            raise TypeError("Engine must be a subclass of NPCDecisionEngine")
        cls._registry[name] = engine_cls

    @classmethod
    def create_engine(cls, engine_type: str, engine_params: Dict[str, Any]) -> NPCDecisionEngine:
        if engine_type not in cls._registry:
            raise ValueError(f"Unknown engine type: {engine_type}")
        engine_cls = cls._registry[engine_type]
        engine = engine_cls()
        engine.initialize(engine_params)
        return engine

# ---------- NPC自治主类 ----------
class NPCAutonomy:
    """NPC自治系统，负责管理所有NPC的自主行为决策与执行"""
    def __init__(self, config: NPCAutonomyConfig):
        self.config = config
        self.logger = self._setup_logger()
        self.engine = DecisionEngineFactory.create_engine(config.engine_type, config.engine_params)
        self.active_npcs: Dict[str, Dict[str, Any]] = {}  # npc_id -> state
        self.data_dir = config.data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.logger.info("NPCAutonomy initialized with engine: %s", config.engine_type)

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger("NPCAutonomy")
        logger.setLevel(getattr(logging, self.config.log_level.upper(), logging.INFO))
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    def register_npc(self, npc_id: str, initial_state: Dict[str, Any]) -> bool:
        """注册一个NPC到自治系统"""
        if len(self.active_npcs) >= self.config.max_active_npcs:
            self.logger.warning("NPC registration failed: max active limit reached.")
            return False
        if npc_id in self.active_npcs:
            self.logger.warning("NPC %s already registered, overwriting state.", npc_id)
        self.active_npcs[npc_id] = initial_state
        self.logger.debug("NPC %s registered.", npc_id)
        return True

    def unregister_npc(self, npc_id: str) -> bool:
        """移除NPC"""
        if npc_id in self.active_npcs:
            del self.active_npcs[npc_id]
            self.logger.debug("NPC %s unregistered.", npc_id)
            return True
        return False

    def update(self, world_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        对所有活跃NPC执行一次决策更新。
        :param world_context: 当前世界上下文
        :return: NPC动作映射 {npc_id: decision}
        """
        actions = {}
        for npc_id, state in self.active_npcs.items():
            try:
                decision = self.engine.decide(state, world_context)
                actions[npc_id] = decision
                # 可以在此根据决策更新内部状态（如位置变化等），这里暂时不更新，留给上层
            except Exception as e:
                self.logger.error("Decision failed for NPC %s: %s", npc_id, str(e))
        return actions

    def save_state(self, file_name: str = "npc_states.json") -> str:
        """持久化所有NPC状态到文件"""
        path = os.path.join(self.data_dir, file_name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.active_npcs, f, ensure_ascii=False, indent=2)
        self.logger.info("NPC states saved to %s", path)
        return path

    def load_state(self, file_name: str = "npc_states.json") -> bool:
        """从文件加载NPC状态"""
        path = os.path.join(self.data_dir, file_name)
        if not os.path.exists(path):
            self.logger.warning("State file not found: %s", path)
            return False
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.active_npcs = data
        self.logger.info("NPC states loaded from %s, count: %d", path, len(self.active_npcs))
        return True

    def hot_reload_engine(self, new_engine_type: str, new_engine_params: Optional[Dict[str, Any]] = None) -> bool:
        """热更新决策引擎（运行时切换）"""
        try:
            self.engine = DecisionEngineFactory.create_engine(
                new_engine_type, new_engine_params or self.config.engine_params
            )
            self.config.engine_type = new_engine_type
            self.logger.info("Decision engine hot-reloaded to: %s", new_engine_type)
            return True
        except Exception as e:
            self.logger.error("Failed to hot-reload engine: %s", str(e))
            return False

    def shutdown(self):
        """安全关闭，保存状态"""
        self.logger.info("NPCAutonomy shutting down, saving states...")
        self.save_state()
        self.logger.info("Shutdown complete.")

# ---------- 自测 ----------
if __name__ == "__main__":
    # 配置
    config = NPCAutonomyConfig(
        log_level="DEBUG",
        engine_type="default",
    )
    # 创建自治系统
    npc_auto = NPCAutonomy(config)

    # 注册NPC
    npc1_state = {
        "name": "Guard",
        "location": "village_gate",
        "needs": {"hunger": 70, "fatigue": 30},
        "personality": "brave"
    }
    npc2_state = {
        "name": "Merchant",
        "location": "market",
        "needs": {"hunger": 20, "wealth": 100},
        "personality": "greedy"
    }
    npc_auto.register_npc("npc_001", npc1_state)
    npc_auto.register_npc("npc_002", npc2_state)

    # 模拟世界上下文
    world = {"time": "morning", "weather": "sunny", "danger_level": 0}

    # 第一次更新
    decisions = npc_auto.update(world)
    print("Decisions:", decisions)

    # 保存状态
    npc_auto.save_state()

    # 模拟卸载再加载
    npc_auto2 = NPCAutonomy(config)
    npc_auto2.load_state()
    print("Loaded NPCs:", npc_auto2.active_npcs)

    # 热更新引擎测试（注册一个自定义引擎）
    class TestEngine(NPCDecisionEngine):
        def initialize(self, config: Dict[str, Any]) -> None:
            pass
        def decide(self, npc_state: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
            return {"action": "test_action", "params": {}}

    DecisionEngineFactory.register_engine("test", TestEngine)
    npc_auto2.hot_reload_engine("test")
    test_decisions = npc_auto2.update(world)
    print("Test engine decisions:", test_decisions)

    # 关闭
    npc_auto.shutdown()
    npc_auto2.shutdown()