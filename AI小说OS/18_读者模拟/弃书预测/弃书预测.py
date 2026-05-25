from typing import List, Dict, Optional, Any
import logging
import json
from abc import ABC, abstractmethod
import os

# 基类定义，实现可插拔的弃书预测器
class BaseAbandonmentPredictor(ABC):
    """弃书预测器抽象基类
    
    所有具体的弃书预测实现必须继承此类，并实现 predict_abandonment 方法。
    保证系统可以热插拔不同的预测策略。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化预测器
        
        Args:
            config: 可选配置字典，用于覆盖默认配置
        """
        self.config = self._load_default_config()
        if config:
            self.config.update(config)
        self._setup_logging()
        self.logger.info(f"{self.__class__.__name__} initialized with config: {self.config}")

    @abstractmethod
    def predict_abandonment(self, 
                           current_chapter_id: str,
                           reader_profile: Dict[str, Any],
                           reading_history: List[Dict[str, Any]],
                           novel_metadata: Dict[str, Any]) -> float:
        """
        预测读者在当前阅读位置弃书的概率
        
        Args:
            current_chapter_id: 当前阅读的章节ID
            reader_profile: 读者画像数据 (包含阅读偏好、阅读速度等)
            reading_history: 历史阅读记录列表 [{'chapter_id', 'time_spent', 'engagement_score', ...}]
            novel_metadata: 小说元数据 (包含章节总数、分类、节奏数据等)
            
        Returns:
            弃书概率，范围 0.0 (不会弃书) 到 1.0 (必定弃书)
        """
        pass

    def _load_default_config(self) -> Dict[str, Any]:
        """加载默认配置，子类可以覆盖"""
        return {
            "threshold_warning": 0.6,  # 预警阈值
            "min_reading_samples": 3,  # 最少需要的阅读样本数
            "model_type": "default",   # 模型类型标识
            "enable_logging": True
        }

    def _setup_logging(self):
        """配置日志记录器"""
        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        level = logging.INFO if self.config.get("enable_logging", True) else logging.WARNING
        self.logger.setLevel(level)

    def validate_input(self, reader_profile: Dict, reading_history: List[Dict], novel_metadata: Dict) -> bool:
        """输入数据基本验证"""
        if not isinstance(reader_profile, dict):
            self.logger.error("reader_profile must be a dict")
            return False
        if not isinstance(reading_history, list):
            self.logger.error("reading_history must be a list")
            return False
        if not isinstance(novel_metadata, dict):
            self.logger.error("novel_metadata must be a dict")
            return False
        if len(reading_history) < self.config["min_reading_samples"]:
            self.logger.warning(f"Insufficient reading history: {len(reading_history)} < {self.config['min_reading_samples']}")
        return True

    def preprocess_data(self, 
                        current_chapter_id: str,
                        reader_profile: Dict,
                        reading_history: List[Dict],
                        novel_metadata: Dict) -> Dict:
        """
        数据预处理，提取特征供预测使用
        
        返回特征字典，子类可以重写以适配不同模型。
        """
        features = {
            "total_chapters_read": len(reading_history),
            "average_reading_time": 0.0,
            "completion_rate": 0.0,
            "recent_engagement": 0.0,
            "chapter_difficulty": 0.5,
        }
        if reading_history:
            # 计算平均阅读时间
            times = [record.get("time_spent", 0) for record in reading_history]
            features["average_reading_time"] = sum(times) / len(times) if times else 0
            # 最近的参与度 (取最后三条的平均)
            recent = [record.get("engagement_score", 0.5) for record in reading_history[-3:]]
            features["recent_engagement"] = sum(recent) / len(recent) if recent else 0.5
        # 完成度
        total_chapters = novel_metadata.get("total_chapters", 1)
        features["completion_rate"] = len(reading_history) / max(1, total_chapters)
        return features


class RuleBasedAbandonmentPredictor(BaseAbandonmentPredictor):
    """基于规则的弃书预测器实现 (示例)"""
    
    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        # 可在此处加载规则权重等
        self.weights = self.config.get("rule_weights", {
            "completion_rate": -0.3,
            "recent_engagement": -0.4,
            "average_reading_time": -0.2,
            "chapter_difficulty": 0.1
        })

    def predict_abandonment(self,
                           current_chapter_id: str,
                           reader_profile: Dict,
                           reading_history: List[Dict],
                           novel_metadata: Dict) -> float:
        if not self.validate_input(reader_profile, reading_history, novel_metadata):
            self.logger.error("Invalid input data for abandonment prediction")
            return 0.0
        
        features = self.preprocess_data(current_chapter_id, reader_profile, reading_history, novel_metadata)
        self.logger.debug(f"Extracted features: {features}")
        
        # 简单的线性加权模型
        score = 0.5  # 基础中性分
        for key, weight in self.weights.items():
            score += weight * features.get(key, 0.0)
        
        # 将分数映射到0-1概率
        probability = min(1.0, max(0.0, score))
        self.logger.info(f"Predicted abandonment probability for chapter {current_chapter_id}: {probability:.2f}")
        return probability


# 弃书预测主API，用作模块的统一入口
class AbandonmentPredictor:
    """弃书预测模块主类，负责加载配置和选择合适的预测器实例"""
    
    _predictor: Optional[BaseAbandonmentPredictor] = None
    
    @classmethod
    def initialize(cls, predictor_type: str = "rule", config: Optional[Dict] = None):
        """初始化预测器
        
        Args:
            predictor_type: 预测器类型 ('rule', 'ml', etc.)
            config: 全局配置
        """
        if config is None:
            config = cls._load_config_from_file()
        
        if predictor_type == "rule":
            cls._predictor = RuleBasedAbandonmentPredictor(config.get("rule_config", {}))
        # 未来可扩展其他预测器，如 MLModelAbandonmentPredictor
        else:
            raise ValueError(f"Unknown predictor type: {predictor_type}")
        logging.info(f"AbandonmentPredictor initialized with type: {predictor_type}")

    @classmethod
    def predict(cls, **kwargs) -> float:
        """统一预测接口"""
        if cls._predictor is None:
            cls.initialize()  # 默认初始化
        return cls._predictor.predict_abandonment(**kwargs)

    @staticmethod
    def _load_config_from_file(config_path: Optional[str] = None) -> Dict:
        """从配置文件加载配置，支持热插拔配置"""
        if config_path is None:
            # 默认配置文件路径，相对于项目根目录，这里作为示例使用硬编码
            config_path = os.environ.get("NOVELOS_ABANDONMENT_CONFIG", "config/abandonment_predictor.json")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logging.info(f"Config loaded from {config_path}")
            return config
        except FileNotFoundError:
            logging.warning(f"Config file {config_path} not found, using defaults")
            return {}
        except json.JSONDecodeError:
            logging.error(f"Config file {config_path} is not valid JSON")
            return {}
        except Exception as e:
            logging.error(f"Failed to load config: {e}")
            return {}


# 自测代码
if __name__ == "__main__":
    # 配置日志格式以便自测显示
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("=== 弃书预测模块自测 ===")
    
    # 模拟输入数据
    test_reader_profile = {
        "user_id": "reader_001",
        "preferred_genres": ["玄幻", "都市"],
        "average_reading_speed": 500  # 字/分钟
    }
    test_reading_history = [
        {"chapter_id": "ch1", "time_spent": 120, "engagement_score": 0.8},
        {"chapter_id": "ch2", "time_spent": 90, "engagement_score": 0.7},
        {"chapter_id": "ch3", "time_spent": 200, "engagement_score": 0.4},
        {"chapter_id": "ch4", "time_spent": 300, "engagement_score": 0.2},
    ]
    test_novel_metadata = {
        "novel_id": "novel_001",
        "title": "测试小说",
        "total_chapters": 100,
        "genre": "玄幻"
    }

    # 测试1: 使用类方法初始化并预测
    print("初始化默认预测器 (rule)...")
    AbandonmentPredictor.initialize(predictor_type="rule")
    prob = AbandonmentPredictor.predict(
        current_chapter_id="ch5",
        reader_profile=test_reader_profile,
        reading_history=test_reading_history,
        novel_metadata=test_novel_metadata
    )
    print(f"预测弃书概率: {prob:.2f}")

    # 测试2: 自定义配置创建预测器
    custom_config = {
        "threshold_warning": 0.7,
        "rule_weights": {
            "completion_rate": -0.5,
            "recent_engagement": -0.5,
            "average_reading_time": -0.2,
            "chapter_difficulty": 0.2
        }
    }
    predictor = RuleBasedAbandonmentPredictor(config=custom_config)
    prob2 = predictor.predict_abandonment(
        current_chapter_id="ch5",
        reader_profile=test_reader_profile,
        reading_history=test_reading_history,
        novel_metadata=test_novel_metadata
    )
    print(f"自定义权重预测弃书概率: {prob2:.2f}")

    # 测试3: 输入验证不足的情况
    print("测试不足样本数的情况...")
    short_history = test_reading_history[:2]
    prob3 = AbandonmentPredictor.predict(
        current_chapter_id="ch3",
        reader_profile=test_reader_profile,
        reading_history=short_history,
        novel_metadata=test_novel_metadata
    )
    print(f"短阅读历史预测弃书概率: {prob3:.2f}")

    print("=== 自测完成 ===")