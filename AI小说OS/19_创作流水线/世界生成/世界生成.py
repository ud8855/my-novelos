"""
世界生成模块
负责根据设定生成小说的世界观，包括地理、历史、文化、势力等。
可插拔设计：支持多种生成器插件。
"""

import logging
import json
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class WorldGenerator:
    """
    世界观生成器基类，所有具体生成器需继承此类。
    """
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def generate(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成世界观的核心方法，子类必须实现。
        :param parameters: 生成参数
        :return: 世界观数据字典
        """
        raise NotImplementedError


class DefaultWorldGenerator(WorldGenerator):
    """
    默认世界观生成器，使用简单规则生成。
    """
    def generate(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info("使用默认生成器生成世界观")
        # TODO: 实现具体生成逻辑，调用模型等
        world = {
            "name": parameters.get("name", "未命名世界"),
            "description": "一个由AI生成的世界",
            "geography": {},
            "history": [],
            "cultures": [],
            "factions": []
        }
        return world


class WorldGenerationPipeline:
    """
    世界生成流水线，管理多个生成器，支持热插拔。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        self.generators: Dict[str, WorldGenerator] = {}
        self._load_default_generators()

    def _load_default_generators(self):
        """
        加载默认的生成器集合，可从配置扩展。
        """
        self.register_generator("default", DefaultWorldGenerator(self.config.get("default", {})))
        # 预留动态加载扩展生成器的能力
        extra_generators = self.config.get("extra_generators", [])
        # 示例：此处可根据配置动态加载类，实际使用时需实现安全导入机制
        for _ in extra_generators:
            pass

    def register_generator(self, name: str, generator: WorldGenerator):
        """
        注册生成器，实现热插拔。
        """
        self.logger.info(f"注册世界生成器: {name}")
        self.generators[name] = generator

    def unregister_generator(self, name: str):
        """
        移除生成器。
        """
        if name in self.generators:
            self.logger.info(f"移除世界生成器: {name}")
            del self.generators[name]

    def generate_world(self, generator_name: str = "default", parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        使用指定的生成器生成世界观。
        :param generator_name: 生成器名称
        :param parameters: 生成参数
        :return: 世界观数据字典
        """
        if parameters is None:
            parameters = {}
        generator = self.generators.get(generator_name)
        if not generator:
            raise ValueError(f"未找到生成器: {generator_name}")
        self.logger.info(f"开始生成世界观: {generator_name}")
        try:
            world = generator.generate(parameters)
            self.logger.info(f"世界观生成完成: {world.get('name', 'unknown')}")
            return world
        except Exception as e:
            self.logger.error(f"世界观生成失败: {e}", exc_info=True)
            raise


# 简单自测
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pipeline = WorldGenerationPipeline()
    params = {"name": "测试世界", "theme": "奇幻"}
    world = pipeline.generate_world("default", params)
    print(json.dumps(world, ensure_ascii=False, indent=2))