"""
Module: module_loader
Layer: 03_内核系统 (Core System Layer)
Dependency: logging, importlib, json, pathlib
Called by: Any component that needs dynamic module management (e.g., 05_Agent总控, 02_消息总线, etc.)
Problem solved: Provides a pluggable, configurable module loading/unloading/reloading mechanism with logging and exception recovery.
"""

import logging
import importlib
import importlib.util
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Set

class ModuleLoader:
    """模块加载器：支持可插拔的模块动态加载、卸载和热重载，配置化，带日志。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None):
        """
        初始化加载器。
        :param config: 直接传入的配置字典
        :param config_path: JSON配置文件路径，内容会自动合并到config
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.loaded_modules: Dict[str, Any] = {}  # module_name -> module_object
        self.module_info: Dict[str, Dict] = {}    # module_name -> metadata
        self.config = config if config else {}
        if config_path:
            self._load_config_from_file(config_path)
        # 可配置的模块搜索目录
        self.module_dirs = self.config.get('module_dirs', [])
        self.enabled_modules: Set[str] = set(self.config.get('enabled_modules', []))
        self.logger.info("ModuleLoader initialized.")

    def _load_config_from_file(self, config_path: str):
        """从 JSON 文件读取配置并更新。"""
        path = Path(config_path)
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
            self.config.update(file_config)
            self.logger.info(f"Loaded config from {config_path}")
        else:
            self.logger.warning(f"Config file not found: {config_path}")

    def add_module_dir(self, directory: str):
        """动态添加模块搜索路径。"""
        if directory not in self.module_dirs:
            self.module_dirs.append(directory)
            if directory not in sys.path:
                sys.path.insert(0, directory)
            self.logger.info(f"Added module directory: {directory}")

    def load_module(self, module_name: str, package: Optional[str] = None, force_reload: bool = False) -> Any: