"""
Runtime规则引擎
负责运行时规则的定义、注册、触发和异常恢复。
提供可插拔的规则接口，支持热更新、日志记录和配置化。
"""

import abc
import logging
import sys
from typing import Dict, List, Callable, Any, Optional

# ------------------- 配置化 -------------------
def _load_config():
    # TODO: 从配置文件或环境变量加载规则引擎配置
    # 参数: debug, log_level, rule_dirs 等
    return {
        "log_level": "DEBUG",
        "rule_dirs": ["rules"]
    }

CONFIG = _load_config()

# ------------------- 日志设置 -------------------
logger = logging.getLogger("Runtime规则引擎")
logger.setLevel(getattr(logging, CONFIG.get("log_level", "INFO").upper(), logging.INFO))
if not logger.handlers:
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s] %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# ------------------- 异常定义 -------------------
class RuleException(Exception):
    """规则执行异常"""
    pass

class RuleNotFoundError(RuleException):
    """规则未找到"""
    pass

class RuleExecutionError(RuleException):
    """规则执行错误"""
    pass

# ------------------- 规则基类 -------------------
class BaseRule(abc.ABC):
    """所有运行时规则的抽象基类。
    实现该类的规则必须可插拔，即通过注册加载。
    """
    def __init__(self, name: str, priority: int = 0):
        self.name = name
        self.priority = priority  # 优先级，数值越大越先执行
        logger.debug(f"规则初始化: {self.name} (priority={self.priority})")

    @abc.abstractmethod
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """评估规则条件，返回True表示触发。
        :param context: 运行时上下文，包含各模块传递的信息
        :return: 是否满足规则条件
        """
        pass

    @abc.abstractmethod
    def execute(self, context: Dict[str, Any]) -> Any:
        """执行规则动作，当evaluate返回True时调用。
        :param context: 运行时上下文
        :return: 执行结果
        """
        pass

    def __repr__(self):
        return f"<Rule:{self.name}:{self.priority}>"

# ------------------- 规则引擎 -------------------
class RuntimeRuleEngine:
    """运行时可插拔规则引擎。
    负责管理规则的生命周期，包括注册、卸载、触发、异常恢复。
    """
    def __init__(self):
        self._rules: Dict[str, BaseRule] = {}
        self._rule_queue: List[BaseRule] = []  # 按优先级排序的规则列表
        self._is_running = False
        logger.info("Runtime规则引擎初始化完成")