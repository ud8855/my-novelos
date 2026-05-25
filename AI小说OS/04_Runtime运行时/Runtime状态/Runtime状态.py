# -*- coding: utf-8 -*-
"""
模块路径：04_Runtime运行时/Runtime状态/Runtime状态.py
层级：Runtime运行时层
职责：管理整个系统的运行时状态，提供线程安全的状态存储、查询、快照及变更通知。
依赖：标准库 logging, threading, copy, json, os；可选 yaml（配置加载）。
被调用：由 Runtime引擎 或 其他需要访问全局状态的模块调用。
可插拔：通过 RuntimeStateBase 抽象接口实现插拔，当前提供默认实现。
日志：使用 Python logging，所有关键操作记录 INFO 及以上日志，异常记录 ERROR。
配置化：支持从字典或 YAML 配置文件初始化，默认配置内置于类变量 DEFAULT_CONFIG。
自测：模块末尾包含 __main__ 自测代码。
"""

import logging
import threading
import copy
import json
import os
from typing import Any, Callable, Dict, List, Optional

try:
    import yaml
except ImportError:
    yaml = None  # 配置文件为可选依赖

# ------------------------------
# 抽象接口（可插拔定义）
# ------------------------------
class RuntimeStateBase:
    """运行时状态抽象接口，所有具体实现需继承此类。"""
    def set(self, key: str, value: Any) -> None:
        raise NotImplementedError

    def get(self, key: str, default: Any = None) -> Any:
        raise NotImplementedError

    def update(self, mapping: Dict[str, Any]) -> None:
        raise NotImplementedError

    def snapshot(self) -> Dict[str, Any]:
        raise NotImplementedError

    def subscribe(self, event: str, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        raise NotImplementedError

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


# ------------------------------
# 默认实现
# ------------------------------
class RuntimeState(RuntimeStateBase):
    """
    运行时状态管理器（线程安全，支持事件订阅）。
    作为全局单例或通过工厂创建，确保整个应用使用同一状态中心。
    """

    DEFAULT_CONFIG = {
        "enable_persistence": False,
        "persistence_path": "./runtime_state_snapshot.json",
        "lock_timeout": 5
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化状态管理器。
        :param config: 配置字典，如果为 None 则使用默认配置。
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self._lock = threading.RLock()
        self._state: Dict[str, Any] = {}
        self._subscribers: Dict[str, List[Callable]] = {}
        self._active = False

        # 加载配置
        self.config = self._load_config(config)
        self._logger.info("RuntimeState 初始化完成，配置：%s", self.config)

    def _load_config(self, config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """加载并合并配置：优先使用传入字典，其次从配置文件（若启用）加载，最后使用默认值。"""
        final_config = copy.deepcopy(self.DEFAULT_CONFIG)
        if config:
            final_config.update(config)
        # 如果指定了配置文件路径，尝试读取 YAML 或 JSON
        config_file = final_config.get("config_file")
        if config_file and os.path.exists(config_file):
            try:
                if yaml and config_file.endswith((".yaml", ".yml")):
                    with open(config_file, "r", encoding="utf-8") as f:
                        file_conf = yaml.safe_load(f)
                elif config_file.endswith(".json"):
                    with open(config_file, "r", encoding="utf-8") as f:
                        file_conf = json.load(f)
                else:
                    self._logger.warning("不支持的配置文件格式，将忽略: %s", config_file)
                    file_conf = {}
                final_config.update(file_conf)
                self._logger.info("已从配置文件加载配置：%s", config_file)
            except Exception as e:
                self._logger.error("加载配置文件失败: %s", e)
        return final_config

    # ---------- 基础状态操作 ----------
    def set(self, key: str, value: Any) -> None:
        """设置状态键值（线程安全）"""
        if not self._active:
            raise RuntimeError("RuntimeState 未启动，无法写入状态")
        with self._lock:
            old_value = self._state.get(key)
            self._state[key] = value
            self._logger.debug("状态变更: key=%s, old=%s, new=%s", key, old_value, value)
            self._notify("state_changed", {"key": key, "old_value": old_value, "new_value": value})

    def get(self, key: str, default: Any = None) -> Any:
        """获取状态值（线程安全）"""
        with self._lock:
            value = self._state.get(key, default)
            self._logger.debug("状态读取: key=%s, value=%s", key, value)
            return value

    def update(self, mapping: Dict[str, Any]) -> None:
        """批量更新状态（原子操作）"""
        if not mapping:
            return
        if not self._active:
            raise RuntimeError("RuntimeState 未启动，无法批量更新")
        with self._lock:
            for k, v in mapping.items():
                old = self._state.get(k)
                self._state[k] = v
                self._logger.debug("批量状态变更: key=%s, old=%s, new=%s", k, old, v)
            self._notify("state_batch_updated", {"keys": list(mapping.keys())})

    def snapshot(self) -> Dict[str, Any]:
        """返回当前状态的深拷贝（线程安全）"""
        with self._lock:
            snap = copy.deepcopy(self._state)
            self._logger.debug("状态快照创建，包含 %d 个键", len(snap))
            return snap

    # ---------- 事件订阅 ----------
    def subscribe(self, event: str, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """
        订阅事件。
        :param event: 事件名称，如 'state_changed', 'state_batch_updated'
        :param callback: 回调函数，接收 event_name 和 data 字典
        """
        with self._lock:
            if event not in self._subscribers:
                self._subscribers[event] = []
            self._subscribers[event].append(callback)
            self._logger.info("新增事件订阅: event=%s, 当前订阅者数量=%d", event, len(self._subscribers[event]))

    def _notify(self, event: str, data: Dict[str, Any]) -> None:
        """通知所有订阅者（需持有锁？此处由 set/update 调用时已持有锁，故不加锁以避免死锁）"""
        callbacks = self._subscribers.get(event, [])
        if not callbacks:
            return
        self._logger.debug("触发事件: %s, 数据: %s, 通知 %d 个订阅者", event, data, len(callbacks))
        for cb in callbacks:
            try:
                cb(event, data)
            except Exception as e:
                self._logger.error("事件回调异常: event=%s, callback=%s, error=%s", event, cb, e)

    # ---------- 生命周期 ----------
    def start(self) -> None:
        """启动状态管理器，可用于加载持久化状态（如果配置启用）"""
        with self._lock:
            if self._active:
                self._logger.warning("RuntimeState 已经处于启动状态")
                return
            if self.config.get("enable_persistence"):
                self._load_persisted_state()
            self._active = True
            self._logger.info("RuntimeState 已启动")

    def stop(self) -> None:
        """停止状态管理器，可选择持久化当前状态（如果配置启用）"""
        with self._lock:
            if not self._active:
                self._logger.warning("RuntimeState 已处于停止状态")
                return
            if self.config.get("enable_persistence"):
                self._save_persisted_state()
            self._active = False
            self._logger.info("RuntimeState 已停止")

    def _load_persisted_state(self) -> None:
        """从文件加载持久化状态（未加锁，需在持有锁时调用）"""
        path = self.config["persistence_path"]
        if not os.path.exists(path):
            self._logger.info("持久化文件不存在，跳过加载: %s", path)
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._state.update(data)
                self._logger.info("从 %s 加载了 %d 个状态键", path, len(data))
            else:
                self._logger.error("持久化文件格式异常，非字典结构")
        except Exception as e:
            self._logger.error("加载持久化状态失败: %s", e)

    def _save_persisted_state(self) -> None:
        """保存当前状态到文件（未加锁，需在持有锁时调用）"""
        path = self.config["persistence_path"]
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
            self._logger.info("持久化状态已保存至 %s，键数 %d", path, len(self._state))
        except Exception as e:
            self._logger.error("保存持久化状态失败: %s", e)


# ------------------------------
# 自测
# ------------------------------
if __name__ == "__main__":
    # 配置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # 实例化 RuntimeState
    state = RuntimeState({"enable_persistence": False})

    # 测试启动和停止
    state.start