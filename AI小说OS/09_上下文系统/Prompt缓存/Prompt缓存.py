from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

# 配置默认值，可通过外部环境变量或全局配置覆盖
DEFAULT_CONFIG: Dict[str, Any] = {
    "cache_type": "memory",      # 缓存后端类型: "memory", "redis", "disk" (预留)
    "max_size": 1000,           # 内存缓存最大条目数
    "ttl": None,                # 过期时间(秒), None表示永不过期
    "log_level": "INFO",        # 日志级别
}

class PromptCacheInterface(ABC):
    """Prompt缓存接口，所有缓存后端必须实现此接口，确保可插拔"""

    @abstractmethod
    def get(self, key: str) -> Optional[str]:
        """根据key获取缓存的prompt，如果不存在返回None"""
        pass

    @abstractmethod
    def set(self, key: str, prompt: str, ttl: Optional[int] = None) -> None:
        """将prompt缓存到key，ttl为过期秒数，None表示使用全局配置"""
        pass

    @abstractmethod
    def invalidate(self, key: str) -> None:
        """清除指定key的缓存"""
        pass

    @abstractmethod
    def clear(self) -> None:
        """清空所有缓存"""
        pass

    @abstractmethod
    def size(self) -> int:
        """返回当前缓存条目数"""
        pass

class InMemoryPromptCache(PromptCacheInterface):
    """基于字典的内存缓存实现，支持最大容量和条目过期"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or DEFAULT_CONFIG
        self.max_size = self.config.get("max_size", 1000)
        self.ttl = self.config.get("ttl", None)      # 全局ttl
        self.cache: Dict[str, str] = {}
        self.access_times: Dict[str, float] = {}     # 简单记录最后访问时间，用于ttl
        self.logger = logging.getLogger(f"{__name__}.InMemoryPromptCache")
        self.logger.setLevel(self.config.get("log_level", "INFO"))

    def get(self, key: str) -> Optional[str]:
        if key not in self.cache:
            self.logger.debug(f"缓存未命中: {key}")
            return None
        # 检查ttl
        if self.ttl is not None:
            import time
            if time.time() - self.access_times.get(key, 0) > self.ttl:
                self.logger.debug(f"缓存过期: {key}")
                self.invalidate(key)
                return None
        self.logger.debug(f"缓存命中: {key}")
        return self.cache[key]

    def set(self, key: str, prompt: str, ttl: Optional[int] = None) -> None:
        if len(self.cache) >= self.max_size:
            # 简单策略：移除最早插入的键 (这里先用popitem移除任意键，后续可优化)
            removed_key = next(iter(self.cache))
            self.logger.warning(f"缓存已满，移除最早键: {removed_key}")
            self.invalidate(removed_key)
        self.cache[key] = prompt
        import time
        self.access_times[key] = time.time()
        self.logger.debug(f"缓存写入: {key} (ttl={ttl or self.ttl})")

    def invalidate(self, key: str) -> None:
        self.cache.pop(key, None)
        self.access_times.pop(key, None)
        self.logger.debug(f"缓存删除: {key}")

    def clear(self) -> None:
        self.cache.clear()
        self.access_times.clear()
        self.logger.info("缓存已清空")

    def size(self) -> int:
        return len(self.cache)

# 工厂函数，根据配置创建缓存实例，实现可插拔
_cache_instance: Optional[PromptCacheInterface] = None

def get_prompt_cache(config: Optional[Dict[str, Any]] = None) -> PromptCacheInterface:
    """获取全局prompt缓存实例，延迟初始化，支持配置注入"""
    global _cache_instance
    if _cache_instance is None:
        if config is None:
            config = DEFAULT_CONFIG
        cache_type = config.get("cache_type", "memory")
        if cache_type == "memory":
            _cache_instance = InMemoryPromptCache(config)
        elif cache_type == "redis":
            # 预留Redis缓存实现，需安装redis包
            raise NotImplementedError("Redis缓存后端暂未实现")
        elif cache_type == "disk":
            raise NotImplementedError("磁盘缓存后端暂未实现")
        else:
            raise ValueError(f"不支持的缓存类型: {cache_type}")
    return _cache_instance

# 自测代码
if __name__ == "__main__":
    # 配置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("=== Prompt缓存模块自测 ===")
    # 使用默认内存缓存
    cache = get_prompt_cache()

    # 测试set/get
    cache.set("test_key", "这是一个测试prompt")
    assert cache.get("test_key") == "这是一个测试prompt"
    print("步骤1: 写入并读取成功")

    # 测试不存在的key
    assert cache.get("non_exist") is None
    print("步骤2: 不存在的key返回None")

    # 测试invalidate
    cache.invalidate("test_key")
    assert cache.get("test_key") is None
    print("步骤3: 删除后读取返回None")

    # 测试容量限制 (max_size默认为1000，这里测试小容量)
    small_cache = get_prompt_cache({"max_size": 2})
    small_cache.set("a", "1")
    small_cache.set("b", "2")
    small_cache.set("c", "3")  # 应当触发逐出
    assert small_cache.size() <= 2
    print("步骤4: 容量限制测试通过")

    # 测试ttl (这里不好在短时间自测，仅演示逻辑)
    import time
    ttl_cache = get_prompt_cache({"max_size": 10, "ttl": 1})  # 1秒过期
    ttl_cache.set("ttl_key", "短期缓存")
    assert ttl_cache.get("ttl_key") == "短期缓存"
    time.sleep(1.1)
    assert ttl_cache.get("ttl_key") is None
    print("步骤5: TTL过期测试通过")

    # 测试clear
    cache.clear()
    assert cache.size() == 0
    print("步骤6: 清空缓存测试通过")

    print("所有自测通过！")