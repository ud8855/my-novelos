""" 
Runtime核心 - NovelOS运行时执行引擎

所属层级: 04_Runtime运行时  
依赖: 配置管理(07_配置), 日志(01_Utils/日志), 模块注册中心(03_模块管理器)  
被调用: 主控程序, 调度器, 测试入口  
职责:  
  - 统一管理模块的加载、初始化、运行、卸载  
  - 提供主执行循环, 支持异步任务调度  
  - 异常捕获与恢复机制  
  - 配置驱动, 可插拔的模块集成  
  - 热更新支持  
"""

import os
import sys
import time
import logging
import importlib
import traceback
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path

# 确保项目根目录在sys.path中, 支持模块热加载
PROJECT_ROOT = Path(__file__).parent.parent.parent  # 向上两级到项目根
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 尝试导入配置加载器 (假设存在通用配置模块)
try:
    from Utils.config_loader import load_config, ConfigDict
except ImportError:
    # 配置模块可能尚未实现, 提供默认简易加载器
    def load_config(path: str) -> Dict[str, Any]:
        import yaml
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    ConfigDict = dict

# 日志初始化 (可以后续移入统一日志模块)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('RuntimeCore')

class RuntimeCore:
    """Runtime核心引擎, 负责模块生命周期管理和任务调度"""
    _instance = None  # 单例模式

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        # 防止重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True

        self.config: ConfigDict = {}
        self.modules: Dict[str, Any] = {}
        self.running = False
        self.task_queue = []  # 简单任务队列
        self.hooks: Dict[str, List[Callable]] = {
            "on_start": [],
            "on_stop": [],
            "before_task": [],
            "after_task": [],
            "on_error": []
        }

        # 加载配置
        if config_path:
            self.load_config(config_path)
        else:
            self._load_default_config()

        logger.info("Runtime核心初始化完成")

    def load_config(self, config_path: str):
        """加载运行时配置"""
        try:
            self.config = load_config(config_path)
            logger.info(f"配置已加载: {config_path}")
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            self._load_default_config()

    def _load_default_config(self):
        """默认配置"""
        self.config = {
            "runtime": {
                "loop_interval": 0.1,       # 主循环间隔(秒)
                "max_retries": 3,           # 任务最大重试次数
                "enable_hot_reload": True,  # 是否支持热加载模块
                "modules_dir": "modules",   # 可插拔模块目录
                "active_modules": []        # 默认启用的模块列表
            }
        }

    def register_module(self, module_name: str, module_instance: Any):
        """注册一个运行时模块"""
        if module_name in self.modules:
            logger.warning(f"模块 {module_name} 已存在, 将被覆盖")
        self.modules[module_name] = module_instance
        logger.info(f"模块已注册: {module_name}")

    def unregister_module(self, module_name: str):
        """卸载模块"""
        if module_name in self.modules:
            # 尝试调用模块的清理方法
            module = self.modules[module_name]
            if hasattr(module, 'shutdown'):
                try:
                    module.shutdown()
                except Exception as e:
                    logger.error(f"模块 {module_name} shutdown异常: {e}")
            del self.modules[module_name]
            logger.info(f"模块已卸载: {module_name}")
        else:
            logger.warning(f"要卸载的模块不存在: {module_name}")

    def load_module_from_path(self, module_path: str, module_name: str):
        """动态加载模块并注册 (支持热更新)"""
        try:
            spec = importlib.util.spec_from_file_location(module_name, module_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # 假设模块中有 'get_instance' 工厂方法
            if hasattr(module, 'get_instance'):
                instance = module.get_instance()
            else:
                instance = module
            self.register_module(module_name, instance)
        except Exception as e:
            logger.error(f"动态加载模块失败: {module_path}, 错误: {e}")
            traceback.print_exc()

    def hot_reload_module(self, module_name: str):
        """热更新指定模块 (重新导入并替换)"""
        if module_name not in self.modules:
            logger.error(f"模块 {module_name} 未注册, 无法热更新")
            return
        # 简单实现: 先卸载再加载 (需要知道模块路径)
        # 实际需配合模块管理器维护元信息
        old_module = self.modules[module_name]
        # 获取模块原始文件路径 (需模块提供 __file__)
        # 此处简化, 假设模块属性中有 file_path
        file_path = getattr(old_module, 'file_path', None)
        if file_path and os.path.exists(file_path):
            self.unregister_module(module_name)
            self.load_module_from_path(file_path, module_name)
            logger.info(f"模块 {module_name} 热更新完成")
        else:
            logger.warning(f"无法获取模块 {module_name} 的源文件路径, 热更新失败")

    def start(self):
        """启动运行时, 初始化所有注册模块并进入主循环"""
        if self.running:
            logger.warning("Runtime已在运行")
            return

        logger.info("Runtime启动...")
        self.running = True

        # 触发启动钩子
        for hook in self.hooks.get("on_start", []):
            try:
                hook(self)
            except Exception as e:
                logger.error(f"on_start钩子执行失败: {e}")

        # 调用各模块的启动方法 (假设模块有 start() 方法)
        for name, module in self.modules.items():
            if hasattr(module, 'start'):
                try:
                    module.start()
                except Exception as e:
                    logger.error(f"模块 {name} 启动失败: {e}")

        # 主事件循环
        try:
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("接收到中断信号")
        except Exception as e:
            logger.critical(f"主循环异常退出: {e}")
            traceback.print_exc()
        finally:
            self.stop()

    def stop(self):
        """停止运行时, 依次关闭所有模块"""
        if not self.running:
            return
        logger.info("Runtime停止...")
        self.running = False

        # 触发停止钩子
        for hook in self.hooks.get("on_stop", []):
            try:
                hook(self)
            except Exception as e:
                logger.error(f"on_stop钩子执行失败: {e}")

        # 调用各模块的停止方法
        for name, module in self.modules.items():
            if hasattr(module, 'stop'):
                try:
                    module.stop()
                except Exception as e:
                    logger.error(f"模块 {name} 停止失败: {e}")

        logger.info("Runtime停止完成")

    def _main_loop(self):
        """核心执行循环, 持续处理任务队列"""
        interval = self.config.get("runtime", {}).get("loop_interval", 0.1)
        while self.running:
            # 处理队列中的任务 (这里简化, 实际应使用异步队列)
            while self.task_queue:
                task = self.task_queue.pop(0)
                self._execute_task(task)

            # 调用各模块的 update/tick 方法, 支持模块自我驱动
            for name, module in self.modules.items():
                if hasattr(module, 'update'):
                    try:
                        module.update()
                    except Exception as e:
                        logger.error(f"模块 {name} update异常: {e}")

            time.sleep(interval)

        # 循环结束后的清理
        self.task_queue.clear()

    def _execute_task(self, task: Dict[str, Any]):
        """执行单个任务, 带重试和异常恢复"""
        func = task.get("func")
        args = task.get("args", ())
        kwargs = task.get("kwargs", {})
        retries = 0
        max_retries = self.config.get("runtime", {}).get("max_retries", 3)

        # 触发 before_task 钩子
        for hook in self.hooks.get("before_task", []):
            try:
                hook(task)
            except Exception as e:
                logger.error(f"before_task钩子异常: {e}")

        while retries <= max_retries:
            try:
                if callable(func):
                    result = func(*args, **kwargs)
                else:
                    logger.error(f"任务不可调用: {func}")
                    break
                # 成功执行, 触发 after_task 钩子
                for hook in self.hooks.get("after_task", []):
                    try:
                        hook(task, result)
                    except Exception as e:
                        logger.error(f"after_task钩子异常: {e}")
                return result
            except Exception as e:
                retries += 1
                logger.warning(f"任务执行失败 (重试 {retries}/{max_retries}): {e}")
                if retries > max_retries:
                    # 触发错误钩子
                    for hook in self.hooks.get("on_error", []):
                        try:
                            hook(task, e)
                        except Exception as hook_e:
                            logger.error(f"on_error钩子异常: {hook_e}")
                    logger.error(f"任务最终失败: {func}")
                else:
                    time.sleep(0.5)  # 重试间隔

    def add_task(self, func: Callable, *args, **kwargs):
        """向任务队列添加任务"""
        task = {"func": func, "args": args, "kwargs": kwargs}
        self.task_queue.append(task)

    def register_hook(self, hook_type: str, callback: Callable):
        """注册生命周期钩子"""
        if hook_type in self.hooks:
            self.hooks[hook_type].append(callback)
        else:
            logger.warning(f"未知钩子类型: {hook_type}")

    def get_module(self, module_name: str) -> Optional[Any]:
        """获取已注册模块实例"""
        return self.modules.get(module_name)


# ------------------------------------------------
# 自测代码
# ------------------------------------------------
if __name__ == "__main__":
    print("=== Runtime核心 自检模式 ===")

    # 创建一个简单模块用于测试
    class TestModule:
        def __init__(self, name="Test"):
            self.name = name
            self.file_path = __file__  # 仅供演示

        def start(self):
            logger.info(f"{self.name} 模块启动")

        def stop(self):
            logger.info(f"{self.name} 模块停止")

        def update(self):
            # 模拟执行操作
            pass

    # 初始化Runtime
    rt = RuntimeCore()
    rt.register_module("test_module",