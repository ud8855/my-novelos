"""
移动端.py

模块说明：移动端UI界面层核心模块，提供移动端界面的抽象基类和实现工厂，
支持可插拔的移动端实现（如Flask Web App, Kivy App等）。
提供统一的启动、停止、热更新、异常恢复和日志记录功能。
所属层级：25_UI界面/移动端
依赖：15_配置中心（配置管理），20_日志中心（日志记录, 本地实现）
被调用：由主程序或上层调度器调用
"""

import logging
import os
import sys
import abc
from typing import Optional

# 默认配置模板（后续可从配置中心动态加载）
DEFAULT_CONFIG = {
    "host": "0.0.0.0",
    "port": 8080,
    "debug": True,
    "mobile_mode": "flask_web",  # 可选: flask_web, kivy, react_native
    "log_level": "INFO",
    "log_file": "logs/mobile.log"
}

class MobileUIBase(abc.ABC):
    """移动端UI抽象基类，所有移动端实现必须继承此类"""
    
    def __init__(self, config: dict = None):
        self.config = config if config else self._load_default_config()
        self.logger = self._setup_logger()
        self._running = False
    
    def _load_default_config(self) -> dict:
        """加载默认配置，并尝试从配置文件合并（热插拔设计）"""
        config = DEFAULT_CONFIG.copy()
        # 尝试从配置中心加载，如果不可用则使用本地默认配置
        try:
            from configs.mobile_config import MOBILE_CONFIG
            config.update(MOBILE_CONFIG)
        except ImportError:
            self.logger.warning("未找到外部配置文件，使用默认配置")
        return config

    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器，支持文件和控制台输出"""
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(getattr(logging, self.config.get("log_level", "INFO"), logging.INFO))
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # 控制台输出
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # 文件输出
        log_file = self.config.get("log_file", "mobile.log")
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        return logger

    @abc.abstractmethod
    def start(self):
        """启动移动端服务或应用"""
        pass

    @abc.abstractmethod
    def stop(self):
        """停止移动端服务或应用"""
        pass

    @abc.abstractmethod
    def reload(self):
        """热更新配置或代码（无需重启），必须实现"""
        pass

    def is_running(self) -> bool:
        """返回当前运行状态"""
        return self._running

    def handle_exception(self, exc: Exception):
        """统一异常处理与自动恢复记录"""
        self.logger.exception(f"发生异常，尝试恢复: {exc}")
        # 此处可添加扩展的恢复策略，例如重启服务

class FlaskWebMobile(MobileUIBase):
    """基于Flask的移动端Web App实现"""
    
    def start(self):
        self.logger.info("启动Flask移动端...")
        self._running = True
        # 实际启动代码：导入并运行Flask应用
        # from .flask_app import app
        # app.run(host=self.config["host"], port=self.config["port"])
        pass

    def stop(self):
        self.logger.info("停止Flask移动端...")
        self._running = False
        # 关闭服务器逻辑
        pass

    def reload(self):
        self.logger.info("热更新Flask移动端配置...")
        # 重新加载配置、重新导入模块等
        pass

class KivyMobile(MobileUIBase):
    """基于Kivy的移动端App实现"""
    
    def start(self):
        self.logger.info("启动Kivy移动端...")
        self._running = True
        # 实际启动代码
        pass

    def stop(self):
        self.logger.info("停止Kivy移动端...")
        self._running = False
        pass

    def reload(self):
        self.logger.info("热更新Kivy移动端配置...")
        pass

def create_mobile_ui(config: dict = None) -> MobileUIBase:
    """工厂函数：根据配置动态创建移动端实现，实现可插拔"""
    config = config if config else DEFAULT_CONFIG.copy()
    mode = config.get("mobile_mode", "fl