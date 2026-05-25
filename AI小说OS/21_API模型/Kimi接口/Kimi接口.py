"""
Kimi API 接口模块
负责与 Moonshot AI 的 Kimi 大模型进行交互，提供文本生成能力。
依赖：20_模型协同/ （可能在未来需要协同） 和 配置系统、日志系统
被调用者：上层业务逻辑（如 Agent 或推理引擎）
解决：统一封装 Kimi API 的调用、重试、流式处理、错误处理等
"""

import logging
import time
from typing import Optional, Dict, Any, Generator

# 假设的配置和基类导入，实际开发时需要根据项目实现调整
from novel_os.config import get_config  # 假设存在配置模块
from novel_os.api.base import BaseAPIModel  # 假设存在基类

class KimiAPI(BaseAPIModel):
    """
    Kimi API 封装类，提供非流式和流式文本生成接口。
    所有功能支持热更新（通过配置重新加载）、异常恢复、日志记录。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化 Kimi API 客户端。
        :param config: 可选的配置字典，若不提供则从全局配置加载。
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self._config = config or self._load_config()
        self._api_key = self._config.get('kimi_api_key', '')
        self._api_base = self._config.get('kimi_api_base', 'https://api.moonshot.cn/v1')
        self._model = self._config.get('kimi_model', 'moonshot-v1-8k')
        self._max_retries = self._config.get('kimi_max_retries', 3)
        self._timeout = self._config.get('kimi_timeout', 30)
        self._logger.info("KimiAPI 初始化完成，model=%s", self._model)

    def _load_config(self) -> Dict[str, Any]:
        """从全局配置加载 Kimi 相关配置。"""
        # TODO: 实现从配置中心获取配置
        cfg = get_config().get('kimi', {})
        self._logger.debug("加载 Kimi 配置: %s", cfg)
        return cfg

    def reload_config(self):
        """热重载配置，支持无需重启更新参数。"""
        self._logger.info("重新加载 Kimi 配置...")
        self._config = self._load_config()
        self._api_key = self._config.get('kimi_api_key', '')
        self._api_base = self._config.get('kimi_api_base', 'https://api.moonshot.cn/v1')
        self._model = self._config.get('kimi_model', 'moonshot-v1-8k')
        self._max_retries = self._config.get('kimi_max_retries', 3)
        self._timeout = self._config.get('kimi_timeout', 30)
        self._logger.info("Kimi 配置重载完成")

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头。"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}"
        }

    def _build_request_body(self, messages: list, stream: bool = False, **kwargs) -> Dict[str, Any]:
        """构建请求体。"""
        body = {
            "model": self._model,
            "messages": messages,
            "stream": stream,
        }
        # 允许覆盖参数
        for key in ['temperature', 'top_p', 'n', 'max_tokens', 'stop']:
            if key in kwargs:
                body[key] = kwargs[key]
        return body

    def _handle_response(self, response: Any) -> Any:
        """处理非流式响应，提取文本内容。"""
        # TODO: 根据实际 API 响应格式解析
        try:
            resp_json = response.json()
            # 假设格式 {"choices": [{"message": {"content": "..."}}]}
            return resp_json["choices"][0]["message"]["content"]
        except Exception as e:
            self._logger.error("解析 Kimi 响应失败: %s", e)
            raise

    def _handle_stream(self, response: Any) -> Generator[str, None, None]:
        """处理流式响应，逐个产出文本块。"""
        # TODO: 实现流式解析
        for line in response.iter_lines():
            if line:
                # 解析 SSE 数据
                try:
                    data = line.decode("utf-8")
                    if data.startswith("data: "):
                        data = data[6:]
                        if data != "[DONE]":
                            import json
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                except Exception as e:
                    self._logger.warning("流