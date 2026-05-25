# -*- coding: utf-8 -*-
"""
系统内核 (System Kernel)
所属层级: 03_内核系统 (Kernel System)
依赖模块: None (直接依赖标准库，未来可注入配置管理器、插件管理器等)
被调用: 由主入口启动，管理整个生命期
解决问题: 提供可插拔的服务容器、模块生命周期管理、事件调度和日志记录
"""

import logging
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Any, Callable, List, Optional
from configparser import ConfigParser
import importlib
import importlib.util
import traceback

# 定义内核状态
KERNEL_STATES = {
    "UNINITIALIZED": 0,
    "STARTING": 1,
    "RUNNING": 2,
    "STOPPING": 3,
    "STOPPED": 4,
    "ERROR": -1
}

class Kernel:
    """
    NovelOS 系统内核
    职责: 插件加载、服务管理、事件循环、配置加载、日志记录
    可插拔: 通过接口注入配置加载器、插件管理器等
    """
    
    def __init__(self, config_path: Optional[str] = None, log_level: str = "INFO"):
        self._state = KERNEL_STATES["UNINITIALIZED"]
        self._services: Dict[str, Any] = {}        # 已注册的服务
        self._plugins: Dict[str, Any] = {}         # 已加载的插件模块
        self._event_handlers: Dict[str, List[Callable]] = {}  # 事件处理器
        self._config: ConfigParser = ConfigParser()
        self._logger = self._setup_logger(log_level)
        self._plugin_dirs: List[Path] = []
        self._event_queue = []  # 简单事件队列（生产环境可替换为线程安全队列）
        self._running = False
        
        # 加载配置
        if config_path:
            self.load_config(config_path)
    
    def _setup_logger(self, level: str) -> logging.Logger:
        """配置日志系统"""
        logger = logging.getLogger("NovelOS.Kernel")
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ 配置管理 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def load_config(self, path: str) -> bool:
        """从文件加载配置（支持.ini格式，未来可扩展yaml/json）"""
        try:
            self._config.read(path, encoding='utf-8')
            self._logger.info(f"Configuration loaded from {path}")
            return True
        except Exception as e:
            self._logger.error(f"Failed to load config: {e}")
            return False
    
    def get_config(self, section: str, key: str, fallback: Any = None) -> Any:
        """读取一个配置项"""
        return self._config.get(section, key, fallback=fallback)
    
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ 服务容器 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def register_service(self, name: str, service: Any) -> None:
        """注册一个服务（可插拔）"""
        self._services[name] = service
        self._logger.info(f"Service registered: {name}")
    
    def get_service(self, name: str) -> Optional[Any]:
        """获取已注册的服务"""
        return self._services.get(name)
    
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ 插件管理 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def set_plugin_directories(self, directories: List[str]) -> None:
        """设置插件扫描目录"""
        self._plugin_dirs = [Path(d) for d in directories]
        self._logger.info(f"Plugin directories set: {self._plugin_dirs}")
    
    def discover_plugins(self) -> None:
        """扫描插件目录，发现并加载有效插件模块"""
        for plugin_dir in self._plugin_dirs:
            if not plugin_dir.exists():
                self._logger.warning(f"Plugin directory does not exist: {plugin_dir}")
                continue
            for item in plugin_dir.iterdir():
                if item.is_dir() and (item / "__init__.py").exists():
                    self._load_plugin(item.name, item)
                elif item.suffix == ".py" and item.stem != "__init__":
                    self._load_plugin(item.stem, item)
    
    def _load_plugin(self, name: str, file_path: Path) -> None:
        """动态加载单个插件模块"""
        try:
            spec = importlib.util.spec_from_file_location(name, str(file_path))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # 检查插件是否实现了标准入口函数 setup(kernel)
            if hasattr(module, "setup"):
                module.setup(self)
                self._plugins[name] = module
                self._logger.info(f"Plugin loaded: {name} from {file_path}")
            else:
                self._logger.warning(f"Plugin {name} has no setup(kernel) function, ignored.")
        except Exception:
            self._logger.error(f"Failed to load plugin {name}: {traceback.format_exc()}")
    
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ 事件系统 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def register_event_handler(self, event_type: str, handler: Callable) -> None:
        """注册事件处理器"""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        self._logger.debug(f"Handler registered for event: {event_type}")
    
    def emit_event(self, event_type: str, data: Any = None) -> None:
        """发射事件，立即触发同步处理器（未来可扩展异步/队列）"""
        handlers = self._event_handlers.get(event_type, [])
        if not handlers:
            self._logger.debug(f"No handlers for event: {event_type}")
        for handler in handlers:
            try:
                handler(data)
            except Exception:
                self._logger.error(f"Error in event handler for {event_type}: {traceback.format_exc()}")
    
    def queue_event(self, event_type: str, data: Any = None) -> None:
        """将事件放入队列，由事件循环异步处理（简化版）"""
        self._event_queue.append((event_type, data))
        self._logger.debug(f"Event queued: {event_type}")
    
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ 生命周期 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def start(self) -> None:
        """启动内核：发现插件、启动事件循环、改变状态"""
        if self._state != KERNEL_STATES["UNINITIALIZED"]:
            self._logger.warning("Kernel already started or in invalid state.")
            return
        self._state = KERNEL_STATES["STARTING"]
        self._logger.info("Kernel starting...")
        # 发现插件
        self.discover_plugins()
        # 触发启动事件
        self.emit_event("kernel.start", self)
        # 启动事件处理循环（简化版，实际可为单独线程）
        self._running = True
        self._event_loop_thread = threading.Thread(target=self._event_loop, daemon=True)
        self._event_loop_thread.start()
        self._state = KERNEL_STATES["RUNNING"]
        self._logger.info("Kernel started.")
    
    def stop(self) -> None:
        """停止内核：触发停止事件、清理资源"""
        if self._state != KERNEL_STATES["RUNNING"]:
            self._logger.warning("Kernel not running.")
            return
        self._state = KERNEL_STATES["STOPPING"]
        self._logger.info("Kernel stopping...")
        self._running = False
        self.emit_event("kernel.stop", self)
        # 等待事件循环线程结束
        if hasattr(self, '_event_loop_thread') and self._event_loop_thread.is_alive():
            self._event_loop_thread.join(timeout=2)
        # 卸载插件
        for name, module in self._plugins.items():
            if hasattr(module, "teardown"):
                try:
                    module.teardown(self)
                    self._logger.info(f"Plugin {name} teardown completed.")
                except Exception:
                    self._logger.error(f"Error during plugin {name} teardown: {traceback.format_exc()}")
        self._plugins.clear()
        self._services.clear()
        self._event_handlers.clear()
        self._state = KERNEL_STATES["STOPPED"]
        self._logger.info("Kernel stopped.")
    
    def _event_loop(self) -> None:
        """简单的事件循环，从队列中取出事件并处理"""
        while self._running or self._event_queue:
            if not self._event_queue:
                time.sleep(0.1)
                continue
            event_type, data = self._event_queue.pop(0)
            self.emit_event(event_type, data)
    
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ 辅助 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    @property
    def state(self) -> str:
        """返回当前内核状态名称"""
        for name, val in KERNEL_STATES.items():
            if val == self._state:
                return name
        return "UNKNOWN"


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ 自测 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
if __name__ == "__main__":
    print("Running Kernel self-test...")
    kernel = Kernel(log_level="DEBUG")
    # 注册一个测试服务
    kernel.register_service("test_service", {"name": "dummy"})
    assert kernel.get_service("test_service") is not None
    
    # 注册事件处理器
    received_events = []
    def on_start(data):
        received_events.append("started")
    kernel.register_event_handler("kernel.start", on_start)
    
    # 启动内核
    kernel.start()
    time.sleep(0.5)
    # 检查事件是否触发
    assert "started" in received_events, "Start event not handled"
    print("Start event handled correctly.")
    
    # 队列一个测试事件
    kernel.queue_event("test.event", {"msg": "hello"})
    def on_test(data):
        print(f"Test event received: {data}")
    kernel.register_event_handler("test.event", on_test)
    time.sleep(0.5)
    
    # 停止内核
    kernel.stop()
    print("Kernel stopped. Self-test passed.")
    
    # 状态检查
    assert kernel.state == "STOPPED"
    print("All self-test assertions passed.")