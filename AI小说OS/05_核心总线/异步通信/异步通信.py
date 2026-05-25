#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步通信 - 核心总线异步通信模块
所属层：05_核心总线
依赖：标准库 (asyncio, logging, typing, dataclasses, configparser)
被谁调用：所有需要异步消息传递的模块（Agent、Runtime、模型协同等）
解决什么问题：提供统一的异步消息总线，支持发布/订阅，解耦模块，支持热插拔

设计原则：
- 可插拔：通过抽象基类定义接口，具体实现可替换
- 可配置：支持从配置文件或环境变量读取参数
- 日志：所有关键操作记录日志
- 单一职责：仅处理异步消息传递
- 支持热更新：总线实例可在运行时动态替换（需外部管理）
"""
import asyncio
import logging
import uuid
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Coroutine, Any, Dict, List, Optional, Set
from enum import Enum
import configparser
import os
from pathlib import Path

# ======================== 日志配置 ========================
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - [%(levelname)s] - %(name)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)  # 默认级别，可通过配置覆盖


# ======================== 配置管理 ========================
@dataclass
class AsyncCommunicationConfig:
    """异步通信配置"""
    max_queue_size: int = 10000
    worker_count: int = 2
    retry_attempts: int = 3
    retry_delay: float = 0.5
    log_level: str = "INFO"
    
    @classmethod
    def from_config_file(cls, config_path: Optional[str] = None) -> "AsyncCommunicationConfig":
        """从配置文件加载配置，支持默认值"""
        config = cls()
        if config_path is None:
            # 默认尝试从环境变量或标准路径加载
            config_path = os.getenv("NOVELOS_COMM_CONFIG", None)
            if config_path is None:
                possible_paths = [
                    Path(__file__).parent / "async_communication.conf",
                    Path("config/async_communication.conf")
                ]
                for p in possible_paths:
                    if p.exists():
                        config_path = str(p)
                        break
        
        if config_path and Path(config_path).exists():
            parser = configparser.ConfigParser()
            parser.read(config_path, encoding='utf-8')
            if 'AsyncCommunication' in parser:
                section = parser['AsyncCommunication']
                config.max_queue_size = section.getint('max_queue_size', 10000)
                config.worker_count = section.getint('worker_count', 2)
                config.retry_attempts = section.getint('retry_attempts', 3)
                config.retry_delay = section.getfloat('retry_delay', 0.5)
                config.log_level = section.get('log_level', 'INFO')
        else:
            logger.debug("未找到异步通信配置文件，使用默认值")
        
        return config


# ======================== 消息定义 ========================
class MessagePriority(Enum):
    """消息优先级枚举"""
    LOW = 10
    NORMAL = 50
    HIGH = 100
    CRITICAL = 200


@dataclass
class Message:
    """标准消息结构"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    payload: Any = None
    priority: MessagePriority = MessagePriority.NORMAL
    sender: str = ""  # 发送者标识
    timestamp: float = field(default_factory=asyncio.get_event_loop().time if asyncio.get_event_loop().is_running() else __import__('time').time)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ======================== 异步通信抽象基类 ========================
class AsyncCommunicationBus(ABC):
    """异步消息总线抽象基类 (可插拔)"""
    
    @abstractmethod
    async def start(self) -> None:
        """启动总线，初始化内部资源"""
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """停止总线，清理资源"""
        pass
    
    @abstractmethod
    async def publish(self, message: Message) -> bool:
        """发布消息到总线，返回是否成功投递到内部队列（不代表已被消费）"""
        pass
    
    @abstractmethod
    async def subscribe(self, topic: str, callback: Callable[[Message], Coroutine[Any, Any, None]]) -> str:
        """订阅指定主题，返回订阅ID，可用来取消订阅"""
        pass
    
    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """根据订阅ID取消订阅"""
        pass
    
    @abstractmethod
    async def unsubscribe_all(self, topic: str) -> bool:
        """取消某个主题的所有订阅"""
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """返回总线是否正在运行"""
        pass
    
    @abstractmethod
    async def get_queue_info(self) -> Dict[str, Any]:
        """获取总线运行状态信息，用于监控"""
        pass


# ======================== 默认实现：基于asyncio的简单内存总线 ========================
class SimpleAsyncBus(AsyncCommunicationBus):
    """简单异步消息总线，在进程内使用asyncio.Queue传递消息，支持优先级（简化版）"""
    
    def __init__(self, config: AsyncCommunicationConfig = AsyncCommunicationConfig()):
        self._config = config
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=config.max_queue_size)
        self._subscriptions: Dict[str, Dict[str, Callable[[Message], Coroutine[Any, Any, None]]]] = {}  # topic -> {sub_id: callback}
        self._sub_id_counter: int = 0
        self._running: bool = False
        self._workers: List[asyncio.Task] = []
        self._lock = asyncio.Lock()
        
    async def start(self) -> None:
        """启动总线：启动工作协程"""
        if self._running:
            logger.warning("SimpleAsyncBus 已经在运行")
            return
        logger.info("SimpleAsyncBus 正在启动...")
        self._running = True
        for i in range(self._config.worker_count):
            task = asyncio.create_task(self._worker(f"worker-{i}"))
            self._workers.append(task)
        logger.info(f"SimpleAsyncBus 启动完成，启动了 {self._config.worker_count} 个工作协程")
    
    async def stop(self) -> None:
        """停止总线：停止工作协程，清理"""
        if not self._running:
            return
        logger.info("SimpleAsyncBus 正在停止...")
        self._running = False
        # 向队列发送停止标记
        for _ in range(len(self._workers)):
            await self._queue.put(None)
        # 等待所有工作协程结束
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        async with self._lock:
            self._subscriptions.clear()
        logger.info("SimpleAsyncBus 已停止")
    
    async def publish(self, message: Message) -> bool:
        """发布消息到队列"""
        if not self._running:
            logger.error("总线未启动，无法发布消息")
            return False
        try:
            # 根据优先级将消息放入队列（这里简化处理，直接放入）
            # 未来可以实现优先级队列
            await self._queue.put(message)
            logger.debug(f"消息已入队: topic={message.topic}, id={message.id}")
            return True
        except asyncio.QueueFull:
            logger.error(f"消息队列已满，丢弃消息: topic={message.topic}, id={message.id}")
            return False
        except Exception as e:
            logger.exception(f"发布消息时发生异常: {e}")
            return False
    
    async def subscribe(self, topic: str, callback: Callable[[Message], Coroutine[Any, Any, None]]) -> str:
        """订阅主题"""
        async with self._lock:
            if topic not in self._subscriptions:
                self._subscriptions[topic] = {}
            sub_id = self._generate_sub_id(topic)
            self._subscriptions[topic][sub_id] = callback
            logger.debug(f"新订阅: topic={topic}, sub_id={sub_id}")
            return sub_id
    
    async def unsubscribe(self, subscription_id: str) -> bool:
        """根据订阅ID取消订阅"""
        # 解析 topic 从 sub_id (格式: topic:counter)
        parts = subscription_id.rsplit(":", 1)
        if len(parts) != 2:
            logger.warning(f"无效的订阅ID格式: {subscription_id}")
            return False
        topic = parts[0]
        async with self._lock:
            if topic in self._subscriptions and subscription_id in self._subscriptions[topic]:
                del self._subscriptions[topic][subscription_id]
                if not self._subscriptions[topic]:
                    del self._subscriptions[topic]
                logger.debug(f"取消订阅: sub_id={subscription_id}")
                return True
            else:
                logger.warning(f"未找到订阅: {subscription_id}")
                return False
    
    async def unsubscribe_all(self, topic: str) -> bool:
        """取消某个主题的所有订阅"""
        async with self._lock:
            if topic in self._subscriptions:
                removed_count = len(self._subscriptions[topic])
                del self._subscriptions[topic]
                logger.debug(f"移除主题 '{topic}' 的所有订阅，共 {removed_count} 个")
                return True
            else:
                logger.debug(f"主题 '{topic}' 没有订阅")
                return False
    
    def is_running(self) -> bool:
        return self._running
    
    async def get_queue_info(self) -> Dict[str, Any]:
        """获取队列状态信息"""
        return {
            "running": self._running,
            "queue_size": self._queue.qsize(),
            "maxsize": self._queue.maxsize,
            "worker_count": len(self._workers),
            "subscription_topics": list(self._subscriptions.keys()),
            "total_subscriptions": sum(len(subs) for subs in self._subscriptions.values()),
        }
    
    # ======================== 内部方法 ========================
    def _generate_sub_id(self, topic: str) -> str:
        self._sub_id_counter += 1
        return f"{topic}:{self._sub_id_counter}"
    
    async def _worker(self, name: str):
        """工作协程，从队列取消息并分发给订阅者"""
        logger.debug(f"工作协程 {name} 开始")
        retry_count = self._config.retry_attempts
        while self._running:
            try:
                message = await self._queue.get()
                if message is None:  # 停止信号
                    logger.debug(f"工作协程 {name} 收到停止信号")
                    self._queue.task_done()
                    break
                
                # 获取该主题的订阅者快照
                async with self._lock:
                    subscribers = list(self._subscriptions.get(message.topic, {}).values())
                
                if not subscribers:
                    logger.debug(f"没有订阅者处理主题 '{message.topic}' 的消息")
                    self._queue.task_done()
                    continue
                
                # 分发给所有订阅者（并行执行）
                tasks = []
                for callback in subscribers:
                    tasks.append(self._dispatch_with_retry(callback, message, retry_count))
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if isinstance(res, Exception):