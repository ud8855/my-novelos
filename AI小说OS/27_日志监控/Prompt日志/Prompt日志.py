#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module: Prompt日志
Layer: 27_日志监控
Description: 可插拔的Prompt交互日志记录器，负责记录所有模型的Prompt输入与输出，
             支持热插拔、配置化、异常恢复和日志轮转。

Dependencies:
    - logging (standard library)
    - json (standard library)
    - os, time, threading (standard library)
    - 配置模块: 27_日志监控/配置 (假设存在 config.py 提供日志配置)
    - 可选: 外部插件管理器 (尚未实现，此处用简单的注册/注销模拟)

Called by:
    - 20_模型协同/ 中的协调器，用于在模型调用前后记录Prompt日志。
    - 21_API模型/ 中的实际API调用模块，作为回调钩子。

注意：当前为骨架代码，遵循单一职责，不包含业务逻辑。
"""

import logging
import logging.handlers
import json
import time
import os
import threading
from typing import Optional, Dict, Any, Callable

# 尝试导入配置模块，若不存在则使用默认配置
try:
    from .config import LOG_CONFIG  # 假设存在配置模块
except ImportError:
    LOG_CONFIG = {
        "level": "DEBUG",
        "log_dir": "logs/prompt",
        "max_bytes": 10 * 1024 * 1024,  # 10MB
        "backup_count": 5,
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    }


class PromptLogger:
    """
    Prompt日志记录器 (可插拔单例)
    功能：
        - 记录每次模型调用的Prompt内容、模型名称、时间戳、响应摘要等。
        - 支持配置化日志级别、存储路径和轮转策略。
        - 提供注册/注销方法，实现可插拔。
        - 内部使用线程安全锁，确保多线程环境安全。
        - 异常恢复：记录过程失败时不影响主流程，并回退到console输出。
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """单例模式，保证全局只有一个日志记录器实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化日志记录器
        :param config: 可选配置字典，覆盖默认配置。
                       结构: {
                           "level": "INFO",
                           "log_dir": "custom_log_path",
                           "max_bytes": 10485760,
                           "backup_count": 7,
                           "format": "..."
                       }
        """
        # 防止重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return

        self._initialized = True
        self._config = LOG_CONFIG.copy()
        if config:
            self._config.update(config)

        # 创建日志目录
        log_dir = self._config.get("log_dir", "logs/prompt")
        os.makedirs(log_dir, exist_ok=True)

        # 配置logger
        self.logger = logging.getLogger("PromptLogger")
        self.logger.setLevel(self._config.get("level", "DEBUG").upper())
        # 避免重复添加handler
        if not self.logger.handlers:
            # 文件handler（支持轮转）
            log_file = os.path.join(log_dir, "prompt.log")
            fh = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=self._config.get("max_bytes", 10*1024*1024),
                backupCount=self._config.get("backup_count", 5),
                encoding='utf-8'
            )
            # 格式
            formatter = logging.Formatter(
                self._config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)

            # 可选的console handler，用于调试
            ch = logging.StreamHandler()
            ch.setLevel(logging.WARNING)  # 只输出警告和错误到控制台
            ch.setFormatter(formatter)
            self.logger.addHandler(ch)

        # 注册状态
        self._active = False  # 是否已激活（可插拔控制）
        self._registered_sinks = []  # 可扩展的额外日志输出目标

        self.logger.info("PromptLogger initialized with config: %s", self._config)

    def register(self) -> None:
        """
        激活日志记录器（注册到系统中）
        可插拔接口：当模块被热加载时调用此方法激活记录。
        """
        if self._active:
            self.logger.warning("PromptLogger is already active.")
            return
        self._active = True
        self.logger.info("PromptLogger activated and ready to record prompts.")

    def unregister(self) -> None:
        """
        停用日志记录器（从系统中注销）
        可插拔接口：当模块被热卸载时调用此方法停止记录。
        """
        if not self._active:
            self.logger.warning("PromptLogger is not active.")
            return
        self._active = False
        self.logger.info("PromptLogger deactivated.")

    def is_active(self) -> bool:
        """查询记录器是否处于激活状态"""
        return self._active

    def log_prompt(self,
                   model_name: str,
                   prompt_text: str,
                   response_text: str = "",
                   metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        记录一次完整的Prompt交互。
        :param model_name: 使用的模型标识（如 "gpt-4", "claude-3"）
        :param prompt_text: 发送给模型的完整Prompt文本
        :param response_text: 模型返回的响应文本（可选）
        :param metadata: 额外元数据（如时间戳、对话ID、用户ID等）
        """
        if not self._active:
            self.logger.debug("PromptLogger is not active, skip logging.")
            return

        try:
            timestamp = time.time()
            log_entry = {
                "timestamp": timestamp,
                "model": model_name,
                "prompt": prompt_text,
                "response": response_text,
                "metadata": metadata or {}
            }
            # 序列化为JSON字符串进行存储（便于结构化查询）
            log_json = json.dumps(log_entry, ensure_ascii=False)
            self.logger.info(log_json)

            # 调用注册的额外sink（可扩展性，例如发送到ELK、数据库等）
            for sink in self._registered_sinks:
                try:
                    sink(log_entry)
                except Exception as sink_err:
                    self.logger.error("Error in log sink %s: %s", sink, sink_err)

        except Exception as e:
            # 异常恢复：记录异常但不影响主业务
            self.logger.exception("Failed to log prompt: %s", e)

    def add_sink(self, sink: Callable[[Dict[str, Any]], None]) -> None:
        """
        添加额外的日志输出目标 (可插拔扩展)
        :param sink: 一个接受日志字典作为参数的函数
        """
        if sink not in self._registered_sinks:
            self._registered_sinks.append(sink)
            self.logger.info("Added log sink: %s", sink)

    def remove_sink(self, sink: Callable[[Dict[str, Any]], None]) -> None:
        """
        移除日志输出目标
        :param sink: 之前注册的sink函数
        """
        if sink in self._registered_sinks:
            self._registered_sinks.remove(sink)
            self.logger.info("Removed log sink: %s", sink)


# ===================== 自测代码 =====================
if __name__ == "__main__":
    """
    使用示例：
    1. 实例化记录器（自动使用默认配置）
    2. 激活记录
    3. 模拟记录一条prompt日志
    4. 演示注册额外sink（打印到控制台）
    5. 演示停用及重新激活
    """
    print("=== Prompt日志模块自测 ===")

    # 1. 创建实例（单例，带有定制配置）
    custom_config = {
        "level": "DEBUG",
        "log_dir": "test_logs/prompt",
        "max_bytes": 1024,  # 故意设小，测试轮转
        "backup_count": 2
    }
    logger = PromptLogger(custom_config)

    # 2. 激活记录
    logger.register()

    # 3. 记录一条日志
    logger.log_prompt(
        model_name="gpt-3.5-turbo",
        prompt_text="写一首关于夏天的诗",
        response_text="夏日炎炎正好眠...",
        metadata={"user_id": "test_user", "session_id": "abc123"}
    )

    # 4. 添加一个简单的sink：打印到stdout（注意控制台已输出，此处作为演示）
    def console_sink(entry):
        print(f"[EXTRA SINK] Model: {entry['model']}, Prompt length: {len(entry['prompt'])}")

    logger.add_sink(console_sink)

    # 再记录一条，会触发sink
    logger.log_prompt(
        model_name="gpt-4",
        prompt_text="解释量子计算",
        response_text="量子计算是一种...",
        metadata={"topic": "physics"}
    )

    # 5. 停用，再记录一次（应被跳过）
    logger.unregister()
    logger.log_prompt(model_name="dummy", prompt_text="测试", response_text="无")

    # 重新激活，再次记录
    logger.register()
    logger.log_prompt(model_name="claude-3", prompt_text="Hello", response_text="Hi there!")

    # 移除sink
    logger.remove_sink(console_sink)

    # 记录最后一条，验证sink移除
    logger.log_prompt(model_name="gpt-4", prompt_text="Final test", response_text="Done")

    print("自测完成，请检查日志文件：", os.path.join(custom_config["log_dir"], "prompt.log"))