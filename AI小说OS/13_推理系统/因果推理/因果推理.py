"""
13_推理系统/因果推理/因果推理.py
因果推理模块 - 负责小说情节中的因果关系推断
可插拔设计，支持配置化、日志记录
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

# 配置日志
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("CausalReasoner")

class CausalReasoner:
    """
    因果推理器
    遵循统一推理接口协议，实现可插拔的因果分析能力
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化因果推理器

        Args:
            config: 字典形式的配置参数，可从配置文件或环境变量加载
        """
        self.config = config or self._load_default_config()
        self.rules: List[Dict[str, Any]] = []  # 存储因果规则
        self.knowledge_base: Dict[str, Any] = {}  # 知识库（例如事件图谱）
        self._setup_from_config()

    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置，支持从环境变量覆盖"""
        return {
            "max_chain_length": int(os.getenv("CAUSAL_MAX_CHAIN", 5)),
            "confidence_threshold": float(os.getenv("CAUSAL_CONFIDENCE", 0.7)),
            "enable_logging": os.getenv("CAUSAL_LOG", "True").lower() == "true",
            "model_backend": os.getenv("CAUSAL_BACKEND", "default"),
        }

    def _setup_from_config(self):
        """根据配置初始化内部状态"""
        if self.config.get("enable_logging", True):
            logger.setLevel(logging.INFO)
        else:
            logger.setLevel(logging.WARNING)

    def add_rule(self, cause: str, effect: str, confidence: float = 1.0):
        """
        添加因果规则

        Args:
            cause: 原因事件
            effect: 结果事件
            confidence: 置信度 (0~1)
        """
        rule = {"cause": cause, "effect": effect, "confidence": confidence}
        self.rules.append(rule)
        logger.debug(f"新增因果规则: {cause} -> {effect} (置信度: {confidence})")

    def remove_rule(self, cause: str, effect: str):
        """移除指定因果规则"""
        self.rules = [
            r for r in self.rules if not (r["cause"] == cause and r["effect"] == effect)
        ]
        logger.debug(f"移除因果规则: {cause} -> {effect}")

    def infer(
        self,
        event: str,
        context: Optional[List[str]] = None,
        direction: str = "forward",
    ) -> List[Tuple[str, float]]:
        """
        基于当前事件进行因果推理

        Args:
            event: 当前事件描述
            context: 上下文事件列表（可选）
            direction: 推理方向，'forward' 为向前推断结果，'backward' 为回溯原因

        Returns:
            含有 (事件, 置信度) 的列表，按置信度降序排列
        """
        logger.info(f"执行因果推理: 事件='{event}', 方向='{direction}'")
        # TODO: 实现具体的因果推理算法（例如规则匹配或模型调用）
        results: List[Tuple[str, float]] = []
        if direction == "forward":
            # 伪实现：返回示例结果
            results = [("结果事件A", 0.9), ("结果事件B", 0.8)]
        elif direction == "backward":
            results = [("原因事件X", 0.85), ("原因事件Y", 0.75)]
        else:
            logger.warning(f"未知的推理方向: {direction}")

        return sorted(results, key=lambda x: x[1], reverse=True)

    def analyze_chain(
        self, event_sequence: List[str]
    ) -> List[Dict[str, Any]]:
        """
        分析事件序列中的因果链

        Args:
            event_sequence: 按时间顺序的事件列表

        Returns:
            因果链列表，每个元素包含 'cause_index', 'effect_index', 'confidence'
        """
        logger.info(f"分析事件序列因果链，长度={len(event_sequence)}")
        # TODO: 实现因果链发现算法
        return [
            {"cause_index": 0, "effect_index": 1, "confidence": 0.95},
            {"cause_index": 1, "effect_index": 2, "confidence": 0.87},
        ]

    def shutdown(self):
        """安全关闭推理器，释放资源"""
        logger.info("因果推理器关闭")
        # 清理资源（如果有持久化连接等）
        self.rules.clear()
        self.knowledge_base.clear()


# 自测代码
if __name__ == "__main__":
    print("=== 因果推理器自测 ===")
    reasoner = CausalReasoner()
    reasoner.add_rule("下雨", "地面湿滑", confidence=0.95)
    reasoner.add_rule("地面湿滑", "摔倒", confidence=0.8)

    # 前向推理测试
    forward_results = reasoner.infer("下雨", direction="forward")
    print(f"前向推理结果: {forward_results}")

    # 后向推理测试
    backward_results = reasoner.infer("摔倒", direction="backward")
    print(f"后向推理结果: {backward_results}")

    # 因果链分析测试
    chain = reasoner.analyze_chain(["下雨", "地面湿滑", "摔倒"])
    print(f"因果链分析: {chain}")

    reasoner.shutdown()
    print("自测完成")