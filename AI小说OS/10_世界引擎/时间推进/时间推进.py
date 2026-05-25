# 时间推进模块
# 层：10_世界引擎/时间推进
# 依赖：无（或依赖配置管理模块）
# 被调用：世界引擎核心、故事事件系统
# 功能：管理小说世界的时间线，提供时间推进、暂停、变速、时间查询等基础能力，确保时间推进可插拔、可配置、可恢复。

import logging
import time
import threading
from typing import Optional, Dict, Any, Callable

class TimeAdvancer:
    """
    时间推进器，负责管理小说世界的时间状态。
    实现可插拔：通过继承此类并重写核心方法替换，或使用相同接口的其他实现。
    """
    
    # 默认配置值
    DEFAULT_TICK_INTERVAL = 1.0  # 现实秒
    DEFAULT_TIME_UNIT = "minute"
    DEFAULT_START_TIME = 0
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化时间推进器
        :param config: 配置字典，可包含 tick_interval, time_unit, start_time, log_level 等
        """
        self._config = config if config is not None else {}
        self._load_config()
        self._setup_logging()
        self.logger = logging.getLogger("TimeAdvancer")
        
        # 时间核心状态
        self.current_time: int = self._config.get("start_time", self.DEFAULT_START_TIME)
        self.time_unit: str = self._config.get("time_unit", self.DEFAULT_TIME_UNIT)
        self.tick_interval: float = self._config.get("tick_interval", self.DEFAULT_TICK_INTERVAL)
        
        # 运行控制
        self.is_running: bool = False
        self._lock = threading.Lock()
        self._timer_thread: Optional[threading.Thread] = None
        self._on_tick_callbacks: list[Callable[[int], None]] = []  # 时间变化回调
        
        self.logger.info("时间推进器初始化完成，当前时间: %d %s", self.current_time, self.time_unit)
    
    def _load_config(self):
        """从配置字典加载参数，可扩展为从文件读取"""
        # 此处预留配置校验和默认值合并逻辑
        pass
    
    def _setup_logging(self):
        """配置日志系统，支持从 config 获取日志级别"""
        log_level = self._config.get("log_level", logging.INFO)
        logging.basicConfig(level=log_level,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # ---- 核心操作 ----
    def start(self) -> bool:
        """开始自动时间推进（独立线程）"""
        with self._lock:
            if self.is_running:
                self.logger.warning("时间推进已处于运行状态")
                return False
            self.is_running = True
            self._timer_thread = threading.Thread(target=self._run_loop, daemon=True)
            self._timer_thread.start()
            self.logger.info("时间自动推进已启动，周期: %.2f 秒", self.tick_interval)
            return True
    
    def stop(self) -> bool:
        """停止自动时间推进"""
        with self._lock:
            if not self.is_running:
                self.logger.warning("时间推进未运行")
                return False
            self.is_running = False
            if self._timer_thread:
                self._timer_thread.join(timeout=2.0)
            self.logger.info("时间自动推进已停止")
            return True
    
    def _run_loop(self):
        """内部自动推进循环"""
        self.logger.debug("自动推进线程启动")
        while self.is_running:
            start_real = time.time()
            self.advance(1)  # 默认每次前进1个单位
            elapsed = time.time() - start_real
            sleep_time = max(0, self.tick_interval - elapsed)
            time.sleep(sleep_time)
        self.logger.debug("自动推进线程退出")
    
    def advance(self, amount: int = 1) -> int:
        """
        手动推进时间
        :param amount: 向前推进的单位数量（整数）
        :return: 推进后的当前时间
        """
        with self._lock:
            if amount < 1:
                self.logger.error("推进量必须为正整数")
                return self.current_time
            self.current_time += amount
            self.logger.debug("时间推进 %d 单位，当前时间: %d", amount, self.current_time)
            # 触发所有时间变化回调
            for callback in self._on_tick_callbacks:
                try:
                    callback(self.current_time)
                except Exception as e:
                    self.logger.error("时间变化回调执行异常: %s", e)
            return self.current_time
    
    # ---- 辅助控制 ----
    def set_speed(self, multiplier: float) -> None:
        """设置时间倍速（相对于真实时间）"""
        if multiplier <= 0:
            self.logger.error("倍速必须大于0")
            return
        with self._lock:
            self.tick_interval = 1.0 / multiplier
            self.logger.info("时间倍速调整为 %.2fX", multiplier)
    
    def pause(self) -> None:
        """暂停自动推进（等效于stop）"""
        self.stop()
    
    def resume(self) -> bool:
        """恢复自动推进（等效于start）"""
        return self.start()
    
    # ---- 状态查询 ----
    def get_current_time(self) -> int:
        """获取当前世界时间（与时间单位相关）"""
        return self.current_time
    
    def get_time_unit(self) -> str:
        """获取时间单位"""
        return self.time_unit
    
    def is_active(self) -> bool:
        """检查是否在自动推进中"""
        return self.is_running
    
    # ---- 扩展接口 ----
    def register_tick_callback(self, callback: Callable[[int], None]) -> None:
        """注册时间推进回调，每次时间变化时调用，传入当前时间"""
        self._on_tick_callbacks.append(callback)
        self.logger.debug("注册时间变化回调: %s", callback.__name__)
    
    def remove_tick_callback(self, callback: Callable[[int], None]) -> bool:
        """移除已注册的回调"""
        try:
            self._on_tick_callbacks.remove(callback)
            self.logger.debug("移除时间变化回调: %s", callback.__name__)
            return True
        except ValueError:
            return False
    
    # ---- 序列化与恢复 ----
    def get_state(self) -> Dict[str, Any]:
        """获取当前状态，用于保存/恢复"""
        return {
            "current_time": self.current_time,
            "time_unit": self.time_unit,
            "tick_interval": self.tick_interval,
            "is_running": self.is_running
        }
    
    def load_state(self, state: Dict[str, Any]) -> None:
        """从状态字典恢复"""
        with self._lock:
            self.current_time = state.get("current_time", self.current_time)
            self.time_unit = state.get("time_unit", self.time_unit)
            self.tick_interval = state.get("tick_interval", self.tick_interval)
            self.logger.info("时间推进器状态已恢复，当前时间: %d", self.current_time)
            if state.get("is_running", False) and not self.is_running:
                self.start()

# 自测代码
if __name__ == "__main__":
    # 基础功能测试
    print("=== 时间推进器自测 ===")
    
    advancer = TimeAdvancer(config={"tick_interval": 0.5, "start_time": 1000})
    
    # 手动推进
    advancer.advance(5)
    print(f"手动推进后时间: {advancer.get_current_time()}")
    
    # 注册回调
    def on_time_change(new_time):
        print(f"事件触发：时间变更至 {new_time}")
    advancer.register_tick_callback(on_time_change)
    
    # 测试自动推进3秒
    advancer.start()
    time.sleep(3)
    advancer.stop()
    
    print(f"自动推进后时间: {advancer.get_current_time()}")
    print("自测完成")