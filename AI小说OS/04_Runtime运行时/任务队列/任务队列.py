# -*- coding: utf-8 -*-
"""
任务队列模块 - Task Queue Module

层级：04_Runtime运行时/任务队列
依赖：系统底层日志、配置（通过依赖注入，避免跨层污染）
被调用：上层Agent（如创作Agent、优化Agent）、调度器
职责：提供统一的任务队列接口，支持可插拔后端（内存、Redis等），
      具备日志、配置化、异常恢复能力。
"""

import logging
import abc
import queue
import threading
import time
import uuid
from typing import Any, Dict, Optional, Callable, Type, List
from dataclasses import dataclass, field
from enum import Enum, auto

# ---------- 通用数据结构 ----------
class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = auto()      # 等待执行
    RUNNING = auto()      # 执行中
    COMPLETED = auto()    # 已完成
    FAILED = auto()       # 失败
    CANCELLED = auto()    # 已取消

@dataclass
class Task:
    """任务数据类"""
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])  # 唯一标识
    task_type: str = ""           # 任务类型（用于路由）
    payload: Dict[str, Any] = field(default_factory=dict)  # 任务负载
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    retries: int = 0              # 已重试次数
    max_retries: int = 3          # 最大重试次数
    result: Any = None            # 执行结果
    error: Optional[str] = None   # 错误信息

    def to_dict(self) -> dict:
        """序列化为字典（用于持久化）"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "payload": self.payload,
            "status": self.status.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "result": self.result,
            "error": self.error
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """从字典反序列化"""
        return cls(
            task_id=data.get("task_id", ""),
            task_type=data.get("task_type", ""),
            payload=data.get("payload", {}),
            status=TaskStatus[data.get("status", "PENDING")],
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            retries=data.get("retries", 0),
            max_retries=data.get("max_retries", 3),
            result=data.get("result"),
            error=data.get("error")
        )

# ---------- 抽象任务队列接口 ----------
class AbstractTaskQueue(abc.ABC):
    """任务队列抽象基类（可插拔协议）"""

    def __init__(self, config: Optional[Dict[str, Any]] = None, logger: Optional[logging.Logger] = None):
        self.config = config or {}
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self._closed = False

    @abc.abstractmethod
    def enqueue(self, task: Task) -> bool:
        """将任务放入队列，返回是否成功"""
        pass

    @abc.abstractmethod
    def dequeue(self, timeout: Optional[float] = None) -> Optional[Task]:
        """从队列取出一个任务（阻塞或超时），若无任务返回None"""
        pass

    @abc.abstractmethod
    def task_done(self, task: Task) -> None:
        """标记任务完成（某些队列实现需要此步骤）"""
        pass

    @abc.abstractmethod
    def size(self) -> int:
        """返回队列中待处理任务数量"""
        pass

    def close(self) -> None:
        """关闭队列，释放资源"""
        self._closed = True

    @property
    def is_closed(self) -> bool:
        return self._closed

    def handle_error(self, task: Task, exception: Exception) -> None:
        """异常处理：记录日志，增加重试计数，若超限则标记失败"""
        task.retries += 1
        task.error = str(exception)
        task.updated_at = time.time()
        if task.retries > task.max_retries:
            task.status = TaskStatus.FAILED
            self.logger.error(f"Task {task.task_id} failed after {task.retries} retries. Error: {exception}")
        else:
            task.status = TaskStatus.PENDING  # 重新排队等待重试
            self.logger.warning(f"Task {task.task_id} retrying {task.retries}/{task.max_retries} after error: {exception}")
            # 注意：是否自动重新入队由具体实现决定，此处仅记录状态
            self.enqueue(task)

# ---------- 内存队列实现（默认） ----------
class InMemoryTaskQueue(AbstractTaskQueue):
    """基于内存的任务队列（适合单进程开发/测试）"""

    def __init__(self, config: Optional[Dict[str, Any]] = None, logger: Optional[logging.Logger] = None):
        super().__init__(config, logger)
        maxsize = self.config.get("max_queue_size", 0)  # 0表示无限
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)
        self._pending_count = 0

    def enqueue(self, task: Task) -> bool:
        if self._closed:
            self.logger.error("Cannot enqueue to closed queue.")
            return False
        try:
            self._queue.put(task, block=False)
            self._pending_count += 1
            self.logger.debug(f"Task {task.task_id} enqueued. Total pending: {self._pending_count}")
            return True
        except queue.Full:
            self.logger.warning("Queue is full, cannot enqueue task.")
            return False
        except Exception as exc:
            self.logger.exception(f"Unexpected error during enqueue: {exc}")
            return False

    def dequeue(self, timeout: Optional[float] = None) -> Optional[Task]:
        if self._closed:
            return None
        try:
            # 使用超时，避免永久阻塞
            task = self._queue.get(timeout=timeout)
            self._pending_count -= 1
            self.logger.debug(f"Task {task.task_id} dequeued. Remaining: {self._pending_count}")
            return task
        except queue.Empty:
            return None
        except Exception as exc:
            self.logger.exception(f"Unexpected error during dequeue: {exc}")
            return None

    def task_done(self, task: Task) -> None:
        """内存队列中无需特别处理，但可记录状态"""
        self.logger.debug(f"Task {task.task_id} marked as done.")

    def size(self) -> int:
        return self._pending_count

    def close(self) -> None:
        super().close()
        # 清空队列（可选）
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._pending_count -= 1
            except queue.Empty:
                break
        self.logger.info("InMemoryTaskQueue closed.")

# ---------- 队列工厂 ----------
class TaskQueueFactory:
    """任务队列工厂，根据配置创建实例，实现可插拔"""
    
    _registry: Dict[str, Type[AbstractTaskQueue]] = {
        "memory": InMemoryTaskQueue,
        # 可扩展其他实现："redis": RedisTaskQueue, ...
    }

    @classmethod
    def register(cls, name: str, queue_cls: Type[AbstractTaskQueue]) -> None:
        """注册新的队列实现"""
        cls._registry[name] = queue_cls

    @classmethod
    def create(cls, config: Dict[str, Any], logger: Optional[logging.Logger] = None) -> AbstractTaskQueue:
        """
        根据配置创建任务队列实例。
        配置示例：
        {
            "queue_type": "memory",      # 队列类型
            "max_queue_size": 1000,      # 特定参数
            ...
        }
        """
        queue_type = config.get("queue_type", "memory")
        queue_cls = cls._registry.get(queue_type)
        if not queue_cls:
            raise ValueError(f"Unknown queue type: {queue_type}. Available: {list(cls._registry.keys())}")
        instance_logger = logger or logging.getLogger(f"TaskQueue.{queue_type}")
        return queue_cls(config=config, logger=instance_logger)

# ---------- 自测与演示 ----------
if __name__ == "__main__":
    # 配置基础日志
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
    )
    test_logger = logging.getLogger("TaskQueueTest")

    # 测试配置
    config = {
        "queue_type": "memory",
        "max_queue_size": 10
    }

    # 1. 创建队列
    q = TaskQueueFactory.create(config, test_logger)
    
    # 2. 入队几个演示任务
    tasks = [
        Task(task_type="generate_outline", payload={"novel_id": "1001"}),
        Task(task_type="write_chapter", payload={"chapter": 1}),
        Task(task_type="polish_text", payload={"text_id": "abc"}),
    ]
    for t in tasks:
        success = q.enqueue(t)
        test_logger.info(f"Enqueue {t.task_id} -> {'OK' if success else 'FAILED'}")
    
    test_logger.info(f"Queue size: {q.size()}")

    # 3. 模拟出队并处理
    def worker():
        while True:
            task = q.dequeue(timeout=2.0)
            if task is None:
                test_logger.info("No more tasks, worker exiting.")
                break
            test_logger.info(f"Processing {task.task_id} of type '{task.task_type}'")
            # 模拟处理成功
            task.status = TaskStatus.COMPLETED
            task.result = f"Result of {task.task_id}"
            q.task_done(task)