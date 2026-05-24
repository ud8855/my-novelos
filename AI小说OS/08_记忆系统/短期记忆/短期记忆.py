#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NovelOS 短期记忆模块 (ShortTermMemory)
所属层级：08_记忆系统
依赖：无外部模块，仅依赖Python标准库
被调用：由 07_核心引擎/ 调用，用于存储临时上下文，供后续推理使用。
解决问题：以可插拔方式管理短时对话、情节片段等临时信息，支持超时淘汰、容量限制、配置化。
"""

import time
import threading
import logging
import json
import os
from collections import OrderedDict

# 配置默认值
DEFAULT_CONFIG = {
    "capacity": 100,               # 最大记忆条数
    "ttl": 600,                    # 记忆生存时间（秒），0表示永不超时
    "cleanup_interval": 60,        # 自动清理间隔（秒）
    "enable_auto_cleanup": True,   # 是否启用自动清理线程
    "log_level": "INFO"            # 日志级别
}

class ShortTermMemory:
    """
    短期记忆核心类
    提供基于容量的LRU-like淘汰 + TTL超时的短期存储。
    可插拔：通过配置文件或参数注入实现策略替换。
    """

    def __init__(self, config=None):
        """
        初始化短期记忆模块
        :param config: 配置字典，与DEFAULT_CONFIG合并
        """
        # 加载配置
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)

        # 初始化日志
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, self.config["log_level"].upper(), logging.INFO))
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # 核心存储结构：OrderedDict保持插入顺序，方便LRU
        self._storage = OrderedDict()
        # 记录插入时间
        self._timestamps = {}
        # 线程锁保证线程安全
        self._lock = threading.RLock()

        # 自动清理线程
        self._cleanup_thread = None
        self._stop_event = threading.Event()
        if self.config["enable_auto_cleanup"]:
            self._start_auto_cleanup()

        self.logger.info(f"ShortTermMemory initialized with config: {self.config}")

    def _start_auto_cleanup(self):
        """启动后台自动清理线程"""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
        self._stop_event.clear()
        self._cleanup_thread = threading.Thread(
            target=self._auto_cleanup_loop,
            daemon=True,
            name="STM-Cleaner"
        )
        self._cleanup_thread.start()
        self.logger.info("Auto-cleanup thread started.")

    def _auto_cleanup_loop(self):
        """自动清理循环，定期移除过期条目"""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self.config["cleanup_interval"])
            if not self._stop_event.is_set():
                self._remove_expired()

    def _remove_expired(self):
        """移除所有过期的记忆条目"""
        with self._lock:
            if self.config["ttl"] <= 0:
                return
            now = time.time()
            expired_keys = [
                key for key, ts in self._timestamps.items()
                if now - ts > self.config["ttl"]
            ]
            for key in expired_keys:
                self._storage.pop(key, None)
                self._timestamps.pop(key, None)
            if expired_keys:
                self.logger.debug(f"Removed {len(expired_keys)} expired memories.")

    def _evict_if_needed(self):
        """
        如果超出容量，执行淘汰策略：移除最旧的条目（LRU）
        """
        while len(self._storage) > self.config["capacity"]:
            # OrderedDict popitem(last=False) 移除最早插入的条目
            key, value = self._storage.popitem(last=False)
            self._timestamps.pop(key, None)
            self.logger.debug(f"Evicted memory key: {key} due to capacity limit.")

    def store(self, key: str, data: object) -> bool:
        """
        存储一条短期记忆
        :param key: 唯一标识字符串
        :param data: 可序列化的数据对象
        :return: 是否成功
        """
        with self._lock:
            try:
                # 如果key已存在，先移除旧的时间戳
                if key in self._storage:
                    # 移动位置：先删除再插入，使其成为最新
                    del self._storage[key]
                    del self._timestamps[key]
                self._storage[key] = data
                self._timestamps[key] = time.time()
                # 检查容量并淘汰
                self._evict_if_needed()
                self.logger.debug(f"Stored memory: {key}")
                return True
            except Exception as e:
                self.logger.error(f"Failed to store memory {key}: {e}")
                return False

    def retrieve(self, key: str) -> object:
        """
        根据key获取记忆，并更新时间戳（保持活跃）
        :param key: 键
        :return: 数据对象，不存在则返回None
        """
        with self._lock:
            if key not in self._storage:
                return None
            # 检查是否过期
            if self.config["ttl"] > 0:
                elapsed = time.time() - self._timestamps[key]
                if elapsed > self.config["ttl"]:
                    # 过期清理
                    del self._storage[key]
                    del self._timestamps[key]
                    self.logger.debug(f"Memory {key} expired on access.")
                    return None
            # 更新时间戳，并移动到末尾（LRU更新）
            data = self._storage.pop(key)
            self._storage[key] = data
            self._timestamps[key] = time.time()
            self.logger.debug(f"Retrieved memory: {key}")
            return data

    def forget(self, key: str) -> bool:
        """
        主动遗忘指定记忆
        :param key: 键
        :return: 是否成功移除
        """
        with self._lock:
            if key in self._storage:
                del self._storage[key]
                del self._timestamps[key]
                self.logger.debug(f"Forgot memory: {key}")
                return True
            return False

    def clear(self):
        """清空所有短期记忆"""
        with self._lock:
            self._storage.clear()
            self._timestamps.clear()
            self.logger.info("All short-term memories cleared.")

    def snapshot(self) -> dict:
        """
        获取当前所有有效记忆的快照（浅拷贝）
        :return: 字典 {key: data}
        """
        with self._lock:
            # 先清理过期条目
            self._remove_expired()
            return dict(self._storage)

    def shutdown(self):
        """关闭短期记忆模块，停止后台线程"""
        self.logger.info("Shutting down ShortTermMemory...")
        self._stop_event.set()
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=2)
        self.logger.info("ShortTermMemory shut down.")


# 自测代码
if __name__ == "__main__":
    # 配置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 测试1：基本存储与检索
    stm = ShortTermMemory({"capacity": 3, "ttl": 2, "cleanup_interval": 1, "enable_auto_cleanup": True})
    stm.store("key1", "data1")
    stm.store("key2", {"nested": True})
    assert stm.retrieve("key1") == "data1"
    assert stm.retrieve("key2") == {"nested": True}
    print("Test 1 passed: basic store/retrieve")

    # 测试2：容量淘汰
    stm.store("key3", "data3")
    stm.store("key4", "data4")  # 应淘汰最早插入的key1
    assert stm.retrieve("key1") is None
    assert stm.retrieve("key4") == "data4"
    print("Test 2 passed: capacity eviction")

    # 测试3：TTL过期
    import time as t
    stm.store("temp", "will_expire")
    t.sleep(3)  # 等待TTL超时 (ttl=2)
    assert stm.retrieve("temp") is None
    print("Test 3 passed: TTL expiration")

    # 测试4：主动遗忘
    stm.store("del_me", 123)
    stm.forget("del_me")
    assert stm.retrieve("del_me") is None
    print("Test 4 passed: forget")

    # 测试5：snapshot
    stm.clear()
    stm.store("a", 1)
    stm.store("b", 2)
    snap = stm.snapshot()
    assert snap == {"a": 1, "b": 2}
    print("Test 5 passed: snapshot")

    # 测试6：LRU更新 (通过retrieve刷新)
    stm2 = ShortTermMemory({"capacity": 2, "ttl": 100, "enable_auto_cleanup": False})
    stm2.store("x", 1)
    stm2.store("y", 2)
    stm2.retrieve("x")    # 使x成为最新
    stm2.store("z", 3)    # 容量满，应淘汰最旧的 y
    assert stm2.retrieve("y") is None
    assert stm2.retrieve("x") == 1
    print("Test 6 passed: LRU update on retrieve")

    # 清理线程
    stm.shutdown()
    stm2.shutdown()
    print("All tests passed. ShortTermMemory works correctly.")