"""
重复检测模块
负责检测小说内容中是否存在重复段落或高度相似内容。
可插拔设计，支持配置化调整检测阈值和策略。
"""

import logging
from typing import List, Tuple, Optional, Callable, Dict
from ..config import config  # 项目统一配置模块
from ..utils.logger import get_logger  # 项目统一日志模块

# 获取模块专用日志器
logger = get_logger(__name__)


class DuplicateDetector:
    """
    重复检测器，负责检测文本中的重复内容。
    可配置相似度算法、窗口大小、阈值等。
    支持运行时注册新算法，实现可插拔扩展。
    """
    def __init__(self, config_section: str = "duplicate_detection"):
        """
        初始化检测器，从配置中加载参数。
        :param config_section: 配置文件中对应的节名称
        """
        self.config = config.get_section(config_section)
        self.threshold: float = self.config.get("similarity_threshold", 0.85)
        self.window_size: int = self.config.get("window_size", 100)
        self.algorithm: str = self.config.get("algorithm", "jaccard")  # 默认杰卡德相似度
        # 可插拔算法注册表
        self._algorithms: Dict[str, Callable] = {
            "jaccard": self._detect_jaccard,
            "minhash": self._detect_minhash,
        }
        logger.info(
            f"DuplicateDetector initialized: threshold={self.threshold}, "
            f"window_size={self.window_size}, algorithm={self.algorithm}"
        )

    def detect(self, text: str) -> List[Tuple[int, int, float]]:
        """
        检测文本中的重复段落，返回重复区域及相似度。
        :param text: 待检测的完整文本内容
        :return: 重复对列表，每项为 (start_pos, end_pos, similarity)
        """
        logger.debug(f"Detecting duplicates in text of length {len(text)}...")
        if not text:
            logger.warning("Empty text provided, no duplicates possible.")
            return []

        detect_func = self._algorithms.get(self.algorithm)
        if detect_func is None:
            logger.error(f"Unknown algorithm: {self.algorithm}, falling back to jaccard.")
            detect_func = self._detect_jaccard

        try:
            duplicates = detect_func(text)
            logger.info(f"Detection completed. Found {len(duplicates)} duplicate pairs.")
            return duplicates
        except Exception as e:
            logger.exception(f"Error during duplicate detection: {e}")
            return []

    def _detect_jaccard(self, text: str) -> List[Tuple[int, int, float]]:
        """基于杰卡德相似度的重复检测（骨架实现）"""
        # 实际实现需要滑动窗口、计算集合相似度并聚合
        # 这里返回空列表作为骨架
        return []

    def _detect_minhash(self, text: str) -> List[Tuple[int, int, float]]:
        """基于MinHash的近似重复检测（骨架实现）"""
        # 实际实现需要 LSH 等
        return []

    def register_algorithm(self, name: str, func: Callable[[str], List[Tuple[int, int, float]]]):
        """
        注册新的检测算法，实现热插拔扩展。
        :param name: 算法名称
        :param func: 算法函数，接受文本，返回重复对列表
        """
        if name in self._algorithms:
            logger.warning(f"Algorithm '{name}' already exists, overwriting.")
        self._algorithms[name] = func
        logger.info(f"Registered new duplicate detection algorithm: {name}")

    def unregister_algorithm(self, name: str):
        """移除算法（默认算法不可移除）"""
        if name in ("jaccard", "minhash"):
            logger.warning(f"Cannot unregister built-in algorithm: {name}")
            return
        if name in self._algorithms:
            del self._algorithms[name]
            logger.info(f"Unregistered algorithm: {name}")


# 自测代码
if __name__ == "__main__":
    # 配置基础日志输出
    logging.basicConfig(level=logging.DEBUG)

    # 模拟配置模块
    class MockConfig:
        def get_section(self, section):
            return {
                "similarity_threshold": 0.9,
                "window_size": 50,
                "algorithm": "jaccard"
            }
    config = MockConfig()

    # 实例化检测器
    detector = DuplicateDetector()

    # 测试正常调用
    test_text = "这是一个测试文本，用于检测重复内容。这是一个测试文本，用于检测重复内容。"
    result = detector.detect(test_text)
    print(f"检测结果: {result}")

    # 测试注册新算法
    def custom_algo(text: str) -> List[Tuple[int, int, float]]:
        return [(0, len(text), 1.0)]

    detector.register_algorithm("custom", custom_algo)
    detector.algorithm = "custom"
    result2 = detector.detect(test_text)
    print(f"Custom算法结果: {result2}")

    # 测试移除算法
    detector.unregister_algorithm("custom")
    detector.algorithm = "custom"  # 触发回退
    result3 = detector.detect(test_text)
    print(f"移除后检测结果: {result3}")

    print("自测完成")