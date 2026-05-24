# 废弃实验.py
# 所属层：99_实验室/废弃实验
# 功能：用于标识和管理已废弃的实验模块，提供兼容性警告和迁移指引
# 依赖：标准库logging, 系统配置模块（从配置中心加载）
# 被调用：任何需要检查废弃状态的运行时组件
# 解决：集中管理废弃实验，避免运行时直接调用已淘汰功能
# 设计：可插拔（通过配置控制），日志记录，配置化，支持热更新（通过重新加载配置）

import logging
import sys
from typing import Any, Dict, Optional


class DeprecatedExperimentManager:
    """管理废弃实验的注册、状态检查与警告输出"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化管理器
        :param config: 配置字典，若未提供则从默认配置加载
        """
        self._config = config or self._load_default_config()
        self._logger = self._setup_logger()
        self._deprecated_experiments = self._config.get("deprecated_experiments", {})
        self._is_enabled = self._config.get("enable_warnings", True)
        self._logger.info("DeprecatedExperimentManager initialized. Enabled: %s", self._is_enabled)

    def _load_default_config(self) -> Dict[str, Any]:
        """从配置中心加载默认配置（临时占位）"""
        # TODO: 接入配置中心
        # 示例配置结构
        return {
            "enable_warnings": True,
            "warn_on_use": True,
            "log_level": "WARNING",
            "deprecated_experiments": {
                "old_feature_a": {
                    "removal_version": "2.0",
                    "alternative": "new_feature_x",
                    "message": "FeatureA is deprecated, use FeatureX instead."
                },
                "legacy_api": {
                    "removal_version": "3.0",
                    "alternative": "v2_api",
                    "message": "Legacy API will be removed in v3.0. Migrate to v2_api."
                }
            }
        }

    def _setup_logger(self) -> logging.Logger:
        """配置日志器"""
        logger = logging.getLogger("DeprecatedExperiment")
        level = getattr(logging, self._config.get("log_level", "WARNING").upper(), logging.WARNING)
        logger.setLevel(level)
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    def reload_config(self, new_config: Optional[Dict[str, Any]] = None) -> None:
        """热更新配置"""
        if new_config:
            self._config = new_config
        else:
            self._config = self._load_default_config()
        self._deprecated_experiments = self._config.get("deprecated_experiments", {})
        self._is_enabled = self._config.get("enable_warnings", True)
        log_level = getattr(logging, self._config.get("log_level", "WARNING").upper(), logging.WARNING)
        self._logger.setLevel(log_level)
        self._logger.info("Configuration reloaded.")

    def is_deprecated(self, experiment_name: str) -> bool:
        """检查实验是否已废弃"""
        return experiment_name in self._deprecated_experiments

    def warn_if_deprecated(self, experiment_name: str, context: str = "") -> None:
        """
        若实验已废弃，则发出警告日志（如果启用）
        :param experiment_name: 实验名称
        :param context: 调用上下文信息
        """
        if not self._is_enabled:
            return
        if self.is_deprecated(experiment_name):
            info = self._deprecated_experiments[experiment_name]
            msg = f"DEPRECATED EXPERIMENT '{experiment_name}' is used. {info.get('message', 'No message provided.')}"
            if context:
                msg += f" Context: {context}"
            self._logger.warning(msg)
        else:
            self._logger.debug("Experiment '%s' is not deprecated.", experiment_name)

    def get_alternative(self, experiment_name: str) -> Optional[str]:
        """获取废弃实验的替代建议"""
        info = self._deprecated_experiments.get(experiment_name)
        if info:
            return info.get("alternative")
        return None


# 全局单例（可选，但提供便捷访问点）
_global_manager: Optional[DeprecatedExperimentManager] = None


def get_deprecated_manager() -> DeprecatedExperimentManager:
    """获取全局废弃实验管理器单例"""
    global _global_manager
    if _global_manager is None:
        _global_manager = DeprecatedExperimentManager()
    return _global_manager


# 自测部分
if __name__ == "__main__":
    print("=== DeprecatedExperimentManager 自测 ===")
    # 使用默认配置创建实例
    manager = DeprecatedExperimentManager()

    # 测试检查废弃
    test_exp = "old_feature_a"
    print(f"Is '{test_exp}' deprecated? {manager.is_deprecated(test_exp)}")

    # 发出警告
    manager.warn_if_deprecated(test_exp, context="Testing main")

    # 获取替代方案
    alt = manager.get_alternative(test_exp)
    print(f"Alternative for '{test_exp}': {alt}")

    # 测试未废弃的实验
    manager.warn_if_deprecated("new_feature_b")

    # 热更新配置（禁用警告）
    new_config = {"enable_warnings": False, "deprecated_experiments": {}}
    manager.reload_config(new_config)
    manager.w