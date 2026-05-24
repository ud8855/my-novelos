"""
成本控制模块 - 位于 NovelOS 20_模型协同 层
职责：监控与分析模型调用成本，实施预算控制、策略优化与告警
依赖：配置管理模块（假设位于 00_系统配置/），日志模块（假设位于 01_日志系统/）
被调用者：模型协同编排器、任务调度器、运行时监控
可插拔设计：通过依赖注入配置、日志记录器，策略可扩展
"""

import logging
from typing import Dict, Any, Optional, Callable

# 默认日志记录器，若未注入则使用根日志器
_default_logger = logging.getLogger("CostControl")

class CostControlConfig:
    """成本控制配置容器，支持从字典或文件加载"""
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        # 总预算（单位：美元）
        self.total_budget: float = config_dict.get("total_budget", 10.0) if config_dict else 10.0
        # 已使用预算
        self.used_budget: float = config_dict.get("used_budget", 0.0) if config_dict else 0.0
        # 模型单价表（每1K tokens的价格）
        self.model_prices: Dict[str, float] = config_dict.get("model_prices", {
            "gpt-3.5-turbo": 0.002,
            "gpt-4": 0.03,
            "claude-2": 0.008
        }) if config_dict else {
            "gpt-3.5-turbo": 0.002,
            "gpt-4": 0.03,
            "claude-2": 0.008
        }
        # 告警阈值（已使用预算占比，超过则触发告警）
        self.alert_threshold: float = config_dict.get("alert_threshold", 0.8) if config_dict else 0.8
        # 是否启用严格模式（超预算时直接拒绝调用）
        self.strict_mode: bool = config_dict.get("strict_mode", False) if config_dict else False
        # 成本记录持久化路径（可选）
        self.record_path: Optional[str] = config_dict.get("record_path") if config_dict else None

    def update(self, **kwargs):
        """动态更新配置项"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(f"无效的配置项: {key}")


class CostController:
    """成本控制器，提供预算检查、成本累计、模型选择建议等功能"""

    def __init__(self, config: CostControlConfig,
                 logger: Optional[logging.Logger] = None):
        """
        :param config: 成本控制配置实例
        :param logger: 日志记录器，若不提供则使用默认控制台日志
        """
        self.config = config
        self.logger = logger or _default_logger
        if not self.logger.handlers:  # 确保默认日志器有处理器
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            self.logger.addHandler(h)
            self.logger.setLevel(logging.DEBUG)
        self._used_tokens: Dict[str, int] = {}  # 记录每个模型使用的token数

    def estimate_cost(self, model_name: str, token_count: int) -> float:
        """估算指定模型处理给定token数的费用"""
        price = self.config.model_prices.get(model_name)
        if price is None:
            self.logger.warning(f"未知模型 {model_name}，无法估算成本，假定单价为0.01")
            price = 0.01
        cost = (token_count / 1000) * price
        self.logger.debug(f"估算成本: 模型={model_name}, tokens={token_count}, 费用=${cost:.4f}")
        return cost

    def check_budget(self, estimated_cost: float) -> bool:
        """检查当前预算是否足够，返回 True 表示允许调用"""
        remaining = self.config.total_budget - self.config.used_budget
        if estimated_cost > remaining:
            self.logger.warning(f"预算不足！预估费用 ${estimated_cost:.4f} 超出剩余预算 ${remaining:.4f}")
            if self.config.strict_mode:
                raise BudgetExceededError(f"严格模式：预算超限，调用被拒绝。剩余 {remaining}，需要 {estimated_cost}")
            return False
        return True

    def record_usage(self, model_name: str, token_count: int):
        """记录一次模型调用，更新已用预算和token计数"""
        cost = self.estimate_cost(model_name, token_count)
        if not self.check_budget(cost):
            # 非严格模式下仍然允许记录但会触发告警
            self.logger.warning("预算不足，仍然记录使用量（非严格模式）")
        # 更新计数
        self._used_tokens[model_name] = self._used_tokens.get(model_name, 0) + token_count
        self.config.used_budget += cost
        self.logger.info(f"记录使用: 模型={model_name}, tokens={token_count}, 费用=${cost:.4f}, 累计=${self.config.used_budget:.4f}")
        # 检查告警阈值
        if self.config.used_budget / self.config.total_budget >= self.config.alert_threshold:
            self.logger.warning(f"预算使用率已达 {self.config.used_budget/self.config.total_budget:.1%}，触发告警")
        # 可选持久化
        if self.config.record_path:
            self._persist_record()

    def get_cheapest_model(self, eligible_models: list) -> str:
        """从候选模型列表中选择单价最低的模型"""
        if not eligible_models:
            raise ValueError("候选模型列表不能为空")
        prices = {m: self.config.model_prices.get(m, float('inf')) for m in eligible_models}
        cheapest = min(prices, key=prices.get)
        self.logger.debug(f"从 {eligible_models} 中选择最便宜模型: {cheapest} (单价 {prices[cheapest]})")
        return cheapest

    def reset_budget(self, new_total: Optional[float] = None):
        """重置预算计数器，可选重新设定总额"""
        if new_total is not None:
            self.config.total_budget = new_total
        self.config.used_budget = 0.0
        self._used_tokens.clear()
        self.logger.info(f"预算已重置，总额为 {self.config.total_budget}")

    def _persist_record(self):
        """将当前使用记录持久化到文件（占位实现）"""
        # 实际应写入文件或数据库，此处仅示意
        self.logger.debug(f"持久化记录（占位）: 路径 {self.config.record_path}")

    def inject_strategy(self, strategy_func: Callable, strategy_name: str):
        """
        可插拔策略注入：允许动态替换或添加自定义成本控制策略
        """
        self.logger.info(f"注入策略: {strategy_name}")
        setattr(self, strategy_name, strategy_func)


class BudgetExceededError(Exception):
    """预算超限异常"""
    pass


# --------------------- 自测代码 ---------------------
if __name__ == "__main__":
    print("开始成本控制模块自测...")
    # 创建测试配置
    test_config = CostControlConfig({
        "total_budget": 1.0,
        "used_budget": 0.0,
        "strict_mode": False,
        "record_path": "cost_records.json"
    })

    # 创建成本控制器
    cc = CostController(test_config)
    print("预算检查通过" if cc.check_budget(0.5) else "预算检查未通过（预期通过）")
    
    # 模拟记录使用
    cc.record_usage("gpt-3.5-turbo", 5000)  # 使用5K tokens
    cc.record_usage("gpt-4", 1000)          # 使用1K tokens
    print(f"当前已用预算: ${cc.config.used_budget:.4f}")

    # 测试最便宜模型选择
    models = ["gpt-3.5-turbo", "gpt-4", "claude-2"]
    cheapest = cc.get_cheapest_model(models)
    print(f"最便宜模型: {cheapest}")

    # 测试预算超限情况
    cc.config.total_budget = 0.01  # 设置极低预算
    try:
        cc.record_usage("gpt-4", 10000)  # 将触发预算不足
    except BudgetExceededError:
        print("捕获到预算超限异常（预期）")
    else:
        print("预算超限未被拒绝（非严格模式）")

    # 测试动态配置更新
    cc.config.update(alert_threshold=0.5)
    print(f"告警阈值已更新为: {cc.config.alert_threshold}")

    # 测试策略注入
    def custom_budget_check(cost):
        return cost < 100  # 总是允许小于100
    cc.inject_strategy(custom_budget_check, "check_budget")
    print("自定义预算检查注入成功")
    
    print("自测结束。")