"""
悬念系统：故事悬念管理模块
职责：设置、追踪、揭示、评估悬念状态，支持活跃度与重要性管理。
可插拔：通过继承 SuspenseEngine 或注入策略实现自定义行为。
配置化：参数集中在 SuspenseConfig，日志默认使用标准 logging。
"""
import logging
import uuid
from typing import Dict, List, Optional, Any

# ================== 配置 ==================
class SuspenseConfig:
    """悬念系统配置参数，可通过字典或关键字参数初始化"""
    def __init__(self, **kwargs: Any) -> None:
        self.max_active_suspense: int = kwargs.get('max_active_suspense', 10)
        self.min_importance_for_active: float = kwargs.get('min_importance_for_active', 0.3)
        self.auto_reveal_threshold: float = kwargs.get('auto_reveal_threshold', 0.8)
        self.preserve_history: bool = kwargs.get('preserve_history', True)

    def to_dict(self) -> Dict[str, Any]:
        """导出配置为字典（便于序列化）"""
        return {
            'max_active_suspense': self.max_active_suspense,
            'min_importance_for_active': self.min_importance_for_active,
            'auto_reveal_threshold': self.auto_reveal_threshold,
            'preserve_history': self.preserve_history,
        }

# ================== 悬念节点 ==================
class SuspenseNode:
    """单个悬念实体"""
    def __init__(self, suspense_id: str, description: str, importance: float = 0.5) -> None:
        self.suspense_id: str = suspense_id
        self.description: str = description
        self.importance: float = importance
        self.status: str = "active"        # active, pending_reveal, revealed, abandoned
        self.reveal_progress: float = 0.0  # 0.0 - 1.0

    def update_status(self, new_status: str) -> None:
        """更新悬念状态"""
        self.status = new_status

    def update_progress(self, progress: float) -> None:
        """更新揭示进度，progress 应在 0.0 - 1.0 之间"""
        self.reveal_progress = max(0.0, min(1.0, progress))

    def to_dict(self) -> Dict[str, Any]:
        """序列化悬念节点"""
        return {
            'suspense_id': self.suspense_id,
            'description': self.description,
            'importance': self.importance,
            'status': self.status,
            'reveal_progress': self.reveal_progress,
        }

# ================== 悬念引擎 ==================
class SuspenseEngine:
    """悬念系统核心引擎，负责生命周期管理和基本操作"""

    def __init__(self, config: Optional[SuspenseConfig] = None) -> None:
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.config: SuspenseConfig = config or SuspenseConfig()
        self.active_suspense: Dict[str, SuspenseNode] = {}      # 当前活跃悬念
        self.revealed_history: List[SuspenseNode] = []           # 历史悬念（如果配置开启）
        self._setup_logging()

    def _setup_logging(self) -> None:
        """配置基础日志处理器（仅在无 handler 时添加）"""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def _generate_id(self) -> str:
        """生成唯一悬念标识"""
        return str(uuid.uuid4())[:8]

    def add_suspense(self, description: str, importance: float = 0.5) -> Optional[str]:
        """
        添加一个新的悬念
        :param description: 悬念描述
        :param importance: 重要性（0-1）
        :return: 新悬念ID，若超出上限则返回 None
        """
        if len(self.active_suspense) >= self.config.max_active_suspense:
            self.logger.warning("达到最大活跃悬念数量，无法添加新悬念")
            return None
        if importance < self.config.min_importance_for_active:
            self.logger.info(f"悬念重要性 {importance} 低于阈值，不予添加")
            return None
        sid = self._generate_id()
        node = SuspenseNode(sid, description, importance)
        self.active_suspense[sid] = node
        self.logger.info(f"添加悬念 [{sid}]: {description} (重要性 {importance})")
        return sid

    def get_active_suspense(self) -> List[SuspenseNode]:
        """获取当前所有活跃状态的悬念"""
        return [node for node in self.active_suspense.values() if node.status == 'active']

    def get_all_active_nodes(self) -> List[SuspenseNode]:
        """获取所有活跃节点（包含 pending_reveal）"""
        return list(self.active_suspense.values())

    def reveal_suspense(self, suspense_id: str, partially: bool = False, progress: float = 1.0) -> bool:
        """
        揭示悬念（完全揭示或部分推进）
        :param suspense_id: 悬念ID
        :param partially: 是否部分揭示
        :param progress: 若部分揭示，增加的进度值
        :return: 操作是否成功
        """
        node = self.active_suspense.get(suspense_id)
        if not node:
            self.logger.warning(f"悬念 {suspense_id} 不存在")
            return False
        if node.status == 'revealed':
            self.logger.info(f"悬念 {suspense_id} 已处于揭示状态")
            return True
        if partially:
            node.update_progress(node.reveal_progress + progress)
            self.logger.info(f"悬念 {suspense_id} 进度更新为 {node.reveal_progress:.2f}")
            if node.reveal_progress >= self.config.auto_reveal_threshold:
                self._finalize_reveal(node)
        else:
            node.update_progress(1.0)
            self._finalize_reveal(node)
        return True

    def _finalize_reveal(self, node: SuspenseNode) -> None:
        """完成揭示并将节点移至历史（如果配置开启）"""
        node.update_status('revealed')
        self.logger.info(f"悬念 [{node.suspense_id}] 已揭示")
        if self.config.preserve_history:
            self.revealed_history.append(node)
        del self.active_suspense[node.suspense_id]

    def abandon_suspense(self, suspense_id: str) -> bool:
        """放弃一个悬念（不再追踪）"""
        node = self.active_suspense.pop(suspense_id, None)
        if node:
            node.update_status('abandoned')
            self.logger.info(f"放弃悬念 [{suspense_id}]")
            if self.config.preserve_history:
                self.revealed_history.append(node)
            return True
        self.logger.warning(f"放弃失败，悬念 {suspense_id} 不存在")
        return False

    def query_suspense(self, suspense_id: str) -> Optional[Dict[str, Any]]:
        """查询单个悬念信息（含历史）"""
        node = self.active_suspense.get(suspense_id)
        if not node and self.config.preserve_history:
            for hist in self.revealed_history:
                if hist.suspense_id == suspense_id:
                    node = hist
                    break
        return node.to_dict() if node else None

    def get_statistics(self) -> Dict[str, int]:
        """返回简单的统计