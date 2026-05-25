"""
成长系统模块
用于管理角色经验值、等级提升、属性成长等功能。
支持自定义成长策略，可插拔，配置化。
"""

import logging
from typing import Dict, Any, Optional
import threading

# 设置日志
logger = logging.getLogger(__name__)

class GrowthStrategy:
    """成长策略基类"""
    def calculate_exp_needed(self, current_level: int, config: Dict[str, Any]) -> int:
        """计算升级所需经验值"""
        raise NotImplementedError

    def calculate_attribute_gains(self, character: Any, config: Dict[str, Any]) -> Dict[str, float]:
        """计算属性增长数值"""
        raise NotImplementedError


class DefaultGrowthStrategy(GrowthStrategy):
    """默认成长策略"""
    def calculate_exp_needed(self, current_level: int, config: Dict[str, Any]) -> int:
        base = config.get("base_exp", 100)
        factor = config.get("exp_factor", 1.5)
        return int(base * (factor ** (current_level - 1)))

    def calculate_attribute_gains(self, character: Any, config: Dict[str, Any]) -> Dict[str, float]:
        # 默认每个属性随机增加固定值，可扩展为随机
        return {"strength": 1.0, "intelligence": 1.0, "agility": 1.0}


class GrowthSystem:
    """角色成长系统，单例模式，管理成长策略与升级流程"""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if self._initialized:
            return
        self._initialized = True
        self.strategies: Dict[str, GrowthStrategy] = {}
        self.config: Dict[str, Any] = config if config else self._default_config()
        self._register_default_strategies()
        logger.info("GrowthSystem initialized with config: %s", self.config)

    def _default_config(self) -> Dict[str, Any]:
        """默认配置"""
        return {
            "base_exp": 100,
            "exp_factor": 1.5,
            "max_level": 100,
            "attrs_per_level": ["strength", "intelligence", "agility"]
        }

    def _register_default_strategies(self):
        """注册默认策略"""
        self.register_strategy("default", DefaultGrowthStrategy())

    def register_strategy(self, name: str, strategy: GrowthStrategy):
        """注册新的成长策略"""
        if name in self.strategies:
            logger.warning("Strategy '%s' already exists, overwriting.", name)
        self.strategies[name] = strategy
        logger.info("Strategy '%s' registered.", name)

    def unregister_strategy(self, name: str):
        """移除成长策略"""
        if name in self.strategies:
            del self.strategies[name]
            logger.info("Strategy '%s' unregistered.", name)

    def get_strategy(self, name: str = "default") -> GrowthStrategy:
        """获取成长策略，若未找到