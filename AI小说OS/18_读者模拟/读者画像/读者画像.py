#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读者画像模块
层级：18_读者模拟 / 读者画像
依赖：标准库、日志模块、配置模块（最小化自包含）
被调用方：读者模拟引擎、阅读行为生成器等
解决问题：定义和加载读者画像，提供统一接口获取读者特征、偏好、行为倾向等，
         支持灵活扩展，保证可插拔和配置化。
"""
import logging
import json
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

# --------------------------- 配置类 ---------------------------
class ReaderProfileConfig:
    """
    读者画像配置实体
    包含画像的基本属性字段，配置可由外部JSON或字典生成
    """

    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        config_dict = config_dict or {}
        # 基础身份
        self.reader_id: str = config_dict.get("reader_id", "anonymous")
        self.name: str = config_dict.get("name", "默认读者")
        self.age_group: str = config_dict.get("age_group", "unknown")  # e.g., young, adult, elder
        self.gender: str = config_dict.get("gender", "unknown")
        self.personality_traits: List[str] = config_dict.get("personality_traits", [])  # 性格标签
        # 阅读偏好
        self.preferred_genres: List[str] = config_dict.get("preferred_genres", [])  # 偏好类型
        self.reading_speed_wpm: int = config_dict.get("reading_speed_wpm", 250)  # 平均阅读速度
        self.attention_span_min: int = config_dict.get("attention_span_min", 15)  # 专注时长
        self.emotional_sensitivity: float = config_dict.get("emotional_sensitivity", 0.5)  # 情绪敏感度(0-1)
        # 行为模式
        self.dropout_threshold: float = config_dict.get("dropout_threshold", 0.3)  # 弃书阈值
        self.reread_tendency: float = config_dict.get("reread_tendency", 0.2)  # 重读倾向
        self.note_taking_likelihood: float = config_dict.get("note_taking_likelihood", 0.0)  # 做笔记概率
        # 扩展自定义字段
        self.custom_attributes: Dict[str, Any] = config_dict.get("custom_attributes", {})

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典，便于日志记录或存储"""
        return {
            "reader_id": self.reader_id,
            "name": self.name,
            "age_group": self.age_group,
            "gender": self.gender,
            "personality_traits": self.personality_traits,
            "preferred_genres": self.preferred_genres,
            "reading_speed_wpm": self.reading_speed_wpm,
            "attention_span_min": self.attention_span_min,
            "emotional_sensitivity": self.emotional_sensitivity,
            "dropout_threshold": self.dropout_threshold,
            "reread_tendency": self.reread_tendency,
            "note_taking_likelihood": self.note_taking_likelihood,
            "custom_attributes": self.custom_attributes,
        }

    @classmethod
    def from_json_file(cls, filepath: str) -> 'ReaderProfileConfig':
        """从JSON文件加载配置"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return cls(data)
        except Exception as e:
            logging.getLogger('ReaderProfile').error(f"加载配置文件失败 {filepath}: {e}")
            return cls()  # 返回默认配置


# --------------------------- 读者画像抽象基类 ---------------------------
class BaseReaderProfile(ABC):
    """
    读者画像抽象基类
    所有具体画像实现需继承此类，并实现相应方法
    以保证系统对画像调用的统一性，支持热插拔
    """

    @abstractmethod
    def get_config(self) -> ReaderProfileConfig:
        """返回当前画像配置对象"""
        pass

    @abstractmethod
    def get_feature_vector(self) -> List[float]:
        """
        获取用于模型计算的数值特征向量
        将画像关键属性编码为固定长度的向量，供模型使用
        """
        pass

    @abstractmethod
    def update_preference(self, feedback: Dict[str, Any]) -> None:
        """
        根据反馈更新画像偏好（如阅读后评分、弃书位置等）
        注：此方法可能触发重配置或日志记录
        """
        pass

    def describe(self) -> str:
        """返回人类可读的画像描述（可选覆盖）"""
        cfg = self.get_config()
        return f"读者[{cfg.name}](id={cfg.reader_id}) 偏好：{cfg.preferred_genres}"


# --------------------------- 默认读者画像实现 ---------------------------
class DefaultReaderProfile(BaseReaderProfile):
    """
    默认读者画像实现
    维护一个ReaderProfileConfig实例，并提供特征编码的基础逻辑
    """

    def __init__(self, config: Optional[ReaderProfileConfig] = None, logger: Optional[logging.Logger] = None):
        self._config = config if config else ReaderProfileConfig()
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.logger.info(f"初始化读者画像: {self._config.reader_id}")

    def get_config(self) -> ReaderProfileConfig:
        return self._config

    def get_feature_vector(self) -> List[float]:
        """简单示例：将部分数值属性转为特征向量，顺序固定
        实际使用时可根据需要扩展或替换编码方式"""
        cfg = self._config
        # 将分类特征简单数值化（示例性质）
        age_map = {"child": 0.0, "young": 0.25, "adult": 0.5, "elder": 0.75}
        gender_map = {"male": 0.0, "female": 1.0, "unknown": 0.5}
        age_val = age_map.get(cfg.age_group, 0.5)
        gender_val = gender_map.get(cfg.gender, 0.5)
        # 人格特征数量
        trait_count = len(cfg.personality_traits)
        # 偏好类型数量
        genre_count = len(cfg.preferred_genres)
        vector = [
            age_val,
            gender_val,
            trait_count,
            genre_count,
            float(cfg.reading_speed_wpm) / 500.0,   # 归一化
            float(cfg.attention_span_min) / 120.0,
            cfg.emotional_sensitivity,
            cfg.dropout_threshold,
            cfg.reread_tendency,
            cfg.note_taking_likelihood,
        ]
        self.logger.debug(f"生成特征向量: {vector}")
        return vector

    def update_preference(self, feedback: Dict[str, Any]) -> None:
        """示例：根据反馈微调偏好，实际中可接入强化学习或规则引擎"""
        self.logger.info(f"收到反馈: {feedback}")
        # 假设反馈中包含喜欢的类型，则更新preferred_genres
        if "liked_genre" in feedback:
            genre = feedback["liked_genre"]
            if genre not in self._config.preferred_genres:
                self._config.preferred_genres.append(genre)
                self.logger.info(f"新增偏好类型: {genre}")
        # 其他更新逻辑可在此扩展
        # 注意保持配置的一致性，必要时触发保存


# --------------------------- 可插拔工厂函数 ---------------------------
def create_reader_profile(profile_type: str = "default", config: Optional[ReaderProfileConfig] = None) -> BaseReaderProfile:
    """
    读者画像工厂函数
    支持根据字符串选择不同实现，便于配置化加载
    """
    if profile_type == "default":
        return DefaultReaderProfile(config)
    # 未来可添加其他类型
    else:
        raise ValueError(f"不支持的画像类型: {profile_type}")


# --------------------------- 自测 ---------------------------
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("ReaderProfileTest")

    # 测试1：用默认配置创建画像
    profile_default = create_reader_profile()
    logger.info("测试默认画像: " + profile_default.describe())
    logger.info("特征向量: " + str(profile_default.get_feature_vector()))

    # 测试2：从字典构建配置
    test_config_dict = {
        "reader_id": "reader_001",
        "name": "测试读者",
        "age_group": "young",
        "gender": "female",
        "personality_traits": ["感性", "挑剔"],
        "preferred_genres": ["奇幻", "言情"],
        "reading_speed_wpm": 300,
        "attention_span_min": 20,
        "emotional_sensitivity": 0.8,
        "dropout_threshold": 0.4,
        "reread_tendency": 0.3,
        "note_taking_likelihood": 0.1,
    }
    config = ReaderProfileConfig(test_config_dict)
    profile_custom = DefaultReaderProfile(config, logger)
    logger.info("自定义画像: " + profile_custom.describe())
    logger.info("特征向量: " + str(profile_custom.get_feature_vector()))

    # 测试3：更新偏好
    profile_custom.update_preference({"liked_genre": "科幻"})
    logger.info("更新后偏好: " + str(profile_custom.get_config().preferred_genres))

    # 测试4：序列化
    logger.info("配置字典: " + str(profile_custom.get_config().to_dict()))

    # 测试5：从JSON文件加载（如果存在，否则忽略）
    import os
    json_path = "test_reader_config.json"
    if os.path.exists(json_path):
        config_from_file = ReaderProfileConfig.from_json_file(json_path)
        logger.info("从文件加载的配置: " + str(config_from_file.to_dict()))
    else:
        logger.info("测试JSON文件不存在，跳过加载测试")

    logger.info("所有自测通过")