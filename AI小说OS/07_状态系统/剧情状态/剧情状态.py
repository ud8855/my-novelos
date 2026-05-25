"""
剧情状态模块
负责管理小说剧情的状态，包括当前剧情节点、已触发事件、角色状态等。
特点：
- 可插拔状态存储后端
- 日志记录所有状态变更
- 配置化初始状态
- 自测用例
"""

import logging
from typing import Any, Dict, Optional, List
from abc import ABC, abstractmethod

# 配置默认日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('PlotState')


class PlotStateStorage(ABC):
    """抽象状态存储接口，支持可插拔存储后端"""

    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """加载剧情状态"""
        pass

    @abstractmethod
    def save(self, state: Dict[str, Any]) -> None:
        """保存剧情状态"""
        pass

    @abstractmethod
    def clear(self) -> None:
        """清除状态"""
        pass


class MemoryPlotStateStorage(PlotStateStorage):
    """基于内存的状态存储，用于测试或简单场景"""

    def __init__(self):
        self._state = {}

    def load(self) -> Dict[str, Any]:
        return self._state.copy()

    def save(self, state: Dict[str, Any]) -> None:
        self._state = state.copy()
        logger.info("剧情状态已保存到内存")

    def clear(self) -> None:
        self._state.clear()
        logger.info("剧情状态已清除")


class PlotState:
    """
    剧情状态管理器
    维护当前剧情节点、历史事件、角色状态等。
    支持配置化初始状态，可插拔存储后端。
    """

    def __init__(self, storage: PlotStateStorage = None, initial_config: Dict[str, Any] = None):
        """
        初始化剧情状态
        :param storage: 状态存储后端实例，不提供则使用内存存储
        :param initial_config: 初始状态配置字典，例如：
            {
                "current_node": "start",
                "triggered_events": [],
                "character_states": {},
                "global_flags": {}
            }
        """
        self.storage = storage if storage else MemoryPlotStateStorage()
        self.logger = logging.getLogger('PlotState')

        # 尝试加载已保存的状态，如果没有则使用初始配置
        saved_state = self.storage.load()
        if saved_state:
            self.state = saved_state
            self.logger.info("已从存储加载剧情状态")
        else:
            self.state = initial_config if initial_config else self._default_state()
            self.storage.save(self.state)
            self.logger.info("使用初始配置初始化剧情状态")

    @staticmethod
    def _default_state() -> Dict[str, Any]:
        """返回默认状态结构"""
        return {
            "current_node": "start",
            "triggered_events": [],
            "character_states": {},
            "global_flags": {}
        }

    def get_current_node(self) -> str:
        """获取当前剧情节点标识"""
        return self.state.get("current_node", "start")

    def set_current_node(self, node_id: str) -> None:
        """设置当前剧情节点"""
        self.state["current_node"] = node_id
        self.storage.save(self.state)
        self.logger.info(f"剧情节点切换至: {node_id}")

    def add_triggered_event(self, event_id: str) -> None:
        """添加已触发的事件ID"""
        if event_id not in self.state["triggered_events"]:
            self.state["triggered_events"].append(event_id)
            self.storage.save(self.state)
            self.logger.info(f"事件已触发: {event_id}")

    def is_event_triggered(self, event_id: str) -> bool:
        """检查事件是否已触发"""
        return event_id in self.state["triggered_events"]

    def get_character_state(self, character_id: str) -> Optional[Dict[str, Any]]:
        """获取角色状态"""
        return self.state["character_states"].get(character_id)

    def set_character_state(self, character_id: str, state: Dict[str, Any]) -> None:
        """设置或更新角色状态"""
        self.state["character_states"][character_id] = state
        self.storage.save(self.state)
        self.logger.info(f"角色 {character_id} 状态已更新")

    def get_global_flag(self, flag_name: str) -> Any:
        """获取全局标志的值"""
        return self.state["global_flags"].get(flag_name)

    def set_global_flag(self, flag_name: str, value: Any) -> None:
        """设置全局标志"""
        self.state["global_flags"][flag_name] = value
        self.storage.save(self.state)
        self.logger.info(f"全局标志 {flag_name} 设置为 {value}")

    def reset_to_initial(self, initial_config: Dict[str, Any] = None) -> None:
        """重置剧情状态