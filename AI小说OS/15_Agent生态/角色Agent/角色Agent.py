# -*- coding: utf-8 -*-
"""
角色Agent骨架代码
所属层：15_Agent生态/角色Agent
依赖：核心事件总线（暂不依赖）、配置管理、日志
被调用者：Agent调度器、小说生成流程
解决问题：提供可插拔的角色扮演与生成能力，负责维护角色状态、生成对话、行为等
"""

import logging
import traceback
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

# ---------- 基础配置 ----------
@dataclass
class RoleAgentConfig:
    """角色Agent的配置类，支持热更新"""
    agent_name: str = "RoleAgent"
    model_name: str = "default_model"           # 使用的模型名称，实际由模型协同层提供
    prompt_template_path: str = "templates/role_agent_prompt.txt"  # Prompt