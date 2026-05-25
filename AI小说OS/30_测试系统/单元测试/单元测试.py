"""
30_测试系统/单元测试/单元测试.py
单元测试框架骨架
职责：提供可插拔、日志化、配置化的单元测试基础设施
依赖：Python标准库（unittest, logging, configparser等）
被调用：各模块单元测试文件
"""
import logging
import configparser
import unittest
import os
import sys
import importlib
import argparse
from typing import Optional, List

# ---------------------------
# 配置管理（配置化）
# ---------------------------
class UnitTestConfig:
    """单元测试配置管理类，支持外部配置文件覆盖默认值"""
    def __init__(self, config_path: Optional[str] = None):
        self.config = configparser.ConfigParser()
        # 默认配置项
        self.config['DEFAULT'] = {
            'log_level': 'INFO',
            'log_file': 'test_unit.log',
            'test_discover_path': os.path.dirname(os.path.abspath(__file__)),
            'pattern': 'test_*.py',
            'failfast': 'False',
            'verbosity': '2'
        }
        if config_path and os.path.exists(config_path):
            self.config.read(config_path, encoding='utf-8')
    
    def get(self, section: str = 'DEFAULT', option: str = 'log_level', fallback: Optional[str] = None) -> str:
        """获取配置项"""
        try:
            return self.config.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            if fallback is not None:
                return fallback
            return self.config['DEFAULT'].get(option, '')
    
    def getint(self, section: str = 'DEFAULT', option: str = 'verbosity', fallback: int = 2) -> int:
        """获取整数配置项"""
        try:
            return self.config.getint(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback
    
    def getboolean(self, section: str = 'DEFAULT', option: str = 'failfast', fallback: bool = False) -> bool:
        """获取布尔配置项"""
        try:
            return self.config.getboolean(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError, ValueError):
            return fallback

# ---------------------------
# 日志系统（日志化）
# ---------------------------
def setup_logging(config: Optional[UnitTestConfig] = None) -> logging.Logger:
    """
    根据配置初始化日志系统
    返回根日志记录器，同时输出到控制台和文件
    """
    if config is None:
        config = UnitTestConfig()
    log_level_str = config.get('DEFAULT', 'log_level', 'INFO')
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    log_file = config.get('DEFAULT', 'log_file', 'test_unit.log')
    
    # 确保日志目录存在
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # 根日志记录器配置
    logger = logging.getLogger()
    logger.setLevel(log_level)
    # 清除已有处理器（避免重复）
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # 文件处理器
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(log_level)
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    return logging.getLogger('UnitTest')

# ---------------------------
# 基础测试类（可插拔、异常恢复）
# ---------------------------
class UnitTestBase(unittest.TestCase):
    """
    单元测试基类
    提供：
    - 自动日志记录
    - 配置访问
    -