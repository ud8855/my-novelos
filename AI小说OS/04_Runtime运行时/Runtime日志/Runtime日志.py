"""
Runtime日志模块
属于：04_Runtime运行时层
依赖：标准库 logging，以及运行时配置（通过参数传入或本地配置）
被调用：其他 Runtime 组件，用于记录运行时事件、调试信息
解决：提供统一的、可插拔的运行时日志记录功能，支持配置化输出目标、级别和格式
"""

import logging
import sys
from typing import Optional, Dict, Any, List, Union

class RuntimeLogger:
    """
    运行时日志记录器
    可插拔：通过配置工厂创建，或运行时动态添加 handler
    配置化：支持从字典或配置文件加载日志级别、格式、输出目标
    中文注释：本类所有公共方法均包含中文说明
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化日志器
        :param config: 配置字典，包含 log_level, log_format, handlers 等
                       若未提供，则使用默认控制台输出，级别为 DEBUG
        """
        self._config = config or self._default_config()
        self._logger = logging.getLogger("NovelOS.Runtime")
        self._logger.setLevel(self._config.get("log_level", logging.DEBUG))
        # 避免重复添加 handler，先清除已有的
        self._logger.handlers.clear()
        # 根据配置添加 handlers
        handlers = self._config.get("handlers", None)
        if handlers is None:
            # 默认添加控制台 handler
            self._add_console_handler(self._config.get("log_format"))
        else:
            for handler_cfg in handlers:
                self._apply_handler_config(handler_cfg)

    def _default_config(self) -> Dict[str, Any]:
        """默认配置：控制台输出，DEBUG级别，带时间戳和模块名"""
        return {
            "log_level": logging.DEBUG,
            "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "handlers": None
        }

    def _add_console_handler(self, fmt: Optional[str] = None):
        """添加控制台 handler"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(fmt or self._config.get("log_format"))
        console_handler.setFormatter(formatter)
        self._logger.addHandler(console_handler)

    def _add_file_handler(self, file_path: str, fmt: Optional[str] = None):
        """添加文件 handler"""
        file_handler = logging.FileHandler(file_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(fmt or self._config.get("log_format"))
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)

    def _apply_handler_config(self, handler_cfg: Dict[str, Any]):
        """根据配置字典添加对应的 handler"""
        h_type = handler_cfg.get("type", "console")
        fmt = handler_cfg.get("format")
        if h_type == "console":
            self._add_console_handler(fmt)
        elif h_type == "file":
            file_path = handler_cfg.get("file_path", "runtime.log")
            self._add_file_handler(file_path, fmt)
        # 可扩展其他类型，如网络、数据库等

    def debug(self, message: str, *args, **kwargs):
        """记录 DEBUG 级别日志"""
        self._logger.debug(message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        """记录 INFO 级别日志"""
        self._logger.info(message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        """记录 WARNING 级别日志"""
        self._logger.warning(message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        """记录 ERROR 级别日志"""
        self._logger.error(message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        """记录 CRITICAL 级别日志"""
        self._logger.critical(message, *args, **kwargs)

    def add_handler(self, handler: logging.Handler):
        """动态添加自定义 handler，支持热插拔"""
        self._logger.addHandler(handler)

    def remove_handler(self, handler: logging.Handler):
        """动态移除 handler"""
        self._logger.removeHandler(handler)

# 自测代码
if __name__ == "__main__":
    # 测试默认配置（控制台输出）
    print("=== 测试默认配置 ===")
    logger = RuntimeLogger()
    logger.debug("这是一条 DEBUG 日志")
    logger.info("这是一条 INFO 日志")
    logger.warning("这是一条 WARNING 日志")
    logger.error("这是一条 ERROR 日志")
    logger.critical("这是一条 CRITICAL 日志")

    # 测试文件输出配置
    print("\n=== 测试文件输出配置 ===")
    config = {
        "log_level": logging.INFO,
        "log_format": "%(levelname)s - %(message)s",
        "handlers": [
            {"type": "console"},
            {"type": "file", "file_path": "test_runtime.log"}
        ]
    }
    file_logger = RuntimeLogger(config)
    file_logger.info("这条日志会同时输出到控制台和文件")
    file_logger.warning("请注意文件 test_runtime.log 中应存在相应记录")

    # 演示热插拔：动态添加 handler
    print("\n=== 演示动态添加 handler ===")
    new_handler = logging.StreamHandler(sys.stdout)
    new_handler.setLevel(logging.ERROR)
    formatter = logging.Formatter("CUSTOM: %(message)s")
    new_handler.setFormatter(formatter)
    file_logger.add_handler(new_handler)
    file_logger.error("这条 ERROR 日志会通过新添加的 handler 输出一次额外信息")
    # 移除该 handler
    file_logger.remove_handler(new_handler)
    file_logger.error("移除后，这条 ERROR 日志不会再被自定义 handler 影响")