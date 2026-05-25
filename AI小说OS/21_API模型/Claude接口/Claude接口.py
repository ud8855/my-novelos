"""Claude接口模块
属于：21_API模型层
依赖：外部库anthropic，内部配置管理、日志系统
被调用：由20_模型协同层调用，提供统一的AI模型访问接口
解决：封装Anthropic Claude API的调用，实现可插拔、配置化、带日志的客户端
"""

import logging
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

# 假设存在配置加载工具，实际开发中替换为项目统一的配置模块
try:
    from novel_os.utils.config_loader import load_yaml_config
except ImportError:
    # 如果还没有配置加载模块，提供一个最小实现作为fallback
    def load_yaml_config(filepath: str) -> dict:
        """临时配置加载函数，正式环境需替换"""
        import yaml
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

# 尝试导入日志工厂，如果没有则使用标准logging
try:
    from novel_os.utils.logger import get_module_logger
except ImportError:
    def get_module_logger(name: str, level: int = logging.INFO) -> logging.Logger:
        """临时日志工厂函数"""
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(level)
        return logger


class ClaudeInterfaceError(Exception):
    """Claude接口自定义异常基类"""
    pass


class ClaudeClient:
    """Claude API客户端，封装与Anthropic Claude模型的交互

    可插拔设计：通过配置指定模型名称、API密钥等，不依赖具体业务逻辑
    配置化：从YAML配置文件或字典加载参数
    日志：使用统一日志系统记录请求与响应概要，便于监控与排查
    扩展性：支持同步/异步调用、流式输出、多模态等，通过子类或方法扩展
    """

    DEFAULT_CONFIG_PATH = "config/claude_api.yaml"

    def __init__(self, config: Optional[Union[str, Dict[str, Any]]] = None):
        """初始化Claude客户端

        Args:
            config: 配置文件路径(str) 或 配置字典(dict)。若为None，则使用默认路径加载。
                    字典需包含: api_key, model (可选), max_tokens (可选), temperature (可选) 等
        Raises:
            FileNotFoundError: 配置文件不存在时
            ClaudeInterfaceError: 配置缺失必要字段时
        """
        self.logger = get_module_logger("ClaudeClient")
        self.config = self._load_config(config)
        self._validate_config()
        self.logger.info("ClaudeClient初始化完成，模型: %s", self.config.get('model', 'default'))

    def _load_config(self, config: Optional[Union[str, Dict[str, Any]]]) -> Dict[str, Any]:
        """加载并合并配置

        Args:
            config: 配置文件路径或字典

        Returns:
            合并后的配置字典
        """
        if config is None:
            config = self.DEFAULT_CONFIG_PATH

        if isinstance(config, str):
            config_path = Path(config)
            if not config_path.exists():
                raise FileNotFoundError(f"Claude配置文件未找到: {config_path}")
            self.logger.info("从文件加载Claude配置: %s", config_path)
            return load_yaml_config(str(config_path))
        elif isinstance(config, dict):
            self.logger.info("从字典加载Claude配置")
            return config
        else:
            raise ClaudeInterfaceError(f"不支持的配置类型: {type(config)}")

    def _validate_config(self):
        """验证配置的完整性，缺失关键字段则报错或使用默认值"""
        required = ['api_key']
        for field in required:
            if field not in self.config or not self.config[field]:
                raise ClaudeInterfaceError(f"Claude配置缺少必要字段: {field}")
        # 设置默认值
        self.config.setdefault('model', 'claude-3-opus-20240229')
        self.config.setdefault('max_tokens', 1024)
        self.config.setdefault('temperature', 0.7)

    def generate_text(self, prompt: str, system: Optional[str] = None,
                      max_tokens: Optional[int] = None,
                      temperature: Optional[float] = None,
                      stop_sequences: Optional[List[str]] = None) -> str:
        """生成文本（同步阻塞模式）

        Args:
            prompt: 用户提示
            system: 系统提示词
            max_tokens: 最大输出token数，默认使用配置
            temperature: 采样温度，默认使用配置
            stop_sequences: 停止序列列表

        Returns:
            模型生成的文本字符串

        Raises:
            ClaudeInterfaceError: 调用失败时
        """
        # TODO: 实际实现API调用
        self.logger.info("开始生成文本，prompt长度: %d", len(prompt))
        # 模拟返回，实际需要调用anthropic SDK
        raise NotImplementedError("generate_text方法待实现")

    def chat(self, messages: List[Dict[str, str]],
             system: Optional[str] = None,
             **kwargs) -> str:
        """多轮对话接口，使用messages格式

        Args:
            messages: 对话历史，格式[{"role": "user", "content": "..."}, ...]
            system: 系统提示词
            **kwargs: 其他参数传递给底层API

        Returns:
            助手回复文本
        """
        self.logger.info("开始对话，消息数量: %d", len(messages))
        raise NotImplementedError("chat方法待实现")

    def stream_text(self, prompt: str, **kwargs) -> Any:
        """流式生成文本（生成器或异步迭代器占位）

        Returns:
            生成器对象，每次产出增量文本
        """
        self.logger.info("开始流式生成文本...")
        raise NotImplementedError("stream_text方法待实现")

    def _handle_api_error(self, error: Exception, context: str = ""):
        """统一处理API调用错误，记录日志并包装异常"""
        self.logger.error("Claude API调用异常 [%s]: %s", context, str(error))
        raise ClaudeInterfaceError(f"API调用失败: {context}") from error

    # ---------- 可插拔扩展接口 ----------
    def reload_config(self, new_config: Union[str, Dict[str, Any]]):
        """运行时重新加载配置，无需重启"""
        self.logger.info("重新加载Claude配置")
        self.config = self._load_config(new_config)
        self._validate_config()

    def health_check(self) -> bool:
        """健康检查，验证API密钥是否有效（轻量调用）"""
        # TODO: 执行一个最小成本的API调用，如models list
        self.logger.info("执行Claude健康检查")
        return True  # 模拟


# 自测代码
if __name__ == "__main__":
    # 使用基本配置进行自测，展示可插拔性
    test_config = {
        'api_key': 'sk-ant-test-key',  # 请替换为真实密钥或使用环境变量
        'model': 'claude-3-haiku-20240307',
        'max_tokens': 50,
        'temperature': 0.5
    }
    try:
        client = ClaudeClient(config=test_config)
        print("ClaudeClient初始化成功")
        # 此处实际调用会抛NotImplementedError，仅用于验证骨架
        # response = client.generate_text("Hello Claude!")
        print("模块加载正常，功能待实现。")
    except Exception as e:
        print(f"自测失败: {e}")
    else:
        print("自测通过")