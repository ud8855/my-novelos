"""第三方扩展系统
所属层：28_插件系统 (Plugin System)
依赖：日志系统、配置管理
被调用者：主程序、插件热插拔管理
解决问题：提供标准化的第三方插件加载、卸载、热更新能力，所有插件必须实现PluginBase接口
"""
import importlib
import importlib.util
import sys
import os
import logging
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

# 配置日志
logger = logging.getLogger("ThirdPartyExtension")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

# ----------------------------------------------------------------
# 插件接口定义
# ----------------------------------------------------------------
class PluginBase(ABC):
    """所有第三方扩展必须继承的抽象基类，定义了插件生命周期和核心方法"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = self.__class__.__name__
    
    @abstractmethod
    def initialize(self) -> bool:
        """插件初始化，返回True表示成功"""
        pass
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """插件核心执行逻辑"""
        pass
    
    @abstractmethod
    def shutdown(self) -> bool:
        """插件清理与关闭，返回True表示成功"""
        pass
    
    def get_metadata(self) -> Dict[str, Any]:
        """返回插件元数据"""
        return {
            "name": self.name,
            "version": "1.0.0",
            "author": "unknown",
            "description": "A third-party extension plugin"
        }

# ----------------------------------------------------------------
# 第三方扩展管理器
# ----------------------------------------------------------------
class ExtensionManager:
    """管理第三方插件的加载、卸载、热更新与监控"""
    
    def __init__(self, plugin_dirs: List[str] = None, config: Dict[str, Any] = None):
        """
        初始化扩展管理器
        :param plugin_dirs: 存放第三方插件的目录列表
        :param config: 全局配置，可能包含插件特定设置
        """
        self.plugin_dirs = plugin_dirs or [str(Path(__file__).parent / "plugins")]
        self.config = config or {}
        self.loaded_plugins: Dict[str, PluginBase] = {}  # 存储已加载插件实例
        self.failed_plugins: Dict[str, str] = {}  # 记录加载失败原因
        
        # 确保插件目录存在
        for d in self.plugin_dirs:
            os.makedirs(d, exist_ok=True)
        logger.info(f"ExtensionManager initialized with dirs: {self.plugin_dirs}")
    
    def load_plugin(self, plugin_name: str) -> bool:
        """
        动态加载指定插件模块并实例化
        :param plugin_name: 插件文件名(不含.py)或模块名
        :return: 加载成功返回True
        """
        if plugin_name in self.loaded_plugins:
            logger.warning(f"Plugin {plugin_name} already loaded, skipping")
            return True
        
        # 尝试从插件目录中查找并加载
        module_found = False
        for plugin_dir in self.plugin_dirs:
            plugin_path = Path(plugin_dir) / f"{plugin_name}.py"
            if plugin_path.exists():
                try:
                    spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[plugin_name] = module
                    spec.loader.exec_module(module)
                    
                    # 查找实现了PluginBase的类
                    plugin_cls = None
                    for attr_name in dir(module):
                        obj = getattr(module, attr_name)
                        if (isinstance(obj, type) and 
                            issubclass(obj, PluginBase) and 
                            obj is not PluginBase):
                            plugin_cls = obj
                            break
                    
                    if plugin_cls is None:
                        raise Exception("No PluginBase subclass found in module")
                    
                    # 实例化并初始化
                    plugin_instance = plugin_cls(self.config.get(plugin_name, {}))
                    if not plugin_instance.initialize():
                        raise Exception("Plugin initialization failed")
                    
                    self.loaded_plugins[plugin_name] = plugin_instance
                    logger.info(f"Plugin {plugin_name} loaded successfully from {plugin_path}")
                    module_found = True
                    break
                except Exception as e:
                    logger.error(f"Failed to load plugin {plugin_name}: {e}\n{traceback.format_exc()}")
                    self.failed_plugins[plugin_name] = str(e)
                    if plugin_name in sys.modules:
                        del sys.modules[plugin_name]
                    return False
        
        if not module_found:
            logger.error(f"Plugin {plugin_name} not found in any directory")
            self.failed_plugins[plugin_name] = "Module not found"
            return False
        
        return True
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """
        卸载已加载的插件，并调用其shutdown方法
        :param plugin_name: 插件名称
        :return: 卸载成功返回True
        """
        if plugin_name not in self.loaded_plugins:
            logger.warning(f"Plugin {plugin_name} is not loaded")
            return False
        
        plugin = self.loaded_plugins[plugin_name]
        try:
            if not plugin.shutdown():
                logger.warning(f"Plugin {plugin_name} shutdown reported failure")
        except Exception as e:
            logger.error(f"Error during plugin {plugin_name} shutdown: {e}")
        
        # 移除模块引用
        if plugin_name in sys.modules:
            del sys.modules[plugin_name]
        del self.loaded_plugins[plugin_name]
        logger.info(f"Plugin {plugin_name} unloaded successfully")
        return True
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """
        重新加载插件(先卸载再加载)
        :param plugin_name: 插件名称
        :return: 重加载成功返回True
        """
        logger.info(f"Reloading plugin {plugin_name}...")
        if plugin_name in self.loaded_plugins:
            self.unload_plugin(plugin_name)
        # 清除失败记录
        self.failed_plugins.pop(plugin_name, None)
        return self.load_plugin(plugin_name)
    
    def load_all_from_config(self, config_key: str = "enabled_plugins") -> Dict[str, bool]:
        """
        从配置中加载所有启用的插件
        :param config_key: 配置文件中定义启用插件列表的键
        :return: 插件加载状态字典 {plugin_name: success}
        """
        enabled_plugins = self.config.get(config_key, [])
        if not enabled_plugins:
            logger.info("No enabled plugins found in configuration")
            # 可尝试自动发现目录下所有.py文件
            enabled_plugins = self._discover_plugins()
        
        results = {}
        for plugin_name in enabled_plugins:
            results[plugin_name] = self.load_plugin(plugin_name)
        return results
    
    def _discover_plugins(self) -> List[str]:
        """扫描插件目录，发现所有.py文件作为候选插件"""
        candidates = []
        for plugin_dir in self.plugin_dirs:
            if not os.path.isdir(plugin_dir):
                continue
            for file in os.listdir(plugin_dir):
                if file.endswith('.py') and not file.startswith('_'):
                    candidates.append(file[:-3])  # 去掉.py
        return candidates
    
    def execute_plugin(self, plugin_name: str, *args, **kwargs) -> Optional[Any]:
        """
        执行指定插件
        :param plugin_name: 插件名称
        :param args, kwargs: 传递给execute的参数
        :return: 插件返回值，失败则返回None
        """
        if plugin_name not in self.loaded_plugins:
            logger.error(f"Cannot execute unloaded plugin: {plugin_name}")
            return None
        
        plugin = self.loaded_plugins[plugin_name]
        try:
            result = plugin.execute(*args, **kwargs)
            logger.debug(f"Plugin {plugin_name} executed successfully")
            return result
        except Exception as e:
            logger.error(f"Plugin {plugin_name} execution failed: {e}\n{traceback.format_exc()}")
            self.failed_plugins[plugin_name] = f"Execution error: {e}"
            return None
    
    def get_status(self) -> Dict[str, Any]:
        """获取扩展系统的状态信息"""
        return {
            "loaded_plugins": list(self.loaded_plugins.keys()),
            "failed_plugins": self.failed_plugins.copy(),
            "plugin_dirs": self.plugin_dirs
        }

# ----------------------------------------------------------------
# 自测代码
# ----------------------------------------------------------------
if __name__ == "__main__":
    # 简单的自测：创建一个测试插件目录，并写一个假插件
    test_dir = Path(__file__).parent / "test_plugins"
    test_dir.mkdir(exist_ok=True)
    test_plugin_code = """
import logging
from third_party_extension import PluginBase

class TestEchoPlugin(PluginBase):
    def initialize(self):
        logging.info("TestEchoPlugin initialized")
        return True
    
    def execute(self, text):
        return f"Echo: {text}"
    
    def shutdown(self):
        logging.info("TestEchoPlugin shutdown")
        return True
"""
    # 写入测试文件
    (test_dir / "echo_plugin.py").write_text(test_plugin_code, encoding="utf-8")
    
    # 配置管理器使用测试目录
    config = {
        "enabled_plugins": ["echo_plugin"],
        "echo_plugin": {}  # 插件配置
    }
    manager = ExtensionManager(plugin_dirs=[str(test_dir)], config=config)
    print("=== Loading plugins ===")
    manager.load_all_from_config()
    print("Status:", manager.get_status())
    
    # 执行测试插件
    result = manager.execute_plugin("echo_plugin", "Hello NovelOS!")
    print("Plugin output:", result)
    
    # 清理：卸载插件
    manager.unload_plugin("echo_plugin")
    print("After unload:", manager.get_status())
    
    # 清理测试文件
    import shutil
    shutil.rmtree(test_dir)