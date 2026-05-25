"""
疲劳检测模块：检测读者在阅读过程中的疲劳状态。
用于模拟读者可能因疲劳而暂停或跳过内容。
此模块可插拔，通过配置调整检测参数，并提供标准接口供其他系统调用。
"""

import logging
from configparser import ConfigParser
from pathlib import Path
from typing import Optional, Dict, Any

# 获取模块日志记录器
logger = logging.getLogger(__name__)

class FatigueDetector:
    """疲劳检测器，可插拔组件。

    支持通过配置文件调整阈值和权重参数。
    检测逻辑基于阅读时间、滚动和跳过事件等信号，
    输出0到1之间的疲劳指数，并根据阈值判断是否疲劳。
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化疲劳检测器，加载配置。

        参数:
            config_path: 配置文件路径，若为None则使用默认配置。
        """
        self.config = self._load_config(config_path)
        # 从配置读取阈值，若不存在则使用默认值0.7
        self.fatigue_threshold = self.config.getfloat('Fatigue', 'threshold', fallback=0.7)
        logger.info("FatigueDetector initialized with threshold=%f", self.fatigue_threshold)

    def _load_config(self, config_path: Optional[str]) -> ConfigParser:
        """
        加载配置文件，提供默认参数。

        默认包含：
            - fatigue.threshold: 疲劳判断阈值，默认0.7
            - fatigue.max_reading_time_minutes: 最大无疲劳阅读时长（分钟），默认60
            - fatigue.scroll_weight: 滚动事件在疲劳计算中的权重
            - fatigue.skip_weight: 跳过事件在疲劳计算中的权重

        参数:
            config_path: 外部配置文件路径。

        返回:
            ConfigParser对象，包含合并后的配置。
        """
        config = ConfigParser()
        # 预设默认配置
        config.read_dict({
            'Fatigue': {
                'threshold': '0.7',
                'max_reading_time_minutes': '60',
                'scroll_weight': '0.1',
                'skip_weight': '0.2'
            }
        })
        if config_path:
            # 读取外部配置文件，覆盖默认值
            config.read(config_path)
        return config

    def detect_fatigue(self, reading_time: float,
                       scroll_events: int = 0,
                       skip_events: int = 0,
                       other_signals: Optional[Dict[str, Any]] = None) -> float:
        """
        检测疲劳程度，返回一个0到1之间的浮点数，值越大表示越疲劳。

        参数:
            reading_time: 总阅读时间（分钟）
            scroll_events: 滚动次数
            skip_events: 跳过的段落/内容次数
            other_signals: 其他可选的信号字典，如停顿时间等

        返回:
            float: 疲劳指数，范围[0,1]
        """
        # 简化计算，仅作为骨架示例，未来可替换为更复杂的算法
        max_time = self.config.getfloat('Fatigue', 'max_reading_time_minutes', fallback=60.0)
        time_factor = min(reading_time / max_time, 1.0)

        scroll_weight = self.config.getfloat('Fatigue', 'scroll_weight', fallback=0.1)
        skip_weight = self.config.getfloat('Fatigue', 'skip_weight', fallback=0.2)

        # 使用线性组合计算疲劳指数，可根据需要调整
        fatigue = (time_factor * 0.6 +
                   (scroll_events * scroll_weight) +
                   (skip_events * skip_weight))

        # 确保值在0到1之间
        fatigue = max(0.0, min(fatigue, 1.0))

        logger.debug("detect_fatigue: reading_time=%.2f, scroll=%d, skip=%d, fatigue=%.3f",
                     reading_time, scroll_events, skip_events, fatigue)
        return fatigue

    def is_fatigued(self, reading_time: float,
                    scroll_events: int = 0,
                    skip_events: int = 0,
                    other_signals: Optional[Dict[str, Any]] = None) -> bool:
        """
        判断读者当前是否疲劳，基于detect_fatigue的结果与阈值比较。

        参数:
            reading_time: 总阅读时间（分钟）
            scroll_events: 滚动次数
            skip_events: 跳过的内容次数
            other_signals: 其他可选的信号字典

        返回:
            bool: 若疲劳指数 >= threshold则返回True
        """
        fatigue_level = self.detect_fatigue(reading_time, scroll_events, skip_events, other_signals)
        result = fatigue_level >= self.fatigue_threshold
        logger.debug("is_fatigued: level=%.3f, threshold=%.3f, result=%s",
                     fatigue_level, self.fatigue_threshold, result)
        return result


# 模块自测部分，只在直接运行该文件时执行
if __name__ == "__main__":
    # 设置日志输出到控制台，便于调试
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 使用默认配置创建检测器
    detector = FatigueDetector()
    # 测试检测疲劳
    test_reading_time = 45.0  # 分钟
    test_scroll = 5
    test_skip = 2
    fatigue = detector.detect_fatigue(test_reading_time, test_scroll, test_skip)
    is_fat = detector.is_fatigued(test_reading_time, test_scroll, test_skip)

    print(f"阅读{test_reading_time}分钟后，疲劳指数: {fatigue:.2f}")
    print(f"是否判定为疲劳: {is_fat}")

    # 测试修改配置后的行为（演示可配置性）
    custom_detector = FatigueDetector()
    custom_detector.fatigue_threshold = 0.5
    print(f"调整阈值后，相同数据是否疲劳: {custom_detector.is_fatigued(test_reading_time, test_scroll, test_skip)}")