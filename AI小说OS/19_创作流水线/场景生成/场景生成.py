"""场景生成模块
功能：根据小说大纲、人物设定、当前进度等，生成下一个或指定场景的详细内容。
层次：19_创作流水线
依赖：核心抽象，下游插件可调用 20_模型协同 或 21_API模型 完成实际生成。
被调用者：编排器(创作流水线主控)、UI层通过接口调用。

本骨架提供基类、配置化、日志、插件注册机制，确保可插拔、可扩展。
"""

import logging
import configparser
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

# ---------- 日志配置 ----------
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
_ch = logging.StreamHandler()
_ch.setLevel(logging.DEBUG)
_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_ch.setFormatter(_formatter)
if not logger.handlers:
    logger.addHandler(_ch)

# ---------- 默认配置 ----------
DEFAULT_CONFIG = {
    'generator': {
        'default_model': 'gpt-4',
        'max_retries': '3',
        'temperature': '0.7',
        'max_tokens': '2000',
    },
    'plugins': {
        'enabled': 'default_generator',  # 默认插件名
    }
}

def load_config(config_path: Optional[str] = None) -> configparser.ConfigParser:
    """加载配置，若文件不存在则使用默认配置"""
    config = configparser.ConfigParser()
    config.read_dict(DEFAULT_CONFIG)
    if config_path:
        path = Path(config_path)
        if path.exists():
            config.read(path, encoding='utf-8')
            logger.info(f"已加载配置文件: {config_path}")
        else:
            logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
    else:
        logger.info("未指定配置文件，使用默认配置")
    return config


# ---------- 场景数据协议定义 ----------
class SceneContext:
    """传递给场景生成器的上下文信息，定义输入协议"""
    def __init__(self,
                 outline: str = "",           # 大局大纲
                 characters: List[Dict] = None,  # 人物列表，每个字典包含姓名、性格、背景等
                 current_chapter: int = 0,    # 当前章节
                 previous_scene: str = "",    # 前一个场景摘要
                 extra: Optional[Dict] = None):
        self.outline = outline
        self.characters = characters if characters is not None else []
        self.current_chapter = current_chapter
        self.previous_scene = previous_scene
        self.extra = extra if extra is not None else {}

class SceneResult:
    """场景生成结果协议"""
    def __init__(self,
                 scene_text: str = "",
                 scene_id: str = "",
                 metadata: Optional[Dict] = None):
        self.scene_text = scene_text
        self.scene_id = scene_id
        self.metadata = metadata if metadata is not None else {}


# ---------- 抽象基类 ----------
class BaseSceneGenerator(ABC):
    """场景生成器抽象基类，所有具体生成器必须实现 generate 方法"""

    def __init__(self, config: configparser.ConfigParser):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def generate(self, context: SceneContext) -> SceneResult:
        """根据上下文生成场景"""
        ...

    def validate_context(self, context: SceneContext) -> bool:
        """基础验证，子类可覆盖"""
        if not context.outline:
            self.logger.error("大纲为空，无法生成场景")
            return False
        return True

    def __repr__(self):
        return f"<{self.__class__.__name__}>"


# ---------- 插件注册与工厂 ----------
class GeneratorRegistry:
    """场景生成器注册中心，支持热插拔"""
    _generators: Dict[str, Type[BaseSceneGenerator]] = {}

    @classmethod
    def register(cls, name: str, generator_cls: Type[BaseSceneGenerator]):
        """注册一个新的场景生成器插件"""
        if name in cls._generators:
            logger.warning(f"生成器 '{name}' 已存在，将被覆盖")
        cls._generators[name] = generator_cls
        logger.info(f"已注册场景生成器: {name} -> {generator_cls.__name__}")

    @classmethod
    def unregister(cls, name: str):
        """移除一个生成器插件"""
        if name in cls._generators:
            del cls._generators[name]
            logger.info(f"已移除场景生成器: {name}")
        else:
            logger.warning(f"尝试移除不存在的生成器: {name}")

    @classmethod
    def get_generator(cls, name: str, config: configparser.ConfigParser) -> BaseSceneGenerator:
        """根据名称获取生成器实例"""
        if name not in cls._generators:
            logger.error(f"未找到生成器: {name}")
            raise KeyError(f"未注册的场景生成器: {name}")
        gen_cls = cls._generators[name]
        return gen_cls(config)

    @classmethod
    def list_registered(cls) -> List[str]:
        """列出所有已注册的生成器名称"""
        return list(cls._generators.keys())


# ---------- 一个默认的空实现，用于演示 ----------
class DefaultSceneGenerator(BaseSceneGenerator):
    """默认场景生成器，仅返回占位文本，实际使用需替换或扩展"""

    def generate(self, context: SceneContext) -> SceneResult:
        if not self.validate_context(context):
            return SceneResult(scene_text="[错误] 无效的上下文")
        # 实际应调用模型协同模块，这里只生成占位内容
        self.logger.info("使用默认生成器生成场景")
        scene_text = (
            f"根据大纲: {context.outline[:50]}...，章 {context.current_chapter} 的场景。"
            "（此处应由AI模型填充具体内容）"
        )
        return SceneResult(scene_text=scene_text, scene_id="auto_generated_001")


# ---------- 自测入口 ----------
if __name__ == "__main__":
    # 1. 加载配置
    cfg = load_config()
    
    # 2. 注册默认生成器
    GeneratorRegistry.register("default_generator", DefaultSceneGenerator)
    
    # 3. 获取启用的生成器名称
    enabled_plugin = cfg.get('plugins', 'enabled', fallback='default_generator')
    generator = GeneratorRegistry.get_generator(enabled_plugin, cfg)
    
    # 4. 构造测试上下文
    test_context = SceneContext(
        outline="主角穿越到异世界，面临生存挑战。",
        characters=[{"name": "林风", "role": "主角"}],
        current_chapter=3,
        previous_scene="林风在森林中遇到了神秘老人。"
    )
    
    # 5. 生成并打印结果
    result = generator.generate(test_context)
    print("生成结果：")
    print(result.scene_text)
    print("元数据：", result.metadata)
    
    # 6. 验证可插拔性：可动态注册/注销
    GeneratorRegistry.unregister("default_generator")
    print("注销后已注册生成器:", GeneratorRegistry.list_registered())