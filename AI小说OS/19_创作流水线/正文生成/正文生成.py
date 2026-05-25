"""
正文生成模块
功能: 负责根据大纲、前文、设定等信息，调用模型生成具体章节或段落正文。
所属层: 19_创作流水线
依赖:
    20_模型协同/
    21_API模型/ (可选)
    10_数据持久层/ 用于读取上下文和保存结果
    00_系统基础服务/ 日志、配置等
被调用: 由流水线调度器触发，或者上一步骤（如大纲规划）完成后的回调。
"""

import logging
from typing import Dict, Any, Optional

# 假定系统基础服务提供了配置加载和日志初始化
try:
    from core.config import ConfigManager
except ImportError:
    class ConfigManager:
        """Mock配置管理，用于独立测试"""
        def __init__(self):
            self.config = {
                "generation": {
                    "model_name": "default-model",
                    "max_tokens": 2000,
                    "temperature": 0.7,
                    "retry_count": 3,
                    "prompt_template": "请根据以下大纲和前文，续写小说正文：\n大纲：{outline}\n前文：{context}\n请继续："
                }
            }
        def get(self, key, default=None):
            keys = key.split('.')
            value = self.config
            for k in keys:
                if isinstance(value, dict):
                    value = value.get(k)
                else:
                    return default
            return value if value is not None else default

try:
    from core.logger import get_logger
except ImportError:
    def get_logger(name):
        logging.basicConfig(level=logging.DEBUG)
        return logging.getLogger(name)

# 异常定义
class BodyGenerationError(Exception):
    """正文生成异常"""
    pass

class BodyGenerator:
    """
    正文生成器
    负责执行一次正文生成请求，可插拔设计，通过配置切换模型和策略。
    """

    def __init__(self, config: ConfigManager = None):
        """
        初始化生成器
        :param config: 配置管理器实例，若未提供则使用默认配置
        """
        self.logger = get_logger(self.__class__.__name__)
        self.config = config if config else ConfigManager()
        self.model_name = self.config.get("generation.model_name", "default-model")
        self.max_tokens = self.config.get("generation.max_tokens", 2000)
        self.temperature = self.config.get("generation.temperature", 0.7)
        self.retry_count = self.config.get("generation.retry_count", 3)
        self.prompt_template = self.config.get("generation.prompt_template", 
                                               "Please continue writing the novel based on the following outline and context:\n{outline}\n{context}\n")
        # 模型协调器占位，后续通过依赖注入或工厂模式注入
        self.model_coordinator = None
        self.logger.info(f"BodyGenerator initialized with model={self.model_name}")

    def set_model_coordinator(self, coordinator):
        """
        设置模型协调器实例（依赖注入）
        :param coordinator: 实现了模型调用接口的协调器
        """
        self.model_coordinator = coordinator

    def generate(self, outline: str, context: str = "", extra_params: Dict[str, Any] = None) -> str:
        """
        生成正文核心方法
        :param outline: 当前章节的大纲或摘要
        :param context: 前文上下文，通常为之前生成的文本
        :param extra_params: 额外控制参数，可覆盖默认配置
        :return: 生成的正文文本
        :raises BodyGenerationError: 生成失败时抛出
        """
        self.logger.info(f"Starting body generation. Outline length: {len(outline)}, Context length: {len(context)}")
        
        # 生成提示词
        prompt