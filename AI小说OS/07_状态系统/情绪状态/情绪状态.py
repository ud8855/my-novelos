#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
情绪状态模块：管理小说角色的情绪状态及变化。
包含情绪值的存储、更新、衰减、融合等逻辑，支持配置化和热更新。
属于：07_状态系统。
依赖：配置管理模块（待定）、日志系统。
被调用：Agent系统、剧情驱动模块。
"""

import copy
import logging
from typing import Any, Dict, Optional

# 设置日志
logger = logging.getLogger(__name__)

# 默认情绪类型及初始值
DEFAULT_EMOTIONS = {
    'joy': 0.0,
    'sadness': 0.0,
    'anger': 0.0,
    'fear': 0.0,
    'surprise': 0.0,
    'disgust': 0.0,
    'trust': 0.0,
    'anticipation': 0.0,
}

# 默认配置
DEFAULT_CONFIG = {
    'decay_rate': 0.01,          # 每分钟衰减率
    'max_intensity': 1.0,
    'min_intensity': 0.0,
    'emotion_types': list(DEFAULT_EMOTIONS.keys()),