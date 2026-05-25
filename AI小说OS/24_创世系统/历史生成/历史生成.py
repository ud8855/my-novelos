"""
24_创世系统/历史生成.py

职责：
    - 生成小说世界的宏观历史事件、年代记、文明兴衰等。
    - 提供可插拔的历史生成策略，支持配置化与日志记录。
    - 依赖：20_模型协同/、21_API模型/（通过统一接口调用底层AI模型）。
    - 被调用：创世系统总控模块，或直接由上层服务调用。

设计原则：
    - 单一职责：仅负责“历史生成”，不涉及地理、种族等其他创世内容。
    - 可插拔：通过继承或组合方式，允许替换不同的生成算法/模型。
    - 配置化：生成参数、提示词模板、模型选择等均可配置。
    - 异常恢复与日志：所有生成过程带日志，失败时记录并尝试回退。
"""

import logging
import configparser
import os
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

# -----------------------------------------------------------------------------
# 基础配置与日志
# -----------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# 默认配置文件路径（可通过环境变量覆盖）
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "历史生成配置.ini")

class ConfigLoader:
    """简化的配置加载器，支持 ini 或环境变量"""
    def __init__(self, config_path: Optional[str] = None):
        self.config = configparser.ConfigParser()
        path = config_path or os.getenv("HISTORY_GEN_CONFIG", DEFAULT_CONFIG_PATH)
        if os.path.exists(path):
            self.config.read(path, encoding='utf-8')
            logger.info(f"已加载配置文件: {path}")
        else:
            logger.warning(f"配置文件不存在: {path}，将使用默认值")
    
    def get(self, section: str, key: str, fallback: Any = None) -> str:
        """获取配置项，优先使用环境变量"""
        env_key = f"HISTORYGEN_{section.upper()}_{key.upper()}"
        env_val = os.getenv(env_key)
        if env_val is not None:
            return env_val
        try:
            return self.config.get(section, key, fallback=fallback)
        except configparser.NoSectionError:
            return fallback

# 全局配置实例（可在任务中重新加载）
_config = ConfigLoader()

# -----------------------------------------------------------------------------
# 抽象基类：历史生成器接口
# -----------------------------------------------------------------------------
class BaseHistoryGenerator(ABC):
    """
    历史生成器基类，定义生成器必须实现的接口。
    允许通过实现子类来切换不同的生成逻辑（如不同AI模型、不同Prompt等）。
    """
    def __init__(self, config: ConfigLoader = _config):
        self.config = config
    
    @abstractmethod
    def generate_world_history(self, world_params: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据世界参数生成完整历史。
        
        参数:
            world_params: 包含世界基本设定的字典，例如：
                - `world_type`: 世界类型（如奇幻、科幻、仙侠）
                - `magic_system`: 魔法系统描述
                - `initial_era`: 起始纪元
                - 其他自定义键
        
        返回:
            dict, 至少包含:
                - `eras`: 各个时代的描述列表
                - `events`: 关键历史事件列表
                - `timeline`: 时间线结构
        """
        pass
    
    @abstractmethod
    def expand_event(self, event_key: str, extra_context: Optional[Dict] = None) -> Dict:
        """
        对已有历史事件的细节进行扩展（如战争细节、人物传记等）。
        
        参数:
            event_key: 事件标识符，如时间线中的事件ID
            extra_context: 额外上下文
        
        返回:
            dict, 包含扩展后的详细信息
        """
        pass

# -----------------------------------------------------------------------------
# 默认实现：基于大语言模型的历史生成器
# -----------------------------------------------------------------------------
class LLMHistoryGenerator(BaseHistoryGenerator):
    """
    使用底层AI模型（通过20_模型协同层调用）生成历史。
    支持Prompt模板化，配置化。
    """
    def __init__(self, config: ConfigLoader = _config):
        super().__init__(config)
        # 从配置读取模型选择、温度等
        self.model_name = self.config.get("LLM", "model_name", "default_novel_model")
        self.temperature = float(self.config.get("LLM", "temperature", "0.7"))
        self.max_tokens = int(self.config.get("LLM", "max_tokens", "2048"))
        # 模拟服务调用接口，实际应注入模型协同客户端
        # 这里只是骨架，实际调用时需实现或替换服务
        self._model_service = None  # 占位，后期对接

    def _call_model(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        调用底层模型服务，进行文本生成。
        当前为骨架，实际需实现模型调用逻辑。
        """
        # TODO: 集成20_模型协同/ 和 21_API模型/
        logger.debug(f"调用模型 {self.model_name}，参数: temp={self.temperature}, max_tokens={self.max_tokens}")
        # 模拟返回
        return f"[模拟生成内容] 基于Prompt: {prompt[:50]}... 返回的历史文本"
    
    def _build_prompt(self, template_key: str, **kwargs) -> str:
        """从配置或默认模板库构建提示词"""
        # 骨架：后续可从单独模板文件加载（如 yaml/json）
        templates = {
            "world_history": "请为以下世界设定生成详尽的历史：{world_type}，魔法特点：{magic_system}，起始纪元：{initial_era}。请产出年代、大事件、文明变迁。",
            "event_expand": "关于事件 {event_key}，请深入扩展其细节。上下文：{extra_context}"
        }
        template = templates.get(template_key, "")
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"构建Prompt缺少参数: {e}")
            return template
    
    def generate_world_history(self, world_params: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("开始生成世界历史")
        try:
            prompt = self._build_prompt("world_history",
                                        world_type=world_params.get("world_type", "奇幻"),
                                        magic_system=world_params.get("magic_system", "元素魔法"),
                                        initial_era=world_params.get("initial_era", "创世纪元"))
            raw_text = self._call_model(prompt)
            # 简单解析：实际应结构化提取（骨架暂返回原始文本和模拟结构）
            result = {
                "raw_output": raw_text,
                "eras": [{"name": "示例纪元", "description": "由模型生成"}],
                "events": [{"id": "event_1", "summary": "示例事件"}],
                "timeline": {"start_year": 0, "nodes": []}
            }
            logger.info("世界历史生成完成")
            return result
        except Exception as e:
            logger.error(f"世界历史生成失败: {e}", exc_info=True)
            # 返回基础错误结构
            return {"error": str(e)}
    
    def expand_event(self, event_key: str, extra_context: Optional[Dict] = None) -> Dict:
        logger.info(f"扩展事件: {event_key}")
        try:
            extra = extra_context or {}
            prompt = self._build_prompt("event_expand", event_key=event_key, extra_context=extra)
            raw_text = self._call_model(prompt)
            result = {
                "event_key": event_key,
                "expanded_text": raw_text,
                "details": {}
            }
            logger.info("事件扩展完成")
            return result
        except Exception as e:
            logger.error(f"扩展事件失败: {e}", exc_info=True)
            return {"error": str(e)}

# -----------------------------------------------------------------------------
# 生成器工厂（简单可插拔机制）
# -----------------------------------------------------------------------------
_generator_registry = {
    "llm": LLMHistoryGenerator,
    # 未来可以注册其他生成器，如基于规则、模板等
}

def get_history_generator(generator_type: str = "llm", config: Optional[ConfigLoader] = None) -> BaseHistoryGenerator:
    """
    根据类型获取历史生成器实例。
    支持运行时替换，实现可插拔。
    """
    generator_class = _generator_registry.get(generator_type)
    if generator_class is None:
        logger.error(f"未找到历史生成器类型: {generator_type}，回退到 LLM")
        generator_class = LLMHistoryGenerator
    return generator_class(config=config or _config)

# -----------------------------------------------------------------------------
# 自测（仅在直接执行本文件时运行）
# -----------------------------------------------------------------------------
def _self_test():
    """简单的自检，测试基本功能"""
    logging.basicConfig(level=logging.DEBUG)
    logger.info("=" * 40)
    logger.info("开始历史生成模块自测")
    # 使用默认生成器
    gen = get_history_generator()
    world = {
        "world_type": "仙侠",
        "magic_system": "灵力修炼，境界分明",
        "initial_era": "混沌纪元"
    }
    history = gen.generate_world_history(world)
    logger.info(f"历史生成结果: {history}")
    
    # 扩展事件
    expanded = gen.expand_event("event_1", {"extra": "测试"})
    logger.info(f"事件扩展结果: {expanded}")
    
    # 测试配置切换（若存在不同配置）
    test_gen2 = get_history_generator("llm")
    assert isinstance(test_gen2, LLMHistoryGenerator)
    logger.info("自测通过")

if __name__ == "__main__":
    _self_test()