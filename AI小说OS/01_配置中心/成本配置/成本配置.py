"""
成本配置模块 - 管理API调用成本、模型使用成本等
功能：
    - 从配置文件加载成本数据
    - 提供成本查询接口
    - 支持热更新配置
    - 日志记录
    - 可插拔设计，通过配置切换实现
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------- 默认配置路径 ----------
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "cost_config.json")

class CostConfig:
    """成本配置管理类，支持热更新、日志、异常恢复"""
    _instance: Optional['CostConfig'] = None
    _config: Dict[str, Any] = {}
    _config_path: str = ""

    def __new__(cls, config_path: str = DEFAULT_CONFIG_PATH):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_config(config_path)
        return cls._instance

    def _init_config(self, config_path: str):
        """初始化配置（仅在首次创建实例时调用）"""
        self._config_path = config_path
        self.load_config()

    def load_config(self) -> bool:
        """从文件加载配置，异常恢复：加载失败使用空配置"""
        try:
            path = Path(self._config_path)
            if not path.exists():
                logger.warning(f"配置文件不存在: {self._config_path}，使用空配置")
                self._config = {}
                self._save_default_config()
                return False

            with open(path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            logger.info(f"成本配置加载成功: {self._config_path}")
            return True
        except json.JSONDecodeError as e:
            logger.error(f"配置解析失败: {e}，使用空配置")
            self._config = {}
            return False
        except Exception as e:
            logger.error(f"加载配置异常: {e}，使用空配置")
            self._config = {}
            return False

    def _save_default_config(self):
        """保存默认配置模板（用于初始化）"""
        default_config = {
            "models": {
                "gpt-3.5-turbo": {
                    "input_per_1k_tokens": 0.0015,
                    "output_per_1k_tokens": 0.002
                },
                "gpt-4": {
                    "input_per_1k_tokens": 0.03,
                    "output_per_1k_tokens": 0.06
                }
            },
            "default_unit": "USD"
        }
        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            logger.info(f"默认成本配置文件已创建: {self._config_path}")
        except Exception as e:
            logger.error(f"无法写入默认配置文件: {e}")

    def reload(self) -> bool:
        """热更新：重新加载配置"""
        logger.info("触发配置热更新")
        return self.load_config()

    def get_cost(self, model: str, input_tokens: int = 0, output_tokens: int = 0) -> float:
        """
        根据模型和token数量计算成本
        :param model: 模型名称
        :param input_tokens: 输入token数
        :param output_tokens: 输出token数
        :return: 总成本（默认货币单位）
        """
        models = self._config.get("models", {})
        if model not in models:
            logger.warning(f"未知模型: {model}，成本无法计算")
            return 0.0

        model_cost = models[model]
        cost = (
            (input_tokens / 1000) * model_cost.get("input_per_1k_tokens", 0) +
            (output_tokens / 1000) * model_cost.get("output_per_1k_tokens", 0)
        )
        return round(cost, 6)

    def get_all_models(self):
        """返回配置中所有模型名称"""
        return list(self._config.get("models", {}).keys())

    def update_config_value(self, key: str, value: Any):
        """
        运行时更新配置值（用于热更新场景，不写入文件）
        :param key: 配置键（支持点分隔路径，如 'models.gpt-4.input_per_1k_tokens'）
        :param value: 新值
        """
        keys = key.split('.')
        current = self._config
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        current[keys[-1]] = value
        logger.info(f"配置更新: {key} = {value}")

    def save_current_config(self):
        """将当前配置保存到文件（持久化）"""
        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info(f"配置已保存至: {self._config_path}")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            raise

    @property
    def config(self):
        """返回完整配置字典（只读）"""
        return dict(self._config)


# ---------- 自测与演示 ----------
if __name__ == "__main__":
    # 测试配置加载和成本计算
    logger.info("=== 成本配置模块自测开始 ===")
    # 创建实例（会自动加载或创建默认配置）
    cost_cfg = CostConfig()
    print("当前模型列表:", cost_cfg.get_all_models())

    # 测试成本计算
    model = "gpt-3.5-turbo"
    input_t = 500
    output_t = 200
    cost = cost_cfg.get_cost(model, input_t, output_t)
    print(f"模型: {model}, 输入tokens: {input_t}, 输出tokens: {output_t}, 成本: {cost} {cost_cfg.config.get('default_unit', '?')}")

    # 测试未知模型
    unknown_cost = cost_cfg.get_cost("unknown-model", 100, 100)
    print(f"未知模型成本: {unknown_cost}")

    # 测试热更新（运行时修改）
    cost_cfg.update_config_value("models.gpt-3.5-turbo.input_per_1k_tokens", 0.002)
    new_cost = cost_cfg.get_cost(model, input_t, output_t)
    print(f"更新价格后成本: {new_cost}")

    # 保存（如果需要持久化）
    # cost_cfg.save_current_config()

    # 测试重新加载
    cost_cfg.reload()
    after_reload_cost = cost_cfg.get_cost(model, input_t, output_t)
    print(f"重新加载后成本: {after_reload_cost}")

    logger.info("=== 自测完成 ===")