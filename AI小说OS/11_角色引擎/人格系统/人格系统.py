# -*- coding: utf-8 -*-
"""
模块位置：11_角色引擎/人格系统/人格系统.py
所属层级：角色引擎层（核心组件之一）
依赖关系：
    - 上层：被 12_剧情引擎/、13_对话系统/ 等模块调用，提供角色人格数据。
    - 下层：不直接访问数据库或模型，仅处理数据结构；如需持久化，通过标准接口注入存储后端。
    - 同层：可能与 11_角色引擎/行为系统、情感系统 等协作。
职责：
    管理角色的人格特征、性格维度、行为倾向等参数。
    提供统一接口获取/更新人格数据，支持配置化加载、热插拔、日志记录。
特点：
    - 可插拔：定义抽象基类，方便替换实现。
    - 配置化：通过 JSON/YAML 配置文件定义人格维度及默认值。
    - 日志：关键操作均记录日志。
    - 异常恢复与热更新：支持重新加载配置而不中断服务。
注意：
    严格遵守分层架构，不跨层直接操作数据存储或外部API。
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


# ==================== 全局日志配置 ====================
logger = logging.getLogger("NovelOS.PersonalitySystem")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)


# ==================== 抽象基类 ====================
class PersonalitySystemBase(ABC):
    """
    人格系统抽象接口。
    所有具体实现必须继承此类，以实现可插拔特性。
    """

    @abstractmethod
    def load_config(self, config_source: str) -> None:
        """
        加载人格配置。
        :param config_source: 配置文件路径 或 配置数据字符串（实现决定）
        """
        pass

    @abstractmethod
    def get_personality(self, character_id: str) -> Dict[str, Any]:
        """
        获取指定角色当前人格数据。
        :param character_id: 角色唯一标识符
        :return: 人格参数字典，键为维度名，值为参数值
        """
        pass

    @abstractmethod
    def update_personality(self, character_id: str, traits: Dict[str, Any]) -> None:
        """
        更新指定角色的人格参数。
        :param character_id: 角色唯一标识符
        :param traits: 待更新的人格参数字典
        """
        pass

    @abstractmethod
    def reset_personality(self, character_id: str) -> None:
        """
        重置角色人格为配置默认值。
        :param character_id: 角色唯一标识符
        """
        pass

    @abstractmethod
    def list_characters(self) -> list:
        """
        列出所有已管理的角色ID。
        :return: 角色ID列表
        """
        pass


# ==================== 默认实现 ====================
class DefaultPersonalitySystem(PersonalitySystemBase):
    """
    基于配置文件的人格系统默认实现。
    配置文件格式期望为 JSON，包含人格维度定义及默认模板。
    """

    def __init__(self):
        """初始化，不自动加载任何配置，需调用 load_config 激活。"""
        self._personality_config = {}   # 人格维度定义
        self._default_template = {}     # 默认人格模板
        self._character_data: Dict[str, Dict[str, Any]] = {}  # 角色人格存储
        self._is_loaded = False
        logger.info("DefaultPersonalitySystem 实例已创建，等待配置加载。")

    # ---------- 配置加载 ----------
    def load_config(self, config_source: str) -> None:
        """
        从文件路径加载 JSON 配置。
        配置文件结构示例：
        {
            "dimensions": {
                "openness": {"default": 0.5, "range": [0.0, 1.0]},
                "conscientiousness": {"default": 0.5, "range": [0.0, 1.0]},
                ...
            },
            "default_template": {
                "openness": 0.5,
                "conscientiousness": 0.5,
                ...
            }
        }
        :param config_source: 配置文件路径
        """
        if not os.path.exists(config_source):
            error_msg = f"配置文件不存在: {config_source}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            with open(config_source, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self._personality_config = config.get("dimensions", {})
            self._default_template = config.get("default_template", {})
            self._is_loaded = True
            logger.info(f"人格配置加载成功，维度数量: {len(self._personality_config)}，"
                        f"默认模板字段: {list(self._default_template.keys())}")
        except Exception as e:
            logger.exception("加载人格配置失败")
            raise RuntimeError(f"人格配置加载失败: {str(e)}")

    # ---------- 人格数据访问 ----------
    def get_personality(self, character_id: str) -> Dict[str, Any]:
        """
        获取角色人格。若角色不存在，则创建一份基于默认模板的新人格。
        :param character_id: 角色ID
        :return: 人格数据副本，避免外部直接修改内部状态
        """
        if not self._is_loaded:
            raise RuntimeError("人格系统尚未加载配置，请先调用 load_config()")
        if character_id not in self._character_data:
            logger.debug(f"角色 '{character_id}' 不存在，自动创建默认人格。")
            self._character_data[character_id] = self._default_template.copy()
        return self._character_data[character_id].copy()

    def update_personality(self, character_id: str, traits: Dict[str, Any]) -> None:
        """
        更新角色人格。只更新 traits 中指定的维度，其余保持不变。
        会校验维度是否在配置中存在，并限制范围（可选实现）。
        :param character_id: 角色ID
        :param traits: 待更新的维度键值对
        """
        if not self._is_loaded:
            raise RuntimeError("人格系统尚未加载配置，请先调用 load_config()")
        # 确保角色存在
        if character_id not in self._character_data:
            self._character_data[character_id] = self._default_template.copy()

        # 更新并记录变化
        changed = {}
        for dim, value in traits.items():
            if dim in self._personality_config:
                old_val = self._character_data[character_id].get(dim)
                # 简单的范围检查（如果配置了range）
                dim_conf = self._personality_config[dim]
                if "range" in dim_conf:
                    low, high = dim_conf["range"]
                    value = max(low, min(high, value))
                self._character_data[character_id][dim] = value
                changed[dim] = (old_val, value)
            else:
                logger.warning(f"忽略未知人格维度: '{dim}'")
        if changed:
            logger.info(f"更新角色 '{character_id}' 人格: {changed}")
        else:
            logger.debug(f"角色 '{character_id}' 人格无变化。")

    def reset_personality(self, character_id: str) -> None:
        """
        重置为配置默认值。
        """
        if not self._is_loaded:
            raise RuntimeError("人格系统尚未加载配置，请先调用 load_config()")
        self._character_data[character_id] = self._default_template.copy()
        logger.info(f"角色 '{character_id}' 人格已重置为默认值。")

    def list_characters(self) -> list:
        """
        列出所有管理的角色ID。
        """
        return list(self._character_data.keys())

    # ---------- 热更新支持 ----------
    def reload_config(self) -> None:
        """
        重新加载当前配置（如果先前加载了文件路径，需保存路径）。
        注意：这里简化演示，实际使用时可记忆 config_source。
        """
        logger.warning("reload_config 需要提供配置路径；本示例仅重置内部数据。")
        self._is_loaded = False
        logger.info("人格配置已清除，请重新调用 load_config()。")


# ==================== 自测代码 ====================
if __name__ == "__main__":
    print("=" * 60)
    print("人格系统自测开始")
    print("=" * 60)

    # 1. 创建默认人格系统实例
    ps = DefaultPersonalitySystem()

    # 2. 准备一个简单的测试配置文件
    test_config = {
        "dimensions": {
            "openness": {"default": 0.5, "range": [0.0, 1.0]},
            "conscientiousness": {"default": 0.6, "range": [0.0, 1.0]},
            "extraversion": {"default": 0.4, "range": [0.0, 1.0]},
            "agreeableness": {"default": 0.7, "range": [0.0, 1.0]},
            "neuroticism": {"default": 0.3, "range": [0.0, 1.0]}
        },
        "default_template": {
            "openness": 0.5,
            "conscientiousness": 0.6,
            "extraversion": 0.4,