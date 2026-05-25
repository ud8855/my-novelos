# 22_审核安全/色情检测/色情检测.py
# 色情内容检测模块 - 可插拔的检测器基类及默认实现

import logging
import abc
from typing import Dict, Any, Optional

# 配置模块日志
logger = logging.getLogger(__name__)


class PornographyDetector(abc.ABC):
    """色情内容检测器抽象基类，所有具体检测器必须实现 detect 方法"""
    
    @abc.abstractmethod
    def detect(self, text: str) -> Dict[str, Any]:
        """
        检测文本中是否包含色情内容
        
        Args:
            text: 待检测的文本字符串
            
        Returns:
            字典，包含以下字段：
                - is_pornographic (bool): 是否判定为色情内容
                - confidence (float): 模型给出的置信度分数，0~1 之间
                - detail (str): 检测过程的详细信息（用于日志或调试）
        """
        pass


class DefaultPornographyDetector(PornographyDetector):
    """
    默认色情检测器，通过可注入的模型客户端实现内容分析。
    模型客户端需具备 analyze(text) -> dict 方法，用于调用实际 AI 服务。
    """
    
    def __init__(self, config: Dict[str, Any], model_client: Optional[Any] = None):
        """
        初始化检测器
        
        Args:
            config: 配置字典，例如 {'threshold': 0.7}
            model_client: AI 模型客户端实例，具有 analyze 方法。若为 None，则使用内置 MockModelClient（仅用于测试）
        """
        self.config = config
        self.threshold = config.get('threshold', 0.5)
        self.model_client = model_client if model_client else MockModelClient()
        logger.info(f"DefaultPornographyDetector initialized with threshold={self.threshold}")
        
    def detect(self, text: str) -> Dict[str, Any]:
        """
        执行色情内容检测
        
        Args:
            text: 待检测文本
            
        Returns:
            检测结果字典
        """
        logger.debug(f"Detecting pornography in text: {text[:50]}...")
        try:
            # 调用注入的模型客户端进行分析
            result = self.model_client.analyze(text)
            score = result.get('porn_score', 0.0)
            is_porn = score >= self.threshold
            detection_result = {
                'is_pornographic': is_porn,
                'confidence': score,
                'detail': f"Model score: {score}, threshold: {self.threshold}"
            }
            logger.debug(f"Detection result: {detection_result}")
            return detection_result
        except Exception as e:
            logger.error(f"Error during pornography detection: {e}", exc_info=True)
            # 发生异常时采用保守策略：视为不通过（可根据业务需求配置）
            return {
                'is_pornographic': False,
                'confidence': 0.0,
                'detail': f"Detection failed: {str(e)}"
            }


class MockModelClient:
    """
    模拟的模型客户端，用于开发调试阶段。
    生产环境中必须替换为由 21_API模型/ 提供的真实模型调用实现。
    """
    
    def analyze(self, text: str) -> Dict[str