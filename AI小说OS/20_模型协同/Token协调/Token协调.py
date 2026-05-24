from __future__ import annotations

import logging
import json
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

# ------------------------------
# 配置数据类
# ------------------------------

@dataclass
class TokenBudgetConfig:
    """
    Token预算配置，支持从字典构建，便于热更新
    """
    total_token_limit: int = 1000000       # 全局总Token上限
    model_limits: Dict[str, int] = field(default_factory=lambda: {
        "gpt-3.5-turbo": 4096,
        "gpt-4": 8192,
        "claude-2": 100000,
    })
    daily_limit: Optional[int] = None      # 每日总Token限制，None表示不限
    hourly_limit: Optional[int] = None     # 每小时总Token限制
    burst_limit: int = 10000               # 短期突发限制（秒级窗口）
    allocation_strategy: str = "proportional"  # 分配策略: proportional, equal, priority
    log_level: str = "INFO"
    enable_metrics: bool = True

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "TokenBudgetConfig":
        """从字典构造配置，未知键忽略，安全插拔"""
        valid_keys = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in config_dict.items() if k in valid_keys}
        return cls(**filtered)

import dataclasses

# ------------------------------
# Token协调器主类
# ------------------------------

class TokenCoordinator:
    """
    负责多模型Token预算的管理、分配、消耗追踪与限制。
    所有模型调用都必须经过此协调器检查Token可用性。

    依赖：配置模块、日志组件（自包含）
    被调用：由模型调用代理（如ModelDispatcher）在每次请求前调用consume_tokens申请Token，
            若不足则拒绝或排队。
    解决：避免单个模型或全局超出Token配额，保证资源公平分配。

    可插拔：可通过子类化或改变配置中的allocation_strategy替换分配逻辑。
    """

    def __init__(self, config: Optional[TokenBudgetConfig] = None, logger: Optional[logging.Logger] = None):
        """
        初始化协调器

        Args:
            config: TokenBudgetConfig实例，若为None则使用默认配置
            logger: 外部日志记录器，若为None则内部创建
        """
        self.config = config or TokenBudgetConfig()
        self.logger = logger or self._setup_logger()

        # 运行状态
        self._token_usage: Dict[str, int] = {}  # 每个模型累计已用Token数
        self._global_usage: int = 0
        self._daily_start_time = time.time()
        self._hourly_start_time = time.time()
        self._burst_window_tokens: int = 0
        self._burst_window_start: float = time.time()

        self.logger.info(f"TokenCoordinator initialized with strategy={self.config.allocation_strategy}")

    def _setup_logger(self) -> logging.Logger:
        """创建内部日志记录器，保持模块独立"""
        logger = logging.getLogger(f"TokenCoordinator_{id(self)}")
        logger.setLevel(getattr(logging, self.config.log_level, logging.INFO))
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    # -------------------- 核心Token管理API --------------------

    def allocate_token_budget(self, model_name: str, requested: int, priority: int = 0) -> int:
        """
        为特定模型分配Token预算（一种配额），不实际扣除，用于规划。
        根据配置中的allocation_strategy分配。

        Args:
            model_name: 模型名称
            requested: 请求分配的Token数量
            priority: 请求优先级，数值越大优先级越高（仅priority策略有效）

        Returns:
            实际分配的Token数量（可能小于请求值）
        """
        strategy = self.config.allocation_strategy
        self.logger.debug(f"Budget allocation for {model_name}: requested={requested}, priority={priority}, strategy={strategy}")

        # 简化策略示例，真实实现可扩展策略模式
        if strategy == "proportional":
            # 按照配置比例分配，此处简单返回请求值，假设足够
            allocated = requested
        elif strategy == "equal":
            # 平等分配，所有模型平均总限额？暂简化
            allocated = requested
        elif strategy == "priority":
            # 优先级高给更多，这里简单返回请求值
            allocated = requested
        else:
            allocated = requested

        self.logger.info(f"Allocated {allocated} tokens to {model_name} (strategy={strategy})")
        return allocated

    def check_availability(self, model_name: str, tokens: int) -> bool:
        """
        检查指定模型当前是否可以消耗给定数量的Token。
        检查：全局限制、模型限制、日/小时限制、突发限制。

        Args:
            model_name: 模型名称
            tokens: 需要消耗的Token数量

        Returns:
            True表示可用，False表示不可用
        """
        # 全局限制检查
        if self._global_usage + tokens > self.config.total_token_limit:
            self.logger.warning(f"Global token limit would be exceeded: current={self._global_usage}, tokens={tokens}, limit={self.config.total_token_limit}")
            return False

        # 模型限制检查
        model_limit = self.config.model_limits.get(model_name, self.config.total_token_limit)
        current_model_usage = self._token_usage.get(model_name, 0)
        if current_model_usage + tokens > model_limit:
            self.logger.warning(f"Model {model_name} limit would be exceeded: current={current_model_usage}, tokens={tokens}, limit={model_limit}")
            return False

        # 日限制检查
        if self.config.daily_limit is not None:
            self._refresh_daily_window()
            if self._global_usage + tokens > self.config.daily_limit:
                self.logger.warning(f"Daily token limit would be exceeded")
                return False

        # 小时限制检查
        if self.config.hourly_limit is not None:
            self._refresh_hourly_window()
            if self._global_usage + tokens > self.config.hourly_limit:
                self.logger.warning(f"Hourly token limit would be exceeded")
                return False

        # 突发限制检查（短窗口）
        self._refresh_burst_window()
        if self._burst_window_tokens + tokens > self.config.burst_limit:
            self.logger.warning(f"Burst token limit would be exceeded")
            return False

        return True

    def consume_tokens(self, model_name: str, tokens: int) -> bool:
        """
        实际消耗Token，先检查可用性，若可用则扣除并记录。

        Args:
            model_name: 模型名称
            tokens: 消耗的Token数量

        Returns:
            True消耗成功，False失败（资源不足）
        """
        if not self.check_availability(model_name, tokens):
            self.logger.error(f"Token consumption denied for {model_name}: {tokens} tokens")
            return False

        # 更新内部状态
        self._global_usage += tokens
        self._token_usage[model_name] = self._token_usage.get(model_name, 0) + tokens
        self._burst_window_tokens += tokens

        self.logger.info(f"Consumed {tokens} tokens for {model_name}, global usage={self._global_usage}")
        if self.config.enable_metrics:
            self._record_metrics(model_name, tokens)
        return True

    def reset_limits(self, preserve_usage: bool = False):
        """
        重置所有限制窗口计数器（如日清、时清），但不修改已配置的限制值。
        若preserve_usage为True，则保留累计使用量（不建议）。

        Args:
            preserve_usage: 是否保留累计使用量
        """
        if not preserve_usage:
            self._global_usage = 0
            self._token_usage.clear()
            self.logger.info("All token usage counters have been reset.")
        # 重置窗口时间
        now = time.time()
        self._daily_start_time = now
        self._hourly_start_time = now
        self._burst_window_start = now
        self._burst_window_tokens = 0
        self.logger.info("All time windows have been reset.")

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        获取当前Token使用统计信息，用于监控或调试。

        Returns:
            包含全局和各模型使用量的字典
        """
        return {
            "global_usage": self._global_usage,
            "per_model_usage": dict(self._token_usage),
            "burst_window_tokens": self._burst_window_tokens,
            "daily_start": self._daily_start_time,
            "hourly_start": self._hourly_start_time,
        }

    # -------------------- 内部辅助方法 --------------------

    def _refresh_daily_window(self):
        """如果超过24小时，重置每日窗口"""
        now = time.time()
        if now - self._daily_start_time >= 86400:
            self._global_usage = 0  # 每日重置全局使用量
            self._daily_start_time = now
            self.logger.info("Daily token window reset.")

    def _refresh_hourly_window(self):
        """如果超过1小时，重置每小时窗口"""
        now = time.time()
        if now - self._hourly_start_time >= 3600:
            self._global_usage = 0  # 也可仅重置小时计数器，这里简化全局重置
            self._hourly_start_time = now
            self.logger.info("Hourly token window reset.")

    def _refresh_burst_window(self):
        """如果超过1秒，重置突发窗口计数器"""
        now = time.time()
        if now - self._burst_window_start >= 1.0:
            self._burst_window_tokens = 0
            self._burst_window_start = now

    def _record_metrics(self, model_name: str, tokens: int):
        """预留的度量记录点，可扩展为发送指标到监控系统"""
        self.logger.debug(f"Metrics: model={model_name}, tokens={tokens}, global_usage={self._global_usage}")

    # -------------------- 配置热更新 --------------------

    def update_config(self, new_config: TokenBudgetConfig):
        """运行时更新配置，保留当前使用量状态"""
        self.config = new_config
        self.logger.setLevel(getattr(logging, self.config.log_level, logging.INFO))
        self.logger.info("TokenCoordinator configuration updated.")

# ------------------------------ 自测入口 ------------------------------
if __name__ == "__main__":
    # 简单自测：演示Token协调器的基本用法
    print("=== TokenCoordinator Self-Test ===")

    # 使用默认配置
    coordinator = TokenCoordinator()
    print("Default config loaded.")

    # 测试Token消耗
    model = "gpt-3.5-turbo"
    tokens_needed = 100

    print(f"\nChecking availability for {model} with {tokens_needed} tokens...")
    available = coordinator.check_availability(model, tokens_needed)
    print(f"Available: {available}")

    if available:
        success = coordinator.consume_tokens(model, tokens_needed)
        print(f"Consumed: {success}