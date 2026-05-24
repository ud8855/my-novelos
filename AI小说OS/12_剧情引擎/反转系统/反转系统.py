"""
反转系统核心骨架
职责：提供可插拔的反转策略管理，支持多策略注册、配置化驱动、日志记录与自测
依赖：无外部依赖，仅使用标准库 logging, abc, typing
被调用：由剧情引擎（12_剧情引擎）统一调度，向其它子系统暴露反转执行接口
解决：将反转逻辑从剧情流程中解耦，允许动态加载/卸载策略，便于长期演化
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

# ---------- 日志配置 ----------
def _setup_logger() -> logging.Logger:
    """配置并返回反转系统专用日志器"""
    logger = logging.getLogger("ReversalSystem")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

logger = _setup_logger()

# ---------- 反转策略抽象基类 ----------
class ReversalStrategy(ABC):
    """反转策略接口，所有具体反转必须实现此抽象"""
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.config = config or {}
        logger.debug(f"初始化反转策略: {self.name}")

    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行反转逻辑
        :param context: 剧情上下文，包含当前状态、角色、情节等信息
        :return: 反转后的上下文结果
        """
        pass

    def validate(self) -> bool:
        """可选验证：检查策略是否可用"""
        return True

# ---------- 反转引擎 ----------
class ReversalEngine:
    """反转系统核心引擎，负责策略管理、配置加载、反转执行与异常恢复"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        :param config: 全局配置，可包含默认策略列表、策略参数等
        """
        self.config = config or {}
        self._strategies: Dict[str, ReversalStrategy] = {}
        logger.info("反转引擎初始化完成")

    def register_strategy(self, strategy: ReversalStrategy) -> None:
        """
        注册一个反转策略（可插拔）
        :param strategy: 实现 ReversalStrategy 的具体策略实例
        """
        if not strategy.validate():
            logger.error(f"策略验证失败，注册中止: {strategy.name}")
            return
        if strategy.name in self._strategies:
            logger.warning(f"策略名称重复，将覆盖旧策略: {strategy.name}")
        self._strategies[strategy.name] = strategy
        logger.info(f"策略已注册: {strategy.name}")

    def unregister_strategy(self, name: str) -> None:
        """
        移除一个反转策略
        :param name: 策略名称
        """
        if name in self._strategies:
            del self._strategies[name]
            logger.info(f"策略已移除: {name}")
        else:
            logger.warning(f"尝试移除不存在的策略: {name}")

    def execute_reversal(self, strategy_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        依据策略名称执行反转，并返回结果
        :param strategy_name: 已注册的策略名
        :param context: 剧情上下文
        :return: 反转后的上下文
        :raises KeyError: 策略不存在
        :raises Exception: 策略执行异常
        """
        strategy = self._strategies.get(strategy_name)
        if not strategy:
            logger.error(f"反转策略未找到: {strategy_name}")
            raise KeyError(f"策略未注册: {strategy_name}")

        logger.info(f"开始执行反转策略: {strategy_name}, 上下文概要: {str(context)[:100]}...")
        try:
            result = strategy.execute(context)
            logger.info(f"反转策略执行成功: {strategy_name}")
            return result
        except Exception as e:
            logger.exception(f"反转策略执行异常: {strategy_name}, 错误: {e}")
            # 异常恢复：返回原始上下文或空字典，由上层决策
            raise

    def load_from_config(self, strategy_configs: List[Dict[str, Any]]) -> None:
        """
        从配置列表批量加载反转策略（配置化）
        :param strategy_configs: 形如 [{"class": "模块路径.类名", "name": "...", "config": {...}}]
        """
        for item in strategy_configs:
            class_path = item.get("class")
            name = item.get("name", class_path.split('.')[-1])
            config = item.get("config", {})
            try:
                # 动态导入并实例化策略
                module_name, class_name = class_path.rsplit('.', 1)
                import importlib
                module = importlib.import_module(module_name)
                cls = getattr(module, class_name)
                if not issubclass(cls, ReversalStrategy):
                    logger.error(f"类 {cls} 不是 ReversalStrategy 的子类")
                    continue
                instance = cls(name=name, config=config)
                self.register_strategy(instance)
            except Exception as e:
                logger.error(f"无法从配置加载策略 {item}: {e}")

# ---------- 自测模块 ----------
if __name__ == "__main__":
    # 简单测试：实现一个示例反转策略并执行
    class DemoReversal(ReversalStrategy):
        def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
            # 示例反转：将角色身份互换
            if "hero" in context and "villain" in context:
                context["hero"], context["villain"] = context["villain"], context["hero"]
            return context

    # 初始化引擎
    engine = ReversalEngine()
    # 注册示例策略
    engine.register_strategy(DemoReversal("swap_roles"))
    # 准备上下文
    ctx = {"hero": "正义骑士", "villain": "黑暗领主"}
    print("原始上下文:", ctx)
    try:
        new_ctx = engine.execute_reversal("swap_roles", ctx)
        print("反转后上下文:", new_ctx)
    except Exception as e:
        print("反转失败:", e)
    # 测试移除
    engine.unregister_strategy("swap_roles")
    try:
        engine.execute_reversal("swap_roles", ctx)
    except KeyError as ke:
        print(f"预期错误: {ke}")