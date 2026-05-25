import logging
import configparser
import abc
from typing import Any, Dict, List, Optional
from pathlib import Path

# ----------------------------------------------------------------------
# 模块：社会模拟 (SocialSimulation)
# 层级：10_世界引擎 → 社会模拟
# 依赖：无外部实际依赖，所有外部服务通过抽象接口注入
# 被调用：世界引擎核心调度器，通过 run_simulation() 循环调用
# 解决：小说世界中社会关系、群体行为、文化演变等动态模拟
# ----------------------------------------------------------------------

class ISocialModel(abc.ABC):
    """
    社会模型抽象接口 (可插拔)
    所有具体社会模型必须实现此接口
    """
    @abc.abstractmethod
    def initialize(self, config: Dict[str, Any]) -> None:
        """根据配置初始化模型"""
        pass

    @abc.abstractmethod
    def step(self, world_state: Dict[str, Any]) -> Dict[str, Any]:
        """执行一个模拟步骤，返回更新后的世界状态"""
        pass

    @abc.abstractmethod
    def shutdown(self) -> None:
        """释放资源，优雅关闭"""
        pass


class SocialSimulator:
    """
    社会模拟器核心类
    负责加载配置、管理社会模型实例、执行模拟循环、记录日志
    所有功能支持热插拔和配置化
    """
    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化模拟器
        :param config_path: 配置文件路径，默认从模块config.ini读取
        """
        self._config_path = config_path or Path(__file__).parent / "config.ini"
        self._config = configparser.ConfigParser()
        self._model: Optional[ISocialModel] = None
        self._is_running = False
        self._setup_logging()
        self._load_config()
        self.logger.info("SocialSimulator instance created.")

    def _setup_logging(self):
        """配置日志系统，默认输出到控制台和文件"""
        self.logger = logging.getLogger("SocialSimulator")
        self.logger.setLevel(logging.DEBUG)
        # 避免重复添加处理器
        if not self.logger.handlers:
            # 控制台处理器
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

            # 文件处理器（示例，可配置）
            file_handler = logging.FileHandler("social_simulation.log", encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def _load_config(self):
        """从配置文件加载设置，配置缺失时使用默认值"""
        if not self._config_path.exists():
            self.logger.warning(f"Config file {self._config_path} not found, using defaults.")
            self._apply_defaults()
            return

        try:
            self._config.read(self._config_path, encoding="utf-8")
            # 验证必要节
            if "SocialModel" not in self._config:
                raise ValueError("Missing [SocialModel] section in config")
            model_name = self._config["SocialModel"].get("model_class", "DefaultSocialModel")
            self.logger.info(f"Loading model class: {model_name}")
            # 其他配置项可根据需要读取，交给具体模型处理
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}, falling back to defaults.")
            self._apply_defaults()

    def _apply_defaults(self):
        """应用默认配置"""
        self._config["SocialModel"] = {"model_class": "DefaultSocialModel"}

    def get_config(self) -> Dict[str, Any]:
        """对外提供配置信息（只读）"""
        return {section: dict(self._config[section]) for section in self._config.sections()}

    def load_model(self, model_class_path: str):
        """
        动态加载社会模型类（可插拔核心）
        :param model_class_path: 完全限定类路径，如 "models.my_model.MySocialModel"
        """
        try:
            module_path, class_name = model_class_path.rsplit(".", 1)
            import importlib
            module = importlib.import_module(module_path)
            model_class = getattr(module, class_name)
            if not issubclass(model_class, ISocialModel):
                raise TypeError(f"{class_name} must implement ISocialModel")
            self._model = model_class()
            self.logger.info(f"Successfully loaded model: {model_class_path}")
        except Exception as e:
            self.logger.exception(f"Failed to load model {model_class_path}: {e}")
            raise

    def initialize_model(self):
        """使用当前配置初始化已加载的模型"""
        if self._model is None:
            raise RuntimeError("No model loaded. Call load_model() first.")
        model_config = self.get_config().get("SocialModel", {})
        self._model.initialize(model_config)
        self.logger.info("Model initialized.")

    def start_simulation(self):
        """启动模拟循环（设置运行标志）"""
        if self._model is None:
            raise RuntimeError("Model not initialized.")
        self._is_running = True
        self.logger.info("Simulation started.")

    def stop_simulation(self):
        """安全停止模拟"""
        self._is_running = False
        self.logger.info("Simulation stop signal sent.")

    def run_simulation(self, world_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行一个模拟步骤（由外部调度器周期性调用）
        :param world_state: 当前世界状态字典
        :return: 更新后的世界状态
        """
        if not self._is_running:
            self.logger.warning("Simulation not running, step ignored.")
            return world_state

        try:
            new_state = self._model.step(world_state)
            self.logger.debug("Simulation step completed.")
            return new_state
        except Exception as e:
            self.logger.exception(f"Simulation step failed: {e}")
            # 异常恢复：返回未修改的状态，保证系统稳定
            return world_state

    def shutdown(self):
        """优雅关闭模拟器，释放资源"""
        self.stop_simulation()
        if self._model:
            try:
                self._model.shutdown()
                self.logger.info("Model shutdown successfully.")
            except Exception as e:
                self.logger.exception(f"Error shutting down model: {e}")

    def hot_reload_model(self, model_class_path: str):
        """
        热更新模型：卸载当前模型，加载新模型，保持运行状态
        """
        self.logger.info("Hot reloading model...")
        # 先关闭旧模型
        if self._model:
            try:
                self._model.shutdown()
            except Exception as e:
                self.logger.warning(f"Old model shutdown error (ignored): {e}")
        # 加载新模型
        self.load_model(model_class_path)
        self.initialize_model()
        # 如果之前在运行，保持运行状态
        if self._is_running:
            self.logger.info("Resuming simulation after hot reload.")
        else:
            self.start_simulation()
        self.logger.info("Hot reload completed.")

# ----------------------------------------------------------------------
# 默认社会模型实现（示例，可被替换）
# ----------------------------------------------------------------------
class DefaultSocialModel(ISocialModel):
    """默认社会模型，仅作占位，不做实际计算"""
    def initialize(self, config: Dict[str, Any]) -> None:
        self.logger = logging.getLogger("DefaultSocialModel")
        self.logger.info("DefaultSocialModel initialized with config: %s", config)

    def step(self, world_state: Dict[str, Any]) -> Dict[str, Any]:
        # 无操作，直接返回原状态
        return world_state

    def shutdown(self) -> None:
        self.logger.info("DefaultSocialModel shutdown.")


# ----------------------------------------------------------------------
# 自测代码 (仅在直接运行本文件时执行)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # 测试基本流程
    sim = SocialSimulator()
    print("Config:", sim.get_config())

    # 加载默认模型
    sim.load_model("__main__.DefaultSocialModel")
    sim.initialize_model()
    sim.start_simulation()

    # 模拟几个步骤
    world = {"population": 100, "culture": "中土"}
    for i in range(3):
        world = sim.run_simulation(world)
        print(f"Step {i+1}: {world}")

    # 热更新模型（使用同一模型类模拟）
    sim.hot_reload_model("__main__.DefaultSocialModel")

    # 再模拟一步
    world = sim.run_simulation(world)
    print("After hot reload:", world)

    # 关闭
    sim.shutdown()
    print("Test completed.")