# -*- coding: utf-8 -*-
"""
环境检查模块
所属层：00_启动入口
依赖：标准库 (sys, os, logging, importlib, json)
被调用：由启动脚本 (如 main.py) 在程序入口首先调用
功能：可插拔的环境检查框架，通过配置驱动检查项，输出检查报告，确保系统运行前环境完备
"""
import sys
import os
import logging
import importlib
import json
from typing import List, Dict, Callable, Tuple, Optional, Union

# ---------- 配置区（可由外部配置注入） ----------
DEFAULT_CHECK_CONFIG = {
    "python_version": {
        "min": "3.10",
        "max": "4.0",
        "enabled": True
    },
    "required_packages": {
        "list": ["pydantic", "loguru", "aiohttp", "openai"],
        "enabled": True
    },
    "required_dirs": {
        "list": [
            "00_启动入口",
            "10_数据层",
            "20_模型协同",
            "21_API模型",
            "30_业务规则",
            "40_应用服务",
            "50_表示层",
            "60_配置",
            "70_测试",
            "80_工具",
            "90_文档"
        ],
        "base_path": os.path.dirname(os.path.dirname(__file__)),  # 项目根目录
        "enabled": True
    },
    "config_files": {
        "list": ["config/settings.toml", "config/agents.toml"],
        "enabled": True
    }
}

# ---------- 日志设置 ----------
logger = logging.getLogger("EnvironmentChecker")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)


class CheckItem:
    """单个检查项定义"""
    def __init__(self, name: str, check_func: Callable[[], Tuple[bool, str]], enabled: bool = True):
        self.name = name
        self.check_func = check_func
        self.enabled = enabled

    def run(self) -> Tuple[bool, str]:
        """执行检查，返回 (通过, 消息)"""
        if not self.enabled:
            return True, f"检查项 '{self.name}' 已被禁用，跳过。"
        try:
            result, message = self.check_func()
            return result, message
        except Exception as e:
            return False, f"检查项 '{self.name}' 执行异常: {str(e)}"


class EnvironmentChecker:
    """环境检查器，支持动态注册检查项和配置驱动"""

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or DEFAULT_CHECK_CONFIG
        self.checks: List[CheckItem] = []
        self._register_default_checks()

    def _register_default_checks(self):
        """根据默认配置注册检查项（可被外部覆盖）"""
        if self.config.get("python_version", {}).get("enabled", True):
            self.register_check(
                "Python版本检查",
                self._check_python_version,
                enabled=True
            )
        if self.config.get("required_packages", {}).get("enabled", True):
            self.register_check(
                "必要依赖包检查",
                self._check_required_packages,
                enabled=True
            )
        if self.config.get("required_dirs", {}).get("enabled", True):
            self.register_check(
                "项目目录结构检查",
                self._check_required_dirs,
                enabled=True
            )
        if self.config.get("config_files", {}).get("enabled", True):
            self.register_check(
                "配置文件存在性检查",
                self._check_config_files,
                enabled=True
            )

    def register_check(self, name: str, check_func: Callable[[], Tuple[bool, str]], enabled: bool = True):
        """注册新的检查项，实现可插拔"""
        item = CheckItem(name, check_func, enabled)
        self.checks.append(item)
        logger.info(f"注册环境检查项: {name} (启用={enabled})")

    def remove_check(self, name: str):
        """移除检查项"""
        self.checks = [c for c in self.checks if c.name != name]
        logger.info(f"移除环境检查项: {name}")

    def run_all_checks(self) -> bool:
        """运行所有已启用的检查，返回是否全部通过"""
        logger.info("========== 开始环境检查 ==========")
        all_passed = True
        for check in self.checks:
            passed, msg = check.run()
            status = "通过" if passed else "失败"
            log_level = logging.INFO if passed else logging.ERROR
            logger.log(log_level, f"[{status}] {check.name}: {msg}")
            if not passed:
                all_passed = False
        if all_passed:
            logger.info("========== 环境检查全部通过 ==========")
        else:
            logger.error("========== 环境检查存在失败项，系统可能无法正常运行 ==========")
        return all_passed

    # ---------- 内置检查函数 ----------
    @staticmethod
    def _check_python_version() -> Tuple[bool, str]:
        """检查Python版本是否满足要求"""
        min_ver = tuple(map(int, DEFAULT_CHECK_CONFIG["python_version"]["min"].split(".")))
        max_ver = tuple(map(int, DEFAULT_CHECK_CONFIG["python_version"]["max"].split(".")))
        cur_ver = sys.version_info[:3]
        if cur_ver < min_ver:
            return False, f"Python版本过低: 当前 {sys.version.split()[0]}，要求 >= {'.'.join(map(str, min_ver))}"
        if cur_ver >= max_ver:
            return False, f"Python版本过高: 当前 {sys.version.split()[0]}，要求 < {'.'.join(map(str, max_ver))}"
        return True, f"Python版本 {sys.version.split()[0]} 符合要求"

    @staticmethod
    def _check_required_packages() -> Tuple[bool, str]:
        """检查必需的pip包是否已安装"""
        pkgs = DEFAULT_CHECK_CONFIG["required_packages"]["list"]
        missing = []
        for pkg in pkgs:
            try:
                importlib.import_module(pkg.replace("-", "_"))  # 简单处理
            except ImportError:
                missing.append(pkg)
        if missing:
            return False, f"缺少依赖包: {', '.join(missing)}"
        return True, "所有必要依赖包已安装"

    @staticmethod
    def _check_required_dirs() -> Tuple[bool, str]:
        """检查项目必需目录是否存在"""
        base = DEFAULT_CHECK_CONFIG["required_dirs"]["base_path"]
        dirs = DEFAULT_CHECK_CONFIG["required_dirs"]["list"]
        missing = []
        for d in dirs:
            path = os.path.join(base, d)
            if not os.path.isdir(path):
                missing.append(d)
        if missing:
            return False, f"缺少目录: {', '.join(missing)} (相对于 {base})"
        return True, "项目目录结构完整"

    @staticmethod
    def _check_config_files() -> Tuple[bool, str]:
        """检查配置文件是否存在"""
        base = DEFAULT_CHECK_CONFIG["required_dirs"]["base_path"]
        files = DEFAULT_CHECK_CONFIG["config_files"]["list"]
        missing = []
        for f in files:
            path = os.path.join(base, f)
            if not os.path.isfile(path):
                missing.append(f)
        if missing:
            return False, f"缺少配置文件: {', '.join(missing)} (相对于 {base})"
        return True, "所有配置文件存在"


# ---------- 快捷函数 ----------
def quick_check() -> bool:
    """快速执行默认环境检查"""
    checker = EnvironmentChecker()
    return checker.run_all_checks()


# ---------- 自测 ----------
if __name__ == "__main__":
    # 执行环境检查
    success = quick_check()
    if not success:
        sys.exit(1)
    else:
        print("环境自测通过，可以启动系统。")