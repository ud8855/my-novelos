#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NovelOS - 世界事件引擎模块 (WorldEvent Engine)
所属层: 10_世界引擎

职责:
    定义和管理小说世界中发生的各种“事件”(Event)。事件可以是剧情触发、环境变化、
    人物行动、时空扭曲、规则变更等。本模块提供统一的事件定义、注册、触发和处理
    机制，并且与上层的故事调度、下层模型协同解耦。

依赖:
    - logging: 标准日志模块
    - config 模块: NovelOS 统一配置接口 (待实现具体加载逻辑)
    - 事件数据格式定义可能依赖 protobuf/自定义序列化协议 (待实现)

被调用者:
    主要为上层的“故事叙事调度器”(Narrative Scheduler)、游戏循环或Agent协作
    模块。通过暴露接口，使得其他模块可以向世界注入事件或订阅事件通知。

设计原则:
    - 可插拔: 事件引擎本身可被替换为更复杂的规则引擎，提供抽象基类支持。
    - 配置化: 事件处理链、触发条件、日志级别等均通过配置控制。
    - 热更新: 支持运行时加载新的事件类型定义或处理函数。
    - 异常恢复: 每个事件处理都应捕获异常，避免单点故障影响整个系统。
    - 日志记录: 所有事件流的产生、处理、结果均记录，便于调试与回溯。
    - 单一职责: 仅负责事件的表示与基础流转，不包含复杂的业务逻辑（如生成对话、决定剧情走向）。

版本: 0.1.0
"""

import logging
from typing import Dict, Any, Optional, Callable, List
import json
import time
from enum import Enum

# 配置模块占位
try:
    from ..config import load_config  # 假设上层配置工具
except ImportError:
    def load_config():
        return {}

# ============================================================================
# 基础定义
# ============================================================================
class EventType(Enum):
    """预定义的事件类型枚举"""
    GENERIC = "generic"
    CHARACTER_ACTION = "character_action"
    ENVIRONMENT_CHANGE = "environment_change"
    PLOT_TRIGGER = "plot_trigger"
    ITEM_USE = "item_use"
    CONVERSATION = "conversation"
    # 可扩展更多类型

class WorldEvent:
    """世界事件的通用数据模型"""
    def __init__(self, event_type: str, source: str, timestamp: float = None,
                 payload: Dict[str, Any] = None):
        self.event_type = event_type          # 事件类型标识
        self.source = source                  # 事件来源（如角色ID、系统模块名）
        self.timestamp = timestamp or time.time()
        self.payload = payload or {}          # 附加数据

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.event_type,
            "source": self.source,
            "timestamp": self.timestamp,
            "payload": self.payload
        }

    def __repr__(self):
        return f"WorldEvent(type={self.event_type}, source={self.source})"


# ============================================================================
# 核心引擎
# ============================================================================
class WorldEventEngine:
    """
    世界事件引擎主类
    负责事件队列管理、分发、处理函数注册和配置加载。
    """
    VERSION = "0.1.0"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化世界事件引擎

        Args:
            config: 可选配置字典，覆盖默认配置。包括：
                - log_level: 日志级别
                - max_event_queue: 事件队列最大长度
                - enable_event_log: 是否记录事件日志
        """
        self.config = config or self._default_config()
        self._setup_logging()
        self.logger = logging.getLogger("WorldEventEngine")
        self.logger.info("Initializing WorldEventEngine v%s", self.VERSION)

        # 事件队列 (简单列表，生产环境中考虑线程安全)
        self._event_queue: List[WorldEvent] = []
        self._max_queue_size = self.config.get("max_event_queue", 1000)

        # 事件处理器注册表: { event_type: [handler_function, ...] }
        self._handlers: Dict[str, List[Callable[[WorldEvent], Any]]] = {}

        # 运行时统计
        self.stats = {
            "events_processed": 0,
            "events_dropped": 0,
            "errors": 0,
            "start_time": time.time()
        }

        self._initialized = True
        self.logger.debug("Engine initialized with config: %s", self.config)

    def _default_config(self) -> Dict[str, Any]:
        """默认配置"""
        return {
            "log_level": "INFO",
            "max_event_queue": 500,
            "enable_event_log": True,
            "processor_timeout": 5.0  # 单个处理器超时（秒）
        }

    def _setup_logging(self):
        """配置日志（基于config中的log_level）"""
        level = self.config.get("log_level", "INFO").upper()
        numeric_level = getattr(logging, level, logging.INFO)
        # 简单设置，假设根日志已由框架配置好，这里只调整级别
        logging.getLogger("WorldEventEngine").setLevel(numeric_level)

    # ========== 事件注入接口 ==========
    def push_event(self, event: WorldEvent) -> bool:
        """
        向世界注入一个新事件，加入待处理队列

        Args:
            event: WorldEvent 实例

        Returns:
            是否成功入队
        """
        if not self._initialized:
            raise RuntimeError("WorldEventEngine not initialized")

        if len(self._event_queue) >= self._max_queue_size:
            self.stats["events_dropped"] += 1
            self.logger.warning("Event queue full, dropping event: %s", event)
            return False

        self._event_queue.append(event)
        self.logger.log(logging.DEBUG, "Event queued: %s", event)
        return True

    def process_events(self) -> int:
        """
        处理当前队列中的所有事件（同步方式）。
        逐一取出事件，调用注册的处理器。

        Returns:
            成功处理的事件数量
        """
        if not self._initialized:
            raise RuntimeError("WorldEventEngine not initialized")

        processed_count = 0
        while self._event_queue:
            event = self._event_queue.pop(0)
            try:
                self._dispatch_event(event)
                processed_count += 1
                self.stats["events_processed"] += 1
            except Exception as e:
                self.stats["errors"] += 1
                self.logger.exception("Error processing event %s: %s", event, e)

        return processed_count

    def _dispatch_event(self, event: WorldEvent):
        """将事件分发给匹配的处理器"""
        handlers = self._handlers.get(event.event_type, [])
        if not handlers:
            self.logger.debug("No handler for event type: %s", event.event_type)
            # 可以添加默认处理器
            return

        for handler in handlers:
            # 简单顺序执行，未做超时处理
            try:
                handler(event)
            except Exception as e:
                self.logger.error("Handler error for event %s: %s", event, e)
                # 不中断后续处理器

    # ========== 处理器注册 ==========
    def register_handler(self, event_type: str, handler: Callable[[WorldEvent], Any]) -> None:
        """
        注册一个事件处理器函数

        Args:
            event_type: 事件类型字符串
            handler: 处理函数，接收一个WorldEvent参数
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        self.logger.info("Handler registered for %s: %s", event_type, handler.__name__)

    def unregister_handler(self, event_type: str, handler: Callable[[WorldEvent], Any]) -> bool:
        """
        移除一个已注册的处理器

        Returns:
            是否成功移除
        """
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                self.logger.info("Handler unregistered for %s: %s", event_type, handler.__name__)
                return True
            except ValueError:
                pass
        return False

    # ========== 状态查询与维护 ==========
    def get_queue_size(self) -> int:
        return len(self._event_queue)

    def clear_queue(self) -> None:
        """清空事件队列"""
        count = len(self._event_queue)
        self._event_queue.clear()
        self.logger.info("Cleared %d pending events", count)

    def get_stats(self) -> Dict[str, Any]:
        """返回运行统计信息"""
        stats = self.stats.copy()
        stats["uptime"] = time.time() - stats["start_time"]
        stats["queue_size"] = self.get_queue_size()
        stats["handler_count"] = sum(len(h) for h in self._handlers.values())
        return stats

    # ========== 热切换与配置更新 ==========
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """运行时更新配置（部分参数即时生效）"""
        self.config.update(new_config)
        self._setup_logging()
        self._max_queue_size = self.config.get("max_event_queue", self._max_queue_size)
        self.logger.info("Configuration updated: %s", new_config)

    def shutdown(self) -> None:
        """安全关闭引擎，清理资源"""
        self.clear_queue()
        self._handlers.clear()
        self._initialized = False
        self.logger.info("WorldEventEngine shutdown complete")


# ============================================================================
# 自测与示例
# ============================================================================
if __name__ == "__main__":
    # 简单自测：启动引擎，注册处理器，注入事件，处理事件，输出统计
    print("===== WorldEvent Engine Self-Test =====")
    # 配置：设置控制台日志级别
    test_config = {
        "log_level": "DEBUG",
        "max_event_queue": 10
    }
    engine = WorldEventEngine(config=test_config)

    # 注册一个示例处理器
    def sample_character_action_handler(event: WorldEvent):
        print(f"[Handler] Processing character action from {event.source}: {event.payload}")

    engine.register_handler("character_action", sample_character_action_handler)

    # 创建几个测试事件
    event1 = WorldEvent(
        event_type="character_action",
        source="npc_001",
        payload