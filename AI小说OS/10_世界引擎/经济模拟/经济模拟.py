"""
模块：经济模拟 (Economy Simulator)
位置：10_世界引擎/经济模拟/经济模拟.py
层级：世界引擎层 - 处理小说世界中的经济系统
依赖：基础配置、日志系统（通过项目通用模块）
被谁调用：世界引擎总控、剧情生成器、Agent决策、NPC行为系统
解决的问题：提供可插拔的经济模拟框架，支持不同经济规则、资源流动、市场模拟等的统一接口
"""

import logging
import abc
from typing import Dict, Any, Optional, List
from configparser import ConfigParser
import importlib
import inspect

# 配置
from pathlib import Path
import sys

# 如果项目有全局配置，可以从这里导入，否则独立加载
# from config.global_config import config  # 假设存在

logger = logging.getLogger(__name__)

# ------------------------------
# 基础抽象类
# ------------------------------
class BaseEconomySimulator(abc.ABC):
    """
    经济模拟器抽象基类，所有具体的经济模拟器必须继承并实现其抽象方法。
    支持热插拔：通过 register_simulator 注册新模拟器，可在运行时切换。
    """

    def __init__(self, name: str, config: dict):
        """
        初始化模拟器
        :param name: 模拟器唯一名称
        :param config: 该模拟器的配置字典
        """
        self.name = name
        self.config = config
        self.is_running = False
        logger.info(f"初始化经济模拟器 -> {self.name}")

    @abc.abstractmethod
    def initialize(self) -> bool:
        """
        初始化经济环境，加载资源、市场模板等。
        :return: 成功返回 True，否则 False
        """
        pass

    @abc.abstractmethod
    def update(self, delta_time: float, world_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行一帧（或一个时间步长）的经济更新。
        :param delta_time: 时间增量
        :param world_state: 当前世界状态（包含所有经济主体数据）
        :return: 更新后的经济状态字典
        """
        pass

    @abc.abstractmethod
    def shutdown(self):
        """
        关闭经济模拟，释放资源，保持状态。
        """
        pass

    def start(self):
        """启动模拟器，调用 initialize，并设置运行标志"""
        if not self.is_running:
            logger.info(f"启动经济模拟器: {self.name}")
            success = self.initialize()
            if success:
                self.is_running = True
            else:
                logger.error(f"经济模拟器 {self.name} 初始化失败")
        else:
            logger.warning(f"经济模拟器 {self.name} 已在运行中")

    def stop(self):
        """停止模拟器，调用 shutdown"""
        if self.is_running:
            logger.info(f"停止经济模拟器: {self.name}")
            self.shutdown()
            self.is_running = False

    def get_config_value(self, key: str, default=None):
        """从配置中获取值"""
        return self.config.get(key, default)

# ------------------------------
# 模拟器注册中心（可插拔机制）
# ------------------------------
class EconomySimulatorRegistry:
    """经济模拟器注册表，支持动态添加/移除/选择模拟器"""
    _simulators: Dict[str, type] = {}  # 类名 -> 类
    _instances: Dict[str, BaseEconomySimulator] = {}  # 实例名称 -> 实例

    @classmethod
    def register(cls, simulator_class: type):
        """注册一个经济模拟器类（添加装饰器支持）"""
        if not issubclass(simulator_class, BaseEconomySimulator):
            raise TypeError(f"只能注册 BaseEconomySimulator 的子类，得到: {simulator_class}")
        name = simulator_class.__name__
        cls._simulators[name] = simulator_class
        logger.info(f"注册经济模拟器类型: {name}")

    @classmethod
    def unregister(cls, simulator_class_name: str):
        """移除注册的模拟器类"""
        if simulator_class_name in cls._simulators:
            del cls._simulators[simulator_class_name]
            logger.info(f"注销经济模拟器类型: {simulator_class_name}")

    @classmethod
    def create_instance(cls, simulator_type_name: str, instance_name: str, config: dict = None) -> Optional[BaseEconomySimulator]:
        """根据注册的模拟器类型创建实例。返回实例或 None"""
        if simulator_type_name not in cls._simulators:
            logger.error(f"未找到注册的模拟器类型: {simulator_type_name}")
            return None
        sim_cls = cls._simulators[simulator_type_name]
        if config is None:
            config = {}
        # 合并全局配置？
        instance = sim_cls(name=instance_name, config=config)
        cls._instances[instance_name] = instance
        return instance

    @classmethod
    def get_instance(cls, instance_name: str) -> Optional[BaseEconomySimulator]:
        return cls._instances.get(instance_name)

    @classmethod
    def remove_instance(cls, instance_name: str):
        """停止并移除实例"""
        inst = cls._instances.pop(instance_name, None)
        if inst:
            inst.stop()
            logger.info(f"移除经济模拟器实例: {instance_name}")

    @classmethod
    def list_registered_types(cls) -> List[str]:
        return list(cls._simulators.keys())

    @classmethod
    def list_instances(cls) -> List[str]:
        return list(cls._instances.keys())

# 装饰器，用于方便注册
def register_economy_simulator(cls):
    EconomySimulatorRegistry.register(cls)
    return cls

# ------------------------------
# 配置加载工具
# ------------------------------
def load_economy_config(config_path: str = None) -> dict:
    """
    加载经济模拟配置文件（如 economoy_config.ini 或 json）。
    如果文件不存在，返回默认配置。
    """
    default_config = {
        "default_simulator_type": "BasicEconomySimulator",
        "update_interval_ms": 1000,
        "enable_market": "true",
        "initial_money_supply": 100000,
        "resource_types": "gold,wood,food,stone",
        "enable_logging": "true"
    }
    if not config_path:
        # 从系统配置路径读取
        base_dir = Path(__file__).parent.parent.parent  # 假设项目根目录为 ../../
        config_path = base_dir / "config" / "economy_config.ini"
    else:
        config_path = Path(config_path)
    
    config = ConfigParser()
    if config_path.exists():
        config.read(config_path)
        if "economy" in config.sections():
            return dict(config["economy"])
        logger.warning(f"经济配置文件 {config_path} 中没有 [economy] 节，使用默认配置")
    else:
        logger.warning(f"经济配置文件 {config_path} 不存在，使用默认配置")
    # 返回默认配置
    return default_config

# ------------------------------
# 主控制类（可选，用于世界引擎集成）
# ------------------------------
class EconomyManager:
    """
    经济管理器，负责加载配置、创建和切换经济模拟器实例，协调更新。
    """
    def __init__(self, config: dict = None):
        if config is None:
            config = load_economy_config()
        self.config = config
        self.simulator: Optional[BaseEconomySimulator] = None
        self._auto_create_default()

    def _auto_create_default(self):
        """根据配置自动创建一个默认模拟器实例"""
        type_name = self.config.get("default_simulator_type", "BasicEconomySimulator")
        inst_name = "default_instance"
        instance = EconomySimulatorRegistry.create_instance(type_name, inst_name, self.config)
        if instance:
            self.simulator = instance
            logger.info(f"自动创建经济模拟器实例: {type_name} 命名为 {inst_name}")
        else:
            logger.error("无法自动创建经济模拟器实例，请检查配置或注册")

    def switch_simulator(self, new_type_name: str, new_instance_name: str = "default_instance"):
        """切换当前使用的经济模拟器"""
        if self.simulator:
            self.simulator.stop()
            # 可以选择是否移除旧实例
        instance = EconomySimulatorRegistry.create_instance(new_type_name, new_instance_name, self.config)
        if instance:
            self.simulator = instance
            self.simulator.start()
            logger.info(f"切换经济模拟器至: {new_type_name}")
        else:
            logger.error(f"切换失败，无法创建模拟器: {new_type_name}")

    def update(self, delta_time: float, world_state: dict) -> dict:
        """更新经济状态，如果模拟器未运行则尝试启动"""
        if not self.simulator:
            logger.error("没有活跃的经济模拟器，无法更新")
            return world_state
        if not self.simulator.is_running:
            logger.warning("经济模拟器未运行，尝试启动...")
            self.simulator.start()
            if not self.simulator.is_running:
                return world_state
        try:
            new_economy_state = self.simulator.update(delta_time, world_state)
            return new_economy_state
        except Exception as e:
            logger.exception(f"经济模拟器更新时发生异常: {e}")
            # 异常恢复：尝试重启模拟器？
            self.simulator.stop()
            self.simulator.start()
            return world_state  # 返回原始状态

    def shutdown(self):
        if self.simulator:
            self.simulator.stop()
            self.simulator = None

# ------------------------------
# 自测
# ------------------------------
if __name__ == "__main__":
    # 配置日志格式
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger.info("开始经济模拟模块自测")

    # 1. 注册一个简单的测试模拟器
    @register_economy_simulator
    class TestEconomySimulator(BaseEconomySimulator):
        def initialize(self) -> bool:
            logger.info("TestEconomySimulator 初始化")
            return True
        def update(self, delta_time: float, world_state: Dict[str, Any]) -> Dict[str, Any]:
            logger.info(f"TestEconomySimulator 更新，delta={delta_time}")
            # 简单修改世界状态，模拟经济变化
            if "economy" not in world_state:
                world_state["economy"] = {}
            world_state["economy"]["last_update"] = delta_time
            return world_state
        def shutdown(self):
            logger.info("TestEconomySimulator 关闭")

    # 2. 测试注册中心
    print("已注册类型:", EconomySimulatorRegistry.list_registered_types())
    instance = EconomySimulatorRegistry.create_instance("Test