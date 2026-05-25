#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Runtime调度模块 - 任务调度核心
层级: 04_Runtime运行时
依赖: 日志系统(07_日志与监控), 配置系统(05_配置与状态)
被谁调用: Runtime管理器(04_Runtime运行时主模块), 各个Agent
解决: 统一的任务调度，支持可插拔调度策略，日志记录，热更新
"""

import logging
import time
import threading
import queue
from abc import ABC, abstractmethod
from typing import Callable, Any, Dict, List, Optional

# 默认配置，可被外部覆盖
DEFAULT_CONFIG = {
    "max_workers": 5,
    "default_priority": 10,
    "scheduler_type": "priority",  # 可选: "priority", "fifo", "round_robin"
    "poll_interval": 0.1,          # 调度循环间隔(秒)
}


class Scheduler(ABC):
    """调度器抽象基类，定义调度接口"""
    @abstractmethod
    def add_job(self, func: Callable, *args, priority: int = None, **kwargs) -> str:
        """添加任务，返回任务ID"""
        pass

    @abstractmethod
    def remove_job(self, job_id: str) -> bool:
        """移除任务"""
        pass

    @abstractmethod
    def start(self):
        """启动调度器"""
        pass

    @abstractmethod
    def stop(self):
        """停止调度器"""
        pass

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """获取调度器状态"""
        pass


class PriorityScheduler(Scheduler):
    """基于优先级的任务调度器实现"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)

        self.logger = logging.getLogger("Runtime调度.PriorityScheduler")
        self.logger.info("初始化优先级调度器，配置: %s", self.config)

        self._job_queue = queue.PriorityQueue()
        self._jobs = {}  # job_id -> (func, args, kwargs, priority)
        self._lock = threading.Lock()
        self._running = False
        self._workers = []
        self._next_job_id = 0

    def _get_next_id(self) -> str:
        with self._lock:
            self._next_job_id += 1
            return f"job_{self._next_job_id}"

    def add_job(self, func: Callable, *args, priority: int = None, **kwargs) -> str:
        if priority is None:
            priority = self.config["default_priority"]
        job_id = self._get_next_id()

        with self._lock:
            self._jobs[job_id] = (func, args, kwargs, priority)
            self._job_queue.put((priority, job_id))

        self.logger.debug("添加任务 ID=%s, 优先级=%d", job_id, priority)
        return job_id

    def remove_job(self, job_id: str) -> bool:
        with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                self.logger.debug("移除任务 ID=%s", job_id)
                return True
        return False

    def start(self):
        if self._running:
            self.logger.warning("调度器已在运行")
            return
        self._running = True
        max_workers = self.config["max_workers"]
        self.logger.info("启动调度器，工作线程数: %d", max_workers)

        for i in range(max_workers):
            t = threading.Thread(target=self._worker_loop, name=f"SchedulerWorker-{i}", daemon=True)
            t.start()
            self._workers.append(t)

    def stop(self):
        self._running = False
        self.logger.info("正在停止调度器...")
        for t in self._workers:
            t.join(timeout=5)
        self._workers.clear()
        self.logger.info("调度器已停止")

    def _worker_loop(self):
        while self._running:
            try:
                try:
                    priority, job_id = self._job_queue.get(timeout=self.config["poll_interval"])
                except queue.Empty:
                    continue

                with self._lock:
                    job_info = self._jobs.get(job_id)
                    if job_info is None:
                        continue

                func, args, kwargs, _ = job_info
                self.logger.debug("执行任务 ID=%s", job_id)
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    self.logger.error("任务 %s 执行失败: %s", job_id, e, exc_info=True)
                finally:
                    self._job_queue.task_done()
                    with self._lock:
                        if job_id in self._jobs:
                            del self._jobs[job_id]
            except Exception:
                self.logger.exception("工作线程异常")

    def get_status(self) -> Dict[str, Any