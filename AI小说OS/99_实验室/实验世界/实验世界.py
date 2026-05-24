"""
实验世界骨架代码
层级：99_实验室/实验世界
依赖：20_模型协同, 21_API模型（通过接口注入），配置系统，日志系统
被调用：由实验室调度器（未来99_实验室）调用
功能：提供可插拔的实验世界环境，支持配置化实验流程，热加载实验逻辑，记录详细日志
"""

import logging
import importlib
import inspect
from typing import Dict, Any, Optional, Callable

# 配置和日志的基础结构
class ExperimentalWorldConfig:
    """实验世界配置类，支持从外部YAML/JSON加载（骨架阶段使用字典模拟）"""
    def __init__(self, config_dict: Dict[str, Any] = None):
        self.config = config_dict or {}
        
    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

class ExperimentalWorldLogger:
    """实验世界专用日志记录器，具备日志模板化和异常恢复"""
    def __init__(self, name: str = "ExperimentalWorld"):
        self.logger = logging.getLogger(name)
        if not self.logger.handlers:
            # 避免重复添加handler（骨架环境可能没有配置根logging）
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)
            
    def log_event(self, event_type: str, details: Dict[str, Any]):
        """结构化事件日志"""
        self.logger.info(f"Event [{event_type}]: {details}")
        
    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        """异常恢复日志"""
        self.logger.error(f"Exception occurred: {error}, Context: {context or {}}")
        
    def get_logger(self) -> logging.Logger:
        return self.logger

class ExperimentalWorld:
    """
    实验世界主类，负责协调实验环境
    遵循可插拔设计：通过插件路径动态加载实验逻辑
    支持热更新：通过watchdog监视实验模块变化（骨架仅预留接口）
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = ExperimentalWorldConfig(config or {})
        self.logger_manager = ExperimentalWorldLogger()
        self.logger = self.logger_manager.get_logger()
        self.plugins = {}  # 已加载的实验插件 {name: module}
        self.runtime_context = {}  # 运行时上下文，用于在实验步骤间传递数据
        self.logger.info("ExperimentalWorld initialized with config: %s", self.config.config)
        
    def load_plugin(self, plugin_path: str, plugin_name: str = None) -> bool:
        """
        动态加载实验插件模块
        :param plugin_path: 模块完整路径，如'experiments.plugins.my_experiment'
        :param plugin_name: 插件别名，若不指定则使用模块名
        :return: 是否加载成功
        """
        try:
            module = importlib.import_module(plugin_path)
            name = plugin_name or module.__name__.split('.')[-1]
            if name in self.plugins:
                self.logger.warning(f"Plugin '{name}' already loaded, overwriting.")
            self.plugins[name] = module
            self.logger.log_event("plugin_loaded", {"name": name, "path": plugin_path})
            return True
        except Exception as e:
            self.logger_manager.log_error(e, {"action": "load_plugin", "path": plugin_path})
            return False
            
    def unload_plugin(self, plugin_name: str) -> bool:
        """卸载插件"""
        if plugin_name in self.plugins:
            del self.plugins[plugin_name]
            self.logger.log_event("plugin_unloaded", {"name": plugin_name})
            return True
        else:
            self.logger.warning(f"Plugin '{plugin_name}' not found")
            return False
            
    def execute_experiment_step(self, step_name: str, *args, **kwargs) -> Any:
        """
        执行一个实验步骤，由当前激活的插件提供
        预留步骤注册机制，目前从配置或插件中查找step处理函数
        """
        # 查找所有插件中是否有名为step_name的函数
        for pname, plugin in self.plugins.items():
            if hasattr(plugin, step_name) and callable(getattr(plugin, step_name)):
                func = getattr(plugin, step_name)
                self.logger.log_event("step_executing", {"plugin": pname, "step": step_name})
                try:
                    result = func(context=self.runtime_context, *args, **kwargs)
                    self.logger.log_event("step_completed", {"plugin": pname, "step": step_name, "status": "success"})
                    return result
                except Exception as e:
                    self.logger_manager.log_error(e, {"plugin": pname, "step": step_name})
                    # 异常恢复：可以记录后重新抛出或返回错误标志
                    raise
        # 如果没有找到，尝试从配置中的默认步骤处理器执行（例如调用模型协同）
        default_step_handler = self.config.get("default_step_handler")
        if default_step_handler and callable(default_step_handler):
            self.logger.log_event("step_executing", {"step": step_name, "handler": "default"})
            try:
                result = default_step_handler(context=self.runtime_context, step=step_name, *args, **kwargs)
                return result
            except Exception as e:
                self.logger_manager.log_error(e, {"step": step_name})
                raise
        else:
            self.logger.error(f"No handler found for step '{step_name}'")
            raise ValueError(f"Unknown experiment step: {step_name}")
            
    def run_experiment_sequence(self, sequence: list = None):
        """
        运行预设的实验序列，由配置文件定义或传入
        sequence 是步骤名列表，或更复杂的dict列表
        """
        if sequence is None:
            sequence = self.config.get("experiment_sequence", [])
        for step in sequence:
            if isinstance(step, str):
                self.execute_experiment_step(step)
            elif isinstance(step, dict):
                step_name = step.get("step")
                args = step.get("args", [])
                kwargs = step.get("kwargs", {})
                self.execute_experiment_step(step_name, *args, **kwargs)
            else:
                self.logger.warning(f"Invalid step format: {step}")
                
    def register_default_step_handler(self, handler: Callable):
        """设置默认步骤处理器，可用于模型协同调用等"""
        self.config.config["default_step_handler"] = handler
        self.logger.info("Default step handler registered")
        
    def hot_reload_monitor(self, watch_path: str):
        """
        热更新监视接口（预留，后续实现文件系统监视）
        当监测到插件文件变化时自动重载
        """
        self.logger.info(f"Hot-reload monitoring requested for path: {watch_path}, not yet implemented.")
        # TODO: 使用watchdog或类似库监视文件变化，触发插件重载
        pass

# 自测代码
if __name__ == "__main__":
    # 配置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG)
    
    # 模拟一个简单的实验插件（直接定义函数，不使用外部文件）
    class MockPlugin:
        def greet(self, context, name="World"):
            print(f"Hello, {name}!")
            context['greeted'] = True
            return "greet done"
            
        def farewell(self, context):
            print("Goodbye!")
            return "farewell done"
    
    # 创建实验世界实例
    test_config = {
        "experiment_sequence": [
            {"step": "greet", "kwargs": {"name": "NovelOS"}},
            "farewell"
        ]
    }
    world = ExperimentalWorld(config=test_config)
    
    # 注入模拟插件（模拟插件加载）
    # 实际load_plugin会从文件加载，这里直接赋值模块
    mock_module = type('mock_module', (), {})
    mock_module.greet = MockPlugin().greet
    mock_module.farewell = MockPlugin().farewell
    world.plugins['mock'] = mock_module
    
    # 运行序列
    print("=== Running experiment sequence ===")
    world.run_experiment_sequence()
    
    # 测试步骤执行
    print("\n=== Testing direct step execution ===")
    world.execute_experiment_step("greet", name="DirectCall")
    
    # 演示默认步骤处理器
    def default_handler(context, step, *args, **kwargs):
        print(f"[DefaultHandler] Processing step: {step} with args={args}, kwargs={kwargs}")
        return "default handler result"
    world.register_default_step_handler(default_handler)
    
    # 执行未注册步骤
    try:
        world.execute_experiment_step("unknown_step", extra_data=123)
    except ValueError as e:
        print(f"Expected error: {e}")
        
    # 测试热加载提示
    world.hot_reload_monitor("./plugins")
    
    print("\nExperimentalWorld自测完成。")