"""
模块：28_插件系统/插件生命周期.py
层级：插件系统（第八层）
依赖：标准库 logging、os、importlib、abc；配置模块（占位符）
被调用：插件系统其他模块（插件加载器、运行时管理器）
解决的问题：统一管理所有插件的生命周期状态转换，支持热插拔和异常恢复。
"""
import logging
import os
import importlib
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Dict, List, Optional, Callable, Any

# 日志配置（占位：实际由统一日志模块注入）
logger = logging.getLogger("PluginLifecycle")
logger.addHandler(logging.NullHandler())

# 默认插件目录（占位配置）
DEFAULT_PLUGIN_DIR = "plugins"


class PluginState(Enum):
    """插件生命周期状态枚举"""
    UNLOADED = auto()
    LOADED = auto()
    INITIALIZED = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPED = auto()
    ERROR = auto()


class PluginBase(ABC):
    """所有插件必须实现的抽象基类，当前为协议占位"""
    @abstractmethod
    def initialize(self) -> bool:
        """初始化插件，若失败返回False"""
        ...

    @abstractmethod
    def run(self) -> None:
        """插件主运行逻辑"""
        ...

    @abstractmethod
    def pause(self) -> None:
        """暂停插件"""
        ...

    @abstractmethod
    def resume(self) -> None:
        """从暂停恢复"""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """关闭插件并释放资源"""
        ...

    @abstractmethod
    def get_manifest(self) -> dict:
        """返回插件描述信息（名称、版本、依赖等）"""
        ...


class LifecycleHook(ABC):
    """生命周期钩子协议（可插拔）"""
    @abstractmethod
    def on_state_change(self, plugin_id: str, old_state: PluginState, new_state: PluginState) -> None:
        ...


class PluginLifecycleManager:
    """
    插件生命周期管理器
    职责：管理插件实例的加载、状态转换、热插拔、异常恢复。
    特性：可插拔（通过钩子注册监听）、日志记录、配置化（插件目录从配置读取）。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        :param config: 全局配置字典，至少包含 'plugin_dir' 键
        """
        self.plugin_dir = config.get("plugin_dir", DEFAULT_PLUGIN_DIR) if config else DEFAULT_PLUGIN_DIR
        # 存储已注册的插件实例 {plugin_id: (instance, current_state)}
        self._plugins: Dict[str, (PluginBase, PluginState)] = {}
        # 状态转换历史（用于恢复和调试）
        self._history: List[tuple] = []
        # 注册的生命周期钩子列表
        self._hooks: List[LifecycleHook] = []
        logger.info(f"PluginLifecycleManager initialized. Plugin directory = {self.plugin_dir}")

    def register_hook(self, hook: LifecycleHook) -> None:
        """注册生命周期钩子（可插拔）"""
        self._hooks.append(hook)
        logger.debug(f"Hook registered: {hook.__class__.__name__}")

    def unregister_hook(self, hook: LifecycleHook) -> None:
        """移除钩子"""
        self._hooks.remove(hook)

    def _notify_hooks(self, plugin_id: str, old_state: PluginState, new_state: PluginState) -> None:
        """通知所有钩子状态变化"""
        for hook in self._hooks:
            try:
                hook.on_state_change(plugin_id, old_state, new_state)
            except Exception as e:
                logger.exception(f"Hook {hook.__class__.__name__} failed to handle state change: {e}")

    def _set_state(self, plugin_id: str, new_state: PluginState) -> None:
        """内部状态设置，记录历史并通知钩子"""
        instance, current = self._plugins.get(plugin_id, (None, None))
        if current == new_state:
            return
        old_state = current if current else PluginState.UNLOADED
        if instance:
            self._plugins[plugin_id] = (instance, new_state)
        else:
            # 如果插件尚未存在，只记录状态（例如首次加载）
            self._plugins[plugin_id] = (None, new_state)
        self._history.append((plugin_id, old_state, new_state))
        logger.info(f"Plugin '{plugin_id}' state transition: {old_state.name} -> {new_state.name}")
        self._notify_hooks(plugin_id, old_state, new_state)

    def load_plugin(self, plugin_id: str, module_path: str, class_name: str) -> bool:
        """
        动态加载一个插件并初始化。
        :param plugin_id: 唯一的插件标识符
        :param module_path: Python模块路径（如 'myplugins.example'）
        :param class_name: 插件类名
        :return: 成功返回 True，否则 False
        """
        if plugin_id in self._plugins:
            logger.warning(f"Plugin '{plugin_id}' already loaded. Unload first.")
            return False
        try:
            module = importlib.import_module(module_path)
            plugin_cls = getattr(module, class_name)
            if not issubclass(plugin_cls, PluginBase):
                raise TypeError(f"{class_name} must implement PluginBase")
            instance = plugin_cls()
            self._plugins[plugin_id] = (instance, PluginState.LOADED)
            self._set_state(plugin_id, PluginState.LOADED)
            logger.info(f"Plugin '{plugin_id}' loaded successfully.")
            return True
        except Exception as e:
            logger.exception(f"Failed to load plugin '{plugin_id}': {e}")
            self._set_state(plugin_id, PluginState.ERROR)
            return False

    def initialize_plugin(self, plugin_id: str) -> bool:
        """初始化已加载的插件"""
        instance, state = self._get_plugin(plugin_id)
        if state != PluginState.LOADED:
            logger.error(f"Cannot initialize plugin '{plugin_id}' in state {state.name}.")
            return False
        try:
            success = instance.initialize()
            if success:
                self._set_state(plugin_id, PluginState.INITIALIZED)
            else:
                self._set_state(plugin_id, PluginState.ERROR)
            return success
        except Exception as e:
            logger.exception(f"Error initializing plugin '{plugin_id}': {e}")
            self._set_state(plugin_id, PluginState.ERROR)
            return False

    def run_plugin(self, plugin_id: str) -> bool:
        """运行插件（进入RUNNING状态）"""
        instance, state = self._get_plugin(plugin_id)
        if state != PluginState.INITIALIZED:
            logger.error(f"Cannot run plugin '{plugin_id}' in state {state.name}.")
            return False
        try:
            # 注意：run() 可能是一个阻塞调用，实际使用时应在独立线程中执行
            # 这里仅模拟状态转换和调用
            instance.run()
            self._set_state(plugin_id, PluginState.RUNNING)
            return True
        except Exception as e:
            logger.exception(f"Error running plugin '{plugin_id}': {e}")
            self._set_state(plugin_id, PluginState.ERROR)
            return False

    def pause_plugin(self, plugin_id: str) -> bool:
        """暂停插件"""
        instance, state = self._get_plugin(plugin_id)
        if state != PluginState.RUNNING:
            logger.error(f"Cannot pause plugin '{plugin_id}' in state {state.name}.")
            return False
        try:
            instance.pause()
            self._set_state(plugin_id, PluginState.PAUSED)
            return True
        except Exception as e:
            logger.exception(f"Error pausing plugin '{plugin_id}': {e}")
            self._set_state(plugin_id, PluginState.ERROR)
            return False

    def resume_plugin(self, plugin_id: str) -> bool:
        """恢复暂停的插件"""
        instance, state = self._get_plugin(plugin_id)
        if state != PluginState.PAUSED:
            logger.error(f"Cannot resume plugin '{plugin_id}' in state {state.name}.")
            return False
        try:
            instance.resume()
            self._set_state(plugin_id, PluginState.RUNNING)
            return True
        except Exception as e:
            logger.exception(f"Error resuming plugin '{plugin_id}': {e}")
            self._set_state(plugin_id, PluginState.ERROR)
            return False

    def stop_plugin(self, plugin_id: str) -> bool:
        """停止插件（正常关闭）"""
        instance, state = self._get_plugin(plugin_id)
        if state not in (PluginState.RUNNING, PluginState.PAUSED, PluginState.INITIALIZED):
            logger.error(f"Cannot stop plugin '{plugin_id}' in state {state.name}.")
            return False
        try:
            instance.shutdown()
            self._set_state(plugin_id, PluginState.STOPPED)
            return True
        except Exception as e:
            logger.exception(f"Error stopping plugin '{plugin_id}': {e}")
            self._set_state(plugin_id, PluginState.ERROR)
            return False

    def unload_plugin(self, plugin_id: str) -> bool:
        """卸载插件，释放所有资源"""
        instance, state = self._get_plugin(plugin_id)
        if state in (PluginState.UNLOADED, PluginState.ERROR):
            # 尝试从记录中移除
            if plugin_id in self._plugins:
                del self._plugins[plugin_id]
                logger.info(f"Plugin '{plugin_id}' removed from registry (unloaded/error).")
            else:
                logger.warning(f"Plugin '{plugin_id}' not found.")
            return True
        # 如果是运行态，先尝试停止
        if state in (PluginState.RUNNING, PluginState.PAUSED, PluginState.INITIALIZED):
            logger.info(f"Auto-stopping plugin '{plugin_id}' before unload...")
            self.stop_plugin(plugin_id)
        # 最终移除
        if plugin_id in self._plugins:
            del self._plugins[plugin_id]
            self._set_state(plugin_id, PluginState.UNLOADED)
            logger.info(f"Plugin '{plugin_id}' unloaded and removed.")
        return True

    def get_plugin_state(self, plugin_id: str) -> Optional[PluginState]:
        """获取插件当前状态"""
        _, state = self._get_plugin(plugin_id)
        return state

    def list_plugins(self) -> Dict[str, PluginState]:
        """列出所有已注册插件及其状态"""
        return {pid: state for pid, (_, state) in self._plugins.items()}

    def _get_plugin(self, plugin_id: str):
        """内部获取插件实例和状态，若不存在则返回(None, UNLOADED)"""
        entry = self._plugins.get(plugin_id)
        if entry is None:
            return (None, PluginState.UNLOADED)
        return entry

    def recover(self) -> List[str]:
        """
        尝试从历史中恢复所有因异常导致错误状态的插件。
        返回成功恢复的插件ID列表。
        可扩展: 支持热更新恢复策略。
        """
        recovered = []
        for plugin_id, (instance, state) in self._plugins.items():
            if state == PluginState.ERROR:
                logger.info(f"Attempting recovery of plugin '{plugin_id}'...")
                # 简化恢复：重新初始化
                try:
                    if instance and hasattr(instance, 'initialize'):
                        instance.initialize()
                        self._set_state(plugin_id, PluginState.INITIALIZED)
                        recovered.append(plugin_id)
                except Exception as