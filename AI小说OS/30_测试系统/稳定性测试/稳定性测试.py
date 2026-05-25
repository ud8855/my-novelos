# -*- coding: utf-8 -*-
"""
稳定性测试模块 (Stability Test)
模块路径: 30_测试系统/稳定性测试/稳定性测试.py
层级: 30_测试系统 (系统级测试)
依赖: 标准库, 可选的项目配置模块
被调用: 由测试调度器、CI/CD 流水线或平台监控模块调用
解决问题: 对 NovelOS 核心服务进行长期稳定性测试，包含：
    - 长时间运行下的内存/句柄泄漏检测
    - 高频并发调用的死锁和竞态条件暴露
    - 异常自动恢复能力验证
    - 关键性能指标的退化监测
"""

import logging
import time
import signal
import sys
import threading
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable

# --------------------------- 配置管理尝试 ---------------------------
try:
    from utils.config_manager import ConfigManager  # 假设存在全局配置工具
except ImportError:
    ConfigManager = None

# --------------------------- 日志初始化 ---------------------------
logger = logging.getLogger("StabilityTest")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '[%(asctime)s][%(name)s][%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)


@dataclass
class StabilityTestConfig:
    """
    稳定性测试配置 (可被外部配置文件覆盖)
    """
    # 测试总时长（秒），0 表示永久运行直到手动停止
    duration_seconds: int = 3600
    # 并发模拟用户数
    concurrent_users: int = 10
    # 单个操作超时阈值（秒）
    operation_timeout: float = 30.0
    # 内存增长报警阈值（MB/小时），0 表示不检查
    memory_growth_threshold_mb_per_hour: float = 50.0
    # 是否在失败时收集详细堆栈
    collect_full_traceback: bool = True
    # 结果报告路径
    report_path: str = "logs/stability_report.json"
    # 自定义参数（由子测试传递）
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StabilityTestConfig":
        """从字典创建配置"""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> Dict[str, Any]:
        """转为字典用于报告"""
        return self.__dict__.copy()


class StabilityTestBase(ABC):
    """
    稳定性测试抽象基类
    所有稳定性测试用例必须继承此类并实现抽象方法。
    保证可插拔：外部只需实例化子类并调用 run_stability_suite()
    """
    def __init__(self, config: Optional[StabilityTestConfig] = None):
        self.config = config or StabilityTestConfig()
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._failed = False
        self._error_message: Optional[str] = None
        self._metrics: Dict[str, List[float]] = {}  # 指标名 -> 时间序列

        # 注册信号处理，以便优雅退出
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("稳定性测试实例初始化完成，配置: %s", self.config.to_dict())

    def _signal_handler(self, signum, frame):
        """信号处理器：收到终止信号时停止测试"""
        logger.warning("收到信号 %s，准备停止稳定性测试...", signum)
        self._stop_event.set()

    @abstractmethod
    def setup(self) -> bool:
        """
        测试前置准备（创建资源、启动服务等）
        返回 True 表示准备成功，否则 False
        """
        pass

    @abstractmethod
    def teardown(self):
        """测试后清理资源"""
        pass

    @abstractmethod
    def execute_operation(self, user_id: int) -> bool:
        """
        执行单次业务操作（模拟用户行为）
        user_id: 模拟的用户标识
        返回操作是否成功
        """
        pass

    @abstractmethod
    def collect_metrics(self) -> Dict[str, float]:
        """
        收集当前系统指标（内存、CPU、句柄数等）
        返回指标字典
        """
        pass

    def _monitor_loop(self):
        """后台监控线程：周期采集指标并检测异常"""
        logger.info("后台指标监控线程启动")
        while not self._stop_event.is_set():
            try:
                metrics = self.collect_metrics()
                timestamp = time.time()
                for key, value in metrics.items():
                    if key not in self._metrics:
                        self._metrics[key] = []
                    self._metrics[key].append(value)
                # 内存增长检测
                if self.config.memory_growth_threshold_mb_per_hour > 0:
                    self._check_memory_growth()
            except Exception as e:
                logger.error("指标采集异常: %s", traceback.format_exc())
            time.sleep(5)  # 采集间隔
        logger.info("后台指标监控线程结束")

    def _check_memory_growth(self):
        """检查内存增长是否超过阈值（简化示例）"""
        # 实际需实现更精确的线性回归，此处仅为骨架
        if "rss_mb" in self._metrics and len(self._metrics["rss_mb"]) > 2:
            recent = self._metrics["rss_mb"][-10:]  # 最近10个点
            if len(recent) >= 2:
                growth = (recent[-1] - recent[0]) / len(recent) * 720  # 粗略估算每小时增长
                if growth > self.config.memory_growth_threshold_mb_per_hour:
                    logger.error("内存增长过快: %.2f MB/h，超过阈值 %.2f", growth, self.config.memory_growth_threshold_mb_per_hour)
                    self._failed = True
                    self._error_message = f"Memory growth exceeded: {growth:.2f} MB/h"

    def _worker(self, user_id: int):
        """单个模拟用户的执行循环"""
        logger.debug("用户 %d 开始执行", user_id)
        while not self._stop_event.is_set():
            try:
                start = time.monotonic()
                success = self.execute_operation(user_id)
                elapsed = time.monotonic() - start
                if not success:
                    logger.error("用户 %d 操作失败", user_id)
                    self._failed = True
                    self._error_message = f"User {user_id} operation failed"
                if elapsed > self.config.operation_timeout:
                    logger.warning("用户 %d 操作超时: %.2fs", user_id, elapsed)
            except Exception as e:
                logger.error("用户 %d 异常: %s", user_id, traceback.format_exc() if self.config.collect_full_traceback else str(e))
                self._failed = True
                self._error_message = f"User {user_id} exception: {e}"
            time.sleep(1)  # 操作间隔

    def run_stability_suite(self) -> bool:
        """
        启动稳定性测试套件（主入口）
        返回 True 表示测试通过（未发现稳定性问题），False 表示发现问题
        """
        logger.info("====== 稳定性测试启动 ======")
        if not self.setup():
            logger.error("测试前置准备失败，终止测试")
            return False

        # 启动指标监控线程
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

        # 启动并发用户线程
        user_threads = []
        for uid in range(self.config.concurrent_users):
            t = threading.Thread(target=self._worker, args=(uid,), daemon=True)
            t.start()
            user_threads.append(t)

        # 等待测试结束（时长到或手动停止）
        deadline = time.time() + self.config.duration_seconds if self.config.duration_seconds > 0 else float('inf')
        while time.time() < deadline and not self._stop_event.is_set():
            time.sleep(1)
        self._stop_event.set()  # 通知所有线程结束

        # 等待所有线程退出
        for t in user_threads:
            t.join(timeout=5)
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)

        # 执行清理
        self.teardown()

        # 生成报告
        self._generate_report()

        if self._failed:
            logger.error("稳定性测试失败: %s", self._error_message)
        else:
            logger.info("稳定性测试通过")
        return not self._failed

    def _generate_report(self):
        """生成测试报告（骨架）"""
        import json
        report = {
            "test_name": self.__class__.__name__,
            "config": self.config.to_dict(),
            "passed": not self._failed,
            "error": self._error_message,
            "metrics_keys": list(self._metrics.keys()),
            "metrics_summary": {
                key: {
                    "min": min(vals) if vals else None,
                    "max": max(vals) if vals else None,
                    "avg": sum(vals)/len(vals) if vals else None
                } for key, vals in self._metrics.items()
            },
        }
        try:
            with open(self.config.report_path, 'w') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info("测试报告已保存至: %s", self.config.report_path)
        except Exception as e:
            logger.error("保存报告失败: %s", e)

# --------------------------- 自测桩 ---------------------------
class _DummyStabilityTest(StabilityTestBase):
    """
    用于自测的简单实现，模拟内存泄漏场景
    """
    def setup(self) -> bool:
        logger.info("自测桩: setup")
        return True

    def teardown(self):
        logger.info("自测桩: teardown")

    def execute_operation(self, user_id: int) -> bool:
        # 模拟逐渐增加的内存占用
        global _dummy_memory
        _dummy_memory.append("x" * 1024 * 10)  # 每次增加10KB
        return True

    def collect_metrics(self) -> Dict[str, float