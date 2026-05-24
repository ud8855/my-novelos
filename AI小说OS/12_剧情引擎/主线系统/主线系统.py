"""
12_剧情引擎/主线系统
层：剧情引擎层
依赖：01_核心框架层（配置管理、日志、事件总线）
被调用：引擎调度器、叙事系统
解决：管理主线剧情序列，根据状态推进剧情，触发事件，支持分支与回溯
"""
import logging
import copy
from typing import Dict, Any, List, Optional, Callable
from enum import Enum

# 占位配置加载器（实际应替换为 00_根基层/配置管理）
def placeholder_load_config(config_path: str) -> Dict[str, Any]:
    # 实际项目中应从 00_根基层/配置管理 导入
    return {}

# 占位事件发布器（实际应替换为 01_核心框架层/事件总线）
def placeholder_publish_event(event_type: str, data: Dict[str, Any]) -> None:
    pass

# 占位状态存储（实际应替换为 05_状态系统/情景状态机）
class PlaceholderStateStore:
    def __init__(self):
        self.state = {}
    def get(self, key: str, default=None):
        return self.state.get(key, default)
    def set(self, key: str, value):
        self.state[key] = value
    def update(self, d: Dict):
        self.state.update(d)

class PlotNodeStatus(Enum):
    LOCKED = "locked"        # 未解锁
    AVAILABLE = "available"  # 可触发
    ACTIVE = "active"        # 正在进行
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败

class PlotNode:
    """
    剧情节点，表示一个主线剧情步骤
    """
    def __init__(self, node_id: str, data: Dict[str, Any]):
        self.node_id = node_id
        self.title = data.get("title", "")
        self.description = data.get("description", "")
        self.preconditions: List[str] = data.get("preconditions", [])  # 前置节点ID列表
        self.effects: List[Dict] = data.get("effects", [])  # 完成后触发的效果
        self.children: List[str] = data.get("children", [])  # 子节点ID列表
        self.is_branch_point = data.get("is_branch_point", False)  # 是否分支点
        self.status: PlotNodeStatus = PlotNodeStatus.LOCKED
        self.custom_params: Dict[str, Any] = data.get("custom_params", {})

class MainPlotSystem:
    """
    主线系统：负责管理小说主线剧情的推进、分支、回溯。
    可插拔设计：可通过注入不同的剧情数据源（如文件、数据库）和状态存储来替换实现。
    配置化：剧情结构由外部配置文件定义，通过 load_plot_data() 加载。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None, state_store=None, event_publisher=None, logger=None):
        """
        初始化主线系统
        :param config: 主线剧情配置字典，包含剧情节点信息
        :param state_store: 状态存储对象，遵循 get/set 接口
        :param event_publisher: 事件发布函数，签名: (event_type, data)
        :param logger: 日志记录器
        """
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self.config = config if config is not None else {}
        self.state_store = state_store if state_store is not None else PlaceholderStateStore()
        self.event_publisher = event_publisher if event_publisher is not None else placeholder_publish_event

        self.nodes: Dict[str, PlotNode] = {}  # 所有剧情节点
        self.active_node_ids: List[str] = []   # 当前激活的节点ID（通常只有一个，但分支时可多个）
        self.completed_node_ids: set = set()   # 已完成节点ID集合

        self.on_node_completed_callbacks: List[Callable] = []  # 节点完成回调列表

        # 加载初始剧情数据
        self._initialize()

    def _initialize(self):
        """根据配置初始化剧情节点"""
        raw_nodes = self.config.get("nodes", [])
        if not raw_nodes:
            self.logger.warning("未提供主线剧情节点配置，系统将处于空状态。")
            return
        for node_data in raw_nodes:
            node = PlotNode(node_data["id"], node_data)
            self.nodes[node.node_id] = node
        self.logger.info(f"已加载 {len(self.nodes)} 个主线剧情节点。")

        # 加载状态（若状态存储中已有数据，则恢复状态）
        saved_data = self.state_store.get("main_plot", {})
        if saved_data:
            self.active_node_ids = saved_data.get("active_node_ids", [])
            self.completed_node_ids = set(saved_data.get("completed_node_ids", []))
            # 恢复节点状态
            for node_id, status_str in saved_data.get("node_statuses", {}).items():
                if node_id in self.nodes:
                    self.nodes[node_id].status = PlotNodeStatus(status_str)
            self.logger.info("从状态存储恢复了主线剧情状态。")

        # 如果没有激活节点且存在初始节点，自动激活初始节点
        if not self.active_node_ids:
            initial_node = self.find_initial_nodes()
            if initial_node:
                self.activate_node(initial_node[0])
                self.logger.info(f"自动激活初始节点: {initial_node[0]}")

    def load_plot_data(self, plot_config: Dict[str, Any]):
        """
        动态加载新的剧情数据（热更新）
        :param plot_config: 包含 nodes 的字典
        """
        # 简单替换，实际可做增量更新
        self.nodes.clear()
        self.active_node_ids.clear()
        self.completed_node_ids.clear()
        self.config = plot_config
        self._initialize()
        self.logger.info("主线剧情数据已重新加载。")

    def find_initial_nodes(self) -> List[str]:
        """查找没有前置条件或前置条件为空的节点，作为初始节点"""
        initial = []
        for node in self.nodes.values():
            if not node.preconditions:
                initial.append(node.node_id)
        return initial

    def activate_node(self, node_id: str) -> bool:
        """
        激活一个剧情节点，使其进入 ACTIVE 状态
        :param node_id: 节点ID
        :return: 是否成功激活
        """
        if node_id not in self.nodes:
            self.logger.error(f"企图激活不存在的节点: {node_id}")
            return False
        node = self.nodes[node_id]
        if node.status not in (PlotNodeStatus.LOCKED, PlotNodeStatus.AVAILABLE):
            self.logger.warning(f"节点 {node_id} 当前状态为 {node.status}，无法激活。")
            return False

        node.status = PlotNodeStatus.ACTIVE
        self.active_node_ids.append(node_id)
        self._save_state()
        self.logger.info(f"主线节点激活: {node_id} ({node.title})")
        self.event_publisher("main_plot.node_activated", {"node_id": node_id, "title": node.title})
        return True

    def complete_node(self, node_id: str) -> bool:
        """
        完成当前节点，处理效果并激活后续节点
        :param node_id: 要完成的节点ID
        :return: 是否成功完成
        """
        if node_id not in self.nodes:
            self.logger.error(f"企图完成不存在的节点: {node_id}")
            return False
        node = self.nodes[node_id]
        if node.status != PlotNodeStatus.ACTIVE:
            self.logger.warning(f"节点 {node_id} 不是激活状态，无法完成。当前状态: {node.status}")
            return False

        node.status = PlotNodeStatus.COMPLETED
        self.completed_node_ids.add(node_id)
        if node_id in self.active_node_ids:
            self.active_node_ids.remove(node_id)

        # 应用效果（可通过事件或直接修改状态）
        for effect in node.effects:
            self._apply_effect(effect)

        # 激活子节点（分支点需要进行选择处理，这里暂时直接激活所有可达子节点）
        for child_id in node.children:
            if child_id in self.nodes:
                child = self.nodes[child_id]
                if self._check_preconditions(child):
                    child.status = PlotNodeStatus.AVAILABLE
                    # 是否自动激活？主线通常自动推进，这里自动激活
                    self.activate_node(child_id)

        self._save_state()
        self.logger.info(f"主线节点完成: {node_id} ({node.title})")
        self.event_publisher("main_plot.node_completed", {"node_id": node_id, "title": node.title})

        # 触发回调
        for callback in self.on_node_completed_callbacks:
            try:
                callback(node_id, self)
            except Exception as e:
                self.logger.exception(f"节点完成回调执行异常: {e}")

        return True

    def _check_preconditions(self, node: PlotNode) -> bool:
        """检查节点的前置条件是否全部完成"""
        for pre_id in node.preconditions:
            if pre_id not in self.completed_node_ids:
                return False
        return True

    def _apply_effect(self, effect: Dict):
        """应用剧情效果（修改状态、触发事件等）"""
        effect_type = effect.get("type", "")
        params = effect.get("params", {})
        if effect_type == "set_state":
            self.state_store.set(params["key"], params["value"])
        elif effect_type == "publish_event":
            self.event_publisher(params["event_type"], params.get("data", {}))
        else:
            self.logger.debug(f"未知的效果类型: {effect_type}")

    def get_active_nodes(self) -> List[PlotNode]:
        """返回当前激活的节点列表"""
        return [self.nodes[nid] for nid in self.active_node_ids if nid in self.nodes]

    def get_node_by_id(self, node_id: str) -> Optional[PlotNode]:
        return self.nodes.get(node_id)

    def is_node_completed(self, node_id: str) -> bool:
        return node_id in self.completed_node_ids

    def get_progress(self) -> Dict[str, Any]:
        """返回主线进度信息"""
        total = len(self.nodes)
        completed = len(self.completed_node_ids)
        return {
            "total_nodes": total,
            "completed_nodes": completed,
            "active_nodes": self.active_node_ids.copy(),
            "progress_percent": (completed / total * 100) if total > 0 else 0
        }

    def register_callback(self, callback: Callable):
        """注册节点完成回调"""
        self.on_node_completed_callbacks.append(callback)

    def remove_callback(self, callback: Callable):
        """移除回调"""
        if callback in self.on_node_completed_callbacks:
            self.on_node_completed_callbacks.remove(callback)

    def _save_state(self):
        """保存当前状态到状态存储（用于恢复与持久化）"""
        node_statuses = {nid: node.status.value for nid, node in self.nodes.items()}
        data = {
            "active_node_ids": self.active_node_ids.copy(),
            "completed_node_ids": list(self.completed_node_ids),
            "node_statuses": node_statuses,
        }
        self.state_store.set("main_plot", data)

    def reset(self):
        """重置主线系统"""
        self.nodes.clear()
        self.active_node_ids.clear()
        self.completed_node_ids.clear()
        self.on_node_completed_callbacks.clear()
        self._initialize()
        self.logger.info("主线系统已重置。")

# ---------- 自测部分 ----------
if __name__ == "__main__":
    # 简单剧情配置
    test_config = {
        "nodes": [
            {
                "id": "start",
                "title": "起始",
                "description": "故事开始",
                "preconditions": [],
                "effects": [],
                "children": ["chapter1"],
                "is_branch_point": False
            },
            {
                "id": "chapter1",
                "title": "第一章",
                "description": "进入第一章",
                "preconditions": ["start"],