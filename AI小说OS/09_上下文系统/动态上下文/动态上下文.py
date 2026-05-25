import logging
import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

# --- 配置管理 ---
class DynamicContextConfig:
    """
    动态上下文配置管理器
    负责加载/保存配置，支持热更新（文件监控可后续扩展）
    """
    DEFAULT_CONFIG_PATH = "config/dynamic_context.json"

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._config: Dict[str, Any] = self._load_or_default()

    def _load_or_default(self) -> Dict[str, Any]:
        """加载配置，若文件不存在则返回默认配置"""
        default_config = {
            "enabled": True,
            "max_history_size": 100,          # 上下文事件最大记录数
            "update_interval": 1.0,           # 更新间隔（秒）
            "priority_sources": ["action", "emotion", "chapter"],   # 上下文源优先级
            "source_configs": {
                "action": {"max_events": 30},
                "emotion": {"max_events": 20},
                "chapter": {"max_events": 10},
                "custom": {"max_events": 50}
            }
        }
        if not os.path.exists(self.config_path):
            self._config = default_config
            self.save()
        else:
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
            except Exception:
                logging.getLogger("DynamicContext").warning(
                    f"配置加载失败，使用默认配置。路径: {self.config_path}"
                )
                self._config = default_config
        return self._config

    def save(self) -> None:
        """保存配置到文件"""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self._config.get(key, default)

    def reload(self) -> None:
        """重新加载配置（热更新支持）"""
        self._config = self._load_or_default()
        logging.getLogger("DynamicContext").info("动态上下文配置已重新加载")


# --- 上下文事件基类 ---
@dataclass
class ContextEvent:
    """
    上下文事件基类
    所有动态上下文变化都以事件形式存在
    """
    source: str                                 # 来源标识（如 action, emotion, chapter）
    event_type: str                             # 事件类型（如 "character_act", "plot_twist"）
    data: Dict[str, Any] = field(default_factory=dict)  # 事件携带的数据
    timestamp: float = 0.0                      # 时间戳（UNIX时间，由系统填充）
    priority: int = 0                           # 优先级（越大越重要）

    def __post_init__(self):
        import time
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ContextEvent":
        return cls(
            source=d["source"],
            event_type=d["event_type"],
            data=d.get("data", {}),
            timestamp=d.get("timestamp", 0.0),
            priority=d.get("priority", 0),
        )


# --- 上下文源插件接口 ---
class IContextSource(ABC):
    """
    上下文源抽象接口
    每个源负责生成特定类型的动态上下文事件
    实现该接口即可插拔式新增上下文源
    """
    @abstractmethod
    def get_source_name(self) -> str:
        """返回源名称，用于标识"""
        pass

    @abstractmethod
    def fetch_events(self) -> List[ContextEvent]:
        """
        获取当前产生的事件列表
        系统会定期调用该方法
        """
        pass

    @abstractmethod
    def configure(self, source_config: Dict[str, Any]) -> None:
        """根据配置初始化或更新源参数"""
        pass

    @abstractmethod
    def reset(self) -> None:
        """重置源状态（如用户开始新章节时调用）"""
        pass


# --- 动态上下文核心引擎 ---
class DynamicContextEngine:
    """
    动态上下文引擎
    负责管理多个上下文源，合并事件，维护上下文状态，并提供查询接口
    支持热插拔（注册/注销源）
    """
    def __init__(self, config_path: Optional[str] = None):
        self.log = logging.getLogger("DynamicContext")
        self.config = DynamicContextConfig(config_path)
        self.sources: Dict[str, IContextSource] = {}
        self.event_history: List[ContextEvent] = []
        self.max_history = self.config.get("max_history_size", 100)
        # 初始化后加载默认源（可配置，这里先留空，由外部注册）
        self.log.info("动态上下文引擎初始化完成")

    def register_source(self, source: IContextSource) -> None:
        """注册上下文源，若已存在则更新"""
        name = source.get_source_name()
        if name in self.sources:
            self.log.warning(f"上下文源 {name} 已存在，将被覆盖")
        self.sources[name] = source
        # 应用该源的配置
        source_configs = self.config.get("source_configs", {})
        source_config = source_configs.get(name, {})
        source.configure(source_config)
        self.log.info(f"上下文源已注册: {name}")

    def unregister_source(self, source_name: str) -> None:
        """注销上下文源"""
        if source_name in self.sources:
            del self.sources[source_name]
            self.log.info(f"上下文源已注销: {source_name}")
        else:
            self.log.warning(f"尝试注销不存在的源: {source_name}")

    def update(self) -> List[ContextEvent]:
        """
        触发一次上下文的更新：从所有源拉取事件，合并并过滤
        返回本次新增的事件列表（同时存入历史）
        """
        new_events = []
        priority_order = self.config.get("priority_sources", [])
        # 按优先级排序源名称
        ordered_sources = sorted(
            self.sources.keys(),
            key=lambda x: priority_order.index(x) if x in priority_order else len(priority_order)
        )
        for name in ordered_sources:
            source = self.sources[name]
            try:
                events = source.fetch_events()
                # 赋予优先级（可基于源默认值，也可从配置获取）
                for event in events:
                    event.priority = priority_order.index(name) if name in priority_order else 100
                    new_events.append(event)
            except Exception as e:
                self.log.error(f"上下文源 {name} 获取事件失败: {e}", exc_info=True)
        # 合并历史，截断超出上限的部分
        self.event_history.extend(new_events)
        if len(self.event_history) > self.max_history:
            self.event_history = self.event_history[-self.max_history:]
        self.log.debug(f"上下文更新完成，新增事件数: {len(new_events)}")
        return new_events

    def get_context_summary(self, max_events: int = 20) -> List[Dict[str, Any]]:
        """
        获取最近的上下文摘要（返回事件字典列表）
        """
        return [e.to_dict() for e in self.event_history[-max_events:]]

    def query(self, source: Optional[str] = None,
              event_type: Optional[str] = None,
              limit: int = 10) -> List[Dict[str, Any]]:
        """按条件查询上下文事件"""
        result = []
        for e in reversed(self.event_history):
            if source and e.source != source:
                continue
            if event_type and e.event_type != event_type:
                continue
            result.append(e.to_dict())
            if len(result) >= limit:
                break
        return result

    def reset(self):
        """重置所有上下文源及历史记录"""
        for source in self.sources.values():
            try:
                source.reset()
            except Exception as e:
                self.log.error(f"重置源 {source.get_source_name()} 失败: {e}")
        self.event_history.clear()
        self.log.info("动态上下文已重置")

    def reload_config(self):
        """重新加载配置，并应用到所有源"""
        self.config.reload()
        self.max_history = self.config.get("max_history_size", 100)
        # 更新每个源的配置
        source_configs = self.config.get("source_configs", {})
        for name, source in self.sources.items():
            source_config = source_configs.get(name, {})
            try:
                source.configure(source_config)
            except Exception as e:
                self.log.error(f"更新源 {name} 配置失败: {e}")
        self.log.info("动态上下文配置已重载")


# --- 内置示例源：动作上下文源 ---
class ActionContextSource(IContextSource):
    """
    动作上下文源示例：用于生成角色动作相关事件
    实际开发中可对接游戏引擎输入或用户操作日志
    """
    def __init__(self):
        self.name = "action"
        self.max_events = 30
        self._events: List[ContextEvent] = []

    def get_source_name(self) -> str:
        return self.name

    def configure(self, source_config: Dict[str, Any]) -> None:
        self.max_events = source_config.get("max_events", self.max_events)

    def fetch_events(self) -> List[ContextEvent]:
        # 模拟：此处应直接返回已产生的事件，并清空内部缓冲
        events = self._events[:self.max_events]
        self._events = []
        return events

    def reset(self) -> None:
        self._events.clear()

    def add_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """外部可调用此方法添加事件（实际应由某种钩子触发）"""
        if len(self._events) >= self.max_events:
            self._events.pop(0)
        event = ContextEvent(source=self.name, event_type=event_type, data=data)
        self._events.append(event)


# --- 自测代码 ---
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    print("=== 动态上下文模块自测 ===")
    # 创建配置（临时目录）
    test_config_path = "test_dynamic_context_config.json"
    try:
        os.remove(test_config_path)
    except:
        pass

    engine = DynamicContextEngine(test_config_path)
    print("引擎创建成功，当前源数量:", len(engine.sources))

    # 注册一个动作源
    action_source = ActionContextSource()
    engine.register_source(action_source)
    print("已注册动作源")

    # 手动添加一些事件
    action_source.add_event("character_move", {"character": "主角", "location": "酒馆"})
    action_source.add_event("dialogue", {"speaker": "主角", "text": "今晚的月亮真圆"})

    # 执行更新
    new_events = engine.update()
    print("更新后获取事件数:", len(new_events))
    for e in new_events:
        print(" - ", e.to_dict())

    # 查询
    actions = engine.query(source="action", limit=5)
    print("查询动作事件:", actions)

    # 测试重置
    engine.reset()
    print("重置后历史长度:", len(engine.event_history))

    # 清理测试配置文件
    try:
        os.remove(test_config_path)
    except:
        pass
    print("自测完成。")