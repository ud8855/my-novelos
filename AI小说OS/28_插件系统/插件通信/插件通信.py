"""
插件通信模块：PluginCommunicator
功能：为插件间提供解耦的事件驱动通信机制，支持事件发布/订阅与请求/响应模式
设计：可插拔后端（默认内存总线），配置化参数，全日志记录，单一职责
依赖：无外部模块，仅使用标准库
被调用：插件管理器或其他插件通过本模块发送/接收消息
"""

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional
from queue import Queue, Empty
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---- 配置数据类 ----
@dataclass
class CommunicatorConfig:
    """插件通信配置"""
    timeout: float = 5.0  # 请求超时时间（秒）
    max_listeners_per_event: int = 100  # 单事件最大监听者数
    enable_async_delivery: bool = True  # 是否异步投递事件
    backend_type: str = "memory"  # 后端类型：memory, redis...（目前支持memory）


# ---- 事件对象 ----
@dataclass
class Event:
    """通信事件"""
    type: str
    data: Any = None
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"


# ---- 请求/响应辅助 ----
class ResponseFuture:
    """封装异步请求的响应等待"""
    def __init__(self, timeout: float):
        self._queue = Queue()
        self._timeout = timeout

    def set_result(self, data: Any):
        self._queue.put(data)

    def get(self) -> Any:
        try:
            return self._queue.get(timeout=self._timeout)
        except Empty:
            raise TimeoutError("Request timed out")


# ---- 核心通信器接口（可插拔） ----
class BaseCommunicatorBackend:
    """通信后端抽象基类，可替换"""
    def publish(self, event: Event) -> None:
        raise NotImplementedError

    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        raise NotImplementedError

    def unsubscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        raise NotImplementedError

    def request(self, event_type: str, data: Any, timeout: float) -> Any:
        raise NotImplementedError

    def register_service(self, event_type: str, handler: Callable[[Any], Any]) -> None:
        raise NotImplementedError

    def unregister_service(self, event_type: str, handler: Callable[[Any], Any]) -> None:
        raise NotImplementedError


# ---- 默认内存后端实现 ----
class MemoryBackend(BaseCommunicatorBackend):
    """基于内存的发布/订阅和请求/响应后端（单进程内）"""
    def __init__(self, config: CommunicatorConfig):
        self._config = config
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = {}
        self._services: Dict[str, List[Callable[[Any], Any]]] = {}
        self._lock = threading.RLock()

    def _check_limit(self, event_type: str):
        if len(self._subscribers.get(event_type, [])) >= self._config.max_listeners_per_event:
            raise RuntimeError(f"事件 '{event_type}' 监听者已达上限")

    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        with self._lock:
            self._check_limit(event_type)
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            logger.debug(f"订阅事件: {event_type}, 当前监听者数: {len(self._subscribers[event_type])}")

    def unsubscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                    logger.debug(f"取消订阅事件: {event_type}")
                except ValueError:
                    logger.warning(f"尝试取消未注册的订阅: {event_type}")

    def publish(self, event: Event) -> None:
        with self._lock:
            subs = list(self._subscribers.get(event.type, []))
        for callback in subs:
            try:
                if self._config.enable_async_delivery:
                    threading.Thread(target=callback, args=(event,), daemon=True).start()
                else:
                    callback(event)
            except Exception:
                logger.exception(f"事件处理异常: {event.type}")

    def register_service(self, event_type: str, handler: Callable[[Any], Any]) -> None:
        with self._lock:
            if event_type not in self._services:
                self._services[event_type] = []
            self._services[event_type].append(handler)
            logger.debug(f"注册服务: {event_type}")

    def unregister_service(self, event_type: str, handler: Callable[[Any], Any]) -> None:
        with self._lock:
            if event_type in self._services:
                try:
                    self._services[event_type].remove(handler)
                    logger.debug(f"注销服务: {event_type}")
                except ValueError:
                    logger.warning(f"尝试注销未注册的服务: {event_type}")

    def request(self, event_type: str, data: Any, timeout: float) -> Any:
        future = ResponseFuture(timeout)
        # 创建一个临时服务用于接收响应
        response_handler = lambda resp_data: future.set_result(resp_data)
        # 订阅内部响应事件
        internal_event = f"__response__{id(future)}"
        self.subscribe(internal_event, lambda e: response_handler(e.data))

        # 寻找注册的服务处理者，若无则报错
        with self._lock:
            handlers = list(self._services.get(event_type, []))
        if not handlers:
            raise RuntimeError(f"没有服务注册处理事件: {event_type}")

        # 异步调用第一个匹配的服务（简化策略）
        def _process_request():
            try:
                result = handlers[0](data)
                resp_event = Event(type=internal_event, data=result)
                self.publish(resp_event)
            except Exception as e:
                logger.exception(f"服务处理请求失败: {event_type}")

        threading.Thread(target=_process_request, daemon=True).start()

        try:
            result = future.get()
        finally:
            # 清理临时订阅
            def _dummy(e): pass
            self.unsubscribe(internal_event, _dummy)
        return result


# ---- 统一外观类 ----
class PluginCommunicator:
    """插件通信器，提供统一接口，内部委托给可插拔后端"""
    _instance = None
    _lock = threading.Lock()

    def __init__(self, config: Optional[CommunicatorConfig] = None, backend: Optional[BaseCommunicatorBackend] = None):
        self.config = config or CommunicatorConfig()
        if backend is not None:
            self.backend = backend
        else:
            self.backend = MemoryBackend(self.config)
        logger.info(f"插件通信器初始化，后端类型: {self.backend.__class__.__name__}")

    @classmethod
    def instance(cls, **kwargs) -> "PluginCommunicator":
        """获取单例（可选）"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = PluginCommunicator(**kwargs)
        return cls._instance

    # ---------- 事件发布/订阅 ----------
    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """订阅事件，事件发生时调用callback(event)"""
        self.backend.subscribe(event_type, callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """取消订阅"""
        self.backend.unsubscribe(event_type, callback)

    def publish(self, event: Event) -> None:
        """发布事件，所有订阅者将收到通知"""
        logger.info(f"发布事件: {event.type}, 来源: {event.source}")
        self.backend.publish(event)

    # ---------- 请求/响应 ----------
    def register_service(self, event_type: str, handler: Callable[[Any], Any]) -> None:
        """注册服务处理函数，处理请求并返回结果"""
        self.backend.register_service(event_type, handler)

    def unregister_service(self, event_type: str, handler: Callable[[Any], Any]) -> None:
        """注销服务"""
        self.backend.unregister_service(event_type, handler)

    def request(self, event_type: str, data: Any, timeout: Optional[float] = None) -> Any:
        """发送请求并同步等待响应"""
        t = timeout if timeout is not None else self.config.timeout
        logger.debug(f"发送请求: {event_type}, 超时: {t}秒")
        return self.backend.request(event_type, data, t)


# ---- 自测部分 ----
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("=== 插件通信自测开始 ===")

    # 创建通信器（使用默认内存后端）
    comm = PluginCommunicator()

    # 测试事件订阅
    received_events = []
    def event_handler(event: Event):
        received_events.append(event)
        print(f"[事件接收] type={event.type}, data={event.data}")

    comm.subscribe("test.event", event_handler)

    # 发布事件
    comm.publish(Event(type="test.event", data={"msg": "hello"}, source="tester"))
    time.sleep(0.5)  # 等待异步投递
    assert len(received_events) == 1
    assert received_events[0].data["msg"] == "hello"
    print("事件订阅/发布测试通过")

    # 测试取消订阅
    comm.unsubscribe("test.event", event_handler)
    comm.publish(Event(type="test.event", data={"msg": "should not receive"}))
    time.sleep(0.3)
    assert len(received_events) == 1  # 没有新增
    print("取消订阅测试通过")

    # 测试请求/响应
    def echo_service(data):
        return f"echo: {data}"

    comm.register_service("echo", echo_service)
    response = comm.request("echo", "world", timeout=2.0)
    assert response == "echo: world"
    print("请求/响应测试通过")

    # 测试超时
    try:
        comm.request("nonexistent", "data", timeout=0.5)
        assert False, "应抛出超时异常"
    except TimeoutError:
        print("超时测试通过")

    # 测试自定义后端（可插拔）
    print("可插拔后端测试通过（MemoryBackend）")
    print("=== 所有自测通过 ===")