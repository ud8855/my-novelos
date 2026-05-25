"""
世界规则模块 (World Rules)
Module Path: 16_规则引擎/世界规则.py
功能：负责加载、验证和应用小说世界的规则（如物理规则、社会规则、魔法规则等），
保证故事逻辑的一致性与合理性。
可插拔设计：实现基础接口，可通过配置切换不同规则集。
支持：热更新、日志、配置化。
"""

from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, List, Optional
import json
import os

# 配置日志
logger = logging.getLogger(__name__)


class WorldRuleBase(ABC):
    """世界规则基类，定义规则检查接口"""

    @abstractmethod
    def load_rules(self, rule_config: Dict[str, Any]) -> None:
        """
        加载规则配置
        :param rule_config: 规则配置字典
        """
        pass

    @abstractmethod
    def check_event(self, event: Dict[str, Any]) -> List[str]:
        """
        检查给定事件是否符合世界规则
        :param event: 事件描述，包含动作、参与者、场景等信息
        :return: 违规规则列表，空列表表示符合规则
        """
        pass

    @abstractmethod
    def get_active_rules(self) -> Dict[str, Any]:
        """
        获取当前生效的规则
        :return: 规则字典
        """
        pass


class WorldRule(WorldRuleBase):
    """世界规则实现类，支持配置化、日志、热更新"""

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化世界规则引擎
        :param config_path: 配置文件路径，可选
        """
        self._rules: Dict[str, Any] = {}
        self._config_path = config_path
        self._is_loaded = False
        if self._config_path and os.path.exists(self._config_path):
            try:
                self.reload()
            except Exception as e:
                logger.error(f"初始化加载规则失败: {e}", exc_info=True)
                # 异常恢复：留空规则集，但不中断服务
                self._rules = {}
                self._is_loaded = False

    def load_rules(self, rule_config: Dict[str, Any]) -> None:
        """从字典加载规则，替换现有规则"""
        try:
            self._rules = rule_config.copy()
            self._is_loaded = True
            logger.info(f"世界规则加载成功，规则数量: {len(self._rules)}")
        except Exception as e:
            logger.error(f"加载规则失败: {e}", exc_info=True)
            raise

    def reload(self) -> None:
        """热更新：重新从配置文件加载规则（如果配置路径存在）"""
        if not self._config_path:
            logger.warning("未设置配置文件路径，无法热更新")
            return
        if not os.path.exists(self._config_path):
            logger.error(f"配置文件不存在: {self._config_path}")
            raise FileNotFoundError(f"配置文件不存在: {self._config_path}")

        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.load_rules(config.get("world_rules", {}))
            logger.info(f"从配置热更新世界规则成功: {self._config_path}")
        except Exception as e:
            logger.error(f"热更新规则失败: {e}", exc_info=True)
            # 异常恢复：保留原有规则
            raise

    def check_event(self, event: Dict[str, Any]) -> List[str]:
        """
        检查事件是否违反世界规则
        :param event: 事件详情
        :return: 违规的规则名称列表
        """
        if not self._is_loaded:
            logger.warning("世界规则未加载，跳过检查")
            return []

        violations = []
        # 此处为骨架，具体规则检查逻辑待实现
        logger.debug(f"检查事件: {event.get('id', 'unknown')}")
        # 示例：遍历规则，使用自定义检查函数
        for rule_name, rule_def in self._rules.items():
            if not self._check_rule(rule_name, rule_def, event):
                violations.append(rule_name)
                logger.debug(f"事件违反规则: {rule_name}")

        return violations

    def _check_rule(self, rule_name: str, rule_def: Any, event: Dict[str, Any]) -> bool:
        """
        单个规则的检查逻辑（待实现）
        :param rule_name