""" 
模块路径：99_实验室/实验功能/实验功能.py
所属层级：实验室层（99_实验室）
依赖模块：无（本模块为接口定义，依赖标准库）
被调用者：实验室UI、测试框架、动态加载器
解决的问题：提供可插拔的实验功能管理框架，支持实验的注册、配置化、日志记录、独立执行与自测。
设计说明：所有实验功能必须继承ExperimentBase，并通过ExperimentManager进行统一调度。
"""

import logging
import importlib
import pkgutil
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable

# ---------- 全局日志与配置接口 ----------
# 实际日志和配置将通过依赖注入或配置中心获得，这里仅定义接口
_EXPERIMENT_LOGGER = logging.getLogger("NovelOS.Lab.Experiment")
_EXPERIMENT_CONFIG: Dict[str, Any] = {}
_CONFIG_LOADER: Optional[Callable[[], Dict[str, Any]]] = None


def set_experiment_config_loader(loader: Callable[[], Dict[str, Any]]):
    """设置配置加载函数，由上层注入"""
    global _CONFIG_LOADER
    _CONFIG_LOADER = loader


def get_experiment_config() -> Dict[str, Any]:
    """获取当前实验功能的配置"""
    global _EXPERIMENT_CONFIG
    if _CONFIG_LOADER:
        _EXPERIMENT_CONFIG = _CONFIG_LOADER()
    return _EXPERIMENT_CONFIG


def get_experiment_logger() -> logging.Logger:
    """获取统一日志记录器"""
    return _EXPERIMENT_LOGGER


# ---------- 实验功能基类 ----------
class ExperimentBase(ABC):
    """
    所有实验功能必须实现此类。
    实验功能是独立的业务逻辑单元，支持配置化、可观测、可插拔。
    """

    # 实验元数据，子类必须定义
    name: str = "unnamed_experiment"
    description: str = "No description provided."

    def __init__(self, config_override: Optional[Dict[str, Any]] = None):
        """
        初始化实验，加载配置
        :param config_override: 额外覆盖的配置，优先级最高
        """
        self.logger = get_experiment_logger().getChild(self.name)
        self.config = get_experiment_config().get(self.name, {})
        if config_override:
            self.config.update(config_override)
        self.logger.info(f"Experiment [{self.name}] initialized with config: {self.config}")

    @abstractmethod
    def run(self, **kwargs) -> Any:
        """
        执行实验主逻辑
        :param kwargs: 运行时动态参数
        :return: 实验结果，类型由子类定义
        """
        ...

    def validate(self) -> bool:
        """
        实验启动前自检，默认通过，子类可覆盖
        :return: 自检是否成功
        """
        self.logger.info(f"Experiment [{self.name}] default validate passed.")
        return True

    def on_start(self):
        """实验开始前的回调，可覆盖"""
        self.logger.info(f"Experiment [{self.name}] on_start")

    def on_finish(self, result: Any):
        """实验完成后的回调，可覆盖"""
        self.logger.info(f"Experiment [{self.name}] on_finish, result type: {type(result).__name__}")

    def on_error(self, exception: Exception):
        """实验异常时的回调，可覆盖"""
        self.logger.error(f"Experiment [{self.name}] on_error: {exception}", exc_info=True)

    def execute(self, **kwargs) -> Any:
        """
        完整的执行流程：on_start -> run -> on_finish，异常时调用on_error并重新抛出
        :param kwargs: 运行时动态参数
        :return: 实验结果
        """
        self.logger.info(f"Starting execution of experiment [{self.name}]")
        try:
            self.on_start()
            result = self.run(**kwargs)
            self.on_finish(result)
            return result
        except Exception as e:
            self.on_error(e)
            raise
        finally:
            self.logger.info(f"Execution of experiment [{self.name}] completed.")


# ---------- 实验管理器 ----------
class ExperimentManager:
    """
    管理所有已注册的实验功能，提供注册、查找、执行、自测等统一入口。
    单例模式，可动态加载插件。
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, auto_discover_path: Optional[str] = None):
        """
        :param auto_discover_path: 自动发现实验模块的包路径，如 "lab_experiments"
        """
        if not hasattr(self, '_initialized'):
            self._experiments: Dict[str, type] = {}
            self.logger = get_experiment_logger().getChild("Manager")
            if auto_discover_path:
                self.discover_experiments(auto_discover_path)
            self._initialized = True

    def register(self, experiment_cls: type):
        """注册一个实验类"""
        if not issubclass(experiment_cls, ExperimentBase):
            raise TypeError(f"Class {experiment_cls.__name__} is not a subclass of ExperimentBase")
        name = experiment_cls.name
        if name in self._experiments:
            self.logger.warning(f"Experiment [{name}] is already registered, overwriting.")
        self._experiments[name] = experiment_cls
        self.logger.info(f"Registered experiment: {name}")

    def unregister(self, name: str):
        """注销一个实验"""
        if name in self._experiments:
            del self._experiments[name]
            self.logger.info(f"Unregistered experiment: {name}")
        else:
            self.logger.warning(f"Experiment [{name}] not found for unregistering.")

    def get_experiment(self, name: str) -> Optional[type]:
        """获取已注册的实验类"""
        return self._experiments.get(name)

    def list_experiments(self) -> Dict[str, str]:
        """列出所有注册的实验及其描述"""
        return {name: cls.description for name, cls in self._experiments.items()}

    def run_experiment(self, name: str, config_override: Optional[Dict[str, Any]] = None, **kwargs) -> Any:
        """
        创建并执行一个实验
        :param name: 实验名称
        :param config_override: 运行时配置覆盖
        :param kwargs: 传递给 run 方法的额外参数
        :return: 实验结果
        """
        cls = self.get_experiment(name)
        if cls is None:
            raise ValueError(f"Experiment [{name}] not registered.")
        experiment = cls(config_override=config_override)
        if not experiment.validate():
            raise RuntimeError(f"Experiment [{name}] validation failed.")
        return experiment.execute(**kwargs)

    def run_all(self, **kwargs) -> Dict[str, Any]:
        """运行所有已注册的实验，返回结果字典，异常不会中断其他实验"""
        results = {}
        for name, cls in self._experiments.items():
            try:
                results[name] = self.run_experiment(name, **kwargs)
            except Exception as e:
                self.logger.error(f"Experiment [{name}] failed: {e}")
                results[name] = None
        return results

    def discover_experiments(self, package_path: str):
        """
        从指定包路径自动发现并注册所有 ExperimentBase 子类
        :param package_path: 点号分隔的包名，如 "lab_experiments"
        """
        try:
            package = importlib.import_module(package_path)
        except ImportError as e:
            self.logger.error(f"Failed to import package {package_path}: {e}")
            return

        for _, module_name, is_pkg in pkgutil.iter_modules(package.__path__):
            if is_pkg:
                continue
            try:
                module = importlib.import_module(f"{package_path}.{module_name}")
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, ExperimentBase) and attr is not ExperimentBase:
                        self.register(attr)
            except Exception as e:
                self.logger.error(f"Error loading experiment from module {module_name}: {e}")

    def run_self_tests(self):
        """执行所有已注册实验的 validate 自检，返回自检结果"""
        results = {}
        for name, cls in self._experiments.items():
            try:
                instance = cls()  # 使用默认配置构建
                valid = instance.validate()
                results[name] = valid
                self.logger.info(f"Self-test for [{name}]: {'PASS' if valid else 'FAIL'}")
            except Exception as e:
                self.logger.error(f"Self-test for [{name}] error: {e}")
                results[name] = False
        return results


# ---------- 实验注册装饰器 ----------
def register_experiment(name: Optional[str] = None, description: str = ""):
    """
    装饰器，用于简化实验类的注册。将类自动注册到全局实验管理器。
    :param name: 可选覆盖实验名称
    :param description: 可选覆盖描述
    """
    def decorator(cls):
        if name is not None:
            cls.name = name
        if description:
            cls.description = description
        manager = ExperimentManager()
        manager.register(cls)
        return cls
    return decorator


# ---------- 自测示例 ----------
class SimpleDemoExperiment(ExperimentBase):
    name = "simple_demo"
    description = "一个简单的演示实验，用于验证框架功能"

    def run(self, **kwargs):
        self.logger.info("Running simple demo experiment")
        return {"status": "success", "data": kwargs.get("data", "no data")}

    def validate(self):
        self.logger.info("Simple demo validated.")
        return True


if __name__ == "__main__":
    # 基础自测：注册、执行自测、运行
    print("=== 实验功能模块自测 ===")
    # 1. 设置基础日志配置，方便查看
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    manager = ExperimentManager()
    # 注册演示实验（装饰器方式也可以，这里直接手动）
    manager.register(SimpleDemoExperiment)

    # 2. 列出所有实验
    print("已注册实验:", manager.list_experiments())

    # 3. 执行自检
    print("\n执行自检...")
    test_results = manager.run_self_tests()
    print("自检结果:", test_results)

    # 4. 运行单个实验
    print("\n运行 simple_demo 实验:")
    result = manager.run_experiment("simple_demo", data={"key": "value"})
    print("实验结果:", result)

    # 5. 运行所有实验
    print("\n运行所有实验:")
    all_results = manager.run_all()
    print("所有实验运行结果:", all_results)
    print("=== 自测结束 ===")