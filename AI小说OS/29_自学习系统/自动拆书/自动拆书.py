#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动拆书模块骨架
位置: 29_自学习系统/自动拆书/自动拆书.py
功能: 从已有小说文本中自动拆分出结构、角色、情节等可复用元素，用于模型自学习。
层级: 自学习系统层
依赖: 配置管理模块、日志模块、数据读写接口(待定)
被谁调用: 学习调度器、数据分析任务
解决什么问题: 将原始语料转化为结构化学习样本
当前阶段: 接口定义、协议制定、框架搭建，禁止业务逻辑实现
"""

import logging
import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

# ======================= 配置管理 =======================
class AutoSplitConfig:
    """自动拆书配置容器，所有参数可外部注入，支持JSON/字典初始化"""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # 默认配置
        self.min_chapter_length: int = 500          # 最小章节长度(字符数)
        self.max_split_depth: int = 3               # 最大拆分深度
        self.enable_character_extraction: bool = True
        self.enable_plot_analysis: bool = True
        self.save_intermediate: bool = False        # 是否保存中间过程文件
        self.output_dir: str = "data/split_output"  # 输出目录
        self.temp_dir: str = "data/split_temp"      # 临时目录
        self.log_level: int = logging.INFO          # 日志级别
        
        # 从外部配置覆盖
        if config:
            self.__dict__.update(config)
    
    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
    
    @classmethod
    def from_file(cls, path: str) -> 'AutoSplitConfig':
        """从JSON文件加载配置"""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(data)
    
    def save_to_file(self, path: str) -> None:
        """保存配置到JSON文件"""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

# ======================= 抽象接口定义 =======================
class BookSplitterInterface(ABC):
    """自动拆书器抽象接口，所有实现必须继承此类"""
    
    @abstractmethod
    def load_book(self, content: Union[str, Path]) -> None:
        """
        加载待拆分的小说内容
        :param content: 小说文本字符串或文件路径
        """
        pass
    
    @abstractmethod
    def split(self) -> Dict[str, Any]:
        """
        执行拆分操作
        :return: 拆分结果字典，结构由协议定义
        """
        pass
    
    @abstractmethod
    def validate_output(self, result: Dict[str, Any]) -> bool:
        """
        验证拆分结果是否符合格式协议
        :param result: 拆分后的数据
        :return: 是否有效
        """
        pass
    
    @abstractmethod
    def save_result(self, result: Dict[str, Any], path: Optional[str] = None) -> str:
        """
        持久化拆分结果
        :param result: 拆分结果
        :param path: 输出路径，若为None则使用配置中的默认路径
        :return: 实际保存的文件路径
        """
        pass

# ======================= 结果协议定义 =======================
class SplitResultSchema:
    """定义拆分结果的结构协议，供所有实现共同遵守"""
    REQUIRED_FIELDS = {
        "metadata": dict,       # 书籍元信息
        "chapters": list,       # 章节列表，每项为 dict
        "characters": list,     # 角色列表
        "plots": list,          # 情节/事件列表
        "relationships": list,  # 人物关系
    }
    
    OPTIONAL_FIELDS = {
        "timeline": list,       # 时间线
        "themes": list,         # 主题词
        "stats": dict,         # 统计信息
    }
    
    @staticmethod
    def create_empty_result() -> Dict[str, Any]:
        """创建一个空但符合协议的结果结构"""
        return {
            "metadata": {},
            "chapters": [],
            "characters": [],
            "plots": [],
            "relationships": [],
            "timeline": [],
            "themes": [],
            "stats": {}
        }

# ======================= 可插拔实现基类 =======================
class BaseBookSplitter(BookSplitterInterface):
    """自动拆书器基础实现，提供通用功能，具体业务方法需子类重写"""
    
    def __init__(self, config: Optional[AutoSplitConfig] = None):
        self.config = config or AutoSplitConfig()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup_logging()
        self.book_content: Optional[str] = None
        self._result: Dict[str, Any] = SplitResultSchema.create_empty_result()
        
    def _setup_logging(self):
        """根据配置设置日志"""
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.setLevel(self.config.log_level)
    
    def load_book(self, content: Union[str, Path]) -> None:
        """从字符串或文件路径加载小说文本"""
        if isinstance(content, Path):
            # 从文件读取
            try:
                with open(content, 'r', encoding='utf-8') as f:
                    self.book_content = f.read()
                self.logger.info(f"已从文件加载小说: {content}, 长度: {len(self.book_content)}字")
            except Exception as e:
                self.logger.error(f"读取文件失败: {e}")
                raise
        else:
            self.book_content = content
            self.logger.info(f"已加载小说文本, 长度: {len(self.book_content)}字")
    
    def split(self) -> Dict[str, Any]:
        """执行拆分的主流程，子类可能重写，但建议先调用此基类方法进行前置检查"""
        if not self.book_content:
            raise ValueError("尚未加载小说内容，请先调用load_book()")
        self.logger.info("开始自动拆书流程...")
        self._result = SplitResultSchema.create_empty_result()
        
        # 子类应在此处调用各自的拆分方法
        # self._split_chapters()
        # self._extract_characters()
        # ...
        self.logger.warning("基类split()未实现具体拆分逻辑，请使用子类实现")
        return self._result
    
    def validate_output(self, result: Dict[str, Any]) -> bool:
        """验证输出是否符合协议，只检查必填字段是否存在且类型正确"""
        for field, required_type in SplitResultSchema.REQUIRED_FIELDS.items():
            if field not in result:
                self.logger.error(f"缺少必填字段: {field}")
                return False
            if not isinstance(result[field], required_type):
                self.logger.error(f"字段{field}类型错误，期望{required_type}，实际{type(result[field])}")
                return False
        self.logger.info("结果验证通过，符合协议要求")
        return True
    
    def save_result(self, result: Dict[str, Any], path: Optional[str] = None) -> str:
        """保存拆书结果为JSON文件"""
        if not self.validate_output(result):
            raise ValueError("结果未通过验证，无法保存")
        
        output_path = Path(path or self.config.output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 生成带时间戳的文件名
        import time
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"split_result_{timestamp}.json"
        full_path = output_path / filename
        
        with open(full_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        self.logger.info(f"拆分结果已保存至: {full_path}")
        return str(full_path)

# ======================= 默认实现（空壳，满足可运行） =======================
class DefaultBookSplitter(BaseBookSplitter):
    """默认的书籍拆分器实现，所有具体方法留空，等待后续开发"""
    
    def split(self) -> Dict[str, Any]:
        """占位实现，返回空结果"""
        super().split()  # 调用基类的前置检查
        self.logger.info("DefaultBookSplitter: 执行占位拆分，无实际逻辑。")
        # TODO: 在此实现具体拆分逻辑
        return self._result

# ======================= 自测代码 =======================
if __name__ == "__main__":
    # 1. 测试配置
    print("=== 测试配置管理 ===")
    config = AutoSplitConfig()
    print("默认配置:", config.to_dict())
    
    custom_config = AutoSplitConfig({"min_chapter_length": 300, "log_level": logging.DEBUG})
    print("自定义配置:", custom_config.to_dict())
    
    # 2. 测试加载
    splitter = DefaultBookSplitter(config=custom_config)
    test_text = "第一章 开端\n这是一个测试小说。\n第二章 发展\n故事情节展开..."
    splitter.load_book(test_text)
    
    # 3. 测试拆分（空壳）
    result = splitter.split()
    print("拆分结果:", result)
    
    # 4. 测试验证
    print("验证结果:", splitter.validate_output(result))
    
    # 5. 测试保存（会创建文件，可注释掉）
    # splitter.save_result(result, "test_output")
    
    print("=== 骨架自测完成 ===")