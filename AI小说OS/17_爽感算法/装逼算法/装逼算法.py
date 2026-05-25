"""
Module Path: 17_爽感算法/装逼算法.py
Layer: 核心爽感算法层 / 装逼算法模块
Responsibility: 定义装逼算法接口，实现装逼爽感得分的计算逻辑，作为可插拔模块。
Dependencies:
  - 20_模型协同/ (预留模型调用接口，不直接调用API)
  - 21_API模型/ (通过模型协同间接使用)
  - 19_基础工具/配置管理 (读取全局配置)
  - 19_基础工具/日志 (统一日志记录)
Called by: 爽感计算协调器 (17_爽感算法/爽感协调器.py) 或其他爽感引擎
"""

from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

# -----------------------------------------------------------------------------
# 日志与配置的兼容导入（遵循系统规范，若无法导入则降级至基础模块）
# -----------------------------------------------------------------------------
try:
    from novelos.infrastructure.config import global_config  # 系统全局配置
    from novelos.infrastructure.logging import get_logger
except ImportError:
    # 降级处理，用于独立测试或早期开发
    global_config = {}
    def get_logger(name: str) -> logging.Logger:
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
        return logger

# -----------------------------------------------------------------------------
# 数据模型
# -----------------------------------------------------------------------------
@dataclass
class ZhuangbiResult:
    """装逼算法返回结果的数据结构。"""
    score: float = 0.0                              # 装逼综合得分，0-1或更大
    details: Dict[str, Any] = field(default_factory=dict)  # 详细得分项
    meta: Optional[Dict[str, Any]] = None           # 元信息，如算法版本、处理时间

# -----------------------------------------------------------------------------
# 抽象基类
# -----------------------------------------------------------------------------
class BaseZhuangbiAlgorithm(ABC):
    """装逼算法抽象基类。
    
    所有装逼算法实现必须继承此类，确保可插拔和统一调用接口。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config if config is not None else {}
        self.logger = get_logger(f"ZhuangbiAlgo.{self.__class__.__name__}")
        self.logger.debug("Algorithm instance created with config: %s", self.config)

    @abstractmethod
    def calculate(self, context: Dict[str, Any]) -> ZhuangbiResult:
        """计算给定上下文的装逼得分。
        
        Args:
            context: 包含文本、角色、段落等信息的字典。
        
        Returns:
            ZhuangbiResult 对象。
        """
        ...

    def health_check(self) -> bool:
        """健康检查，验证算法所需依赖是否就绪（可覆盖）。"""
        return True

# -----------------------------------------------------------------------------
# 默认实现：基于规则与关键词的装逼检测
# -----------------------------------------------------------------------------
class RuleBasedZhuangbiAlgorithm(BaseZhuangbiAlgorithm):
    """基于规则和关键词匹配的装逼算法实现。
    
    支持通过配置文件指定关键词及权重。
    可扩展为触发模型调用（通过模型协同接口）。
    """

    ALGORITHM_NAME = "RuleBasedZhuangbiV1"
    DEFAULT_KEYWORDS = [
        "淡淡", "随手", "不经意", "轻描淡写", "风轻云淡",
        "呵呵", "低调", "奢华", "不值一提", "不足挂齿",
        "甩了甩头发", "推开人群", "平凡", "漫不经心"
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # 从配置中加载算法参数，若无则使用默认值
        algo_cfg = self.config.get(self.ALGORITHM_NAME, {})
        self.keywords: List[str] = algo_cfg.get('keywords', self.DEFAULT_KEYWORDS)
        self.weight_matrix: Dict[str, float] = algo_cfg.get('weight_matrix', {kw: 1.0 for kw in self.keywords})
        self.model_enabled: bool = algo_cfg.get('model_enabled', False)
        self.model_name: Optional[str] = algo_cfg.get('model_name', None)
        self.bonus_multiplier: float = float(algo_cfg.get('bonus_multiplier', 1.5))
        
        # 日志记录初始化状态
        self.logger.info(
            "Algorithm '%s' initialized. Keywords count: %d, Model enabled: %s",
            self.ALGORITHM_NAME, len(self.keywords), self.model_enabled
        )

    def calculate(self, context: Dict[str, Any]) -> ZhuangbiResult:
        """执行装逼得分计算。
        
        当前实现仅进行简单关键词匹配，若启用模型则尝试调用（骨架阶段仅预留接口）。
        """
        self.logger.debug("Starting calculation for context id: %s", context.get('id', 'unknown'))
        
        score = 0.0
        details: Dict[str, Any] = {}
        text = context.get('text', '') or ''

        # 1. 关键词匹配
        matched = []
        for kw in self.keywords:
            if kw in text:
                weight = self.weight_matrix.get(kw, 1.0)
                score += weight
                matched.append({'keyword': kw, 'weight': weight})
        details['keyword_matches'] = matched
        details['keyword_score'] = score

        # 2. 特殊句式加分（示例：反问句）
        if '?' in text or '？' in text:
            bonus = len(text.split('?')) * 0.5
            score += bonus
            details['sentence_bonus