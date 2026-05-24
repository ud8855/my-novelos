"""
插件隔离模块
- 提供插件运行环境的隔离能力，防止插件间相互干扰
- 支持可插拔的隔离策略（进程隔离 / 线程隔离 / 无隔离等）
- 隔离策略通过配置文件选择，实现热加载
- 包含完整的异常恢复、日志记录与自测用例
"""

import abc
import logging
import os
import sys
import threading
import multiprocessing
from typing import Any, Dict, Optional, Tuple, Type
from configparser import ConfigParser
from contextlib import contextmanager

# ───────────────────── 日志配置 ─────────────────────
logger = logging.getLogger('PluginIsolator')
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        '[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
    ))
    logger.addHandler(handler)

# ───────────────────── 配置管理 ─────────────────────
DEFAULT_CONFIG = {
    'isolation_mode': 'thread',  # 可选: process, thread, none
    'timeout_seconds': '30',
    'resource_limit': 'none',
    'keep_alive': 'false'
}

def load_config(config_path: Optional[str] = None) -> Dict[str, str]:
    """加载插件隔离配置，优先从文件，否则使用默认值"""
    config = DEFAULT_CONFIG.copy()
    if config_path and os.path.exists(config_path):
        parser = ConfigParser()
        parser.read(config_path, encoding='utf-8')
        if 'plugin_isolation' in parser:
            for key, value in parser.items('plugin_isolation'):
                config[key] = value
    return config

# ───────────────────── 隔离策略抽象基类 ─────────────────────
class BaseIsolator(abc.ABC):
    """隔离器基类，所有隔离策略必须实现该接口"""

    def __init__(self, config: Dict[str, str]):
        self.config = config
        self._validate_config()

    def _validate_config(self) -> None:
        """子类可覆写以实现自定义配置校验"""
        if not isinstance(self.config.get('timeout_seconds', '30'), str):
            raise ValueError('timeout_seconds must be string')

    @abc.abstractmethod
    def run_isolated(self, func: callable, *args, **kwargs) -> Any:
        """在隔离环境中执行传入的函数，并返回结果或抛出异常"""

    @abc.abstractmethod
    def stop(self) -> None:
        """终止隔离环境，释放资源"""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False

# ───────────────────── 无隔离策略（直接执行） ─────────────────────
class NoIsolation(BaseIsolator):
    """无隔离策略：直接在当前主线程执行，适用于测试或信任的插件"""

    def __init__(self, config: Dict[str, str]):
        super().__init__(config)
        logger.info("启用无隔离模式")

    def run_isolated(self, func: callable, *args, **kwargs) -> Any:
        logger.debug("NoIsolation 执行函数: %s", func.__name__)
        return func(*args, **kwargs)

    def stop(self) -> None:
        logger.debug("NoIsolation 停止（无需操作）")

# ───────────────────── 线程隔离策略 ─────────────────────
class ThreadIsolation(BaseIsolator):
    """线程隔离策略：在新线程中执行，可设置超时，共享内存空间但保证调用栈独立"""

    def __init__(self, config: Dict[str, str]):
        super().__init__(config)
        try:
            self.timeout = float(config.get('timeout_seconds', '30'))
        except ValueError:
            self.timeout = 30.0
        self._results: Dict[str, Any] = {}
        self._thread: Optional[threading.Thread] = None
        logger.info("启用线程隔离模式，超时时间 %.1f 秒", self.timeout)

    def _runner(self, func, args, kwargs, result_key: str):
        try:
            self._results[result_key] = func(*args, **kwargs)
        except Exception as e:
            self._results[result_key] = e

    def run_isolated(self, func: callable, *args, **kwargs) -> Any:
        import uuid
        key = str(uuid.uuid4())
        self._thread = threading.Thread(
            target=self._runner,
            args=(func, args, kwargs, key),
            name=f"IsolatedThread-{func.__name__}"
        )
        self._thread.start()
        self._thread.join(timeout=self.timeout)
        if self._thread.is_alive():
            logger.error("函数 %s 执行超时，无法在线程内强制终止", func.__name__)
            raise TimeoutError(f"Function {func.__name__} timed out after {self.timeout}s")
        result = self._results.pop(key, None)
        if isinstance(result, Exception):
            logger.error("隔离线程内发生异常: %s", result)
            raise result
        return result

    def stop(self) -> None:
        logger.debug("线程隔离停止（无法强制杀死线程，仅清理资源）")
        self._results.clear()

# ───────────────────── 进程隔离策略 ─────────────────────
class ProcessIsolation(BaseIsolator):
    """进程隔离策略：使用独立进程运行插件，真正的资源与内存隔离，代价较高"""

    def __init__(self, config: Dict[str, str]):
        super().__init__(config)
        try:
            self.timeout = float(config.get('timeout_seconds', '30'))
        except ValueError:
            self.timeout = 30.0
        self._process: Optional[multiprocessing.Process] = None
        self._result_queue: multiprocessing.Queue = multiprocessing.Queue()
        self._event: multiprocessing.Event = multiprocessing.Event()
        logger.info("启用进程隔离模式，超时时间 %.1f 秒", self.timeout)

    def _worker(self, func, args, kwargs):
        try:
            result = func(*args, **kwargs)
            self._result_queue.put(('success', result))
        except Exception as e:
            # 为了将异常从子进程传递，序列化异常信息
            import traceback
            err_info = {
                'type': type(e).__name__,
                'message': str(e),
                'traceback': traceback.format_exc()
            }
            self._result_queue.put(('error', err_info))
        finally:
            self._event.set()  # 通知主进程可以向队列发送完成信号

    def run_isolated(self, func: callable, *args, **kwargs) -> Any:
        # 注意：传递的函数和参数必须可序列化
        if not callable(func):
            raise ValueError("第一个参数必须是可调用对象")
        self._process = multiprocessing.Process(
            target=self._worker,
            args=(func, args, kwargs),
            name=f"IsolatedProcess-{func.__name__}"
        )
        self._process.start()
        self._process.join(timeout=self.timeout)

        if self._process.is_alive():
            logger.error("进程隔离函数 %s 超时，强制终止进程", func.__name__)
            self._process.terminate()
            self._process.join()
            raise TimeoutError(f"Process isolated function {func.__name__} timed out")

        if self._result_queue.empty():
            raise RuntimeError("子进程未返回任何结果或异常")

        status, payload = self._result_queue.get()
        if status == 'error':
            err = payload
            logger.error("子进程异常: %s", err['message'])
            raise RuntimeError(f"Child process failed: {err['type']}: {err['message']}") from None
        return payload

    def stop(self) -> None:
        if self._process and self._process.is_alive():
            self._process.terminate()
            self._process.join()
        while not self._result_queue.empty():
            self._result_queue.get()
        logger.debug("进程隔离资源已释放")

# ───────────────────── 隔离器工厂 ─────────────────────
ISOLATORS: Dict[str, Type[BaseIsolator]] = {
    'none': NoIsolation,
    'thread': ThreadIsolation,
    'process': ProcessIsolation,
}

def create_isolator(config: Dict[str, str]) -> BaseIsolator:
    """根据配置创建对应的隔离器实例"""
    mode = config.get('isolation_mode', 'thread').lower()
    if mode not in ISOLATORS:
        logger.warning("未知隔离模式 '%s'，回退至线程隔离", mode)
        mode = 'thread'
    isolator_class = ISOLATORS[mode]
    return isolator_class(config)

# ───────────────────── 高层 API ─────────────────────
@contextmanager
def isolated_context(config_path: Optional[str] = None):
    """便捷上下文管理器：自动加载配置并创建隔离器"""
    config = load_config(config_path)
    isolator = create_isolator(config)
    try:
        yield isolator
    finally:
        isolator.stop()

def run_in_isolation(func: callable, *args, config_path: Optional[str] = None, **kwargs) -> Any:
    """一行式隔离执行函数"""
    with isolated_context(config_path) as isolator:
        return isolator.run_isolated(func, *args, **kwargs)

# ───────────────────── 自测 ─────────────────────
if __name__ == '__main__':
    print("====== 插件隔离模块自测开始 ======")

    # 1. 无隔离测试
    def hello(name):
        return f"Hello, {name}!"

    config_none = {'isolation_mode': 'none'}
    iso = NoIsolation(config_none)
    result = iso.run_isolated(hello, "World")
    assert result == "Hello, World!"
    print("无隔离测试通过:", result)

    # 2. 线程隔离测试
    def slow_add(a, b):
        import time
        time.sleep(0.1)
        return a + b

    config_thread = {'isolation_mode': 'thread', 'timeout_seconds': '3'}
    iso_thread = ThreadIsolation(config_thread)
    result = iso_thread.run_isolated(slow_add, 3, 5)
    assert result == 8
    print("线程隔离测试通过:", result)

    # 3. 线程超时测试
    def forever():
        import time
        time.sleep(10)

    try:
        iso_thread.run_isolated(forever)
        assert False, "应触发超时"
    except TimeoutError:
        print("线程超时测试通过")

    # 4. 进程隔离测试（如果平台支持）
    try:
        multiprocessing.set_start_method('spawn', force=True)
    except RuntimeError:
        pass

    config_proc = {'isolation_mode': 'process', 'timeout_seconds': '5'}
    iso_proc = ProcessIsolation(config_proc)
    result = iso_proc.run_isolated(slow_add, 10, 20)
    assert result == 30
    print("进程隔离测试通过:", result)

    # 5. 进程隔离异常传播测试
    def bad_func():
        raise ValueError("故意的错误")

    try:
        iso_proc.run_isolated(bad_func)
        assert False, "应抛出异常"
    except RuntimeError as e:
        print("进程异常传播测试通过:", e)

    # 6. 便捷 API 测试
    out = run_in