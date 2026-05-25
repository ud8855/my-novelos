"""
Prompt编译模块
所属层：09_上下文系统
依赖：无（标准库：abc, logging, importlib, time, typing）
被调用者：上下文管理模块、策略Agent、提示词构造器
解决问题：将模板与上下文变量编译为最终发送给模型的标准提示词，支持多种模板引擎，可插拔。
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
import importlib
import time

# 模块级日志记录器（可由外部配置）
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# ===================== 配置类 =====================
class CompilerConfig:
    """编译器配置，支持从字典加载，可扩展"""
    def __init__(self, compiler_class: str = "SimplePromptCompiler", options: Optional[Dict[str, Any]] = None):
        # compiler_class: 编译器类的完整路径，如 "module.MyCompiler" 或内置类名
        self.compiler_class = compiler_class
        self.options = options or {}
        self.max_template_length = 10000
        self.timeout = 5.0  # 编译超时预留

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "CompilerConfig":
        return cls(**config_dict)


# ===================== 抽象接口（协议） =====================
class CompilerInterface(ABC):
    """编译器抽象接口，所有自定义编译器必须实现此协议"""
    @abstractmethod
    def compile(self, template: str, context: Dict[str, Any]) -> str:
        """编译prompt
        Args:
            template: 模板字符串，支持自定义语法
            context: 变量上下文
        Returns:
            编译后的prompt字符串
        Raises:
            CompilerError: 编译失败时抛出
        """
        pass


# ===================== 默认编译器 =====================
class SimplePromptCompiler(CompilerInterface):
    """默认编译器：使用Python字符串格式化（建议仅在原型阶段使用，生产环境应使用Jinja2等安全引擎）"""
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.SimplePromptCompiler")

    def compile(self, template: str, context: Dict[str, Any]) -> str:
        start_time = time.perf_counter()
        self.logger.info(f"开始编译prompt，模板长度: {len(template)}")
        try:
            result = template.format(**context)
            elapsed = (time.perf_counter() - start_time) * 1000
            self.logger.info(f"编译成功，耗时: {elapsed:.2f}ms")
            return result
        except KeyError as e:
            self.logger.error(f"编译失败：缺少变量 {e}")
            raise CompilerError(f"