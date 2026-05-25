import importlib
import importlib.util
import logging
import threading
import time
import sys
import os
from typing import Dict, Optional, Any

# ============================================================
# 模块：03_内核系统/热更新
# 层：内核系统
# 功能：提供可插拔的模块热更新能力，监视指定目录/文件，
#       当文件变更时自动重新加载对应模块。
# 依赖：Python标准库 (importlib, logging, threading)
# 被调用：由运行时调度器、Agent管理器等内核组件调用。
# ============================================================

# ----------------- 配置管理 -----------------
class HotUpdateConfig:
    """热更新配置类，默认从字典或配置文件加载。
    未来可扩展为读取json/yaml。"""
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        # 默认配置
        self.watch_paths: list = config_dict.get("watch_paths", []) if config_dict else []
        self.watch_extensions: tuple = (".py",)
        self.poll_interval: float = config_dict.get("poll_interval", 1.0) if config_dict else 1.0
        self.enabled: bool = config_dict.get("enabled", True) if config_dict else True

    @classmethod
    def from_file(cls, filepath: str) -> 'HotUpdateConfig':
        """从JSON配置文件加载（未来实现）"""
        # 示例：读取json
        # with open(filepath, 'r') as f:
        #     data = json.load(f)
        # return cls(data)
        return cls()  # 暂时返回默认


# ----------------- 日志设置 -----------------
def _setup_logger(name: str = "HotUpdate") -> logging.Logger:
    """配置并返回模块专用日志记录器"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)  # 初期可用DEBUG级别，后续可配置化
    return logger


logger = _setup_logger()


# ----------------- 核心热更新管理器 -----------------
class HotReloadManager:
    """
    热更新管理器：负责跟踪模块、检测文件改动并执行重载。
    特性：可插拔、配置化、日志记录、异常隔离。
    接口：start() / stop() / add_watch_path()
    """

    def __init__(self, config: HotUpdateConfig):
        self.config = config
        self._watch_paths = set(config.watch_paths)
        # 记录已跟踪模块：name -> (module_object, file_path, last_mtime)
        self._tracked_modules: Dict[str, tuple] = {}
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        logger.info("热更新管理器初始化完成，监视路径：%s", self._watch_paths)

    # --- 公共接口 ---
    def add_watch_path(self, path: str):
        """动态添加新监视路径（可插拔特性）"""
        if os.path.isdir(path) or os.path.isfile(path):
            self._watch_paths.add(path)
            logger.info("添加监视路径: %s", path)
        else:
            logger.warning("无效路径，忽略: %s", path)

    def remove_watch_path(self, path: str):
        """动态移除监视路径"""
        self._watch_paths.discard(path)
        logger.info("移除监视路径: %s", path)

    def start(self):
        """启动后台监视线程"""
        if not self.config.enabled:
            logger.info("热更新功能已禁用，跳过启动")
            return
        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("热更新监视线程已在运行中")
            return
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="HotReloadMonitor",
            daemon=True
        )
        self._monitor_thread.start()
        logger.info("热更新监视线程已启动")

    def stop(self, timeout: float = 5.0):
        """停止监视线程"""
        if not self._monitor_thread or not self._monitor_thread.is_alive():
            logger.info("没有运行中的监视线程")
            return
        self._stop_event.set()
        self._monitor_thread.join(timeout)
        logger.info("热更新监视线程已停止")

    def load_module(self, module_name: str, file_path: str):
        """
        动态加载一个模块并开始跟踪。
        module_name: 模块全限定名（如 'agents.plot_designer'）
        file_path: 对应的.py文件绝对路径
        """
        file_path = os.path.abspath(file_path)
        if module_name in self._tracked_modules:
            logger.debug("模块 %s 已在跟踪中", module_name)
            return

        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"无法为 {file_path} 创建模块规格")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # 同时加入 sys.modules，保证未来 import 使用最新
            sys.modules[module_name] = module
            mtime = os.path.getmtime(file_path)

            with self._lock:
                self._tracked_modules[module_name] = (module, file_path, mtime)
            logger.info("成功加载并跟踪模块: %s 来自 %s", module_name, file_path)
        except Exception as e:
            logger.error("无法加载模块 %s: %s", module_name, e)
            raise

    def reload_module(self, module_name: str):
        """
        重新加载已跟踪的模块。
        实现方式：直接从文件重新执行，替换模块对象。
        """
        with self._lock:
            if module_name not in self._tracked_modules:
                logger.warning("模块 %s 未被跟踪，无法热更新", module_name)
                return False
            _, file_path, _ = self._tracked_modules[module_name]

        logger.info("开始热更新模块: %s", module_name)
        try:
            # 重新加载模块对象，使用importlib.reload会造成引用更新问题，此处采用新建方式
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"无法为 {file_path} 创建规格")
            new_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(new_module)
            # 替换 sys.modules 中的旧模块
            old_module = sys.modules.get(module_name)
            sys.modules[module_name] = new_module

            # 更新内部跟踪
            mtime = os.path.getmtime(file_path)
            with self._lock:
                self._tracked_modules[module_name] = (new_module, file_path, mtime)
            logger.info("模块 %s 热更新成功", module_name)
            # 通知其他组件？预留钩子
            return True
        except Exception as e:
            logger.error("模块 %s 热更新失败: %s", module_name, e, exc_info=True)
            return False

    # --- 内部监视逻辑 ---
    def _find_module_by_path(self, file_path: str) -> Optional[str]:
        """根据文件路径查找已追踪的模块名"""
        with self._lock:
            for name, (_, fpath, _) in self._tracked_modules.items():
                if os.path.abspath(fpath) == os.path.abspath(file_path):
                    return name
        return None

    def _scan_files(self):
        """
        扫描所有监视路径下的文件，返回 (绝对路径, 最后修改时间) 列表。
        支持目录递归，只检查指定扩展名的文件。
        """
        files_to_check = []
        for wpath in self._watch_paths:
            if not os.path.exists(wpath):
                continue
            if os.path.isfile(wpath):
                if wpath.endswith(self.config.watch_extensions):
                    files_to_check.append(wpath)
            elif os.path.isdir(wpath):
                for root, _, filenames in os.walk(wpath):
                    for fname in filenames:
                        if fname.endswith(self.config.watch_extensions):
                            files_to_check.append(os.path.join(root, fname))
        result = []
        for f in files_to_check:
            try:
                result.append((f, os.path.getmtime(f)))
            except OSError:
                continue
        return result

    def _monitor_loop(self):
        """后台监视主循环，周期性检查文件变化"""
        logger.debug("监视循环开始")
        while not self._stop_event.is_set():
            # 收集当前监视到的所有文件
            current_files = self._scan_files()
            # 建立文件路径->mtime的映射
            file_mtimes = {f: mtime for f, mtime in current_files}

            # 检查已追踪的文件是否有变化
            with self._lock:
                tracked_items = list(self._tracked_modules.items())

            for module_name, (_, file_path, last_mtime) in tracked_items:
                abs_file_path = os.path.abspath(file_path)
                if abs_file_path in file_mtimes:
                    new_mtime = file_mtimes[abs_file_path]
                    if new_mtime > last_mtime:
                        logger.info("检测到文件变化: %s (模块 %s)", abs_file_path, module_name)
                        self.reload_module(module_name)

            # 对于新出现的文件，如果有需要自动加载的策略，可以在此