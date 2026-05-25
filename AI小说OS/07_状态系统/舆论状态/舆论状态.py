# -*- coding: utf-8 -*-
"""
舆论状态管理模块
职责：
    1. 维护小说世界中公众舆论的实时状态
    2. 提供接口查询舆论倾向、热点事件、传播范围等
    3. 支持热更新、异常恢复、日志记录、配置化加载
    4. 通过抽象数据提供者实现存储解耦，可插拔替换（如内存、数据库、文件）
"""

import logging
import sys
from typing import Any, Dict, List, Optional, Protocol
from abc import ABC, abstractmethod

# -------------------- 日志配置 --------------------
logger = logging.getLogger("NovelOS.PublicOpinion")
logger.setLevel(logging.DEBUG)  # 可配置

if not logger.handlers:
    console = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s"
    )
    console.setFormatter(formatter)
    logger.addHandler(console)
    logger.propagate = False  # 防止重复输出

# -------------------- 配置管理 --------------------
class OpinionConfig:
    """舆论状态模块配置（可插拔：支持从文件、环境变量加载）"""
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        default = {
            "data_provider": "memory",            # 数据提供者类型：memory, redis, db
            "sentiment_range": (-1.0, 1.0),       # 情感倾向范围
            "propagation_threshold": 0.5,          # 热点事件传播阈值
            "max_hotspots": 10,                    # 最大热点事件数量
            "update_interval": 1.0,                # 后台更新间隔（秒）
        }
        self.config = default.copy()
        if config_dict:
            self.config.update(config_dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

# -------------------- 数据提供者抽象 --------------------
class OpinionDataProvider(Protocol):
    """
    舆论数据存储协议
    实现类需提供以下方法，支持热插拔替换（内存、Redis、数据库等）
    """
    def load_state(self) -> Dict[str, Any]: ...
    def save_state(self, state: Dict[str, Any]) -> None: ...

# -------------------- 默认内存数据提供者 --------------------
class InMemoryProvider:
    def __init__(self):
        self._state = {}

    def load_state(self) -> Dict[str, Any]:
        return self._state

    def save_state(self, state: Dict[str, Any]) -> None:
        self._state = state

# -------------------- 舆论状态核心类 --------------------
class PublicOpinionState:
    """
    舆论状态管理器
    对外接口：
        - initialize()        : 初始化或重新加载状态
        - update(event)       : 根据事件更新舆论
        - get_sentiment()     : 获取全局舆论倾向
        - get_hotspots()      : 获取当前热点事件列表
        - reset()             : 重置舆论状态
    支持通过配置注入不同的数据提供者，默认使用内存存储
    """
    def __init__(self, config: Optional[OpinionConfig] = None,
                 provider: Optional[OpinionDataProvider] = None):
        self.config = config or OpinionConfig()
        self.provider = provider  # 外部传入的数据提供者（可插拔）
        self._state: Dict[str, Any] = {}
        self._initialized = False
        logger.info("PublicOpinionState 实例创建")

    def _get_provider(self) -> OpinionDataProvider:
        """根据配置或传入的 provider 获取数据提供者实例"""
        if self.provider is not None:
            return self.provider
        # 默认使用内存提供者，也可根据配置动态加载
        return InMemoryProvider()

    def initialize(self) -> bool:
        """初始化舆论状态，从数据提供者加载持久化数据"""
        try:
            provider = self._get_provider()
            self._state = provider.load_state()
            # 如果状态为空，设置默认值
            if not self._state:
                self._state = {
                    "global_sentiment": 0.0,
                    "hotspots": [],
                    "event_log": [],
                    "last_update": None,
                }
                provider.save_state(self._state)
            self._initialized = True
            logger.debug("舆论状态初始化完成")
            return True
        except Exception as e:
            logger.error(f"舆论状态初始化失败: {e}", exc_info=True)
            self._initialized = False
            return False

    def _check_initialized(self):
        if not self._initialized:
            raise RuntimeError("舆论状态未初始化，请先调用 initialize()")

    def update(self, event: Dict[str, Any]) -> None:
        """
        根据外部事件更新舆论状态（骨架，后续实现业务逻辑）
        :param event: 事件描述，例如 {'type':'news', 'impact':0.3, 'region':'capital'}
        """
        self._check_initialized()
        logger.info(f"接收到舆论更新事件: {event}")
        # TODO: 实现实际舆论更新算法
        # 1. 计算事件影响
        # 2. 修改 global_sentiment
        # 3. 更新热点列表
        # 4. 记录事件日志
        # 临时示例：直接保存事件
        self._state.setdefault("event_log", []).append(event)
        self._persist()

    def get_sentiment(self) -> float:
        """获取全局舆论倾向值（-1.0 表示最负面，1.0 表示最正面）"""
        self._check_initialized()
        return self._state.get("global_sentiment", 0.0)

    def get_hotspots(self, top_n: int = None) -> List[Dict[str, Any]]:
        """
        获取当前热点事件列表
        :param top_n: 返回前 N 个（默认全部）
        """
        self._check_initialized()
        hotspots = self._state.get("hotspots", [])
        if top_n is not None:
            return hotspots[:top_n]
        return hotspots

    def reset(self) -> None:
        """重置舆论状态至默认初始值（通常用于新故事或测试）"""
        self._state.clear()
        self.initialize()
        logger.info("舆论状态已重置")

    def _persist(self) -> None:
        """内部持久化：将当前状态保存到数据提供者"""
        try:
            self._get_provider().save_state(self._state)
        except Exception as e:
            logger.error(f"舆论状态持久化失败: {e}", exc_info=True)

    def __repr__(self) -> str:
        return f"<PublicOpinionState initialized={self._initialized}>"

# -------------------- 工厂函数（便于基于配置动态创建实例） --------------------
def create_opinion_state(config_path: Optional[str] = None) -> PublicOpinionState:
    """
    从配置文件（或默认）创建 PublicOpinionState 实例
    当前为骨架，未来支持从 YAML/JSON 加载配置并实例化数据提供者
    """
    # 示例配置，实际可从文件读取
    cfg_dict = {}
    if config_path:
        logger.info(f"从 {config_path} 加载舆论模块配置（暂未实现）")
    return PublicOpinionState(config=OpinionConfig(cfg_dict))

# -------------------- 自测 --------------------
if __name__ == "__main__":
    print("=== 舆论状态模块自测启动 ===")
    # 1. 直接创建实例
    state = PublicOpinionState()
    state.initialize()
    print("初始情感值:", state.get_sentiment())
    print("热点事件:", state.get_hotspots())

    # 2. 模拟更新事件
    test_event = {
        "type": "scandal",
        "impact": -0.2,
        "region": "capital",
        "description": "大臣贪污被曝光"
    }
    state.update(test_event)
    print("更新后事件日志条数:", len(state._state.get("event_log", [])))

    # 3. 重置测试
    state.reset()
    print("重置后情感值:", state.get_sentiment())

    # 4. 测试未初始化异常
    state2 = PublicOpinionState()
    try:
        state2.get_sentiment()
    except RuntimeError as e:
        print("预期异常捕获:", e)

    # 5. 测试自定义数据提供者插拔
    class MockProvider:
        def __init__(self):
            self.data = {"global_sentiment": 0.8, "hotspots": [{"title": "战争谣言"}]}
        def load_state(self):
            return self.data
        def save_state(self, state):
            self.data = state

    state3 = PublicOpinionState(provider=MockProvider())
    state3.initialize()
    print("Mock 提供者初始情感值:", state3.get_sentiment())
    print("Mock 提供者热点:", state3.get_hotspots())

    print("=== 自测完成 ===")