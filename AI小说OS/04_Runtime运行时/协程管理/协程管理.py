"""
协程管理模块 (Coroutine Manager)
功能：统一管理异步协程的生命周期，包括创建、调度、取消、异常处理。
设计：可插拔，支持更换底层异步框架（如asyncio、trio等）；配置化，通过配置文件控制参数；日志记录关键操作。
"""

import asyncio
import logging
from typing import Callable, Coroutine, Any, Optional, List
import signal

class CoroutineManager:
    """协程管理器抽象基类，定义通用接口"""
    def start(self):
        """启动事件循环或执行环境"""
        raise NotImplementedError
    
    def submit(self, coro: Coroutine) -> asyncio.Task:
        """提交一个协程任务，返回可追踪的任务对象"""
        raise NotImplementedError
    
    def shutdown(self):
        """优雅关闭，取消所有未完成任务，释放资源"""
        raise NotImplementedError


class AsyncioCoroutineManager(CoroutineManager):
    """基于asyncio的协程管理器实现"""
    
    def __init__(self, config: dict = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        # 配置合并：用户提供的配置覆盖默认配置
        self.config = config or self._default_config()
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self._tasks: List[asyncio.Task] = []
        # 从配置读取参数
        self._max_concurrent = self.config.get("max_concurrent_tasks", 100)
        self._shutdown_timeout = self.config.get("shutdown_timeout", 5.0)
        
    def _default_config(self) -> dict:
        """默认配置参数"""
        return {
            "max_concurrent_tasks": 100,
            "shutdown_timeout": 5.0,
            "log_level": "INFO"
        }
    
    def start(self):
        """启动事件循环，注册信号处理以实现优雅关闭"""
        self.logger.info("Starting AsyncioCoroutineManager")
        self.loop = asyncio.get_event_loop()
        # 注册信号处理（SIGINT, SIGTERM）
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                self.loop.add_signal_handler(sig, self._signal_handler)
            except NotImplementedError:
                # Windows 下可能不支持 add_signal_handler
                self.logger.warning(f"Signal handler for {sig} not supported on this platform")
        self.logger.info("Event loop started")
    
    def _signal_handler(self):
        self.logger.info("Received termination signal, initiating shutdown...")
        asyncio.ensure_future(self._shutdown_async())
    
    async def _shutdown_async(self):
        await self.shutdown()
    
    def submit(self, coro: Coroutine) -> asyncio.Task:
        """提交一个协程任务，返回 asyncio.Task 对象"""
        if not self.loop:
            raise RuntimeError("Event loop not started, call start() first")
        
        # 可扩展：如果当前并发数超过最大值，可以选择等待或拒绝
        # 这里仅做简单示例，直接提交
        task = asyncio.ensure_future(coro, loop=self.loop)
        self._tasks.append(task)
        task.add_done_callback(self._task_done_callback)
        self.logger.debug(f"Task submitted: {coro}")
        return task
    
    def _task_done_callback(self, task: asyncio.Task):
        """任务完成后的回调，处理异常和清理"""
        self._tasks.remove(task)
        if task.exception():
            self.logger.error(f"Task {task} raised exception: {task.exception()}", exc_info=True)
    
    def run_until_complete(self, coro: Coroutine) -> Any:
        """便捷方法：运行一个协程直到完成并返回结果"""
        return self.loop.run_until_complete(coro)
    
    def shutdown(self, timeout: float = None):
        """关闭管理器，取消所有未完成任务，等待指定超时后强制关闭"""
        timeout = timeout or self._shutdown_timeout
        self.logger.info(f"Shutting down AsyncioCoroutineManager, timeout={timeout}s")
        
        # 取消所有未完成的任务
        for task in self._tasks:
            task.cancel()
        
        # 等待所有任务结束或超时
        async def _cancel_all():
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        try:
            self.loop.run_until_complete(
                asyncio.wait_for(_cancel_all(), timeout=timeout)
            )
        except asyncio.TimeoutError:
            self.logger.warning("Shutdown timed out, forcing event loop stop")
        finally:
            self.loop.close()
            self.logger.info("Event loop closed")
    
    def __del__(self):
        if self.loop and self.loop.is_running():
            self.logger.warning("CoroutineManager destroyed while loop is running, attempting shutdown")
            self.shutdown()


# ================== 自测代码 ==================
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(name)s: %(message)s')
    logger = logging.getLogger("TestCoroutineManager")
    
    # 创建管理器实例（使用默认配置）
    manager = AsyncioCoroutineManager()
    manager.start()
    
    async def sample_task(name: str, delay: float = 1.0):
        """示例异步任务"""
        logger.info(f"Task {name} started, will sleep {delay}s")
        await asyncio.sleep(delay)
        logger.info(f"Task {name} finished")
        return name
    
    async def main():
        tasks = []
        for i in range(3):
            task = manager.submit(sample_task(f"task-{i}", i+1))
            tasks.append(task)
        # 等待所有提交的任务完成
        results = await asyncio.gather(*tasks)
        logger.info(f"All tasks completed: {results}")