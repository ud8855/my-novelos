#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上下文召回模块
实现从上下文存储中根据查询召回相关信息的机制。
支持可插拔的召回策略，日志记录，配置化管理。
"""

import logging
import re
from typing import Any, Callable, Dict, List, Optional

# 配置日志
logger = logging.getLogger(__name__)

class ContextRecall:
    """
    上下文召回器基类/主类。
    提供可插拔的召回方法，默认基于关键词匹配。
    可通过注册自定义策略扩展召回能力。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化上下文召回器。

        :param config: 配置字典，可包含召回策略、阈值、最大结果数等。
        """
        self.config = config if config else self._default_config()
        self.strategy = self.config.get("strategy", "keyword")  # 默认关键词策略
        self.threshold = self.config.get("threshold", 0.5)      # 相关性阈值
        self.max_results = self.config.get("max_results", 5)    # 最大召回数量
        # 用于存储自定义策略的函数映射
        self._custom_strategies: Dict[str, Callable] = {}
        logger.info(f"ContextRecall initialized with strategy={self.strategy}, "
                    f"threshold={self.threshold}, max_results={self.max_results}")

    def _default_config(self) -> Dict[str, Any]:
        """返回默认配置。"""
        return {
            "strategy": "keyword",
            "threshold": 0.5,
            "max_results": 5
        }

    def recall(self, query: str, context_store: Any) -> List[Dict[str, Any]]:
        """
        从上下文存储中召回与查询相关的上下文。

        :param query: 查询文本
        :param context_store: 上下文存储对象，需支持 get_all_contexts() 方法，
                              返回包含上下文的列表，每个上下文为字典，至少包含 'content' 键。
        :return: 召回结果列表，每个结果为字典，包含原始内容及 'score' 等附加信息，按分数降序排列。
        """
        logger.info(f"Recalling contexts for query: {query[:50]}...")

        if not context_store:
            logger.warning("Context store is empty or None.")
            return []

        # 根据策略选择召回方法（内置策略或自定义策略）
        if self.strategy == "keyword":
            results = self._keyword_recall(query, context_store)
        elif self.strategy == "semantic":
            # 预留语义召回接口，待实现
            results = self._semantic_recall(query, context_store)
        elif self.strategy in self._custom_strategies:
            results = self._custom_strategies[self.strategy](query, context_store)
        else:
            raise ValueError(f"Unsupported recall strategy: {self.strategy}")

        # 按分数降序排序并截断
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        results = results[:self.max_results]
        logger.info(f"Recall returned {len(results)} results for query.")
        return results

    def _keyword_recall(self, query: str, context_store: Any) -> List[Dict[str, Any]]:
        """
        基于关键词匹配的召回策略。
        提取查询中的关键词，计算每个上下文内容中包含的关键词比例作为相似度分数。

        :param query: 查询文本
        :param context_store: 上下文存储对象
        :return: 带分数的上下文列表
        """
        # 提取查询关键词
        query_tokens = set(re.findall(r'\w+', query.lower()))
        if not query_tokens:
            return []

        # 获取所有上下文
        all_contexts = getattr(context_store, 'get_all_contexts', lambda: [])()
        if not all_contexts:
            logger.warning("No contexts available in the store.")
            return []

        scored = []
        for ctx in all_contexts:
            content = ctx.get("content", "")
            content_tokens = set(re.findall(r'\w+', content.lower()))
            if not content_tokens:
                continue

            # 计算命中关键词的比例作为分数
            match_count = len(query_tokens.intersection(content_tokens))
            if match_count > 0:
                score = match_count / len(query_tokens)
                if score >= self.threshold:
                    scored.append({**ctx, "score": score})

        return scored

    def _semantic_recall(self, query: str, context_store: Any) -> List[Dict[str, Any]]:
        """
        语义召回策略（待实现）。
        可在此处接入嵌入模型、向量检索等。

        :param query: 查询文本
        :param context_store: 上下文存储对象
        :return: 空列表（骨架状态）
        """
        logger.warning("Semantic recall not implemented yet. Returning empty results.")
        # 未来可通过此方法调用模型计算语义相似度
        return []

    def register_strategy(self, name: str, strategy_func: Callable[[str, Any], List[Dict[str, Any]]]):
        """
        注册自定义召回策略，实现可插拔扩展。

        :param name: 策略名称（在 config 中设置 strategy 为同名即可使用）
        :param strategy_func: 策略函数，接收 (query, context_store) 并返回带分数的上下文列表
        """
        if not callable(strategy_func):
            raise TypeError("strategy_func must be callable.")
        self._custom_strategies[name] = strategy_func
        logger.info(f"Registered custom recall strategy: {name}")
        print(f"Strategy '{name}' registered successfully.")  # 简单反馈