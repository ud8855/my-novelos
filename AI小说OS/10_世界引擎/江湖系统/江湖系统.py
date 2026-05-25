# 10_世界引擎/江湖系统/江湖系统.py
# 江湖系统骨架代码
# 功能: 提供江湖世界核心服务，可插拔、日志、配置化。

import logging
import importlib
import json
from pathlib import Path
from typing import Dict, Any, Optional, List

# 日志设置 (可通过配置动态调整)
logger = logging.getLogger(__name__)

# 默认配置 (可被外部配置覆盖)
DEFAULT_CONFIG = {
    "enable_plugins": True,
    "plugin_dirs": ["plugins"],
    "log_level": "INFO",
    "world_data_path": "data/world_data.json"
}


class JianghuSystem:
    """
    江湖系统核心类
    负责管理江湖世界的状态、插件和基础服务
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化江湖系统
        :param config: 外部配置，会与默认配置合并
        """
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        self._setup_logging()
        self.plugins: Dict[str, Any] = {}  # 插件注册表
        self.world_data: Dict[str, Any] = {}  # 世界数据
        self._initialize()

    def _setup_logging(self):
        """根据配置设置日志级别"""
        level = self.config.get("log_level", "INFO").upper()
        logging.basicConfig(level=getattr(logging, level, logging.INFO))
        logger.info(f"江湖系统日志级别设置为: {level}")

    def _initialize(self):
        """系统初始化流程"""
        logger.info("江湖系统初始化...")
        self._load_world_data()
        if self.config.get("enable_plugins", False):
            self._load_plugins()
        logger.info("江湖系统初始化完成")

    def _load_world_data(self):
        """加载世界基础数据（如地图、势力等）"""
        data_path = Path(self.config.get("world_data_path", "data/world_data.json"))
        try:
            if data_path.exists():
                with open(data_path, 'r', encoding='utf-8') as f:
                    self.world_data = json.load(f)
                logger.info(f"世界数据已从 {data_path} 加载")
            else:
                logger.warning(f"世界数据文件不存在: {data_path}, 使用空数据")
                self.world_data = {}
        except Exception as e:
            logger.error(f"加载世界数据失败: {e}")
            self.world_data = {}

    def _load_plugins(self):
        """动态加载插件目录下的插件模块"""
        plugin_dirs = self.config.get("plugin_dirs", ["plugins"])
        for dir_name in plugin_dirs:
            plugin_dir = Path(__file__).parent / dir_name
            if not plugin_dir.exists():
                logger.warning(f"插件目录不存在: {plugin_dir}")
                continue
            # 扫描目录下所有.py文件
            for plugin_file in plugin_dir.glob("*.py"):
                if plugin_file.stem == "__init__":
                    continue
                self._load_single_plugin(plugin_file)

    def _load_single_plugin(self, plugin_path: Path):
        """加载单个插件文件"""
        plugin_name = plugin_path.stem
        try:
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # 插件必须有 register_plugin 函数
            if hasattr(module, "register_plugin"):
                instance = module.register_plugin(self)  # 传入系统实例
                self.plugins[plugin_name] = instance
                logger.info(f"插件 {plugin_name} 加载成功")
            else:
                logger.warning(f"插件 {plugin_name} 缺少 register_plugin 函数，跳过")
        except Exception as e:
            logger.error(f"加载插件 {plugin_name} 失败: {e}")

    def register_plugin(self, name: str, plugin_instance: Any):
        """手动注册插件"""
        if name in self.plugins:
            logger.warning(f"插件 {name} 已存在，将被覆盖")
        self.plugins[name] = plugin_instance
        logger.info(f"插件 {name} 已注册")

    def unregister_plugin(self, name: str):
        """移除插件"""
        if name in self.plugins:
            del self.plugins[name]
            logger.info(f"插件 {name} 已卸载")
        else:
            logger.warning(f"要卸载的插件 {name} 不存在")

    def get_plugin(self, name: str) -> Optional[Any]:
        """获取指定插件"""
        return self.plugins.get(name)

    def run_world_tick(self):
        """执行江湖世界的周期更新（待后续实现）"""
        logger.debug("世界心跳更新...")
        for name, plugin in self.plugins.items():
            try:
                if hasattr(plugin, "on_tick"):
                    plugin.on_tick(self)
            except Exception as e:
                logger.error(f"插件 {name} on_tick 异常: {e}")

    def get_world_info(self) -> Dict[str, Any]:
        """获取世界状态摘要"""
        return {
            "world_data": self.world_data,
            "plugins_loaded": list(self.plugins.keys()),
            "config": self.config
        }


# 自测代码
if __name__ == "__main__":
    # 简单自测
    test_config = {
        "enable_plugins": False,  # 自测不加载插件
        "log_level": "DEBUG"
    }
    jianghu = JianghuSystem(config=test_config)
    world_info = jianghu.get_world_info()
    print("世界信息:", world_info)
    # 模拟世界更新
    jianghu.run_world_tick()
    print("自测通过")