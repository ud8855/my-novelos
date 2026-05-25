"""
并发控制模块 - Runtime层
负责管理并发任务执行，确保系统资源合理利用。
可插拔设计：可通过配置切换并发策略（默认信号量实现）。
配置化：从配置文件读取最大并发数等参数。
日志：记录并发状态变化和任务执行信息。
英文标识符 + 中文注释。
"""

import asyncio
import logging
import os
import sys
from typing import Callable, Coroutine, Any, Optional, Dict

# 添加项目根目录到 sys.path 以便导入配置模块（假设配置模块存在）
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# 尝试导入配置模块，如果不存在则使用默认配置
try:
    from config import get_config
    USE_CONFIG_MODULE = True
except ImportError:
    USE_CONFIG_MODULE = False


class ConcurrencyController:
    """
    并发控制器
    负责管理协程任务的并发数量，支持通过配置调整。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化并发控制器。
        优先使用传入的 config，其次尝试从全局配置模块读取，最后使用默认配置。
        """
        # 日志设置
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # 加载配置
        if config is None:
            if USE_CONFIG_MODULE:
                # 从全局配置读取，假设配置中有 runtime.concurrency 节点
                try:
                    global_config = get_config()
                    self.config = global_config.get('runtime', {}).get('concurrency', {})
                except Exception as e:
                    self.logger.warning(f"读取全局配置失败，使用默认配置: {e}")
                    self.config = {}
            else:
                self.config = {}
        else:
            self.config = config

        # 核心参数
        self.max_concurrency = self.config.get('max_concurrency', 10)  # 最大并发数
        self.task_queue_size = self.config.get('task_queue_size', 0)   # 任务队列大小，0 表示无限制
        self.default_timeout = self.config.get('default_timeout', 30.0)  # 默认超时（秒）

        # 并发控制信号量
        self._semaphore = asyncio.Semaphore(self.max_concurrency)

        # 统计信息
        self.active_count = 0
        self.total_submitted = 0
        self.total_completed = 0
        self.total_failed = 0

        self.logger.info(f"并发控制器初始化完成，最大并发: {self.max_concurrency}")

    async def acquire(self):
        """获取执行许可，阻塞直到有可用槽位"""
        self.logger.debug("等待获取执行许可...")
        await self._semaphore.acquire()
        self.active_count += 1
        self.logger.debug(f"获取执行许可成功，当前活跃任务数: {self.active_count}")

    def release(self):
        """释放执行许可"""
        self._semaphore.release()
        self.active_count -= 1
        self.logger.debug(f"释放执行许可，当前活跃任务数: {self.active_count}")

    async def submit_task(self, 
                          task_func: Callable[..., Coroutine[Any, Any, Any]],
                          *args,
                          **kwargs) -> Any:
        """
        提交一个协程任务，自动管理并发控制。
        
        Args:
            task_func: 异步任务函数
            *args: 传递给任务函数的位置参数
            **kwargs: 传递给任务函数的关键字参数
        
        Returns:
            任务函数的返回值
        
        Raises:
            任务执行过程中的异常
        """
        await self.acquire()
        self.total_submitted += 1
        self.logger.info(f"任务已提交 (编号: {self.total_submitted})")
        try:
            # 执行任务，支持超时
            timeout = kwargs.pop('_timeout', self.default_timeout)
            result = await asyncio.wait_for(task_func(*args, **kwargs), timeout=timeout)
            self.total_completed += 1
            self.logger.info(f"任务完成 (编号: {self.total_submitted})")
            return result
        except Exception as e:
            self.total_failed += 1
            self.logger.error(f"任务失败 (编号: {self.total_submitted}): {e}")
            raise
        finally:
            self.release()

    def get_stats(self) -> Dict[str, Any]:
        """返回当前并发控制器的统计信息"""
        return {
            'max_concurrency': self.max_concurrency,
            'active_count': self.active_count,
            'total_submitted': self.total_submitted,
            'total_completed': self.total_completed,
            'total_failed': self.total_failed,
            'available_slots': self.max_concurrency - self.active_count
        }


# 自测代码
if __name__ == "__main__":
    async def sample_task(seconds: float):
        """模拟耗时任务"""
        print(f"  任务开始，将耗时 {seconds}s")
        await asyncio.sleep(seconds)
        print(f"  任务完成")
        return f"result of {seconds}s"

    async def test():
        controller = ConcurrencyController({'max_concurrency': 2, 'default_timeout': 10.0})
        # 提交一批任务，并发限制为2
        tasks = []
        for i in range(5):
            # 模拟不同耗时
            task = controller.submit_task(sample_task, (i % 3) + 1)
            tasks.append(task)
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        print("\n所有任务结果:", results)
        print("统计信息:", controller.get_stats())

    asyncio.run(test())