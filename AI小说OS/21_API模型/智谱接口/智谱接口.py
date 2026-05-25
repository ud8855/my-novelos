"""智谱接口模块 (Zhipu Interface)
功能: 封装智谱AI API调用，提供统一的模型接口。
所属层: API模型层 (21_API模型)
依赖: 20_模型协同 基类，配置系统，日志系统
被调用: 20_模型协同 模型管理器
解决: 隔离不同AI提供商的接口差异，实现可插拔调用
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List, Iterator
from dataclasses import dataclass, field

# 假设存在以下基类接口（来自20_模型协同）
# 若实际模块路径不同，请调整导入
try:
    from twentieth_model_collaboration.base import BaseModelClient, ModelConfig, ModelResponse, ModelStreamResponse
except ImportError:
    # 抽象基类定义，仅供骨架参考，实际开发时应基于真实基类实现
    class BaseModelClient:
        """模型客户端基类"""
        def __init__(self, config: 'ModelConfig'):
            self.config = config
            self.logger = logging.getLogger(self.__class__.__name__)

        def generate(self, messages: List[Dict[str, Any]], **kwargs) -> 'ModelResponse':
            raise NotImplementedError

        def stream_generate(self, messages: List[Dict[str, Any]], **kwargs) -> Iterator['ModelStreamResponse']:
            raise NotImplementedError

    @dataclass
    class ModelConfig:
        provider: str = "zhipu"
        api_key: str = ""
        model_name: str = "glm-4"
        endpoint: str = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
        temperature: float = 0.7
        max_tokens: int = 2048
        extra: Dict[str, Any] = field(default_factory=dict)

    @dataclass
    class ModelResponse:
        content: str
        usage: Dict[str, int] = field(default_factory=dict)
        finish_reason: str = ""
        extra: Dict[str, Any] = field(default_factory=dict)

    @dataclass
    class ModelStreamResponse:
        delta_content: str
        usage: Optional[Dict[str, int]] = None
        finish_reason: Optional[str] = None
        extra: Dict[str, Any] = field(default_factory=dict)


class ZhipuInterfaceClient(BaseModelClient):
    """智谱AI API客户端，实现可插拔模型调用"""
    
    def __init__(self, config: ModelConfig):
        super().__init__(config)
        self._validate_config()

    def _validate_config(self):
        """验证并补充配置"""
        if not self.config.api_key:
            # 尝试从环境变量读取
            self.config.api_key = os.environ.get("ZHIPU_API_KEY", "")
            if not self.config.api_key:
                raise ValueError("Zhipu API key not found in config or environment variable ZHIPU_API_KEY")
        self.logger.info("智谱客户端初始化完成，模型: %s", self.config.model_name)

    def _build_request_body(self, messages: List[Dict[str, Any]], **kwargs) -> Dict[str, Any]:
        """构建请求体，支持配置与运行时覆盖"""
        body = {
            "model": self.config.model_name,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "stream": False,
            **self.config.extra,
            **kwargs.get("extra", {})
        }
        # 移除不被支持的参数
        body = {k: v for k, v in body.items() if v is not None}
        return body

    def _send_request(self, body: Dict[str, Any], stream: bool = False) -> Any:
        """实际发送HTTP请求（占位，后续实现）"""
        # 使用 requests / httpx 等库，此处骨架预留
        raise NotImplementedError("网络请求逻辑待实现")

    def generate(self, messages: List[Dict[str, Any]], **kwargs) -> ModelResponse:
        """同步生成回复"""
        self.logger.debug("同步调用智谱API，消息条数: %d", len(messages))
        body = self._build_request_body(messages, **kwargs)
        raw_response = self._send_request(body, stream=False)
        # 解析响应，返回ModelResponse（骨架直接返回占位）
        # 解析逻辑待实现
        return ModelResponse(
            content="[占位] 智谱生成内容",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            finish_reason="stop"
        )

    def stream_generate(self, messages: List[Dict[str, Any]], **kwargs) -> Iterator[ModelStreamResponse]:
        """流式生成回复"""
        self.logger.debug("流式调用智谱API，消息条数: %d", len(messages))
        body = self._build_request_body(messages, **kwargs)
        body["stream"] = True
        # 流式传输待实现
        yield from []  # 占位空生成器

    def health_check(self) -> bool:
        """检查接口是否可用"""
        # 可进行简单的连通性测试
        return bool(self.config.api_key)


# ---------- 配置化加载 ----------
def load_config_from_env() -> ModelConfig:
    """从环境变量加载配置"""
    return ModelConfig(
        api_key=os.environ.get("ZHIPU_API_KEY", ""),
        model_name=os.environ.get("ZHIPU_MODEL_NAME", "glm-4"),
        endpoint=os.environ.get("ZHIPU_ENDPOINT", "https://open.bigmodel.cn/api/paas/v4/chat/completions"),
        temperature=float(os.environ.get("ZHIPU_TEMPERATURE", "0.7")),
        max_tokens=int(os.environ.get("ZHIPU_MAX_TOKENS", "2048")),
    )


# ---------- 自测代码 ----------
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("ZhipuInterfaceTest")

    # 加载配置（测试时请设置环境变量 ZHIPU_API_KEY）
    try:
        config = load_config_from_env()
        client = ZhipuInterfaceClient(config)
        logger.info("客户端创建成功，健康检查: %s", client.health_check())

        # 模拟调用（由于网络请求未实现，仅验证骨架）
        test_messages = [{"role": "user", "content": "你好"}]
        logger.info("开始同步调用测试...")
        response = client.generate(test_messages)
        logger.info("同步响应: %s", response)

        logger.info("开始流式调用测试...")
        for chunk in client.stream_generate(test_messages):
            logger.info("流式块: %s", chunk)

    except Exception as e:
        logger.error("自测失败: %s", str(e))