"""
爽感测试模块
用于评估文本片段是否具有网络小说中的“爽感”特质。
提供可插拔的评分策略，支持配置化、日志记录。
"""

import logging
from typing import Any, Dict, List, Optional

# 默认配置
DEFAULT_CONFIG = {
    "log_level": "INFO",
    "score_threshold": 0.7,
    "strategies": ["basic"]  # 可扩展策略列表
}

class ShuangGanTester:
    """
    爽感测试器
    根据配置加载评分策略，对待测文本进行多策略综合评分。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config if config is not None else DEFAULT_CONFIG.copy()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup_logger()
        self.strategies: List[BaseShuangGanStrategy] = []
        self._load_strategies()
    
    def _setup_logger(self):
        """配置日志"""
        level = getattr(logging, self.config.get("log_level", "INFO").upper(), logging.INFO)
        self.logger.setLevel(level)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _load_strategies(self):
        """根据配置动态加载评分策略（可插拔）"""
        strategy_names = self.config.get("strategies", [])
        for name in strategy_names:
            # TODO: 实现策略注册与动态加载机制，目前简单映射
            if name == "basic":
                strategy = BasicShuangGanStrategy()
                self.strategies.append(strategy)
                self.logger.info(f"Loaded strategy: {name}")
            else:
                self.logger.warning(f"Unknown strategy: {name}, skip.")
    
    def register_strategy(self, strategy: 'BaseShuangGanStrategy'):
        """热插拔：动态添加策略"""
        self.strategies.append(strategy)
        self.logger.info(f"Registered new strategy: {strategy.__class__.__name__}")
    
    def unregister_strategy(self, strategy_name: str):
        """移除策略"""
        self.strategies = [s for s in self.strategies if s.__class__.__name__ != strategy_name]
        self.logger.info(f"Unregistered strategy: {strategy_name}")
    
    def test(self, text: str) -> Dict[str, Any]:
        """
        测试文本爽感指数
        :param text: 待测试文本
        :return: 包含总分、是否通过、各策略详情的字典
        """
        self.logger.debug(f"Testing text of length {len(text)}")
        if not self.strategies:
            self.logger.error("No strategy loaded, returning default result")
            return {"score": 0.0, "passed": False, "detail": []}
        
        details = []
        for strategy in self.strategies:
            try:
                detail = strategy.evaluate(text)
                details.append(detail)
                self.logger.debug(f"Strategy {detail['strategy']} score: {detail['score']}")
            except Exception as e:
                self.logger.error(f"Strategy {strategy.__class__.__name__} failed: {e}")
                details.append({"strategy": strategy.__class__.__name__, "score": 0.0, "error": str(e)})
        
        aggregate_score = sum(d["score"] for d in details) / len(details)
        passed = aggregate_score >= self.config.get("score_threshold", 0.7)
        return {
            "score": aggregate_score,
            "passed": passed,
            "detail": details
        }

class BaseShuangGanStrategy:
    """爽感评分策略抽象基类，所有策略需实现此接口"""
    def evaluate(self, text: str) -> Dict[str, Any]:
        """
        评估文本爽感
        :return: 字典至少包含 'strategy' 和 'score' 字段
        """
        raise NotImplementedError("Subclasses must implement evaluate()")

class BasicShuangGanStrategy(BaseShuangGanStrategy):
    """基础爽感策略：基于关键词和简单规则"""
    def evaluate(self, text: str) -> Dict[str, Any]:
        # TODO: 实现基于关键词（如“打脸”、“逆袭”、“系统”、“震惊”）的简单评分
        # 占位示例
        return {
            "strategy": "basic",
            "score": 0.5,
            "info": "Basic strategy not implemented yet"
        }

# 自测代码块
if __name__ == "__main__":
    # 配置化测试
    test_config = {
        "log_level": "DEBUG",
        "score_threshold": 0.6,
        "strategies": ["basic"]
    }
    tester = ShuangGanTester(config=test_config)
    sample_text = "小明被欺负后，意外获得系统，从此逆袭，打脸众人。"
    result = tester.test(sample_text)
    print("爽感测试结果：", result)
    # 测试动态添加策略
    class DummyStrategy(BaseShuangGanStrategy):
        def evaluate(self, text):
            return {"strategy": "dummy", "score": 0.9}
    tester.register_strategy(DummyStrategy())
    result2 = tester.test(sample_text)
    print("添加策略后结果：", result2)