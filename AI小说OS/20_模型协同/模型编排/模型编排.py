# -*- coding: utf-8 -*-
"""
模型编排模块
层级：20_模型协同
职责：管理多个模型的协同编排，支持可插拔的策略，提供统一的编排接口
依赖：21_API模型/（通过抽象接口依赖，不直接依赖具体实现）
被调用者：任务调度器、Agent等需要多模型协同的模块
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Callable, Optional

# 日志配置
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# --- 抽象基类与接口定义 ---

class IModelInvoker(ABC):
    """
    模型调用抽象接口，用于隔离具体模型 API 调用。
    实际调用由 21_API模型 层实现。
    """
    @abstractmethod
    def invoke(self, model_name: str, input_data: Any, **kwargs) -> Any:
        """
        调用指定的模型并返回结果
        """
        pass

class OrchestrationStrategy(ABC):
    """
    编排策略抽象基类。每种具体的编排算法实现该接口。
    """
    @abstractmethod
    def execute(self, task: Dict[str, Any], model_invoker: IModelInvoker, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        执行编排逻辑
        :param task: 任务描述，包含所需模型、输入等
        :param model_invoker: 模型调用器
        :param context: 上下文信息
        :return: 编排结果
        """
        pass

# --- 编排管理器 ---

class OrchestrationManager:
    """
    编排管理器，负责注册、选择和执行编排策略。
    可插拔：通过 register 方法添加新的策略。
    """
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self._strategies: Dict[str, OrchestrationStrategy] = {}
        logger.info("编排管理器初始化完成")
    
    def register_strategy(self, name: str, strategy: OrchestrationStrategy):
        """
        注册一个编排策略
        """
        if name in self._strategies:
            logger.warning(f"策略 '{name}' 已存在，将被覆盖")
        self._strategies[name] = strategy
        logger.info(f"策略 '{name}' 注册成功")
    
    def unregister_strategy(self, name: str):
        """
        注销一个编排策略
        """
        if name in self._strategies:
            del self._strategies[name]
            logger.info(f"策略 '{name}' 已注销")
        else:
            logger.warning(f"策略 '{name}' 不存在，无法注销")
    
    def execute(self, strategy_name: str, task: Dict[str, Any], model_invoker: IModelInvoker, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        使用指定策略执行编排
        """
        strategy = self._strategies.get(strategy_name)
        if not strategy:
            logger.error(f"未找到策略: {strategy_name}")
            raise ValueError(f"Unknown strategy: {strategy_name}")
        logger.info(f"开始执行编排策略: {strategy_name}")
        try:
            result = strategy.execute(task, model_invoker, context)
            logger.info(f"编排策略 '{strategy_name}' 执行成功")
            return result
        except Exception as e:
            logger.error(f"策略 '{strategy_name}' 执行失败: {str(e)}")
            raise

# --- 默认的基础编排策略实现 ---

class SequentialStrategy(OrchestrationStrategy):
    """
    顺序编排策略：按照任务中定义的模型列表顺序依次调用，将前一个模型的输出作为下一个的输入（或按配置）。
    """
    def execute(self