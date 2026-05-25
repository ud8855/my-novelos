"""
时间线面板 - 小说创作时间线可视化组件
负责：展示故事时间线、事件排序、时间线编辑交互
遵循：UI层组件，只负责展示与用户交互，数据通过事件总线或协调层获取
"""
import logging
import json
from typing import Dict, List, Optional, Callable

# 假设存在的事件总线基类（符合核心层接口）
try:
    from core.event_bus import EventBus
except ImportError:
    # 若核心层尚未实现，使用简易占位
    class EventBus:
        """事件总线占位实现，不得直接用于生产环境"""
        _instance = None
        def __init__(self):
            self._subscribers = {}
        def subscribe(self, event_type: str, callback: Callable):
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
        def publish(self, event_type: str, data=None):
            for cb in self._subscribers.get(event_type, []):
                cb(data)

# 假设的UI组件基类
try:
    from ui_base import UIComponent
except ImportError:
    class UIComponent:
        """UI组件基类占位"""
        def __init__(self, config: dict):
            self.config = config
            self.logger = logging.getLogger(self.__class__.__name__)
        def register(self):
            pass
        def unregister(self):
            pass

class TimeLinePanel(UIComponent):
    """
    时间线面板组件
    职责：渲染时间线、处理用户交互（缩放、拖拽、筛选）、对外发送编辑事件
    不直接操作数据库，不调用模型API，数据来源由事件或协调器注入
    """
    
    # 组件标识，用于注册和配置
    COMPONENT_NAME = "timeline_panel"
    # 支持的事件类型
    LISTENED_EVENTS = [
        "timeline.data_updated",
        "novel.chapter_added",
        "novel.event_added",
        "timeline.filter_changed",
        "ui.theme_changed"
    ]
    # 可发出的事件
    EMITTED_EVENTS = [
        "timeline.node_selected",
        "timeline.node_moved",
        "timeline.range_changed",
        "timeline.edit_request"
    ]

    def __init__(self, config: Optional[Dict] = None, event_bus: Optional['EventBus'] = None):
        """
        初始化时间线面板
        :param config: 配置字典，可包含 display_options, interaction, data_source 等
        :param event_bus: 事件总线实例，若未提供则使用默认实例（需先注册）
        """
        # 赋予默认配置
        default_config = {
            "display": {
                "show_grid": True,
                "grid_interval": 1,           # 时间网格间隔（小时/天/章节）
                "default_range": 50,           # 默认显示条目数
                "theme": "dark"
            },
            "interaction": {
                "enable_drag": True,
                "enable_zoom": True,
                "enable_filter": True,
                "enable_edit": False
            },
            "data_source": {
                "type": "eventbus",            # 数据来源：eventbus, direct（禁止直连数据库）, mock
                "mock_data_path": "mock/timeline.json"
            }
        }
        merged_config = {**default_config, **(config or {})}
        super().__init__(merged_config)
        
        # 初始化日志
        self.logger = logging.getLogger(f"NovelOS.UI.{self.COMPONENT_NAME}")
        self.logger.info("时间线面板组件初始化开始")
        
        # 内部状态
        self._current_data: List[Dict] = []      # 当前展示的时间线事件列表
        self._filter_conditions: Dict = {}       # 筛选条件
        self._display_range: tuple = (0, 50)     # 当前可视范围
        self._selected_node_id: Optional[str] = None
        
        # 事件总线绑定
        self.event_bus = event_bus or EventBus()
        self._registered = False
        self._register_events()
        
        self.logger.info("时间线面板组件初始化完成")
    
    def _register_events(self):
        """向事件总线订阅关心的事件，实现可插拔"""
        if self._registered:
            return
        try:
            for evt in self.LISTENED_EVENTS:
                self.event_bus.subscribe(evt, self._handle_event)
            self._registered = True
            self.logger.debug(f"已订阅事件: {self.LISTENED_EVENTS}")
        except Exception as e:
            self.logger.error(f"订阅事件失败: {e}", exc_info=True)
            raise
    
    def _unregister_events(self):
        """取消事件订阅（移除该组件的监听器）"""
        # 注意：简单实现中可能无法精确移除，这里用占位表示可插拔设计
        self._registered = False
        self.logger.debug("事件监听已标记为注销")
    
    def _handle_event(self, event_data):
        """
        统一事件处理入口，根据事件类型分发到具体处理方法
        :param event_data: 事件携带数据，期望包含 'type' 字段
        """
        if not isinstance(event_data, dict) or 'type' not in event_data:
            self.logger.warning(f"收到无效事件数据: {event_data}")
            return
        
        event_type = event_data['type']
        handler_map = {
            "timeline.data_updated": self._on_data_updated,
            "novel.chapter_added": self._on_chapter_added,
            "novel.event_added": self._on_event_added,
            "timeline.filter_changed": self._on_filter_changed,
            "ui.theme_changed": self._on_theme_changed
        }
        handler = handler_map.get(event_type)
        if handler:
            try:
                handler(event_data.get('payload', {}))
            except Exception as e:
                self.logger.error(f"处理事件 {event_type} 失败: {e}", exc_info=True)
        else:
            self.logger.debug(f"未处理的事件类型: {event_type}")
    
    def _on_data_updated(self, payload: dict):
        """当完整时间线数据更新时调用"""
        new_data = payload.get('events', [])
        self._current_data = new_data
        self.logger.info(f"时间线数据已更新，共 {len(new_data)} 个事件")
        self._render()
    
    def _on_chapter_added(self, payload: dict):
        """新增章节时，可能需要在时间线插入标记"""
        chapter_info = payload.get('chapter')
        if chapter_info:
            # 此处仅记录日志，实际渲染逻辑可扩展
            self.logger.info(f"时间线感知到新章节: {chapter_info.get('title')}")
            self._render()  # 可能重新计算布局
    
    def _on_event_added(self, payload: dict):
        """新增故事事件时，加入时间线"""
        event = payload.get('event')
        if event:
            self._current_data.append(event)
            self._sort_events()
            self.logger.info(f"时间线添加新事件: {event.get('id')}")
            self._render()
    
    def _on_filter_changed(self, payload: dict):
        """筛选条件变化"""
        self._filter_conditions = payload.get('filters', {})
        self.logger.info(f"时间线筛选条件更新: {self._filter_conditions}")
        self._render()
    
    def _on_theme_changed(self, payload: dict):
        """主题变化，更新显示样式"""
        theme = payload.get('theme', 'dark')
        self.config['display']['theme'] = theme
        self.logger.info(f"时间线主题切换为: {theme}")
        self._render()
    
    def _sort_events(self):
        """按时间排序事件列表（需事件字典含 'timestamp' 键）"""
        try:
            self._current_data.sort(key=lambda e: e.get('timestamp', 0))
        except Exception as e:
            self.logger.warning(f"事件排序失败: {e}")
    
    def _render(self):
        """
        核心渲染函数（占位）
        实际项目中会调用UI框架重绘面板
        这里仅输出日志表示渲染请求
        """
        self.logger.debug("时间线重新渲染")
        # 虚拟渲染：可在此更新内部状态，等待外部渲染引擎调用 get_display_data()
        self._update_display_range()
    
    def _update_display_range(self):
        """根据当前数据和筛选条件计算可视范围"""
        total = len(self._current_data)
        self._display_range = (0, min(total, self.config['display']['default_range']))
    
    def get_display_data(self) -> List[Dict]:
        """
        提供给渲染引擎的当前展示数据（筛选后）
        :return: 应该展示的事件列表
        """
        # 简单筛选示例：假设事件有 'tags' 字段，筛选条件 {'tags': ['romance']}
        filtered = self._current_data
        if 'tags' in self._filter_conditions:
            required_tags = set(self._filter_conditions['tags'])
            filtered = [e for e in filtered if required_tags.issubset(set(e.get('tags', [])))]
        # 裁剪可视范围
        start, end = self._display_range
        return filtered[start:end]
    
    def select_node(self, node_id: str):
        """选择时间线上的一个节点，并发布事件"""
        self._selected_node_id = node_id
        self.event_bus.publish("timeline.node_selected", {"node_id": node_id})
        self.logger.info(f"选中时间线节点: {node_id}")
    
    def move_node(self, node_id: str, new_timestamp: float):
        """移动节点（用户拖拽），发布移动事件"""
        for event in self._current_data:
            if event.get('id') == node_id:
                event['timestamp'] = new_timestamp
                break
        self._sort_events()
        self.event_bus.publish("timeline.node_moved", {"node_id": node_id, "new_timestamp": new_timestamp})
        self.logger.info(f"节点 {node_id} 移动到时间 {new_timestamp}")
        self._render()
    
    def zoom_in(self):
        """放大时间线（减少显示条目数）"""
        self.config['display']['default_range'] = max(1, self.config['display']['default_range'] - 10)
        self._update_display_range()
        self._render()
        self.logger.debug("时间线放大")
    
    def zoom_out(self):
        """缩小时间线（增加显示条目数）"""
        self.config['display']['default_range'] += 10
        self._update_display_range()
        self._render()
        self.logger.debug("时间线缩小")
    
    def set_filter(self, filter_dict: Dict):
        """设置筛选条件，并发布事件（通常由工具栏触发）"""
        self._filter_conditions = filter_dict
        self.event_bus.publish("timeline.filter_changed", {"filters": filter_dict})
        self._render()