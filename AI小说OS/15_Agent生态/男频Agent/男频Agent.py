只输出代码，不要markdown。```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NovelOS - 15_Agent生态/男频Agent
男频专属Agent骨架：具备可插拔、配置化、日志、自测能力。
遵循NovelOS核心架构规则，依赖20_模型协同/与21_API模型/，提供标准化Agent接口。
"""

import logging
import json
import os
from typing import Any, Dict, Optional

# ============================================================================
# 日志配置（可被外部覆盖）
# ============================================================================
logger = logging.getLogger("MaleAgent")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s][%(name)s][%(levelname)s] %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)  # 默认级别，可由外部调整


class MaleAgent:
    """
    男频Agent —— 专注于男频小说创作场景的AI助手。
    设计为可插拔组件，依赖模型协同中枢和模型API，不直接操作UI或数据库。
    """

    # 默认配置文件路径（相对于本模块）
    DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "male_agent_config.json")

    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None):
        """
        初始化男频Agent。

        Args:
            config: 字典形式的配置参数（优先级高于配置文件）
            config_path: 自定义配置文件路径，默认使用同目录下的 male_agent_config.json
        """
        # 1. 加载配置
        self.config = self._load_config(config, config_path if config_path else self.DEFAULT_CONFIG_PATH)
        logger.info("男频Agent初始化开始，配置加载完成。")

        # 2. 核心依赖占位（在骨架阶段不实际实例化）
        # 比如模型协同器、工具集等，后续填充
        self.model_coordinator = None   # 将由外部注入或从配置中延迟初始化
        self.tool_registry = None       # 工具注册表
        self.state: Dict[str, Any] = {} # Agent运行时状态

        # 3. 自检机制
        self._self_check()

        logger.info("男频Agent初始化成功，等待任务。")

    def _load_config(self, config: Optional[Dict[str, Any]], config_path: str) -> Dict[str, Any]:
        """加载配置：优先使用传入字典，否则从文件读取，文件不存在则用默认值。"""
        default_config = {
            "agent_name": "MaleFrequencyAgent",
            "description": "男频小说创作专属Agent",
            "model_config": {
                "default_model": "gpt-4",       # 占位示例
                "temperature": 0.7,
                "max_tokens": 2000
            },
            "tools": [],                        # 启用的工具列表
            "allowed_genres": ["都市", "玄幻", "仙侠", "历史", "科幻"],  # 男频常见分类
            "max_context_length": 4096,
            "enable_logging": True,
            "response_format": "json"
        }

        if config is not None:
            # 用户传入的配置直接覆盖默认
            merged = {**default_config, **config}
            logger.info("使用外部传入配置。")
            return merged

        # 尝试从文件加载
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    file_config = json.load(f)
                merged = {**default_config, **file_config}
                logger.info(f"从文件 {config_path} 加载配置。")
                return merged
            except Exception as e:
                logger.warning(f"配置文件读取失败: {e}，使用默认配置。")
                return default_config
        else:
            logger.warning(f"配置文件 {config_path} 不存在，使用默认配置。")
            return default_config

    def _self_check(self):
        """启动自检，验证配置完整性（不涉及真实依赖）。"""
        required_keys = ["agent_name", "model_config", "allowed_genres"]
        for key in required_keys:
            if key not in self.config:
                logger.warning(f"配置缺少必要字段: {key}")
        # 检查模型配置基础字段
        model_cfg = self.config.get("model_config", {})
        if "default_model" not in model_cfg:
            logger.warning("模型配置缺少 default_model")
        logger.info("自检通过（仅结构检查）。")

    def set_model_coordinator(self, coordinator):
        """
        注入模型协同器（遵循依赖注入原则）。
        该协同器负责调度21_API模型/的具体调用。

        Args:
            coordinator: 实现了模型协同接口的对象
        """
        self.model_coordinator = coordinator
        logger.info("已注入模型协同器。")

    def set_tool_registry(self, tools):
        """注入工具注册表。"""
        self.tool_registry = tools
        logger.info("已注入工具注册表。")

    def process(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        核心处理入口：接收用户输入（如创作需求），返回结构化响应。

        Args:
            user_input: 用户自然语言输入
            context: 可选的上下文信息（如当前章节、人物卡等）

        Returns:
            处理结果字典，至少包含 'status', 'message', 'data'
        """
        logger.info(f"收到任务: {user_input[:50]}...")

        # TODO: 实际调用模型协同器进行推理与工具编排
        # 骨架阶段仅返回模拟结果
        result = {
            "status": "success",
            "message": "男频Agent骨架处理中（尚未连接模型）",
            "data": {
                "output": None,
                "tool_calls": [],
                "model_used": self.config["model_config"]["default_model"]
            }
        }

        logger.info("任务处理完成（占位）。")
        return result

    def update_config(self, new_config: Dict[str, Any]):
        """运行时热更新配置（可插拔特性），配置会立即生效。"""
        self.config.update(new_config)
        logger.info(f"配置已热更新，当前配置: {json.dumps(self.config, ensure_ascii=False)}")

    def shutdown(self):
        """优雅关闭Agent，执行资源清理。"""
        logger.info("男频Agent正在关闭...")
        # 清理状态等
        self.state.clear()
        logger.info("男频Agent已安全关闭。")

    # ---------- 自测专用 ----------
    @staticmethod
    def selftest():
        """静态自测方法，用于无外部依赖验证骨架功能。"""
        print("=== 男频Agent 自测开始 ===")
        agent = MaleAgent()
        # 测试默认配置加载
        print("Agent名称:", agent.config["agent_name"])
        # 测试热更新
        agent.update_config({"model_config": {"default_model": "test-model"}})
        print("模型更新后:", agent.config["model_config"])
        # 测试处理
        res = agent.process("写一段主角出场描写")
        print("处理结果:", res)
        # 测试关闭
        agent.shutdown()
        print("=== 自测通过 ===")


# ============================================================================
# 自测入口
# ============================================================================
if __name__ == "__main__":
    # 设置日志级别以便观察
    logging.basicConfig(level=logging.INFO)
    MaleAgent.selftest()