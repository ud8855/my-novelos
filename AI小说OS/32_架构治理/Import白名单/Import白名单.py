# -*- coding: utf-8 -*-
"""
架构治理 - 导入白名单
层级：32_架构治理
依赖：Python 标准库
被谁调用：系统启动脚本，全局生效
解决问题：防止模块间非法依赖，确保只能导入白名单内模块，维护架构边界。

设计要点：
- 单例检查器，全局唯一
- 支持运行时启用/禁用（热插拔）
- 白名单可配置，支持通配符（如 "module.*"）
- 日志记录每一次拦截
- 可在任何时刻注入新的白名单规则
"""
import sys
import logging
import re
from typing import List, Optional, Set, Pattern


# ---------- 配置常量 ----------
# 默认白名单（允许的所有基础模块，后续可通过配置文件覆盖）
DEFAULT_WHITELIST = [
    "os",
    "sys",
    "importlib",
    "logging",
    "pathlib",
    "typing",
    "json",
    "yaml",
    "re",
    # 项目内部允许的顶级包（示例，实际应从配置加载）
    "01_核心层.*",
    "10_数据层.*",
    "20_模型协同.*",
    "21_API模型.*",
    "30_运行时.*",
    "32_架构治理.*",
]


# ---------- 辅助工具 ----------
def _pattern_to_regex(pattern: str) -> Pattern:
    """将简单的 glob 风格模式转换为正则表达式。"""
    escaped = re.escape(pattern)
    escaped = escaped.replace(r"\*", ".*")  # * 匹配任意
    if not pattern.startswith("*"):
        escaped = "^" + escaped
    if not pattern.endswith("*"):
        escaped = escaped + "$"
    return re.compile(escaped)


# ---------- 核心类 ----------
class ImportWhitelistChecker:
    """
    导入白名单检查器（单例）
    维护一组允许的模块模式，并在启用时通过 sys.meta_path 拦截导入。
    """

    _instance = None
    _enabled: bool = False

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, whitelist: Optional[List[str]] = None):
        # 避免重复初始化
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.logger = logging.getLogger("ImportWhitelist")
        self._patterns: List[Pattern] = []  # 已编译的正则表达式列表
        self._finder = None  # 类型: WhitelistFinder，启用时创建
        self.load_whitelist(whitelist)

    # ----- 配置管理 -----
    def load_whitelist(self, whitelist: Optional[List[str]] = None):
        """
        加载白名单配置
        参数 whitelist：模块名列表，每一项可包含 * 通配符；
                       若为 None 则使用 DEFAULT_WHITELIST。
        """
        if whitelist is None:
            whitelist = DEFAULT_WHITELIST

        # 编译每一条规则为正则
        self._patterns = [_pattern_to_regex(p) for p in whitelist]
        self.logger.info(f"Import whitelist loaded: {len(self._patterns)} patterns.")

    def add_rule(self, pattern: str):
        """动态添加一条白名单规则（热更新）"""
        self._patterns.append(_pattern_to_regex(pattern))
        self.logger.info(f"Added whitelist rule: {pattern}")

    def remove_rule(self, pattern: str):
        """动态移除一条白名单规则（通过原始模式文本）"""
        regex = _pattern_to_regex(pattern)
        before = len(self._patterns)
        self._patterns = [p for p in self._patterns if p.pattern != regex.pattern]
        after = len(self._patterns)
        if after < before:
            self.logger.info(f"Removed whitelist rule: {pattern}")
        else:
            self.logger.warning(f"Rule not found: {pattern}")

    # ----- 检查逻辑 -----
    def allow_module(self, module_name: str) -> bool:
        """判断指定模块名是否在白名单内"""
        for pattern in self._patterns:
            if pattern.search(module_name):
                return True
        return False

    # ----- 启用/禁用 -----
    def enable(self):
        """启用导入拦截。可重复调用（幂等）"""
        if self._enabled:
            return
        # 创建 Finder 并插入 meta_path 最前面
        self._finder = WhitelistFinder(self)
        sys.meta_path.insert(0, self._finder)
        self._enabled = True
        self.logger.info("Import whitelist ENABLED. All imports will be checked.")

    def disable(self):
        """禁用导入拦截，恢复原始导入行为。可重复调用"""
        if not self._enabled:
            return
        # 从 meta_path 中移除我们的 finder
        if self._finder:
            sys.meta_path = [f for f in sys.meta_path if f is not self._finder]
            self._finder = None
        self._enabled = False
        self.logger.info("Import whitelist DISABLED. Imports unrestricted.")

    def is_enabled(self) -> bool:
        return self._enabled


class WhitelistFinder:
    """
    自定义导入查找器。
    符合 importlib.abc.MetaPathFinder 协议，在 sys.meta_path 中优先执行。
    """

    def __init__(self, checker: ImportWhitelistChecker):
        self.check