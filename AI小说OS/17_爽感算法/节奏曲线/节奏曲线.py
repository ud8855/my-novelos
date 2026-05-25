""" 
节奏曲线模块 (Rhythm Curve Module) 
所属层级: 17_爽感算法 
依赖: 日志模块, 配置系统(通过依赖注入), 核心数据结构定义(协议)
被调用者: 爽感评估引擎, 节奏调整控制器 
解决问题: 根据文本事件流、情感强度、冲突密度等指标，生成小说的节奏曲线，评估节奏质量，提供优化建议。
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


# -----------------------------------------------------------------------------
# 核心数据结构定义
# -----------------------------------------------------------------------------

@dataclass
class RhythmPoint:
    """节奏曲线上的一个采样点"""
    position: int  # 文本位置（如章节序号、字数偏移等）
    intensity: float  # 当前点的强度值 (0~1)
    event_type: str = ""  # 事件类型标识
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RhythmConfig:
    """节奏分析配置"""
    window_size: int = 500  # 滑动窗口大小（字数或句子数）
    smooth_factor: float = 0.3  # 曲线平滑系数 (0~1)
    climax_threshold: float = 0.8  # 高潮判定阈值
    trough_threshold: float = 0.3  # 低谷判定阈值
    # 可扩展其他参数
    extra_params: Dict[str, Any] = field(default_factory=dict)


# -----------------------------------------------------------------------------
# 抽象基类 / 协议
# -----------------------------------------------------------------------------

class BaseRhythmCurveAnalyzer(ABC):
    """节奏曲线分析器抽象基类，定义统一接口 (可插拔)"""

    def __init__(self, config: RhythmConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self._validate_config()

    def _validate_config(self):
        """校验配置合法性"""
        if not (0 < self.config.window_size):
            raise ValueError("window_size must be positive")
        if not (0 <= self.config.smooth_factor <= 1):
            raise ValueError("smooth_factor must be between 0 and 1")
        if not (0 <= self.config.climax_threshold <= 1):
            raise ValueError("climax_threshold must be between 0 and 1")
        if not (0 <= self.config.trough_threshold <= 1):
            raise ValueError("trough_threshold must be between 0 and 1")
        if self.config.climax_threshold <= self.config.trough_threshold:
            raise ValueError("climax_threshold must be greater than trough_threshold")

    @abstractmethod
    def generate_curve(self, events: List[Dict]) -> List[RhythmPoint]:
        """
        根据输入事件流生成节奏曲线
        Args:
            events: 事件列表，每个事件包含位置、强度等信息
        Returns:
            节奏点列表
        """
        ...

    @abstractmethod
    def analyze_rhythm(self, curve: List[RhythmPoint]) -> Dict[str, Any]:
        """
        分析节奏曲线，返回节奏评估报告
        Args:
            curve: 节奏曲线
        Returns:
            包含节奏评分、高低潮区间、改进建议等的字典
        """
        ...

    def get_default_config(self) -> RhythmConfig:
        """获取默认配置（方便插件发现）"""
        return RhythmConfig()

    def __repr__(self):
        return f"<{self.__class__.__name__}(config={self.config})>"


# -----------------------------------------------------------------------------
# 默认实现
# -----------------------------------------------------------------------------

class DefaultRhythmCurveAnalyzer(BaseRhythmCurveAnalyzer):
    """
    基于滑动窗口和平滑处理的默认节奏曲线分析器
    算法简述：
        1. 将事件列表按位置排序
        2. 计算每个窗口内的事件强度均值
        3. 使用指数移动平均平滑曲线
        4. 识别高潮区间与低谷区间
    """

    def generate_curve(self, events: List[Dict]) -> List[RhythmPoint]:
        self.logger.info(f"开始生成节奏曲线，事件数量: {len(events)}")
        if not events:
            return []

        # 提取有效事件并排序
        points = []
        for ev in events:
            pos = ev.get("position", 0)
            intensity = float(ev.get("intensity", 0.5))
            points.append((pos, intensity))
        points.sort(key=lambda x: x[0])

        # 生成原始采样点
        curve = []
        max_pos = points[-1][0]
        stride = max(1, self.config.window_size // 2)
        for start in range(0, max_pos + 1, stride):
            end = start + self.config.window_size
            window_intensities = [p[1] for p in points if start <= p[0] < end]
            if window_intensities:
                avg_intensity = sum(window_intensities) / len(window_intensities)
            else:
                avg_intensity = 0.5  # 默认强度
            curve.append(RhythmPoint(position=start + self.config.window_size//2,
                                     intensity=avg_intensity))
        self.logger.debug(f"原始采样点数量: {len(curve)}")

        # 平滑处理 (指数移动平均)
        smoothed = self._smooth_curve(curve)
        self.logger.info("节奏曲线生成完成")
        return smoothed

    def analyze_rhythm(self, curve: List[RhythmPoint]) -> Dict[str, Any]:
        self.logger.info("开始分析节奏曲线")
        if not curve:
            return {
                "climax_regions": [],
                "trough_regions": [],
                "overall_rhythm_score": 0.5,
                "suggestions": ["节奏曲线为空，请检查输入事件"]
            }

        climax_regions = self._find_regions(curve, above=self.config.climax_threshold)
        trough_regions = self._find_regions(curve, below=self.config.trough_threshold)
        variance = self._calculate_variance(curve)
        # 基础评分：高潮区域占比与方差结合
        climax_coverage = sum(r[1]-r[0] for r in climax_regions) / curve[-1].position if curve[-1].position > 0 else 0
        score = 0.6 * (climax_coverage / 0.2) + 0.4 * (min(variance / 0.1, 1.0))
        score = max(0.0, min(1.0, score))

        suggestions = []
        if score < 0.4:
            suggestions.append("整体节奏过于平缓，建议增加冲突强度变化")
        if len(climax_regions) < 1:
            suggestions.append("未检测到明显高潮段落，考虑强化关键事件")
        if len(trough_regions) < 1:
            suggestions.append("未检测到明显低谷，考虑增加缓释段落")
        elif len(trough_regions) > 3:
            suggestions.append("低谷段落过多，可能造成读者疲劳，适当缩减")

        report = {
            "climax_regions": climax_regions,
            "trough_regions": trough_regions,
            "variance": variance,
            "overall_rhythm_score": score,
            "suggestions": suggestions
        }
        self.logger.info(f"节奏分析完成，评分: {score:.2f}")
        return report

    def _smooth_curve(self, curve: List[RhythmPoint]) -> List[RhythmPoint]:
        """指数移动平均平滑"""
        alpha = self.config.smooth_factor
        smoothed = []
        prev = None
        for pt in curve:
            if prev is None:
                smoothed.append(RhythmPoint(position=pt.position, intensity=pt.intensity))
                prev = pt.intensity
            else:
                new_intensity = alpha * pt.intensity + (1 - alpha) * prev
                smoothed.append(RhythmPoint(position=pt.position, intensity=new_intensity))
                prev = new_intensity
        return smoothed

    @staticmethod
    def _find_regions(curve: List[RhythmPoint], above: float = None, below: float = None) -> List[Tuple[int, int]]:
        """找出连续高于/低于阈值的位置区间"""
        regions = []
        in_region = False
        start_pos = 0
        for pt in curve:
            condition = False
            if above is not None and pt.intensity >= above:
                condition = True
            if below is not None and pt.intensity <= below:
                condition = True
            if condition and not in_region:
                start_pos = pt.position
                in_region = True
            elif not condition and in_region:
                regions.append((start_pos, pt.position))
                in_region = False
        if in_region:
            regions.append((start_pos, curve[-1].position))
        return regions

    @staticmethod
    def _calculate_variance(curve: List[RhythmPoint]) -> float:
        """计算强度方差"""
        if not curve:
            return 0.0
        mean = sum(p.intensity for p in curve) / len(curve)
        return sum((p.intensity - mean) ** 2 for p in curve) / len(curve)


# -----------------------------------------------------------------------------
# 自测代码
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("=== 节奏曲线模块自测 ===")
    # 构造模拟事件数据
    mock_events = [
        {"position": 100, "intensity": 0.2},
        {"position": 400, "intensity": 0.4},
        {"position": 700, "intensity": 0.9},
        {"position": 1200, "intensity": 0.6},
        {"position": 1500, "intensity": 0.3},
        {"position": 1800, "intensity": 0.1},
        {"position": 2200, "intensity": 0.85},
    ]
    config = RhythmConfig(window_size=800, smooth_factor=0.2)
    analyzer = DefaultRhythmCurveAnalyzer(config)

    # 生成曲线
    curve = analyzer.generate_curve(mock_events)
    print(f"生成节奏点数量: {len(curve)}")
    for i, pt in enumerate(curve[:5]):
        print(f"  点{i}: pos={pt.position}, intensity={pt.intensity:.2f}")

    # 分析
    report = analyzer.analyze_rhythm(curve)
    print(f"\n节奏评分: {report['overall_rhythm_score']:.2f}")
    print(f"高潮区间: {report['climax_regions']}")
    print(f"低谷区间: {report['trough_regions']}")
    print(f"建议: {report['suggestions']}")

    print