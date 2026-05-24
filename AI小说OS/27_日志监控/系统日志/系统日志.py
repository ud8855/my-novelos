# -*- coding: utf-8 -*-
"""
系统日志模块
提供统一的日志记录功能，支持可插拔的处理器，配置化管理。
"""
import logging
from typing import Dict, Any, Optional, List

# 全局默认日志器名称
DEFAULT_LOGGER_NAME = "NovelOS_System"

class SystemLogger:
    """系统日志管理器，负责配置和管理日志记录器。"""

    def __init__(self):
        self._loggers: Dict[str, logging.Logger] = {}
        self._configured = False

    def setup(self, config: Dict[str, Any]) -> None:
        """
        根据配置字典设置日志系统。
        配置格式示例：
        {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "handlers": [
                {
                    "type": "console",
                    "level": "DEBUG",
                    "format": "..."
                },
                {
                    "type": "file",
                    "filename": "novelos.log",
                    "level": "INFO"
                }
            ]
        }
        """
        if self._configured:
            # 如果已配置，可选择重新配置，但一般只配置一次
            pass
        logger = logging.getLogger(DEFAULT_LOGGER_NAME)
        logger.setLevel(config.get("level", "INFO").upper())
        # 清除已有的处理器，实现可插拔
        logger.handlers.clear()

        # 默认格式
        log_format = config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        formatter = logging.Formatter(log_format)

        # 根据配置添加处理器
        handlers_config = config.get("handlers", [])
        if not handlers_config:
            # 如果没有配置处理器，默认添加一个控制台处理器
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        else:
            for h_config in handlers_config:
                h_type = h_config.get("type")
                if h_type == "console":
                    handler = logging.StreamHandler()
                elif h_type == "file":
                    filename = h_config.get("filename", "novelos.log")
                    handler = logging.FileHandler(filename)
                else:
                    # 可扩展更多类型
                    continue
                handler.setLevel(h_config.get("level", "INFO").upper())
                # 如果handler有自己的格式，则覆盖
                h_format = h_config.get("format")
                if h_format:
                    handler.setFormatter(logging.Formatter(h_format))
                else:
                    handler.setFormatter(formatter)
                logger.addHandler(handler)

        self._loggers[DEFAULT_LOGGER_NAME] = logger
        self._configured = True

    def get_logger(self, name: Optional[str] = None) -> logging.Logger:
        """
        获取指定名称的日志器。若未提供名称，返回默认系统日志器。
        """
        if name is None:
            name = DEFAULT_LOGGER_NAME
        if name not in self._loggers:
            logger = logging.getLogger(name)
            self._loggers[name] = logger
        return self._loggers[name]

    def add_handler(self, handler: logging.Handler, logger_name: Optional[str] = None) -> None:
        """
        动态添加一个处理器到指定日志器。
        """
        logger = self.get_logger(logger_name)
        logger.addHandler(handler)

    def remove_handler(self, handler: logging.Handler, logger_name: Optional[str] = None) -> None:
        """
        动态移除一个处理器。
        """
        logger = self.get_logger(logger_name)
        logger.removeHandler(handler)

# 创建全局实例，方便模块级直接调用
system_logger = SystemLogger()

# 提供快捷函数
def setup_logging(config: Dict[str, Any]) -> None:
    """配置系统日志。"""
    system_logger.setup(config)

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """获取日志器。"""
    return system_logger.get_logger(name)

# 默认日志器，可以在导入后直接使用
logger = get_logger()

def debug(msg, *args, **kwargs):
    logger.debug(msg, *args, **kwargs)

def info(msg, *args, **kwargs):
    logger.info(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    logger.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    logger.error(msg, *args, **kwargs)

def critical(msg, *