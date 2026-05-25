"""
系统缓存模块
所属层次：03_内核系统
依赖：10_配置系统（配置），19_日志系统（日志）
被调用者：04_核心引擎、05_项目管理器、06_上下文管理器等需要缓存的模块
解决的问题：提供统一、可插拔、可配置的缓存服务，支持热插拔多种后端（内存、Redis等），提供日志和异常恢复能力
"""

import importlib
import time
from typing import Any, Callable, Dict, Optional, Union
from threading import RLock

# 日志和配置接口（遵循依赖注入，不直接硬编码导入）
_logger = None  # 模块级日志记录器
_config = None  # 模块级配置

class PluginCacheBackend:
    """缓存后端抽象接口，所有缓存后端必须实现此类"""
    def get(self, key: str) -> Any:
        raise NotImplementedError

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError

    def exists(self, key: str) -> bool:
        raise NotImplementedError

    def stats(self) -> Dict[str, Any]:
        # 返回后端统计信息
        return {}

class MemoryCacheBackend(PluginCacheBackend):
    """基于内存字典的内置缓存后端，支持过期和线程安全"""
    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._expire: Dict[str, float] = {}
        self._lock = RLock()
        self._hits = 0
        self._misses = 0

    def _is_expired(self, key: str) -> bool:
        if key in self._expire:
            return time.time() > self._expire[key]
        return False

    def _purge_expired(self):
        """清理所有过期键（惰性清理调用）"""
        now = time.time()
        expired_keys = [k for k, exp in self._expire.items() if now > exp]
        for k in expired_keys:
            self._store.pop(k, None)
            self._expire.pop(k, None)

    def get(self, key: str) -> Any:
        with self._lock:
            if key not in self._store or self._is_expired(key):
                if key in self._store:
                    # 过期但还未清理，手动清理
                    self.delete(key)
                self._misses += 1
                return None
            self._hits += 1
            return self._store[key]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            self._store[key] = value
            if ttl:
                self._expire[key] = time.time() + ttl
            else:
                # 移除过期设置
                self._expire.pop(key, None)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)
            self._expire.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._expire.clear()
            self._hits = 0
            self._misses = 0

    def exists(self, key: str) -> bool:
        with self._lock:
            if key not in self._store or self._is_expired(key):
                if key in self._store:
                    self.delete(key)
                return False
            return True

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            self._purge_expired()
        return {
            "backend": "memory",
            "keys": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_ratio": round(self._hits / max(1, self._hits + self._misses), 3)
        }

class SystemCache:
    """
    系统缓存管理器，支持动态加载/卸载缓存后端，提供一致的API和日志记录。
    遵循单一职责：只负责缓存抽象和生命周期管理。
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: Optional[Dict[str, Any]] = None, logger: Optional[Callable] = None):
        if self._initialized:
            return
        self._initialized = True

        # 依赖注入配置和日志
        global _config, _logger
        if config:
            _config = config
        else:
            try:
                from config_system import get_config
                _config = get_config("system_cache", {})
            except ImportError:
                _config = {}
        if logger:
            _logger = logger
        else:
            try:
                from log_system import get_logger
                _logger = get_logger("SystemCache")
            except ImportError:
                _logger = _default_logger

        # 后端注册表
        self.backends: Dict[str, PluginCacheBackend] = {}
        self.active_backend_name: Optional[str] = None
        self._lock = RLock()

        # 初始化默认后端（内存）
        self._register_builtin_backends()
        # 从配置加载激活后端
        default_backend = _config.get("active_backend", "memory")
        self.activate_backend(default_backend)

        _logger(f"SystemCache initialized with backend: {self.active_backend_name}", level="info")

    def _register_builtin_backends(self):
        """注册内置缓存后端"""
        mem = MemoryCacheBackend()
        self.backends["memory"] = mem
        # 可在此扩展注册其他内置后端（如RedisStub）

    def register_backend(self, name: str, backend: PluginCacheBackend):
        """注册自定义缓存后端"""
        with self._lock:
            if name in self.backends:
                _logger(f"Backend {name} already registered, overwriting.", level="warning")
            self.backends[name] = backend
            _logger(f"Registered cache backend: {name}", level="debug")

    def unregister_backend(self, name: str):
        """注销缓存后端，禁止注销当前激活的后端"""
        with self._lock:
            if name == self.active_backend_name:
                raise RuntimeError(f"Cannot unregister active backend: {name}")
            if name in self.backends:
                del self.backends[name]
                _logger(f"Unregistered cache backend: {name}", level="debug")

    def activate_backend(self, name: str):
        """切换激活的缓存后端"""
        with self._lock:
            if name not in self.backends:
                raise ValueError(f"Cache backend '{name}' not found. Registered: {list(self.backends.keys())}")
            self.active_backend_name = name
            _logger(f"Activated cache backend: {name}", level="info")

    def get_active_backend(self) -> PluginCacheBackend:
        """获取当前激活的后端实例"""
        if self.active_backend_name is None:
            raise RuntimeError("No active cache backend set")
        return self.backends[self.active_backend_name]

    # 核心缓存操作，委托给激活后端，并附加日志/异常处理
    def get(self, key: str, default: Any = None) -> Any:
        try:
            backend = self.get_active_backend()
            value = backend.get(key)
            if value is None:
                _logger(f"Cache miss: {key}", level="debug")
                return default
            _logger(f"Cache hit: {key}", level="debug")
            return value
        except Exception as e:
            _logger(f"Cache get error for key '{key}': {e}", level="error")
            return default

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        try:
            backend = self.get_active_backend()
            backend.set(key, value, ttl)
            _logger(f"Cache set: {key}, TTL: {ttl}", level="debug")
            return True
        except Exception as e:
            _logger(f"Cache set error for key '{key}': {e}", level="error")
            return False

    def delete(self, key: str) -> bool:
        try:
            backend = self.get_active_backend()
            backend.delete(key)
            _logger(f"Cache delete: {key}", level="debug")
            return True
        except Exception as e:
            _logger(f"Cache delete error for key '{key}': {e}", level="error")
            return False

    def clear(self) -> bool:
        try:
            backend = self.get_active_backend()
            backend.clear()
            _logger("Cache cleared", level="info")
            return True
        except Exception as e:
            _logger(f"Cache clear error: {e}", level="error")
            return False

    def exists(self, key: str) -> bool:
        try:
            backend = self.get_active_backend()
            return backend.exists(key)
        except Exception as e:
            _logger(f"Cache exists error for key '{key}': {e}", level="error")
            return False

    def stats(self) -> Dict[str, Any]:
        """获取当前激活后端的统计信息"""
        try:
            backend = self.get_active_backend()
            stats = backend.stats()
            stats["active_backend"] = self.active_backend_name
            return stats
        except Exception as e:
            _logger(f"Cache stats error: {e}", level="error")
            return {"error": str(e)}

    # 组合操作：获取或计算并缓存
    def get_or_set(self, key: str, factory: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        """
        从缓存获取值，若不存在则调用factory生成，并缓存。
        """
        value = self.get(key)
        if value is None:
            try:
                value = factory()
                if value is not None:
                    self.set(key, value, ttl)
                else:
                    _logger(f"Factory returned None for key {key}, not cached.", level="warning")
            except Exception as e:
                _logger(f"Factory error for key {key}: {e}", level="error")
                return None
        return value

def _default_logger(message: str, level: str = "info"):
    """默认日志输出（当没有注入日志系统时使用）"""
    print(f"[SystemCache][{level.upper()}] {message}")

# 便捷全局单例获取
def get_system_cache(config: Optional[Dict[str, Any]] = None, logger: Optional[Callable] = None) -> SystemCache:
    """获取系统缓存单例，可注入配置和日志"""
    if SystemCache._instance is None:
        SystemCache(config, logger)
    else:
        if config:
            # 可以更新配置（可选实现）
            pass
    return SystemCache._instance

# 自测代码
if __name__ == "__main__":
    print("=== 系统缓存自测 ===")
    cache = get_system_cache()

    # 基本 set/get
    cache.set("test_key", "hello", ttl=10)
    assert cache.get("test_key") == "hello"
    print("set/get 通过")

    # 存在性检查
    assert cache.exists("test_key")
    assert not cache.exists("nonexistent")
    print("exists 通过")

    # 删除
    cache.delete("test_key")
    assert cache.get("test_key") is None
    print("delete 通过")

    # get_or_set
    call_count = 0
    def factory():
        nonlocal call_count
        call_count += 1
        return "computed"
    v1 = cache.get_or_set("lazy_key", factory, ttl=5)
    assert v1 == "computed"
    assert call_count == 1
    v2 = cache.get_or_set("lazy_key", factory, ttl=5)
    assert v2 == "computed"
    assert call_count == 1  # 第二次应该来自缓存
    print("get_or_set 通过")

    # 过期测试（简化，手动等待）
    cache.set("expire_key", "temp", ttl=1)
    assert cache.get("expire_key") == "temp"
    time.sleep(1.5)
    assert cache.get("expire_key") is None
    print("过期测试通过")

    # 后端切换测试
    cache.register_backend("test_mem", MemoryCacheBackend())
    cache.activate_backend("test_mem")
    cache.set("switch_key", 42)
    assert cache.get("switch_key") == 42
    print("后端切换通过")

    # 统计信息
    print("Stats:", cache.stats())

    # 清理
    cache.clear()
    assert cache.get("switch_key") is None
    print("清理通过")

    print("=== 所有自测通过 ===")