"""
模块：上下文排序 (Context Sorting)
层级：09_上下文系统
依赖：上下文数据结构（可能由上下文管理模块提供）
被调用：上下文管道处理、模型调用前的上下文组装
功能：对传入的上下文项（如对话消息）进行排序，支持多种排序策略（可插拔），配置化，带日志和异常恢复。
设计原则：单一职责（只负责排序），可插拔（通过策略模式选择排序方法），配置驱动，日志记录，可自测。
"""

import logging
import traceback
from typing import List, Any, Callable, Dict, Optional

# -------------------- 日志配置 --------------------
logger = logging.getLogger(__name__)


# -------------------- 自定义异常 --------------------
class ContextSortingError(Exception):
    """上下文排序异常基类"""
    pass


# -------------------- 排序策略接口 --------------------
class SortingStrategy:
    """
    排序策略基类（接口）
    所有具体排序策略必须实现 sort 方法
    """

    def sort(self, context_items: List[Any]) -> List[Any]:
        """
        对上下文项列表进行排序
        :param context_items: 待排序的上下文项列表
        :return: 排序后的列表
        """
        raise NotImplementedError("子类必须实现 sort 方法")


# -------------------- 具体排序策略 --------------------
class ChronologicalSortStrategy(SortingStrategy):
    """按时间顺序排序（示例）"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        logger.info("初始化 ChronologicalSortStrategy")

    def sort(self, context_items: List[Any]) -> List[Any]:
        logger.info("执行按时间顺序排序，项目数量: %d", len(context_items))
        try:
            # 假设每个 item 都有 timestamp 属性，这里仅作示例
            return sorted(context_items, key=lambda x: getattr(x, 'timestamp', 0))
        except Exception as e:
            logger.error("时间排序失败: %s", traceback.format_exc())
            raise ContextSortingError(f"ChronologicalSortStrategy 排序失败: {e}")


class ImportanceSortStrategy(SortingStrategy):
    """按重要性排序（示例）"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        logger.info("初始化 ImportanceSortStrategy")

    def sort(self, context_items: List[Any]) -> List[Any]:
        logger.info("执行按重要性排序，项目数量: %d", len(context_items))
        try:
            # 假设每个 item 都有 importance 属性
            return sorted(context_items, key=lambda x: getattr(x, 'importance', 0), reverse=True)
        except Exception as e:
            logger.error("重要性排序失败: %s", traceback.format_exc())
            raise ContextSortingError(f"ImportanceSortStrategy 排序失败: {e}")


class CustomSortStrategy(SortingStrategy):
    """自定义排序策略，支持传入排序键函数"""

    def __init__(self, key_func: Callable[[Any], Any], config: Optional[Dict] = None):
        self.key_func = key_func
        self.config = config or {}
        logger.info("初始化 CustomSortStrategy，使用自定义键函数")

    def sort(self, context_items: List[Any]) -> List[Any]:
        logger.info("执行自定义排序，项目数量: %d", len(context_items))
        try:
            return sorted(context_items, key=self.key_func)
        except Exception as e:
            logger.error("自定义排序失败: %s", traceback.format_exc())
            raise ContextSortingError(f"CustomSortStrategy 排序失败: {e}")


# -------------------- 上下文排序器 --------------------
class ContextSorter:
    """
    上下文排序器
    负责根据配置加载排序策略，并对上下文项进行排序。
    支持运行时切换排序策略。
    """

    def __init__(self, config: Dict):
        """
        :param config: 配置字典，需包含 'strategy' 字段指定默认策略名称
        """
        self.config = config
        logger.info("初始化 ContextSorter，默认策略: %s", config.get('strategy', 'chronological'))
        self._strategies: Dict[str, SortingStrategy] = {}
        self._register_default_strategies()

    def _register_default_strategies(self):
        """注册内置排序策略"""
        self._strategies['chronological'] = ChronologicalSortStrategy(self.config.get('chronological', {}))
        self._strategies['importance'] = ImportanceSortStrategy(self.config.get('importance', {}))
        # 其他策略可在此扩展
        logger.debug("已注册策略: %s", list(self._strategies.keys()))

    def register_strategy(self, name: str, strategy: SortingStrategy):
        """
        注册一个新的排序策略（可插拔）
        :param name: 策略名称
        :param strategy: 策略实例
        """
        logger.info("注册排序策略: %s", name)
        self._strategies[name] = strategy

    def get_strategy(self, strategy_name: Optional[str] = None) -> SortingStrategy:
        """
        获取排序策略实例
        :param strategy_name: 策略名称，不提供则使用配置中的默认策略
        :return: 排序策略实例
        """
        name = strategy_name or self.config.get('strategy', 'chronological')
        strategy = self._strategies.get(name)
        if not strategy:
            logger.error("未找到排序策略: %s", name)
            raise ContextSortingError(f"策略 '{name}' 未注册")
        return strategy

    def sort(self, context_items: List[Any], strategy_name: Optional[str] = None) -> List[Any]:
        """
        对上下文项进行排序
        :param context_items: 待排序的上下文项列表
        :param strategy_name: 可选，指定此次排序策略（覆盖默认）
        :return: 排序后的列表
        """
        logger.info("开始上下文排序，项目数量: %d，策略: %s", len(context_items), strategy_name or 'default')
        try:
            strategy = self.get_strategy(strategy_name)
            sorted_items = strategy.sort(context_items)
            logger.info("排序完成，输出数量: %d", len(sorted_items))
            return sorted_items
        except Exception as e:
            logger.error("排序过程异常: %s", traceback.format_exc())
            # 根据配置决定是否降级：返回原始顺序
            if self.config.get('fallback_to_original', True):
                logger.warning("排序异常，降级返回原始顺序")
                return context_items
            else:
                raise ContextSortingError(f"排序失败，且不允许降级: {e}")


# -------------------- 自测 --------------------
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 模拟上下文项（仅仅示例对象）
    class DummyContextItem:
        def __init__(self, id, timestamp, importance):
            self.id = id
            self.timestamp = timestamp
            self.importance = importance

        def __repr__(self):
            return f"Item(id={self.id}, ts={self.timestamp}, imp={self.importance})"

    items = [
        DummyContextItem(1, 100, 3),
        DummyContextItem(2, 50, 5),
        DummyContextItem(3, 200, 1),
    ]

    # 配置：默认使用时间顺序，并注册重要性策略
    config = {
        'strategy': 'chronological',
        'fallback_to_original': True
    }
    sorter = ContextSorter(config)

    print("原始顺序:", items)
    print("按时间排序:", sorter.sort(items))
    print("按重要性排序:", sorter.sort(items, strategy_name='importance'))

    # 注册一个自定义排序策略（按 id 逆序）
    custom_strategy = CustomSortStrategy(key_func=lambda x: -x.id)
    sorter.register_strategy('reverse_id', custom_strategy)
    print("自定义逆序ID排序:", sorter.sort(items, strategy_name='reverse_id'))

    # 测试未注册策略的情况（应降级返回原始顺序）
    print("未注册策略测试:", sorter.sort(items, strategy_name='no_exist'))