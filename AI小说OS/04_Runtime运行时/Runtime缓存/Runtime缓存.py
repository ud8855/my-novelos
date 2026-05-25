"""
Runtime缓存模块
所属层：04_Runtime运行时
依赖：30_配置/配置文件（通过配置管理器间接依赖）
被调用方：各Agent、功能模块需要缓存数据时调用
职责：提供统一的缓存服务，支持可插拔后端，热切换，异常恢复，配置化，日志记录
"""

import logging
import time
import threading
import configparser
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict

# ---------- 配置管理 ----------
class CacheConfig:
    """
    缓存配置类，负责读取和提供缓存相关配置
    """
    def __init__(self, config_path: Optional[str] = None):
        self.config = configparser.ConfigParser()
        # 默认配置
        self.default_backend = "MemoryCacheBackend"
        self.default_max_size = 1000
        self.default_ttl_seconds = 3600  # 1小时
        self.default_cleanup_interval = 300  # 5分钟清理一次过期条目
        # 如果有配置文件路径，则加载
        if config_path:
            self.config.read(config_path, encoding='utf-8')
        else:
            # 尝试从默认位置加载
            default_cfg = "30_配置/cache_config.ini"
            if __import__('os').path.exists(default_cfg):
                self.config.read(default_cfg, encoding='utf-8')

    @property
    def backend(self) -> str:
        """返回配置的后端类名"""
        return self.config.get('Cache', 'backend', fallback=self.default_backend)

    @property
    def max_size(self) -> int:
        """返回配置的最大缓存条目数"""
        return self.config.getint('Cache', 'max_size', fallback=self.default_max_size)

    @property
    def ttl_seconds(self) -> int:
        """返回配置的默认存活时间（秒）"""
        return self.config.getint('Cache', 'ttl_seconds', fallback=self.default_ttl_seconds)

    @property
    def cleanup_interval(self) -> int:
        """返回清理间隔（秒）"""
        return self.config.getint('Cache', 'cleanup_interval', fallback=self.default_cleanup_interval)


# ---------- 抽象后端接口 ----------
class CacheBackend(ABC):
    """
    缓存后端抽象基类，所有具体后端必须继承并实现以下接口
    """
    @abstractmethod
    def get(self, key: str) -> Any:
        """获取键对应的值，若不存在或过期返回None"""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置键值对，可选生存时间（秒）"""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除一个键，返回是否成功删除"""
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空所有缓存"""
        pass

    @abstractmethod
    def size(self) -> int:
        """返回当前缓存条目数量"""
        pass


# ---------- 内存后端实现 ----------
class MemoryCacheBackend(CacheBackend):
    """
    基于字典的内存缓存后端，支持TTL和最大容量控制
    """
    def __init__(self, config: CacheConfig):
        self._store: Dict[str, tuple] = {}  # key -> (value, expiry_time)
        self._lock = threading.RLock()
        self.max_size = config.max_size
        self.default_ttl = config.ttl_seconds
        self.logger = logging.getLogger("RuntimeCache.MemoryBackend")

    def _cleanup_expired(self) -> None:
        """清理所有过期条目（内部调用，需在锁内）"""
        now = time.time()
        expired_keys = [
            k for k, (_, exp) in self._store.items()
            if exp is not None and exp < now
        ]
        for k in expired_keys:
            del self._store[k]
            self.logger.debug(f"清理过期缓存键：{k}")

    def get(self, key: str) -> Any:
        with self._lock:
            # 先检查是否过期
            if key in self._store:
                value, expiry = self._store[key]
                if expiry is None or expiry >= time.time():
                    return value
                else:
                    # 过期，删除
                    del self._store[key]
                    self.logger.debug(f"缓存键已过期：{key}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        with self._lock:
            # 如果达到容量上限，执行一次清理或简单的先进先出淘汰（这里采用简单随机删除一个）
            if len(self._store) >= self.max_size:
                # 随机删除一个，简化处理，实际可用LRU等策略
                # 为了简单，先执行过期清理，再判断
                self._cleanup_expired()
                if len(self._store) >= self.max_size:
                    # 如果还是满了，移除第一个键（任意）
                    first_key = next(iter(self._store))
                    del self._store[first_key]
                    self.logger.warning(f"缓存容量满，移除键：{first_key}")
            # 计算过期时间
            expire_time = None
            if ttl is not None:
                expire_time = time.time() + ttl
            elif self.default_ttl > 0:
                expire_time = time.time() + self.default_ttl
            self._store[key] = (value, expire_time)

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        with self._lock:
            self._cleanup_expired()  # 返回前清理，保证准确性
            return len(self._store)


# ---------- 缓存管理器 ----------
class RuntimeCache:
    """
    运行时缓存管理器，统一对外接口，可配置后端
    """
    _instance = None
    _initialized = False

    def __new__(cls):
        # 使用简单的单例模式（懒汉式）
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.logger = logging.getLogger("RuntimeCache")
            self.config = CacheConfig()
            self.backend: Optional[CacheBackend] = None
            self._init_backend()
            self._start_cleanup_thread()
            self._initialized = True

    def _init_backend(self):
        """根据配置实例化后端，实现可插拔"""
        backend_cls_name = self.config.backend
        try:
            # 尝试从全局命名空间获取类（简单方式，实际可用反射或注册表）
            backend_cls = globals().get(backend_cls_name)
            if backend_cls is None:
                # 如果找不到，尝试导入其他模块？（此处只支持内存后端）
                raise ValueError(f"未找到缓存后端类：{backend_cls_name}")
            self.backend = backend_cls(self.config)
            self.logger.info(f"已加载缓存后端：{backend_cls_name}")
        except Exception as e:
            self.logger.error(f"初始化缓存后端失败：{e}，使用默认内存后端")
            self.backend = MemoryCacheBackend(self.config)

    def _start_cleanup_thread(self):
        """启动定期清理过期条目的守护线程"""
        if isinstance(self.backend, MemoryCacheBackend):
            def cleanup_loop():
                while True:
                    time.sleep(self.config.cleanup_interval)
                    try:
                        self.backend._cleanup_expired()
                    except Exception as e:
                        self.logger.error(f"缓存清理异常：{e}")
            t = threading.Thread(target=cleanup_loop, daemon=True, name="CacheCleaner")
            t.start()
            self.logger.info("缓存定期清理线程已启动")

    def get(self, key: str) -> Any:
        """获取缓存值"""
        try:
            return self.backend.get(key)
        except Exception as e:
            self.logger.error(f"获取缓存失败 key={key}：{e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值"""
        try:
            self.backend.set(key, value, ttl)
        except Exception as e:
            self.logger.error(f"设置缓存失败 key={key}：{e}")

    def delete(self, key: str) -> bool:
        """删除缓存键"""
        try:
            return self.backend.delete(key)
        except Exception as e:
            self.logger.error(f"删除缓存失败 key={key}：{e}")
            return False

    def clear(self) -> None:
        """清空所有缓存"""
        try:
            self.backend.clear()
            self.logger.info("缓存已完全清空")
        except Exception as e:
            self.logger.error(f"清空缓存失败：{e}")

    def size(self) -> int:
        """返回当前缓存条目数"""
        try:
            return self.backend.size()
        except Exception as e:
            self.logger.error(f"获取缓存大小失败：{e}")
            return 0

    # 支持热插拔：动态切换后端（需确保新后端实现了接口）
    def switch_backend(self, backend_cls_name: str) -> bool:
        """
        切换到指定的后端，返回是否成功
        要求新后端构造参数与当前配置兼容
        """
        try:
            backend_cls = globals().get(backend_cls_name)
            if backend_cls is None:
                raise ValueError(f"未找到后端类：{backend_cls_name}")
            new_backend = backend_cls(self.config)
            # 可选择性迁移数据？此处略
            self.backend = new_backend
            self.logger.info(f"缓存后端已切换至：{backend_cls_name}")
            return True
        except Exception as e:
            self.logger.error(f"切换后端失败：{e}")
            return False


# ---------- 自测 ----------
if __name__ == "__main__":
    # 配置基础日志输出
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 使用单例缓存实例
    cache = RuntimeCache()

    print("=== 基础功能测试 ===")
    # 设置值
    cache.set("test_key", "Hello NovelOS", ttl=5)
    print(f"Set 'test_key': test_value")
    # 获取
    value = cache.get("test_key")
    print(f"Get 'test_key': {value}")

    # 测试过期（等待6秒后查看）
    print("等待6秒后测试过期...")
    time.sleep(6)
    value_expired = cache.get("test_key")
    print(f"Get 'test_key' after expiration: {value_expired}")  # 应为None

    # 测试删除
    cache.set("del_key", "will be deleted")
    print(f"Delete 'del_key': {cache.delete('del_key')}")
    print(f"Get 'del_key' after delete: {cache.get('del_key')}")

    # 测试清空