# 模型路由模块
# 所属层：04_Runtime运行时
# 依赖：配置管理、日志模块、模型协同接口（通过配置间接依赖）
# 被调用：由上层工作流或任务调度器调用，分配模型处理请求
# 解决问题：根据请求特征动态选择最优模型，实现负载均衡、成本优化、能力匹配

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

# 配置默认路径
DEFAULT_CONFIG_PATH = "config/model_routing.json"

# 日志配置
logger = logging.getLogger("ModelRouter")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


class RouteStrategy(ABC):
    """路由策略抽象基类，所有路由策略必须实现此接口"""

    @abstractmethod
    def select_model(self, request: Dict[str, Any], available_models: List[str]) -> Optional[str]:
        """
        根据请求内容和可用模型列表选择模型
        :param request: 请求上下文，应包含任务类型、复杂度等信息
        :param available_models: 当前可用的模型标识符列表
        :return: 选中的模型标识符，若无可选则返回None
        """
        pass

    @abstractmethod
    def update_weights(self, models: Dict[str, float]):
        """
        更新模型权重（可选实现）
        :param models: 模型及其权重映射
        """
        pass


class RoundRobinStrategy(RouteStrategy):
    """轮询策略，简单均衡负载"""

    def __init__(self):
        self._index = 0

    def select_model(self, request: Dict[str, Any], available_models: List[str]) -> Optional[str]:
        if not available_models:
            return None
        selected = available_models[self._index % len(available_models)]
        self._index += 1
        logger.debug(f"RoundRobin策略选择模型: {selected}")
        return selected

    def update_weights(self, models: Dict[str, float]):
        # 轮询策略不使用权重，空实现
        pass


class PriorityBasedStrategy(RouteStrategy):
    """基于优先级的策略，根据请求优先级分配不同能力的模型"""

    def __init__(self, config: Dict[str, Any]):
        # 配置格式：{"high": ["gpt-4", "claude-2"], "medium": ["gpt-3.5", "gemini-pro"], "low": ["gpt-3.5"]}
        self.priority_map = config.get("priority_map", {})

    def select_model(self, request: Dict[str, Any], available_models: List[str]) -> Optional[str]:
        priority = request.get("priority", "medium")
        candidates = self.priority_map.get(priority, [])
        # 从候选中选择第一个可用的模型
        for model in candidates:
            if model in available_models:
                logger.debug(f"优先级策略选择模型: {model} (priority={priority})")
                return model
        # 如果没有对应优先级的模型可用，则退回任意可用模型
        if available_models:
            fallback = available_models[0]
            logger.warning(f"未找到优先级为{priority}的可用模型，回退至{fallback}")
            return fallback
        return None

    def update_weights(self, models: Dict[str, float]):
        # 可根据权重动态调整优先级映射，此处为骨架省略
        pass


class ModelRouter:
    """
    模型路由器：负责管理路由策略，根据请求上下文动态选择模型
    具有可插拔的策略注册机制和配置热更新能力
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化路由器
        :param config_path: 配置文件路径，若为None则使用默认路径
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.strategies: Dict[str, RouteStrategy] = {}
        self.active_strategy_name = "round_robin"  # 默认策略
        self.config = {}
        self._load_config()
        self._init_strategies()
        logger.info("ModelRouter初始化完成，活跃策略: %s", self.active_strategy_name)

    def _load_config(self):
        """加载路由配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.debug("加载路由配置成功: %s", self.config_path)
            except Exception as e:
                logger.error("加载路由配置失败: %s, 使用默认配置", e)
                self.config = {}
        else:
            logger.warning("路由配置文件不存在: %s, 使用默认配置", self.config_path)
            self.config = {}

    def _init_strategies(self):
        """从配置初始化策略实例并注册"""
        # 默认注册轮询策略
        round_robin = RoundRobinStrategy()
        self.register_strategy("round_robin", round_robin)

        # 根据配置文件动态注册其他策略
        strategy_configs = self.config.get("strategies", {})
        for name, params in strategy_configs.items():
            if name == "round_robin":
                continue  # 避免重复
            strategy_type = params.get("type")
            if strategy_type == "priority_based":
                strategy = PriorityBasedStrategy(params)
            else:
                logger.warning("未知的策略类型: %s, 跳过", strategy_type)
                continue
            self.register_strategy(name, strategy)

        # 设置活跃策略
        self.active_strategy_name = self.config.get("active_strategy", "round_robin")
        logger.info("策略注册完成，策略列表: %s", list(self.strategies.keys()))

    def register_strategy(self, name: str, strategy: RouteStrategy):
        """注册一个新路由策略（热插拔）"""
        if not isinstance(strategy, RouteStrategy):
            raise TypeError("策略必须实现RouteStrategy接口")
        self.strategies[name] = strategy
        logger.info("注册路由策略: %s", name)

    def unregister_strategy(self, name: str):
        """移除一个策略"""
        if name in self.strategies:
            del self.strategies[name]
            logger.info("移除路由策略: %s", name)
        else:
            logger.warning("尝试移除不存在的策略: %s", name)

    def set_active_strategy(self, name: str):
        """切换活跃路由策略"""
        if name not in self.strategies:
            raise ValueError(f"策略 '{name}' 未注册")
        self.active_strategy_name = name
        logger.info("切换活跃策略为: %s", name)

    def reload_config(self):
        """热重载配置并更新策略"""
        self._load_config()
        # 重新初始化策略（保留现有已注册的，或全部重新创建？这里设计为清空后重建以保持与配置一致）
        old_strategies = self.strategies.copy()
        self.strategies.clear()
        self._init_strategies()
        # 若配置中不存在之前的策略，则可能丢失；此处可扩展为保留未出现在配置中的策略
        logger.info("配置热重载完成")

    def route(self, request: Dict[str, Any], available_models: Optional[List[str]] = None) -> Optional[str]:
        """
        主要路由方法：根据请求选择模型
        :param request: 请求描述，至少包含任务类型等字段
        :param available_models: 可用模型列表，若为None则从配置中读取默认模型列表
        :return: 选中的模型标识符
        """
        if available_models is None:
            available_models = self.config.get("default_models", [])
            if not available_models:
                logger.error("没有可用的模型列表，无法路由")
                return None

        strategy = self.strategies.get(self.active_strategy_name)
        if not strategy:
            logger.error("活跃策略 '%s' 不存在", self.active_strategy_name)
            return None

        try:
            selected = strategy.select_model(request, available_models)
            if selected:
                logger.info("路由选择模型: %s (策略: %s)", selected, self.active_strategy_name)
            else:
                logger.warning("策略 %s 未能选出模型", self.active_strategy_name)
            return selected
        except Exception as e:
            logger.exception("模型路由发生异常: %s", e)
            return None


# 自测代码
if __name__ == "__main__":
    # 创建临时配置用于测试
    test_config = {
        "active_strategy": "round_robin",
        "default_models": ["gpt-3.5", "gpt-4", "claude-3-opus", "gemini-1.5-pro"],
        "strategies": {
            "round_robin": {"type": "round_robin"},
            "priority_based": {
                "type": "priority_based",
                "priority_map": {
                    "high": ["gpt-4", "claude-3-opus"],
                    "medium": ["gpt-3.5", "gemini-1.5-pro"],
                    "low": ["gpt-3.5"]
                }
            }
        }
    }

    # 写入临时配置文件
    temp_config_path = "temp_routing_config.json"
    with open(temp_config_path, 'w', encoding='utf-8') as f:
        json.dump(test_config, f, ensure_ascii=False, indent=2)

    # 初始化路由器
    router = ModelRouter(temp_config_path)

    # 测试轮询策略
    print("=== 测试轮询策略 ===")
    for i in range(5):
        selected = router.route({"task": "generate", "priority": "medium"})
        print(f"请求 {i+1}: 选中模型 -> {selected}")

    # 切换为优先级策略
    router.set_active_strategy("priority_based")
    print("\n=== 测试优先级策略 ===")
    priorities = ["high", "medium", "low", "high"]
    for p in priorities:
        selected = router.route({"task": "generate", "priority": p})
        print(f"优先级 {p}: 选中模型 -> {selected}")

    # 测试热插拔：动态注册一个新策略（简单随机，略）
    # 清理临时文件
    os.remove(temp_config_path)

    print("\n自测完成。")