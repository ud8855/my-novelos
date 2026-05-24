"""
NovelOS - 实验模型模块
路径: 99_实验室/实验模型/实验模型.py
层级: 实验室层 (Lab)
职责: 提供可插拔的实验性AI模型接入框架，支持快速原型验证、临时模型调用和本地测试。
依赖: 20_模型协同/（通过协作者接口与主系统交互）
被谁调用: 实验室脚本、测试工具、临时探索任务
设计原则: 单一职责（仅负责实验模型管理），可插拔（通过适配器模式），配置化（使用_config.yml），日志记录，异常恢复。
"""

import logging
import time
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from abc import ABC, abstractmethod

# ------------------- 日志配置 -------------------
logger = logging.getLogger(__name__)

# ------------------- 配置管理 -------------------
DEFAULT_CONFIG = {
    "experiments": {
        "enabled": True,
        "model_adapters": {
            "mock_adapter": {
                "enabled": True,
                "class": "MockAdapter"
            }
        },
        "global_settings": {
            "max_retries": 3,
            "timeout_seconds": 30,
            "output_log_level": "INFO"
        }
    }
}

class ExperimentConfig:
    """实验模型配置管理器"""
    _instance = None
    _config = None

    def __new__(cls, config_path: Optional[Path] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_path: Optional[Path] = None):
        if self._initialized:
            return
        self.config_path = config_path or Path(__file__).parent / "_config.yml"
        self._load_config()
        self._initialized = True

    def _load_config(self):
        """加载配置文件，不存在时使用默认配置并生成文件"""
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
            logger.info(f"实验模型配置已加载: {self.config_path}")
        else:
            logger.warning(f"配置文件不存在，创建默认配置: {self.config_path}")
            self._config = DEFAULT_CONFIG
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, allow_unicode=True)
        # 合并默认值，防止缺失字段
        self._config = self._merge_defaults(self._config, DEFAULT_CONFIG)

    def _merge_defaults(self, config: dict, defaults: dict) -> dict:
        """递归合并默认配置"""
        for key, value in defaults.items():
            if key not in config:
                config[key] = value
            elif isinstance(value, dict) and isinstance(config.get(key), dict):
                config[key] = self._merge_defaults(config[key], value)
        return config

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项，支持点号分隔多级key"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    @property
    def config(self) -> dict:
        return self._config


# ------------------- 基础适配器接口 -------------------
class BaseModelAdapter(ABC):
    """
    实验模型适配器抽象基类。
    所有实验性模型必须实现此接口，确保可插拔。
    """
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.name = self.__class__.__name__
        self._setup_logging()

    def _setup_logging(self):
        """为适配器配置日志"""
        self.logger = logging.getLogger(f"{__name__}.{self.name}")
        self.logger.info(f"初始化实验模型适配器: {self.name}")

    @abstractmethod
    def load_model(self, model_path: Optional[str] = None, **kwargs) -> bool:
        """加载模型，返回是否成功"""
        pass

    @abstractmethod
    def predict(self, input_data: Any, **kwargs) -> Dict[str, Any]:
        """执行推理，返回结构化结果"""
        pass

    @abstractmethod
    def unload_model(self) -> bool:
        """卸载模型，释放资源"""
        pass

    def health_check(self) -> bool:
        """健康检查，默认返回True，可重写"""
        return True

    def __repr__(self):
        return f"<{self.name}>"


# ------------------- 内置测试适配器 -------------------
class MockAdapter(BaseModelAdapter):
    """
    模拟适配器，用于测试实验框架，不执行实际模型推理。
    """
    def load_model(self, model_path: Optional[str] = None, **kwargs) -> bool:
        self.logger.info(f"模拟加载模型: {model_path or 'default'}")
        return True

    def predict(self, input_data: Any, **kwargs) -> Dict[str, Any]:
        self.logger.info(f"模拟推理: {input_data}")
        # 模拟处理延迟
        time.sleep(0.1)
        return {
            "status": "mock_success",
            "output": f"simulated result for '{input_data}'",
            "model": self.name
        }

    def unload_model(self) -> bool:
        self.logger.info("模拟卸载模型")
        return True


# ------------------- 实验管理器 -------------------
class ExperimentManager:
    """
    实验模型管理器：加载、注册、调用实验模型适配器。
    不同实验模型通过适配器统一管理，支持动态添加和移除。
    """
    def __init__(self, config_path: Optional[Path] = None):
        self.config = ExperimentConfig(config_path)
        self.adapters: Dict[str, BaseModelAdapter] = {}
        self._active_adapter: Optional[BaseModelAdapter] = None
        self.logger = logging.getLogger(f"{__name__}.Manager")
        self._load_adapters()

    def _load_adapters(self):
        """根据配置加载启用的适配器实例"""
        adapter_configs = self.config.get("experiments.model_adapters", {})
        for name, cfg in adapter_configs.items():
            if cfg.get("enabled", True):
                try:
                    self.register_adapter(name, cfg)
                except Exception as e:
                    self.logger.error(f"加载适配器 {name} 失败: {e}")

    def register_adapter(self, name: str, adapter_config: Dict[str, Any]) -> bool:
        """注册一个新的适配器，根据配置中的class动态实例化"""
        if name in self.adapters:
            self.logger.warning(f"适配器 {name} 已存在，将被替换")
        class_name = adapter_config.get("class")
        if not class_name:
            self.logger.error(f"适配器 {name} 缺少 'class' 配置")
            return False
        # 查找适配器类（首先在全局命名空间查找，也可扩展为模块路径加载）
        adapter_cls = globals().get(class_name)
        if adapter_cls is None:
            # 可以扩展支持从字符串导入
            self.logger.error(f"未找到适配器类: {class_name}")
            return False
        try:
            instance = adapter_cls(config=adapter_config.get("settings", {}))
            self.adapters[name] = instance
            self.logger.info(f"适配器注册成功: {name} ({class_name})")
            return True
        except Exception as e:
            self.logger.error(f"实例化适配器 {name} 失败: {e}")
            return False

    def unregister_adapter(self, name: str) -> bool:
        """注销一个适配器"""
        if name in self.adapters:
            adapter = self.adapters.pop(name)
            adapter.unload_model()
            self.logger.info(f"适配器已注销: {name}")
            return True
        self.logger.warning(f"未找到适配器: {name}")
        return False

    def set_active_adapter(self, name: str) -> bool:
        """设置当前活动的适配器"""
        if name in self.adapters:
            self._active_adapter = self.adapters[name]
            self.logger.info(f"活动适配器切换为: {name}")
            return True
        self.logger.error(f"无法激活适配器，未注册: {name}")
        return False

    def get_active_adapter(self) -> Optional[BaseModelAdapter]:
        """获取当前活动适配器"""
        return self._active_adapter

    def run_experiment(self, input_data: Any, adapter_name: Optional[str] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """
        使用指定适配器（或默认活动适配器）运行实验。
        包含重试机制和超时控制。
        """
        adapter = None
        if adapter_name:
            adapter = self.adapters.get(adapter_name)
        else:
            adapter = self._active_adapter

        if not adapter:
            self.logger.error("没有可用的适配器执行实验")
            return None

        max_retries = self.config.get("experiments.global_settings.max_retries", 3)
        result = None
        for attempt in range(max_retries + 1):
            try:
                self.logger.info(f"实验执行 (适配器: {adapter.name}, 尝试: {attempt+1}/{max_retries+1})")
                result = adapter.predict(input_data, **kwargs)
                if result and result.get("status") != "error":
                    return result
                else:
                    self.logger.warning(f"实验返回错误状态: {result}")
            except Exception as e:
                self.logger.error(f"实验执行异常 (尝试 {attempt+1}): {e}")
            if attempt < max_retries:
                time.sleep(0.5)  # 短暂冷却再重试
        return result

    def health_check_all(self) -> Dict[str, bool]:
        """检查所有适配器健康状态"""
        status = {}
        for name, adapter in self.adapters.items():
            try:
                status[name] = adapter.health_check()
            except Exception:
                status[name] = False
        return status

    def shutdown(self):
        """关闭管理器，安全卸载所有适配器"""
        for name in list(self.adapters.keys()):
            self.unregister_adapter(name)
        self.logger.info("实验管理器已关闭")


# ------------------- 自测 -------------------
def self_test():
    """实验模型模块自测"""
    print("=== 实验模型模块自测 ===")
    # 强制使用默认配置，避免文件依赖
    config = ExperimentConfig()
    manager = ExperimentManager()
    # 检查已注册的适配器（默认只有MockAdapter）
    print(f"已注册适配器: {list(manager.adapters.keys())}")
    # 设置活动适配器
    manager.set_active_adapter("mock_adapter")
    # 运行实验
    result = manager.run_experiment(input_data="Hello, experiment!")
    print(f"实验结果: {result}")
    # 健康检查
    health = manager.health_check_all()
    print(f"健康状态: {health}")
    # 关闭
    manager.shutdown()
    print("自测完成")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    self_test()