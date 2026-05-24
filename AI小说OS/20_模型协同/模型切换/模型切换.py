"""
模块：20_模型协同/模型切换.py
职责：根据上下文动态决定使用哪个模型，实现模型路由与切换逻辑。
层级：第20层 模型协同
依赖：配置管理模块(utils/config)，日志模块(utils/logger)，模型适配器协议(20_模型协同/模型适配器协议.py)
被调用：21_API模型/ 中的模型调用接口，或在20层内被任务调度调用
功能：
    - 注册多个模型适配器，定义切换策略
    - 根据任务上下文（如成本、延迟、能力需求）选择最优模型
    - 支持热插拔：运行时动态增加/移除模型
    - 异常恢复：切换失败时回退到默认模型
    - 完全配置化：策略参数从配置文件读取
    - 日志记录所有切换决策
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from contextlib import contextmanager

# 假设存在配置工具与日志工具，实际应从项目导入
try:
    from utils.config import get_config
    from utils.logger import setup_logger
except ImportError:
    # 自测时的简易替代
    def get_config(section: str, key: str, default=None):
        return default

    def setup_logger(name: str, level=logging.INFO):
        logger = logging.getLogger(name)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
        logger.setLevel(level)
        return logger


# 定义模型适配器协议（简化版，实际由协议模块提供）
class ModelAdapterProtocol:
    """模型适配器需实现的接口"""
    def name(self) -> str:
        """返回模型唯一标识"""
        raise NotImplementedError

    def capabilities(self) -> List[str]:
        """返回模型能力标签，如 ['text', 'reasoning', 'fast']"""
        raise NotImplementedError

    def cost_per_token(self) -> float:
        """每token成本"""
        raise NotImplementedError

    def invoke(self, prompt: str, **kwargs) -> str:
        """调用模型"""
        raise NotImplementedError


@dataclass
class ModelEntry:
    """模型注册信息"""
    adapter: ModelAdapterProtocol
    weight: float = 1.0  # 优先级权重，暂未使用

    def __hash__(self):
        return hash(self.adapter.name())


class ModelSwitchError(Exception):
    """模型切换异常"""
    pass


class ModelSwitcher:
    """
    模型切换器：管理多个模型，根据上下文选择最佳模型。
    设计为可插拔，通过注册/注销适配器扩展。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # 加载配置
        self.config = config or {}
        self.default_model_name = self.config.get("default_model", "default")
        self.strategy = self.config.get("strategy", "least_cost")  # 可选: least_cost, highest_capability, weighted_random
        self.fallback_enabled = self.config.get("fallback_enabled", True)

        # 模型注册表
        self._models: Dict[str, ModelAdapterProtocol] = {}
        self._default_adapter: Optional[ModelAdapterProtocol] = None

        # 初始化日志
        self.logger = setup_logger("ModelSwitcher", level=logging.INFO)
        self.logger.info("模型切换器初始化完成，策略=%s，默认模型=%s", self.strategy, self.default_model_name)

    # ==================== 注册管理（热插拔支持） ====================
    def register_model(self, adapter: ModelAdapterProtocol) -> None:
        """注册一个模型适配器。若名称已存在则更新，实现热更新。"""
        name = adapter.name()
        self._models[name] = adapter
        self.logger.info("模型已注册/更新: %s", name)
        # 如果注册的恰好是默认模型，更新引用
        if name == self.default_model_name:
            self._default_adapter = adapter

    def unregister_model(self, model_name: str) -> None:
        """注销模型，若为默认模型则警告。"""
        if model_name in self._models:
            del self._models[model_name]
            self.logger.info("模型已注销: %s", model_name)
            if model_name == self.default_model_name:
                self.logger.warning("默认模型 %s 被注销，将尝试使用其它模型", model_name)
                self._default_adapter = None
        else:
            self.logger.warning("尝试注销不存在的模型: %s", model_name)

    def get_registered_models(self) -> List[str]:
        """返回当前注册的所有模型名称"""
        return list(self._models.keys())

    # ==================== 核心切换逻辑 ====================
    def select_model(self, context: Dict[str, Any]) -> str:
        """
        根据上下文选择最适合的模型，返回模型名称。
        context可能包含: required_capabilities, max_cost, preferred_model等
        """
        self.logger.debug("选择模型，上下文: %s", context)
        if not self._models:
            raise ModelSwitchError("没有注册任何模型")

        required = context.get("required_capabilities", [])
        max_cost = context.get("max_cost", float("inf"))
        preferred = context.get("preferred_model")

        # 如果明确要求某个模型且已注册，直接返回
        if preferred and preferred in self._models:
            # 仍检查能力要求？简单期间这里直接信任调用方
            self.logger.info("根据偏好选择模型: %s", preferred)
            return preferred

        # 筛选满足能力要求的模型
        candidates = []
        for name, adapter in self._models.items():
            caps = adapter.capabilities()
            if all(req in caps for req in required):
                if adapter.cost_per_token() <= max_cost:
                    candidates.append(adapter)

        if not candidates:
            # 如果没有完全满足的，尝试放宽代价约束，或者回退到默认
            if self.fallback_enabled:
                fallback = self._fallback_model()
                if fallback:
                    self.logger.warning("无满足要求的模型，回退到: %s", fallback.name())
                    return fallback.name()
            raise ModelSwitchError("没有模型满足要求，且回退禁用或无可用模型")

        # 根据策略排序选择
        if self.strategy == "least_cost":
            candidates.sort(key=lambda a: a.cost_per_token())
            chosen = candidates[0]
        elif self.strategy == "highest_capability":
            # 按能力数量降序，简单实现
            candidates.sort(key=lambda a: len(a.capabilities()), reverse=True)
            chosen = candidates[0]
        else:  # 默认取第一个
            chosen = candidates[0]

        self.logger.info("策略[%s]选择模型: %s", self.strategy, chosen.name())
        return chosen.name()

    def maybe_switch(self, current_model_name: str, context: Dict[str, Any]) -> Optional[str]:
        """
        判断是否需要切换模型，如果需要则返回新模型名称，否则返回None。
        可用于原有模型已经在使用，决定是否切换以优化。
        """
        try:
            target = self.select_model(context)
        except ModelSwitchError as e:
            self.logger.error("选择模型失败: %s", e)
            return None

        if target != current_model_name:
            self.logger.info("建议从 %s 切换到 %s", current_model_name, target)
            return target
        return None

    def _fallback_model(self) -> Optional[ModelAdapterProtocol]:
        """获取回退模型：默认模型或任意一个注册模型"""
        if self._default_adapter:
            return self._default_adapter
        if self._models:
            # 取第一个
            return next(iter(self._models.values()))
        return None

    # ==================== 上下文管理辅助 ====================
    @contextmanager
    def model_context(self, context: Dict[str, Any]):
        """
        上下文管理器，用于临时切换模型，结束自动恢复。
        （此处为示例，具体实现需结合21层调用，暂留接口）
        """
        # 记录原始状态
        # 实际调用时需要全局模型状态，此处仅展示设计
        self.logger.debug("进入模型上下文，配置: %s", context)
        try:
            yield
        finally:
            self.logger.debug("退出模型上下文")


# ==================== 自测代码 ====================
if __name__ == "__main__":
    print("=== 模型切换器自测 ===")

    # 简易的模拟适配器
    class MockAdapter(ModelAdapterProtocol):
        def __init__(self, name, caps, cost):
            self._name = name
            self._caps = caps
            self._cost = cost

        def name(self):
            return self._name

        def capabilities(self):
            return self._caps

        def cost_per_token(self):
            return self._cost

        def invoke(self, prompt, **kwargs):
            return f"mock response from {self._name}"

    # 创建切换器
    config = {
        "default_model": "cheap_gpt",
        "strategy": "least_cost",
        "fallback_enabled": True
    }
    switcher = ModelSwitcher(config)

    # 注册模型
    cheap_adapter = MockAdapter("cheap_gpt", ["text"], 0.001)
    advanced_adapter = MockAdapter("advanced_gpt", ["text", "reasoning"], 0.01)
    vision_adapter = MockAdapter("vision_gpt", ["text", "vision"], 0.015)
    switcher.register_model(cheap_adapter)
    switcher.register_model(advanced_adapter)
    switcher.register_model(vision_adapter)

    print("注册模型:", switcher.get_registered_models())

    # 场景1：只需文本能力，最大成本不限 -> 应选 cheapest (cheap_gpt)
    ctx = {"required_capabilities": ["text"]}
    chosen = switcher.select_model(ctx)
    print(f"场景1 选择: {chosen}")  # 期望 cheap_gpt

    # 场景2：需要 reasoning，成本不限 -> advanced_gpt
    ctx2 = {"required_capabilities": ["reasoning"]}
    chosen2 = switcher.select_model(ctx2)
    print(f"场景2 选择: {chosen2}")  # 期望 advanced_gpt

    # 场景3：需要 vision，成本不限 -> vision_gpt
    ctx3 = {"required_capabilities": ["vision"]}
    chosen3 = switcher.select_model(ctx3)
    print(f"场景3 选择: {chosen3}")

    # 场景4：需要 reasoning，但最大成本0.0001（低于advanced） -> 无法满足，回退到默认 cheap_gpt
    ctx4 = {"required_capabilities": ["reasoning"], "max_cost": 0.0001}
    chosen4 = switcher.select_model(ctx4)
    print(f"场景4 选择（回退）: {chosen4}")

    # 测试 maybe_switch
    current = "cheap_gpt"
    target = switcher.maybe_switch(current, {"required_capabilities": ["reasoning"]})
    print(f"maybe_switch from {current}: {target} (期望 advanced_gpt)")

    # 热插拔测试：注销 cheap_gpt 再选
    switcher.unregister_model("cheap_gpt")
    print("注销 cheap_gpt 后注册模型:", switcher.get_registered_models())
    try:
        switcher