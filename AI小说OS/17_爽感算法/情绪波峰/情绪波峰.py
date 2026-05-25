"""情绪波峰检测模块
层: 17_爽感算法
依赖: 无外部模块，依赖日志配置
被调用: 爽感分析流程，用于识别文本中的情绪高峰点
职责: 根据情绪强度序列，检测并标记波峰位置，提供峰值强度和上下文信息
可插拔: 通过配置参数调整检测策略，支持替换为不同的波峰检测算法
"""
import logging
import json

class EmotionPeakDetector:
    """情绪波峰检测器，可插拔的波峰算法组件"""
    
    def __init__(self, config: dict = None):
        """
        初始化检测器，加载配置并设置日志
        Args:
            config: 配置字典，包含阈值、窗口、平滑等参数
        """
        self.logger = logging.getLogger("EmotionPeakDetector")
        self.config = config or {}
        # 默认配置
        self.default_config = {
            "peak_threshold": 0.7,       # 波峰最小强度阈值
            "min_distance": 3,           # 波峰最小间隔（字符/句子距离）
            "window_size": 5,            # 滑动窗口大小
            "smooth_method": "average",  # 平滑方式：average/median/none
            "prominence_ratio": 0.3      # 突出度相对前后谷底的比例
        }
        self._apply_config()
        self.logger.info("EmotionPeakDetector initialized with config: %s", 
                        json.dumps(self.config, ensure_ascii=False))
    
    def _apply_config(self):
        """将用户配置与默认配置合并，并更新实例属性"""
        merged = self.default_config.copy()
        merged.update(self.config)
        self.peak_threshold = merged["peak_threshold"]
        self.min_distance = merged["min_distance"]
        self.window_size = merged["window_size"]
        self.smooth_method = merged["smooth_method"]
        self.prominence_ratio = merged["prominence_ratio"]
    
    def detect_peaks(self, text: str, emotion_scores: list) -> list:
        """
        检测情绪波峰
        Args:
            text: 输入文本
            emotion_scores: 每个文本单元的情绪强度分数列表，与文本单元对应
        Returns:
            list of dict: 波峰信息列表，每个元素包含 position, intensity, context, prominence 等
        """
        self.logger.debug("Detecting peaks for text length %d, scores count %d", len(text), len(emotion_scores))
        # TODO: 实现具体的波峰检测算法
        # 骨架实现：返回空列表
        peak_results = []
        # 生产级实现将包含：
        # 1. 预处理情绪序列（平滑等）
        # 2. 识别局部极大值
        # 3. 过滤低阈值、过近的波峰
        # 4. 计算突出度和上下文
        # 5. 返回结构化结果
        self.logger.info("Peak detection completed, found %d peaks", len(peak_results))
        return peak_results
    
    def reload_config(self, new_config: dict):
        """热更新配置，无需重启"""
        self.config.update(new_config)
        self._apply_config()
        self.logger.info("Configuration reloaded")
    
    def get_config(self) -> dict:
        """返回当前配置"""
        return {
            "peak_threshold": self.peak_threshold,
            "min_distance": self.min_distance,
            "window_size": self.window_size,
            "smooth_method": self.smooth_method,
            "prominence_ratio": self.prominence_ratio
        }

# 自测代码
if __name__ == "__main__":
    # 配置日志输出
    logging.basicConfig(level=logging.DEBUG, 
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # 测试实例
    detector = EmotionPeakDetector({
        "peak_threshold": 0.8,
        "min_distance": 2
    })
    test_text = "测试文本，用于情绪波峰检测。"
    test_scores = [0.1, 0.2, 0.9, 0.8, 0.3, 0.2, 0.85, 0.75, 0.2]
    peaks = detector.detect_peaks(test_text, test_scores)
    print("检测到的波峰:", peaks)
    # 测试热更新
    detector.reload_config({"peak_threshold": 0.6})
    peaks2 = detector.detect_peaks(test_text, test_scores)
    print("降低阈值后波峰:", peaks2)