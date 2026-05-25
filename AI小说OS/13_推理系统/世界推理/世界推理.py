# 13_推理系统/世界推理/世界推理.py

"""
世界推理模块 (WorldReasoner)
层级：13_推理系统
依赖：日志系统、配置系统、模型协同(20_)、API模型(21_)(可选)
被调用：剧情推理、互动生成、世界状态更新模块
解决：根据当前故事状态推理世界变化、一致性检查、事件触发
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple, Callable
from pathlib import Path
import traceback

# 系统内部模块（遵循抽象导入，可后期替换）
try:
    from common.logger import get_logger
    from common.config import ConfigManager
    from common.exceptions import RecoverableError, NonRecoverableError
    from common.hot_updater import HotUpdatable
    from common.interfaces import ReasonerInterface
except ImportError:
    # 骨架占位，实际部署时替换
    get_logger = logging.getLogger
    ConfigManager = None
    ReasonerInterface = ABC
    HotUpdatable = object
    class RecoverableError(Exception): pass
    class NonRecoverableError(Exception): pass

logger = get_logger(__name__)


class WorldReasoner(HotUpdatable, ReasonerInterface):
    """
    世界推理器基类
    - 接收世界状态和叙事事件，输出推理结果
    - 支持规则推理和基于模型推理的切换
    - 可插拔：通过配置文件指定具体实现子类
    - 支持热更新、异常恢复、日志追踪
    """

    # 配置键名
    CONFIG_SECTION = "world_reasoner"

    def __init__(self, config_path: Optional[str] = None, **kwargs):
        """
        :param config_path: 配置文件路径，若为None则使用默认配置
        :param kwargs: 额外参数，可覆盖配置
        """
        self._config = self._load_config(config_path) if config_path and ConfigManager else {}
        self._config.update(kwargs)
        self._validate_config()

        # 日志
        self.logger = logger.getChild(self.__class__.__name__)
        self.logger.info(f"Initializing {self.__class__.__name__}")

        # 推理组件（可插拔）
        self._rule_engine = None
        self._model_invoker = None  # 调用模型协同层
        self._state_cache = {}
        self._last_recovery_timestamp = 0

        # 初始化组件
        self._init_components()

    # ---------- 配置管理 ----------
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        加载配置
        """
        try:
            if ConfigManager:
                cm = ConfigManager()
                return cm.load(config_path, self.CONFIG_SECTION)
            else:
                import json
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f).get(self.CONFIG_SECTION, {})
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
            raise NonRecoverableError(f"Configuration error: {e}")

    def _validate_config(self):
        """验证必要配置项"""
        required = []
        for key in required:
            if key not in self._config:
                raise NonRecoverableError(f"Missing required config: {key}")

    def _init_components(self):
        """初始化推理引擎、模型调用器等组件"""
        # 根据配置动态加载推理策略
        engine_type = self._config.get("engine_type", "rule")  # rule / model / hybrid
        if engine_type in ("rule", "hybrid"):
            # 规则引擎延迟加载
            from .rule_engine import RuleEngine
            self._rule_engine = RuleEngine(self._config.get("rule_engine_config", {}))
        if engine_type in ("model", "hybrid"):
            # 模型推理调用器延迟导入
            from ..model_integrator import ModelInvoker
            self._model_invoker = ModelInvoker(self._config.get("model_config", {}))

        # 注册热更新回调
        if hasattr(self, 'register_update_callback'):
            self.register_update_callback('reload_config', self.reload_config)

    # ---------- 核心推理接口 ----------
    @abstractmethod
    def reason(self, world_state: Dict[str, Any], narrative_events: List[Dict]) -> Dict[str, Any]:
        """
        执行世界推理
        :param world_state: 当前世界状态快照（角色、地点、时间、天气、因果链等）
        :param narrative_events: 新发生的故事事件列表
        :return: 推理结果：
            {
                "new_world_state": Dict,    # 更新后的世界状态（部分）
                "changes": List[Dict],      # 变化列表
                "triggered_events": List[Dict], # 被触发的新事件
                "consistency_report": Dict, # 一致性检查报告
            }
        """
        pass

    def reason_with_recovery(self, world_state: Dict, narrative_events: List[Dict],
                             max_retries: int = 3) -> Dict[str, Any]:
        """
        带异常恢复的推理执行
        """
        for attempt in range(max_retries):
            try:
                return self.reason(world_state, narrative_events)
            except RecoverableError as e:
                self.logger.warning(f"Recoverable error during reasoning (attempt {attempt+1}): {e}")
                time.sleep(0.5 * (attempt+1))
                # 可尝试重置状态或修复输入
                world_state = self._attempt_state_fix(world_state, e)
                continue
            except NonRecoverableError as e:
                self.logger.error(f"Non-recoverable error: {e}")
                raise
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}\n{traceback.format_exc()}")
                # 尝试回退到上一次稳定状态
                if self._last_recovery_timestamp > 0:
                    self.logger.info("Attempting rollback to last stable state.")
                raise
        raise NonRecoverableError("Max retries exceeded in reasoning.")

    def _attempt_state_fix(self, state: Dict, error: Exception) -> Dict:
        """尝试修复状态以便重试（由子类实现）"""
        return state

    # ---------- 辅助方法 ----------
    def validate_consistency(self, world_state: Dict) -> Tuple[bool, List[str]]:
        """世界状态一致性检查（规则引擎）"""
        if self._rule_engine:
            return self._rule_engine.check_consistency(world_state)
        return True, []

    def infer_causality(self, event: Dict, state: Dict) -> Dict:
        """推断事件的因果链（可用于模型推理）"""
        if self._model_invoker:
            return self._model_invoker.infer_causality(event, state)
        return {}

    def predict_future_state(self, current_state: Dict, steps: int = 1) -> Dict:
        """预测未来状态（可选）"""
        raise NotImplementedError

    # ---------- 热更新支持 ----------
    def reload_config(self, **kwargs):
        """热更新配置"""
        self._config.update(kwargs)
        self._validate_config()
        self._init_components()  # 重新初始化组件
        self.logger.info("WorldReasoner config reloaded.")

    # ---------- 状态缓存（用于恢复）----------
    def save_state_cache(self):
        """保存当前推理状态用于恢复"""
        self._last_recovery_timestamp = time.time()
        # 保存到内存或文件
        self._state_cache['timestamp'] = self._last_recovery_timestamp

    def load_state_cache(self) -> Optional[Dict]:
        """加载上次推理状态"""
        return self._state_cache if self._state_cache.get('timestamp') else None


# ---------- 可插拔示例子类（规则引擎版） ----------
class RuleBasedWorldReasoner(WorldReasoner):
    """基于规则的快速世界推理"""

    def __init__(self, config_path=None, **kwargs):
        super().__init__(config_path, **kwargs)
        self.rules = self._load_rules()

    def _load_rules(self):
        # 从配置文件或默认规则加载
        return []

    def reason(self, world_state, narrative_events):
        # 示例推理流程
        new_state = world_state.copy()
        changes = []
        triggered = []
        consistency_report = {"valid": True, "warnings": []}

        for event in narrative_events:
            # 规则匹配与执行
            pass

        # 一致性检查
        valid, warnings = self.validate_consistency(new_state)
        if not valid:
            consistency_report["valid"] = False
            consistency_report["warnings"].extend(warnings)

        return {
            "new_world_state": new_state,
            "changes": changes,
            "triggered_events": triggered,
            "consistency_report": consistency_report
        }


# ---------- 模型协同版子类 ----------
class ModelWorldReasoner(WorldReasoner):
    """调用大模型进行世界推理（用于复杂场景）"""

    def reason(self, world_state, narrative_events):
        if not self._model_invoker:
            raise NonRecoverableError("Model invoker not initialized.")
        # 调用模型协同层
        combined_input = {
            "world_state": world_state,
            "events": narrative_events
        }
        result = self._model_invoker.reason_world(combined_input)
        return result


# ---------- 自测 ----------
if __name__ == "__main__":
    # 简单自测：基本实例化、配置加载、推理调用
    import json
    test_config = {
        "engine_type": "rule",
        "rule_engine_config": {},
        "model_config": {}
    }
    try:
        reasoner = RuleBasedWorldReasoner(config_path=None, **test_config)
        print("RuleBasedWorldReasoner 初始化成功")
        # 模拟推理
        state = {"location": "tavern", "time": "night", "characters": ["Hero", "Barmaid"]}
        events = [{"type": "conversation", "content": "Hero asks for a drink"}]
        result = reasoner.reason_with_recovery(state, events)
        print("推理结果:", json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        traceback.print_exc()
        print("测试失败:", e)