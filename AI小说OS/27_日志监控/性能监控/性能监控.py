"""性能监控模块 - Performance Monitor
提供系统性能指标采集、记录和监控能力。
支持自定义指标、装饰器、上下文管理器。
可插拔：通过配置启用/禁用。
配置化：从配置文件或环境变量读取参数。
日志记录：所有监控数据统一记录。
"""

import time
import threading
import logging
import functools
from typing import Callable, Dict, Any, Optional, List
from pathlib import Path

# 模块级日志器
logger = logging.getLogger("PerformanceMonitor")


class PerformanceMonitor:
    """性能监控器（单例模式）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # 防止重复初始化
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self.config = {
            "enabled": True,
            "sampling_interval": 5,      # 采样间隔（秒）
            "record_to_log": True,
            "metrics": ["cpu", "memory", "elapsed"],
            "custom_metrics": {},
        }
        if config:
            self.config.update(config)

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._metrics_data: Dict[str, List[Dict[str, Any]]] = {
            "cpu": [],
            "memory": [],
            "elapsed": []
        }
        self._custom_metrics: Dict[str, Callable[[], Any]] = {}

    # ---- 管理 ----
    def start(self):
        """启动后台监控线程"""
        if not self.config["enabled"]:
            logger.info("性能监控未启用")
            return
        if self._running:
            logger.warning("性能监控已在运行")
            return
        logger.info("启动性能监控")
        self._running = True
        self._thread = threading.Thread(target=self._sampling_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止后台监控线程"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("性能监控已停止")

    def _sampling_loop(self):
        """采样循环"""
        while self._running:
            self.collect_metrics()
            time.sleep(self.config["sampling_interval"])

    def collect_metrics(self):
        """采集所有启用的指标并记录"""
        enabled_metrics = self.config.get("metrics", [])
        for metric_name in enabled_metrics:
            if metric_name == "cpu":
                self._record_cpu()
            elif metric_name == "memory":
                self._record_memory()
            elif metric_name == "elapsed":
                # elapsed 不采背景采，由装饰器/上下文触发
                continue
            else:
                # 检查自定义指标
                if metric_name in self._custom_metrics:
                    try:
                        value = self._custom_metrics[metric_name]()
                        self._metrics_data.setdefault(metric_name, []).append({
                            "timestamp": time.time(),
                            "value": value
                        })
                        if self.config["record_to_log"]:
                            logger.debug(f"自定义指标 [{metric_name}]: {value}")
                    except Exception as e:
                        logger.error(f"采集自定义指标 [{metric_name}] 失败: {e}")

    def _record_cpu(self):
        """记录CPU使用率（骨架不依赖psutil，使用空实现）"""
        # 实际集成时替换为 psutil.cpu_percent()
        value = 0.0
        self._metrics_data["cpu"].append({
            "timestamp": time.time(),
            "percent": value
        })
        if self.config["record_to_log"]:
            logger.debug(f"CPU: {value}%")

    def _record_memory(self):
        """记录内存使用率（骨架不依赖psutil，使用空实现）"""
        # 实际集成时替换为 psutil.virtual_memory().percent
        value = 0.0
        self._metrics_data["memory"].append({
            "timestamp": time.time(),
            "percent": value
        })
        if self.config["record_to_log"]:
            logger.debug(f"Memory: {value}%")

    def register_custom_metric(self, name: str, collect_func: Callable[[], Any]):
        """注册自定义指标采集函数"""
        self._custom_metrics[name] = collect_func
        # 确保相应存储存在
        if name not in self._metrics_data:
            self._metrics_data[name] = []
        logger.info(f"注册自定义性能指标: {name}")

    # ---- 装饰器/上下文 ----
    def monitor(self, name: Optional[str] = None):
        """函数执行时间监测装饰器"""
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                nonlocal name
                metric_name = name or func.__name__
                start_time = time.time()
                result = func(*args, **kwargs)
                elapsed = time.time() - start_time
                self._metrics_data["elapsed"].append({
                    "timestamp": start_time,
                    "function": metric_name,
                    "elapsed": elapsed
                })
                if self.config["record_to_log"]:
                    logger.info(f"性能监测 [{metric_name}]: {elapsed:.4f}s")
                return result
            return wrapper
        return decorator

    def measure(self, name: Optional[str] = None):
        """上下文管理器用于测量代码块的执行时间"""
        class TimerContext:
            def __init__(self, monitor_instance, block_name):
                self.monitor = monitor_instance
                self.block_name = block_name or "unnamed_block"
                self.start = None

            def __enter__(self):
                self.start = time.time()
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                elapsed = time.time() - self.start
                self.monitor._metrics_data["elapsed"].append({
                    "timestamp": self.start,
                    "function": self.block_name,
                    "elapsed": elapsed
                })
                if self.monitor.config["record_to_log"]:
                    logger.info(f"性能监测 [{self.block_name}]: {elapsed:.4f}s")
                return False  # 不抑制异常

        return TimerContext(self, name)

    # ---- 数据访问 ----
    def get_metrics(self, metric_name: str, last_n: int = 10) -> List[Dict]:
        """获取指定指标的最近数据"""
        data = self._metrics_data.get(metric_name, [])
        return data[-last_n:]

    def get_average(self, metric_name: str, key: str = "elapsed") -> float:
        """计算指定指标的平均值（适用于内部有数值的记录）"""
        data = self._metrics_data.get(metric_name, [])
        if not data:
            return 0.0
        values = [entry.get(key, 0.0) for entry in data]
        return sum(values) / len(values)

    def reset_metrics(self, metric_name: Optional[str] = None):
        """清空指标数据"""
        if metric_name:
            self._metrics_data[metric_name] = []
        else:
            for k in self._metrics_data:
                self._metrics_data[k] = []


# 模块级便捷实例
_perf_monitor = PerformanceMonitor()


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    return _perf_monitor


if __name__ == "__main__":
    # 自测代码
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    print("性能监控模块自测开始...")
    monitor = get_performance_monitor()

    # 测试装饰器
    @monitor.monitor(name="test_func")
    def test_func(delay=0.1):
        time.sleep(delay)

    test_func(0.2)
    print("elapsed data:", monitor.get_metrics("elapsed"))

    # 测试上下文管理器
    with monitor.measure("test_block"):
        time.sleep(0.3)

    print("elapsed data after block:", monitor.get_metrics("elapsed"))

    # 测试注册自定义指标
    monitor.register_custom_metric("dummy", lambda: 42)
    monitor.collect_metrics()
    print("dummy data:", monitor.get_metrics("dummy"))

    # 测试启动后台采样（短时间内）
    monitor.config["sampling_interval"] = 1
    monitor.start()
    time.sleep(2.1)
    monitor.stop()
    print("cpu samples:", monitor.get_metrics("cpu"))

    print("自测完成。")