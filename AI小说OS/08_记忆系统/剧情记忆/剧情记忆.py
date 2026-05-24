# -*- coding: utf-8 -*-
"""
剧情记忆模块
所属层级：08_记忆系统
功能：存储和管理小说的剧情发展记忆（事件、因果、人物关联等）
依赖：配置中心、日志系统
被调用：AI写作Agent、情节规划器、角色记忆模块等
设计原则：可插拔（抽象接口 + 多实现）、配置化、日志记录、单一职责
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import os
import json


# ---------- 配置 ----------
class PlotMemoryConfig:
    """剧情记忆配置（可插拔配置源）"""
    def __init__(self, config_source: Optional[Dict[str, Any]] = None):
        # 默认从环境变量/配置文件读取，也可传入字典覆盖
        self.memory_backend = os.getenv("PLOT_MEMORY_BACKEND", "in_memory")
        self.persist_path = os.getenv("PLOT_MEMORY_PERSIST_PATH", "./data/plot_memory.json")
        self.max_events_per_context = int(os.getenv("PLOT_MEMORY_MAX_EVENTS", "100"))
        self.log_level = os.getenv("PLOT_MEMORY_LOG_LEVEL", "INFO")
        # 覆盖配置
        if config_source:
            for key, value in config_source.items():
                setattr(self, key, value)


# ---------- 日志配置 ----------
def _init_logger(config: PlotMemoryConfig):
    logger = logging.getLogger("PlotMemory")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(name)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))
    return logger


# ---------- 剧情记忆抽象接口 ----------
class PlotMemoryInterface(ABC):
    """
    剧情记忆抽象接口
    所有具体实现必须继承此类，保证可插拔
    """

    @abstractmethod
    def store_event(self, event: Dict[str, Any]) -> str:
        """
        存储一个剧情事件
        :param event: 事件字典，必须包含 'event_id', 'type', 'description', 'timestamp'
        :return: 事件ID
        """
        pass

    @abstractmethod
    def query_events(self, filters: Optional[Dict[str, Any]] = None,
                     limit: int = 10) -> List[Dict[str, Any]]:
        """
        按条件查询历史事件
        :param filters: 过滤条件
        :param limit: 最大返回数量
        :return: 事件列表
        """
        pass

    @abstractmethod
    def get_plot_context(self, context_size: int = 5) -> List[Dict[str, Any]]:
        """
        获取最近的关键剧情上下文（用于喂给AI模型）
        :param context_size: 返回事件数量
        :return: 紧凑的剧情上下文列表
        """
        pass

    @abstractmethod
    def update_memory(self, event_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新已有事件记忆
        :param event_id: 事件ID
        :param updates: 要更新的字段
        :return: 是否成功
        """
        pass

    @abstractmethod
    def clear_memory(self, before_timestamp: Optional[float] = None) -> int:
        """
        清空剧情记忆（可指定时间戳之前的记忆）
        :param before_timestamp: 清除早于该时间戳的事件
        :return: 清除的事件数量
        """
        pass

    @abstractmethod
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取记忆统计信息（事件数、类型分布等）
        :return: 统计字典
        """
        pass


# ---------- 内存实现（默认） ----------
class InMemoryPlotMemory(PlotMemoryInterface):
    """
    基于内存的剧情记忆实现（支持持久化到JSON文件）
    支持热更新、异常恢复、日志
    """

    def __init__(self, config: PlotMemoryConfig):
        self.config = config
        self.logger = _init_logger(config)
        self._events: Dict[str, Dict[str, Any]] = {}
        self._event_order: List[str] = []  # 保持插入顺序
        self._load_from_disk()  # 热恢复
        self.logger.info(f"InMemoryPlotMemory initialized with {len(self._events)} events from disk")

    def _load_from_disk(self):
        """从磁盘加载持久化数据（异常恢复）"""
        if not os.path.exists(self.config.persist_path):
            return
        try:
            with open(self.config.persist_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and "events" in data:
                self._events = data["events"]
                self._event_order = data.get("order", list(self._events.keys()))
            self.logger.info("记忆数据已从磁盘恢复")
        except Exception as e:
            self.logger.error(f"加载持久化记忆失败: {e}，使用空记忆")

    def _save_to_disk(self):
        """持久化到磁盘（异常安全）"""
        try:
            os.makedirs(os.path.dirname(self.config.persist_path), exist_ok=True)
            with open(self.config.persist_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "events": self._events,
                    "order": self._event_order
                }, f, ensure_ascii=False, indent=2)
            self.logger.debug("记忆已持久化")
        except Exception as e:
            self.logger.error(f"持久化记忆失败: {e}")

    def store_event(self, event: Dict[str, Any]) -> str:
        event_id = event.get("event_id")
        if not event_id:
            event_id = f"evt_{datetime.now().timestamp()}_{id(event)}"
            event["event_id"] = event_id
        if "timestamp" not in event:
            event["timestamp"] = datetime.now().isoformat()
        # 存储
        self._events[event_id] = event
        if event_id not in self._event_order:
            self._event_order.append(event_id)
        # 限制记忆大小
        if len(self._event_order) > self.config.max_events_per_context * 2:
            # 移除最旧的一半
            remove_count = len(self._event_order) - self.config.max_events_per_context
            for old_id in self._event_order[:remove_count]:
                del self._events[old_id]
            self._event_order = self._event_order[remove_count:]
        self._save_to_disk()
        self.logger.debug(f"存储事件: {event_id}")
        return event_id

    def query_events(self, filters: Optional[Dict[str, Any]] = None,
                     limit: int = 10) -> List[Dict[str, Any]]:
        results = []
        for evt_id in self._event_order:
            evt = self._events[evt_id]
            if filters:
                match = True
                for key, value in filters.items():
                    if evt.get(key) != value:
                        match = False
                        break
                if not match:
                    continue
            results.append(evt)
        # 返回最近的limit个
        return results[-limit:]

    def get_plot_context(self, context_size: int = 5) -> List[Dict[str, Any]]:
        # 返回最近的关键事件（可根据类型过滤，这里简化返回最后几个）
        recent = self._event_order[-context_size:]
        return [self._events[eid] for eid in recent if eid in self._events]

    def update_memory(self, event_id: str, updates: Dict[str, Any]) -> bool:
        if event_id not in self._events:
            self.logger.warning(f"事件ID不存在: {event_id}")
            return False
        self._events[event_id].update(updates)
        self._save_to_disk()
        self.logger.debug(f"更新事件: {event_id} 字段: {list(updates.keys())}")
        return True

    def clear_memory(self, before_timestamp: Optional[float] = None) -> int:
        if before_timestamp is None:
            count = len(self._events)
            self._events.clear()
            self._event_order.clear()
            self._save_to_disk()
            self.logger.info(f"清除全部记忆，共 {count} 条")
            return count
        remove_ids = []
        for eid in self._event_order:
            evt = self._events[eid]
            ts = evt.get("timestamp")
            if ts:
                try:
                    if isinstance(ts, str):
                        ts_float = datetime.fromisoformat(ts).timestamp()
                    else:
                        ts_float = float(ts)
                    if ts_float < before_timestamp:
                        remove_ids.append(eid)
                except Exception:
                    pass
        for eid in remove_ids:
            del self._events[eid]
        self._event_order = [eid for eid in self._event_order if eid not in remove_ids]
        self._save_to_disk()
        self.logger.info(f"清除 {len(remove_ids)} 条早于 {before_timestamp} 的记忆")
        return len(remove_ids)

    def get_statistics(self) -> Dict[str, Any]:
        type_counts = {}
        for evt in self._events.values():
            t = evt.get("type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "total_events": len(self._events),
            "type_distribution": type_counts,
            "oldest_timestamp": self._events[self._event_order[0]]["timestamp"] if self._event_order else None,
            "newest_timestamp": self._events[self._event_order[-1]]["timestamp"] if self._event_order else None,
        }


# ---------- 工厂函数（可插拔入口） ----------
def create_plot_memory(config: Optional[PlotMemoryConfig] = None) -> PlotMemoryInterface:
    """
    剧情记忆工厂，根据配置动态创建实例
    :param config: 配置对象，默认从环境变量生成
    :return: PlotMemoryInterface 实现
    """
    if config is None:
        config = PlotMemoryConfig()
    backend = config.memory_backend
    if backend == "in_memory":
        return InMemoryPlotMemory(config)
    else:
        raise ValueError(f"不支持的剧情记忆后端: {backend}")


# ---------- 自测 ----------
if __name__ == "__main__":
    # 基础自测：创建内存记忆，存储/查询/统计
    config = PlotMemoryConfig({
        "memory_backend": "in_memory",
        "log_level": "DEBUG"
    })
    memory = create_plot_memory(config)

    # 插入事件
    memory.store_event({
        "event_id": "evt_001",
        "type": "plot_twist",
        "description": "主角发现隐藏的秘密",
        "characters": ["主角", "反派"],
        "location": "古堡"
    })
    memory.store_event({
        "event_id": "evt_002",
        "type": "dialogue",
        "description": "关键对话",
        "characters": ["主角", "导师"],
        "location": "山洞"
    })

    # 查询
    print("查询所有事件：")
    for e in memory.query_events(limit=10):
        print(f"  {e['event_id']}: {e['description']}")

    # 上下文
    ctx = memory.get_plot_context(context_size=2)
    print("剧情上下文：", ctx)

    # 更新
    memory.update_memory("evt_001", {"importance": "high"})
    print("更新后 evt_001:", memory.query_events(filters={"event_id": "evt_001"}))

    # 统计
    stats = memory.get_stat