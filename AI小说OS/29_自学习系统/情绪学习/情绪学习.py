"""
模块名: emotion_learning.py
路径: 29_自学习系统/情绪学习/
层级: 应用层 (29_自学习系统)
依赖: core.logging, core.config (假设存在), 可能依赖 20_模型协同/ 或 21_API模型/
被调用: 由 自学习系统调度器 或 情绪相关模块调用
功能: 从用户反馈、情节情绪流中学习情绪演化模式，优化情绪生成模型 (骨架)
"""

import logging
import json
from typing import Any, Dict, Optional

# 配置和日志接口，按照系统约定从核心层导入
try:
    from core.config import ConfigManager
    from core.logging import get_logger
except ImportError:
    # 如果核心模块尚未实现，使用标准库代替，保持兼容性
    ConfigManager = None
    get_logger = logging.getLogger

logger = get_logger(__name__)


class EmotionLearner:
    """
    情绪学习器：通过持续交互收集情绪信号，更新内部模型。
    可插拔设计：通过配置中的 enabled 字段控制是否激活；支持热加载配置。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化情绪学习器。
        :param config: 字典配置或None，如果为None则尝试从全局ConfigManager加载
        """
        self.config = config or {}
        if ConfigManager and not config:
            self.config = ConfigManager().get_section("emotion_learning", {})

        # 学习相关参数
        self.enabled = self.config.get("enabled", True)
        self.model_path = self.config.get("model_path", "data/emotion_model.json")
        self.learning_rate = self.config.get("learning_rate", 0.01)
        self.max_history = self.config.get("max_history", 1000)

        # 内部状态
        self.feedback_buffer = []   # 存储 (text, emotion_label, reward) 三元组
        self.model = {}             # 简化模型：emotion -> co-occurrence matrix 等 (实际可扩展)

        # 尝试加载已有模型
        if self.enabled:
            self.load_model()
            logger.info("情绪学习器初始化完成，状态: %s", "启用" if self.enabled else "禁用")
        else:
            logger.info("情绪学习器已禁用，跳过模型加载")

    def learn_from_context(self, text: str, target_emotion: str, feedback_score: float = 0.0) -> None:
        """
        从文本上下文和情绪目标中学习。
        :param text: 情节文本或对话文本
        :param target_emotion: 目标情绪标签
        :param feedback_score: 用户或系统反馈的评分（-1~1），0表示无反馈
        """
        if not self.enabled:
            return

        logger.debug("收到学习样本: 情绪=%s, 反馈=%.2f", target_emotion, feedback_score)

        # 缓存样本
        self.feedback_buffer.append((text, target_emotion, feedback_score))
        if len(self.feedback_buffer) > self.max_history:
            self.feedback_buffer.pop(0)

        # 更新内部模型（占位：实际调用 20_模型协同 或算法）
        self._update_internal_model(text, target_emotion, feedback_score)

    def _update_internal_model(self, text: str, emotion: str, reward: float) -> None:
        """
        内部模型更新逻辑（骨架）。
        实际实现应提取文本特征，与情绪标签关联，可能调用外部模型。
        """
        # TODO: 调用 特征提取 -> 协同学习模块
        # 例如: features = FeatureExtractor.extract(text)
        # ModelCoordinator.update("emotion_model", features, emotion, reward)
        logger.debug("内部模型更新占位: 情绪=%s, 奖励=%.2f", emotion, reward)

    def save_model(self) -> bool:
        """
        保存学习到的模型到文件。
        """
        if not self.enabled:
            return False
        try:
            with open(self.model_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "model": self.model,
                    "metadata": {
                        "learning_rate": self.learning_rate,
                        "buffer_size": len(self.feedback_buffer)
                    }
                }, f, indent=2, ensure_ascii=False)
            logger.info("情绪模型已保存至 %s", self.model_path)
            return True
        except Exception as e:
            logger.error("保存情绪模型失败: %s", str(e))
            return False

    def load_model(self) -> bool:
        """
        从文件加载已有模型。
        """
        if not self.enabled:
            return False
        try:
            with open(self.model_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.model = data.get("model", {})
                # 可选择性加载元数据
                logger.info("情绪模型从 %s 加载成功", self.model_path)
            return True
        except FileNotFoundError:
            logger.info("未找到模型文件 %s，将从零开始学习", self.model_path)
            return False
        except Exception as e:
            logger.error("加载情绪模型失败: %s", str(e))
            return False

    def reset_model(self) -> None:
        """
        重置模型和缓冲区。
        """
        self.model = {}
        self.feedback_buffer.clear()
        logger.info("情绪学习模型已重置")

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取学习器当前统计信息。
        """
        return {
            "enabled": self.enabled,
            "buffer_size": len(self.feedback_buffer),
            "model_keys": list(self.model.keys()) if self.model else [],
            "learning_rate": self.learning_rate,
        }

    def graceful_shutdown(self) -> None:
        """
        优雅关闭：保存模型，清理资源。
        """
        if self.enabled:
            self.save_model()
        logger.info("情绪学习器已关闭")


# --------------------- 自测代码 ---------------------
if __name__ == "__main__":
    # 配置测试日志
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("=== 情绪学习器自测开始 ===")
    # 使用空配置，启动学习器
    learner = EmotionLearner(config={
        "enabled": True,
        "model_path": "test_emotion_model.json",
        "learning_rate": 0.1,
        "max_history": 100
    })

    # 模拟学习过程
    test_samples = [
        ("主角愤怒地推开桌子", "anger", 0.8),
        ("她露出了温柔的笑容", "joy", 0.9),
        ("一阵未知的恐惧笼罩着他", "fear", 0.5),
        ("平静的湖面没有一丝波澜", "calm", 0.7),
    ]
    for text, emotion, reward in test_samples:
        learner.learn_from_context(text, emotion, reward)

    # 打印统计
    stats = learner.get_statistics()
    print("学习器统计:", stats)

    # 保存模型
    learner.save_model()

    # 重新加载模型并验证
    learner2 = EmotionLearner(config={
        "enabled": True,
        "model_path": "test_emotion_model.json",
        "learning_rate": 0.1
    })
    print("重新加载后统计:", learner2.get_statistics())

    # 重置并验证
    learner2.reset_model()
    print("重置后统计:", learner2.get_statistics())

    # 优雅关闭
    learner.graceful_shutdown()
    learner2.graceful_shutdown()

    # 清理测试文件（可选）
    import os
    if os.path.exists("test_emotion_model.json"):
        os.remove("test_emotion_model.json")

    print("=== 自测完成 ===")