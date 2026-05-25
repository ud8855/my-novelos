# -*- coding: utf-8 -*-
"""
21_API模型/Gemini接口
模块职责：封装 Google Gemini API 的调用逻辑，对外提供统一接口。
所属层级：API模型层
依赖：
    - 21_API模型/（同级抽象基类或协议，待定义）
被调用者：上层模型协同模块（20_模型协同/），或任何需要通过Gemini生成文本的组件
解决：
    - 配置化管理 API Key、模型名称、请求参数等
    - 提供可插拔的接口，便于替换或Mock
    - 统一的日志记录与异常处理
    - 支持连接测试和重试机制（骨架阶段仅打印日志，不实现完整逻辑）
"""
import json
import logging
import os
from typing import Any, Dict, Optional

import requests  # 实际项目中需要安装 requests


class GeminiAPI:
    """Google Gemini API 的封装类（可插拔，未来可继承自 BaseAPIModel）"""

    def __init__(
        self,
        config_path: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        max_output_tokens: int = 2048,
        temperature: float = 0.7,
        top_p: float = 0.95,
    ):
        """
        初始化 GeminiAPI 实例。
        参数优先级：显式传入 > 配置文件 > 环境变量 GEMINI_API_KEY
        :param config_path: JSON 配置文件路径，支持从文件加载Api Key等参数
        :param api_key: 显式设置 API Key
        :param model_name: 模型名称，如 'gemini-2.0-flash-exp'
        :param max_output_tokens: 最大输出Token数
        :param temperature: 温度参数
        :param top_p: top_p 参数
        """
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._configured = False

        # 加载配置（如果提供了 config_path）
        config_data = self._load_config(config_path) if config_path else {}

        # 设置 API Key（优先级：参数 > 配置 > 环境 > 默认抛出异常）
        self.api_key = api_key or config_data.get("api_key") or os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("Gemini API Key 未提供，请通过参数、配置文件或环境变量 GEMINI_API_KEY 设置")

        # 设置模型名称
        self.model_name = model_name or config_data.get("model_name", "gemini-2.0-flash-exp")
        # 生成参数
        self.max_output_tokens = max_output_tokens
        self.temperature = temperature
        self.top_p = top_p

        # API 基础 URL（可根据需要调整）
        self.base_url = config_data.get("base_url", "https://generativelanguage.googleapis.com/v1beta")

        # 内部会话或请求相关
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

        self._configured = True
        self.logger.info(
            "GeminiAPI 初始化完成，模型: %s, max_output_tokens: %d, temperature: %.2f",
            self.model_name,
            self.max_output_tokens,
            self.temperature
        )

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """从 JSON 配置文件加载配置"""
        self.logger.debug("尝试加载配置文件: %s", config_path)
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.logger.debug("配置文件加载成功")
            return config
        except FileNotFoundError:
            self.logger.warning("配置文件未找到: %s，将使用环境变量或默认值", config_path)
            return {}
        except json.JSONDecodeError as e:
            self.logger.error("配置文件 JSON 解析错误: %s", e)
            return {}

    def health_check(self) -> bool:
        """
        检查 API 连接是否可用（骨架阶段仅模拟，实际项目中可发送简单请求测试）
        :return: 连接是否正常
        """
        self.logger.info("执行健康检查（占位实现）")
        # 实际可发送一个简单请求，例如列举模型
        # 这里直接返回 True
        return True

    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """
        使用 Gemini 生成文本（占位实现，未来完善实际调用逻辑）
        :param prompt: 提示文本
        :param kwargs: 可覆盖的生成参数（如 temperature, max_output_tokens）
        :return: 生成的文本（失败时返回 None）
        """
        self.logger.info("调用 generate，prompt 长度: %d", len(prompt) if prompt else 0)
        # 合并参数：实例默认值可以被 kwargs 覆盖
        request_params = {
            "model": self.model_name,
            "maxOutputTokens": kwargs.get("max_output_tokens", self.max_output_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "topP": kwargs.get("top_p", self.top_p),
        }

        # 构建请求体（根据 Gemini API 格式）
        request_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": request_params,
        }

        url = f"{self.base_url}/models/{self.model_name}:generateContent?key={self.api_key}"

        try:
            # 在骨架阶段不真正发送请求，仅模拟日志记录
            self.logger.debug("模拟发送请求到 %s", url)
            # response = self._session.post(url, json=request_body)
            # response.raise_for_status()
            # data = response.json()
            # 返回占位结果
            self.logger.info("generate 调用成功（模拟）")
            return "[Gemini 占位回复] 这是一段由 Gemini 模型生成的示例文本。"
        except requests.RequestException as e:
            self.logger.error("Gemini API 请求失败: %s", e)
            return None
        except Exception as e:
            self.logger.exception("未预料的异常: %s", e)
            return None

    def close(self):
        """关闭底层会话（可选）"""
        if self._session:
            self._session.close()
            self.logger.debug("HTTP 会话已关闭")


if __name__ == '__main__':
    # 自测：使用骨架进行简单实例化和模拟调用
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    print("===== Gemini接口自测 (骨架) =====")
    try:
        # 使用环境变量或显式设置 key 进行测试，这里为便于演示使用占位 key
        # 请在实际使用时替换为有效 key
        client = GeminiAPI(api_key="fake-test-key-123")
        print(f"健康检查结果: {client.health_check()}")

        response = client.generate("Hello, what is NovelOS?")
        print(f"生成回复: {response}")
    except Exception as e:
        print(f"自测过程中出现错误: {e}")
    finally:
        if 'client' in locals():
            client.close()