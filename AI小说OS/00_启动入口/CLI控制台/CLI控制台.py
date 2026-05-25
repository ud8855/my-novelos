#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NovelOS CLI控制台
启动入口模块，负责参数解析、配置加载、日志初始化及动态模块加载。
遵循：可插拔、日志、配置化、热插拔原则。
"""

import argparse
import importlib
import json
import logging
import os
import sys
import traceback
from typing import Any, Dict, List, Optional

# 默认值
DEFAULT_CONFIG_PATH = "config.json"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"


def setup_logging(level: str, log_file: Optional[str] = None) -> None:
    """初始化日志系统，支持文件与控制台输出"""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=numeric_level,
        format=DEFAULT_LOG_FORMAT,
        handlers=handlers,
    )
    logging.info(f"日志系统初始化完成，级别={level}，文件={log_file or '无'}")


def load_config(config_path: str) -> Dict[str, Any]:
    """加载配置文件，支持JSON/YAML，返回配置字典"""
    if not os.path.isfile(config_path):
        logging.warning(f"配置文件不存在: {config_path}，使用空配置。")
        return {}
    ext = os.path.splitext(config_path)[1].lower()
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            if ext in (".yaml", ".yml"):
                import yaml  # type: ignore
                config = yaml.safe_load(f)
            else:
                config = json.load(f)
        logging.info(f"配置文件已加载: {config_path}")
        return config
    except Exception as e:
        logging.error(f"加载配置文件失败: {e}")
        return {}


def load_modules(module_configs: List[Dict[str, Any]]) -> None:
    """
    动态加载并初始化模块。
    每个模块配置需包含: name, path, 可选的 init 参数字典。
    模块需实现 initialize(**init_params) 函数。
    """
    for idx, module_cfg in enumerate(module_configs):
        name = module_cfg.get("name", f"module_{idx}")
        path = module_cfg.get("path")
        if not path:
            logging.error(f"模块 '{name}' 未指定路径，跳过。")
            continue
        try:
            logging.info(f"加载模块: {name} <- {path}")
            mod = importlib.import_module(path)
            if hasattr(mod, "initialize"):
                init_params = module_cfg.get("init", {})
                mod.initialize(**init_params)
                logging.info(f"模块 '{name}' 初始化成功。")
            else:
                logging.warning(f"模块 '{name}' 未定义 initialize()，跳过初始化。")
        except ImportError:
            logging.error(
                f"模块 '{name}' 导入失败: {path} 不可用。",
                exc_info=True,
            )
        except Exception:
            logging.error(
                f"模块 '{name}' 初始化异常。",
                exc_info=True,
            )


def run_self_test() -> None:
    """自测流程：验证日志、配置加载、模块模拟加载"""
    print("=== NovelOS CLI 自测开始 ===")
    os.environ["NOVELOS_TEST"] = "1"
    # 测试日志
    try:
        setup_logging("DEBUG", "test_cli.log")
        logging.debug("自测日志记录成功")
        assert os.path.isfile("test_cli.log"), "日志文件未生成"
        print("[PASS] 日志系统")
    except Exception as e:
        print(f"[FAIL] 日志系统: {e}")

    # 测试配置加载
    try:
        test_config = {"modules": []}
        with open("test_config.json", "w", encoding="utf-8") as f:
            json.dump(test_config, f)
        loaded = load_config("test_config.json")
        assert loaded == test_config, "配置不一致"
        os.remove("test_config.json")
        print("[PASS] 配置加载")
    except Exception as e:
        print(f"[FAIL] 配置加载: {e}")

    # 测试模块加载（使用不存在模块和空模块）
    try:
        test_modules = [
            {
                "name": "missing",
                "path": "nonexistent.module",
            },
            {
                "name": "empty_test",
                "path": "00_启动入口.empty_test_module",
                "init": {"key": "value"},
            },
        ]
        # 创建一个临时空测试模块
        os.makedirs("00_启动入口/__pycache__", exist_ok=True)
        with open("00_启动入口/empty_test_module.py", "w", encoding="utf-8") as f: