import abc
import logging
import json
from typing import List, Dict, Any, Optional

# ----- 配置与日志基础 -----
DEFAULT_CONFIG = {
    "retrieval_method": "keyword",  # 可选: "keyword", "embedding"
    "top_k": 5,
    "similarity_threshold": 0.7,
    "index_path": "./memory_index",
}

MODULE_LOGGER = logging.getLogger("NovelOS.Memory.Recall")
if not MODULE_LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s] %(message)s'))
    MODULE_LOGGER.addHandler(handler)
    MODULE_LOGGER.setLevel(logging.INFO)


# ----- 核心接口（可插拔） -----
class BaseMemoryRetriever(abc.ABC):
    """记忆召回器抽象基类，所有召回策略必须实现此接口"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.logger = MODULE_LOGGER.getChild(self.__class__.__name__)
        self.logger.info(f"初始化召回器，配置: {self.config}")

    @abc.abstractmethod
    def recall(self, query: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        根据查询召回相关记忆项
        :param query: 查询文本或关键词
        :param context: 可选上下文信息（如当前故事状态、角色等）
        :return: 记忆列表，每一项包含至少 {id, content, score, metadata}
        """
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}(config={self.config})"


# ----- 简单关键词召回实现（示例） -----
class SimpleKeywordRetriever(BaseMemoryRetriever):
    """基于关键词匹配的简单召回器，用于示范和测试"""

    def __init__(self, memory_store=None, config: Dict[str, Any] = None):
        """
        :param memory_store: 可选的记忆存储接口，需支持 search(keyword) 方法
        """
        super().__init__(config)
        self.memory_store = memory_store  # 外部注入，实现解耦
        if self.memory_store is None:
            self.logger.warning("未提供memory_store，召回功能将返回空结果")

    def recall(self, query: str, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        self.logger.info(f"执行关键词召回: query='{query}', top_k={self.config['top_k']}")
        if self.memory_store is None:
            return []
        # 假定memory_store有search方法，返回带分数和内容的字典
        try:
            results = self.memory_store.search(query, top_k=self.config["top_k"])
        except AttributeError:
            self.logger.error("memory_store 缺少 search 方法")
            return []
        # 过滤低于阈值的
        filtered = [
            {**item, "recall_method": "keyword"}
            for item in results
            if item.get("score", 0) >= self.config["similarity_threshold"]
        ]
        self.logger.info(f"召回完成，返回 {len(filtered)} 条记忆")
        return filtered


# ----- 召回器工厂（实现可插拔选择） -----
class RecallFactory:
    """召回器工厂，根据配置创建对应的召回器实例"""
    _registry = {}

    @classmethod
    def register(cls, name: str, retriever_cls):
        cls._registry[name] = retriever_cls

    @classmethod
    def create(cls, config: Dict[str, Any], **kwargs) -> BaseMemoryRetriever:
        method = config.get("retrieval_method", "keyword")
        if method not in cls._registry:
            raise ValueError(f"未知的召回方法: {method}，已注册: {list(cls._registry.keys())}")
        retriever_cls = cls._registry[method]
        return retriever_cls(config=config, **kwargs)


# 注册默认实现
RecallFactory.register("keyword", SimpleKeywordRetriever)


# ----- 自测部分 -----
def self_test():
    """模块自检，仅用于开发阶段验证基础功能"""
    print("========== 记忆召回模块自检 ==========")
    # 模拟一个存储
    class FakeMemoryStore:
        def __init__(self):
            self.memories = [
                {"id": "1", "content": "主角在森林中迷路", "score": 0.9},
                {"id": "2", "content": "主角遇到了一位老人", "score": 0.8},
                {"id": "3", "content": "老人给了主角一张地图", "score": 0.95},
                {"id": "4", "content": "天空开始下雨", "score": 0.3},
            ]

        def search(self, keyword, top_k=5):
            results = []
            kw = keyword.lower()
            for m in self.memories:
                if kw in m["content"].lower():
                    results.append(m)
            return sorted(results, key=lambda x: x["score"], reverse=True)[:top_k]

    store = FakeMemoryStore()
    retriever = RecallFactory.create({"retrieval_method": "keyword", "top_k": 3}, memory_store=store)
    query = "主角 森林"
    rec = retriever.recall(query)
    print(f"查询: {query}")
    print(f"召回结果: {json.dumps(rec, ensure_ascii=False, indent=2)}")

    # 可选：无存储测试
    retriever2 = RecallFactory.create({"retrieval_method": "keyword"})
    rec2 = retriever2.recall("测试")
    print(f"无存储召回: {rec2}")

    print("========== 自检完成 ==========")


if __name__ == "__main__":
    self_test()