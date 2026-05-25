"""
模块：地图生成
所属层：24_创世系统
依赖：无（或可依赖配置/日志基础设施）
被调用：世界构建流程、用户界面层（通过接口调用）
职责：根据世界参数生成基础地图数据结构（抽象接口与基础实现）
可插拔：通过配置切换不同地图生成策略
配置化：读取全局配置，动态选择生成器
日志：记录生成过程、异常信息
"""

from abc import ABC, abstractmethod
import logging
import json
import os
import sys
from typing import Dict, Any, Optional

# --------------------------------------------------------------
# 日志配置 (可插拔：若顶层未配置，则自动初始化)
# --------------------------------------------------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)  # 可根据配置调整


# --------------------------------------------------------------
# 地图生成器抽象接口 (协议层)
# --------------------------------------------------------------
class BaseMapGenerator(ABC):
    """
    地图生成器抽象基类。
    所有具体生成器必须实现此接口，确保可插拔。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化生成器，注入配置。
        
        Args:
            config: 生成器专用配置字典（可选），若未提供则使用默认配置。
        """
        self.config = config or {}  # 配置覆盖由子类处理
        logger.debug("地图生成器初始化完成，类型: %s", self.__class__.__name__)

    @abstractmethod
    def generate_map(self, world_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据世界参数生成地图数据结构。
        
        Args:
            world_params: 世界参数字典，包含如尺寸、地形比例、生物群系等。
        
        Returns:
            地图数据结构字典，格式由具体实现定义。
        """
        pass

    @abstractmethod
    def validate_params(self, world_params: Dict[str, Any]) -> bool:
        """
        校验世界参数合法性。
        
        Args:
            world_params: 待校验的世界参数。
        
        Returns:
            若参数合法返回 True，否则 False。
        """
        pass


# --------------------------------------------------------------
# 默认地图生成器实现 (示例/地基)
# --------------------------------------------------------------
class DefaultMapGenerator(BaseMapGenerator):
    """
    默认地图生成器，生成简单的二维网格地图。
    支持通过配置自定义算法参数。
    """
    DEFAULT_CONFIG = {
        "default_size": (100, 100),          # 默认地图宽度和高度
        "terrain_types": ["平原", "森林", "山脉", "水体"],
        "default_terrain": "平原",
        "algorithm": "random_fill",          # 当前使用的算法
        "random_seed": None
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        # 合并默认配置与用户配置
        merged_config = self.DEFAULT_CONFIG.copy()
        if config:
            merged_config.update(config)
        super().__init__(merged_config)
        logger.info("默认地图生成器已就绪，配置: %s", merged_config)

    def validate_params(self, world_params: Dict[str, Any]) -> bool:
        """
        简单校验：尺寸必须为两个正整数元组。
        """
        size = world_params.get("size", self.config["default_size"])
        if not (isinstance(size, (list, tuple)) and len(size) == 2 and
                all(isinstance(i, int) and i > 0 for i in size)):
            logger.error("地图尺寸无效: %s", size)
            return False
        # 可扩展更多校验...
        return True

    def generate_map(self, world_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成默认地图。
        当前为骨架实现，返回固定尺寸的空地图，真实逻辑待后续填充。
        
        Args:
            world_params: 世界参数，必须包含 size 键。
        
        Returns:
            字典格式：
            {
                "width": int,
                "height": int,
                "tiles": [[terrain_str, ...], ...],
                "metadata": {...}
            }
        """
        if not self.validate_params(world_params):
            raise ValueError("世界参数验证失败，无法生成地图")

        size = world_params.get("size", self.config["default_size"])
        width, height = size[0], size[1]
        default_terrain = self.config["default_terrain"]

        logger.info("开始生成地图，尺寸: %dx%d，默认地形: %s", width, height, default_terrain)
        
        # 骨架：填充全是默认地形
        tiles = [[default_terrain for _ in range(width)] for _ in range(height)]

        map_data = {
            "width": width,
            "height": height,
            "tiles": tiles,
            "metadata": {
                "generator": self.__class__.__name__,
                "algorithm": self.config["algorithm"],
                "seed": self.config.get("random_seed"),
                "description": "骨架地图，待实现算法"
            }
        }
        logger.info("地图生成完成")
        return map_data


# --------------------------------------------------------------
# 生成器工厂函数 (用于插拔式加载)
# --------------------------------------------------------------
def get_map_generator(generator_type: str = "default", config: Optional[Dict[str, Any]] = None) -> BaseMapGenerator:
    """
    根据类型标识获取地图生成器实例。
    支持动态扩展，可注册新类型。
    
    Args:
        generator_type: 生成器类型字符串，如 "default"。
        config: 传递给生成器的配置。
    
    Returns:
        BaseMapGenerator 子类实例。
    
    Raises:
        ValueError: 若生成器类型未注册。
    """
    registry = {
        "default": DefaultMapGenerator,
        # 未来可添加: "perlin": PerlinMapGenerator, ...
    }
    if generator_type not in registry:
        raise ValueError(f"未知的地图生成器类型: {generator_type}，可用类型: {list(registry.keys())}")
    
    generator_class = registry[generator_type]
    logger.debug("通过工厂创建生成器: %s", generator_type)
    return generator_class(config=config)


# --------------------------------------------------------------
# 配置读取辅助 (可独立使用)
# --------------------------------------------------------------
def load_config_from_file(filepath: str) -> Dict[str, Any]:
    """
    从 JSON/YAML 文件加载配置。当前仅支持 JSON 示例。
    
    Args:
        filepath: 配置文件路径。
    
    Returns:
        配置字典。
    """
    logger.debug("加载配置文件: %s", filepath)
    # 骨架：简单 JSON 加载，可扩展为 YAML 等
    with open(filepath, 'r', encoding='utf-8') as f:
        config = json.load(f)
    return config


# --------------------------------------------------------------
# 自测逻辑
# --------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 50)
    print("地图生成模块自测")
    print("=" * 50)

    # 1. 无配置，使用默认生成器
    logger.info("测试1：默认生成器无参数")
    gen = get_map_generator()
    try:
        result = gen.generate_map({"size": (10, 10)})
        logger.info("生成成功，返回数据结构键: %s", list(result.keys()))
        # 示例输出部分数据
        print(f"地图宽度: {result['width']}, 高度: {result['height']}")
        print(f"左上角瓦片地形: {result['tiles'][0][0]}")
    except Exception as e:
        logger.error("生成失败: %s", e)

    # 2. 自定义配置
    logger.info("测试2：使用自定义配置生成器")
    custom_config = {
        "default_terrain": "草原",
        "random_seed": 42
    }
    gen2 = get_map_generator("default", config=custom_config)
    try:
        result2 = gen2.generate_map({"size": (5, 5)})
        logger.info("自定义配置生成成功，默认地形为: %s", result2["tiles"][0][0])
    except Exception as e:
        logger.error("生成失败: %s", e)

    # 3. 参数验证测试
    logger.info("测试3：参数验证")
    print("无效参数测试:", gen.validate_params({"size": (-1, 5)}))  # 预期 False

    # 4. 错误类型处理
    logger.info("测试4：未知生成器类型")
    try:
        get_map_generator("unknown")
    except ValueError as e:
        logger.info("正确捕获未知生成器错误: %s", e)

    print("自测完成")