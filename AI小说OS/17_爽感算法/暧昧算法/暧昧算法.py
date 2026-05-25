"""
暧昧算法模块
位于 17_爽感算法/暧昧算法
功能：计算给定文本或交互数据中的暧昧程度得分。
可插拔设计：通过继承基类实现不同算法，当前为骨架。
配置化：可通过配置文件调整参数。
日志：记录关键计算过程。
"""

import logging
import json
from typing import Any, Dict, Optional

# 配置日志
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())  # 默认无处理，由上层配置


class AmbiguityConfig:
    """
    暧昧算法配置类
    所有参数均支持从字典或JSON文件加载，可热更新。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # 默认配置
        self.weight_keywords: float = 0.4          # 关键词权重
        self.weight_context: float = 0.3           # 上下文权重
        self.weight_interaction: float = 0.3       # 交互频率权重
        self.keywords: list = ["靠近", "微笑", "凝视", "触碰", "悄悄话"]  # 暧昧关键词
        self.threshold: float = 0.6                # 判定为暧昧的阈值
        # 自定义配置覆盖
        if config:
            self.update(config)

    def update(self, config: Dict[str, Any]):
        """热更新配置"""
        for key, value in config.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.info(f"AmbiguityConfig updated: {key} = {value}")
            else:
                logger.warning(f"Unknown config key: {key}")

    def to_dict(self) -> Dict[str, Any]:
        """导出当前配置"""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}


class BaseAmbiguityAlgorithm:
    """
    暧昧算法基类
    所有具体暧昧算法必须继承此类，并实现 calculate() 方法。
    支持可插拔：运行时可通过类名动态加载。
    """
    def __init__(self, config: Optional[AmbiguityConfig] = None):
        self.config = config or AmbiguityConfig()
        self.logger = logging.getLogger(self.__class__.__name__)

    def calculate(self, text: str, context: Optional[Dict[str, Any]] = None) -> float:
        """
        计算暧昧得分的主接口。
        :param text: 输入文本（对话、叙述等）
        :param context: 上下文信息，如人物关系、前文交互等
        :return: 暧昧得分，范围 [0.0, 1.0]，越高越暧昧
        """
        raise NotImplementedError("Subclasses must implement calculate()")

    def is_ambiguity(self, score: float) -> bool:
        """根据阈值判断是否达到暧昧状态"""
        return score >= self.config.threshold


class SimpleKeywordAmbiguity(BaseAmbiguityAlgorithm):
    """
    基于关键词匹配的简单暧昧算法（骨架实现）
    用于演示接口，实际可替换为复杂模型。
    """
    def calculate(self, text: str, context: Optional[Dict[str, Any]] = None) -> float:
        """简单关键词匹配计算"""
        self.logger.debug(f"Calculating ambiguity for text length={len(text)}")
        if not text:
            return 0.0
        
        # 关键词匹配得分
        keyword_score = 0.0
        for kw in self.config.keywords:
            if kw in text:
                keyword_score += 1
        keyword_score = min(1.0, keyword_score / max(len(self.config.keywords), 1))
        
        # 上下文得分（示例：若有前文亲密关系，加分）
        context_score = 0.0
        if context:
            relationship = context.get("relationship", 0.0)  # 0-1的关系值
            context_score = relationship
        
        # 交互频率得分（示例：对话轮次多可能更暧昧）
        interaction_score = 0.0
        if context:
            turns = context.get("turn_count", 0)
            if turns > 3:
                interaction_score = min(1.0, turns / 10.0)
        
        # 加权总得分
        total = (self.config.weight_keywords * keyword_score +
                 self.config.weight_context * context_score +
                 self.config.weight_interaction * interaction_score)
        
        # 归一化并记录
        final_score = max(0.0, min(1.0, total))
        self.logger.info(f"Ambiguity score: {final_score:.3f} (kw={keyword_score:.2f}, ctx={context_score:.2f}, int={interaction_score:.2f})")
        return final_score


# 自测代码
if __name__ == "__main__":
    # 配置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 测试1：默认配置
    print("=== 测试默认简单关键词算法 ===")
    algo = SimpleKeywordAmbiguity()
    test_text = "他慢慢靠近，凝视着她的眼睛，微笑着悄悄话。"
    context = {"relationship": 0.8, "turn_count": 5}
    score = algo.calculate(test_text, context)
    print(f"暧昧得分: {score:.2f}")
    print(f"是否暧昧: {algo.is_ambiguity(score)}")
    
    # 测试2：热更新配置
    print("\n=== 测试配置热更新 ===")
    new_config = {
        "weight_keywords": 0.6,
        "keywords": ["靠近", "凝视", "脸红"],
        "threshold": 0.5
    }
    algo.config.update(new_config)
    score2 = algo.calculate(test_text, context)
    print(f"更新后得分: {score2:.2f}, 是否暧昧: {algo.is_ambiguity(score2)}")
    
    # 测试3：空文本
    print("\n=== 测试空文本 ===")
    score3 = algo.calculate("")
    print(f"空文本得分: {score3:.2f}")
    
    # 测试4：导出配置
    print("\n=== 当前配置 ===")
    print(json.dumps(algo.config.to_dict(), indent=2, ensure_ascii=False))
    
    # 测试5：基本接口（基类直接调用会报错）
    print("\n=== 测试基类未实现 ===")
    base = BaseAmbiguityAlgorithm()
    try:
        base.calculate("test")
    except NotImplementedError as e:
        print(f"捕获到异常: {e}")