"""
NovelOS - 插件系统：插件加载模块
职责：负责动态发现、加载、初始化、卸载插件。支持热插拔、配置化、日志记录。
依赖：无核心模块依赖，仅标准库。
被调用：由 28_插件系统/插件管理器 调用，提供服务。
"""

import abc
import importlib
import importlib.util
import logging
import os
import sys
import traceback
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Dict, List, Optional, Type

# ---------- 日志配置 ----------
logger = logging.getLogger("NovelOS.PluginLoader")

# ---------- 自定义异常 ----------
class PluginLoadError(Exception):
    """插件加载异常基类"""
    pass

class PluginNotFoundError(PluginLoadError):
    """指定插件未找到"""
    pass

class PluginInitError(PluginLoadError):
    """插件初始化失败"""
    pass

# ---------- 插件接口定义 ----------
class PluginBase(abc.ABC):
    """
    所有插件必须实现的抽象基类。
    提供生命周期方法：初始化、启动、停止、卸载。
    插件作者需继承此类并实现所有抽象方法。
    """

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._is_running = False

    @abc.abstractmethod
    def initialize(self) -> bool:
        """
        插件初始化，读取配置、预加载资源等。
        返回 True 表示成功，False 表示失败。
        """
        ...

    @abc.abstractmethod
    def start(self) -> bool:
        """启动插件核心逻辑，返回是否成功。"""
        ...

    @abc.abstractmethod
    def stop(self) -> bool:
        """停止插件，保存状态，释放资源。"""
        ...

    @abc.abstractmethod
    def unload(self) -> bool:
        """彻底卸载插件，清理所有痕迹。"""
        ...

    @property
    def is_running(self) -> bool:
        return self._is_running

    def __repr__(self):
        return f"<{self.__class__.__name__} running={self._is_running}>"

# ---------- 插件描述符 ----------
class PluginDescriptor:
    """
    描述一个已发现的插件，包含名称、版本、作者、入口类等元数据。
    """
    __slots__ = (
        "name", "version", "author", "description",
        "entry_class", "module_path", "config_path",
        "enabled", "priority", "dependencies"
    )

    def __init__(self,
                 name: str,
                 version: str = "0.1.0",
                 author: str = "unknown",
                 description: str = "",
                 entry_class: str = "",
                 module_path: str = "",
                 config_path: str = "",
                 enabled: bool = True,
                 priority: int = 100,
                 dependencies: List[str] = None):
        self.name = name
        self.version = version
        self.author = author
        self.description = description
        self.entry_class = entry_class
        self.module_path = module_path
        self.config_path = config_path
        self.enabled = enabled
        self.priority = priority
        self.dependencies = dependencies or []

    def __repr__(self):
        return f"PluginDescriptor({self.name}, enabled={self.enabled})"

# ---------- 抽象插件加载器 ----------
class AbstractPluginLoader(abc.ABC):
    """插件加载器的抽象基类，定义扫描、加载、卸载接口，实现可插拔。"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._plugins: Dict[str, PluginBase] = {}

    @abc.abstractmethod
    def scan_plugins(self, plugin_dir: str) -> List[PluginDescriptor]:
        """
        扫描指定目录，发现所有可用插件，返回描述符列表。
        """
        ...

    @abc.abstractmethod
    def load_plugin(self, descriptor: PluginDescriptor) -> Optional[PluginBase]:
        """
        根据描述符动态加载并实例化插件，返回插件实例。
        如果加载或初始化失败，应抛出 PluginLoadError 或返回 None 并记录日志。
        """
        ...

    @abc.abstractmethod
    def unload_plugin(self, plugin_name: str) -> bool:
        """卸载指定名称的插件，调用其 unload 方法并移除引用。"""
        ...

    def get_plugin(self, plugin_name: str) -> Optional[PluginBase]:
        """获取已加载的插件实例。"""
        return self._plugins.get(plugin_name)

    def list_loaded_plugins(self) -> Dict[str, PluginBase]:
        """返回所有已加载的插件字典（拷贝）。"""
        return self._plugins.copy()

# ---------- 默认插件加载器实现 ----------
class DefaultPluginLoader(AbstractPluginLoader):
    """
    默认的插件加载器，基于文件系统扫描和 importlib 动态导入。
    约定：每个插件是一个 Python 包，包内必须有一个 plugin.json 配置文件和
    一个标记为入口的类（继承 PluginBase）。
    """

    def __init__(self, config: dict = None):
        super().__init__(config)
        # 可配置项
        self.metadata_file = config.get("metadata_file", "plugin.json") if config else "plugin.json"
        self.plugin_base_dir = config.get("plugin_base_dir", "./plugins") if config else "./plugins"

    def scan_plugins(self, plugin_dir: str = None) -> List[PluginDescriptor]:
        """
        扫描插件目录，读取每个子目录下的 plugin.json 并创建 PluginDescriptor。
        """
        search_dir = plugin_dir or self.plugin_base_dir
        descriptors = []
        try:
            path = Path(search_dir)
            if not path.exists():
                logger.warning(f"Plugin directory not found: {path}")
                return descriptors
            for item in path.iterdir():
                if item.is_dir() and not item.name.startswith("_"):
                    meta_file = item / self.metadata_file
                    if meta_file.exists():
                        try:
                            import json
                            with open(meta_file, 'r', encoding='utf-8') as f:
                                meta = json.load(f)
                            # 生成绝对路径
                            module_path = str(item.resolve())
                            config_path = str(item / "config.json") if (item / "config.json").exists() else ""
                            desc = PluginDescriptor(
                                name=meta.get("name", item.name),
                                version=meta.get("version", "0.1.0"),
                                author=meta.get("author", ""),
                                description=meta.get("description", ""),
                                entry_class=meta.get("entry_class", ""),
                                module_path=module_path,
                                config_path=config_path,
                                enabled=meta.get("enabled", True),
                                priority=meta.get("priority", 100),
                                dependencies=meta.get("dependencies", [])
                            )
                            descriptors.append(desc)
                            logger.debug(f"Found plugin descriptor: {desc}")
                        except Exception as e:
                            logger.error(f"Failed to parse plugin metadata {meta_file}: {e}")
                    else:
                        logger.debug(f"No {self.metadata_file} in {item}, skipping")
        except Exception as e:
            logger.error(f"Error scanning plugin directory {search_dir}: {e}")
        # 按优先级排序
        descriptors.sort(key=lambda x: x.priority)
        return descriptors

    def load_plugin(self, descriptor: PluginDescriptor) -> Optional[PluginBase]:
        """
        动态加载一个插件模块，实例化入口类，并调用 initialize()。
        """
        plugin_name = descriptor.name
        logger.info(f"Loading plugin: {plugin_name} from {descriptor.module_path}")

        # 1. 检查是否已加载
        if plugin_name in self._plugins:
            logger.warning(f"Plugin {plugin_name} is already loaded, skipping")
            return self._plugins[plugin_name]

        # 2. 如果未启用，则跳过
        if not descriptor.enabled:
            logger.info(f"Plugin {plugin_name} is disabled, skip loading")
            return None

        # 3. 确保模块路径在 sys.path 中以便导入
        module_parent = str(Path(descriptor.module_path).parent)
        if module_parent not in sys.path:
            sys.path.insert(0, module_parent)

        # 4. 动态导入模块
        try:
            module_name = Path(descriptor.module_path).name  # 包名即目录名
            spec = importlib.util.find_spec(module_name)
            if spec is None:
                # 尝试从文件位置加载
                init_file = os.path.join(descriptor.module_path, "__init__.py")
                if os.path.isfile(init_file):
                    spec = importlib.util.spec_from_file_location(
                        module_name, init_file,
                        submodule_search_locations=[descriptor.module_path]
                    )
                else:
                    raise PluginLoadError(f"No __init__.py found in {descriptor.module_path}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as e:
            logger.error(f"Failed to import module for plugin {plugin_name}: {e}")
            raise PluginLoadError(f"Failed to import module for plugin {plugin_name}: {e}") from e

        # 5. 查找入口类
        entry_class_name = descriptor.entry_class
        entry_class = getattr(module, entry_class_name, None)
        if entry_class is None:
            logger.error(f"Entry class '{entry_class_name}' not found in plugin {plugin_name}")
            # 卸载已导入的模块？通常保留，但不加载
            return None
        if not issubclass(entry_class, PluginBase):
            logger.error(f"Entry class '{entry_class_name}' does not inherit PluginBase")
            return None

        # 6. 加载插件配置
        plugin_config = {}
        if descriptor.config_path and os.path.exists(descriptor.config_path):
            try:
                import json
                with open(descriptor.config_path, 'r', encoding='utf-8') as f:
                    plugin_config = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load plugin config {descriptor.config_path}: {e}")

        # 7. 实例化并初始化
        try:
            instance = entry_class(config=plugin_config)
            if not instance.initialize():
                logger.error(f"Plugin {plugin_name} initialization returned False")
                return None
            self._plugins[plugin_name] = instance
            logger.info(f"Plugin {plugin_name} loaded and initialized successfully")
            return instance
        except Exception as e:
            logger.error(f"Failed to instantiate or initialize plugin {plugin_name}: {e}")
            raise PluginInitError(f"Failed to instantiate or initialize plugin {plugin_name}: {e}") from e

    def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载插件：调用 unload() 并从内部字典中移除。
        """
        plugin = self._plugins.get(plugin_name)
        if plugin is None:
            logger.warning(f"Attempt to unload non-loaded plugin: {plugin_name}")
            return False
        try:
            logger.info(f"Unloading plugin: {plugin_name}")
            if hasattr(plugin, 'stop') and plugin.is_running:
                plugin.stop()
            plugin.unload()
            del self._plugins[plugin_name]
            logger.info(f"Plugin {plugin_name} unloaded successfully")
            return True
        except Exception as e:
            logger.error(f"Error while unloading plugin {plugin_name}: {e}")
            # 即便出错也从字典移除，避免死锁
            del self._plugins[plugin_name]
            return False

# ---------- 自测 ----------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建一个临时测试插件结构
    test_dir = Path("./temp_test_plugins/test_plugin")
    test_dir.mkdir(parents=True, exist_ok=True)
    with open(test_dir / "__init__.py", "w", encoding="utf-8") as f:
        f.write("""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from plugin_loader import PluginBase

class TestPlugin(PluginBase):
    def initialize(self):