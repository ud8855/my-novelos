"""
NovelOS 生命周期启动模块
作用：系统入口，负责配置加载、日志初始化、模块生命周期管理、信号处理、优雅启停。
所属层级：00_启动入口
依赖：无（最低层依赖标准库）
被调用：直接由 Python 解释器启动
设计原则：可插拔、配置化、日志分级、异常恢复、自测试
"""

import sys
import os
import json
import logging
import signal
import threading
import time
from typing import Any, Callable, Dict, List, Optional

# --- 配置常量 ---
DEFAULT_CONFIG_PATH = "config.json"
DEFAULT_LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

class LifecycleLauncher:
    """
    生命周期启动器，负责系统的启停和模块挂载。
    所有子模块需实现 start() / stop() 接口以便自动管理。
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化启动器
        :param config_path: 配置文件路径，默认使用 DEFAULT_CONFIG_PATH
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config: Dict[str, Any] = {}
        self.modules: Dict[str, Any] = {}       # 已注册模块
        self._logger: Optional[logging.Logger] = None

        # 线程安全锁
        self._lock = threading.Lock()
        # 停止事件，用于通知所有线程优雅退出
        self._stop_event = threading.Event()

        # 注册默认信号处理
        self._register_signals()

    # ---------- 配置加载 ----------
    def load_config(self):
        """加载 JSON 配置文件，支持默认值。"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            print(f"[OK] 配置加载成功: {self.config_path}")
        except FileNotFoundError:
            print(f"[WARN] 配置文件未找到: {self.config_path}，使用空配置。")
            self.config = {}
        except json.JSONDecodeError as e:
            raise ValueError(f"配置文件格式错误: {e}")

    # ---------- 日志初始化 ----------
    def init_logging(self):
        """初始化根日志记录器，可扩展输出到文件等。"""
        log_level = self.config.get("log_level", "INFO").upper()
        level = getattr(logging, log_level, DEFAULT_LOG_LEVEL)

        log_format = self.config.get("log_format", LOG_FORMAT)
        date_format = self.config.get("date_format", DATE_FORMAT)

        logging.basicConfig(
            level=level,
            format=log_format,
            datefmt=date_format,
            stream=sys.stdout
        )
        self._logger = logging.getLogger("NovelOS")
        self._logger.info("日志系统初始化完成，级别: %s", log_level)

    @property
    def logger(self) -> logging.Logger:
        if self._logger is None:
            raise RuntimeError("日志系统尚未初始化，请先调用 init_logging()")
        return self._logger

    # ---------- 模块管理（可插拔） ----------
    def register_module(self, name: str, module: Any):
        """
        注册一个模块。模块必须实现 start() 和 stop() 方法（鸭子类型）。
        :param name: 模块唯一标识
        :param module: 模块实例
        """
        with self._lock:
            if name in self.modules:
                self.logger.warning("模块 %s 已存在，将被覆盖。", name)
            # 简单校验必要接口
            if not (hasattr(module, "start") and hasattr(module, "stop")):
                raise TypeError(f"模块 {name} 必须实现 start() 和 stop() 方法")
            self.modules[name] = module
            self.logger.info("模块已注册: %s", name)

    def unregister_module(self, name: str):
        """移除模块（如热插拔）"""
        with self._lock:
            if name in self.modules:
                del self.modules[name]
                self.logger.info("模块已移除: %s", name)
            else:
                self.logger.warning("模块 %s 不存在，无法移除。", name)

    # ---------- 生命周期方法 ----------
    def start(self):
        """
        系统启动：按顺序加载配置、初始化日志、启动所有已注册模块。
        """
        self.logger.info("=== NovelOS 正在启动 ===")
        self._stop_event.clear()

        # 启动所有模块（顺序启动）
        for name, module in self.modules.items():
            try:
                self.logger.info("启动模块: %s", name)
                module.start()
                self.logger.info("模块 %s 启动成功", name)
            except Exception as e:
                self.logger.error("模块 %s 启动失败: %s", name, str(e), exc_info=True)
                # 策略：可选择停止所有已启动模块并退出，或继续（根据配置）
                if self.config.get("stop_on_module_error", False):
                    self.shutdown()
                    sys.exit(1)

        self.logger.info("=== NovelOS 启动完成 ===")
        # 主线程挂起直到停止事件被触发（可由信号或外部调用）
        try:
            while not self._stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("接收到键盘中断")
            self.shutdown()

    def shutdown(self):
        """
        系统停止：通知所有模块退出，并逆序调用 stop()，最后清理资源。
        """
        if self._stop_event.is_set():
            self.logger.debug("系统已在停止流程中")
            return
        self.logger.info("=== NovelOS 正在关闭 ===")
        self._stop_event.set()

        # 逆序停止模块，保证依赖关系
        for name in reversed(list(self.modules.keys())):
            module = self.modules[name]
            try:
                self.logger.info("停止模块: %s", name)
                module.stop()
                self.logger.info("模块 %s 已停止", name)
            except Exception as e:
                self.logger.error("模块 %s 停止异常: %s", name, str(e), exc_info=True)

        self.logger.info("=== NovelOS 已关闭 ===")
        # 关闭日志处理器等
        logging.shutdown()

    # ---------- 信号处理 ----------
    def _register_signals(self):
        """注册系统信号，实现优雅退出。"""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """信号处理回调"""
        signame = signal.Signals(signum).name
        if self._logger:
            self._logger.info("接收到信号: %s，准备退出。", signame)
        else:
            print(f"接收到信号: {signame}，准备退出。")
        self.shutdown()

    # ---------- 自测试 ----------
    @staticmethod
    def _demo_module_factory(name: str):
        """生成一个简单的演示模块，用于自测"""
        class DemoModule:
            def __init__(self, name):
                self.name = name
            def start(self):
                print(f"[Demo] {self.name} 启动")
            def stop(self):
                print(f"[Demo] {self.name} 停止")
        return DemoModule(name)

    @classmethod
    def run_self_test(cls):
        """内置自测试：模拟完整启动-停止流程"""
        print("====== NovelOS 自测试开始 ======")
        launcher = cls("test_config.json")
        launcher.load_config()
        launcher.init_logging()

        # 注册两个演示模块
        launcher.register_module("demo1", cls._demo_module_factory("模块一"))
        launcher.register_module("demo2", cls._demo_module_factory("模块二"))

        # 在另一个线程中触发停止（模拟运行3秒后退出）
        def auto_stop():
            time.sleep(3)
            print("\n[自测] 自动触发停止...")
            launcher.shutdown()
        threading.Thread(target=auto_stop, daemon=True).start()

        # 启动（会阻塞直到 shutdown 被调用）
        launcher.start()
        print("====== NovelOS 自测试结束 ======")

if __name__ == "__main__":
    # 直接将此文件作为入口执行时进行自测
    LifecycleLauncher.run_self_test()