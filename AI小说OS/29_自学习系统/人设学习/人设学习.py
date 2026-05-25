"""
人设学习模块 (Character Learning Module)
层级：29_自学习系统
依赖：20_模型协同/ 或 21_API模型/ (未来使用)
被调用者：上层Agent（如写作Agent）在生成内容后，调用本模块学习角色人设，以维护角色一致性。
解决：从章节文本中提取、更新、强化角色人设信息，实现角色记忆和学习。
设计原则：可插拔（策略模式），配置化，日志化，支持热插拔。
"""
import logging
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

# ---------- 配置 ----------
@dataclass
class CharacterLearningConfig:
    """人设学习配置，支持从文件加载"""
    # 学习算法类型：'basic', 'advanced', 'custom'
    learner_type: str = "basic"
    
    # 是否启用日志记录
    enable_logging: bool = True
    
    # 角色人设存储路径（可以是数据库连接字符串或文件路径）
    storage_path: str = "data/characters/"
    
    # 最小学习文本长度（太短忽略）
    min_text_length: int = 50
    
    # 更新阈值：相似度低于此值时触发更新
    similarity_threshold: float = 0.8
    
    # 自定义参数扩展
    extra: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "CharacterLearningConfig":
        """从字典创建配置"""
        return cls(**{k: v for k, v in config_dict.items() if k in cls.__dataclass_fields__})

# ---------- 日志 ----------
logger = logging.getLogger("CharacterLearning")
if not logger.handlers:
    # 避免重复添加handler，简单设置一个stream handler
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

# ---------- 抽象基类（可插拔接口） ----------
class BaseCharacterLearner(ABC):
    """人设学习器抽象基类，定义学习接口"""
    
    def __init__(self, config: CharacterLearningConfig):
        self.config = config
        self.logger = logger
    
    @abstractmethod
    def learn_from_text(self, character_name: str, text: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        从给定文本中学习角色人设。
        参数:
            character_name: 角色名称
            text: 包含该角色相关内容的新文本（如章节）
            metadata: 额外元数据（如章节号、场景等）
        返回: 学习结果，包含提取的人设更新建议
        """
        pass
    
    @abstractmethod
    def get_character_profile(self, character_name: str) -> Dict[str, Any]:
        """
        获取当前存储的完整角色人设。
        参数:
            character_name: 角色名称
        返回: 角色人设字典
        """
        pass
    
    @abstractmethod
    def update_character_profile(self, character_name: str, updates: Dict[str, Any]) -> bool:
        """
        手动更新角色人设（通常由上层Agent决定是否应用学习结果）。
        参数:
            character_name: 角色名称
            updates: 要更新的字段及值
        返回: 是否成功
        """
        pass

# ---------- 基础实现（骨架） ----------
class BasicCharacterLearner(BaseCharacterLearner):
    """基础人设学习器，提供简单模板，未来可替换为高级模型"""
    
    def __init__(self, config: CharacterLearningConfig):
        super().__init__(config)
        # 可在此初始化存储后端等
        if config.enable_logging:
            self.logger.info(f"Initialized BasicCharacterLearner with config: {config}")
    
    def learn_from_text(self, character_name: str, text: str, metadata: Optional[Dict] = None) -> Dict[str, Any]:
        self.logger.info(f"Learning character '{character_name}' from text of length {len(text)}")
        if len(text) < self.config.min_text_length:
            self.logger.warning("Text too short, skipping learning.")
            return {"status": "skipped", "reason": "text_too_short"}
        
        # TODO: 调用模型协同模块分析文本，提取人设信息
        # 当前骨架返回占位结果
        extracted_traits = {"personality": "unknown", "appearance": "unknown", "abilities": []}
        result = {
            "status": "success",
            "character_name": character_name,
            "extracted_traits": extracted_traits,
            "confidence": 0.5,
            "suggested_updates": extracted_traits  # 在实际实现中应计算差异
        }
        self.logger.debug(f"Learning result: {result}")
        return result
    
    def get_character_profile(self, character_name: str) -> Dict[str, Any]:
        self.logger.info(f"Retrieving profile for '{character_name}'")
        # TODO: 从存储加载角色人设
        # 返回占位样例
        profile = {
            "name": character_name,
            "first_appearance": None,
            "traits": {},
            "history": []
        }
        self.logger.debug(f"Profile: {profile}")
        return profile
    
    def update_character_profile(self, character_name: str, updates: Dict[str, Any]) -> bool:
        self.logger.info(f"Updating profile for '{character_name}' with {updates}")
        # TODO: 合并更新到存储，并保留历史版本
        self.logger.debug("Update simulated successfully.")
        return True

# ---------- 管理器函数（用于热插拔） ----------
_global_learner_instance: Optional[BaseCharacterLearner] = None

def get_character_learner(config: Optional[CharacterLearningConfig] = None) -> BaseCharacterLearner:
    """获取全局人设学习器实例（单例），允许热替换"""
    global _global_learner_instance
    if config is not None or _global_learner_instance is None:
        cfg = config or CharacterLearningConfig()
        if cfg.learner_type == "basic":
            _global_learner_instance = BasicCharacterLearner(cfg)
        else:
            logger.error(f"Unsupported learner type: {cfg.learner_type}")
            raise ValueError(f"Unsupported learner type: {cfg.learner_type}")
    return _global_learner_instance

def hot_swap_learner(new_learner: BaseCharacterLearner) -> None:
    """热替换当前学习器实例，实现可插拔"""
    global _global_learner_instance
    logger.info(f"Hot swapping learner from {type(_global_learner_instance).__name__} to {type(new_learner).__name__}")
    _global_learner_instance = new_learner

# ---------- 单元测试/自测 ----------
if __name__ == "__main__":
    print("Running self-test for CharacterLearning module...")
    # 创建配置
    test_config = CharacterLearningConfig(
        learner_type="basic",
        min_text_length=20,
        similarity_threshold=0.7
    )
    # 获取学习器
    learner = get_character_learner(test_config)
    
    # 测试学习
    result = learner.learn_from_text("Alice", "Alice walked down the street, her red hair glowing in the sun. She was determined to find the truth.", {"chapter": 1})
    print("Learn result:", json.dumps(result, indent=2))
    
    # 测试获取人设
    profile = learner.get_character_profile("Alice")
    print("Profile:", json.dumps(profile, indent=2))
    
    # 测试更新
    update_status = learner.update_character_profile("Alice", {"hair_color": "red"})
    print("Update status:", update_status)
    
    # 测试热替换（模拟）
    class MockLearner(BaseCharacterLearner):
        def learn_from_text(self, char, text, meta=None):
            return {"status": "mocked"}
        def get_character_profile(self, char):
            return {"name": char, "mocked": True}
        def update_character_profile(self, char, updates):
            return True
    
    hot_swap_learner(MockLearner(test_config))
    print("After hot swap, learner type:", type(get_character_learner()).__name__)
    
    # 使用新的学习器测试
    new_result = get_character_learner().learn_from_text("Bob", "Some text", None)
    print("New learner result:", new_result)
    
    print("Self-test completed.")