"""Token监控模块
属于：27_日志监控/Token监控
依赖：配置系统、日志系统
被调用：Runtime层、Agent层（上报token使用）、监控面板
解决：实时/准实时监控模型调用的token消耗，支持超限报警、统计展示
"""
import logging
import threading
import time
from typing import Dict, List, Optional, Callable, Any

from utils.config_loader import get_config  # 假设配置加载模块
from utils.logging_config import get_logger  # 假设日志配置模块


class TokenUsageRecord:
    """单次token使用记录"""
    def __init__(self, timestamp: float, model: str, prompt_tokens: int, completion_tokens: int, total_tokens: int, metadata: Optional[Dict] = None):
        self.timestamp = timestamp
        self.model = model
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.metadata = metadata or {}


class TokenMonitor:
    """Token监控器(可插拔组件)"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config_section: str = "token_monitor"):
        """
        初始化监控器 (仅首次创建时执行)
        :param config_section: 配置节名称
        """
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True

        self.logger = get_logger("TokenMonitor")
        self.config = get_config().get(config_section, {})

        # 监控参数
        self.enabled = self.config.get("enabled", True)
        self.window_seconds = self.config.get("window_seconds", 60)          # 滑动窗口大小(秒)
        self.max_total_tokens = self.config.get("max_total_tokens", 1000000) # 窗口内总量阈值
        self.max_requests = self.config.get("max_requests", 1000)           # 窗口内请求数阈值
        self.alarm_callback: Optional[Callable[[str], None]] = None          # 报警回调
        self.record_keep_limit = self.config.get("record_keep_limit", 10000) # 最大记录数

        # 内部状态
        self._records: List[TokenUsageRecord] = []
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None

        self.logger.info("TokenMonitor initialized (enabled=%s)", self.enabled)

    def set_alarm_callback(self, callback: Callable[[str], None]):
        """设置报警回调函数"""
        self.alarm_callback = callback

    def start(self):
        """启动后台监控线程"""
        if not self.enabled:
            self.logger.info("TokenMonitor is disabled, skipping start.")
            return
        if self._monitor_thread and self._monitor_thread.is_alive():
            self.logger.warning("TokenMonitor already running.")
            return
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self.logger.info("TokenMonitor started.")

    def stop(self):
        """停止监控线程"""
        if self._monitor_thread:
            self._stop_event.set()
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None
            self.logger.info("TokenMonitor stopped.")

    def record_usage(self, model: str, prompt_tokens: int, completion_tokens: int, metadata: Optional[Dict] = None):
        """
        记录一次token使用
        :param model: 模型名称
        :param prompt_tokens: 提示token数
        :param completion_tokens: 生成token数
        :param metadata: 额外信息
        """
        if not self.enabled:
            return
        total = prompt_tokens + completion_tokens
        record = TokenUsageRecord(
            timestamp=time.time(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            metadata=metadata
        )
        with self._lock:
            self._records.append(record)
            if len(self._records) > self.record_keep_limit:
                self._records = self._records[-self.record_keep_limit:]   # 只保留最近记录
        self.logger.debug("Token recorded: model=%s, total=%d", model, total)

    def get_current_usage(self) -> Dict[str, Any]:
        """
        获取当前窗口内的统计信息
        :return: 包含 total_tokens, request_count, per_model_stats 的字典
        """
        now = time.time()
        window_start = now - self.window_seconds
        with self._lock:
            # 过滤窗口内记录
            window_records = [r for r in self._records if r.timestamp >= window_start]
            total_tokens = sum(r.total_tokens for r in window_records)
            request_count = len(window_records)
            # 按模型聚合
            per_model = {}
            for r in window_records:
                if r.model not in per_model:
                    per_model[r.model] = {"total_tokens": 0, "request_count": 0}
                per_model[r.model]["total_tokens"] += r.total_tokens
                per_model[r.model]["request_count"] += 1

        return {
            "window_seconds": self.window_seconds,
            "total_tokens": total_tokens,
            "request_count": request_count,
            "max_total_tokens": self.max_total_tokens,
            "max_requests": self.max_requests,
            "per_model": per_model
        }

    def _monitor_loop(self):
        """后台监控循环，定时检查阈值"""
        check_interval = self.config.get("check_interval", 10)  # 检查间隔（秒）
        while not self._stop_event.wait(check_interval):
            try:
                stats = self.get_current_usage()
                if stats["total_tokens"] >= self.max_total_tokens or stats["request_count"] >= self.max_requests:
                    alarm_msg = (
                        f"Token usage exceeded threshold! "
                        f"Total tokens: {stats['total_tokens']}/{self.max_total_tokens}, "
                        f"Requests: {stats['request_count']}/{self.max_requests}"
                    )
                    self.logger.warning(alarm_msg)
                    if self.alarm_callback:
                        try:
                            self.alarm_callback(alarm_msg)
                        except Exception as e:
                            self.logger.error("Alarm callback error: %s", e)
            except Exception as e:
                self.logger.error("Monitor loop error: %s", e)

    def reset_statistics(self):
        """清空历史记录 (谨慎使用)"""
        with self._lock:
            self._records.clear()
        self.logger.info("Token statistics reset.")

    def shutdown(self):
        """关闭监控器，释放资源"""
        self.stop()
        self.logger.info("TokenMonitor shutdown complete.")


# ---------- 自测 ----------
if __name__ == "__main__":
    # 简单自测，需要配置环境或有模拟配置
    class MockConfig:
        @staticmethod
        def get(section, default=None):
            return {
                "enabled": True,
                "window_seconds": 30,
                "max_total_tokens": 1000,
                "max_requests": 50,
                "check_interval": 5,
                "record_keep_limit": 100
            }
    # 替换真实的配置加载（模拟）
    import builtins
    # 简单模拟
    import logging
    logging.basicConfig(level=logging.DEBUG)
    # 假设get_config返回MockConfig
    def mock_get_config():
        return MockConfig()
    # 注入
    import utils.config_loader as cl
    cl.get_config = mock_get_config
    import utils.logging_config as lc
    lc.get_logger = logging.getLogger

    monitor = TokenMonitor()
    monitor.set_alarm_callback(lambda msg: print("ALARM:", msg))
    monitor.start()

    # 模拟一些使用
    for i in range(60):
        monitor.record_usage("gpt-4", prompt_tokens=20, completion_tokens=10)
        time.sleep(0.5)
    # 查看统计
    stats = monitor.get_current_usage()
    print("Current stats:", stats)

    monitor.stop()
    monitor.shutdown()