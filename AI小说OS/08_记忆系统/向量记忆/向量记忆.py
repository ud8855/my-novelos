"""
向量记忆模块 (Vector Memory)
所属层级: 08_记忆系统
依赖: 配置系统、日志系统
被调用: 记忆管理器、Agent记忆检索
功能: 提供基于向量的记忆存储与相似性检索，支持多种后端实现
"""

import os
import json
import logging
import hashlib
import math
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Union

# 配置系统（占位，实际可能从config.json加载）
try:
    from core.config import load_config
except ImportError:
    load_config = None

# 日志
logger = logging.getLogger(__name__)


# ---------- 默认配置 ----------
DEFAULT_CONFIG = {
    "backend": "in_memory",      # 向量存储后端: in_memory / faiss / milvus / chroma 等
    "embedding_dim": 512,        # 向量维度
    "similarity_metric": "cosine",  # 相似度计算方式: cosine / euclidean / dot
    "top_k": 5,                  # 默认返回最相似的top_k条记忆
    "threshold": 0.7,            # 相似度阈值，低于此值的结果将被过滤
    "index_path": None,          # 若使用持久化索引，存储路径
    "embedding_model": "text-embedding-ada-002",  # 嵌入模型标识（供下游使用）
}


# ---------- 抽象接口 ----------
class VectorMemoryInterface(ABC):
    """向量记忆系统的抽象接口，所有具体实现必须继承此类。"""

    @abstractmethod
    def store(self, content: str, metadata: Optional[Dict] = None, 
              vector: Optional[List[float]] = None) -> str:
        """
        存储一条记忆。
        :param content: 原始文本内容
        :param metadata: 元数据字典 (时间戳、标签等)
        :param vector: 外部计算好的向量，若为None则由内部调用嵌入模型生成
        :return: 记忆的唯一ID
        """
        pass

    @abstractmethod
    def query(self, query_text: Optional[str] = None,
              query_vector: Optional[List[float]] = None,
              top_k: Optional[int] = None,
              threshold: Optional[float] = None) -> List[Dict]:
        """
        查询最相似的记忆。
        :param query_text: 查询文本 (优先使用vector，若无则文本转向量)
        :param query_vector: 查询向量
        :param top_k: 返回数量
        :param threshold: 相似度阈值
        :return: 匹配的记忆列表，每项包含 {id, content, metadata, score}
        """
        pass

    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """删除指定ID的记忆"""
        pass

    @abstractmethod
    def update(self, memory_id: str, 
               content: Optional[str] = None,
               metadata: Optional[Dict] = None,
               vector: Optional[List[float]] = None) -> bool:
        """更新记忆内容、元数据或向量"""
        pass

    @abstractmethod
    def count(self) -> int:
        """返回记忆总数"""
        pass

    def embed(self, text: str) -> List[float]:
        """
        将文本转换为向量。基础实现可调用外部嵌入服务，
        这里提供一个占位实现，实际使用时必须覆盖。
        """
        raise NotImplementedError("嵌入方法未实现，请使用具体子类或配置嵌入模型")


# ---------- 简单内存实现（用于开发调试和自测） ----------
class InMemoryVectorMemory(VectorMemoryInterface):
    """纯内存的向量记忆实现，支持余弦相似度检索，无持久化。"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        self.dim = self.config.get("embedding_dim", 512)
        self.similarity_metric = self.config.get("similarity_metric", "cosine")
        self.top_k_default = self.config.get("top_k", 5)
        self.threshold_default = self.config.get("threshold", 0.7)
        
        # 存储数据结构: dict: id -> {"content": str, "metadata": dict, "vector": List[float]}
        self._store: Dict[str, Dict] = {}
        
        logger.info(f"InMemoryVectorMemory 初始化，维度={self.dim}, 距离度量={self.similarity_metric}")

    def _generate_id(self, content: str) -> str:
        """简单的ID生成，基于内容的哈希"""
        return hashlib.md5(content.encode()).hexdigest()

    def _cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """计算余弦相似度"""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _euclidean_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """欧氏距离转换为相似度 (1/(1+distance))"""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(vec_a, vec_b)))
        return 1.0 / (1.0 + distance)

    def _compute_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        """根据配置的相似度度量计算相似度"""
        if self.similarity_metric == "cosine":
            return self._cosine_similarity(vec_a, vec_b)
        elif self.similarity_metric == "euclidean":
            return self._euclidean_similarity(vec_a, vec_b)
        elif self.similarity_metric == "dot":
            return sum(a * b for a, b in zip(vec_a, vec_b))
        else:
            raise ValueError(f"不支持的相似度度量: {self.similarity_metric}")

    def embed(self, text: str) -> List[float]:
        """内存实现中如果没有外部嵌入模型，则使用伪随机向量（仅用于测试）"""
        import random
        random.seed(hash(text) % 10**8)  # 固定种子使得相同文本生成相同向量
        return [random.random() for _ in range(self.dim)]

    def store(self, content: str, metadata: Optional[Dict] = None,
              vector: Optional[List[float]] = None) -> str:
        if not content and vector is None:
            raise ValueError("必须提供content或vector")
        memory_id = self._generate_id(content) if content else self._generate_id(str(vector))
        
        # 如果没有提供向量，则通过嵌入生成（调用embed）
        if vector is None:
            if not content:
                raise ValueError("当未提供向量时，必须提供content用于生成向量")
            vector = self.embed(content)
        
        if len(vector) != self.dim:
            logger.warning(f"向量维度 {len(vector)} 与配置维度 {self.dim} 不一致，将使用配置维度截断或填充")
            if len(vector) > self.dim:
                vector = vector[:self.dim]
            else:
                vector += [0.0] * (self.dim - len(vector))
        
        self._store[memory_id] = {
            "content": content,
            "metadata": metadata if metadata else {},
            "vector": vector,
        }
        logger.debug(f"存储记忆 {memory_id[:8]}... 向量维度={len(vector)}")
        return memory_id

    def query(self, query_text: Optional[str] = None,
              query_vector: Optional[List[float]] = None,
              top_k: Optional[int] = None,
              threshold: Optional[float] = None) -> List[Dict]:
        if query_vector is None:
            if query_text:
                query_vector = self.embed(query_text)
            else:
                raise ValueError("必须提供query_text或query_vector")
        
        top_k = top_k if top_k is not None else self.top_k_default
        threshold = threshold if threshold is not None else self.threshold_default
        
        scores = []
        for mem_id, mem_data in self._store.items():
            sim = self._compute_similarity(query_vector, mem_data["vector"])
            if sim >= threshold:
                scores.append((mem_id, sim, mem_data))
        
        # 按相似度降序排列
        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for mem_id, sim, mem_data in scores[:top_k]:
            results.append({
                "id": mem_id,
                "content": mem_data["content"],
                "metadata": mem_data["metadata"],
                "score": sim,
            })
        logger.info(f"查询返回 {len(results)} 条相似记忆 (threshold={threshold}, top_k={top_k})")
        return results

    def delete(self, memory_id: str) -> bool:
        if memory_id in self._store:
            del self._store[memory_id]
            logger.debug(f"删除记忆 {memory_id[:8]}...")
            return True
        return False

    def update(self, memory_id: str, content: Optional[str] = None,
               metadata: Optional[Dict] = None,
               vector: Optional[List[float]] = None) -> bool:
        if memory_id not in self._store:
            return False
        mem = self._store[memory_id]
        if content is not None:
            mem["content"] = content
            # 如果提供了内容且未提供向量，则重新生成向量
            if vector is None:
                vector = self.embed(content)
        if metadata is not None:
            mem["metadata"] = metadata
        if vector is not None:
            mem["vector"] = vector
        logger.debug(f"更新记忆 {memory_id[:8]}...")
        return True

    def count(self) -> int:
        return len(self._store)


# ---------- 工厂函数 ----------
def create