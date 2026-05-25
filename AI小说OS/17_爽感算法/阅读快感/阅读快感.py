"""
Module: 阅读快感分析器 (Reading Pleasure Analyzer)
Layer: 17_爽感算法
Responsibility: 分析文本阅读快感指标，如节奏、爽点密度等
Dependencies: 配置文件、日志系统
Interfaces: 可插拔，通过继承 ReadingPleasureAnalyzer 基类扩展
"""

import logging
from typing import Dict, Any, Optional

# 配置日志
logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_CONFIG = {
    "rhythm_weight": 0.3,          # 节奏权重
    "climax_density_weight": 0.4,  # 爽点密度权重
    "smoothness_weight": 0.3,      # 流畅度权重
    "min_threshold": 0.2,          # 最小有效阈值
}


class ReadingPleasureAnalyzer:
    """
    阅读快感分析器基类，所有具体实现必须继承此类。
    定义了可插拔接口。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化分析器，加载配置。
        
        Args:
            config: 自定义配置字典，若为None则使用默认配置
        """
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        logger.info(f"ReadingPleasureAnalyzer initialized with config: {self.config}")

    def analyze(self, text: str) -> Dict[str, float]:
        """
        分析文本的阅读快感指标。
        
        Args:
            text: 输入文本（章节或段落）
        
        Returns:
            包含各维度得分及综合得分的字典，例如：
            {
                "rhythm_score": float,
                "climax_density_score": float,
                "smoothness_score": float,
                "overall_pleasure": float
            }
        """
        logger.debug(f"Analyzing text of length {len(text)}")
        # 基础实现返回默认值，子类需重写
        return {
            "rhythm_score": 0.0,
            "climax_density_score": 0.0,
            "smoothness_score": 0.0,
            "overall_pleasure": 0.0
        }

    def update_config(self, new_config: Dict[str, Any]):
        """热更新配置"""
        self.config.update(new_config)
        logger.info(f"Configuration updated: {new_config}")

    def reset_config(self):
        """重置为默认配置"""
        self.config = DEFAULT_CONFIG.copy()
        logger.info("Configuration reset to defaults.")


class DefaultReadingPleasureAnalyzer(ReadingPleasureAnalyzer):
    """
    默认的阅读快感分析器实现，使用简单的统计方法。
    可作为模板或测试用。
    """

    def analyze(self, text: str) -> Dict[str, float]:
        """
        简单实现：根据文本长度、标点密度等粗略估算。
        """
        logger.debug(f"Default analyze on text: {text[:50]}...")
        # 示例算法：节奏得分（句长变化）、爽点密度（感叹号问号密度）等
        sentences = [s.strip() for s in text.replace('!', '.').replace('?', '.').split('.') if s.strip()]
        num_sentences = len(sentences)
        if num_sentences == 0:
            return {
                "rhythm_score": 0.0,
                "climax_density_score": 0.0,
                "smoothness_score": 0.0,
                "overall_pleasure": 0.0
            }

        # 节奏简单以句长方差衡量
        avg_len = sum(len(s) for s in sentences) / num_sentences
        var_len = sum((len(s) - avg_len) ** 2 for s in sentences) / num_sentences
        rhythm_score = min(1.0, var_len / 100) * self.config["rhythm_weight"]

        # 爽点密度：感叹号、问号数量比例
        climax_chars = text.count('!') + text.count('？') + text.count('?')
        density = climax_chars / len(text) if len(text) > 0 else 0
        climax_density_score = min(1.0, density * 10) * self.config["climax_density_weight"]

        # 流畅度假定为1减去重复字词比例
        words = text.split()
        unique_ratio = len(set(words)) / len(words) if words else 0
        smoothness_score = unique_ratio * self.config["smoothness_weight"]

        overall = max(0.0, rhythm_score + climax_density_score + smoothness_score)
        if overall < self.config.get("min_threshold", 0.2):
            overall = 0.0

        return {
            "rhythm_score": rhythm_score,
            "climax_density_score": climax_density_score,
            "smoothness_score": smoothness_score,
            "overall_pleasure": overall
        }


# 自测部分
if __name__ == "__main__":
    # 配置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 测试默认分析器
    analyzer = DefaultReadingPleasureAnalyzer()
    sample_text = "这是一个测试句子！真的很爽吗？确实很爽。再来一句！超级爽！"
    result = analyzer.analyze(sample_text)
    print("Analysis result:", result)

    # 测试热更新配置
    analyzer.update_config({"rhythm_weight": 0.5})
    result2 = analyzer.analyze(sample_text)
    print("After config update:", result2)

    # 测试重置
    analyzer.reset_config()
    result3 = analyzer.analyze(s