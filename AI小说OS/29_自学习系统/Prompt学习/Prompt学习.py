"""29_自学习系统/Prompt学习.py - Prompt学习模块骨架
负责从历史交互数据中学习 Prompt 优化策略，提供可插拔的学习与适配能力。
依赖：无外部模块依赖（仅标准库），由上层调度器调用。
被调用：通过 29_自学习系统 的调度器按需调用学习与更新流程。
"""

import logging
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

# 默认日志格式
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DEFAULT_CONFIG = {
    "learning_rate": 0.01,
    "max_history_samples": 1000,
    "prompt_template_cache": "prompt_templates.json",
    "log_level": "INFO",
    "log_file": "prompt_learning.log"
}


class PromptLearner:
    """Prompt 学习器：负责分析历史 Prompt 与效果反馈，持续优化 Prompt 模板。"""

    def __init__(self, config_path: Optional[str] = None):
        """初始化学习器，加载配置并设置日志。

        Args:
            config_path: 配置文件路径 (JSON)，若为 None 则使用默认配置。
        """
        self.config = self._load_config(config_path)
        self.logger = self._setup_logger()
        self.learned_params: Dict[str, Any] = {}  # 存储学习到的参数
        self.logger.info("PromptLearner 已初始化，配置: %s", self.config)

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """加载配置文件，缺失项用默认值填充。

        Args:
            config_path: 配置文件路径。

        Returns:
            完整的配置字典。
        """
        config = DEFAULT_CONFIG.copy()
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                config.update(user_config)
            except Exception as e:
                # 使用 logging 之前尚未初始化，只能 print 或假定默认
                print(f"配置文件加载失败: {e}，使用默认配置")
        return config

    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器。

        Returns:
            配置好的 logger 对象。
        """
        log_level = getattr(logging, self.config.get("log_level", "INFO").upper(), logging.INFO)
        log_file = self.config.get("log_file")
        logger = logging.getLogger("PromptLearner")
        logger.setLevel(log_level)

        # 避免重复添加 handler
        if not logger.handlers:
            # 控制台输出
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_formatter = logging.Formatter(LOG_FORMAT)
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

            # 文件输出（若指定）
            if log_file:
                file_handler = logging.FileHandler(log_file, encoding='utf-8')
                file_handler.setLevel(log_level)
                file_handler.setFormatter(console_formatter)
                logger.addHandler(file_handler)

        return logger

    def learn(self, interaction_history: List[Dict[str, Any]]) -> None:
        """根据交互历史数据执行学习，更新内部 learned_params。

        Args:
            interaction_history: 交互历史列表，每项包含 prompt, response, feedback 等字段。
        """
        if not interaction_history:
            self.logger.warning("交互历史为空，跳过学习")
            return

        self.logger.info("开始学习，历史样本数: %d", len(interaction_history))
        # ---- 骨架学习逻辑（待实现） ----
        # 1. 数据清洗与特征提取
        # 2. 分析 prompt 结构与反馈关系
        # 3. 更新学习参数 (例如调整提示词权重、关键词选择规则等)
        # ---- 模拟学习过程 ----
        self.learned_params["last_update"] = len(interaction_history)
        self.learned_params["sample_count"] = len(interaction_history)
        self.learned_params["strategy"] = "baseline"  # 模拟
        self.logger.info("学习完成，当前参数: %s", self.learned_params)

    def apply_learning(self, current_prompt: str) -> str:
        """应用学习成果到给定的 prompt 模板，返回优化后的 prompt。

        Args:
            current_prompt: 原始 prompt 模板。

        Returns:
            经过学习策略优化后的 prompt 字符串。
        """
        self.logger.debug("应用学习到 prompt: %s...", current_prompt[:50])
        # ---- 骨架逻辑（待实现） ----
        # 例如根据 learned_params 调整 prompt 中的指令、添加示例等
        optimized = current_prompt  # 占位
        if self.learned_params:
            # 模拟：在 prompt 末尾追加学习标识
            optimized += f"\n[优化策略: {self.learned_params.get('strategy', 'none')}]"
        self.logger.info("应用学习完成")
        return optimized

    def save_state(self, save_path: str) -> None:
        """保存学习器状态到文件（持久化学习参数）。

        Args:
            save_path: 保存路径。
        """
        dir_name = os.path.dirname(save_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        try:
            data = {
                "config": self.config,
                "learned_params": self.learned_params
            }
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.info("学习器状态已保存至 %s", save_path)
        except Exception as e:
            self.logger.error("保存状态失败: %s", e)
            raise

    def load_state(self, load_path: str) -> None:
        """从文件恢复学习器状态。

        Args:
            load_path: 状态文件路径。
        """
        if not os.path.exists(load_path):
            self.logger.warning("状态文件 %s 不存在，无法加载", load_path)
            return
        try:
            with open(load_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.config.update(data.get("config", {}))
            self.learned_params = data.get("learned_params", {})
            self.logger.info("状态已从 %s 恢复", load_path)
        except Exception as e:
            self.logger.error("加载状态失败: %s", e)
            raise


# ---------- 自测 ----------
if __name__ == "__main__":
    print("开始 PromptLearner 自测...")

    # 使用默认配置
    learner = PromptLearner()

    # 模拟交互历史
    mock_history = [
        {"prompt": "写一个关于友谊的故事", "response": "（长文本）", "feedback": {"quality": 0.8, "keywords": ["友谊", "冒险"]}},
        {"prompt": "写一个科幻故事", "response": "（长文本）", "feedback": {"quality": 0.6, "keywords": ["科幻", "反乌托邦"]}},
    ]

    # 学习
    learner.learn(mock_history)

    # 应用学习
    original_prompt = "请生成一个精彩的故事"
    optimized_prompt = learner.apply_learning(original_prompt)
    print("优化后的 prompt:", optimized_prompt)

    # 保存与加载状态
    test_save_path = "./test_prompt_learner_state.json"
    learner.save_state(test_save_path)

    # 创建新实例并加载状态
    learner2 = PromptLearner()
    learner2.load_state(test_save_path)
    print("加载后的学习参数:", learner2.learned_params)

    # 清理测试文件
    if os.path.exists(test_save_path):
        os.remove(test_save_path)

    print("自测完成，无异常。")