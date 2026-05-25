# -*- coding: utf-8 -*-
"""
情绪系统 - 角色引擎子模块
负责角色情绪的初始化、更新、衰减、事件响应。
可插拔设计：通过继承抽象基类 EmotionSystem 实现不同的情绪模型。
配置化：所有参数可通过字典传入，默认使用 EMOTION_DEFAULT_CONFIG。
日志：使用 logging 记录情绪变化、事件处理、异常等。
"""

import logging
import copy
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple

# 日志器
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())  # 由上层配置handler

# --------------------------- 默认配置 ---------------------------
EMOTION_DEFAULT_CONFIG = {
    "initial_emotions": {
        "joy": 0.0,
        "sadness": 0.0,
        "anger": 0.0,
        "fear": 0.0,
        "surprise": 0.0,
        "disgust": 0.0,
        "trust": 0.0,
        "anticipation": 0.0,
    },
    "decay_rate": 0.01,          # 每时间单位衰减系数
    "max_emotion_value": 1.0,
    "min_emotion_value": 0.0,
    "event_impact_scale": 1.0,  # 事件影响缩放因子
    "enable_logging": True,
}

# --------------------------- 抽象接口 ---------------------------
class EmotionSystem(ABC):
    """
    情绪系统抽象基类，定义角色情绪操作的标准接口。
    所有具体情绪模型必须实现此接口。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化情绪系统。

        Args:
            config: 配置字典，若为 None 则使用默认配置 EMOTION_DEFAULT_CONFIG。
        """
        if config is None:
            config = copy.deepcopy(EMOTION_DEFAULT_CONFIG)
        self.config = config
        self.emotions: Dict[str, float] = {}
        self._init_emotions()
        self.logger = logger
        if self.config.get("enable_logging", True):
            self.logger.info("EmotionSystem initialized with config=%s", str(config))

    def _init_emotions(self):
        """根据配置初始化情绪字典。"""
        initial = self.config.get("initial_emotions", {})
        if not initial:
            # 如果配置为空，使用默认情绪列表全部置零
            initial = {k: 0.0 for k in EMOTION_DEFAULT_CONFIG["initial_emotions"]}
        self.emotions = copy.deepcopy(initial)

    @abstractmethod
    def update_emotion(self, event: Dict[str, Any], dt: float = 1.0) -> Dict[str, float]:
        """
        根据事件和时间步长更新情绪值。
        具体实现可包含事件映射、强度计算、衰减等。

        Args:
            event: 事件字典，至少包含 'type' 和可选的 'intensity', 'valence' 等。
            dt: 时间步长，用于衰减计算。

        Returns:
            更新后的情绪状态字典。
        """
        pass

    @abstractmethod
    def apply_decay(self, dt: float = 1.0) -> None:
        """
        仅对当前情绪进行自然衰减，不考虑事件。

        Args:
            dt: 时间步长。
        """
        pass

    @abstractmethod
    def get_dominant_emotion(self) -> Tuple[str, float]:
        """
        获取当前主导情绪。

        Returns:
            (情绪名, 强度) 元组。
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """重置情绪到初始状态。"""
        pass

    def register_logger(self, logger_instance: logging.Logger):
        """允许外部注入日志器，实现可插拔日志。"""
        self.logger = logger_instance

    def validate_config(self) -> bool:
        """检查配置完整性，可按需重载。"""
        required_keys = ["initial_emotions", "decay_rate"]
        for key in required_keys:
            if key not in self.config:
                self.logger.error("Missing config key: %s", key)
                return False
        return True

# --------------------------- 基础实现示例 ---------------------------
class BasicEmotionSystem(EmotionSystem):
    """
    一个基本的情绪系统实现，演示线性衰减和基于事件的情绪调整。
    作为默认实现，可直接使用或作为开发参考。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.event_mapping: Dict[str, Dict[str, float]] = self.config.get(
            "event_mapping",
            {
                "happy_event": {"joy": 0.3, "trust": 0.1},
                "sad_event": {"sadness": 0.4, "fear": 0.1},
                "angry_event": {"anger": 0.5, "disgust": 0.2},
                "surprise_event": {"surprise": 0.6, "anticipation": 0.1},
                # 更多映射可扩展
            }
        )

    def update_emotion(self, event: Dict[str, Any], dt: float = 1.0) -> Dict[str, float]:
        try:
            if not event or "type" not in event:
                self.logger.warning("Invalid event without 'type': %s", event)
                return self.emotions

            # 先进行自然衰减
            self.apply_decay(dt)

            event_type = event["type"]
            intensity = event.get("intensity", 1.0) * self.config.get("event_impact_scale", 1.0)
            valence = event.get("valence", 0.0)  # 可用于精细调整

            # 查找事件映射
            delta = self.event_mapping.get(event_type, {})
            if not delta:
                self.logger.debug("No mapping for event type '%s'", event_type)
                # 尝试使用 valence 做通用调整，但保持简单
                return self.emotions

            # 应用情绪变化，并限制范围
            for emotion_name, base_change in delta.items():
                change = base_change * intensity
                new_val = self.emotions.get(emotion_name, 0.0) + change
                max_val = self.config.get("max_emotion_value", 1.0)
                min_val = self.config.get("min_emotion_value", 0.0)
                self.emotions[emotion_name] = max(min_val, min(max_val, new_val))

            self.logger.info(
                "Event '%s' processed. Emotions: %s", event_type, str(self.emotions)
            )
            return self.emotions
        except Exception as e:
            self.logger.error("Error updating emotion: %s", e, exc_info=True)
            raise

    def apply_decay(self, dt: float = 1.0) -> None:
        if dt <= 0:
            return
        decay_rate = self.config.get("decay_rate", 0.01)
        for emotion_name in self.emotions:
            current = self.emotions[emotion_name]
            # 线性衰减向中性值0衰减，但情绪具有最小值限制
            min_val = self.config.get("min_emotion_value", 0.0)
            decayed = current - decay_rate * dt
            self.emotions[emotion_name] = max(min_val, decayed)

    def get_dominant_emotion(self) -> Tuple[str, float]:
        if not self.emotions:
            return ("none", 0.0)
        dominant = max(self.emotions.items(), key=lambda item: item[1])
        return dominant

    def reset(self) -> None:
        self._init_emotions()
        self.logger.info("Emotions reset to initial state.")

# --------------------------- 自测 ---------------------------
if __name__ == "__main__":
    # 配置日志输出到控制台
    test_logger = logging.getLogger("EmotionSystemTest")
    test_logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    test_logger.addHandler(handler)

    # 使用基础情绪系统
    system = BasicEmotionSystem()
    system.register_logger(test_logger)

    print("初始情绪:", system.emotions)
    print("主导情绪:", system.get_dominant_emotion())

    # 模拟事件
    event1 = {"type": "happy_event", "intensity": 0.8}
    system.update_emotion(event1, dt=1.0)
    print("事件后:", system.emotions)

    # 衰减
    system.apply_decay(2.0)
    print("衰减后:", system.emotions)

    # 重置
    system.reset()
    print("重置后:", system.emotions)