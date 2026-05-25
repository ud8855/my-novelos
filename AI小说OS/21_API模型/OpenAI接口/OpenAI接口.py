"""
OpenAI API 接口实现模块
路径：21_API模型/OpenAI接口/OpenAI接口.py
功能：封装 OpenAI API 调用，提供统一模型接口，支持配置化、日志、热插拔
依赖：Common.config_manager (配置获取)
被调用：20_模型协同/ 中的模型管理器
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

# 尝试导入 openai，如果不存在则警告
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# 假设的配置模块，可根据实际调整
try:
    from Common.config_manager import get_config
except ImportError:
    # 简易模拟配置，用于自测
    def get_config(section, key, default=None):
        return default

logger = logging.getLogger(__name__)


class ModelAPI(ABC):
    """
    模型API抽象基类，定义了统一的模型调用接口。
    所有具体API实现（如OpenAI、Claude等）必须继承此类。
    """
    @abstractmethod
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """
        同步生成文本
        :param prompt: 用户提示词
        :param system_prompt: 系统提示词
        :param kwargs: 其他模型参数
        :return: 生成的文本
        """
        pass

    @abstractmethod
    def stream_generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs):
        """
        流式生成文本，返回生成器
        :param prompt: 用户提示词
        :param system_prompt: 系统提示词
        :param kwargs: 其他模型参数
        :yield: 文本块
        """
        pass

    @abstractmethod
    def get_embedding(self, text: str, **kwargs) -> List[float]:
        """
        获取文本嵌入向量
        :param text: 输入文本
        :param kwargs: 其他参数
        :return: 嵌入向量列表
        """
        pass


class OpenAIModelAPI(ModelAPI):
    """
    OpenAI API 的具体实现
    支持配置化：从配置中心获取 API Key, Base URL, 默认模型等
    支持日志记录
    可插拔：遵循 ModelAPI 接口，可被其他 API 实现替换
    """
    def __init__(self):
        self.api_key = get_config("OpenAI", "api_key", default=None)
        self.base_url = get_config("OpenAI", "base_url", default="https://api.openai.com/v1")
        self.default_model = get_config("OpenAI", "default_model", default="gpt-3.5-turbo")
        if OPENAI_AVAILABLE:
            openai.api_key = self.api_key
            openai.base_url = self.base_url
            logger.info("OpenAI API 初始化完成，模型: %s, base_url: %s", self.default_model, self.base_url)
        else:
            logger.warning("未安装 openai 库，无法使用 OpenAI API，请安装：pip install openai")

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> str:
        """
        调用 OpenAI ChatCompletion 接口生成文本
        """