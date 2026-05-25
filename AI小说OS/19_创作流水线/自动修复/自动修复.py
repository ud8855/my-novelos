"""
自动修复模块 (Automated Fix Module)

属于: 19_创作流水线 / 自动修复
依赖: 日志模块 (标准库 logging), 配置管理 (通过字典传入)
被调用: 创作流水线主控模块、故事修订Agent 等
职责: 接收原始文本与错误信息, 调用内部策略进行自动修复, 返回修复后的文本
协议:
  - 输入: original_text (str), error_info (dict, 可选)
  - 输出: fixed_text (str)
  - 允许热重载配置, 支持异常隔离
"""

import logging
import sys
from typing import Optional, Dict, Any, Callable

# ---------- 配置默认值 ----------
DEFAULT_CONFIG: Dict[str, Any] = {
    "max_attempts": 3,                 # 最大尝试修复次数
    "default_fallback": True,          # 修复失败时是否返回原文
    "strategy": "basic",               # 当前使用的修复策略
    "log_level": logging.INFO,         # 日志级别
    "log_format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
}


class AutoFixer:
    """
    自动修复器 (可插拔组件)

    遵循:
      - 单一职责: 仅负责文本修复逻辑
      - 可插拔: 通过构造函数传入配置, 动态加载策略
      - 热更新: 支持运行时 update_config
      - 异常恢复: 修复过程异常时记录日志并安全回退
      - 日志记录: 标准化日志
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化修复器

        Args:
            config: 自定义配置字典, 缺失项自动使用 DEFAULT_CONFIG
        """
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)

        # 日志初始化
        self.logger = logging.getLogger(f"{__name__}.AutoFixer")
        self._setup_logging()

        # 策略映射 (当前仅注册 basic, 后续可扩展)
        self._strategies: Dict[str, Callable[[str, dict], str]] = {
            "basic": self._basic_fix,
        }

        # 当前策略实例
        self.current_strategy = self._strategies.get(
            self.config["strategy"], self._strategies["basic"]
        )

        self.logger.info(
            "AutoFixer initialized with strategy: %s", self.config["strategy"]
        )

    def _setup_logging(self) -> None:
        """配置日志格式与级别 (不干扰全局设置)"""
        self.logger.setLevel(self.config.get("log_level", logging.INFO))
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(self.config.get("log_format", DEFAULT_CONFIG["log_format"]))
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """
        热更新配置 (支持运行时切换策略)
        """
        self.config.update(new_config)
        # 可能切换策略
        strategy_name = self.config.get("strategy", "basic")
        if strategy_name in self._strategies:
            self.current_strategy = self._strategies[strategy_name]
            self.logger.info("Strategy updated to %s", strategy_name)
        else:
            self.logger.warning("Unknown strategy '%s', keeping current.", strategy_name)
        # 重新设置日志级别如果有变化
        if "log_level" in new_config:
            self.logger.setLevel(new_config["log_level"])

        self.logger.debug("Configuration updated: %s", new_config)

    def fix(self, original_text: str, error_info: Optional[Dict[str, Any]] = None) -> str:
        """
        对文本进行自动修复

        Args:
            original_text: 待修复的原始文本
            error_info: 错误详情, 如 {'type': 'logic', 'description': '...'}

        Returns:
            修复后的文本, 若失败且配置 default_fallback=True 则返回原文, 否则抛出异常
        """
        if error_info is None:
            error_info = {}

        attempts = 0
        last_exception = None
        max_attempts = self.config.get("max_attempts", 1)
        fallback_allowed = self.config.get("default_fallback", True)

        while attempts < max_attempts:
            attempts += 1
            self.logger.debug(
                "Fix attempt %d/%d for text (length %d)", attempts, max_attempts, len(original_text)
            )
            try:
                # 调用当前策略进行修复
                fixed = self.current_strategy(original_text, error_info)
                self.logger.info("Fix succeeded in attempt %d", attempts)
                return fixed
            except Exception as e:
                last_exception = e
                self.logger.warning(
                    "Fix attempt %d failed: %s", attempts, e
                )
                # 可以在此加入不同尝试之间的退避或策略切换

        self.logger.error("All %d fix attempts failed.", max_attempts)
        if fallback_allowed:
            self.logger.warning("Falling back to original text.")
            return original_text
        else:
            raise RuntimeError("AutoFix failed after all attempts.") from last_exception

    def _basic_fix(self, text: str, error_info: dict) -> str:
        """
        基础修复策略: 不做实际修改, 仅作为占位

        实际开发时由下层模块实现真实修复算法, 此处仅返回原文并记录日志
        """
        self.logger.debug("Basic fix applied (no changes).")
        # TODO: 集成规则引擎、NLP模型等
        return text

    def register_strategy(self, name: str, strategy_callable: Callable[[str, dict], str]) -> None:
        """
        注册新的修复策略 (实现可插拔扩展)

        Args:
            name: 策略名称
            strategy_callable: 接收 (original_text, error_info) 返回 fixed_text 的可调用对象
        """
        self._strategies[name] = strategy_callable
        self.logger.info("New strategy registered: %s", name)


# ---------- 自测 ----------
if __name__ == "__main__":
    # 简单自测：单模块可运行
    print("=== AutoFixer Self-Test ===")

    # 1. 默认配置测试
    fixer = AutoFixer()
    test_text = "这是一个测试句子，存在逻辑错误。"
    test_error = {"type": "logic", "description": "时间线矛盾"}
    result = fixer.fix(test_text, test_error)
    print(f"Input: {test_text}\nOutput: {result}\n")

    # 2. 热更新配置测试
    fixer.update_config({"strategy": "basic"})
    result2 = fixer.fix(test_text)
    print(f"After config update: {result2}")

    # 3. 注册新策略演示
    def reverse_strategy(text, error_info):
        return text[::-1]

    fixer.register_strategy("reverse", reverse_strategy)
    fixer.update_config({"strategy": "reverse"})
    reversed_result = fixer.fix(test_text)
    print(f"Reversed strategy result: {reversed_result}")

    # 4. 异常恢复测试 (使用一个会出错的自定义策略)
    def faulty_strategy(text, error_info):
        raise ValueError("Simulated strategy failure")

    fixer.register_strategy("faulty", faulty_strategy)
    fixer.update_config({"strategy": "faulty", "max_attempts": 2})
    fallback_result = fixer.fix(test_text)
    print(f"Fallback result: {fallback_result} (should be original)")

    print("=== Test Completed ===")