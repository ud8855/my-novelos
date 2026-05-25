"""
数据清洗模块 (Data Cleaning Module)

本模块提供了一个可插拔的数据清洗框架，用于对小说创作过程中产生的文本数据进行清洗和预处理。
它定义了清洗器的抽象接口，并包含一个基本的默认实现，同时支持配置化和日志记录。
所有清洗器必须实现 DataCleaner 接口，以便系统可以动态加载和替换不同的清洗策略。

依赖：
- 无外部模块依赖，仅使用 Python 标准库（abc, logging, typing 等）。

被调用：
- 自学习系统中的数据预处理流程会调用此模块，也可能是其他需要数据清洗的组件通过接口调用。
- 通过工厂方法 get_cleaner 获取具体的清洗器实例。

解决的核心问题：
- 为自学习系统提供统一的数据清洗入口，确保数据质量。
- 支持热插拔，允许开发人员添加新的清洗算法而不影响现有代码。
- 通过配置灵活控制清洗行为。
- 提供详细的日志记录，便于追踪和调试。
"""

import logging
import hashlib
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DataCleaningConfig:
    """
    数据清洗配置类，用于设置清洗参数。

    参数:
        remove_duplicates (bool): 是否去除重复数据，默认为 True。
        remove_empty (bool): 是否去除空字符串或仅包含空白字符的数据，默认为 True。
        max_length (int): 数据保留的最大长度，超过此长度的数据将被截断，0 表示不限，默认为 0。
        min_length (int): 数据保留的最小长度，低于此长度的数据将被丢弃，0 表示不限，默认为 0。
        custom_params (Dict): 留给特定清洗器的自定义参数字典，默认为空。
    """

    def __init__(self, 
                 remove_duplicates: bool = True,
                 remove_empty: bool = True,
                 max_length: int = 0,
                 min_length: int = 0,
                 custom_params: Optional[Dict[str, Any]] = None):
        self.remove_duplicates = remove_duplicates
        self.remove_empty = remove_empty
        self.max_length = max_length
        self.min_length = min_length
        self.custom_params = custom_params if custom_params is not None else {}

    def to_dict(self) -> Dict:
        """将配置转为字典，便于序列化。"""
        return {
            "remove_duplicates": self.remove_duplicates,
            "remove_empty": self.remove_empty,
            "max_length": self.max_length,
            "min_length": self.min_length,
            "custom_params": self.custom_params
        }

    @classmethod
    def from_dict(cls, config_dict: Dict) -> 'DataCleaningConfig':
        """从字典创建配置实例。"""
        return cls(
            remove_duplicates=config_dict.get("remove_duplicates", True),
            remove_empty=config_dict.get("remove_empty", True),
            max_length=config_dict.get("max_length", 0),
            min_length=config_dict.get("min_length", 0),
            custom_params=config_dict.get("custom_params", {})
        )


class DataCleaner(ABC):
    """
    抽象数据清洗器接口。

    所有具体的清洗器必须继承此类并实现 clean 方法。
    清洗器应当处理一批数据列表，返回清洗后的数据列表，并保持顺序基本不变（除非去重等操作导致）。
    """

    def __init__(self, config: Optional[DataCleaningConfig] = None):
        self.config = config if config else DataCleaningConfig()
        logger.info(f"初始化清洗器：{self.__class__.__name__}，配置：{self.config.to_dict()}")

    @abstractmethod
    def clean(self, data: List[str]) -> List[str]:
        """
        清洗数据的主方法。

        参数:
            data (List[str]): 待清洗的原始文本数据列表。

        返回:
            List[str]: 清洗后的数据列表。
        """
        pass

    def __str__(self):
        return f"<{self.__class__.__name__} config={self.config.to_dict()}>"


class DefaultDataCleaner(DataCleaner):
    """
    默认的数据清洗器，提供基础的数据清洗功能。

    根据配置执行以下操作：
    - 去除重复项（基于内容的哈希值）。
    - 去除空字符串或仅含空白符的项。
    - 根据最小/最大长度过滤/截断数据。
    这些操作按顺序执行：先去除空项 -> 去重 -> 长度处理。
    """

    def clean(self, data: List[str]) -> List[str]:
        logger.info(f"开始清洗数据，原始数量：{len(data)}")
        cleaned = data

        # 1. 去除空白项
        if self.config.remove_empty:
            before = len(cleaned)
            cleaned = [item for item in cleaned if item.strip()]
            logger.info(f"移除空项：{before} -> {len(cleaned)}")

        # 2. 去除重复项（保持首次出现顺序）
        if self.config.remove_duplicates:
            before = len(cleaned)
            seen_hashes: Set[str] = set()
            deduped = []
            for item in cleaned:
                item_hash = hashlib.md5(item.encode('utf-8')).hexdigest()
                if item_hash not in seen_hashes:
                    seen_hashes.add(item_hash)
                    deduped.append(item)
            cleaned = deduped
            logger.info(f"去重：{before} -> {len(cleaned)}")

        # 3. 长度处理
        processed = []
        for item in cleaned:
            # 最小长度过滤
            if self.config.min_length > 0 and len(item) < self.config.min_length:
                logger.debug(f"丢弃长度不足项：{item[:30]}...")
                continue
            # 最大长度截断
            if self.config.max_length > 0 and len(item) > self.config.max_length:
                item = item[:self.config.max_length]
            processed.append(item)
        cleaned = processed

        logger.info(f"清洗完成，最终数量：{len(cleaned)}")
        return cleaned


# 清洗器注册表，用于动态加载不同清洗器
_CLEANER_REGISTRY: Dict[str, type] = {
    "default": DefaultDataCleaner,
}

def register_cleaner(name: str, cleaner_class: type) -> None:
    """注册一个新的清洗器类，以便通过名称获取。"""
    if not issubclass(cleaner_class, DataCleaner):
        raise TypeError(f"{cleaner_class.__name__} 必须继承自 DataCleaner")
    _CLEANER_REGISTRY[name] = cleaner_class
    logger.info(f"注册数据清洗器：'{name}' -> {cleaner_class.__name__}")

def get_cleaner(name: str = "default", config: Optional[DataCleaningConfig] = None) -> DataCleaner:
    """
    根据名称获取清洗器实例。
    
    参数:
        name (str): 清洗器名称，默认为 'default'。
        config (DataCleaningConfig): 可选配置对象。
    
    返回:
        DataCleaner: 对应的清洗器实例。
    """
    cleaner_class = _CLEANER_REGISTRY.get(name)
    if cleaner_class is None:
        raise ValueError(f"未找到名称为 '{name}' 的数据清洗器。可用清洗器：{list(_CLEANER_REGISTRY.keys())}")
    return cleaner_class(config)

def list_cleaners() -> List[str]:
    """返回所有已注册的清洗器名称列表。"""
    return list(_CLEANER_REGISTRY.keys())


# 自测代码块
if __name__ == "__main__":
    logger.info("===== 数据清洗模块自测 =====")
    
    # 测试配置
    config = DataCleaningConfig(
        remove_duplicates=True,
        remove_empty=True,
        max_length=6,
        min_length=2,
        custom_params={"test": 123}
    )
    
    # 获取默认清洗器
    cleaner = get_cleaner("default", config)
    print(f"当前清洗器: {cleaner}")
    
    # 测试数据
    raw_data = [
        "你好世界",
        "   ",          # 空项
        "AI小说",
        "你好世界",     # 重复
        "ab",           # 等于最小长度
        "a",            # 小于最小长度
        "这是一个超过六个字的例子",  # 超过最大长度，会被截断
        "有效数据",
        "",
    ]
    
    print(f"\n原始数据 ({len(raw_data)} 条):")
    for i, item in enumerate(raw_data, 1):
        print(f"  {i}: '{item}'")
    
    # 执行清洗
    cleaned_data = cleaner.clean(raw_data)
    
    print(f"\n清洗后数据 ({len(cleaned_data)} 条):")
    for i, item in enumerate(cleaned_data, 1):
        print(f"  {i}: '{item}'")
    
    # 展示可用清洗器
    print(f"\n已注册的清洗器: {list_cleaners()}")
    
    # 测试注册新清洗器和通过名称获取
    class AnotherCleaner(DataCleaner):
        def clean(self, data: List[str]) -> List[str]:
            return [item.upper() for item in data if item.strip()]  # 简单的示例
    
    register_cleaner("upper", AnotherCleaner)
    print(f"注册后可用清洗器: {list_cleaners()}")
    
    # 使用新的清洗器
    new_cleaner = get_cleaner("upper")
    test_data = ["hello", "  ", "world"]
    print(f"\n使用 'upper' 清洗器：{new_cleaner.clean(test_data)}")