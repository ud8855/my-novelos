import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List

# ---------- 日志配置 ----------
logger = logging.getLogger(__name__)

# ---------- 协议配置 ----------
class MemoryConfig:
    """
    记忆模块配置容器。
    提供默认值，允许外部覆盖，保证配置化。
    """
    DEFAULT_CONFIG = {
        "storage_backend": "in_memory",
        "max_entries": 1000,
        "persist": False,
        "serializer": "json",
        "cache_ttl": 3600,               # 缓存生存时间（秒）
        "enable_compression": False,
    }

    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        self._config = {}
        self._config.update(self.DEFAULT_CONFIG)
        if config_dict:
            self._config.update(config_dict)
        logger.debug(f"MemoryConfig initialized with: {self._config}")

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        return self._config.copy()

# ---------- 记忆协议抽象 ----------
class MemoryProtocol(ABC):
    """
    记忆服务核心协议。
    所有记忆后端必须继承此类并实现全部抽象方法，
    以保证可插拔性和行为一致性。
    """
    def __init__(self, config: Optional[MemoryConfig] = None):
        self.config = config if config is not None else MemoryConfig()
        self._logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._logger.info(f"初始化记忆服务，配置：{self.config.to_dict()}")

    @abstractmethod
    def save(self, key: str, data: Any, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        保存一条记忆。
        :param key: 唯一标识符
        :param data: 记忆内容（任意可序列化结构）
        :param metadata: 附加元数据（标签、时间戳等）
        :return: 保存是否成功
        """
        ...

    @abstractmethod
    def load(self, key: str) -> Optional[Any]:
        """
        加载指定 key 的记忆。
        :return: 记忆内容，未找到返回 None
        """
        ...

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        删除指定 key 的记忆。
        :return: 删除是否成功（key 不存在也视为成功）
        """
        ...

    @abstractmethod
    def search(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        根据条件搜索记忆。
        :param query: 搜索条件字典，例如 {"tag": "对话记录", "time_range": [...]}
        :return: 匹配的记忆条目列表（至少包含 key 和 data）
        """
        ...

    @abstractmethod
    def clear(self) -> None:
        """清空当前记忆空间的所有数据。"""
        ...

    # ---------- 可选协议扩展 ----------
    def health_check(self) -> bool:
        """
        健康检查接口，子类可覆写以提供后端状态检测。
        默认返回 True。
        """
        self._logger.debug("执行基础健康检查")
        return True

    def get_stats(self) -> Dict[str, Any]:
        """
        返回后端统计信息（条目数、存储占用等），子类可覆写。
        默认返回空。
        """
        return {}

# ---------- 可插拔工厂 ----------
class MemoryFactory:
    """
    记忆服务工厂。
    通过注册机制实现后端的动态发现与实例化，满足热插拔要求。
    """
    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str, backend_cls: type):
        """注册一个记忆后端实现类"""
        if not issubclass(backend_cls, MemoryProtocol):
            raise TypeError(
                f"注册失败：{backend_cls} 必须继承 MemoryProtocol"
            )
        cls._registry[name] = backend_cls
        logger.info(f"记忆后端已注册：{name} -> {backend_cls.__name__}")

    @classmethod
    def unregister(cls, name: str):
        """移除一个已注册的后端"""
        if name in cls._registry:
            del cls._registry[name]
            logger.info(f"记忆后端已移除：{name}")

    @classmethod
    def list_backends(cls) -> List[str]:
        """列出当前可用的后端名称"""
        return list(cls._registry.keys())

    @classmethod
    def create(cls, backend_name: str, config: Optional[MemoryConfig] = None) -> MemoryProtocol:
        """
        根据名称创建记忆服务实例。
        :param backend_name: 注册时使用的名称
        :param config: 传给后端的配置对象
        :return: MemoryProtocol 实例
        :raises ValueError: 若后端不存在
        """
        if backend_name not in cls._registry:
            available = ", ".join(cls._registry.keys()) or "(无)"
            raise ValueError(
                f"未知记忆后端：{backend_name}，可用后端：{available}"
            )
        backend_cls = cls._registry[backend_name]
        logger.info(f"创建记忆服务实例：{backend_name} ({backend_cls.__name__})")
        return backend_cls(config=config)

# ---------- 自测 ----------
if __name__ == "__main__":
    # 配置日志输出
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )

    print("===== 记忆协议自测开始 =====")

    # 1. 测试配置
    cfg = MemoryConfig({"storage_backend": "demo", "max_entries": 500})
    print(f"配置内容: {cfg.to_dict()}")

    # 2. 定义一个用于测试的虚拟后端
    class DummyMemory(MemoryProtocol):
        """用于自测的虚拟记忆后端，仅打印操作日志"""
        def __init__(self, config=None):
            super().__init__(config)
            self._store = {}

        def save(self, key, data, metadata=None):
            self._logger.info(f"保存记忆: key={key}, metadata={metadata}")
            self._store[key] = (data, metadata)
            return True

        def load(self, key):
            self._logger.info(f"加载记忆: key={key}")
            entry = self._store.get(key)
            return entry[0] if entry else None

        def delete(self, key):
            self._logger.info(f"删除记忆: key={key}")