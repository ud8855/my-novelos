"""
27_日志监控/错误日志/错误日志.py

所属层：监控与日志
依赖：标准库logging, configparser或自定义配置加载器（这里简化为字典）
被调用：系统中任何需要记录错误的模块
解决：提供统一、可配置、可插拔的错误日志记录机制

遵循系统规则：可插拔（通过抽象基类和注册机制）、配置化、日志、中文注释、英文标识符
"""
import logging
import traceback
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

# ------------------------------------------------------------
# 配置默认值
# ------------------------------------------------------------
DEFAULT_CONFIG = {
    "log_level": "ERROR",
    "log_format": "[{time}] [{level}] [{module}] {message}",
    "output_targets": ["console"],  # console, file, remote etc.
    "file_path": "logs/error.log",
    "max_file_size": 10 * 1024 * 1024,
    "backup_count": 5,
    "module_name": "ErrorLog",
}

# ------------------------------------------------------------
# 抽象基类，定义错误日志接口（可插拔）
# ------------------------------------------------------------
class BaseErrorLogger(ABC):
    """
    错误日志抽象基类，所有错误日志实现必须继承此类。
    确保能够在不修改调用方代码的情况下替换实现。
    """
    @abstractmethod
    def log_error(self, error: Exception, module: str = "", extra_info: Optional[Dict[str, Any]] = None) -> None:
        """
        记录一个异常错误。
        :param error: 异常对象
        :param module: 发生错误的模块名
        :param extra_info: 额外信息字典
        """
        pass

    @abstractmethod
    def log_message(self, level: str, message: str, module: str = "", extra_info: Optional[Dict[str, Any]] = None) -> None:
        """
        记录一条自定义级别的消息。
        :param level: 日志级别字符串，如 ERROR,WARNING,INFO
        :param message: 日志消息
        :param module: 来源模块
        :param extra_info: 额外信息
        """
        pass

# ------------------------------------------------------------
# 默认错误日志实现
# ------------------------------------------------------------
class DefaultErrorLogger(BaseErrorLogger):
    """
    默认错误日志实现，基于标准化 logging 库。
    支持控制台、文件输出，可配置格式和级别。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化错误日志记录器。
        :param config: 配置字典，若为None则使用默认配置
        """
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)

        self.module_name = self.config.get("module_name", "ErrorLog")
        self.logger = logging.getLogger("novelos.error_log")
        self.logger.setLevel(self._parse_level(self.config.get("log_level", "ERROR")))

        # 防止重复添加处理器（可插拔替换时清理）
        if self.logger.handlers:
            self.logger.handlers.clear()

        # 根据配置添加输出目标
        formatter = logging.Formatter(
            fmt=self.config.get("log_format", "[{time}] [{level}] [{module}] {message}"),
            style='{'
        )
        for target in self.config.get("output_targets", ["console"]):
            if target == "console":
                import sys
                console_handler = logging.StreamHandler(sys.stderr)
                console_handler.setFormatter(formatter)
                self.logger.addHandler(console_handler)
            elif target == "file":
                from logging.handlers import RotatingFileHandler
                file_path = self.config.get("file_path", "logs/error.log")
                max_bytes = self.config.get("max_file_size", 10*1024*1024)
                backup_count = self.config.get("backup_count", 5)
                file_handler = RotatingFileHandler(
                    file_path, maxBytes=max_bytes, backupCount=backup_count
                )
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            # 可扩展其他目标，如网络、数据库等

        # 自身初始化成功记录
        self.logger.debug("DefaultErrorLogger initialized with config: %s", self.config)

    def _parse_level(self, level_str: str) -> int:
        """将字符串日志级别转换为logging常量"""
        return getattr(logging, level_str.upper(), logging.ERROR)

    def log_error(self, error: Exception, module: str = "", extra_info: Optional[Dict[str, Any]] = None) -> None:
        """
        记录异常，包括完整堆栈。
        """
        stack_trace = traceback.format_exc()
        msg = f"{type(error).__name__}: {str(error)}\n{stack_trace}"
        if extra_info:
            # 将额外信息格式化为字符串附加
            extra_str = " ".join(f"{k}={v}" for k, v in extra_info.items())
            msg += f"\nExtraInfo: {extra_str}"
        self._emit("ERROR", msg, module)

    def log_message(self, level: str, message: str, module: str = "", extra_info: Optional[Dict[str, Any]] = None) -> None:
        """
        记录指定级别的消息。
        """
        msg = message
        if extra_info:
            extra_str = " ".join(f"{k}={v}" for k, v in extra_info.items())
            msg += f" | ExtraInfo: {extra_str}"
        self._emit(level, msg, module)

    def _emit(self, level: str, message: str, module: str) -> None:
        """
        内部发送日志，统一处理格式和额外字段。
        使用LogRecord的自定义字段可能会破坏标准格式，因此直接在消息中拼接模块信息。
        也可使用extra参数，但需要适配formatter，此处为了简化直接拼接。
        """
        log_func = getattr(self.logger, level.lower(), self.logger.error)
        # 确保模块信息包含在消息中（formatter里已有{module}占位符，但为了灵活，采用拼接）
        # 如果formatter包含{module}，则需要通过extra传递；否则拼接。
        # 这里采用拼接方式，避免extra和formatter不匹配。
        full_message = f"[Module: {module}] {message}" if module else message
        log_func(full_message)

# ------------------------------------------------------------
# 错误日志管理器（工厂/注册器，实现可插拔）
# ------------------------------------------------------------
class ErrorLogManager:
    """
    全局错误日志管理器，负责创建、注册、切换不同的ErrorLogger实现。
    所有需要错误日志的模块通过此类获取当前生效的记录器实例。
    """
    _instance = None
    _logger_impl: BaseErrorLogger = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._logger_impl is None:
            # 默认使用 DefaultErrorLogger
            self._logger_impl = DefaultErrorLogger()

    def set_logger(self, logger: BaseErrorLogger) -> None:
        """
        设置新的错误日志实现，实现热插拔。
        :param logger: 新的错误日志记录器实例
        """
        if not isinstance(logger, BaseErrorLogger):
            raise TypeError("Logger must be an instance of BaseErrorLogger")
        self._logger_impl = logger
        logging.getLogger("novelos.error_log").info("Error logger implementation changed to %s", type(logger).__name__)

    def get_logger(self) -> BaseErrorLogger:
        """
        获取当前错误日志记录器。
        :return: BaseErrorLogger 实例
        """
        return self._logger_impl

# ------------------------------------------------------------
# 便捷函数，方便其他模块直接调用（使用全局管理器）
# ------------------------------------------------------------
def log_error(error: Exception, module: str = "", extra_info: Optional[Dict[str, Any]] = None):
    """
    可插拔错误记录快捷函数。
    """
    ErrorLogManager().get_logger().log_error(error, module, extra_info)

def log_message(level: str, message: str, module: str = "", extra_info: Optional[Dict[str, Any]] = None):
    """
    可插拔消息记录快捷函数。
    """
    ErrorLogManager().get_logger().log_message(level, message, module, extra_info)

# ------------------------------------------------------------
# 自测部分（仅在直接运行该模块时执行）
# ------------------------------------------------------------
if __name__ == "__main__":
    print("=== 启动错误日志模块自测 ===")

    # 1. 测试默认配置
    print("--- 测试1: 使用默认配置记录错误 ---")
    try:
        raise ValueError("这是一个测试异常")
    except Exception as e:
        log_error(e, module="TestModule", extra_info={"user_id": 123, "action": "test"})

    # 2. 测试自定义级别消息
    print("--- 测试2: 记录自定义消息 ---")
    log_message("WARNING", "磁盘空间不足", module="StorageModule", extra_info={"disk": "/dev/sda1", "free_space": "100MB"})

    # 3. 测试配置切换（文件输出）
    print("--- 测试3: 切换到文件输出并记录错误 ---")
    file_config = {
        "log_level": "DEBUG",
        "output_targets": ["file", "console"],
        "file_path": "test_error.log",
        "max_file_size": 1024*1024,
        "backup_count": 2,
        "module_name": "TestErrorLog",
    }
    custom_logger = DefaultErrorLogger(config=file_config)
    ErrorLogManager().set_logger(custom_logger)  # 热插拔替换
    try:
        1 / 0
    except Exception as e:
        log_error(e, module="Math", extra_info={"operation": "division"})

    print("--- 自测完成，请检查 test_error.log 文件（若有）和控制台输出 ---")
    # 注意：文件日志可能会因路径权限失败，实际部署时需处理。
    # 此处仅作示例，不处理异常，以保持骨架简洁。

# 注意：此模块本身也会使用 logging 记录自身状态，但不会形成循环，
# 因为 error_log 内部使用的是独立的 logger 名称 'novelos.error_log'，
# 而全局 logging 根记录器配置不会影响该 logger 除非显式配置。
# 在实际系统中，可通过 27_日志监控/ 的统一配置来管理所有日志行为。