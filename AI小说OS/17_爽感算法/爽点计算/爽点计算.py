import abc
import logging
import os
import sys
from typing import Dict, Any, Optional

# 设置模块级日志
logger = logging.getLogger(__name__)

# 配置化：从环境变量或配置文件加载参数，提供默认值
# 假设配置文件位于上级目录或项目根目录下的 config/ 中
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../../config/pleasure_calc.ini')
CALCULATOR_TYPE = os.environ.get('PLEASURE_CALC_TYPE', 'default')  # 环境变量可覆盖


class PleasurePointCalculator(abc.ABC):
    """爽点计算抽象基类，定义统一接口"""
    
    @abc.abstractmethod
    def calculate(self, text: str, context: Optional[Dict[str, Any]] = None) -> float:
        """
        计算给定文本的爽点值
        
        Args:
            text: 待分析的小说片段或句子
            context: 可选的上下文信息（如人物状态、情节阶段等）
        
        Returns:
            爽点评分，通常为0-1之间的浮点数，越高代表越爽
        """
        pass
    
    @abc.abstractmethod
    def name(self) -> str:
        """返回计算器唯一名称，用于日志和配置区分"""
        pass


class DefaultPleasurePointCalculator(PleasurePointCalculator):
    """
    默认爽点计算器，基于简单规则（如高频情绪词、转折密度等）
    此处仅为骨架，后续由算法工程师填充具体逻辑
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._load_default_rules()
        logger.info(f"Initialized DefaultPleasurePointCalculator with config: {self.config}")
    
    def _load_default_rules(self):
        # 从配置文件加载规则权重，如果未提供则使用硬编码默认值
        # 示例：情绪词list，强度映射表
        self.emotion_words = self.config.get('emotion_words', ['爽', '惊', '爆发', '逆袭'])
        self.emotion_weights = self.config.get('emotion_weights', {'爽': 0.8, '惊': 0.6, '爆发': 0.9, '逆袭': 0.95})
    
    def calculate(self, text: str, context: Optional[Dict[str, Any]] = None) -> float:
        logger.debug(f"Calculating pleasure for text: {text[:30]}...")
        # 简易实现：检测情绪词并累加权重，归一化
        score = 0.0
        for word, weight in self.emotion_weights.items():
            count = text.count(word)
            score += count * weight
        # 附加上下文调整（如果提供）
        if context:
            # 如：高潮场景加成
            if context.get('is_climax'):
                score *= 1.2
        # 归一化到0-1
        normalized = min(1.0, score / max(len(text.split()), 1))
        logger.info(f"Pleasure score: {normalized:.3f}")
        return normalized
    
    def name(self) -> str:
        return "default"


class AdvancedPleasurePointCalculator(PleasurePointCalculator):
    """
    高级爽点计算器，预留接口，可接入模型或复杂NLP处理
    此处仅返回固定值，表明未实现
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        logger.warning("AdvancedPleasurePointCalculator is not fully implemented yet.")
    
    def calculate(self, text: str, context: Optional[Dict[str, Any]] = None) -> float:
        raise NotImplementedError("Advanced calculator requires model integration. Please implement via 20_模型协同/")
    
    def name(self) -> str:
        return "advanced"


# 计算器注册表，支持热插拔
_CALCULATOR_REGISTRY: Dict[str, PleasurePointCalculator] = {}


def register_calculator(calc: PleasurePointCalculator):
    """注册新的爽点计算器"""
    _CALCULATOR_REGISTRY[calc.name()] = calc
    logger.info(f"Registered pleasure calculator: {calc.name()}")


def get_calculator(name: Optional[str] = None) -> PleasurePointCalculator:
    """
    根据名称获取计算器实例，默认从配置环境变量获取。
    若未注册则尝试自动创建并注册。
    """
    name = name or CALCULATOR_TYPE
    if name in _CALCULATOR_REGISTRY:
        return _CALCULATOR_REGISTRY[name]
    # 懒加载：根据名称实例化对应的类
    # 这里映射类名
    class_map = {
        'default': DefaultPleasurePointCalculator,
        'advanced': AdvancedPleasurePointCalculator
    }
    cls = class_map.get(name)
    if not cls:
        raise ValueError(f"Unknown pleasure calculator type: {name}")
    # 初始化可能需要加载配置，此处从统一配置读取（暂略）
    instance = cls()
    register_calculator(instance)
    return instance


# 预注册默认计算器
register_calculator(DefaultPleasurePointCalculator())


def _self_test():
    """模块自测，检验基本功能"""
    logging.basicConfig(level=logging.DEBUG)
    test_text = "主角一声怒吼，气势瞬间爆发，引得众人震惊无比，这逆袭简直太爽了！"
    calc = get_calculator()
    score = calc.calculate(test_text, context={'is_climax': True})
    print(f"Test score: {score}")
    
    # 测试工厂
    calc2 = get_calculator('default')
    assert calc2.name() == 'default'
    print("Self test passed.")


if __name__ == '__main__':
    _self_test()