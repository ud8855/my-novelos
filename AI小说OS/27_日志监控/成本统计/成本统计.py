"""成本统计模块 - CostTracker
所属层: 27_日志监控/成本统计
依赖: 配置系统(通过初始化参数传入), logging模块
被调用: 由模型调用管道或日志监听器调用，记录每次API调用成本
解决问题: 实时/累计统计模型使用费用，支持多模型、可配价格，提供查询接口，方便成本监控与预算控制
设计原则: 单例、可插拔、配置化、异常恢复、日志记录
"""
import logging
import threading
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

@dataclass
class ModelPricing:
    """模型定价配置"""
    prompt_price_per_1k: float = 0.0
    completion_price_per_1k: float = 0.0

class CostTracker:
    """
    成本统计器（线程安全单例）
    使用方式:
        tracker = CostTracker.get_instance()
        tracker.record_cost("gpt-4", prompt_tokens=1500, completion_tokens=800)
        print(tracker.get_total_cost())
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化成本统计器（不应直接调用，使用 get_instance()）
        :param config: 自定义配置字典，包含模型定价等信息，若未提供则使用默认值
        """
        self.logger = logging.getLogger("CostTracker")
        self._lock = threading.Lock()
        self._total_cost = 0.0
        self._record_count = 0
        # 默认模型定价（生产环境应从配置中心加载）
        self._pricing: Dict[str, ModelPricing] = {
            "gpt-3.5-turbo": ModelPricing(prompt_price_per_1k=0.0015, completion_price_per_1k=0.002),
            "gpt-4": ModelPricing(prompt_price_per_1k=0.03, completion_price_per_1k=0.06),
            "default": ModelPricing(prompt_price_per_1k=0.0, completion_price_per_1k=0.0)
        }
        # 可插拔开关，若配置中disable=True则此实例不记录成本
        self._enabled = True
        if config:
            self.configure(config)

    def configure(self, config: Dict[str, Any]) -> None:
        """
        根据配置更新参数，支持热更新定价和开关状态
        :param config: 配置字典，可能包含 'pricing', 'enabled' 等
        """
        if 'pricing' in config:
            for model, price_info in config['pricing'].items():
                if model in self._pricing:
                    self._pricing[model].prompt_price_per_1k = price_info.get('prompt_price_per_1k', 0.0)
                    self._pricing[model].completion_price_per_1k = price_info.get('completion_price_per_1k', 0.0)
                else:
                    self._pricing[model] = ModelPricing(**price_info)
            self.logger.info(f"定价配置已更新: {list(config['pricing'].keys())}")
        if 'enabled' in config:
            self._enabled = bool(config['enabled'])
            self.logger.info(f"成本统计开关: {'开启' if self._enabled else '关闭'}")

    @classmethod
    def get_instance(cls, config: Optional[Dict[str, Any]] = None) -> 'CostTracker':
        """获取单例实例，可选传入配置（首次调用生效）"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(config)
        return cls._instance

    def record_cost(self, model_name: str, prompt_tokens: int, completion_tokens: int,
                    metadata: Optional[Dict[str, Any]] = None) -> float:
        """
        记录一次调用的成本
        :param model_name: 模型标识
        :param prompt_tokens: 输入token数量
        :param completion_tokens: 输出token数量
        :param metadata: 附加信息（如请求ID等，暂存日志用）
        :return: 本次调用成本（美元），若未启用或异常返回0.0
        """
        if not self._enabled:
            return 0.0
        try:
            pricing = self._pricing.get(model_name, self._pricing.get("default"))
            if pricing is None:
                self.logger.warning(f"未找到模型 '{model_name}' 的定价，使用默认0费用")
                cost = 0.0
            else:
                cost = (prompt_tokens / 1000.0) * pricing.prompt_price_per_1k + \
                       (completion_tokens / 1000.0) * pricing.completion_price_per_1k

            with self._lock:
                self._total_cost += cost
                self._record_count += 1

            self.logger.debug(
                f"模型: {model_name}, 输入tokens: {prompt_tokens}, 输出tokens: {completion_tokens}, "
                f"成本: ${cost:.6f}, 累计成本: ${self._total_cost:.6f}, 记录数: {self._record_count}"
            )
            if metadata:
                self.logger.debug(f"关联元数据: {metadata}")
            return cost
        except Exception as e:
            self.logger.error(f"记录成本失败: {e}", exc_info=True)
            return 0.0

    def get_total_cost(self) -> float:
        """返回累计成本（美元）"""
        return self._total_cost

    def get_record_count(self) -> int:
        """返回已记录调用次数"""
        return self._record_count

    def reset(self) -> None:
        """重置统计"""
        with self._lock:
            self._total_cost = 0.0
            self._record_count = 0
        self.logger.info("成本统计已重置")

    def get_enabled(self) -> bool:
        return self._enabled

# 自测代码
if __name__ == "__main__":
    # 测试配置
    test_config = {
        'pricing': {
            'my-gpt': {'prompt_price_per_1k': 0.01, 'completion_price_per_1k': 0.02}
        },
        'enabled': True
    }
    # 初始化单例
    tracker = CostTracker.get_instance(test_config)
    # 设置日志级别以观察输出
    logging.basicConfig(level=logging.DEBUG)
    print("=== 成本统计自测 ===")
    # 模拟记录
    cost1 = tracker.record_cost("my-gpt", prompt_tokens=2000, completion_tokens=1000, metadata={"req_id": "001"})
    cost2 = tracker.record_cost("gpt-4", prompt_tokens=500, completion_tokens=500)
    cost3 = tracker.record_cost("unknown-model", prompt_tokens=100, completion_tokens=100)
    print(f"本次成本: {cost1}, {cost2}, {cost3}")
    print(f"总成本: {tracker.get_total_cost():.6f} 美元")
    print(f"调用次数: {tracker.get_record_count()}")
    # 重置
    tracker.reset()
    print(f"重置后总成本: {tracker.get_total_cost():.6f}")