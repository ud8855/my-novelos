""" AI规则模块 - 规则引擎核心组件
职责：定义和管理AI驱动的规则，支持条件匹配和动作执行。
可插拔设计，支持热更新、异常恢复、日志记录、配置化。
"""

import logging
import json
import os
from typing import Dict, Any, Callable, List, Optional
from abc import ABC, abstractmethod

# 配置日志
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AIRule")

# 默认配置文件路径
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "ai_rules.json")


class RuleCondition(ABC):
    """条件基类，所有条件需继承此类"""
    @abstractmethod
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """评估条件是否满足"""