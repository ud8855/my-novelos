"""
23_去AI化/情绪强化/情绪强化.py
情绪强化模块：对文本进行情绪加强处理，使表达更具情感色彩。
遵循可插拔原则，提供标准接口，支持配置化与日志记录。
"""

import logging
from typing import Any, Dict, Optional

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)


class EmotionEnhancer:
    """
    情绪强化器，可由外部调用进行文本情绪增强。
    通过配置参数控制强化策略，完全可插拔。
    """

    # 默认配置
    DEFAULT_CONFIG = {
        "intensity": 0.8,          # 强化强度 (0.0 ~ 1.0)
        "method": "lexical",       # 强化方法: lexical (词汇替换), syntactic (句式调整), hybrid (混合)
        "emotion_types": ["joy", "sadness", "anger", "surprise", "fear", "disgust"],  # 支持的情绪类型
        "preserve_original": False # 是否保留原文作为参考输出
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化情绪强化模块。
        :param config: 可选的配置字典，会与默认配置合并。
        """
        self.config = self.DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        logger.info("情绪强化模块初始化完成，当前配置: %s", self.config)
        self._validate_config()

    def _validate_config(self):
        """校验配置合法性，记录警告但不清退。"""
        try:
            assert 0.0 <= self.config["intensity"] <= 1.0, "intensity 必须在 [0.0, 1.0] 区间内"
            assert self.config["method"] in ("lexical", "syntactic", "hybrid"), f"未知的方法: {self.config['method']}"
            logger.debug("配置校验通过")
        except AssertionError as e:
            logger.warning("配置校验发现问题: %s", str(e))
            # 根据需求可回退到默认某值，这里仅记录警告

    def enhance(self, text: str, parameters: Optional[Dict[str, Any]] = None) -> str:
        """
        对输入文本进行情绪强化处理。
        :param text: 原始文本字符串。
        :param parameters: 可选参数字典，可用于覆盖本次调用的部分配置（如 intensity）。
        :return: 强化后的文本字符串。
        """
        if not text:
            logger.warning("输入文本为空，返回空字符串")
            return ""

        # 合并运行时参数到配置快照，不改变实例配置
        runtime_config = self.config.copy()
        if parameters:
            runtime_config.update(parameters)

        logger.info("开始情绪强化，方法: %s，强度: %.2f", runtime_config["method"], runtime_config["intensity"])
        try:
            # 这里是核心算法占位，未来实现替换
            enhanced_text = self._apply_enhancement(text, runtime_config)
            logger.debug("情绪强化成功")
            return enhanced_text
        except Exception as e:
            logger.error("情绪强化过程异常: %s", str(e), exc_info=True)
            # 异常恢复：返回原文（安全降级）
            return text

    def _apply_enhancement(self, text: str, config: Dict[str, Any]) -> str:
        """
        内部强化逻辑占位。根据配置选择不同策略。
        当前为骨架实现，仅简单返回原文附加标记。
        :param text: 待处理文本
        :param config: 运行时配置
        :return: 处理后的文本
        """
        # TODO: 实现具体的情绪强化算法，例如：
        # - 基于词典替换
        # - 句式调整（反问、感叹等）
        # - 混合策略
        # 目前返回带提示的原文
        method = config["method"]
        intensity = config["intensity"]
        # 简单示例：根据强度添加情绪标记（实际应替换）
        if method == "lexical":
            enhanced = f"[情绪强化(词汇-强度{intensity})] {text}"
        elif method == "syntactic":
            enhanced = f"[情绪强化(句式-强度{intensity})] {text}"
        else:  # hybrid
            enhanced = f"[情绪强化(混合-强度{intensity})] {text}"
        return enhanced

    def reload_config(self, new_config: Dict[str, Any]):
        """
        热更新配置，支持运行时动态调整，无需重启。
        :param new_config: 新的配置字典
        """
        logger.info("接收到配置热更新请求")
        self.config.update(new_config)
        self._validate_config()
        logger.info("配置热更新完成: %s", self.config)


# ========== 自测模块 ==========
if __name__ == "__main__":
    print("开始自测情绪强化模块...")
    enhancer = EmotionEnhancer()
    test_text = "今天的天气很好，我很开心。"
    result = enhancer.enhance(test_text, {"intensity": 0.9})
    print(f"原文: {test_text}")
    print(f"强化结果: {result}")

    # 测试热更新配置
    enhancer.reload_config({"method": "hybrid", "intensity": 0.5})
    result2 = enhancer.enhance("他的突然离开让我措手不及。")
    print(f"更新配置后结果: {result2}")

    print("自测完成。")