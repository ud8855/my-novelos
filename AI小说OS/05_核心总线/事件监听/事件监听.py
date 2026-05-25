"""
事件监听模块 - 核心总线的事件分发与监听
功能：提供统一的事件订阅、发布机制，支持热插拔监听器，配置化日志记录
"""

import logging
import traceback
from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict

# 配置默认值
DEFAULT_CONFIG = {
    "max_listeners_per_event": 100,
    "async_support": False,
    "log_events": True,
}

class EventBus:
    """事件总线，负责事件的订阅与发布，支持监听器的动态插拔"""
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化事件总线
        :param config: 事件总线配置，可包含 max_listeners_per_event, log_events 等
        """
        self._config = DEFAULT_CONFIG.copy()
        if config:
            self._config.update(config)
            
        # 事件监听器映射：事件名 -> 监听器列表[(优先级, 监听器标识, 回调), ...]
        self._listeners: Dict[str, List[tuple]] = defaultdict(list)
        self._logger = logging.getLogger(f"{__name__}.EventBus")
        self._logger.info("EventBus initialized with config: %s", self._config)
        
    def subscribe(self, event_name: str, callback: Callable, identifier: Optional[str] = None, priority: int = 0) -> bool:
        """
        订阅事件，添加监听器
        :param event_name: 事件名称
        :param callback: 回调函数，接收事件数据 *args, **kwargs
        :param identifier: 监听器唯一标识，用于取消订阅；若不提供则使用 callback 的 __name__
        :param priority: 优先级，数字越小越先执行
        :return: 是否订阅成功
        """
        if identifier is None:
            identifier = getattr(callback, '__name__', 'anonymous_listener')
            
        # 检查是否已经存在相同标识的监听器
        for _, existing_id, _ in self._listeners[event_name]:
            if existing_id == identifier:
                self._logger.warning("Listener '%s' already subscribed to event '%s', skipping.", identifier, event_name)
                return False
                
        # 检查监听器数量限制
        if len(self._listeners[event_name]) >= self._config.get("max_listeners_per_event", 100):
            self._logger.error("Max listeners reached for event '%s', cannot subscribe listener '%s'.", event_name, identifier)
            return False
            
        # 添加监听器
        self._listeners[event_name].append((priority, identifier, callback))
        # 按优先级排序（稳定性排序，新增的每次插入后排序）
        self._listeners[event_name].sort(key=lambda x: x[0])
        
        self._logger.info("Listener '%s' subscribed to event '%s' with priority %d.", identifier, event_name, priority)
        return True
        
    def unsubscribe(self, event_name: str, identifier: str) -> bool:
        """
        取消订阅，移除监听器
        :param event_name: 事件名称
        :param identifier: 监听器标识
        :return: 是否成功移除
        """
        listeners = self._listeners[event_name]
        for i, (_, lid, _) in enumerate(listeners):
            if lid == identifier:
                removed = listeners.pop(i)
                self._logger.info("Listener '%s' unsubscribed from event '%s'.", identifier, event_name)
                return True
        self._logger.warning("Listener '%s' not found for event '%s'.", identifier, event_name)
        return False
        
    def publish(self, event_name: str, *args: Any, **kwargs: Any) -> None:
        """
        发布事件，触发所有订阅该事件的监听器
        :param event_name: 事件名称
        :param args: 位置参数传递给回调
        :param kwargs: 关键字参数传递给回调
        """
        if self._config.get("log_events", True):
            self._logger.debug("Publishing event '%s' with args=%s kwargs=%s", event_name, args, kwargs)
            
        listeners = self._listeners[event_name]
        # 遍历排序后的监听器列表
        for priority, identifier, callback in listeners:
            try:
                self._logger.debug("Calling listener '%s' for event '%s' (priority %d)", identifier, event_name,