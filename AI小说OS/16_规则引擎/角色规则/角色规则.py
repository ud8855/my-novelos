# -*- coding: utf-8 -*-
"""
角色规则模块 (16_规则引擎/角色规则)
功能：定义和管理角色相关的创作规则，可插拔式扩展，配置化加载。
依赖：基础日志、配置模块（系统级通用日志/配置抽象）
被调用者：规则引擎调度器、角色生成Agent等
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


# ------------------------------ 配置层 ------------------------------
class RoleRuleConfig:
    """角色规则配置容器，支持热更新"""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or self.default_config()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("角色规则配置初始化完成")

    @staticmethod
    def default_config() -> Dict[str, Any]:
        return {
            "enabled": True,
            "strict_mode": False,
            "allowed_roles": [],          # 空列表表示不限制角色类型
            "forbidden_actions": [],      # 禁止的行为列表
            "custom_params": {}           # 预留扩展参数
        }

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def set(self, key: str, value):
        self._config[key] = value
        self.logger.info(f"配置项更新: {key} -> {value}")

    def update_batch(self, new_config: Dict[str, Any]):
        """批量热更新配置"""
        self._config.update(new_config)
        self.logger.info(f"批量更新配置: {new_config}")

    @property
    def is_enabled(self) -> bool:
        return self.get("enabled", True)


# ------------------------------ 抽象接口层 ------------------------------
class BaseRoleRule(ABC):
    """角色规则抽象基类，定义标准接口，实现可插拔"""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = RoleRuleConfig(config)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._active = self.config.is_enabled
        self.logger.info(f"规则 [{self.__class__.__name__}] 实例化，激活状态: {self._active}")

    @property
    def is_active(self) -> bool:
        return self._active

    def activate(self):
        self._active = True
        self.logger.info(f"规则 [{self.__class__.__name__}] 已激活")

    def deactivate(self):
        self._active = False
        self.logger.info(f"规则 [{self.__class__.__name__}] 已停用")

    @abstractmethod
    def validate(self, role_data: Dict[str, Any]) -> bool:
        """
        验证角色数据是否符合规则约束
        参数：
            role_data: 包含角色信息的字典，必须含至少 name 和 personality 字段
        返回：
            True 表示通过验证，False 表示违反规则
        """
        ...

    def apply(self, role_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        应用规则修正/增强角色数据（可选实现）
        默认行为：若不激活则跳过，否则原样返回
        子类可重写实现具体修正逻辑
        """
        if not self._active:
            self.logger.debug("规则未激活，跳过 apply")
            return role_data

        self.logger.debug(f"应用规则 [{self.__class__.__name__}] 于角色: {role_data.get('name', 'Unnamed')}")
        return role_data

    def update_config(self, new_config: Dict[str, Any]):
        """热更新当前规则的配置"""
        self.config.update_batch(new_config)
        # 同步激活状态
        self._active = self.config.is_enabled


# ------------------------------ 具体规则示例 ------------------------------
class PersonalityRule(BaseRoleRule):
    """
    性格一致性规则：
    验证角色的性格描述与近期行为是否矛盾（示例逻辑）
    """
    def validate(self, role_data: Dict[str, Any]) -> bool:
        if not self.is_active:
            return True

        personality = role_data.get("personality", "")
        actions = role_data.get("recent_actions", [])

        if not personality or not actions:
            return True

        # 占位：实际可接入 NLP 或规则匹配
        self.logger.debug(f"检查角色 {role_data.get('name')} 的性格一致性: {personality} vs {actions}")
        # 假设所有行为都允许（骨架版）
        return True

    def apply(self, role_data: Dict[str, Any]) -> Dict[str, Any]:
        # 若需修正角色数据可在此实现
        return super().apply(role_data)


class BehaviorBoundaryRule(BaseRoleRule):
    """