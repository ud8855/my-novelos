""" 
模块：内核调度器 (KernelScheduler)
层级：03_内核系统
依赖：02_配置与日志 (log system, config), 可能依赖事件总线、插件管理器
被谁调用：系统启动脚本、核心容器、自适应循环
解决什么问题：统一调度和管理内核中各子系统的执行周期、任务队列、协程/线程调度；确保系统资源合理分配，保证各个Agent和引擎按照优先级和时间片运行；支持热插拔任务注册、动态调整调度策略。
"""

import logging
import threading
import time
import queue
import json
from pathlib import Path
from typing import Dict, Any, Callable, List, Optional, Union
from enum import Enum

# 配置与日志系统依赖（假设已存在，若不存在则使用默认）
try:
    from novelos.config import ConfigManager  # 虚构，占位
    from novelos.log_manager import get_logger
except ImportError:
    # 降级为内置简单实现
    import logging.config

    def get_logger(name: str) -> logging.Logger:
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
        return logger

    class ConfigManager:
        """临时配置管理器，用于骨架演示"""
        def __init__(self, config_path: Optional[str] = None):
            self.config = {"scheduler": {"tick_interval_sec": 0.1, "max_workers": 4, "task_priority_default": 5}}

        def get(self, section: str, key: str, default=None):
            return self.config.get(section, {}).get(key, default)


logger = get_logger("KernelScheduler")


class TaskPriority(Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


class ScheduledTask:
    """调度任务的抽象封装"""
    def __init__(self,
                 name: str,
                 func: Callable[[], None],
                 priority: TaskPriority = TaskPriority.NORMAL,
                 interval: float = 0.0,  # 0 表示一次性任务
                 args: tuple = (),
                 kwargs: dict = None):
        self.name = name
        self.func = func
        self.priority = priority
        self.interval = interval
        self.args = args
        self.kwargs = kwargs if kwargs is not None else {}
        self.last_run = 0.0
        self.enabled = True

    def should_run(self, now: float) -> bool:
        if not self.enabled:
            return False
        if self.interval <= 0:
            return self.last_run == 0.0  # 一次性仅运行一次
        return (now - self.last_run) >= self.interval

    def execute(self):
        logger.debug(f"执行任务: {self.name}")
        try:
            self.func(*self.args, **self.kwargs)
        except Exception as e:
            logger.error(f"任务 {self.name} 执行异常: {e}")
        self.last_run = time.time()


class KernelScheduler:
    """
    内核调度器
    - 基于优先级和定时间隔的任务调度循环
    - 支持动态注册/注销任务
    - 配置化参数（tick间隔、最大并发等）
    - 线程安全的运行与停止
    - 可插拔：可通过回调/插件机制扩展
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化调度器
        :param config: 配置字典或ConfigManager对象
        """
        self._lock = threading.RLock()
        self._running = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._config = self._load_config(config)
        self.tick_interval = self._config.get("tick_interval_sec", 0.2)
        self.max_workers = self._config.get("max_workers", 4)
        self._task_queue: queue.PriorityQueue = queue.PriorityQueue()
        self._permanent_tasks: List[ScheduledTask] = []
        self._one_shot_tasks: List[ScheduledTask] = []
        self._task_map: Dict[str, ScheduledTask] = {}
        self._worker_pool: Optional[threading.BoundedSemaphore] = None
        if self.max_workers > 0:
            self._worker_pool = threading.BoundedSemaphore(self.max_workers)
        logger.info(f"内核调度器初始化完成，配置: tick={self.tick_interval}s, workers={self.max_workers}")

    def _load_config(self, config) -> Dict[str, Any]:
        if isinstance(config, ConfigManager):
            # 假设配置管理器提供 get 方法
            return {
                "tick_interval_sec": config.get("scheduler", "tick_interval_sec", 0.2),
                "max_workers": config.get("scheduler", "max_workers", 4)
            }
        elif isinstance(config, dict):
            return config
        else:
            # 默认配置
            return {"tick_interval_sec": 0.2, "max_workers": 4}

    def register_task(self, task: ScheduledTask) -> bool:
        """
        注册一个调度任务（可永久执行、也可一次性）
        :param task:  ScheduledTask 实例
        :return: 是否成功
        """
        with self._lock:
            if task.name in self._task_map:
                logger.warning(f"任务 '{task.name}' 已存在，覆盖注册")
                self.unregister_task(task.name)
            self._task_map[task.name] = task
            if task.interval > 0:
                self._permanent_tasks.append(task)
            else:
                self._one_shot_tasks.append(task)
            # 立即尝试加入优先级队列（一次性任务首次调度）
            self._push_to_queue(task, immediate=True)
            logger.info(f"注册任务: {task.name}, priority={task.priority}, interval={task.interval}")
            return True

    def unregister_task(self, task_name: str) -> bool:
        """注销任务"""
        with self._lock:
            task = self._task_map.pop(task_name, None)
            if not task:
                logger.warning(f"任务 '{task_name}' 未找到，无法注销")
                return False
            if task in self._permanent_tasks:
                self._permanent_tasks.remove(task)
            if task in self._one_shot_tasks:
                self._one_shot_tasks.remove(task)
            task.enabled = False
            logger.info(f"注销任务: {task_name}")
            return True

    def _push_to_queue(self, task: ScheduledTask, immediate: bool = False):
        """将任务放入优先级队列"""
        now = time.time()
        if immediate or task.should_run(now):
            # 优先级：数字越小越优先？通常PriorityQueue使用最小堆，我们反转优先级数值
            # 让高数字（高优先级）先执行，使用负数
            priority_value = -task.priority.value
            self._task_queue.put((priority_value, time.time(), task))

    def _worker_execute(self, task: ScheduledTask):
        """执行单个任务，并释放worker信号量"""
        try:
            task.execute()
        finally:
            if self._worker_pool:
                self._worker_pool.release()

    def _scheduler_loop(self):
        """主调度循环，在独立线程中运行"""
        logger.info("调度器循环启动")
        next_tick = time.time() + self.tick_interval
        while not self._stop_event.is_set():
            now = time.time()
            # 遍历永久任务，推入应执行的任务
            with self._lock:
                for task in self._permanent_tasks:
                    if task.should_run(now):
                        self._push_to_queue(task, immediate=True)

            # 从队列中取出并执行任务（注意优先级）
            processed = False
            while not self._task_queue.empty() and not self._stop_event.is_set():
                try:
                    priority, enqueue_time, task = self._task_queue.get_nowait()
                except queue.Empty:
                    break
                if not task.enabled:
                    continue
                now = time.time()
                if task.interval > 0 and not task.should_run(now):
                    # 永久任务还没到执行时间，重新放回？忽略，因为上面推送已经判断了
                    continue
                # 尝试获取worker信号量
                if self._worker_pool:
                    acquired = self._worker_pool.acquire(blocking=False)
                    if not acquired:
                        # 工作线程已满，将任务放回队列稍后重试
                        self._task_queue.put((priority, now, task))
                        break
                    # 启动一个线程执行任务（或使用线程池，这里简化）
                    t = threading.Thread(target=self._worker_execute, args=(task,), daemon=True)
                    t.start()
                else:
                    # 无并发限制，直接执行（阻塞当前调度线程，不建议，仅骨架演示）
                    task.execute()
                processed = True

            # 控制tick频率（大致）
            sleep_time = next_tick - time.time()
            if sleep_time > 0:
                time.sleep(min(sleep_time, self.tick_interval))
            next_tick = time.time() + self.tick_interval

        logger.info("调度器循环退出")

    def start(self):
        """启动调度器（异步）"""
        with self._lock:
            if self._running:
                logger.warning("调度器已在运行")
                return
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._scheduler_loop, name="KernelScheduler-Thread", daemon=True)
            self._thread.start()
            logger.info("调度器已启动")

    def stop(self, timeout: Optional[float] = None):
        """优雅停止调度器"""
        with self._lock:
            if not self._running:
                logger.info("调度器未运行")
                return
            self._running = False
            self._stop_event.set()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout)
            logger.info("调度器已停止")

    def is_running(self) -> bool:
        return self._running

    def get_task_info(self) -> List[Dict[str, Any]]:
        """获取所有注册任务的信息（调试用）"""
        with self._lock:
            info = []
            for name, task in self._task_map.items():
                info.append({
                    "name": name,
                    "priority": task.priority.name,
                    "interval": task.interval,
                    "last_run": task.last_run,
                    "enabled": task.enabled
                })
            return info


# ------------------------- 自测 -------------------------
if __name__ == "__main__":
    # 设置基本日志
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    logger.info("开始内核调度器自测")

    # 使用默认配置
    scheduler = KernelScheduler({"tick_interval_sec": 0.2, "max_workers": 3})

    # 定义一个简单的任务回调
    def print_echo():
        logger.info("Echo task executed")

    def important_check():
        logger.info("执行重要检查...")

    # 注册一个每1秒执行