"""临时状态模块
---
层级: 07_状态系统
依赖: 无外部业务依赖, 使用Python标准库
被调用: 其他模块需要临时存储状态时调用
功能: 提供可插拔的临时键值存储, 支持TTL, 配置化后端
"""
import logging
import time
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class TemporaryState(ABC):
    """临时状态抽象基类, 定义统一接口"""

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置键值, 可选TTL(秒)"""
        ...

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """获取键值, 不存在或过期返回default"""
        ...

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除键, 返回是否成功"""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """检查键是否存在且未过期"""
        ...

    @abstractmethod
    def clear(self) -> None:
        """清空所有状态"""
        ...

    @abstractmethod
    def keys(self) -> list:
        """返回所有有效的键"""
        ...

class InMemoryTemporaryState(TemporaryState):
    """
    基于内存的临时状态实现
    支持TTL, 惰性过期检查
    """

    def __init__(self, max_size: Optional[int] = None):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._max_size = max_size  # None代表无限制
        logger.debug("InMemoryTemporaryState 初始化, max_size=%s", max_size)

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            expire_at = time.time() + ttl if ttl else None
            self._store[key] = {'value': value, 'expire_at': expire_at}
            logger.debug("临时状态设置 key=%s, ttl=%s, expire=%s", key, ttl, expire_at)
            # 简单的容量控制：如果超过max_size，删除最早过期或随机（这里简单忽略）

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            data = self._store.get(key)
            if data is None:
                return default
            expire_at = data.get('expire_at')
            if expire_at is not None and time.time() > expire_at:
                # 过期删除
                del self._store[key]
                logger.debug("临时状态键过期 key=%s", key)
                return default
            return data['value']

    def delete(self, key: str) -> bool:
        with self._lock:
            existed = key in self._store
            if existed:
                del self._store[key]
                logger.debug("临时状态删除 key=%s", key)
            return existed

    def exists(self, key: str) -> bool:
        # 复用get检查，但不用返回值
        with self._lock:
            data = self._store.get(key)
            if data is None:
                return False
            expire_at = data.get('expire_at')
            if expire_at is not None and time.time() > expire_at:
                del self._store[key]
                return False
            return True

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            logger.debug("临时状态全部清空")

    def keys(self) -> list:
        with self._lock:
            now = time.time()
            valid_keys = []
            expired_keys = []
            for k, data in self._store.items():
                expire_at = data.get('expire_at')
                if expire_at is not None and now > expire_at:
                    expired_keys.append(k)
                else:
                    valid_keys.append(k)
            for k in expired_keys:
                del self._store[k]
            return valid_keys

def create_temporary_state(config: Dict[str, Any] = None) -> TemporaryState:
    """
    工厂函数: 根据配置创建临时状态实例
    配置示例: {'backend': 'memory', 'max_size': 1000}
    """
    if config is None:
        config = {}
    backend = config.get('backend', 'memory')
    if backend == 'memory':
        max_size = config.get('max_size', None)
        return InMemoryTemporaryState(max_size=max_size)
    else:
        logger.error("不支持的临时状态后端: %s", backend)
        raise ValueError(f"Unsupported temporary state backend: {backend}")

# ---------- 自测 ----------
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("=== 临时状态模块自测 ===")

    # 测试内存后端
    state = create_temporary_state()
    assert not state.exists('a')
    state.set('a', 1)
    assert state.exists('a')
    assert state.get('a') == 1