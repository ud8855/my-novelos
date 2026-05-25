# -*- coding: utf-8 -*-
"""
情绪模拟模块 - 位于 18_读者模拟/情绪模拟/
职责：模拟读者在阅读过程中的情绪变化，支持情绪状态管理、情绪更新、情绪影响计算
依赖：20_模型协同/ (待定义接口)、21_API模型/ (底层)
被调用者：读者模拟主控、情节评估、反应生成等模块
特性：可插拔、配置化、日志化、支持热更新
"""
import logging
import yaml
from typing import Dict, Any, Optional, List, Tuple

# 配置默认值
DEFAULT_CONFIG = {
    "emotion_dimensions": ["valence", "arousal", "dominance"],  # 情绪维度：效价、唤醒度、支配度
    "initial_state": {"valence": 0.5, "arousal": 0.5, "dominance": 0.5},
    "decay_rate": 0.01,            # 情绪自然衰减率
    "event_impact_scale": 0.1,     # 事件对情绪的影响缩放因子
    "model_provider": "default",   # 使用的模型协同提供者标识
    "log_level": "INFO",
}

class EmotionState:
    """情绪状态对象，存储多维情绪值"""
    def __init__(self, dimensions: List[str], initial_values: Dict[str, float] = None):
        self.dimensions = dimensions
        self.values = {}
        for dim in self.dimensions:
            self.values[dim] = initial_values.get(dim, 0.5) if initial_values else 0.5

    def copy(self) -> "EmotionState":
        new_state = EmotionState(self.dimensions, self.values)
        return new_state

    def to_dict(self) -> Dict[str, float]:
        return self.values.copy()

    def update(self, delta: Dict[str, float]):
        for dim, val in delta.items():
            if dim in self.values:
                self.values[dim] = max(0.0, min(1.0, self.values[dim] + val))
        # 保持总维度一致
        for dim in self.dimensions:
            self.values[dim] = max(0.0, min(1.0, self.values[dim]))

    def __repr__(self):
        return f"EmotionState({self.values})"


class EmotionSimulator:
    """
    情绪模拟器
    负责根据文本事件、阅读进度等更新读者情绪状态，并提供情绪影响的量化输出。
    设计为可插拔组件，通过配置切换不同情绪模型（如基于规则、基于神经网络等）。
    """
    def __init__(self, config_path: Optional[str] = None, **override_config):
        """
        初始化情绪模拟器
        :param config_path: 外部配置文件路径（YAML），可选
        :param override_config: 可覆盖配置项
        """
        self.config = DEFAULT_CONFIG.copy()
        # 加载外部配置文件
        if config_path:
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    external_config = yaml.safe_load(f)
                if external_config:
                    self.config.update(external_config)
            except Exception as e:
                logging.warning(f"情绪模拟器：加载配置文件 {config_path} 失败，使用默认配置。错误：{e}")

        # 应用覆盖参数
        self.config.update(override_config)

        # 初始化日志
        self.logger = logging.getLogger(f"EmotionSimulator")
        log_level = getattr(logging, self.config.get("log_level", "INFO"), logging.INFO)
        self.logger.setLevel(log_level)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s] %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # 情绪维度配置
        self.dimensions = self.config.get("emotion_dimensions", ["valence", "arousal", "dominance"])
        self.initial_state = self.config.get("initial_state", {})
        self.decay_rate = self.config.get("decay_rate", 0.01)
        self.event_impact_scale = self.config.get("event_impact_scale", 0.1)

        # 当前情绪状态
        self.current_state = EmotionState(self.dimensions, self.initial_state)
        self.state_history = []  # 用于回溯和分析

        # 模型提供者标识（预留接口，实际调用通过20_模型协同/）
        self.model_provider = self.config.get("model_provider", "default")

        self.logger.info("情绪模拟器初始化完成，维度: %s", self.dimensions)

    def reset(self, initial_dict: Optional[Dict[str, float]] = None):
        """重置情绪状态到初始值"""
        if initial_dict:
            self.initial_state = initial_dict
        self.current_state = EmotionState(self.dimensions, self.initial_state)
        self.state_history.clear()
        self.logger.info("情绪状态已重置")

    def update_emotion(self, event: Dict[str, Any]):
        """
        根据当前情绪和事件更新情绪状态。
        event 包含 'type', 'intensity', 'text' 等描述。
        此方法调用内部或外部情绪影响计算逻辑。
        """
        self.logger.debug("收到情绪事件: %s", event)
        # 计算情绪变化量
        delta = self._calculate_emotion_delta(event)
        self.logger.debug("情绪变化量: %s", delta)
        # 应用衰减
        self._apply_decay()
        # 更新状态
        old_state = self.current_state.copy()
        self.current_state.update(delta)
        self.state_history.append((old_state.to_dict(), self.current_state.to_dict(), event.get("id", None)))
        self.logger.debug("情绪更新完成: %s -> %s", old_state, self.current_state)
        return self.current_state.to_dict()

    def get_emotion_state(self) -> Dict[str, float]:
        """获取当前情绪状态字典"""
        return self.current_state.to_dict()

    def estimate_emotional_impact(self, text: str) -> Dict[str, float]:
        """
        预估某文本（如段落）可能造成的情绪影响，不改变内部状态。
        依赖模型协同层进行计算。
        """
        self.logger.debug("预评估文本情绪影响: %s...", text[:50])
        # 调用模型协同接口（占位）
        # from 20_模型协同.xxx import estimate_text_emotion_impact
        # 暂时返回零向量
        return {dim: 0.0 for dim in self.dimensions}

    def _apply_decay(self):
        """应用自然衰减，使情绪逐渐回归中性（默认各维度0.5）。"""
        for dim in self.dimensions:
            current_val = self.current_state.values[dim]
            # 向0.5回归
            adjusted = current_val + self.decay_rate * (0.5 - current_val)
            self.current_state.values[dim] = max(0.0, min(1.0, adjusted))

    def _calculate_emotion_delta(self, event: Dict[str, Any]) -> Dict[str, float]:
        """
        计算事件对情绪各维度的影响变化量。
        未来可对接模型协同层，此处提供简单的规则示例。
        """
        event_type = event.get("type", "neutral")
        intensity = float(event.get("intensity", 1.0))

        # 简单规则映射（可插拔替换）
        rule_map = {
            "positive_surprise": {"valence": 0.1, "arousal": 0.2, "dominance": -0.1},
            "negative_surprise": {"valence": -0.2, "arousal": 0.2, "dominance": -0.1},
            "conflict": {"valence": -0.15, "arousal": 0.1, "dominance": 0.1},
            "resolution": {"valence": 0.15, "arousal": -0.1, "dominance": 0.1},
            "sadness": {"valence": -0.2, "arousal": -0.1, "dominance": -0.1},
            "joy": {"valence": 0.2, "arousal": 0.1, "dominance": 0.1},
            "fear": {"valence": -0.1, "arousal": 0.3, "dominance": -0.2},
            "neutral": {"valence": 0.0, "arousal": 0.0, "dominance": 0.0},
        }

        base_delta = rule_map.get(event_type, {"valence": 0.0, "arousal": 0.0, "dominance": 0.0})
        # 乘以强度因子和全局缩放
        delta = {dim: base_delta.get(dim, 0.0) * intensity * self.event_impact_scale for dim in self.dimensions}
        return delta

    def save_state(self, file_path: str):
        """持久化当前情绪状态和历史（用于热恢复）"""
        data = {
            "current_state": self.current_state.to_dict(),
            "history": [(t[0], t[1], t[2]) for t in self.state_history[-100:]],  # 只保留最近100条
        }
        import json
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.logger.info("情绪状态已保存至 %s", file_path)

    def load_state(self, file_path: str):
        """从文件恢复情绪状态"""
        import json
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.current_state = EmotionState(self.dimensions, data["current_state"])
        self.state_history = [tuple(t) for t in data.get("history", [])]
        self.logger.info("情绪状态已从 %s 恢复", file_path)

    def register_model_provider(self, provider):
        """
        注册外部模型提供者，实现可插拔。
        provider 需实现 estimate_impact(event, current_state)->dict 等方法。
        """
        self.model_provider = provider
        self.logger.info("已注册情绪模型提供者: %s", getattr(provider, '__class__', 'unknown'))

    def get_statistics(self) -> Dict[str, Any]:
        """返回情绪模拟的统计信息（用于调试和监控）"""
        if not self.state_history:
            return {"avg_valence": 0.5, "avg_arousal": 0.5, "avg_dominance": 0.5, "total_steps": 0}
        avg = {dim: 0.0 for dim in self.dimensions}
        total = len(self.state_history)
        for _, after_state, _ in self.state_history:
            for dim in self.dimensions:
                avg[dim] += after_state[dim]
        for dim in self.dimensions:
            avg[dim] /= total
        return {"avg_" + dim: avg[dim] for dim in self.dimensions} | {"total_steps": total}


# 自测部分
if __name__ == "__main__":
    import time

    # 基本功能测试
    sim = EmotionSimulator(log_level="DEBUG")
    print("初始情绪:", sim.get_emotion_state())

    # 模拟事件序列
    events = [
        {"type": "positive_surprise", "intensity": 1.5, "text": "主角意外获得宝藏"},
        {"type": "conflict", "intensity": 1.2, "text": "遭遇敌人"},
        {"type": "resolution", "intensity": 1.0, "text": "成功解决问题"},
        {"type": "sadness", "intensity":