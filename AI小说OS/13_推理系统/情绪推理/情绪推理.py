import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

# 配置路径
DEFAULT_CONFIG = {
    "log_level": "INFO",
    "log_file": None,
    "emotion_categories": ["joy", "sadness", "anger", "fear", "surprise", "disgust", "trust", "anticipation"],
    "model_coordinator": None,  # 指向20_模型协同的处理器
}

class EmotionReasoner(ABC):
    """
    情绪推理器抽象基类
    所有情绪推理实现必须继承此类，确保可插拔性。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        self._setup_logger()
        self.logger.info("EmotionReasoner initialized with config: %s", self.config)

    def _setup_logger(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        level = getattr(logging, self.config.get("log_level", "INFO").upper(), logging.INFO)
        self.logger.setLevel(level)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        if self.config.get("log_file"):
            fh = logging.FileHandler(self.config["log_file"], encoding="utf-8")
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)

    @abstractmethod
    def infer_emotion(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据上下文推理情绪状态
        :param context: 包含剧情、角色当前状态等信息的字典
        :return: 情绪推理结果，包含情绪类别及强度等
        """
        pass

    @abstractmethod
    def update_emotion_state(self, character_id: str, new_emotion: Dict[str, Any]) -> None:
        """
        更新角色情绪状态（持久化或缓存）
        :param character_id: 角色标识
        :param new_emotion: 新的情绪数据
        """
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__} config={self.config}>"


class DefaultEmotionReasoner(EmotionReasoner):
    """
    默认情绪推理器实现（占位）
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.logger.info("DefaultEmotionReasoner ready (stub implementation)")

    def infer_emotion(self, context: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.debug("Called infer_emotion with context: %s", context)
        # 实际推理应调用模型协同层
        # 当前返回占位结果
        return {
            "primary_emotion": "neutral",
            "intensity": 0.0,
            "secondary_emotions": {},
            "explanation": "Stub inference, no actual processing."
        }

    def update_emotion_state(self, character_id: str, new_emotion: Dict[str, Any]) -> None:
        self.logger.debug("Updating emotion state for character %s with %s", character_id, new_emotion)
        # TODO: 实现状态更新逻辑，与状态管理模块交互
        pass


# 自测
if __name__ == "__main__":
    print("=== 情绪推理模块自测 ===")
    # 测试默认推理器
    reasoner = DefaultEmotionReasoner()
    test_context = {
        "scene": "主角目睹挚友牺牲",
        "character": {"name": "Alex", "current_mood": "shock"}
    }
    result = reasoner.infer_emotion(test_context)
    print("推理结果：", result)
    reasoner.update_emotion_state("char_001", result)
    print("自测完成。")