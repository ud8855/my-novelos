"""
插件注册模块
负责插件的发现、注册、加载、卸载等。
所有插件必须实现PluginBase接口。
"""
import logging
import importlib
import sys
from typing import Dict, Type, Optional

# 配置模块级日志
logger = logging.getLogger(__name__)

# ============= 插件基类（协议） =============
class PluginBase:
    """所有插件的基类，定义插件生命周期接口"""
    def on_load(self):
        """插件加载时调用"""
        pass

    def on_unload(self):
        """插件卸载时调用"""
        pass

    def get_info(self) -> dict:
        """返回插件信息"""
        return {
            "name": self.__class__.__name__,
            "version": "1.0.0",
            "author": "unknown"
        }

# ============= 插件注册管理器 =============
class PluginRegistry:
    """插件注册器，管理插件实例和类"""

    def __init__(self, config: dict = None):
        """
        初始化注册器
        :param config: 配置字典，可包含 'plugin_paths' (list), 'plugins'(list[dict]) 等
        """
        self._plugins: Dict[str, PluginBase] = {}           # 已加载的插件实例，key 为插件名
        self._plugin_classes: Dict[str, Type[PluginBase]] = {}  # 注册的插件类
        self._config = config or {}
        self._logger = logger.getChild("PluginRegistry")

    def register_plugin_class(self, name: str, plugin_cls: Type[PluginBase]) -> None:
        """
        注册一个插件类（不立即实例化）
        :param name: 插件名称
        :param plugin_cls: 插件类，必须继承 PluginBase
        """
        if name in self._plugin_classes:
            self._logger.warning(f"插件类 {name} 已存在，将被覆盖")
        if not issubclass(plugin_cls, PluginBase):
            raise TypeError(f"{plugin_cls} 必须继承 PluginBase")
        self._plugin_classes[name] = plugin_cls
        self._logger.info(f"插件类 {name} 已注册")

    def load_plugin(self, name: str) -> Optional[PluginBase]:
        """
        根据已注册的插件类实例化并加载插件
        :param name: 插件名称
        :return: 插件实例，失败返回 None
        """
        cls = self._plugin_classes.get(name)
        if not cls:
            self._logger.error(f"插件类 {name} 未注册")
            return None
        if name in self._plugins:
            self._logger.warning(f"插件 {name} 已加载，返回现有实例")
            return self._plugins[name]
        try:
            plugin_instance = cls()
            plugin_instance.on_load()
            self._plugins[name] = plugin_instance
            self._logger.info(f"插件 {name} 加载成功")
            return plugin_instance
        except Exception as e:
            self._logger.exception(f"加载插件 {name} 失败")
            return None

    def unload_plugin(self, name: str) -> None:
        """
        卸载插件，调用 on_unload 并从实例表中移除
        :param name: 插件名称
        """
        plugin = self._plugins.pop(name, None)
        if plugin:
            try:
                plugin.on_unload()
                self._logger.info(f"插件 {name} 已卸载")
            except Exception as e:
                self._logger.exception(f"卸载插件 {name} 时发生错误")
        else:
            self._logger.warning(f"插件 {name} 未加载，无法卸载")

    def get_plugin(self, name: str) -> Optional[PluginBase]:
        """获取已加载的插件实例"""
        return self._plugins.get(name)

    def list_plugins(self) -> list:
        """返回已加载的插件名列表"""
        return list(self._plugins.keys())

    def discover_plugins(self, package_paths: list = None) -> None:
        """
        从指定包路径自动发现插件类（自动注册）
        当前为骨架，后续完善具体发现逻辑。
        """
        # TODO: 实现基于 importlib.metadata 或遍历模块的自动发现
        pass

    def load_from_config(self) -> None:
        """
        根据配置加载插件
        配置示例: config['plugins'] = [{"name": "my_plugin", "module": "mypackage.MyPlugin"}]
        """
        plugins_conf = self._config.get('plugins', [])
        for pc in plugins_conf:
            name = pc.get('name')
            module_path = pc.get('module')
            if not name or not module_path:
                self._logger.warning(f"插件配置不完整，跳过: {pc}")
                continue
            try:
                # 动态导入模块并获取类（简单实现：假定类名与 name 一致或为模块中最后一个标识符）
                module = importlib.import_module(module_path)
                cls_name = module_path.split('.')[-1] if '.' in module_path else module_path
                cls = getattr(module, cls_name, None)
                if cls is None: