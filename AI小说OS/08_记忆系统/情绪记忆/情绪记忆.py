""" 
情绪记忆模块
层级：08_记忆系统
依赖：无外部模块依赖，内部使用文件存储，可替换存储后端
被谁调用：故事生成Agent、情感引擎、角色行为模块等需要记录和检索情绪记忆的组件
解决什么问题：记录和检索与情绪相关的记忆，支持重要性衰减、遗忘机制，为故事生成提供情绪一致性
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional


class EmotionMemory:
    """
    情绪记忆管理器
    提供记忆的增、查、遗忘功能，支持配置化存储路径、日志级别，
    通过配置文件注入实现可插拔性，外部可通过修改 config 切换不同实现。
    所有方法均包含异常恢复与日志记录，确保长期演化中的稳定性。
    """

    def __init__(self, config: Dict[str, Any], storage_path: Optional[str] = None):
        """
        初始化情绪记忆系统
        :param config: 配置字典，必须包含 "logging_level" 可选键，例如 {"logging_level": "DEBUG"}
        :param storage_path: 记忆存储文件路径，若未提供则使用配置中的 "memory_file" 或默认路径
        """
        self.config = config
        self.logger = self._setup_logger()
        self.memory_file = storage_path or config.get("memory_file", "emotion_memory.json")
        self.memories: List[Dict[str, Any]] = []
        self.logger.info("EmotionMemory initialized with storage: %s", self.memory_file)
        self.load_memory()

    def _setup_logger(self) -> logging.Logger:
        """根据配置设置日志器"""
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(self.config.get("logging_level", "INFO"))
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    def load_memory(self) -> bool:
        """
        从文件加载记忆数据
        :return: 加载成功返回 True，否则 False
        """
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    self.memories = json.load(f)
                self.logger.info("Loaded %d memories from %s", len(self.memories), self.memory_file)
                return True
            else:
                self.logger.warning("Memory file not found: %s, starting with empty memory.", self.memory_file)
                self.memories = []
                return True
        except Exception as e:
            self.logger.error("Failed to load memory: %s", e)
            self.memories = []
            return False

    def save_memory(self) -> bool:
        """
        将当前记忆保存到文件
        :return: 保存成功返回 True，否则 False
        """
        try:
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memories, f, ensure_ascii=False, indent=2)
            self.logger.debug("Memories saved to %s", self.memory_file)
            return True
        except Exception as e:
            self.logger.error("Failed to save memories: %s", e)
            return False

    def add_memory(self, memory_entry: Dict[str, Any]) -> bool:
        """
        新增一条情绪记忆
        :param memory_entry: 记忆字典，必须包含 "content", "importance", "emotion" 等字段
        :return: 添加成功返回 True
        """
        try:
            required_keys = {"content", "importance", "emotion", "timestamp"}
            if not required_keys.issubset(memory_entry.keys()):
                missing = required_keys - set(memory_entry.keys())
                raise ValueError(f"Missing required keys: {missing}")
            self.memories.append(memory_entry)
            self.logger.debug("Added memory: %s", memory_entry.get("content", "")[:50])
            return True
        except Exception as e:
            self.logger.error("Failed to add memory: %s", e)
            return False

    def retrieve_memories(self, query: Dict[str, Any], top_k: int = 10) -> List[Dict[str, Any]]:
        """
        根据查询条件检索情绪记忆
        :param query: 检索约束，例如 {"emotion": "sad", "min_importance": 0.5}
        :param top_k: 返回的最大条目数
        :return: 符合条件的记忆列表，按重要性降序
        """
        try:
            filtered = []
            for mem in self.memories:
                match = True
                if "emotion" in query:
                    if mem.get("emotion") != query["emotion"]:
                        match = False
                if "min_importance" in query:
                    if mem.get("importance", 0.0) < query["min_importance"]:
                        match = False
                if match:
                    filtered.append(mem)
            # 按重要性降序排序
            filtered.sort(key=lambda x: x.get("importance", 0.0), reverse=True)
            result = filtered[:top_k]
            self.logger.debug("Retrieved %d memories matching query", len(result))
            return result
        except Exception as e:
            self.logger.error("Error retrieving memories: %s", e)
            return []

    def forget(self, decay_rate: float = 0.1) -> None:
        """
        按照衰减率减少记忆重要性，并移除重要性低于阈值的记忆
        :param decay_rate: 重要性衰减因子 (0~1)
        """
        try:
            threshold = 0.01  # 低于此值则删除
            new_memories = []
            for mem in self.memories:
                mem["importance"] = mem.get("importance", 1.0) * (1 - decay_rate)
                if mem["importance"] > threshold:
                    new_memories.append(mem)
                else:
                    self.logger.debug("Forgetting memory: %s", mem.get("content", "")[:50])
            removed = len(self.memories) - len(new_memories)
            self.memories = new_memories
            self.logger.info("Forget cycle: removed %d memories, %d remaining", removed, len(self.memories))
            self.save_memory()
        except Exception as e:
            self.logger.error("Error during forget cycle: %s", e)

    def reset(self) -> None:
        """清空所有记忆并保存"""
        try:
            self.memories = []
            self.save_memory()
            self.logger.info("Memory reset completed")
        except Exception as e:
            self.logger.error("Failed to reset memory: %s", e)


def self_test() -> None:
    """模块自测函数，验证基本功能"""
    import time
    import tempfile

    # 使用临时文件避免污染正式数据
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
        temp_path = tmp.name

    test_config = {"logging_level": "DEBUG"}
    mem = EmotionMemory(config=test_config, storage_path=temp_path)

    # 添加测试记忆
    assert mem.add_memory({
        "content": "主角感到悲伤",
        "importance": 0.8,
        "emotion": "sad",
        "timestamp": time.time()
    })
    assert mem.add_memory({
        "content": "阳光明媚，心情愉悦",
        "importance": 0.5,
        "emotion": "happy",
        "timestamp": time.time()
    })

    # 检索
    results = mem.retrieve_memories({"emotion": "sad"})
    assert len(results) == 1
    assert results[0]["content"] == "主角感到悲伤"

    # 遗忘
    old_len = len(mem.memories)
    mem.forget(decay_rate=0.5)  # 重要性减半
    # 第二条记忆重要性0.5 -> 0.25，仍大于阈值
    assert len(mem.memories) == old_len, "No memories should be removed yet"
    mem.forget(decay_rate=0.5)  # 0.25 -> 0.125
    assert len(mem.memories) == old_len
    mem.forget(decay_rate=0.9)  # 0.125 -> 0.0125 > 0.01? 0.0125 > 0.01 所以仍然存在？
    # 计算：0.125 * 0.1 = 0.0125 > 0.01，所以还不删除
    mem.forget(decay_rate=0.9)  # 0.0125 -> 0.00125，现在应该被删除
    # 此时第一个记忆也衰减：初始0.8 -> 0.5*0.8=0.4 -> 0.5*0.4=0.2 -> 0.9*0.2=0.02 -> 0.9*0.02=0.002，也被删除
    assert len(mem.memories) == 0, "All memories should be forgotten"

    # 清理
    os.unlink(temp_path)
    print("All self-tests passed.")


if __name__ == "__main__":
    self_test()