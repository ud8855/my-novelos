"""
21_API模型/Qwen接口.py
属于: 21_API模型层
依赖: 20_模型协同层的模型基类 (BaseModelAPI)
被调用: 20_模型协同的模型管理器
功能: 封装通义千问(Qwen)模型API调用，提供统一接口给上层
"""

import os
import json
import logging
from typing import Optional, Dict, Any, Generator, AsyncGenerator

# 确保可以导入上级目录模块
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

# 导入模型基类
try:
    from model_base import BaseModelAPI
except ImportError:
    # 如果直接运行此文件，可能需要调整路径
    try:
        from twenty_model_collaboration.model_base import BaseModelAPI
    except ImportError:
        # 定义一个临时基类用于自测
        class BaseModelAPI:
            def __init__(self, model_name: str = "qwen"):
                self.model_name = model_name
                self.logger = logging.getLogger(self.__class__.__name__)
            def chat(self, prompt: str, **kwargs) -> str: