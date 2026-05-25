# 25_UI界面/可视化系统/可视化系统.py

"""
可视化系统骨架模块
定位：25_UI界面层，提供可视化组件的统一管理和展示接口
依赖：无外部业务模块依赖，仅依赖Python标准库
被调用：由UI主框架或其他需要可视化的模块调用
解决：实现可插拔的可视化组件管理，支持配置化加载、日志记录、热插拔
"""

import logging
import importlib
import json
import os
from typing import Dict, Any, List, Optional

# ------------------------- 默认配置 -------------------------
DEFAULT_CONFIG_PATH = "config/visualization.json"
DEFAULT_VISUALIZERS = ["ConsoleVisualizer"]  # 默认加载的可视化组件

# ------------------------- 日志配置 -------------------------
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())  # 实际日志处理器由主程序统一配置


# ============================================================
# 可视化组件基类
# ============================================================
class BaseVisualizer:
    """
    可视化组件抽象基类
    所有自定义可视化组件必须继承此类并实现 render 方法
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        :param config: 组件的个性化配置字典
        """
        self.config = config or {}
        self.name = self.__class__.__name__
        logger.debug(f"BaseVisualizer initialized: {self.name}")

    def initialize(self) -> bool:
        """
        组件初始化逻辑，子类可重写
        :return: 初始化是否成功
        """
        logger.info(f"Initializing visualizer: {self.name}")
        return True

    def render(self, data: Any) -> bool:
        """
        渲染数据，子类必须实现
        :param data: 需要渲染的数据
        :return: 渲染是否成功
        """
        raise NotImplementedError("Subclasses must implement render() method.")

    def close(self):
        """清理资源，子类可重写"""
        logger.info(f"Closing visualizer: {self.name}")

    def __repr__(self):
        return f"<{self.name} visualizer>"


# ============================================================
# 示例可视化组件：控制台输出
# ============================================================
class ConsoleVisualizer(BaseVisualizer):
    """控制台可视化组件：将数据以文本形式打印到控制台"""
    def render(self, data: Any) -> bool:
        print(f"[{self.name}] Rendering data: {data}")
        return True


# ============================================================
# 可视化系统管理器
# ============================================================
class VisualizationSystem:
    """
    可视化系统主类
    负责：加载配置 → 实例化组件 → 管理组件生命周期 → 提供统一展示入口
    """
    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH):
        """
        :param config_path: 可视化系统配置文件路径
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = self._load_config()
        self.visualizers: Dict[str, BaseVisualizer] = {}
        self._load_visualizers()
        logger.info("VisualizationSystem initialized.")

    # ------------------------- 配置加载 -------------------------
    def _load_config(self) -> Dict[str, Any]:
        """
        加载JSON配置文件，若文件不存在则返回默认配置
        :return: 配置字典
        """
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file {self.config_path} not found. Using default config.")
            return {"visualizers": DEFAULT_VISUALIZERS}
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"Loaded visualization config from {self.config_path}")
            return config
        except Exception as e:
            logger.exception(f"Failed to load config: {e}. Using defaults.")
            return {"visualizers": DEFAULT_VISUALIZERS}

    # ------------------------- 组件自动加载 -------------------------
    def _load_visualizers(self):
        """
        根据配置中的 visualizers 列表动态加载组件
        默认从当前模块中查找类，未来可扩展为从外部模块加载
        """
        viz_list: List[str] = self.config.get("visualizers", [])
        if not viz_list:
            logger.warning("No visualizers specified in config.")
            return

        current_module = importlib.import_module(__name__)  # 加载自身模块，以便查找类
        for viz_name in viz_list:
            try:
                viz_cls = getattr(current_module, viz_name, None)
                if viz_cls is None:
                    # 扩展点：尝试从其他模块动态导入
                    # viz_cls = self._import_class_from_string(viz_name)
                    logger.error(f"Visualizer class '{viz_name}' not found in module {__name__}.")
                    continue

                instance = viz_cls()
                if instance.initialize():
                    self.visualizers[viz_name] = instance
                    logger.info(f"Loaded visualizer: {viz_name}")
                else:
                    logger.error(f"Failed to initialize visualizer: {viz_name}")
            except Exception as e:
                logger.exception(f"Error loading visualizer '{viz_name}': {e}")

    # ------------------------- 动态注册/注销（热插拔） -------------------------
    def register_visualizer(self, name: str, visualizer: BaseVisualizer) -> bool:
        """
        手动注册一个可视化组件（支持热插拔）
        :param name: 组件名称
        :param visualizer: 组件实例
        :return: 是否注册成功
        """
        if name in self.visualizers:
            logger.warning(f"Visualizer '{name}' already exists. Overwriting.")
            self.unregister_visualizer(name)

        try:
            if visualizer.initialize():
                self.visualizers[name] = visualizer
                logger.info(f"Registered visualizer: {name}")
                return True
            else:
                logger.error(f"Failed to initialize visualizer: {name}")
                return False
        except Exception as e:
            logger.exception(f"Error registering visualizer '{name}': {e}")
            return False

    def unregister_visualizer(self, name: str) -> bool:
        """
        注销并关闭一个可视化组件
        :param name: 组件名称
        :return: 是否成功
        """
        if name in self.visualizers:
            try:
                self.visualizers[name].close()
            except Exception as e:
                logger.exception(f"Error closing visualizer '{name}': {e}")
            del self.visualizers[name]