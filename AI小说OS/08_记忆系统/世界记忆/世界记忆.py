# -*- coding: utf-8 -*-
"""
世界记忆模块 (WorldMemory)
所属层级: 08_记忆系统
依赖: 无外部模块 (可选依赖配置管理器)
被调用方: 更高层级的主控模块、叙事引擎、Agent协调器等
功能: 存储、检索、管理小说世界观中的公共知识、历史事件、全局设定等永久性信息。
      提供可插拔的实现接口，支持多种后端（内存 / 文件 / 数据库），当前默认使用内存实现。
      所有方法具备异常恢复和详细日志记录，支持热更新（运行时切换后端）与配置化。
"""

import logging
import copy
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

# ────────────── 配置 ──────────────
@dataclass
class WorldMemoryConfig:
    """世界记忆模块的配置类，集中管理所有可调参数。"""
    # 存储后端类型: "memory", "json", "sqlite" 等
    backend: str = "memory"
    # 内存模式下的初始容量（可选扩展）
    initial_capacity: int = 1000
    # 是否启用冗余备份（用于异常恢复）
    auto_backup: bool = True
    # 备份间隔（秒），仅当后端支持时生效
    backup_interval: int = 300
    # 日志级别
    log_level: str = "INFO"
    # 其他扩展参数（不同后端使用）
    extra_params: Dict[str, Any] = field(default_factory=dict)

# ────────────── 抽象基类（可插拔接口） ──────────────
class BaseWorldMemory(ABC):
    """
    世界记忆的抽象接口。
    所有具体实现必须继承此类并实现全部抽象方法。
    确保不同存储后端可以无缝替换。
    """
    def __init__(self, config: WorldMemoryConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        # 初始化日志级别
        logging.basicConfig(level=getattr(logging, config.log_level, logging.INFO))
        self.logger.info(f"{self.__class__.__name__} 初始化，配置: {config}")

    @abstractmethod
    def store_fact(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        存储一条世界事实。
        Args:
            key: 唯一标识符（建议使用层次化命名，如 "world.geography.capital"）
            value: 事实内容（可序列化的任意类型）
            metadata: 附加元数据（时间戳、来源、可信度等）
        Returns:
            是否存储成功
        """
        ...

    @abstractmethod
    def retrieve_fact(self, key: str) -> Optional[Any]:
        """
        根据键检索一条世界事实。
        Args:
            key: 事实唯一标识符
        Returns:
            找到的事实值，若不存在返回None
        """
        ...

    @abstractmethod
    def update_fact(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        更新已有事实（若key不存在则创建）。
        Args:
            key: 事实唯一标识符
            value: 新的事实值
            metadata: 合并或替换的元数据
        Returns:
            是否更新成功
        """
        ...

    @abstractmethod
    def delete_fact(self, key: str) -> bool:
        """
        删除一条世界事实。
        Args:
            key: 事实唯一标识符
        Returns:
            是否删除成功
        """
        ...

    @abstractmethod
    def query(self, pattern: str) -> List[Dict[str, Any]]:
        """
        根据模式查询匹配的事实列表（支持通配符、前缀匹配等）。
        Args:
            pattern: 查询模式（具体语法由实现定义）
        Returns:
            匹配的事实条目列表，每个条目包含 "key", "value", "metadata"
        """
        ...

    @abstractmethod
    def dump_memory(self) -> Dict[str, Any]:
        """
        导出全部记忆内容，用于备份或热迁移。
        Returns:
            包含所有事实的完整字典，键为fact key，值为包含value和metadata的字典。
        """
        ...

    @abstractmethod
    def load_memory(self, data: Dict[str, Any]) -> bool:
        """
        从导出的数据恢复记忆（可热切换）。
        Args:
            data: dump_memory 产生的字典
        Returns:
            是否加载成功
        """
        ...

    @abstractmethod
    def clear_memory(self) -> bool:
        """
        清空所有记忆（谨慎操作）。
        Returns:
            是否清空成功
        """
        ...

# ────────────── 默认内存实现 ──────────────
class InMemoryWorldMemory(BaseWorldMemory):
    """基于内存的轻量级世界记忆实现，适用于原型开发和快速测试。"""
    def __init__(self, config: WorldMemoryConfig):
        super().__init__(config)
        # 内部存储：键 -> {"value": value, "metadata": metadata}
        self._store: Dict[str, Dict[str, Any]] = {}
        self.logger.info("InMemoryWorldMemory 内存存储初始化完成。")

    def store_fact(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> bool:
        try:
            if key in self._store:
                self.logger.warning(f"键 '{key}' 已存在，使用 update_fact 或先删除。将覆盖存储。")
            self._store[key] = {
                "value": copy.deepcopy(value),  # 深拷贝防止外部修改污染
                "metadata": copy.deepcopy(metadata) if metadata else {}
            }
            self.logger.debug(f"存储事实: {key} = {value}")
            return True
        except Exception as e:
            self.logger.error(f"存储事实失败 [{key}]: {e}", exc_info=True)
            return False

    def retrieve_fact(self, key: str) -> Optional[Any]:
        try:
            if key in self._store:
                return copy.deepcopy(self._store[key]["value"])
            self.logger.debug(f"检索事实 '{key}' 不存在。")
            return None
        except Exception as e:
            self.logger.error(f"检索事实失败 [{key}]: {e}", exc_info=True)
            return None

    def update_fact(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> bool:
        try:
            if key not in self._store:
                self.logger.info(f"键 '{key}' 不存在，将作为新事实存储。")
                return self.store_fact(key, value, metadata)
            old_entry = self._store[key]
            old_entry["value"] = copy.deepcopy(value)
            if metadata is not None:
                # 合并元数据：新metadata覆盖或合并（这里简单覆盖）
                merged = copy.deepcopy(old_entry["metadata"])
                merged.update(metadata)
                old_entry["metadata"] = merged
            self.logger.debug(f"更新事实: {key} -> {value}")
            return True
        except Exception as e:
            self.logger.error(f"更新事实失败 [{key}]: {e}", exc_info=True)
            return False

    def delete_fact(self, key: str) -> bool:
        try:
            if key in self._store:
                del self._store[key]
                self.logger.debug(f"删除事实: {key}")
                return True
            else:
                self.logger.warning(f"尝试删除不存在的键: {key}")
                return False
        except Exception as e:
            self.logger.error(f"删除事实失败 [{key}]: {e}", exc_info=True)
            return False

    def query(self, pattern: str) -> List[Dict[str, Any]]:
        results = []
        # 简单实现：pattern可以是前缀或通配符 '*', '前缀*'
        # 此处实现最简单的全字匹配和前缀匹配
        try:
            if pattern.endswith("*"):
                prefix = pattern[:-1]
                for k, v in self._store.items():
                    if k.startswith(prefix):
                        results.append({"key": k, "value": copy.deepcopy(v["value"]), "metadata": copy.deepcopy(v["metadata"])})
            else:
                # 精确匹配
                if pattern in self._store:
                    v = self._store[pattern]
                    results.append({"key": pattern, "value": copy.deepcopy(v["value"]), "metadata": copy.deepcopy(v["metadata"])})
            self.logger.debug(f"查询模式 '{pattern}' 返回 {len(results)} 条结果。")
        except Exception as e:
            self.logger.error(f"查询失败 [{pattern}]: {e}", exc_info=True)
        return results

    def dump_memory(self) -> Dict[str, Any]:
        try:
            # 深拷贝整个存储
            return copy.deepcopy(self._store)
        except Exception as e:
            self.logger.error(f"导出记忆失败: {e}", exc_info=True)
            return {}

    def load_memory(self, data: Dict[str, Any]) -> bool:
        try:
            if not isinstance(data, dict):
                raise ValueError("导入的数据必须为字典类型")
            self._store = copy.deepcopy(data)
            self.logger.info(f"成功从外部数据加载记忆，共 {len(self._store)} 条事实。")
            return True
        except Exception as e:
            self.logger.error(f"加载记忆失败: {e}", exc_info=True)
            return False

    def clear_memory(self) -> bool:
        try:
            self._store.clear()
            self.logger.info("所有世界记忆已清空。")
            return True
        except Exception as e:
            self.logger.error(f"清空记忆失败: {e}", exc_info=True)
            return False

# ────────────── 工厂函数（热插拔扩展点） ──────────────
def create_world_memory(config: Optional[WorldMemoryConfig] = None) -> BaseWorldMemory:
    """
    根据配置创建对应的世界记忆实例，用于实现运行时可切换。
    Args:
        config: 世界记忆配置对象，若未提供则使用默认配置
    Returns:
        BaseWorldMemory 的具体子类实例
    """
    if config is None:
        config = WorldMemoryConfig()
    backend = config.backend.lower()
    if backend == "memory":
        return InMemoryWorldMemory(config)
    elif backend == "json":
        # 未来扩展：基于JSON文件的后端
        raise NotImplementedError("JSON文件后端尚未实现")
    elif backend == "sqlite":
        raise NotImplementedError("SQLite后端尚未实现")
    else:
        raise ValueError(f"不支持的后端类型: {backend}")

# ────────────── 自测与演示 ──────────────
if __name__ == "__main__":
    # 配置测试
    config = WorldMemoryConfig(log_level="DEBUG")
    memory = create_world_memory(config)

    # 1. 存储事实
    memory.store_fact("world.geography.capital", "艾尔登城",
                      metadata={"source": "创世设定", "reliability": 0.95})
    memory.store_fact("world.history.war_1000", "千年纪战争结束了黑暗时代。",