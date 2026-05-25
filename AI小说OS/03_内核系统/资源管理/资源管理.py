"""
模块：资源管理 (ResourceManager)
层级：03_内核系统 (Kernel System Layer)
职责：统一管理系统运行时所需的各种资源（内存、文件、连接、模型实例等），提供资源生命周期管理、池化、配额限制等功能。
依赖：仅依赖Python标准库及内核配置模块（03_内核系统/配置管理），不依赖上层业务逻辑。
被调用：被内核调度器、任务管理、Agent容器等内核模块调用，作为资源分配的统一出口。
设计原则：可插拔（通过实现ResourceManager抽象基类）、配置化（资源配额通过配置传入）、日志（关键操作记录日志）、异常恢复（资源获取失败有重试或降级策略）。
"""
import logging
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

# 假设有一个配置管理模块，这里简化为导入
try:
    from 配置管理 import ConfigManager
except ImportError:
    ConfigManager = None  # 可选依赖

logger = logging.getLogger(__name__)


class ResourceError(Exception):
    """资源异常基类"""
    pass


class ResourceExhaustedError(ResourceError):
    """资源耗尽异常"""
    pass


class ResourceNotFoundError(ResourceError):
    """资源未找到异常"""
    pass


class ResourceManager(ABC):
    """资源管理器抽象基类，定义资源管理通用接口"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化资源管理器
        :param config: 配置字典，包含资源上限、策略等；若为None，则从ConfigManager获取
        """
        self.config = config or self._load_config()
        self._lock = threading.RLock()
        self._resources: Dict[str, Any] = {}
        logger.info(f"{self.__class__.__name__} initialized with config: {self.config}")

    def _load_config(self) -> Dict[str, Any]:
        """从配置中心加载默认配置，子类可覆盖"""
        if ConfigManager:
            return ConfigManager.get_config("kernel.resource", {})
        return {}

    @abstractmethod
    def acquire(self, resource_type: str, **kwargs) -> Any:
        """
        获取指定类型的资源
        :param resource_type: 资源类型标识
        :param kwargs: 获取资源所需参数
        :return: 资源对象
        :raises: ResourceExhaustedError 如果资源耗尽
        """
        pass

    @abstractmethod
    def release(self, resource: Any) -> None:
        """
        释放资源
        :param resource: 之前获取的资源对象
        """
        pass

    def acquire_safe(self, resource_type: str, timeout: float = 10.0, **kwargs) -> Any:
        """
        安全获取资源，带超时和重试
        :param resource_type: 资源类型标识
        :param timeout: 超时时间（秒）
        :param kwargs: 参数
        :return: 资源对象
        """
        import time
        start = time.time()
        attempt = 0
        max_attempts = self.config.get("max_acquire_attempts", 3)
        while True:
            try:
                resource = self.acquire(resource_type, **kwargs)
                logger.debug(f"Acquired resource {resource_type} (attempt {attempt+1})")
                return resource
            except ResourceExhaustedError as e:
                if attempt < max_attempts - 1 and (time.time() - start) < timeout:
                    wait = self.config.get("acquire_backoff", 0.5)
                    time.sleep(wait)
                    attempt += 1
                    continue
                else:
                    logger.error(f"Failed to acquire resource {resource_type} after {attempt+1} attempts")
                    raise
            except Exception:
                logger.exception(f"Unexpected error acquiring {resource_type}")
                raise

    def release_safe(self, resource: Any) -> bool:
        """
        安全释放资源，捕获所有异常
        :param resource: 资源对象
        :return: 是否成功释放
        """
        try:
            self.release(resource)
            logger.debug("Resource released successfully")
            return True
        except Exception:
            logger.exception("Error releasing resource")
            return False

    def cleanup_stale(self, check_type: Optional[str] = None) -> int:
        """
        清理过期或僵死资源，子类需实现具体逻辑
        :param check_type: 要检查的资源类型，None表示所有
        :return: 清理的资源数量
        """
        logger.info("Cleanup stale resources called (base implementation does nothing)")
        return 0

    def shutdown(self) -> None:
        """关闭资源管理器，释放所有资源"""
        logger.info(f"Shutting down {self.__class__.__name__}")
        with self._lock:
            for res in list(self._resources.values()):
                self.release_safe(res)
            self._resources.clear()
        logger.info("Shutdown complete")


class SimpleResourceManager(ResourceManager):
    """简单的资源管理器实现，用于测试和轻量场景"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self._pool: Dict[str, list] = {}  # 资源类型 -> 可用资源列表
        self._in_use: Dict[str, int] = {}

    def add_resource_type(self, resource_type: str, initial_resources: list, max_count: int = 10):
        """向池中添加资源类型及其初始资源"""
        with self._lock:
            self._pool[resource_type] = initial_resources.copy()
            self._in_use[resource_type] = 0
            self._resources[resource_type] = {'max': max_count, 'available': len(initial_resources)}
            logger.info(f"Added resource type {resource_type} with {len(initial_resources)} items, max {max_count}")

    def acquire(self, resource_type: str, **kwargs) -> Any:
        with self._lock:
            if resource_type not in self._pool:
                raise ResourceNotFoundError(f"Resource type {resource_type} not registered")
            available = self._pool[resource_type]
            if not available:
                raise ResourceExhaustedError(f"No available resources for {resource_type}")
            resource = available.pop()
            self._in_use[resource_type] = self._in_use.get(resource_type, 0) + 1
            logger.debug(f"Acquired {resource_type} (in use: {self._in_use[resource_type]})")
            return resource

    def release(self, resource: Any) -> None:
        # 简单实现：按值匹配释放，生产环境应使用唯一ID
        with self._lock:
            for rtype, pool in self._pool.items():
                if resource in pool:
                    logger.warning(f"Resource {resource} already in pool for {rtype}")
                    return
            # 假设资源可以加入任何池，实际需完善
            for rtype in self._pool:
                if isinstance(resource, str) and rtype == 'file':
                    self._pool[rtype].append(resource)
                    self._in_use[rtype] -= 1
                    logger.debug(f"Released {rtype} (in use: {self._in_use[rtype]})")
                    return
            raise ResourceNotFoundError(f"Unknown resource {resource} for release")

    def cleanup_stale(self, check_type: Optional[str] = None) -> int:
        # 简单实现：无操作
        return 0


# ----------------- 自测 -----------------
if __name__ == "__main__":
    # 配置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("=== 资源管理器自测 ===")
    # 1. 实例化简单资源管理器
    mgr = SimpleResourceManager({'max_acquire_attempts': 2, 'acquire_backoff': 0.1})
    # 2. 添加资源类型
    mgr.add_resource_type('file', ['f1', 'f2', 'f3'], max_count=5)
    # 3. 获取资源
    try:
        res1 = mgr.acquire_safe('file', timeout=1)
        print(f"获取资源成功: {res1}")
        res2 = mgr.acquire_safe('file')
        print(f"再次获取: {res2}")
        res3 = mgr.acquire_safe('file')
        print(f"第三次获取: {res3}")
        # 4. 获取第四个应耗尽
        try:
            res4 = mgr.acquire_safe('file', timeout=0.5)
        except ResourceExhaustedError as e:
            print(f"预期耗尽异常: {e}")
        # 5. 释放一个资源
        mgr.release_safe(res1)
        # 6. 再次获取应该成功
        res4 = mgr.acquire_safe('file')
        print(f"释放后获取: {res4}")
    finally:
        mgr.shutdown()
    print("自测完成")