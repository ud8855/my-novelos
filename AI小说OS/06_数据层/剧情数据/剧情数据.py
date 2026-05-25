"""剧情数据模块 - 数据层核心组件
负责剧情节点、事件、关系的持久化管理与查询
提供可插拔存储后端（内存、文件、数据库），支持热插拔与配置化
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import json
import os

# 配置日志
logger = logging.getLogger(__name__)

# ------------------------------
# 数据模型定义
# ------------------------------

@dataclass
class PlotNode:
    """剧情节点数据结构"""
    node_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    content: str = ""
    parent_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "node_id": self.node_id,
            "title": self.title,
            "content": self.content,
            "parent_id": self.parent_id,
            "children_ids": self.children_ids,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlotNode":
        """从字典反序列化"""
        return cls(**data)


# ------------------------------
# 抽象存储接口（可插拔核心）
# ------------------------------

class AbstractPlotStorage(ABC):
    """剧情存储抽象基类，所有存储后端必须实现此接口"""

    @abstractmethod
    def initialize(self, config: Dict[str, Any] = None) -> None:
        """初始化存储，建立连接或准备资源"""
        pass

    @abstractmethod
    def add_node(self, node: PlotNode) -> str:
        """添加一个剧情节点，返回节点ID"""
        pass

    @abstractmethod
    def get_node(self, node_id: str) -> Optional[PlotNode]:
        """根据ID获取剧情节点"""
        pass

    @abstractmethod
    def update_node(self, node: PlotNode) -> bool:
        """更新剧情节点"""
        pass

    @abstractmethod
    def delete_node(self, node_id: str) -> bool:
        """删除剧情节点及其关联关系"""
        pass

    @abstractmethod
    def list_nodes(self, parent_id: Optional[str] = None) -> List[PlotNode]:
        """列出所有剧情节点，可按父节点过滤"""
        pass

    @abstractmethod
    def search_nodes(self, query: Dict[str, Any]) -> List[PlotNode]:
        """复杂条件搜索剧情节点"""
        pass

    @abstractmethod
    def get_full_tree(self, root_id: Optional[str] = None) -> Dict[str, Any]:
        """获取剧情树结构"""
        pass

    @abstractmethod
    def close(self) -> None:
        """关闭存储，释放资源"""
        pass


# ------------------------------
# 内存存储实现（用于开发/测试）
# ------------------------------

class MemoryPlotStorage(AbstractPlotStorage):
    """基于内存的剧情存储，适用于开发和小规模数据"""

    def __init__(self):
        self._nodes: Dict[str, PlotNode] = {}
        self._config: Dict[str, Any] = {}

    def initialize(self, config: Dict[str, Any] = None) -> None:
        self._config = config or {}
        logger.info("内存剧情存储已初始化，当前配置: %s", self._config)
        # 可加载测试数据等

    def add_node(self, node: PlotNode) -> str:
        if node.node_id in self._nodes:
            raise ValueError(f"节点ID {node.node_id} 已存在")
        self._nodes[node.node_id] = node
        # 维护父子关系（简化：只更新父节点的children_ids）
        if node.parent_id and node.parent_id in self._nodes:
            parent = self._nodes[node.parent_id]
            if node.node_id not in parent.children_ids:
                parent.children_ids.append(node.node_id)
        logger.debug("添加剧情节点: %s", node.node_id)
        return node.node_id

    def get_node(self, node_id: str) -> Optional[PlotNode]:
        return self._nodes.get(node_id)

    def update_node(self, node: PlotNode) -> bool:
        if node.node_id not in self._nodes:
            logger.warning("尝试更新不存在的节点: %s", node.node_id)
            return False
        self._nodes[node.node_id] = node
        node.updated_at = datetime.utcnow().isoformat()
        logger.debug("更新剧情节点: %s", node.node_id)
        return True

    def delete_node(self, node_id: str) -> bool:
        if node_id not in self._nodes:
            return False
        node = self._nodes[node_id]
        # 递归删除子节点（简化为非递归）
        for child_id in node.children_ids:
            self.delete_node(child_id)
        # 从父节点移除关联
        if node.parent_id and node.parent_id in self._nodes:
            parent = self._nodes[node.parent_id]
            if node_id in parent.children_ids:
                parent.children_ids.remove(node_id)
        del self._nodes[node_id]
        logger.debug("删除剧情节点: %s", node_id)
        return True

    def list_nodes(self, parent_id: Optional[str] = None) -> List[PlotNode]:
        if parent_id is None:
            return list(self._nodes.values())
        return [node for node in self._nodes.values() if node.parent_id == parent_id]

    def search_nodes(self, query: Dict[str, Any]) -> List[PlotNode]:
        results = []
        for node in self._nodes.values():
            match = True
            for key, value in query.items():
                if key == "title":
                    if value.lower() not in node.title.lower():
                        match = False
                        break
                elif key == "content":
                    if value.lower() not in node.content.lower():
                        match = False
                        break
                elif key == "metadata":
                    # 假设 metadata 是字典，查询其子字段
                    if isinstance(value, dict):
                        for mk, mv in value.items():
                            if node.metadata.get(mk) != mv:
                                match = False
                                break
                    else:
                        if value not in node.metadata.values():
                            match = False
                    if not match:
                        break
                else:
                    # 其他字段直接比较
                    if getattr(node, key, None) != value:
                        match = False
                        break
            if match:
                results.append(node)
        logger.debug("搜索剧情节点，查询条件: %s，找到 %d 条", query, len(results))
        return results

    def get_full_tree(self, root_id: Optional[str] = None) -> Dict[str, Any]:
        """构建树形结构，返回字典"""
        if root_id is None:
            # 找到所有没有父节点的根节点
            roots = [node for node in self._nodes.values() if node.parent_id is None]
        else:
            root_node = self.get_node(root_id)
            roots = [root_node] if root_node else []

        def build_tree(node: PlotNode):
            tree = node.to_dict()
            tree["children"] = []
            for child_id in node.children_ids:
                child = self._nodes.get(child_id)
                if child:
                    tree["children"].append(build_tree(child))
            return tree

        return {"roots": [build_tree(root) for root in roots]}

    def close(self) -> None:
        self._nodes.clear()
        logger.info("内存剧情存储已关闭")


# ------------------------------
# 剧情数据管理器（高级封装）
# ------------------------------

class PlotDataManager:
    """剧情数据统一管理接口，屏蔽底层存储差异"""

    def __init__(self, storage: AbstractPlotStorage, config: Optional[Dict[str, Any]] = None):
        self.storage = storage
        self.config = config or {}
        self.storage.initialize(self.config.get("storage_config", {}))
        logger.info("PlotDataManager 初始化完成，使用存储: %s", type(storage).__name__)

    def create_node(self, title: str, content: str,
                    parent_id: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> str:
        """创建新剧情节点"""
        node = PlotNode(
            title=title,
            content=content,
            parent_id=parent_id,
            metadata=metadata or {}
        )
        return self.storage.add_node(node)

    def get_node(self, node_id: str) -> Optional[PlotNode]:
        """获取剧情节点"""
        return self.storage.get_node(node_id)

    def update_node(self, node_id: str,
                    title: Optional[str] = None,
                    content: Optional[str] = None,
                    metadata: Optional[Dict[str, Any]] = None) -> bool:
        """更新剧情节点部分字段"""
        node = self.storage.get_node(node_id)
        if not node:
            logger.warning("更新失败，节点不存在: %s", node_id)
            return False
        if title is not None:
            node.title = title
        if content is not None:
            node.content = content
        if metadata is not None:
            node.metadata.update(metadata)
        node.updated_at = datetime.utcnow().isoformat()
        return self.storage.update_node(node)

    def delete_node_and_children(self, node_id: str) -> bool:
        """删除节点及其所有后代"""
        return self.storage.delete_node(node_id)

    def list_nodes(self, parent_id: Optional[str] = None) -> List[PlotNode]:
        """列出剧情节点"""
        return self.storage.list_nodes(parent_id)

    def search(self, keyword: str, field: str = "title") -> List[PlotNode]:
        """快速搜索（基于关键词）"""
        return self.storage.search_nodes({field: keyword})

    def get_tree(self, root_id: Optional[str] = None) -> Dict[str, Any]:
        """获取剧情树完整结构"""
        return self.storage.get_full_tree(root_id)

    def close(self):
        self.storage.close()


# ------------------------------
# 配置化工厂函数
# ------------------------------

def create_plot_storage(storage_type: str = "memory",
                        config: Optional[Dict[str, Any]] = None) -> AbstractPlotStorage:
    """根据配置创建剧情存储实例（可插拔）"""
    config = config or {}
    if storage_type == "memory":
        return MemoryPlotStorage()
    elif storage_type == "json_file":
        # 未来扩展：基于JSON文件的存储
        pass  # 待实现
    elif storage_type == "sqlite":
        # 未来扩展：SQLite存储
        pass
    elif storage_type == "mongodb":
        # 未来扩展：MongoDB存储
        pass
    raise ValueError(f"不支持的存储类型: {storage_type}")


# ------------------------------
# 自测逻辑
# ------------------------------

if __name__ == "__main__":
    # 配置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 创建内存存储
    storage = create_plot_storage()
    manager = PlotDataManager(storage)

    # 测试1：创建根节点
    root_id = manager.create_node(
        title="起始",
        content="故事开始于一个小镇，主角醒来发现自己失去了记忆。",
        metadata={"author": "test", "tags": ["悬疑", "失忆"]}
    )
    print(f"创建根节点: {root_id}")

    #