import logging
import os
from typing import Dict, Any, Optional, Union, List

# 假设存在基础配置模块，这里简化处理
# 在实际系统中，会从 04_全局配置 导入配置管理器
try:
    from config import Config  # 假设存在
except ImportError:
    class Config:
        """简易配置占位符，实际请从配置系统获取"""
        @staticmethod
        def get(key: str, default=None):
            return os.getenv(key, default)

logger = logging.getLogger(__name__)

class GrokAPI:
    """
    Grok模型API接口封装
    职责：将上层请求转换为Grok API调用，返回标准化结果
    依赖：外部HTTP请求库 (如 requests 或 aiohttp)
    被调用：20_模型协同 / 其他需要调用Grok模型的模块
    可插拔：通过统一接口，可替换为其他模型API类
    """

    # ---------- 配置常量 (可从Config注入) ----------
    DEFAULT_MODEL = "grok-beta"  # 默认模型名称
    DEFAULT_API_URL = "https://api.x.ai/v1/chat/completions"  # API端点
    DEFAULT_MAX_TOKENS = 1024
    DEFAULT_TEMPERATURE = 0.7

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, **kwargs):
        """
        初始化Grok API客户端
        
        参数:
            api_key: xAI的API密钥，若不提供则从配置或环境变量读取
            model: 使用的模型标识，默认从配置读取
            **kwargs: 其他可能配置 (如base_url, timeout等)
        """
        # 从配置/环境变量加载默认值
        self.api_key = api_key or Config.get("XAI_API_KEY")
        if not self.api_key:
            raise ValueError("Grok API key 缺失，请设置 XAI_API_KEY 环境变量或配置项")
        
        self.model = model or Config.get("GROK_MODEL", self.DEFAULT_MODEL)
        self.api_url = kwargs.get("api_url") or Config.get("GROK_API_URL", self.DEFAULT_API_URL)
        self.timeout = kwargs.get("timeout") or int(Config.get("GROK_REQUEST_TIMEOUT", "30"))
        self.max_retries = kwargs.get("max_retries") or int(Config.get("GROK_MAX_RETRIES", "3"))
        
        # 日志记录初始化信息
        logger.info(f"GrokAPI 初始化完成，模型={self.model}, URL={self.api_url}")
        
        # 这里可以初始化HTTP会话 (若使用requests.Session或aiohttp.ClientSession)
        # 为骨架清晰，暂时省略HTTP客户端初始化
        
    def _prepare_headers(self) -> Dict[str, str]:
        """构建请求头"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
    
    def _build_payload(self, prompt: Union[str, List[Dict[str, str]]], 
                       system_prompt: Optional[str] = None,
                       max_tokens: Optional[int] = None,
                       temperature: Optional[float] = None,
                       **kwargs) -> Dict[str, Any]:
        """
        构建API请求体
        
        参数:
            prompt: 用户输入，可以是字符串或OpenAI格式的消息列表
            system_prompt: 系统提示词，若提供则添加到消息列表首位
            max_tokens: 最大生成token数，默认使用配置值
            temperature: 采样温度
            **kwargs: 其他模型参数 (top_p, stop等)
        """
        if isinstance(prompt, str):
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
        elif isinstance(prompt, list):
            messages = prompt  # 直接使用消息列表
            if system_prompt:
                # 插入系统消息(如果列表中没有)
                if not any(m.get("role") == "system" for m in messages):
                    messages.insert(0, {"role": "system", "content": system_prompt})
        else:
            raise TypeError("prompt 必须是字符串或消息列表")
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.DEFAULT_MAX_TOKENS,
            "temperature": temperature or self.DEFAULT_TEMPERATURE,
            **kwargs  # 允许传入额外参数，如 top_p, stop 等
        }
        logger.debug(f"构建请求体: {payload}")
        return payload
    
    def _call_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行实际的API调用 (同步版本)
        这里使用占位逻辑，实际需替换为 requests.post 等
        """
        # TODO: 实际实现应包含重试、超时、异常处理
        logger.warning("GrokAPI._call_api 尚未实现实际HTTP调用，返回模拟数据")
        # 模拟返回结构
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": f"这是模拟Grok的回答，基于提示: {payload['messages'][-1]['content'][:30]}..."
                    }
                }
            ],
            "usage": {"total_tokens": 100}
        }
    
    def generate(self, prompt: Union[str, List[Dict[str, str]]], 
                 system_prompt: Optional[str] = None,
                 **kwargs) -> Dict[str, Any]:
        """
        生成回复 (主接口)
        
        参数:
            prompt: 用户提示词或消息列表
            system_prompt: 系统提示词
            **kwargs: 覆盖默认生成参数 (max_tokens, temperature, top_p, stop...)
        
        返回:
            标准化响应字典:
            {
                "content": str,          # 模型回复文本
                "usage": {...},          # token使用情况
                "model": str,            # 实际使用的模型名
                "raw_response": {...}     # 原始API响应，便于调试
            }
        """
        # 分离参数
        max_tokens = kwargs.pop('max_tokens', None)
        temperature = kwargs.pop('temperature', None)
        
        # 构建请求负载
        payload = self._build_payload(prompt, system_prompt, max_tokens, temperature, **kwargs)
        
        # 执行调用 (带重试逻辑可在内部实现)
        try:
            response = self._call_api(payload)
        except Exception as e:
            logger.error(f"Grok API调用失败: {e}", exc_info=True)
            # 可在此处实现自定义异常转换或回退策略
            raise
        
        # 提取文本
        choices = response.get("choices", [])
        if not choices:
            raise ValueError("API响应未包含任何choices")
        content = choices[0].get("message", {}).get("content", "")
        
        # 记录使用情况
        usage = response.get("usage", {})
        logger.info(f"Grok调用成功, 消耗token: {usage.get('total_tokens', 'N/A')}")
        
        return {
            "content": content,
            "usage": usage,
            "model": self.model,
            "raw_response": response
        }
    
    async def async_generate(self, prompt: Union[str, List[Dict[str, str]]], 
                             system_prompt: Optional[str] = None,
                             **kwargs) -> Dict[str, Any]:
        """
        异步生成接口 (暂未实现)
        为将来异步框架预留，调用异步HTTP客户端
        """
        # TODO: 实现异步版本
        logger.warning("async_generate 方法尚未实现，请使用同步版本")
        return self.generate(prompt, system_prompt, **kwargs)
    
    def health_check(self) -> bool:
        """
        快速检查API可用性，可发送最小化请求测试连通性
        这里返回模拟结果
        """
        logger.info("执行Grok健康检查 (模拟)")
        return True


# ------------------ 自测块 ------------------
if __name__ == "__main__":
    # 简单测试，需设置环境变量 XAI_API_KEY
    try:
        # 初始化
        grok = GrokAPI()
        print("GrokAPI 初始化成功")
        
        # 同步生成测试
        print("执行生成测试...")
        result = grok.generate(prompt="你好，请用一句话介绍你自己。")
        print(f"模型回复: {result['content']}")
        print(f"Token消耗: {result['usage']}")
        
        # 测试消息列表格式
        messages = [
            {"role": "system", "content": "你是一个有用的助手。"},
            {"role": "user", "content": "1+1等于几？"}
        ]
        result2 = grok.generate(prompt=messages)
        print(f"消息列表测试回复: {result2['content']}")
        
    except Exception as e:
        print(f"自测失败: {e}")