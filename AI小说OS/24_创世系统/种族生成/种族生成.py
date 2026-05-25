"""
模块：种族生成
层级：创世系统 (24_创世系统)
依赖：基础配置、日志系统
被调用者：世界生成器，或其他需要种族数据的模块
解决：提供可插拔的种族生成功能，支持多种种族类型，配置化参数，日志追踪，热更新，异常恢复
作者：NovelOS核心架构开发者
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Type, Optional
import json
from pathlib import Path

# ------------------------------ 日志配置 ------------------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.DEBUG)
    formatter = logging