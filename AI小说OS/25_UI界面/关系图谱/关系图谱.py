""" 
关系图谱模块 (RelationGraph)
所属层: 25_UI界面/关系图谱
依赖: 核心系统 (通过协议接口访问, 不直接跨层)
被调用: 上层UI框架或其他展示模块
功能: 可视化展示小说人物、情节、地点等实体间的关系图谱
状态: 骨架阶段，实现接口定义、日志、配置、可插拔
"""

import logging
import configparser
import os
from typing import Dict, List, Any, Optional

# 模块默认配置常量
DEFAULT_CONFIG = {
    "graph_type": "force-directed",   # 图谱布局类型: force-directed, tree, circular
    "enable_labels": True,
    "node_color_map": {"person": "blue", "location": "green", "event": "red", "item": "yellow"},
    "max_visible_nodes": 100,
    "auto_update_interval": 0,        # 自动刷新间隔(秒), 0表示手动
}

class RelationGraphConfig:
    """关系图谱配置管理，支持配置化与热更新"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = configparser.ConfigParser()
        self.config.read_dict({"DEFAULT": DEFAULT_CONFIG})
        if config_path:
            self.load_from_file(config_path)
    
    def load_from_file(self, path: str):
        """从配置文件加载设置"""
        if os.path.exists(path):
            self.config.read(path, encoding='utf-8')
            logging.getLogger(__name__).info(f"配置文件已加载: {path}")
        else:
            logging.getLogger(__name__).warning(f"配置文件不存在: {path}，使用默认配置")
    
    def get(self, key: str, fallback=None):
        """获取配置项"""
        try:
            return self.config.get("DEFAULT", key)
        except configparser.NoOptionError:
            return fallback or DEFAULT_CONFIG.get(key)

    def set(self, key: str, value: Any):
        """动态设置配置项"""
        self.config.set("DEFAULT", key, str(value))

class RelationGraph:
    """
    关系图谱核心类
    负责图谱数据的接收、转换、更新以及与UI渲染器对接
    """

    def __init__(self, config: Optional[RelationGraphConfig] = None):
        self.logger = logging.getLogger(f"{__name__}.RelationGraph")
        self.config = config or RelationGraphConfig()
        self._data: Dict[str, Any] = {"nodes": [], "edges": []}
        self._is_initialized = False
        self._setup_logging()
        self.initialize()
    
    def _setup_logging(self):
        """配置模块日志 (可插拔式)"""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def initialize(self):
        """初始化图谱资源，建立与下游服务的接口连接(桩)"""
        self.logger.info("关系图谱模块初始化开始...")
        # TODO: 未来版本中，这里会通过协议向模型协同层注册监听或请求数据接口
        self._is_initialized = True
        self.logger.info("关系图谱模块初始化完成")

    def load_data(self, raw_data: List[dict]):
        """
        接收并解析来自核心系统的关系数据 (协议接口)
        raw_data: 符合协议格式的关系列表，每条包含 source, target, relation, type 等
        """
        self.logger.info(f"接收到关系数据，条目数: {len(raw_data)}")
        # 骨架: 仅缓存原始数据，不做复杂转换
        self._data = {"nodes": [], "edges": []}
        # 简单提取节点和边，留作将来使用
        unique_nodes = {}
        for rel in raw_data:
            source = rel.get("source")
            target = rel.get("target")
            if source:
                unique_nodes[source] = {"id": source, "type": rel.get("source_type", "unknown")}
            if target:
                unique_nodes[target] = {"id": target, "type": rel.get("target_type", "unknown")}
            self._data["edges"].append({
                "from": source,
                "to": target,
                "label": rel.get("relation", ""),
                "type": rel.get("type", "default")
            })
        self._data["nodes"] = list(unique_nodes.values())
        self.logger.debug(f"转换完成: 节点数={len(self._data['nodes'])}, 边数={len(self._data['edges'])}")

    def update_layout(self, layout_type: Optional[str] = None):
        """更新图谱布局(桩)，预留布局算法接口"""
        layout = layout_type or self.config.get("graph_type")
        self.logger.info(f"请求更新布局为: {layout}")
        # 未来将调用布局引擎，目前为骨架

    def render_preview(self) -> str:
        """
        生成图谱的文本预览或简单表示 (仅用于自测)
        返回: 描述字符串
        """
        nodes_count = len(self._data.get("nodes", []))
        edges_count = len(self._data.get("edges", []))
        return f"关系图谱包含 {nodes_count} 个节点, {edges_count} 条边。布局类型: {self.config.get('graph_type')}"

    def shutdown(self):
        """模块关闭清理资源"""
        self.logger.info("关系图谱模块关闭")
        self._is_initialized = False

    @property
    def is_ready(self) -> bool:
        return self._is_initialized


# 模块自测代码
if __name__ == "__main__":
    print("开始 RelationGraph 自测...")
    # 配置日志
    logging.basicConfig(level=logging.INFO)
    
    # 创建配置实例
    config = RelationGraphConfig()
    
    # 创建图谱实例
    graph = RelationGraph(config)
    
    # 测试数据加载 (模拟协议格式)
    test_data = [
        {"source": "主角", "source_type": "person", "target": "神秘老人", "target_type": "person", "relation": "师徒", "type": "人物关系"},
        {"source": "主角", "source_type": "person", "target": "上古遗迹", "target_type": "location", "relation": "探索", "type": "场景事件"},
    ]
    
    graph.load_data(test_data)
    print(graph.render_preview())
    graph.update_layout()
    graph.shutdown()
    print("RelationGraph 自测完成。")