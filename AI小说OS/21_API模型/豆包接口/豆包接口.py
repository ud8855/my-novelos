# -*- coding: utf-8 -*-
"""
豆包接口
功能：封装豆包大模型API的请求与响应处理，实现可插拔的模型调用。
所属层：21_API模型
依赖：requests, json, logging, configparser (或内置配置)
被调用者：20_模型协同（通过统一接口调用）
设计原则：单一职责、可热插拔、异常恢复、日志记录、配置化
"""
import json
import logging
import time
from typing import Dict, Any, Optional

import requests

# 配置化：一般从配置文件读取，这里提供默认值
class DouBaoConfig:
    """豆包接口配置"""
    def __init__(self, config_dict: Dict[str, Any] = None):
        # 默认配置
        self.api_url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
        self.api_key = ""
        self.model_name = "doubao-pro-32k"
        self.max_tokens = 4096
        self.temperature = 0.7
        self.top_p = 0.9
        self.timeout = 60
        self.max_retries = 3
        self.retry_delay = 1
        # 如果有外部配置，覆盖默认
        if config_dict:
            for key, value in config_dict.items():
                if hasattr(self, key):
                    setattr(self, key, value)

class DouBaoInterface:
    """
    豆包API调用接口
    职责：处理请求构建、发送、重试、异常处理、日志记录，返回统一格式响应。
    """

    def __init__(self, config: Optional[DouBaoConfig] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        if config is None:
            self.config = DouBaoConfig()
        else:
            self.config = config
        # 验证必要参数
        if not self.config.api_key:
            self.logger.warning("API key 未配置，豆包接口将无法正常工作。")

    def _build_payload(self, messages: list, system_prompt: str = "", **kwargs) -> Dict[str, Any]:
        """构建请求体"""
        # 完整消息列表
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        payload = {
            "model": self.config.model_name,
            "messages": all_messages,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "top_p": kwargs.get("top_p", self.config.top_p),
        }
        # 可选参数
        if "stop" in kwargs:
            payload["stop"] = kwargs["stop"]
        if "stream" in kwargs:
            payload["stream"] = kwargs["stream"]
        return payload

    def _send_request(self, payload: Dict[str, Any]) -> requests.Response:
        """发送HTTP请求，带重试机制"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }
        session = requests.Session()
        last_exception = None
        for attempt in range(self.config.max_retries):
            try:
                self.logger.debug(f"第 {attempt+1} 次尝试发送请求到 {self.config.api_url}")
                response = session.post(
                    self.config.api_url,
                    headers=headers,
                    json=payload,
                    timeout=self.config.timeout,
                )
                # 检查HTTP状态码
                if response.status_code == 200:
                    return response
                else:
                    self.logger.warning(f"API返回非200状态码: {response.status_code}, body: {response.text}")
                    # 如果是客户端错误（4xx），不重试直接抛出
                    if 400 <= response.status_code < 500:
                        raise requests.exceptions.HTTPError(f"客户端错误: {response.status_code}")
                    # 服务器错误可能重试
                    raise requests.exceptions.HTTPError(f"服务器错误: {response.status_code}")
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, requests.exceptions.HTTPError) as e:
                last_exception = e
                self.logger.error(f"请求失败: {e}")
                if attempt < self.config.max_retries - 1:
                    sleep_time = self.config.retry_delay * (2 ** attempt)
                    self.logger.info(f"等待 {sleep_time} 秒后重试...")
                    time.sleep(sleep_time)
                else:
                    self.logger.error("达到最大重试次数，请求失败。")
        raise last_exception

    def _parse_response(self, response: requests.Response) -> Dict[str, Any]:
        """解析响应，提取必要信息"""
        try:
            result = response.json()
            # 标准OpenAI格式兼容
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0].get("message", {}).get("content", "")
                finish_reason = result["choices"][0].get("finish_reason", "stop")
                usage = result.get("usage", {})
                return {
                    "success": True,
                    "content": content,
                    "finish_reason": finish_reason,
                    "usage": usage,
                    "raw_response": result
                }
            else:
                self.logger.warning(f"响应格式解析异常: {result}")
                return {
                    "success": False,
                    "error": "响应结构无choices",
                    "raw_response": result
                }
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {e}")
            return {
                "success": False,
                "error": f"JSON解析失败: {str(e)}",
                "raw_response": response.text
            }
        except Exception as e:
            self.logger.error(f"响应解析未知错误: {e}")
            return {
                "success": False,
                "error": str(e),
                "raw_response": None
            }

    def chat(self, messages: list, system_prompt: str = "", **kwargs) -> Dict[str, Any]:
        """
        同步对话接口
        :param messages: 对话历史，格式 [{"role":"user","content":"..."}]
        :param system_prompt: 系统提示
        :param kwargs: 其他参数，如temperature等
        :return: dict {
            "success": bool,
            "content": str,   # 模型回复文本
            "finish_reason": str,
            "usage": dict,
            "raw_response": dict
        }
        """
        self.logger.info(f"开始调用豆包模型: model={self.config.model_name}, messages count={len(messages)}")
        try:
            payload = self._build_payload(messages, system_prompt, **kwargs)
            response = self._send_request(payload)
            return self._parse_response(response)
        except Exception as e:
            self.logger.error(f"豆包接口调用异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "content": None,
                "raw_response": None
            }

    def test_connectivity(self) -> bool:
        """
        自测：发送一个简单消息，检查接口是否连通
        """
        test_messages = [{"role": "user", "content": "Hello, are you working?"}]
        ret = self.chat(test_messages, system_prompt="你是一个测试助手。")
        if ret["success"]:
            self.logger.info("豆包接口自测成功。")
            return True
        else:
            self.logger.error(f"豆包接口自测失败: {ret.get('error')}")
            return False

# 自测代码（当模块直接运行时执行）
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger = logging.getLogger("DouBaoTest")
    # 读取配置（这里演示从环境变量或直接指定）
    import os
    api_key = os.getenv("DOUBAO_API_KEY", "")
    if not api_key:
        logger.warning("没有设置DOUBAO_API_KEY环境变量，自测可能失败。")
    # 创建配置对象
    config = DouBaoConfig({
        "api_key": api_key,
        "model_name": "doubao-lite-32k"  # 使用一个通用模型
    })
    interface = DouBaoInterface(config)
    ok = interface.test_connectivity()
    if ok:
        logger.info("自测通过")
    else:
        logger.error("自测未通过")