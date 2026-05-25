"""
AI味检测模块 (AI Flavor Detector)
路径: 22_审核安全/AI味检测/AI味检测.py
层级: 审核安全层
依赖: 无外部模块依赖（仅依赖Python标准库，或可插拔的检测器接口）
被调用: 审核流程、内容发布前检查等
解决: 识别文本是否由AI生成，给出AI味得分及风险等级

本模块遵循可插拔设计，支持配置化阈值、日志记录，提供基础骨架与自测。
"""

import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod
import json
import os

# 配置日志
logger = logging.getLogger(__name__)


class AIFlavorDetector(ABC):
    """AI味检测器抽象基类，所有具体检测算法均需实现此接口"""
    
    @abstractmethod
    def detect(self, text: str) -> Dict[str, Any]:
        """
        检测文本AI痕迹
        Args:
            text: 待检测文本
        Returns:
            检测结果字典，包含 'score' (float, 0-1表示AI可能性), 
            'level' (str: 'low', 'medium', 'high'), 'details' (Any)
        """
        pass


class BaseConfigurableDetector(AIFlavorDetector):
    """带配置支持的基础检测器抽象类"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self._validate_config()
        logger.info(f"{self.__class__.__name__} initialized with config: {self.config}")
    
    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """默认配置，子类可覆盖"""
        return {
            "threshold_low": 0.3,
            "threshold_high": 0.7,
            "enabled": True
        }
    
    def _validate_config(self):
        """验证配置完整性"""
        required_keys = ["threshold_low", "threshold_high", "enabled"]
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required config key: {key}")
    
    def _score_to_level(self, score: float) -> str:
        """根据分数映射等级"""
        if score >= self.config["threshold_high"]:
            return "high"
        elif score >= self.config["threshold_low"]:
            return "medium"
        else:
            return "low"


class SimpleHeuristicDetector(BaseConfigurableDetector):
    """基于简单启发式规则的示例检测器（骨架）"""
    
    def detect(self, text: str) -> Dict[str, Any]:
        """
        示例检测逻辑，实际应替换为真正的AI味检测算法
        """
        if not self.config.get("enabled", True):
            return {"score": 0.0, "level": "low", "details": "detector disabled"}
        
        # TODO: 真实检测逻辑，此处仅返回固定示例
        logger.debug(f"Detecting AI flavor for text length {len(text)}")
        # 占位分数计算
        score = 0.5  # 示例中值
        level = self._score_to_level(score)
        return {
            "score": score,
            "level": level,
            "details": {
                "word_count": len(text.split()),
                "placeholder": True
            }
        }


class DetectorRegistry:
    """检测器注册表，实现插件式管理"""
    
    _detectors: Dict[str, type] = {}
    
    @classmethod
    def register(cls, name: str, detector_cls: type):
        """注册一个检测器类"""
        if not issubclass(detector_cls, AIFlavorDetector):
            raise TypeError(f"Detector {name} must be a subclass of AIFlavorDetector")
        cls._detectors[name] = detector_cls
        logger.info(f"AI flavor detector '{name}' registered")
    
    @classmethod
    def create(cls, name: str, config: Optional[Dict[str, Any]] = None) -> AIFlavorDetector:
        """根据名称创建检测器实例"""
        if name not in cls._detectors:
            raise ValueError(f"Unknown detector: {name}")
        return cls._detectors[name](config)
    
    @classmethod
    def list_detectors(cls) -> list:
        """列出所有已注册的检测器"""
        return list(cls._detectors.keys())


# 默认注册内置检测器
DetectorRegistry.register("simple_heuristic", SimpleHeuristicDetector)


def load_config_from_file(filepath: str) -> Dict[str, Any]:
    """从JSON文件加载配置"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"Loaded config from {filepath}")
        return config
    except Exception as e:
        logger.error(f"Failed to load config from {filepath}: {e}")
        return {}


def detect_ai_flavor(text: str, detector_name: str = "simple_heuristic", 
                     config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    公共接口：使用指定检测器进行AI味检测
    Args:
        text: 待检测文本
        detector_name: 检测器名称（注册名）
        config: 检测器配置（可选）
    Returns:
        检测结果
    """
    try:
        detector = DetectorRegistry.create(detector_name, config)
        result = detector.detect(text)
        logger.info(f"AI flavor detection completed: {result['level']} (score: {result['score']})")
        return result
    except Exception as e:
        logger.error(f"AI flavor detection failed: {e}", exc_info=True)
        return {"score": -1, "level": "error", "details": str(e)}


# 自测代码
if __name__ == "__main__":
    # 配置基础日志输出，便于自测
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 测试简单检测器
    sample_text = "这是一个测试文本，用于检测AI生成的可能性。"
    print("=== AI味检测自测 ===")
    result = detect_ai_flavor(sample_text)
    print(f"Result: {json.dumps(result, ensure_ascii=False, indent=2)}")
    
    # 测试注册与创建
    print("\nRegistered detectors:", DetectorRegistry.list_detectors())
    custom_detector = DetectorRegistry.create("simple_heuristic", {"threshold_low": 0.5, "threshold_high": 0.9, "enabled": True})
    result2 = custom_detector.detect("另一段示例文本。")
    print(f"Custom detector result: {json.dumps(result2, ensure_ascii=False, indent=2)}")
    
    # 测试禁用检测器
    disabled_config = {"threshold_low": 0.3, "threshold_high": 0.7, "enabled": False}
    result3 = detect_ai_flavor("随便写点什么", config=disabled_config)
    print(f"Disabled detector result: {json.dumps(result3, ensure_ascii=False, indent=2)}")