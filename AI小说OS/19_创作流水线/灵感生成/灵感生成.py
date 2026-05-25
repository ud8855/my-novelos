"""
灵感生成模块 (Inspiration Generator)
所属层：19_创作流水线
职责：根据输入条件生成创作灵感/点子
依赖：日志模块、配置管理
被调用：创作流水线编排器
"""

import logging
import abc
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

# ---------- 自定义异常 ----------
class InspirationGenerationError(Exception):
    """灵感生成过程中发生的异常"""
    pass


# ---------- 配置类 ----------
@dataclass
class InspirationConfig:
    """灵感生成相关配置，支持从字典或配置文件加载"""
    # 模型相关
    model_name: str = "default_inspiration_model"
    temperature: float = 0.8
    max_length: int = 200
    # 生成控制
    num_inspirations: int = 1
    # 其他可选配置
    extra_params: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, cfg: Dict[str, Any]) -> "InspirationConfig":
        """从字典构建配置对象"""
        return cls(**{k: v for k, v in cfg.items() if k in cls.__dataclass_fields__})


# ---------- 抽象基类 (插拔式结构) ----------
class BaseInspirationGenerator(abc.ABC):
    """灵感生成器抽象基类，定义统一接口，支持热插拔"""

    def __init__(self, config: InspirationConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    @abc.abstractmethod
    def generate(self, prompt: Optional[str] = None, **kwargs) -> List[str]:
        """
        生成灵感列表
        :param prompt: 生成灵感的提示词，如果为None则使用默认提示
        :param kwargs: 额外参数，可覆盖配置中的部分值
        :return: 灵感文本列表
        """
        pass

    def health_check(self) -> bool:
        """健康检查，用于热更新时判断生成器是否可用"""
        try:
            # 简单检查，子类可重写
            return True
        except Exception:
            return False


# ---------- 具体实现示例 ----------
class DefaultInspirationGenerator(BaseInspirationGenerator):
    """默认灵感生成器，当前为骨架实现，未来接入实际模型"""

    def generate(self, prompt: Optional[str] = None, **kwargs) -> List[str]:
        """
        生成灵感
        当前为占位实现，后续将接入模型协同层 (20_模型协同/21_API模型)
        """
        self.logger.info(f"开始生成灵感，提示词: {prompt if prompt else '默认'}")
        try:
            # 合并配置和运行时参数
            temperature = kwargs.get("temperature", self.config.temperature)
            max_length = kwargs.get("max_length", self.config.max_length)
            num = kwargs.get("num_inspirations", self.config.num_inspirations)

            # TODO: 未来调用真正的模型 API，例如：
            # from models.collaboration import ModelOrchestrator
            # orchestrator = ModelOrchestrator.get_instance()
            # result = orchestrator.generate(
            #     prompt=prompt or "给我一个小说灵感",
            #     temperature=temperature,
            #     max_length=max_length,
            #     num=num
            # )
            # 当前返回模拟数据
            self.logger.debug(f"当前为占位实现，生成 {num} 条模拟灵感")
            mock_inspirations = [
                f"灵感{i+1}: [模拟] 一个关于 {prompt if prompt else '未知主题'} 的创意火花"
                for i in range(num)
            ]
            self.logger.info(f"成功生成 {len(mock_inspirations)} 条灵感")
            return mock_inspirations

        except Exception as e:
            self.logger.error(f"灵感生成失败: {str(e)}", exc_info=True)
            raise InspirationGenerationError(f"灵感生成异常: {str(e)}") from e


# ---------- 生成器工厂 (用于插拔) ----------
class InspirationGeneratorFactory:
    """灵感生成器工厂，根据配置动态加载不同的生成器实现"""
    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str, generator_cls: type):
        """注册生成器实现"""
        if not issubclass(generator_cls, BaseInspirationGenerator):
            raise TypeError(f"注册的类必须继承 BaseInspirationGenerator")
        cls._registry[name] = generator_cls

    @classmethod
    def create(cls, config: InspirationConfig) -> BaseInspirationGenerator:
        """根据配置中的 generator 字段或默认值创建实例"""
        generator_type = config.extra_params.get("generator_type", "default")
        if generator_type not in cls._registry:
            raise ValueError(f"未知生成器类型: {generator_type}，可用: {list(cls._registry.keys())}")
        cls_instance = cls._registry[generator_type]
        return cls_instance(config)


# 注册默认生成器
InspirationGeneratorFactory.register("default", DefaultInspirationGenerator)


# ---------- 自测 (if __name__ == "__main__") ----------
if __name__ == "__main__":
    # 配置日志输出
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    logger = logging.getLogger("InspirationTest")

    # 1. 创建配置
    config = InspirationConfig(
        model_name="test_model",
        temperature=0.9,
        max_length=100,
        num_inspirations=2,
        extra_params={"generator_type": "default"}
    )

    # 2. 通过工厂创建生成器（体现插拔）
    try:
        generator = InspirationGeneratorFactory.create(config)
        logger.info("成功创建灵感生成器实例")
    except Exception as e:
        logger.error(f"创建生成器失败: {e}")
        exit(1)

    # 3. 健康检查
    if generator.health_check():
        logger.info("生成器健康检查通过")
    else:
        logger.warning("生成器健康检查失败")

    # 4. 生成灵感测试
    try:
        ideas = generator.generate(prompt="一个赛博朋克武侠世界")
        print("生成的灵感:")
        for idea in ideas:
            print(f"  - {idea}")
    except InspirationGenerationError as e:
        logger.error(f"灵感生成失败: {e}")

    # 5. 测试工厂注册新类型（演示插拔）
    class CustomInspirationGenerator(BaseInspirationGenerator):
        def generate(self, prompt=None, **kwargs):
            return ["自定义灵感1", "自定义灵感2"]

    InspirationGeneratorFactory.register("custom", CustomInspirationGenerator)
    config2 = InspirationConfig(extra_params={"generator_type": "custom"})
    gen2 = InspirationGeneratorFactory.create(config2)
    print("自定义生成器结果:", gen2.generate())