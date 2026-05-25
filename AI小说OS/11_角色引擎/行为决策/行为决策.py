# 11_角色引擎/行为决策/行为决策.py
# 职责：定义角色行为决策的标准接口与基础操作，所有具体决策逻辑需继承此基类，实现可插拔

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging
import sys

# 配置默认日志格式，可通过外部配置覆盖
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

# 默认配置常量，外部可通过加载配置文件覆盖
DEFAULT_CONFIG = {
    "decision_strategy": "default",   # 决策策略名称
    "max_options": 5,                # 单次决策最多考虑的行动选项数量
    "timeout_seconds": 10,           # 决策超时时间（秒）
    "enable_context_memory": True,   # 是否启用上下文记忆
}

class BehaviorDecision(ABC):
    """
    行为决策抽象基类
    所有具体的角色行为决策器必须继承此类并实现 decide_behavior 方法
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化决策器
        :param config: 可选配置字典，覆盖默认配置
        """
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        logger.info(f"行为决策器初始化：策略={self.config['decision_strategy']}, "
                    f"超时={self.config['timeout_seconds']}s, "
                    f"记忆={self.config['enable_context_memory']}")
        self._validate_config()

    def _validate_config(self):
        """
        内部配置合法性校验，可被子类扩展
        """
        if not isinstance(self.config["max_options"], int) or self.config["max_options"] < 1:
            raise ValueError("配置 max_options 必须为正整数")
        if self.config["timeout_seconds"] <= 0:
            raise ValueError("配置 timeout_seconds 必须大于0")
        # 可扩展更多校验

    @abstractmethod
    def decide_behavior(self, character: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        核心决策方法，根据角色和当前上下文决定行为
        :param character: 角色对象（遵守角色引擎内部定义）
        :param context: 上下文信息，包含剧情状态、环境、关系等
        :return: 决策结果字典，必须包含 action 字段，可选参数
        """
        pass

    def get_context_snapshot(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取上下文快照，用于日志和调试，不改变原始上下文
        :param context: 原始上下文
        :return: 可序列化的摘要
        """
        # 默认实现返回原始字典的浅拷贝，子类可覆写
        return context.copy()

    def report_status(self) -> Dict[str, Any]:
        """
        返回决策器当前状态（用于监控）
        :return: 状态信息字典
        """
        return {
            "decision_strategy": self.config["decision_strategy"],
            "max_options": self.config["max_options"],
            "timeout_seconds": self.config["timeout_seconds"],
            "enable_context_memory": self.config["enable_context_memory"],
        }

# 简易自测
if __name__ == "__main__":
    # 构造一个最小化角色模拟对象
    class MockCharacter:
        def __init__(self, name):
            self.name = name
        def __repr__(self):
            return f"Character({self.name})"

    # 定义一个测试用的具体决策器
    class TestDecision(BehaviorDecision):
        def decide_behavior(self, character, context):
            logger.info(f"决策开始：角色={character}, 上下文关键词={list(context.keys())}")
            # 简单返回一个固定行为
            return {"action": "idle", "reason": "测试决策"}

    # 测试运行
    test_char = MockCharacter("测试角色")
    test_context = {"scene": "客厅", "mood": "平静", "timestamp": 100}

    decision_obj = TestDecision({"max_options": 3})
    result = decision_obj.decide_behavior(test_char, test_context)
    print("决策结果：", result)
    print("决策器状态：", decision_obj.report_status())