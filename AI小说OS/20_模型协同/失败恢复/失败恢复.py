"""
失败恢复模块 (Failure Recovery Module)
所在层级：20_模型协同
依赖：Python标准库 (logging, time, traceback)
被谁调用：模型协同调度器、模型路由器等，用于包裹模型调用以增加容错能力
解决问题：当模型调用失败时（网络异常、超时、服务不可用等），自动重试、降级或记录错误，避免整个流程中断
设计原则：可插拔（通过配置注入）、日志可追踪、配置化、热插拔（运行时替换策略）
"""

import logging
import time
import traceback
from typing import Callable, Any, Optional, TypeVar, Dict, Union

# 全局Logger，外部可通过 set_logger() 替换
_logger = logging.getLogger("ModelFailureRecovery")
_logger.addHandler(logging.NullHandler())  # 默认无输出

def set_logger(logger: logging.Logger) -> None:
    """设置模块专用日志记录器（可插拔）"""
    global _logger
    _logger = logger

# 类型变量，用于保持函数签名
F = TypeVar('F', bound=Callable[..., Any])

class FailureRecoveryConfig:
    """
    失败恢复配置
    所有参数均可通过字典动态传入，支持运行时修改（热更新）
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # 默认配置
        self.max_retries: int = 3
        self.base_delay: float = 1.0           # 基础等待时间（秒）
        self.backoff_factor: float = 2.0        # 退避因子，延长等待
        self.jitter: bool = True                # 是否加入随机抖动
        self.fallback_enabled: bool = False     # 是否启用降级
        self.fallback_func: Optional[Callable[..., Any]] = None  # 降级函数，需要外部注入
        self.log_failures: bool = True          # 是否记录失败详情
        self.retry_on_exceptions: tuple = (Exception,)  # 哪些异常触发重试

        if config:
            self.update(config)

    def update(self, config: Dict[str, Any]) -> None:
        """根据字典更新配置，允许动态调整"""
        for key, value in config.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                _logger.warning(f"Unknown config key: {key}, ignored.")

class ModelFailureRecovery:
    """
    模型调用失败恢复器
    用法：
        recovery = ModelFailureRecovery(config)
        result = recovery.execute(func, arg1, arg2)
        或作为装饰器：
        @recovery.recover
        def my_func(...): ...
    """
    def __init__(self, config: Optional[FailureRecoveryConfig] = None):
        self.config = config or FailureRecoveryConfig()
        self.logger = _logger or logging.getLogger(__name__)
        self.logger.debug("ModelFailureRecovery initialized with config: %s", self.config.__dict__)

    def execute(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        执行函数并带重试和降级恢复
        Args:
            func: 要执行的函数（通常为模型调用）
            *args, **kwargs: 传递给 func 的参数
        Returns:
            正常执行或降级返回的结果
        Raises:
            当所有重试次数耗尽且无降级时，抛出最后一次异常
        """
        retries = 0
        delay = self.config.base_delay
        last_exception = None

        while retries <= self.config.max_retries:
            try:
                return func(*args, **kwargs)
            except self.config.retry_on_exceptions as e:
                last_exception = e
                retries += 1
                if retries > self.config.max_retries:
                    # 重试次数耗尽
                    if self.config.fallback_enabled and self.config.fallback_func:
                        self.logger.warning(
                            f"Max retries exceeded, executing fallback. Last error: {e}"
                        )
                        try:
                            return self.config.fallback_func(*args, **kwargs)
                        except Exception as fb_e:
                            self.logger.error(
                                f"Fallback also failed: {fb_e}"
                            )
                            raise  # 降级也失败，抛出原始异常
                    else:
                        self.logger.error(
                            f"Max retries ({self.config.max_retries}) exceeded, no fallback. Last error: {e}"
                        )
                        raise
                else:
                    wait = delay
                    if self.config.jitter:
                        import random
                        wait = delay * (0.5 + random.random())
                    self.logger.warning(
                        f"Call failed (attempt {retries}/{self.config.max_retries}) "
                        f"with error: {e}. Retrying in {wait:.2f}s ..."
                    )
                    time.sleep(wait)
                    delay *= self.config.backoff_factor
            except Exception as e:
                # 非重试列表中的异常直接抛出
                self.logger.error(f"Non-retryable exception raised: {e}")
                raise

        # 理论上不会走到这里
        raise RuntimeError("Unexpected recovery flow.")

    def recover(self, func: F) -> F:
        """
        装饰器形式，自动对函数注入失败恢复逻辑
        """
        from functools import wraps
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return self.execute(func, *args, **kwargs)
        return wrapper  # type: ignore

# ---------- 自测部分 ----------
if __name__ == "__main__":
    import sys
    import random

    # 设置控制台输出日志
    test_logger = logging.getLogger("TestRecovery")
    test_logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    test_logger.addHandler(handler)
    set_logger(test_logger)

    # 创建一个模拟的不稳定函数
    call_count = 0
    def unstable_model_call(prompt: str) -> str:
        global call_count
        call_count += 1
        r = random.random()
        if r < 0.6:  # 60% 概率失败
            raise ConnectionError("模拟网络错误")
        return f"Success: {prompt} (attempt {call_count})"

    # 配置恢复器
    config = FailureRecoveryConfig({
        "max_retries": 3,
        "base_delay": 0.1,
        "backoff_factor": 1.5,
        "jitter": True,
        "fallback_enabled": True,
        "fallback_func": lambda p: f"Fallback response for: {p}"
    })

    recovery = ModelFailureRecovery(config)

    print("=== 测试执行模式 ===")
    try:
        result = recovery.execute(unstable_model_call, "Hello world")
        print(f"Got result: {result}")
    except Exception as e:
        print(f"Final failure: {e}")

    # 重置测试
    call_count = 0
    @recovery.recover
    def decorated_call(prompt):
        return unstable_model_call(prompt)

    print("\n=== 测试装饰器模式 ===")
    try:
        result = decorated_call("Hello again")
        print(f"Got result: {result}")
    except Exception as e:
        print(f"Final failure: {e}")