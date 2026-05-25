"""
社交系统模块
属于：11_角色引擎/社交系统
负责管理角色之间的社交关系、互动事件、社交网络等。
支持配置化初始化、日志记录、热更新接口、异常恢复。
可插拔：通过配置参数独立实例化。
"""

import logging
from typing import Dict, List, Optional, Any

# 默认配置
DEFAULT_CONFIG = {
    "logging_level": "INFO",
    "enable_relationship_decay": False,  # 关系自然衰减开关
    "max_relationship_value": 100,       # 关系值上限
    "min_relationship_value": -100,      # 关系值下限
    "event_triggers": {},                # 社交事件自动触发的关系修改规则
}


class SocialSystem:
    """
    社交系统核心类
    维护角色间的社交图谱，处理社交事件，支持运行时配置更新与状态序列化。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化社交系统
        :param config: 可选配置字典，会与默认配置合并
        """
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)

        # 配置日志
        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup_logging()

        # 关系图谱：{character_id: {other_id: value}}
        self.relationship_graph = {}
        # 事件日志（可根据需求实现持久化）
        self.event_log = []

        self.logger.info("社交系统初始化完成")

    def _setup_logging(self):
        """根据配置设置日志级别和格式"""
        level_name = self.config.get("logging_level", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)
        self.logger.setLevel(level)
        if not self.logger.handlers:
            handler = logging.Stream