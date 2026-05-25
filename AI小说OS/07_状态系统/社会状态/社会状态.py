#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
07_状态系统/社会状态/社会状态.py
社会状态模块：管理角色的社会属性（声望、信任、势力影响等）以及角色间的关系网络。
可插拔设计：通过配置切换存储后端（当前支持内存字典和JSON文件）。
配置化：通过初始化时传入的config字典或默认配置驱动行为。
日志：所有状态变更均通过logging记录，方便追踪和调试。
中文注释，英文标识符。
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

# 模块级日志器
logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_CONFIG: Dict[str, Any] = {
    "storage_backend": "memory",  # 存储后端类型: "memory" 或 "file"
    "save_path": "data/social_state.json",  # 文件持久化路径
    "default_social_values": {  # 角色社会属性的默认初始值
        "fame": 0,        # 声望
        "trust": 0,       # 信任度
        "influence": 0,   # 影响力
    },
}


class SocialStateManager:
    """
    社会状态管理器
    负责单个角色的社会属性及角色间关系的增删改查。
    支持可插拔存储（内存/文件），通过config['storage_backend']控制。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        初始化社会状态管理器。
        :param config: 可选配置字典，会与默认配置合并。
        """
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)

        # 内部分存储结构
        self.storage: Dict[str, Any] = {
            "characters": {},      # {character_id: social_data_dict}
            "relationships": {},   # {(char1, char2): relation_data_dict}
        }

        # 根据配置决定加载策略
        backend = self.config.get("storage_backend", "memory")
        if backend == "file":
            self.load_from_file()
        else:
            logger.info("Using in-memory storage backend.")

        logger.info("SocialStateManager initialized with config: %s", self.config)

    # ---------- 角色社会属性操作 ----------
    def add_character_social(self, character_id: str, social_data: Optional[Dict[str, Any]] = None) -> None:
        """
        为角色添加或覆盖社会属性。
        若未提供social_data，则使用配置中的默认值。
        :param character_id: 角色唯一标识
        :param social_data: 社会属性字典，如 {'fame': 100, ...}
        """
        if social_data is None:
            social_data = self.config["default_social_values"].copy()
        self.storage["characters"][character_id] = social_data
        logger.debug("Character '%s' social data set: %s", character_id, social_data)

    def get_character_social(self, character_id: str) -> Optional[Dict[str, Any]]:
        """
        获取角色的社会属性。
        :param character_id: 角色标识
        :return: 社会属性字典，不存在则返回None
        """
        return self.storage["characters"].get(character_id)

    def update_social_attribute(self, character_id: str, attribute: str, value: Any) -> None:
        """
        更新角色某项社会属性的值。若角色不存在则自动创建。
        :param character_id: 角色标识
        :param attribute: 属性名，如 'fame'
        :param value: 新值
        """
        if character_id not in self.storage["characters"]:
            self.add_character_social(character_id)
        old_value = self.storage["characters"][character_id].get(attribute)
        self.storage["characters"][character_id][attribute] = value
        logger.info(
            "Updated social attribute '%s' for '%s': %s -> %s",
            attribute, character_id, old_value, value
        )

    # ---------- 角色关系操作 ----------
    def add_relationship(self, char1: str, char2: str, relation_data: Dict[str, Any]) -> None:
        """
        添加或更新两个