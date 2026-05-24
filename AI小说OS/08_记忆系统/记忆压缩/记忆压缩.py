import logging
import abc
from typing import Any, Dict, Optional


class MemoryCompressionConfig:
    """
    记忆压缩模块配置
    支持通过字典初始化，后续可扩展从文件或环境变量加载
    """
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        # 默认配置
        self.max_length: int = 2000          # 最大压缩后长度（字符数）
        self.compression_method: str = 'simple'  # 压缩方式：simple, llm_summary 等
        self.enable_logging: bool = True
        self.log_level: str = 'INFO'
        self.llm_model_name: str = 'gpt-3.5-turbo'  # 若使用LLM压缩，模型名
        self.llm_endpoint: str = ''          # LLM调用端点（由上层注入）
        # 从传入字典覆盖默认值
        if config_dict:
            self.__dict__.update(config_dict)


def setup_logging(config: MemoryCompressionConfig) -> None:
    """根据配置初始化日志系统"""
    if config.enable_logging:
        level = getattr(logging, config.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        logging.disable(logging.CRITICAL)


class BaseMemoryCompressor(abc.ABC):
    """记忆压缩器抽象基类，所有压缩器必须实现compress方法"""

    @abc.abstractmethod
    def compress(self, memory_data: Any, **kwargs) -> Any:
        """
        对记忆数据进行压缩
        :param memory_data: 原始记忆（可以是字符串、字典、列表等）
        :param kwargs: 额外参数
        :return: 压缩后的记忆表示
        """
        ...


class SimpleMemoryCompressor(BaseMemoryCompressor):
    """简单的截断压缩器，仅用于示例和测试"""

    def __init__(self, config: MemoryCompressionConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    def compress(self, memory_data: Any, **kwargs) -> str:
        """
        将输入转换为字符串后按配置的最大长度截断
        """
        raw_str = str(memory_data)
        self.logger.info("开始压缩记忆，原始长度: %d", len(raw_str))
        compressed = raw_str[:self.config.max_length]
        self.logger.debug("压缩后长度: %d", len(compressed))
        return compressed


class LLMSummaryCompressor(BaseMemoryCompressor):
    """基于大模型的摘要压缩器（骨架，不实现实际调用）"""

    def __init__(self, config: MemoryCompressionConfig):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        # 此处预留模型客户端接口，由上层 20_模型协同 注入
        self.llm_client = None

    def set_llm_client(self, client):
        """设置符合协议的LLM客户端（由上层注入）"""
        self.llm_client = client

    def compress(self, memory_data: Any, **kwargs) -> str:
        """
        调用LLM进行摘要压缩
        实际骨架只模拟流程，记录日志
        """
        self.logger.info("LLM摘要压缩开始，原始长度: %d", len(str(memory_data)))
        if self.llm_client is None:
            self.logger.warning("LLM客户端未注入，返回原始文本截断")
            return str(memory_data)[:self.config.max_length]

        # 模拟调用流程（实际应由 20_模型协同 处理）
        prompt = f"请将以下内容压缩为简洁摘要，限制{self.config.max_length}字符：\n{memory_data}"
        # response = self.llm_client.call(self.config.llm_model_name, prompt)
        # 暂时返回截断
        compressed = str(memory_data)[:self.config.max_length]
        self.logger.debug("压缩完成，长度: %d", len(compressed))
        return compressed


class MemoryCompressionManager:
    """
    记忆压缩管理器
    负责根据配置创建压缩器实例，提供统一的压缩接口，并处理异常与日志
    """

    def __init__(self, config: MemoryCompressionConfig):
        setup_logging(config)
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
        self.compressor: BaseMemoryCompressor = self._create_compressor()

    def _create_compressor(self) -> BaseMemoryCompressor:
        """
        工厂方法，根据配置返回对应的压缩器实例
        所有压缩器必须继承 BaseMemoryCompressor
        """
        method = self.config.compression_method.lower()
        if method == 'simple':
            return SimpleMemoryCompressor(self.config)
        elif method == 'llm_summary':
            compressor = LLMSummaryCompressor(self.config)
            # 实际环境中需要通过依赖注入设置 LLM 客户端
            # compressor.set_llm_client(...)
            return compressor
        else:
            self.logger.warning("未知压缩方式 '%s'，回退到simple", method)
            return SimpleMemoryCompressor(self.config)

    def compress(self, memory_data: Any) -> Any:
        """
        执行记忆压缩，统一入口
        :param memory_data: 原始记忆数据
        :return: 压缩后的记忆数据
        """
        try:
            result = self.compressor.compress(memory_data)
            self.logger.info("记忆压缩成功")
            return result
        except Exception as e:
            self.logger.exception("记忆压缩过程发生异常")
            raise


# ----------------------------------------------------------------------
# 自测代码
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # 构建配置
    test_config = MemoryCompressionConfig({
        'max_length': 100,
        'compression_method': 'simple',
        'log_level': 'DEBUG'
    })

    # 初始化压缩管理器
    manager = MemoryCompressionManager(test_config)

    # 模拟一段长记忆
    sample_memory = (
        "这是一段非常长的角色记忆文本，包含了大量关于世界观、人物关系、"
        "事件前因后果的详细描述。" * 30
    )
    print("原始记忆长度:", len(sample_memory))

    # 执行