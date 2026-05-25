# 通知系统.py
"""
通知系统模块 - 核心总线层通知/事件分发
位于 05_核心总线/通知系统
职责：提供统一的事件通知机制，支持发布-订阅模式，解耦模块间通信
依赖：日志系统（内置 logging），配置模块（可注入配置对象）
被调用：上层各业务模块通过核心总线获取通知系统实例，进行事件监听与触发
解决：模块间一对多通信，避免直接调用，提升解耦性与可扩展性
"""

import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field

# 配置默认值（可在初始化时覆盖）
DEFAULT_MAX_LISTENERS = 1000
DEFAULT_ENABLE_LOGGING = True
DEFAULT_LOG_LEVEL = logging.DEBUG

@dataclass
class NotificationConfig:
    """通知系统配置"""
    max_listeners: int = DEFAULT_MAX_LISTENERS  # 单个事件最大监听者数量
    enable_logging: bool = DEFAULT_ENABLE_LOGGING  # 是否启用事件日志
    log_level: int = DEFAULT_LOG_LEVEL  # 日志级别
    # 可插拔：未来可添加持久化、异步等选项

class NotificationSystem:
    """
    核心通知系统，负责事件的注册、注销与分发
    设计为单例（通过核心总线管理），但本身不强制单例，保证可插拔
    """

    def __init__(self, config: Optional[NotificationConfig] = None):
        """
        初始化通知系统
        :param config: 可选配置对象，未提供则使用默认值
        """
        self.config = config if config else NotificationConfig()
        self._listeners: Dict[str, List[Callable[..., None]]] = {}
        self._lock = threading.RLock()  # 保证线程安全

        # 日志设置
        self.logger = logging.getLogger(self.__class__.__name__)
        if self.config.enable_logging:
            self.logger.setLevel(self.config.log_level)
            # 若尚未添加处理器，添加控制台输出
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter(
                    '[%(asctime)s] [%(name)s] %(levelname)s: %(message)s'
                )
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
            self.logger.info("通知系统初始化完成")
        else:
            self.logger.handlers.clear()  # 移除所有处理器以抑制输出
            self.logger.addHandler(logging.NullHandler())

    def register(self, event_name: str, callback: Callable[..., None]) -> bool:
        """
        注册事件监听
        :param event_name: 事件名称
        :param callback: 回调函数，接收与事件相关的任意参数
        :return: 注册成功返回True，否则False
        """
        with self._lock:
            if event_name not in self._listeners:
                self._listeners[event_name] = []
            listeners = self._listeners[event_name]

            # 检查重复注册
            if callback in listeners:
                self.logger.warning(f"事件 '{event_name}' 的回调已注册，跳过重复添加")
                return False

            # 检查最大监听者限制
            if len(listeners) >= self.config.max_listeners:
                self.logger.error(
                    f"事件 '{event_name}' 监听者数量已达上限 {self.config.max_listeners}，注册失败"
                )
                return False

            listeners.append(callback)
            self.logger.debug(f"成功为事件 '{event_name}' 注册回调: {callback.__name__}")
            return True

    def unregister(self, event_name: str, callback: Callable[..., None]) -> bool:
        """
        注销事件监听
        :param event_name: 事件名称
        :param callback: 要移除的回调
        :return: 成功移除返回True，否则False
        """
        with self._lock:
            listeners = self._listeners.get(event_name)
            if not listeners:
                self.logger.warning(f"无事件 '{event_name}' 的监听者，无法注销")
                return False
            try:
                listeners.remove(callback)
                self.logger.debug(f"成功从事件 '{event_name}' 注销回调: {callback.__name__}")
                return True
            except ValueError:
                self.logger.warning(f"事件 '{event_name}' 中未找到指定回调，注销失败")
                return False

    def notify(self, event_name: str, *args, **kwargs) -> None:
        """
        触发事件通知，同步调用所有已注册的回调
        :param event_name: 事件名称
        :param args: 传递给回调的位置参数
        :param kwargs: 传递给回调的关键字参数
        """
        with self._lock:
            listeners = self._listeners.get(event_name, []).copy()  # 避免迭代时修改
        if not listeners:
            self.logger.debug(f"事件 '{event_name}' 无监听者，跳过通知")
            return

        self.logger.debug(f"开始触发事件 '{event_name}'，监听者数量: {len(listeners)}")
        for callback in listeners:
            try:
                callback(*args, **kwargs)
                self.logger.debug(f"事件 '{event_name}' 回调 {callback.__name__} 成功执行")
            except Exception as e:
                self.logger.error(
                    f"事件 '{event_name}' 回调 {callback.__name__} 执行异常: {repr(e)}",
                    exc_info=True  # 记录完整堆栈信息
                )

    def listener_count(self, event_name: str) -> int:
        """获取指定事件的监听者数量"""
        with self._lock:
            return len(self._listeners.get(event_name, []))

    def events(self) -> Set[str]:
        """返回所有已注册的事件名称集合"""
        with self._lock:
            return set(self._listeners.keys())

# 自测代码
if __name__ == '__main__':
    # 创建通知系统实例，可传入自定义配置
    config = NotificationConfig(enable_logging=True, log_level=logging.DEBUG)
    ns = NotificationSystem(config)

    # 定义两个回调
    def on_new_novel(title, author):
        print(f"【小说事件】新书发布: 《{title}》 作者: {author}")

    def on_chapter_update(chapter_id, content_len):
        print(f"【章节事件】章节 {chapter_id} 更新，字数: {content_len}")

    # 测试注册
    ns.register("novel.created", on_new_novel)
    ns.register("chapter.updated", on_chapter_update)

    # 测试再注册同一个回调（应警告）
    ns.register("novel.created", on_new_novel)

    # 发送通知
    ns.notify("novel.created", title="星辰变", author="我吃西红柿")
    ns.notify("chapter.updated", chapter_id=42, content_len=1234)

    # 注销与再通知（应不执行已注销的回调）
    ns.unregister("novel.created", on_new_novel)
    ns.notify("novel.created", title="星辰变（再版）", author="我吃西红柿")

    # 查看事件统计信息
    print(f"当前注册事件: {ns.events()}")
    print(f"'novel.created' 监听者数量: {ns.listener_count('novel.created')}")
    print(f"'chapter.updated' 监听者数量: {ns.listener_count('chapter.updated')}")