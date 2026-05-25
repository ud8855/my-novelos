"""统一模型协议 (UnifiedModelProtocol)

本模块定义了所有外部AI模型调用的统一抽象接口，确保不同模型 (如OpenAI, Claude, 本地模型等)
可以通过同一套协议进行调用和替换，实现热插拔。

依赖:
    - 无内部模块依赖 (本层为基础协议层)
    - 外部依赖: typing, abc, logging, json

被调用:
    - 20_模型协同/ 中的模型调度器
    - 上层任何需要调用模型的模块
"""

import logging
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Iterator, Optional, Union
from pathlib import Path

# 日志配置 (可被外部覆盖)
LOGGER = logging.getLogger("UnifiedModelProtocol")
LOGGER.setLevel(logging.DEBUG)
if not LOGGER.handlers:
    _handler = logging.StreamHandler()
    _formatter = logging.Formatter('[%(asctime)s][%(levelname)s] %(name)s: %(message)s')
    _handler.setFormatter(_formatter)
    LOGGER.addHandler(_handler)


class ModelConfig:
    """
    模型配置对象
    封装单个模型的所有配置参数，支持从字典、JSON文件或环境变量加载。
    """

    def __init__(self,
                 model_id: str,
                 api_key: Optional[str] = None,
                 endpoint: Optional[str] = None,
                 timeout: int = 60,
                 extra_params: Optional[Dict[str, Any]] = None):
        """
        初始化模型配置
        :param model_id: 模型标识名称 (如 'gpt-4', 'claude-3')
        :param api_key: API密钥 (若为None则尝试从环境变量获取)
        :param endpoint: API端点URL (如非标准端点)
        :param timeout: 请求超时秒数
        :param extra_params: 额外的模型参数 (如temperature, max_tokens等默认值)
        """
        self.model_id = model_id
        self.api_key = api_key
        self.endpoint = endpoint
        self.timeout = timeout
        self.extra_params = extra_params if extra_params is not None else {}
        # 若未提供 api_key，尝试从环境变量 MODEL_API_KEY 或 {model_id}_API_KEY 获取
        if not self.api_key:
            import os
            self.api_key = os.environ.get("MODEL_API_KEY") or os.environ.get(f"{model_id}_API_KEY")

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ModelConfig':
        """从字典构建配置"""
        return cls(
            model_id=config_dict.get("model_id", "unknown"),
            api_key=config_dict.get("api_key"),
            endpoint=config_dict.get("endpoint"),
            timeout=config_dict.get("timeout", 60),
            extra_params=config_dict.get("extra_params", {})
        )

    @classmethod
    def from_json(cls, json_path: Union[str, Path]) -> 'ModelConfig':
        """从JSON文件加载配置"""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)

    def to_dict(self) -> Dict[str, Any]:
        """转为字典 (隐藏敏感信息)"""
        result = {
            "model_id": self.model_id,
            "endpoint": self.endpoint,
            "timeout": self.timeout,
            "extra_params": self.extra_params
        }
        # 不导出api_key，防止泄露
        return result

    def __repr__(self):
        return f"ModelConfig(model_id='{self.model_id}', endpoint={self.endpoint})"


class UnifiedModel(ABC):
    """
    统一模型抽象基类

    所有具体的模型实现必须继承此类并实现以下抽象方法:
    - initialize
    - generate
    - stream_generate
    - shutdown
    """

    def __init__(self, config: ModelConfig):
        self.config = config
        self._initialized = False
        LOGGER.info(f"初始化模型实例: {config.model_id}")

    @abstractmethod
    def initialize(self) -> bool:
        """
        模型初始化 (如建立连接、验证API密钥等)
        返回 True 表示成功
        """
        pass

    @abstractmethod
    def generate(self,
                 prompt: str,
                 system_prompt: Optional[str] = None,
                 max_tokens: Optional[int] = None,
                 temperature: Optional[float] = None,
                 **kwargs) -> str:
        """
        同步生成回复
        :param prompt: 用户提示词
        :param system_prompt: 系统级提示词
        :param max_tokens: 最大生成token数
        :param temperature: 温度参数
        :param kwargs: 其他特定于模型的参数
        :return: 模型生成的完整文本
        """
        pass

    @abstractmethod
    def stream_generate(self,
                        prompt: str,
                        system_prompt: Optional[str] = None,
                        max_tokens: Optional[int] = None,
                        temperature: Optional[float] = None,
                        **kwargs) -> Iterator[str]:
        """
        流式生成回复
        :param prompt: 用户提示词
        :param system_prompt: 系统级提示词
        :param max_tokens: 最大生成token数
        :param temperature: 温度参数
        :param kwargs: 其他特定于模型的参数
        :yield: 模型生成的文本片段
        """
        # 注意：yield 语句不能放在抽象方法内，但这里仅定义接口，具体实现中将使用 yield
        # 为了兼容类型检查，返回一个空的生成器
        if False:
            yield ""

    @abstractmethod
    def shutdown(self) -> None:
        """
        关闭模型资源，释放连接等
        """
        pass

    def is_initialized(self) -> bool:
        """检查模型是否已成功初始化"""
        return self._initialized

    def __enter__(self):
        if self.initialize():
            return self
        else:
            raise RuntimeError(f"模型 {self.config.model_id} 初始化失败")

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()

    def __repr__(self):
        return f"{self.__class__.__name__}(model_id='{self.config.model_id}')"


class ModelFactory:
    """
    模型工厂，根据配置动态加载具体的模型实现类。
    支持热插拔：只需将新模型实现模块放入指定位置，并通过配置文件注册即可。
    """

    _registry: Dict[str, type] = {}

    @classmethod
    def register_model(cls, model_name: str, model_class: type):
        """
        注册模型实现类
        :param model_name: 模型名称标识
        :param model_class: 继承自 UnifiedModel 的类
        """
        if not issubclass(model_class, UnifiedModel):
            raise TypeError(f"模型类 {model_class} 必须继承自 UnifiedModel")
        cls._registry[model_name] = model_class
        LOGGER.info(f"注册模型: {model_name} -> {model_class.__name__}")

    @classmethod
    def create_model(cls, config: ModelConfig, **kwargs) -> UnifiedModel:
        """
        根据配置创建模型实例
        首先尝试从注册表中查找 model_id 对应的实现类，若未找到则尝试动态加载
        :param config: 模型配置对象
        :param kwargs: 额外传递给模型构造函数的参数
        :return: UnifiedModel 实例
        """
        model_id = config.model_id
        # 优先从注册表获取
        if model_id in cls._registry:
            model_cls = cls._registry[model_id]
            return model_cls(config, **kwargs)

        # 动态加载备选：假设类名约定为 {ModelId}Model，模块位于当前目录下 model_{model_id}.py
        # 这是可选的扩展机制，项目初期可留空
        LOGGER.warning(f"模型 {model_id} 未在注册表中找到，尝试动态加载...")
        # 此处仅提供接口，实际自动发现逻辑在后续模块实现
        raise ValueError(f"未注册的模型: {model_id}，请先通过 ModelFactory.register_model 注册实现类")

    @classmethod
    def list_registered_models(cls) -> Dict[str, type]:
        """列出所有已注册的模型类"""
        return dict(cls._registry)


# 可选：一个简单的空实现用于测试协议占位
class DummyModel(UnifiedModel):
    """
    哑模型实现，仅用于测试协议连通性，不产生有意义输出。
    """

    def initialize(self) -> bool:
        LOGGER.debug("DummyModel: 初始化成功 (无操作)")
        self._initialized = True
        return True

    def generate(self,
                 prompt: str,
                 system_prompt: Optional[str] = None,
                 max_tokens: Optional[int] = None,
                 temperature: Optional[float] = None,
                 **kwargs) -> str:
        LOGGER.debug("DummyModel: 生成回复")
        return f"这是Dummy模型对 '{prompt[:30]}...' 的回复"

    def stream_generate(self,
                        prompt: str,
                        system_prompt: Optional[str] = None,
                        max_tokens: Optional[int] = None,
                        temperature: Optional[float] = None,
                        **kwargs) -> Iterator[str]:
        LOGGER.debug("DummyModel: 流式生成")
        words = f"(流式)这是Dummy模型对 '{prompt[:10]}...' 的回复".split()
        for word in words:
            yield word + " "

    def shutdown(self) -> None:
        LOGGER.debug("DummyModel: 关闭 (无操作)")
        self._initialized = False


# 自测代码
if __name__ == "__main__":
    print("===== 统一模型协议自测 =====")

    # 1. 配置加载测试
    print("1. 从字典构建配置")
    config = ModelConfig.from_dict({
        "model_id": "dummy-test",
        "api_key": None,
        "endpoint": None,
        "timeout": 10
    })
    print(f"   配置: {config}")

    # 2. 注册并创建哑模型
    print("\n2. 注册 DummyModel 并创建实例")
    ModelFactory.register_model("dummy-test", DummyModel)
    model = ModelFactory.create_model(config)
    print(f"   已创建模型实例: {model}")

    # 3. 初始化模型
    print("\n3. 初始化模型")
    if model.initialize():
        print("   初始化成功")

    # 4. 生成测试
    print("\n4. 同步生成")
    result = model.generate("你好，世界！", system_prompt="你是一个助手", temperature=0.7)
    print(f"   生成结果: {result}")

    # 5. 流式生成测试
    print("\n5. 流式生成")
    print("   流式输出: ", end="")
    for token in model.stream_generate("写一首诗"):
        print(token, end="")
    print()

    # 6. 关闭模型
    print("\n6. 关闭模型")
    model.shutdown()
    print("   模型已关闭")

    # 7. 上下文管理器测试
    print("\n7. 使用 with 语句")
    config2 = ModelConfig.from_dict({"model_id": "dummy-test"})
    dummy_cls = ModelFactory._registry["dummy-test"]
    with dummy_cls(config2) as m:
        r = m.generate("上下文测试")
        print(f"   生成结果: {r}")

    print("\n自测完成。")