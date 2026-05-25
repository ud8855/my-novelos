"""
消息总线模块 (Message Bus)
路径: 05_核心总线/消息总线/消息总线.py
层: 核心总线层 (05_核心总线)
依赖: 无外部依赖 (仅标准库)
被调用: 所有需要模块间解耦通信的组件 (如 Agent, 模型协同, UI 等)
解决: 提供统一的事件消息发布与订阅机制，实现模块间的松耦合通信，支持处理器的动态插拔、配置化与日志跟踪。
"""

import logging
import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

# ----------------------------------------------------------------
# 配置管理 (配置化)
# ----------------------------------------------------------------
class MessageBusConfig:
    """消息总线配置类，集中管理所有可配置项。支持从字典或配置文件加载。"""
    def __init__(self, config_dict: Optional[Dict] = None):
        self.enable_logging: bool = True
        self.log_level: int = logging.INFO
        self.max_queue_size: int = 1000       # 最大待处理消息数 (若启用异步)
        self.enable_async_dispatch: bool = False  # 是否异步分发 (骨架暂时未实现)
        self.plugin_dirs: List[str] = []      # 可插拔处理器自动加载路径
        # 通过传入字典覆盖默认配置
        if config_dict:
            for key, value in config_dict.items():
                if hasattr(self, key):
                    setattr(self, key, value)

# ----------------------------------------------------------------
# 日志器 (日志)
# ----------------------------------------------------------------
def _setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """创建并配置一个日志器，用于记录消息总线事件。"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger

# ----------------------------------------------------------------
# 消息定义
# ----------------------------------------------------------------
class Message:
    """通用消息体，包含消息类型、发起者、负载数据等。"""
    def __init__(self, msg_type: str, sender: str = "unknown", payload: Any = None):
        self.type = msg_type          # 消息类型，用于订阅过滤
        self.sender = sender          # 发送者标识
        self.payload = payload        # 携带的数据
        self.timestamp = None         # 可记录时间戳

    def __repr__(self):
        return f"Message(type='{self.type}', sender='{self.sender}', payload={self.payload!r})"

# ----------------------------------------------------------------
# 可插拔接口 (可插拔)
# ----------------------------------------------------------------
class MessageHandler(ABC):
    """
    消息处理器抽象基类。
    所有自定义处理器必须继承此类并实现 handle 方法。
    可动态注册/注销，实现插拔式功能扩展。
    """
    @abstractmethod
    def handle(self, message: Message) -> None:
        """处理消息。子类实现具体逻辑。"""
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__}>"

# 为了方便，也支持简单的函数处理器 (callable)
HandlerType = Callable[[Message], None]

# ----------------------------------------------------------------
# 消息总线核心
# ----------------------------------------------------------------
class MessageBus:
    """
    核心消息总线，提供 publish/subscribe 机制。
    支持：
    - 按消息类型订阅处理器 (MessageHandler 或 callable)
    - 动态注册/注销
    - 同步分发 (当前版本)
    - 日志记录所有关键操作
    - 配置化 (通过 MessageBusConfig)
    """

    def __init__(self, config: Optional[MessageBusConfig] = None):
        self.config = config if config else MessageBusConfig()
        self.logger = _setup_logger("MessageBus", self.config.log_level) if self.config.enable_logging else None

        # 订阅表: msg_type -> list of (handler_priority, handler_or_callable)
        self._subscribers: Dict[str, List[tuple]] = {}
        self._lock = threading.Lock()  # 简单的线程安全锁

        if self.logger:
            self.logger.info("消息总线初始化完成，配置: %s", self.config.__dict__)

    # ---------- 订阅管理 ----------
    def subscribe(self, msg_type: str, handler: HandlerType, priority: int = 0):
        """
        订阅消息类型。
        :param msg_type: 消息类型字符串
        :param handler: 处理器函数对象
        :param priority: 优先级 (暂未实际影响执行顺序，预留)
        """
        with self._lock:
            if msg_type not in self._subscribers:
                self._subscribers[msg_type] = []
            # 避免重复添加相同函数 (简单判断)
            if not any(existing_handler == handler for _, existing_handler in self._subscribers[msg_type]):
                self._subscribers[msg_type].append((priority, handler))
                if self.logger:
                    self.logger.debug("订阅消息类型 '%s' 成功: %s", msg_type, handler)

    def subscribe_handler(self, msg_type: str, handler: MessageHandler, priority: int = 0):
        """订阅一个 MessageHandler 实例 (可插拔)。"""
        self.subscribe(msg_type, handler.handle, priority)

    def unsubscribe(self, msg_type: str, handler: HandlerType):
        """注销某个消息类型的处理器。"""
        with self._lock:
            if msg_type in self._subscribers:
                self._subscribers[msg_type] = [
                    (p, h) for p, h in self._subscribers[msg_type] if h != handler
                ]
                if self.logger:
                    self.logger.debug("注销消息类型 '%s' 的处理器 %s", msg_type, handler)

    def unsubscribe_handler(self, msg_type: str, handler: MessageHandler):
        """注销一个 MessageHandler 实例。"""
        self.unsubscribe(msg_type, handler.handle)

    # ---------- 消息发布 ----------
    def publish(self, message: Message):
        """
        同步发布消息给所有订阅者。
        (未来可扩展异步分发)
        """
        if self.logger:
            self.logger.info("发布消息: %s", message)

        with self._lock:
            subscribers = self._subscribers.get(message.type, []).copy()

        for priority, handler in subscribers:
            try:
                if self.logger:
                    self.logger.debug("分发消息至 %s", handler)
                handler(message)
            except Exception as e:
                if self.logger:
                    self.logger.error("处理器 %s 处理消息时异常: %s", handler, e, exc_info=True)
                # 异常不中断其他处理器，遵循健壮性原则

    def publish_simple(self, msg_type: str, sender: str = "unknown", payload: Any = None):
        """快捷发布接口。"""
        msg = Message(msg_type, sender, payload)
        self.publish(msg)

    # ---------- 工具与查询 ----------
    def list_subscribed_types(self) -> List[str]:
        """返回当前所有被订阅的消息类型。"""
        with self._lock:
            return list(self._subscribers.keys())

    def get_subscribers_by_type(self, msg_type: str) -> List[HandlerType]:
        """返回指定消息类型的所有处理器 (callable 列表)。"""
        with self._lock:
            return [handler for _, handler in self._subscribers.get(msg_type, [])]

# ----------------------------------------------------------------
# 自测 (Self-test)
# ----------------------------------------------------------------
if __name__ == "__main__":
    # 示例配置
    config = MessageBusConfig({
        "enable_logging": True,
        "log_level": logging.DEBUG
    })
    bus = MessageBus(config)

    # 定义一个简单的函数处理器
    def on_user_login(message: Message):
        print(f"[处理器] 收到登录消息: 用户 {message.payload} 上线")

    def on_system_alert(message: Message):
        print(f"[处理器] 系统警告: {message.payload}")

    # 定义可插拔处理器类
    class LogHandler(MessageHandler):
        def handle(self, message: Message):
            print(f"[LogHandler] 记录: {message}")

    # 注册
    bus.subscribe("user.login", on_user_login)
    bus.subscribe_handler("system.alert", LogHandler())
    bus.subscribe("system.alert", on_system_alert)

    # 发布消息测试
    bus.publish_simple("user.login", sender="login_module", payload="Alice")
    bus.publish_simple("system.alert", sender="monitor", payload="磁盘空间不足")

    # 打印订阅状态
    print("\n当前订阅类型:", bus.list_subscribed_types())
    print("system.alert 订阅者:", bus.get_subscribers_by_type("system.alert"))

    # 注销测试
    bus.unsubscribe("system.alert", on_system_alert)
    print("注销后 system.alert 订阅者:", bus.get_subscribers_by_type("system.alert"))

    # 发布无订阅者的消息 (应无输出，但日志会记录)
    bus.publish_simple("system.alert", payload="无处理器接收")
    print("测试完成")