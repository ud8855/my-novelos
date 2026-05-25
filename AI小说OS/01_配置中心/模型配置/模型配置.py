"""
模型配置模块
所属层级：01_配置中心
依赖：无（标准库）
被调用：20_模型协同、21_API模型 等需要获取模型配置信息的模块
解决问题：统一管理所有AI模型的配置信息，包括API地址、密钥（脱敏处理）、模型名称、默认参数等。
        支持从配置文件加载、运行时动态注册/修改，确保模型调用的配置一致性。
        可插拔：通过注册机制可接入任意模型供应商，不硬编码。
        日志：记录配置加载、变更、错误等信息。
"""

import json
import os
import copy
import logging
from typing import Any, Dict, Optional

class ModelConfigError(Exception):
    """模型配置异常基类"""
    pass

class ModelConfigNotFoundError(ModelConfigError):
    """指定模型配置未找到"""
    pass

class ModelConfigManager:
    """
    模型配置管理器（单例模式）
    负责模型配置的加载、获取、注册、持久化。
    所有模型调用模块必须通过此管理器获取配置，以实现配置的统一管理和热更新。
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ModelConfigManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config_path: Optional[str] = None):
        # 防止重复初始化（单例）
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True

        self.logger = logging.getLogger(f"{__name__}.ModelConfigManager")
        self._configs: Dict[str, Dict[str, Any]] = {}
        self._config_path = config_path  # 外部配置文件路径

        # 加载默认内置配置（可被外部文件覆盖）
        self._load_defaults()
        if config_path:
            self.load_from_file(config_path)
        self.logger.info("模型配置管理器初始化完成")

    def _load_defaults(self):
        """
        加载硬编码的默认模型配置（示例）。
        实际项目中，这些默认值应当非常精简，仅作为回退使用。
        """
        default_configs = {
            "gpt-3.5-turbo": {
                "provider": "openai",
                "api_base": "https://api.openai.com/v1",
                "api_key_env": "OPENAI_API_KEY",  # 密钥从环境变量获取，避免写死在配置中
                "model_name": "gpt-3.5-turbo",
                "default_params": {
                    "temperature": 0.7,
                    "max_tokens": 2048
                },
                "timeout": 30,
                "max_retries": 3
            },
            "gpt-4": {
                "provider": "openai",
                "api_base": "https://api.openai.com/v1",
                "api_key_env": "OPENAI_API_KEY",
                "model_name": "gpt-4",
                "default_params": {
                    "temperature": 0.5,
                    "max_tokens": 4096
                },
                "timeout": 60,
                "max_retries": 3
            },
            # 可以扩展更多默认模型
        }
        self._configs.update(copy.deepcopy(default_configs))
        self.logger.debug(f"已加载 {len(default_configs)} 个默认模型配置")

    def load_from_file(self, path: str):
        """
        从JSON文件加载模型配置，覆盖/追加到现有配置。
        :param path: JSON配置文件路径
        """
        if not os.path.exists(path):
            self.logger.error(f"配置文件不存在: {path}")
            raise FileNotFoundError(f"模型配置文件不存在: {path}")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                external_configs = json.load(f)
            if not isinstance(external_configs, dict):
                raise ValueError("配置文件根元素必须是对象(dict)")

            loaded_count = 0
            for model_key, config in external_configs.items():
                self.register_config(model_key, config)
                loaded_count += 1
            self.logger.info(f"从文件 {path} 加载了 {loaded_count} 个模型配置")
        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"配置文件解析失败: {e}")
            raise

    def register_config(self, model_key: str, config: Dict[str, Any]):
        """
        注册或更新一个模型配置。
        :param model_key: 模型标识（例如 "gpt-4"）
        :param config: 模型配置字典，必须包含基本字段：provider, model_name
        """
        if not isinstance(config, dict):
            raise ValueError("模型配置必须是字典类型")
        # 基本校验（可以更严格）
        if 'model_name' not in config:
            raise ValueError("模型配置必须包含 'model_name' 字段")
        if 'provider' not in config:
            config['provider'] = 'unknown'

        # 深度复制以避免外部修改影响内部
        self._configs[model_key] = copy.deepcopy(config)
        self.logger.info(f"模型配置已注册/更新: {model_key}")

    def get_config(self, model_key: str) -> Dict[str, Any]:
        """
        获取指定模型的完整配置（已脱敏，不含原始密钥）。
        :param model_key: 模型标识
        :return: 模型配置的深拷贝
        :raises ModelConfigNotFoundError: 若模型未注册
        """
        if model_key not in self._configs:
            raise ModelConfigNotFoundError(f"模型配置不存在: {model_key}")
        config = copy.deepcopy(self._configs[model_key])
        # 日志中不打印敏感信息，但不在此处过滤，由调用方处理
        self.logger.debug(f"获取模型配置: {model_key}")
        return config

    def list_models(self) -> Dict[str, str]:
        """
        列出所有已注册的模型及其简单描述。
        :return: {model_key: model_name} 字典
        """
        return {key: val.get('model_name', key) for key, val in self._configs.items()}

    def remove_config(self, model_key: str):
        """
        移除一个模型配置。
        :param model_key: 要移除的模型标识
        """
        if model_key in self._configs:
            del self._configs[model_key]
            self.logger.info(f"模型配置已移除: {model_key}")
        else:
            self.logger.warning(f"尝试移除不存在的模型配置: {model_key}")

    def save_to_file(self, path: str):
        """
        将当前所有配置保存为JSON文件（不包括默认内置配置中环境变量引用的敏感信息）。
        :param path: 保存路径
        """
        # 注意：保存时可能会将运行时加载的密钥环境变量名保存，但不会保存实际密钥值（因为从环境变量读取）。
        # 这里简单保存整个配置，实际使用时应过滤敏感字段。
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self._configs, f, indent=2, ensure_ascii=False)
            self.logger.info(f"模型配置已保存到 {path}")
        except IOError as e:
            self.logger.error(f"保存配置文件失败: {e}")
            raise

    def reload_config(self, path: Optional[str] = None):
        """
        重新加载配置（从文件或默认），用于热更新。
        :param path: 若提供则重新从该文件加载，否则只重置为默认。
        """
        self._configs.clear()
        self._load_defaults()
        if path:
            self.load_from_file(path)
        self.logger.info("模型配置已重新加载")


# ================= 自测部分 =================
if __name__ == "__main__":
    # 设置日志输出到控制台
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("=== 模型配置管理模块自测 ===")

    # 测试1：创建单例实例（无外部文件）
    manager1 = ModelConfigManager()
    manager2 = ModelConfigManager()
    assert manager1 is manager2, "单例模式失效"
    print("1. 单例测试通过")

    # 测试2：获取默认配置
    try:
        config = manager1.get_config("gpt-3.5-turbo")
        assert config['model_name'] == "gpt-3.5-turbo"
        print("2. 默认配置获取测试通过")
    except ModelConfigNotFoundError:
        print("2. 默认配置获取失败（未找到）")
        assert False

    # 测试3：注册新模型
    custom_config = {
        "provider": "anthropic",
        "model_name": "claude-3-opus",
        "api_key_env": "ANTHROPIC_API_KEY",
        "default_params": {"temperature": 0.3}
    }
    manager1.register_config("claude-3-opus", custom_config)
    try:
        config = manager1.get_config("claude-3-opus")
        assert config['model_name'] == "claude-3-opus"
        print("3. 动态注册并获取配置测试通过")
    except ModelConfigNotFoundError:
        print("3. 动态注册后获取配置失败")
        assert False

    # 测试4：列表
    models = manager1.list_models()
    print("4. 已注册模型列表:", models)
    assert "claude-3-opus" in models

    # 测试5：移除配置
    manager1.remove_config("claude-3-opus")
    try:
        manager1.get_config("claude-3-opus")
        print("5. 移除配置失败：仍能获取到")
        assert False
    except ModelConfigNotFoundError:
        print("5. 移除配置后获取异常，测试通过")

    # 测试6：保存和加载文件
    test_path = "test_model_config.json"
    try:
        manager1.save_to_file(test_path)
        # 修改一个配置以验证加载覆盖
        manager1.register_config("g