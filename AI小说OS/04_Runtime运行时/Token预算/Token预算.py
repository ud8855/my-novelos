"""
Token预算模块
所属层: 04_Runtime运行时
依赖: 配置系统（通过配置字典传递）
被调用: 模型调用器、编排器，用于控制API调用成本
解决问题: 追踪和限制 token 使用量，防止预算超支，支持可插拔的预算策略
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass

# ---------- 配置默认值 ----------
DEFAULT_BUDGET = 1000000      # 默认总预算（token数）
DEFAULT_WARNING = 0.8         # 使用量达到80%时警告
DEFAULT_CRITICAL = 0.95       # 使用量达到95%时禁止调用

# ---------- 日志配置 ----------
logger = logging.getLogger("TokenBudget")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# ---------- 数据类 ----------
@dataclass
class BudgetStatus:
    total: int
    used: int
    remaining: int
    percentage_used: float
    warning: bool
    critical: bool

# ---------- 抽象预算管理器 ----------
class TokenBudgetManager(ABC):
    """
    可插拔的Token预算管理器基类。
    所有具体的预算实现必须继承此类并实现抽象方法。
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._init_from_config()
        logger.info("Token预算管理器初始化完成，配置: %s", config)

    def _init_from_config(self):
        """从配置字典提取参数，子类可覆盖"""
        self.total_budget = self.config.get('total_budget', DEFAULT_BUDGET)
        self.warning_threshold = self.config.get('warning_threshold', DEFAULT_WARNING)
        self.critical_threshold = self.config.get('critical_threshold', DEFAULT_CRITICAL)

    @abstractmethod
    def get_used_tokens(self) -> int:
        """返回已使用的 token 数量"""
        pass

    @abstractmethod
    def record_usage(self, tokens: int, context: Optional[str] = None):
        """
        记录一次 token 使用。
        :param tokens: 本次使用的 token 数量
        :param context: 调用上下文（如请求ID或步骤名），用于日志
        """
        pass

    def check_budget(self, required_tokens: int) -> bool:
        """
        检查剩余预算是否足够执行所需 tokens 的操作。
        返回 True 表示允许，False 表示预算不足。
        同时触发警告或严重级别日志。
        """
        used = self.get_used_tokens()
        remaining = self.total_budget - used
        if required_tokens > remaining:
            logger.critical("[CRITICAL] Token 预算不足！需要 %d tokens，剩余 %d tokens", required_tokens, remaining)
            return False

        new_used = used + required_tokens
        new_percent = new_used / self.total_budget
        if new_percent >= self.critical_threshold:
            logger.warning("[WARNING] Token 使用量即将达到严重阈值 (%.1f%%)", new_percent * 100)
        elif new_percent >= self.warning_threshold:
            logger.info("[INFO] Token 使用量已达到警告阈值 (%.1f%%)", new_percent * 100)

        return True

    def get_budget_status(self) -> BudgetStatus:
        """获取当前预算状态快照"""
        used = self.get_used_tokens()
        remaining = self.total_budget - used
        percentage = used / self.total_budget
        warning = percentage >= self.warning_threshold
        critical = percentage >= self.critical_threshold
        return BudgetStatus(
            total=self.total_budget,
            used=used,
            remaining=remaining,
            percentage_used=percentage,
            warning=warning,
            critical=critical
        )

    def reset_budget(self, new_total: Optional[int] = None):
        """重置总预算，可选新预算值。子类实现具体逻辑。"""
        raise NotImplementedError("重置功能未实现")


# ---------- 简单的内存预算管理器（默认实现） ----------
class SimpleTokenBudgetManager(TokenBudgetManager):
    """
    基于内存的 Token 预算管理器。
    记录累计使用量，适合单进程或测试场景。
    """

    def __init__(self, config: Dict[str, Any]):
        self._used_tokens = 0
        super().__init__(config)
        logger.debug("SimpleTokenBudgetManager 实例已创建")

    def get_used_tokens(self) -> int:
        return self._used_tokens

    def record_usage(self, tokens: int, context: Optional[str] = None):
        """
        记录使用量，并写入日志。
        """
        self._used_tokens += tokens
        ctx_str = f" [Context: {context}]" if context else ""
        logger.info("Token 使用记录: +%d tokens (累计: %d/%d)%s",
                    tokens, self._used_tokens, self.total_budget, ctx_str)

    def reset_budget(self, new_total: Optional[int] = None):
        """
        重置使用计数和/或总预算。
        """
        if new_total is not None:
            self.total_budget = new_total
            logger.info("总预算已更新为 %d", new_total)
        self._used_tokens = 0
        logger.info("使用计数已归零")


# ---------- 工厂函数 ----------
def create_token_budget_manager(mode: str = "simple", config: Optional[Dict[str, Any]] = None) -> TokenBudgetManager:
    """
    根据模式创建预算管理器实例。支持扩展新的预算策略。
    :param mode: 策略名称，'simple' 为默认内存实现
    :param config: 配置字典，若为None则使用默认空字典
    :return: TokenBudgetManager 实例
    """
    config = config or {}
    if mode == "simple":
        return SimpleTokenBudgetManager(config)
    else:
        raise ValueError(f"未知的 Token 预算管理模式: {mode}")


# ---------- 自测 ----------
if __name__ == "__main__":
    print("=== Token 预算模块自测 ===")
    # 测试配置
    test_config = {
        "total_budget": 10000,
        "warning_threshold": 0.7,
        "critical_threshold": 0.9,
    }
    manager = create_token_budget_manager("simple", test_config)

    # 检查预算
    print("初始状态:", manager.get_budget_status())

    # 模拟正常使用
    manager.record_usage(2000, "第一章大纲生成")
    print("使用2000后:", manager.get_budget_status())

    # 达到警告
    manager.record_usage(5000, "详细情节生成")  # 累计7000，70% 触发警告阈值
    print("使用5000后:", manager.get_budget_status())

    # 检查预算是否允许
    print("请求3000 tokens, 允许?", manager.check_budget(3000))  # 累计10000，临界，可能警告

    # 模拟超预算请求
    print("请求1 token, 允许?", manager.check_budget(1))  # 此时已用10000，剩余0

    # 重置
    manager.reset_budget()
    print("重置后状态:", manager.get_budget_status())

    # 工厂函数错误测试
    try:
        create_token_budget_manager("unknown")
    except ValueError as e:
        print("已捕获预期错误:", e)