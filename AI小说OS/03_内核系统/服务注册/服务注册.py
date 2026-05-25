"""
服务注册模块
位于：03_内核系统/服务注册/服务注册.py
职责：提供服务注册、发现、注销功能，支持可插拔的后端存储，统一服务管理。
依赖：无外部模块，仅标准库
被调用：其他核心模块（如调度器、通信总线）需要发现服务时调用。
"""

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# ---------- 日志配置 ----------
logger = logging.getLogger("Kernel.ServiceRegistry")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


# ---------- 服务信息数据结构 ----------
@dataclass
class ServiceInfo:
    """描述一个服务的元信息"""
    service_name: str                     # 服务唯一标识
    endpoint: str                         # 服务地址（如 URL、IPC 路径）
    metadata: Dict[str, Any] = field(default_factory=dict)  # 附加属性
    status: str = "active"                # 服务状态


# ---------- 抽象存储后端 ----------
class ServiceRegistryBackend(ABC):
    """服务注册存储后端的抽象接口，支持可插拔替换"""

    @abstractmethod
    def register(self, service: ServiceInfo) -> bool:
        """注册服务，如果已存在同名服务则更新，返回是否成功"""
        ...

    @abstractmethod
    def unregister(self, service_name: str) -> bool:
        """注销服务，返回是否成功"""
        ...

    @abstractmethod
    def get(self, service_name: str) -> Optional[ServiceInfo]:
        """根据名称获取服务信息"""
        ...

    @abstractmethod
    def list_services(self) -> List[ServiceInfo]:
        """获取所有已注册服务列表"""
        ...


# ---------- 内存后端实现 ----------
class InMemoryBackend(ServiceRegistryBackend):
    """基于内存的服务注册后端，适用于单进程环境"""

    def __init__(self):
        self._store: Dict[str, ServiceInfo] = {}
        self._lock = threading.Lock()

    def register(self, service: ServiceInfo) -> bool:
        with self._lock:
            exists = service.service_name in self._store
            self._store[service.service_name] = service
            if exists:
                logger.info("更新服务: %s -> %s", service.service_name, service.endpoint)
            else:
                logger.info("注册服务: %s -> %s", service.service_name, service.endpoint)
            return True

    def unregister(self, service_name: str) -> bool:
        with self._lock:
            if service_name in self._store:
                del self._store[service_name]
                logger.info("注销服务: %s", service_name)
                return True
            logger.warning("尝试注销不存在的服务: %s", service_name)
            return False

    def get(self, service_name: str) -> Optional[ServiceInfo]:
        with self._lock:
            return self._store.get(service_name)

    def list_services(self) -> List[ServiceInfo]:
        with self._lock:
            return list(self._store.values())


# ---------- 服务注册主类 ----------
class ServiceRegistry:
    """
    内核服务注册中心
    通过配置选择存储后端，提供统一的服务管理接口
    """

    # 默认配置
    DEFAULT_CONFIG = {
        "backend": "memory",          # 后端类型: memory, redis, etc.
        "memory": {},                 # 内存后端无需额外参数
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化服务注册中心
        :param config: 配置字典，如果为None则使用默认配置
        """
        self._config = config if config is not None else self.DEFAULT_CONFIG
        self._backend = self._create_backend()
        logger.info("服务注册中心初始化完成，后端: %s", self._config.get("backend"))

    def _create_backend(self) -> ServiceRegistryBackend:
        """根据配置创建存储后端实例"""
        backend_type = self._config.get("backend", "memory")
        if backend_type == "memory":
            return InMemoryBackend()
        # 未来可扩展其他后端（Redis、数据库等）
        # elif backend_type == "redis":
        #     return RedisBackend(self._config.get("redis", {}))
        else:
            raise ValueError(f"不支持的后端类型: {backend_type}")

    def register_service(self, service: ServiceInfo) -> bool:
        """注册服务"""
        try:
            return self._backend.register(service)
        except Exception as e:
            logger.error("注册服务 %s 时发生异常: %s", service.service_name, e)
            return False

    def unregister_service(self, service_name: str) -> bool:
        """注销服务"""
        try:
            return self._backend.unregister(service_name)
        except Exception as e:
            logger.error("注销服务 %s 时发生异常: %s", service_name, e)
            return False

    def get_service(self, service_name: str) -> Optional[ServiceInfo]:
        """获取服务信息"""
        try:
            return self._backend.get(service_name)
        except Exception as e:
            logger.error("获取服务 %s 时发生异常: %s", service_name, e)
            return None

    def list_services(self) -> List[ServiceInfo]:
        """列出所有服务"""
        try:
            return self._backend.list_services()
        except Exception as e:
            logger.error("列出服务列表时发生异常: %s", e)
            return []


# ---------- 自测 ----------
if __name__ == "__main__":
    # 测试基本功能
    registry = ServiceRegistry()

    # 创建服务
    svc1 = ServiceInfo(
        service_name="agent_loader",
        endpoint="ipc:///tmp/agent_loader.sock",
        metadata={"version": "1.0"}
    )
    svc2 = ServiceInfo(
        service_name="prompt_template_svc",
        endpoint="http://localhost:8001",
        metadata={"version": "2.0"}
    )

    # 注册
    assert registry.register_service(svc1) == True
    assert registry.register_service(svc2) == True

    # 重复注册（更新）
    svc1_updated = ServiceInfo(
        service_name="agent_loader",
        endpoint="ipc:///tmp/agent_loader_v2.sock",
        metadata={"version": "1.1"}
    )
    assert registry.register_service(svc1_updated) == True

    # 获取
    fetched = registry.get_service("agent_loader")
    assert fetched is not None
    assert fetched.endpoint == "ipc:///tmp/agent_loader_v2.sock", "更新未生效"

    # 列出
    services = registry.list_services()
    assert len(services) == 2
    print("所有服务:")
    for s in services:
        print(f"  {s.service_name} -> {s.endpoint}")

    # 注销
    assert registry.unregister_service("prompt_template_svc") == True
    assert registry.unregister_service("non_existent") == False

    # 验证
    assert registry.get_service("prompt_template_svc") is None
    assert len(registry.list_services()) == 1

    print("服务注册模块自测通过。")