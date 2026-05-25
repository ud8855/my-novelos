from __future__ import annotations

import importlib
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

# ------------------------------
# 配置管理
# ------------------------------
class ConfigLoader:
    """配置加载器，负责从文件或环境加载创世配置"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "world_creation_config.json")
        self._config: Dict[str, Any] = {}

    def load(self) -> Dict[str, Any]:
        """加载配置，支持json文件与环境变量覆盖"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"创世配置缺失: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            self._config = json.load(f)
        # 环境变量覆盖
        for key in self._config:
            env_val = os.getenv(f"WORLD_CREATION_{key.upper()}")
            if env_val is not None:
                try:
                    self._config[key] = json.loads(env_val)
                except json.JSONDecodeError:
                    self._config[key] = env_val
        return self._config

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

# ------------------------------
# 日志管理
# ------------------------------
class WorldLogger:
    """创世专用日志记录器，可切换输出"""

    def __init__(self, log_name: str = "WorldCreation", log_file: Optional[str] = None):
        self.logger = logging.getLogger(log_name)
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        # 控制台输出
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(formatter)
        self.logger.addHandler(console)
        # 可选文件输出
        if log_file:
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def debug(self, msg: str, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

# ------------------------------
# 基础世界创建器接口（可插拔）
# ------------------------------
class BaseWorldCreator(ABC):
    """所有世界创建器必须实现的抽象基类，保证插拔性"""

    def __init__(self, config: Dict[str, Any], logger: WorldLogger):
        self.config = config
        self.logger = logger

    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """验证创建参数"""
        ...

    @abstractmethod
    def create(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行世界创建，返回创建结果"""
        ...

    @classmethod
    def creator_type(cls) -> str:
        """返回创建器类型标识，用于注册"""
        return cls.__name__

# ------------------------------
# 具体世界创建器示例（可插拔）
# ------------------------------
class RealisticWorldCreator(BaseWorldCreator):
    """现实主义风格世界创建器"""

    def validate_params(self, params: Dict[str, Any]) -> bool:
        required = ["era", "location"]
        return all(k in params for k in required)

    def create(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info(f"开始创建现实主义世界: {params}")
        # 模拟创建流程
        world = {
            "type": "realistic",
            "name": params.get("name", "未命名"),
            "era": params["era"],
            "location": params["location"],
            "description": f"一个设定在{params['era']}，位于{params['location']}的现实世界。"
        }
        self.logger.info(f"现实主义世界创建完成: {world['name']}")
        return world

class FantasyWorldCreator(BaseWorldCreator):
    """奇幻风格世界创建器"""

    def validate_params(self, params: Dict[str, Any]) -> bool:
        required = ["magic_system", "races"]
        return all(k in params for k in required)

    def create(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info(f"开始创建奇幻世界: {params}")
        world = {
            "type": "fantasy",
            "name": params.get("name", "魔法大陆"),
            "magic_system": params["magic_system"],
            "races": params["races"],
            "description": f"一个拥有{params['magic_system']}魔法系统，居住着{'、'.join(params['races'])}的奇幻世界。"
        }
        self.logger.info(f"奇幻世界创建完成: {world['name']}")
        return world

# ------------------------------
# 创建器注册表（动态加载）
# ------------------------------
class CreatorRegistry:
    """管理所有可插拔的世界创建器，支持动态注册"""

    def __init__(self):
        self._creators: Dict[str, Type[BaseWorldCreator]] = {}

    def register(self, creator_class: Type[BaseWorldCreator]):
        type_key = creator_class.creator_type()
        if type_key in self._creators:
            raise ValueError(f"创建器 {type_key} 已注册")
        self._creators[type_key] = creator_class

    def get_creator(self, creator_type: str) -> Type[BaseWorldCreator]:
        if creator_type not in self._creators:
            raise KeyError(f"未找到创建器: {creator_type}")
        return self._creators[creator_type]

    def list_creators(self) -> List[str]:
        return list(self._creators.keys())

# ------------------------------
# 世界创世主引擎
# ------------------------------
class WorldCreationEngine:
    """世界创世主控引擎，负责调度创建器、配置和日志"""

    def __init__(self, config_path: Optional[str] = None, log_file: Optional[str] = None):
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()
        self.logger = WorldLogger(log_file=log_file or self.config.get("log_file"))
        self.registry = CreatorRegistry()
        self._initialize_registry()

    def _initialize_registry(self):
        """初始化注册内置创建器，并动态加载外部创建器"""
        # 注册内置创建器
        self.registry.register(RealisticWorldCreator)
        self.registry.register(FantasyWorldCreator)

        # 动态加载配置文件指定的外部创建器
        external_modules = self.config.get("external_creators", [])
        for module_path in external_modules:
            try:
                module = importlib.import_module(module_path)
                # 假设模块中定义了 creator_class
                creator_class = getattr(module, "creator_class", None)
                if creator_class and issubclass(creator_class, BaseWorldCreator):
                    self.registry.register(creator_class)
                    self.logger.info(f"加载外部创建器: {creator_class.creator_type()}")
                else:
                    self.logger.warning(f"模块 {module_path} 未提供有效的创建器类")
            except Exception as e:
                self.logger.error(f"加载外部创建器模块 {module_path} 失败: {str(e)}")

    def create_world(self, creator_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """根据类型创建世界"""
        self.logger.info(f"尝试使用创建器 {creator_type} 创建世界，参数: {params}")
        creator_class = self.registry.get_creator(creator_type)
        creator = creator_class(self.config, self.logger)

        if not creator.validate_params(params):
            self.logger.error(f"参数验证失败: {params}")
            raise ValueError(f"提供给 {creator_type} 的参数无效")

        try:
            world = creator.create(params)
            self.logger.info(f"世界创建成功: {world.get('name', '未知')}")
            return world
        except Exception as e:
            self.logger.error(f"世界创建过程出错: {str(e)}")
            raise

# ------------------------------
# 自测模块
# ------------------------------
if __name__ == "__main__":
    # 创建默认配置用于自测
    test_config = {
        "log_file": "world_creation_test.log",
        "external_creators": []
    }
    if not os.path.exists("world_creation_config.json"):
        with open("world_creation_config.json", "w", encoding="utf-8") as f:
            json.dump(test_config, f, ensure_ascii=False, indent=2)

    print("====== 世界创世模块自测 ======")
    engine = WorldCreationEngine()

    # 列出可用创建器
    print("可用创建器:", engine.registry.list_creators())

    # 测试现实主义世界
    try:
        realistic_world = engine.create_world("RealisticWorldCreator", {
            "name": "大唐盛世",
            "era": "唐代",
            "location": "长安"
        })
        print("创建的现实世界:", realistic_world)
    except Exception as e:
        print(f"创建失败: {e}")

    # 测试奇幻世界
    try:
        fantasy_world = engine.create_world("FantasyWorldCreator", {
            "name": "艾泽拉斯",
            "magic_system": "元素魔法",
            "races": ["人类", "精灵", "矮人"]
        })
        print("创建的奇幻世界:", fantasy_world)
    except Exception as e:
        print(f"创建失败: {e}")

    print("====== 自测完成 ======")