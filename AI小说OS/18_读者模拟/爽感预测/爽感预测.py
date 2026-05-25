from __future__ import annotations

import logging
import json
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

# ---------- 默认配置 ----------
DEFAULT_CONFIG = {
    "log_level": "INFO",
    "predictor_class": "KeywordPleasurePredictor",
    "keyword_weights": {
        "爽": 0.2,
        "逆袭": 0.3,
        "打脸": 0.25,
        "碾压": 0.15,
        "震惊": 0.1
    }
}

# ---------- 抽象基类：可插拔实现 ----------
class BasePleasurePredictor(ABC):
    """爽感预测器抽象接口，所有具体实现必须继承。"""

    def __init__(self, config: Dict[str, Any] = None, logger: logging.Logger = None):
        self.config = config or {}
        self.logger = logger or logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def predict(self, text: str) -> float:
        """
        对给定文本预测爽感分数。

        Args:
            text: 待分析的小说片段。

        Returns:
            爽感分数（0-10），数值越大代表越爽。
        """
        raise NotImplementedError


# ---------- 基于关键词的简单实现 ----------
class KeywordPleasurePredictor(BasePleasurePredictor):
    """通过关键词加权打分的爽感预测器（骨架示例）。"""

    def __init__(self, config: Dict[str, Any] = None, logger: logging.Logger = None):
        super().__init__(config, logger)
        # 从配置中提取关键词权重
        self.keyword_weights: Dict[str, float] = self.config.get("keyword_weights", {})
        self.logger.info(f"KeywordPredictor 初始化完毕，关键词数量: {len(self.keyword_weights)}")

    def predict(self, text: str) -> float:
        """
        基于关键词出现次数计算初始爽感分数。
        分数 = sum(关键词权重 * 出现次数)，上限限制为10。
        """
        if not text:
            self.logger.warning("输入文本为空，返回0分")
            return 0.0

        score = 0.0
        for keyword, weight in self.keyword_weights.items():
            count = text.count(keyword)
            if count > 0:
                self.logger.debug(f"关键词 '{keyword}' 出现 {count} 次，权重 {weight}")
            score += count * weight

        # 将分数映射到0-10区间（简单截断）
        final_score = min(score, 10.0)
        self.logger.info(f"爽感预测结果: {final_score:.2f} (原始: {score:.2f})")
        return final_score


# ---------- 爽感预测统一门面 ----------
class PleasurePredictor:
    """
    爽感预测模块的统一入口。
    通过配置动态加载不同的预测实现，支持热插拔。
    """

    def __init__(self, config: Dict[str, Any] = None, logger: logging.Logger = None):
        self.config = config or DEFAULT_CONFIG.copy()
        self.logger = logger or logging.getLogger("PleasurePredictor")

        # 日志等级设置
        log_level = self.config.get("log_level", "INFO").upper()
        logging.basicConfig(level=log_level)
        self.logger.setLevel(log_level)

        # 动态加载预测器实例
        predictor_class_name = self.config.get("predictor_class", "KeywordPleasurePredictor")
        predictor_cls = globals().get(predictor_class_name)
        if predictor_cls is None:
            raise ImportError(f"未找到预测器类: {predictor_class_name}")
        if not issubclass(predictor_cls, BasePleasurePredictor):
            raise TypeError(f"预测器 {predictor_class_name} 必须继承 BasePleasurePredictor")

        self._predictor: BasePleasurePredictor = predictor_cls(self.config, self.logger)
        self.logger.info(f"爽感预测模块就绪，使用 {predictor_class_name}")

    def predict(self, text: str) -> float:
        """委托给底层预测器，并确保结果合法性。"""
        score = self._predictor.predict(text)
        # 全局后处理：确保分数在0-10之间
        if score < 0.0:
            self.logger.debug(f"预测分数 {score} < 0，修正为 0")
            score = 0.0
        elif score > 10.0:
            self.logger.debug(f"预测分数 {score} > 10，修正为 10")
            score = 10.0
        return score

    def reload_config(self, new_config: Dict[str, Any]):
        """热更新配置并重新初始化预测器。"""
        self.config.update(new_config)
        # 重新创建预测器实例
        old_class = self._predictor.__class__.__name__
        new_class_name = self.config.get("predictor_class", old_class)
        if new_class_name != old_class:
            self.logger.info(f"预测器切换：{old_class} -> {new_class_name}")
            predictor_cls = globals().get(new_class_name)
            if predictor_cls is None:
                raise ImportError(f"热更新失败，未找到类 {new_class_name}")
            self._predictor = predictor_cls(self.config, self.logger)
        else:
            # 同类型预测器，只更新参数
            self._predictor.config = self.config
            if hasattr(self._predictor, "keyword_weights"):
                self._predictor.keyword_weights = self.config.get("keyword_weights", {})
            self.logger.info("预测器配置已热更新")


# ---------- 自测 ----------
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("=== 爽感预测模块自测 ===")
    # 默认配置
    predictor = PleasurePredictor()

    # 测试用例
    test_texts = [
        "五年后，落魄少年携逆天传承回归，打脸所有看不起他的人，全场震惊！",
        "今天天气真好，阳光明媚。",
        "主角被反复碾压，毫无还手之力，太虐了。",
        "爽！终于获得了神器，逆袭开始！"
    ]

    for idx, txt in enumerate(test_texts, 1):
        print(f"\n测试{idx}: {txt}")
        score = predictor.predict(txt)
        print(f"  爽感分数: {score:.2f}")

    print("\n=== 热更新测试 ===")
    # 修改关键词权重
    new_config = {
        "keyword_weights": {
            "爽": 0.5,
            "无敌": 0.4,
            "秒杀": 0.3
        }
    }
    predictor.reload_config(new_config)
    for txt in test_texts:
        score = predictor.predict(txt)
        print(f"  文本: {txt[:20]}... -> 分数: {score:.2f}")