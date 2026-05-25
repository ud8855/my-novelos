"""
17_爽感算法/爆点预测/爆点预测.py

爆点预测模块
- 职责：预测故事中的爆点（高潮/爽点）位置与强度
- 可插拔：通过接口实现，支持替换不同预测算法
- 配置化：所有参数可通过配置文件或初始化参数传入
- 日志记录：关键步骤和错误记录
- 自测：提供 self_test() 方法
"""
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path
from abc import ABC, abstractmethod

# 尝试从项目公共配置模块加载，若不存在则使用空实现
try:
    from novelos.config import load_config
except ImportError:
    def load_config(path):
        return {}

logger = logging.getLogger(__name__)


class BurstPointPredictor(ABC):
    """
    爆点预测器抽象基类
    定义了预测接口，所有实现必须遵循此接口以保证可插拔性
    """

    @abstractmethod
    def predict(self, text: str, context: Optional[Dict] = None) -> List[Dict]:
        """
        预测文本中的爆点
        :param text: 输入文本（章节或段落）
        :param context: 额外上下文信息
        :return: 爆点列表，每个爆点包含位置、强度、类型等
        """
        pass

    @abstractmethod
    def load_model(self, model_path: str):
        """
        加载预测模型
        """
        pass


class DefaultBurstPointPredictor(BurstPointPredictor):
    """
    默认爆点预测实现
    基于规则/统计的简单预测器（可替换为AI模型）
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化预测器
        :param config: 配置字典，如未提供则从默认配置文件加载
        """
        self.config = config or self._load_default_config()
        self._setup_logging()
        self.model_loaded = False
        self.model = None
        logger.info("爆点预测器初始化完成，配置: %s", self.config)

    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置"""
        config_path = Path(__file__).parent / "burst_point_config.json"
        if config_path.exists():
            return load_config(config_path)
        else:
            logger.warning("未找到配置文件，使用内置默认配置")
            return self._get_default_config()

    @staticmethod
    def _get_default_config() -> Dict[str, Any]:
        """内置默认配置"""
        return {
            "min_burst_intensity": 0.6,
            "max_bursts_per_chapter": 5,
            "burst_types": ["conflict", "revelation", "mood_shift"],
            "window_size": 200,
            "step_size": 50,
            "model_type": "rule_based",
            "model_path": None,
            "log_level": "INFO"
        }

    def _setup_logging(self):
        """根据配置设置日志级别"""
        level = self.config.get("log_level", "INFO")
        logging.getLogger(__name__).setLevel(level)

    def predict(self, text: str, context: Optional[Dict] = None) -> List[Dict]:
        """
        预测爆点
        :param text: 文本内容
        :param context: 额外上下文，例如章节标题、前文概要等
        :return: 爆点列表，格式: [{"position": int, "intensity": float, "type": str, "span": str}, ...]
        """
        logger.info("开始爆点预测，文本长度: %d", len(text))
        if not self.model_loaded:
            logger.warning("模型未加载，正在加载...")
            self.load_model()

        # 骨架实现：简单的基于标点符号的启发式检测（后期替换为真实算法）
        bursts = []
        for i in range(0, len(text), self.config["step_size"]):
            window = text[i : i + self.config["window_size"]]
            # 简单规则：感叹号或问号数量 > 2 视为爆点
            exclam_count = window.count("!") + window.count("?")
            if exclam_count > 2:
                intensity = min(0.5 + exclam_count * 0.1, 1.0)
                if intensity >= self.config["min_burst_intensity"]:
                    bursts.append({
                        "position": i,
                        "intensity": intensity,
                        "type": "emotion",
                        "span": window.strip()[:50]
                    })

        # 按强度降序排列并限制数量
        bursts = sorted(bursts, key=lambda x: x["intensity"], reverse=True)
        bursts = bursts[:self.config["max_bursts_per_chapter"]]
        logger.info("预测完成，发现 %d 个爆点", len(bursts))
        return bursts

    def load_model(self, model_path