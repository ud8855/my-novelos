#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NovelOS 初始化器骨架模块
路径：00_启动入口/初始化器.py
职责：
  - 系统启动时的全局初始化
  - 配置加载与校验
  - 日志系统装配
  - 动态模块注册与加载（可按配置插拔）
  - 统一的生命周期管理（启动、停止、重启）

设计原则：
  1. 配置驱动：通过配置文件控制所有初始化行为，禁止硬编码
  2. 热插拔：模块列表完全由配置决定，动态导入
  3. 异常隔离：单个模块加载失败不影响整体启动，但记录日志
  4. 单一职责：仅负责初始化编排，不深入任何业务逻辑
  5. 可观测：完善的日志与异常链追踪

依赖：
  - 外部库：PyYAML（可选，此处用 json 做基础实现，后续替换）
  - 内部模块：无（禁止跨层依赖）

被调用者：
  - 启动脚本 main.py / run.py（入口点）
  - 系统守护进程 / 容器启动命令

解决的核心问题：
  避免启动逻辑散落各处，提供可维护、可观测的系统入口。

当前阶段：骨架实现，仅搭建结构，不实现具体业务逻辑。
"""

import json
import logging
import os
import sys
import importlib
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

# ----------------------------------------------------------------------
# 全局常量（可配置化）
# ----------------------------------------------------------------------
DEFAULT_CONFIG_PATH = "config.json"          # 默认配置文件路径（优先使用环境变量 NOVELOS_CONFIG）
DEFAULT_LOG_LEVEL = logging.INFO             # 默认日志级别
DEFAULT_MODULE_BASE_PATH = Path(__file__).resolve().parent.parent  # 模块根目录：项目根

class Initializer:
    """
    系统初始化器：负责启动流程编排，所有初始化步骤均通过本类完成
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        参数:
            config_path: 配置文件路径，若为 None 则依次检查环境变量、默认路径
        """
        # 1. 确定配置文件路径
        if config_path is None:
            config_path = os.environ.get("NOVELOS_CONFIG", DEFAULT_CONFIG_PATH)
        self.config_path = Path(config_path)
        # 2. 加载配置
        self.config: Dict[str, Any] = self._load_config()
        # 3. 装配日志系统
        self.logger: logging.Logger = self._setup_logging()
        # 4. 模块注册表（占位，后续动态填充）
        self.registered_modules: List[Any] = []
        self._initialized = False
        
        self.logger.info(f"Initializer created with config: {self.config_path}")

    # ------------------------------------------------------------------
    # 配置加载
    # ------------------------------------------------------------------
    def _load_config(self) -> Dict[str, Any]:
        """
        加载并校验配置文件，当前仅支持 JSON 格式（骨架阶段）
        返回配置字典；失败时抛出明确异常，阻止系统启动。
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                raw_config = json.load(f)
            # 此处可添加 schema 校验（未来可引入 pydantic）
            self.logger.debug("Configuration loaded successfully.")
            return raw_config
        except Exception as e:
            logging.critical(f"Failed to load config from {self.config_path}: {e}")
            raise

    # ------------------------------------------------------------------
    # 日志系统
    # ------------------------------------------------------------------
    def _setup_logging(self) -> logging.Logger:
        """
        根据配置建立日志系统：
          - 支持控制台输出 + 可选文件输出
          - 格式统一：时间、级别、模块、消息
          - 日志级别可由配置覆盖
        返回配置好的 root logger（或自定义 logger）
        """
        log_config = self.config.get("logging", {})
        log_level_str = log_config.get("level", "INFO")
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
        log_format = log_config.get("format", 
                                    "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
        date_format = log_config.get("datefmt", "%Y-%m-%d %H:%M:%S")
        
        # 重置 root logger 避免重复添加（防御性编程）
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(log_level)
        
        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_formatter = logging.Formatter(log_format, datefmt=date_format)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        # 文件处理器（可选）
        log_file = log_config.get("file")
        if log_file:
            try:
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                file_handler = logging.FileHandler(log_path, encoding='utf-8')
                file_handler.setLevel(log_level)
                file_handler.setFormatter(console_formatter)
                root_logger.addHandler(file_handler)
            except Exception as e:
                print(f"Warning: Failed to set up file logging: {e}", file=sys.stderr)
        
        # 创建初始化器专用 logger
        logger = logging.getLogger("NovelOS.Initializer")
        logger.info("Logging system initialized (level=%s)", log_level_str)
        return logger

    # ------------------------------------------------------------------
    # 模块动态注册（插拔核心）
    # ------------------------------------------------------------------
    def _register_modules(self) -> None:
        """
        根据配置中的模块列表，动态导入并初始化各模块。
        模块声明格式（config.json 示例）：
        {
          "modules": [
            {
              "name": "核心引擎",
              "path": "10_核心引擎.初始化器",
              "class": "CoreInit",
              "args": {},
              "enabled": true
            },
            ...
          ]
        }
        每加载一个模块，调用其初始化方法（约定接口：initialize(config) 或构造器接收 config）
        异常处理：单个模块失败记录错误但继续，最终抛出聚合异常（若配置要求严格模式）
        """
        modules_config = self.config.get("modules", [])
        if not modules_config:
            self.logger.warning("No modules specified in configuration. System may be incomplete.")
            return
        
        strict_mode = self.config.get("strict_mode", False)
        errors = []
        
        for module_spec in modules_config:
            if not module_spec.get("enabled", True):
                self.logger.info(f"Module '{module_spec.get('name', 'Unnamed')}' is disabled, skipping.")
                continue
            
            module_name = module_spec.get("name", "Unknown")
            module_path = module_spec.get("path")
            module_class = module_spec.get("class")
            if not module_path or not module_class:
                self.logger.error(f"Invalid module spec for '{module_name}', missing 'path' or 'class'. Skipping.")
                continue
            
            try:
                # 动态导入模块（假设模块在项目根目录下，使用相对路径需要处理 sys.path）
                # 注意：目前我们仍在开发阶段，模块可能未完全实现，需容错
                self.logger.info(f"Loading module: {module_name} from {module_path}")
                # 这里只是占位：实际导入逻辑可调用 importlib
                # importlib.import_module(module_path)   # 骨架阶段暂不真正导入，避免依赖不存在
                # 实例化类并调用初始化
                # module_instance = getattr(mod, module_class)(**module_spec.get("args", {}))
                # module_instance.initialize(self.config)   # 约定初始化方法
                # self.registered_modules.append(module_instance)
                self.logger.debug(f"Module '{module_name}' loaded (skeleton - no real import).")
            except Exception as e:
                err_msg = f"Failed to load module '{module_name}': {e}\n{traceback.format_exc()}"
                self.logger.error(err_msg)
                errors.append(err_msg)
                if strict_mode:
                    raise RuntimeError(f"Strict mode enabled, aborting on module failure: {module_name}") from e
                # 否则继续加载其他模块
        
        if errors:
            self.logger.warning(f"{len(errors)} module(s) failed to load. First error: {errors[0]}")

    # ------------------------------------------------------------------
    # 生命周期管理
    # ------------------------------------------------------------------
    def start(self) -> None:
        """
        启动初始化流程：
          1. 打印启动横幅（可选）
          2. 校验系统环境（Python版本、必要目录等）
          3. 注册并初始化所有模块
          4. 标记初始化完成
        """
        if self._initialized:
            self.logger.warning("Initializer already started, skipping.")
            return
        
        self.logger.info("=" * 60)
        self.logger.info("NovelOS Initialization Starting...")
        self.logger.info("=" * 60)
        
        # 环境预检（骨架版）
        self._check_environment()
        
        # 动态注册模块
        self._register_modules()
        
        self._initialized = True
        self.logger.info("NovelOS initialization completed successfully.")

    def shutdown(self) -> None:
        """
        优雅关闭：执行模块清理，保存状态等
        当前骨架阶段仅记录日志
        """
        self.logger.info("NovelOS shutting down...")
        for module in reversed(self.registered_modules):
            try:
                if hasattr(module, 'shutdown'):
                    module.shutdown()
            except Exception as e:
                self.logger.error(f"Error shutting down module {module.__class__.__name__}: {e}")
        self.logger.info("NovelOS shutdown complete.")
        self._initialized = False

    def restart(self) -> None:
        """
        软重启：关闭所有模块后重新初始化
        """
        self.logger.info("NovelOS restarting...")
        self.shutdown()
        self.start()

    # ------------------------------------------------------------------
    # 环境预检（辅助）
    # ------------------------------------------------------------------
    def _check_environment(self) -> None:
        """
        检查运行环境是否满足最低要求：
          - Python版本
          - 关键目录存在性
          - 必要依赖（骨架阶段略过）
        """
        self.logger.debug("Checking environment...")
        # 示例：检查项目根目录是否存在关键子目录
        required_dirs = self.config.get("required_directories", [])
        for dir_name in required_dirs:
            dir_path = DEFAULT_MODULE_BASE_PATH / dir_name
            if not dir_path.exists():
                self.logger.warning(f"Required directory not found: