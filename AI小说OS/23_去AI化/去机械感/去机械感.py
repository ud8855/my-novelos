# 去机械感.py
# 模块路径: 23_去AI化/去机械感.py
# 功能：文本去机械感处理，减少AI生成痕迹，使输出更自然。
# 依赖：无外部依赖，可调用模型分析（但骨架暂不做实际调用，定义接口）
# 被调用：由小说生成流程中的后处理模块调用
# 设计原则：可插拔规则、配置化规则集、日志记录、自测支持

import logging
import json
from typing import List, Callable, Dict, Any
from pathlib import Path

# 日志配置 (可插拔，外部可覆盖)
logger = logging.getLogger("NovelOS.DeMechanizer")

class DeMechanizerConfig:
    """配置管理器，加载并维护去机械感规则配置"""
    def __init__(self, config_path: str = None):
        self.rules = []  # 规则列表，每个规则是 dict: {'name': str, 'type': str, 'params': dict, 'priority': int}
        if config_path:
            self.load_config(config_path)
        else:
            # 默认配置
            self._set_default_config()

    def _set_default_config(self):
        """设置默认规则配置，可以根据需要扩展"""
        self.rules = [
            {"name": "remove_repetition", "type": "regex", "params": {"pattern": r"([。！？])\s*([。！？])+", "repl": r"\1"}, "priority": 1},
            {"name": "add_variety_punctuation", "type": "replace", "params": {"old": "；；", "new": "；"}, "priority": 2},
            # 更多规则可以在这里添加，或通过配置文件加载
        ]
        logger.info("使用默认去机械感规则配置")

    def load_config(self, config_path: str):
        """从JSON文件加载规则配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f