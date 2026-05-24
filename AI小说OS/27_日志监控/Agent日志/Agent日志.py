"""
Agent日志.py
模块路径: 27_日志监控/Agent日志
职责: 为多Agent系统提供可插拔、可配置、带上下文追踪的日志服务。
依赖: 标准logging模块、配置管理模块（通过注入）
被调用: 各类Agent活动记录、监控系统
符合: NovelOS一级/二级目录冻结规则，模块独立可替换
"""

import logging
import os
import json
import time
from typing import Optional, Dict, Any
from contextvars import ContextVar

# ---------------------------
# 上下文变量，用于跨调用链传递Agent标识
# ---------------------------
current_agent_id: ContextVar[Optional[str]] = ContextVar('current_agent_id', default=None)
current_session_id: ContextVar[Optional[str]] = ContextVar('current_session_id', default=None)

# ---------------------------
# 默认配置
# ---------------------------
DEFAULT_CONFIG = {
    "log_level": "INFO",
    "log_format": "%(asctime)s [%(levelname)s] [Agent:%(agent_id)s] [Session:%(session_id)s] %(name)s - %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S",
    "handlers": {
        "console": {
            "enabled": True,
            "level": "DEBUG",
            "formatter": "console"
        },
        "file": {
            "enabled": True,
            "level": "INFO",
            "file_path": "logs/agent_{agent_id}_session_{session_id}.log",
            "max_bytes": 10 * 1024 * 1024,
            "backup_count": 5
        }
    },
    "formatters": {
        "console": {
            "format": "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            "date_format": "%H:%M:%S"
        }
    }
}


class AgentLogger:
    """
    可插拔Agent日志记录器
    特性:
    - 支持运行时切换handler
    - 自动注入Agent和Session标识
    - 配置驱动，零硬编码
    - 兼容标准库logging，便于集成第三方监控
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化日志器
        :param config: 自定义配置字典，与DEFAULT_CONFIG合并。若为None则使用默认配置。
        """
        self._config = DEFAULT_CONFIG.copy()
        if config:
            self._merge_config(self._config, config)

        # 核心logger
        self.logger = logging.getLogger("NovelOS.Agent")
        self.logger.setLevel(self._config["log_level"])
        self.logger.propagate = False  # 防止传播到根logger

        # 内部存储handler引用，以便动态管理
        self._handlers = {}

        # 应用默认handler
        self._apply_handlers()

        # 注入上下文过滤
        self._inject_context_filter()

    def _merge_config(self, base: dict, override: dict):
        """递归合并配置，override覆盖base"""
        for key, value in override.items():
            if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def _apply_handlers(self):
        """根据当前配置创建并添加handler"""
        # 清除已有handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        self._handlers.clear()

        handler_cfgs = self._config.get("handlers", {})
        if not handler_cfgs:
            # 默认添加一个空handler，避免"No handlers could be found"警告
            self.logger.addHandler(logging.NullHandler())
            return

        for handler_name, h_conf in handler_cfgs.items():
            if not h_conf.get("enabled", True):
                continue

            if handler_name == "console":
                h = logging.StreamHandler()
            elif handler_name == "file":
                # 文件路径可能包含占位符，这里先用基本路径，后续可通过set_context刷新
                raw_path = h_conf.get("file_path", "logs/agent.log")
                # 确保目录存在
                dir_name = os.path.dirname(raw_path)
                if dir_name:
                    os.makedirs(dir_name, exist_ok=True)
                h = logging.FileHandler(raw_path, encoding='utf-8')
            else:
                # 支持扩展自定义handler类型，通过全限定类名动态加载，此处骨架略
                continue

            # 设置handler级别
            h.setLevel(h_conf.get("level", self._config["log_level"]))

            # 设置格式化器
            formatter = self._create_formatter(h_conf.get("formatter"))
            h.setFormatter(formatter)

            self.logger.addHandler(h)
            self._handlers[handler_name] = h

    def _create_formatter(self, formatter_name: Optional[str] = None) -> logging.Formatter:
        """根据配置创建Formatter，使用上下文感知的Filter注入agent_id等"""
        fmt_cfg = self._config.get("formatters", {}).get(formatter_name) if formatter_name else None
        if not fmt_cfg:
            # 使用全局默认格式
            fmt_cfg = {
                "format": self._config.get("log_format", "%(message)s"),
                "date_format": self._config.get("date_format", None)
            }
        return logging.Formatter(fmt_cfg["format"], datefmt=fmt_cfg.get("date_format"))

    def _inject_context_filter(self):
        """添加Filter，将上下文变量动态注入到LogRecord"""
        class AgentContextFilter(logging.Filter):
            def filter(self_, record):
                record.agent_id = current_agent_id.get() or "N/A"
                record.session_id = current_session_id.get() or "N/A"
                return True

        # 避免重复添加
        existing_filters = [f for f in self.logger.filters if isinstance(f, AgentContextFilter)]
        if not existing_filters:
            self.logger.addFilter(AgentContextFilter())

    # ----- 公共接口 -----
    def set_context(self, agent_id: Optional[str] = None, session_id: Optional[str] = None):
        """设置当前日志的上下文标识，通常在Agent启动或会话切换时调用"""
        if agent_id:
            current_agent_id.set(agent_id)
        if session_id:
            current_session_id.set(session_id)
        # 如果使用了文件handler，可能需要刷新文件路径（本例简化处理）
        # 实际应用可监听上下文变化重新创建handler，此处略

    def get_logger(self) -> logging.Logger:
        """获取底层logger实例，供需要精细控制的模块使用"""
        return self.logger

    def reconfigure(self, new_config: Dict[str, Any]):
        """运行时重新配置日志系统（热更新）"""
        self._merge_config(self._config, new_config)
        self.logger.setLevel(self._config["log_level"])
        self._apply_handlers()

    # 快捷日志方法，保持调用简洁
    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)

    def exception(self, msg, *args, **kwargs):
        """记录异常，自动附带堆栈信息"""
        self.logger.exception(msg, *args, **kwargs)


# ---------------------------
# 自测代码
# ---------------------------
if __name__ == "__main__":
    print("=== Agent日志模块自测 ===")

    # 1. 默认配置实例
    agent_log = AgentLogger()
    agent_log.set_context(agent_id="PlotMaster", session_id="session_001")
    agent_log.info("Agent启动")
    agent_log.debug("调试信息：接收任务")
    try:
        1 / 0
    except ZeroDivisionError:
        agent_log.exception("发生除零异常")

    # 2. 自定义配置示例（例如仅控制台输出，格式简化）
    custom_config = {
        "log_level": "DEBUG",
        "handlers": {
            "console": {
                "enabled": True,
                "level": "DEBUG",
                "formatter": "simple"
            },
            "file": {
                "enabled": False
            }
        },
        "formatters": {
            "simple": {
                "format": "[%(levelname)s] %(message)s"
            }
        }
    }
    print("\n--- 切换为自定义配置 ---")
    custom_log = AgentLogger(config=custom_config)
    custom_log.set_context(agent_id="WorldBuilder", session_id="session_002")
    custom_log.info("世界构建完成")
    custom_log.debug("参数检查通过")

    # 3. 热更新测试
    print("\n--- 热更新日志级别为WARNING ---")
    agent_log.reconfigure({"log_level": "WARNING"})
    agent_log.info("这条INFO不应显示")  # 被过滤
    agent_log.warning("这条WARNING应显示")

    print("\n自测结束")