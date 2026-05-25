"""
Module: humanize_rewrite.py
Path: 23_去AI化/人类化重写
Description: 对AI生成的文本进行人类化重写，消除机械感，模拟人类写作风格。
遵循可插拔、配置化、热更新、异常恢复、日志记录原则。
"""

import logging
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
import traceback

# 默认配置路径（可被外部覆盖）
DEFAULT_CONFIG_PATH = Path(__file__).parent / "humanize_config.yaml"

class HumanizeRewriter:
    """
    人类化重写器
    职责：接收原始AI文本，应用风格转换规则，输出更自然的文本。
    可插拔：通过配置文件切换策略或启用/禁用。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: Optional[Path] = None):
        """
        :param config: 直接传入配置字典，优先级高于文件
        :param config_path: 配置文件路径，若不传则使用默认路径
        """
        self.logger = logging.getLogger(f"{__name__}.HumanizeRewriter")
        self._config = None
        self._load_config(config, config_path)
        self.logger.info("HumanizeRewriter initialized with config: %s", self._config)

    def _load_config(self, config: Optional[Dict[str, Any]], config_path: Optional[Path]):
        """加载配置，支持热更新（通过重新加载方法）"""
        if config:
            self._config = config.copy()
            self.logger.debug("Config loaded from direct dict.")
            return
        path = config_path or DEFAULT_CONFIG_PATH
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
            self.logger.debug("Config loaded from file: %s", path)
        except FileNotFoundError:
            self.logger.warning("Config file not found: %s, using default empty config.", path)
            self._config = {}
        except Exception as e:
            self.logger.error("Failed to load config: %s. %s", e, traceback.format_exc())
            self._config = {}

    def reload_config(self, config: Optional[Dict[str, Any]] = None, config_path: Optional[Path] = None):
        """
        热更新配置，无需重启模块
        """
        self.logger.info("Reloading config...")
        self._load_config(config, config_path)
        self.logger.info("Config reloaded successfully.")

    def rewrite(self, text: str, style: Optional[str] = None) -> str:
        """
        核心接口：将输入文本重写为人类化风格
        :param text: 原始AI生成文本
        :param style: 可选风格参数，例如 'casual', 'literary' 等，若不指定则使用默认配置
        :return: 重写后的文本
        """
        if not text:
            return text
        try:
            # 获取风格配置
            effective_style = style or self._config.get("default_style", "casual")
            self.logger.debug("Rewriting text with style: %s, length: %d", effective_style, len(text))
            # TODO: 实际的重写逻辑，现阶段为占位实现（返回原始文本）
            # 未来通过插件化策略实现
            result = self._apply_humanization(text, effective_style)
            self.logger.info("Rewrite completed. Output length: %d", len(result))
            return result
        except Exception as e:
            self.logger.error("Rewrite failed: %s. Returning original text.", traceback.format_exc())
            # 异常恢复：返回原文本，保证系统不中断
            return text

    def _apply_humanization(self, text: str, style: str) -> str:
        """
        内部人类化处理逻辑，可根据style调度不同策略
        当前为骨架实现，仅返回原文本。
        """
        # 示例：根据style选择处理器（待实现）
        # 配置中可能包含短语替换、句式调整等
        # 此处仅记录日志并模拟
        self.logger.debug("Applying humanization style '%s'", style)
        # TODO: 集成更多规则、模型或外部服务
        return text

    def health_check(self) -> bool:
        """
        自检接口，确认模块可用
        """
        return self._config is not None

# 自测代码
if __name__ == "__main__":
    # 配置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 示例配置
    sample_config = {
        "default_style": "casual",
        "rules": {
            "remove_repetition": True,
            "add_personal_touch": True
        }
    }

    rewriter = HumanizeRewriter(config=sample_config)
    original = "在这个充满挑战的时代，我们需要坚持不懈地努力，不断提高自己的能力。"
    rewritten = rewriter.rewrite(original, style="casual")
    print(f"Original: {original}")
    print(f"Rewritten: {rewritten}")

    # 测试热更新
    new_config = {"default_style": "literary"}
    rewriter.reload_config(config=new_config)
    rewritten2 = rewriter.rewrite(original)
    print(f"After reload, rewritten: {rewritten2}")

    # 测试异常恢复（传入空文本）
    print(rewriter.rewrite(""))

    print("Health check:", rewriter.health_check())