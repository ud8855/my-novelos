"""
Runtime日志模块 - 运行日志记录器

功能：提供可插拔、配置化的运行时日志记录功能。
依赖：Python标准库 logging, 配置模块（通过依赖注入）
被调用：所有需要记录日志的模块
遵循：单一职责，可插拔，配置化，热更新支持
"""

import logging
import logging.config
import os
import sys
from typing import Optional, Dict, Any


class RuntimeLogger:
    """
    运行日志记录器，封装logging模块，提供统一日志接口。
    支持从配置字典动态初始化，支持热更新配置。
    """

    _instance: Optional["RuntimeLogger"] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        """单例模式，确保全局唯一日志记录器"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化日志记录器，仅首次调用时生效（可多次调用但跳过重复初始化）"""
        if not self._initialized:
            self._logger = logging.getLogger("NovelOS.Runtime")
            self._config = {}
            if config is not None:
                self.reload_config(config)
            else:
                # 默认配置：控制台输出，INFO级别
                self._apply_default_config()
            self._initialized = True

    def _apply_default_config(self):
        """应用默认日志配置"""
        default_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": "INFO",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                }
            },
            "loggers": {
                "NovelOS.Runtime": {
                    "level": "INFO",
                    "handlers": ["console"],
                    "propagate": False,
                }
            },
        }
        logging.config.dictConfig(default_config)
        self._config = default_config

    def reload_config(self, config: Dict[str, Any]):
        """
        热更新日志配置
        :param config: 符合logging.config.dictConfig格式的配置字典
        """
        try:
            logging.config.dictConfig(config)
            self._config = config
            self.info("RuntimeLogger配置已重新加载")
        except Exception as e:
            self._logger.error(f"加载日志配置失败: {e}")

    def get_logger(self) -> logging.Logger:
        """获取底层的标准logging.Logger对象，供高级定制使用"""
        return self._logger

    # 代理标准日志方法
    def debug(self, msg: str, *args, **kwargs):
        self._logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self._logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        self._logger.critical(msg, *args, **kwargs)

    def exception(self, msg: str, *args, exc_info: bool = True, **kwargs):
        """
        记录异常信息，自动附加堆栈跟踪
        """
        self._logger.exception(msg, *args, exc_info=exc_info, **kwargs)

    def shutdown(self):
        """安全关闭日志系统，刷新所有缓冲区"""
        logging.shutdown()


# 全局便捷接口，方便其他模块快速获取日志实例
def get_runtime_logger() -> RuntimeLogger:
    """获取RuntimeLogger单例，如果未初始化则使用默认配置初始化"""
    return RuntimeLogger()


# 自测模块
if __name__ == "__main__":
    print("=== Runtime日志模块自测 ===")

    # 测试默认初始化
    logger = get_runtime_logger()
    logger.info("测试信息日志")
    logger.debug("这条调试日志在默认级别不会显示")
    logger.warning("测试警告日志")

    # 测试热更新配置：改为DEBUG级别并输出到文件
    import tempfile, os
    log_file = os.path.join(tempfile.gettempdir(), "novelos_runtime_test.log")
    new_config = {
        "version": 1,
        "formatters": {"detail": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"}},
        "handlers": {
            "console": {"class": "logging.StreamHandler", "level": "DEBUG", "formatter": "detail"},
            "file": {"class": "logging.FileHandler", "level": "DEBUG", "formatter": "detail", "filename": log_file},
        },
        "loggers": {
            "NovelOS.Runtime": {"level": "DEBUG", "handlers": ["console", "file"], "propagate": False}
        },
    }
    # 通过类方法热更新（重新创建实例也能触发配置更新，实际会调用reload_config）
    new_logger = RuntimeLogger(config=new_config)
    new_logger.debug("切换为DEBUG模式后可见的调试信息")
    new_logger.info("同时输出到文件: %s", log_file)
    new_logger.error("这是一条错误日志，包含堆栈吗？没有，普通error")

    try:
        1 / 0
    except ZeroDivisionError:
        new_logger.exception("捕获到异常")

    print("查看临时日志文件是否生成: %s" % log_file)
    new_logger.shutdown()