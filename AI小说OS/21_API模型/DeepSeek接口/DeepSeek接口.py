from __future__ import annotations

import abc
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ----------------------------------------------------------------------
# 日志配置 (可插拔：默认使用模块级 logger，外部可替换)
# ----------------------------------------------------------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    # 避免重复添加 handler
    _console_handler = logging.StreamHandler()
    _console_handler.setLevel(logging.DEBUG)
    _formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    _console_handler.setFormatter(_formatter)
    logger.addHandler(_console_handler)
    logger.setLevel(logging.INFO)


# ----------------------------------------------------------------------
# 配置数据类 (配置化：所有可调参数均从此处读取)
# ----------------------------------------------------------------------
@dataclass
class DeepSeekConfig:
    """
    DeepSeek 接口配置参数。
    可从环境变量、配置文件或显式参数初始化。
    """
    api_key: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", "")
    )
    api_base: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
    )
    model_name: str = "deepseek-chat"
    max_tokens: int = 2048
    temperature: float = 0.7
    top_p: float = 0.9
    timeout: int = 30
    retry_count: int = 3

    def validate(self) -> bool:
        """校验必要配置项是否存在"""
        if not self.api_key:
            logger.error("Missing DeepSeek API key")
            return False
        return True


# ----------------------------------------------------------------------
# 基础客户端抽象 (可插拔：任何模型调用者都依赖此抽象)
# ----------------------------------------------------------------------
class BaseModelClient(abc.ABC):
    """
    模型客户端接口，所有第三方 API 实现必须继承此类。
    上层模块（如 20_模型协同）只会依赖此抽象，
    不与具体实现耦合，实现热插拔。
    """

    @abc.abstractmethod
    def initialize(self, config: Any) -> None:
        """根据配置初始化客户端，建立连接/验证等"""
        ...

    @abc.abstractmethod
    def shutdown(self) -> None:
        """优雅关闭客户端，释放资源"""
        ...

    @abc.abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        以文本生成方式调用模型。

        参数：
            prompt: 输入提示词
            **kwargs: 额外生成参数
        返回：
            模型生成的文本
        """
        ...


# ----------------------------------------------------------------------
# DeepSeek 客户端实现
# ----------------------------------------------------------------------
class DeepSeekClient(BaseModelClient):
    """
    DeepSeek API 客户端实现。

    遵循 BaseModelClient 接口，允许由 Runtime 动态加载或卸载。
    内部使用 HTTP 客户端（可替换，默认使用 requests 库）与 API 通信。
    """

    def __init__(self) -> None:
        self.config: Optional[DeepSeekConfig] = None
        self._http_session: Any = None   # 实际使用时应为 requests.Session / aiohttp 等
        self._is_initialized: bool = False
        logger.debug("DeepSeekClient instance created (not initialized).")

    # ----- 初始化与销毁 -----
    def initialize(self, config: Any) -> None:
        """
        加载配置并准备客户端。
        参数 config 可直接为 DeepSeekConfig 实例，或 dict（将转为 DeepSeekConfig）。
        """
        if isinstance(config, dict):
            self.config = DeepSeekConfig(**config)
        elif isinstance(config, DeepSeekConfig):
            self.config = config
        else:
            raise TypeError("config must be dict or DeepSeekConfig instance")

        if not self.config.validate():
            raise ValueError("DeepSeekConfig validation failed")

        # 建立 HTTP 会话（占位：实际项目中创建 requests.Session()）
        # self._http_session = requests.Session()
        # self._http_session.headers.update({"Authorization": f"Bearer {self.config.api_key}"})
        self._is_initialized = True
        logger.info("DeepSeek client initialized with model '%s'.", self.config.model_name)

    def shutdown(self) -> None:
        """关闭会话并释放资源"""
        # if self._http_session:
        #     self._http_session.close()
        self._is_initialized = False
        logger.info("DeepSeek client shutdown.")

    # ----- 核心生成接口 -----
    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        向 DeepSeek API 发送请求并返回结果。

        参数：
            prompt: 用户输入文本
            **kwargs: 可覆盖配置中的参数（如 temperature, max_tokens 等）
        返回：
            生成文本
        """
        if not self._is_initialized:
            raise RuntimeError("DeepSeekClient not initialized. Call initialize() first.")

        # 合并参数：以 kwargs 优先
        generation_params = {
            "model": self.config.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "top_p": kwargs.get("top_p", self.config.top_p),
            # 其他参数可扩展
        }

        logger.debug("Sending request to DeepSeek with prompt len=%d", len(prompt))

        # ---- 实际调用部分（占位逻辑，演示可插拔性）----
        # 这里应当发送 HTTP 请求并处理响应，此处用模拟返回替代
        try:
            # response = self._http_session.post(
            #     f"{self.config.api_base}/chat/completions",
            #     json=generation_params,
            #     timeout=self.config.timeout,
            # )
            # response.raise_for_status()
            # data = response.json()
            # result = data["choices"][0]["message"]["content"]

            # 占位模拟
            logger.warning("Using mock response – replace with real API call.")
            time.sleep(0.5)  # 模拟延迟
            result = f"[Mock DeepSeek response] Prompt was: '{prompt[:50]}...'"

            logger.info("Generation successful, output length=%d", len(result))
            return result

        except Exception as exc:  # 实际应捕获具体异常（网络、API错误等）
            logger.error("DeepSeek API call failed: %s", exc)
            # 异常恢复、重试等逻辑可在此处添加（配置化重试）
            # 简单重新抛出，上层需处理
            raise exc

    # ----- 扩展工具方法 (可选) -----
    def health_check(self) -> bool:
        """
        快速检查 API 可用性。
        返回 True 表示接口可达。
        """
        if not self._is_initialized:
            return False
        # 可发送一个轻量请求或只验证连接
        return True


# ----------------------------------------------------------------------
# 自测代码 (仅当直接执行此模块时运行)
# ----------------------------------------------------------------------
if __name__ == "__main__":
    # 设置测试日志级别
    logger.setLevel(logging.DEBUG)

    print("=== DeepSeek Client Self-Test ===")

    # 1. 使用假配置进行初始化
    test_config = DeepSeekConfig(
        api_key="sk-test-fake",
        api_base="https://api.deepseek.com/v1",
        model_name="deepseek-chat",
        max_tokens=100,
    )

    client = DeepSeekClient()
    try:
        client.initialize(test_config)
        assert client._is_initialized, "Client should be initialized"

        # 2. 测试生成（模拟）
        prompt = "你好，请写一首关于春天的诗。"
        response = client.generate(prompt)
        print(f"Generated response:\n{response}\n")

        # 3. 测试配置覆盖
        response2 = client.generate("Summary test", temperature=0.3, max_tokens=50)
        print(f"Generated with overrides:\n{response2}\n")

        # 4. 测试关闭
        client.shutdown()
        assert not client._is_initialized, "Client should be shutdown"

        print("All tests passed.")
    except Exception as e:
        logger.exception("Test failed")
        print("Test failed with exception:", e)