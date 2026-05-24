"""
插件热更新模块 (Plugin Hot-Reloading)

功能：监控指定目录下的插件文件变化，自动加载、重载、卸载插件。
设计原则：可插拔、配置化、日志化、支持扩展。依赖插件管理器抽象接口。
"""

import os
import time
import logging
import threading
import importlib
import importlib.util
from typing import Optional, Callable, Dict, Any, Set, List


# ---------- 默认配置 ----------
DEFAULT_CONFIG = {
    "watch_dir": "./plugins",               # 监控的插件目录
    "watch_interval": 2.0,                  # 扫描间隔（秒）
    "file_patterns": ["*.py"],              # 监控的文件匹配模式（支持 glob 通配符）
    "ignore_dotfiles": True,                # 是否忽略点文件（隐藏文件）
    "recursive": False,                     # 是否递归监控子目录
}


class PluginHotReloader:
    """插件热更新管理器，独立于具体的插件加载逻辑，通过事件回调实现扩展"""

    def __init__(self, config: Optional[Dict[str, Any]] = None,
                 on_plugin_added: Optional[Callable[[str], None]] = None,
                 on_plugin_modified: Optional[Callable[[str], None]] = None,
                 on_plugin_removed: Optional[Callable[[str], None]] = None):
        """
        初始化热更新器

        :param config: 配置字典，与默认配置合并
        :param on_plugin_added:   当检测到新插件时的回调（参数：插件文件路径）
        :param on_plugin_modified:当检测到修改时的回调
        :param on_plugin_removed: 当检测到删除时的回调
        """
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.logger = logging.getLogger(f"{__name__}.PluginHotReloader")
        self.logger.setLevel(logging.DEBUG)

        # 回调函数（事件钩子）
        self.on_plugin_added = on_plugin_added or self._default_on_plugin_added
        self.on_plugin_modified = on_plugin_modified or self._default_on_plugin_modified
        self.on_plugin_removed = on_plugin_removed or self._default_on_plugin_removed

        # 内部状态
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._watched_files: Dict[str, float] = {}   # 文件路径 -> 上次修改时间戳
        self._lock = threading.Lock()

    # ---------- 默认回调（只打日志） ----------
    def _default_on_plugin_added(self, plugin_path: str):
        self.logger.info(f"[默认回调] 检测到新增插件: {plugin_path}")

    def _default_on_plugin_modified(self, plugin_path: str):
        self.logger.info(f"[默认回调] 检测到插件修改: {plugin_path}")

    def _default_on_plugin_removed(self, plugin_path: str):
        self.logger.info(f"[默认回调] 检测到插件移除: {plugin_path}")

    # ---------- 文件扫描与变化检测 ----------
    def _get_current_plugin_files(self) -> Dict[str, float]:
        """扫描监控目录，返回满足条件的文件路径及其修改时间的字典"""
        import glob
        available = {}
        watch_dir = os.path.abspath(self.config["watch_dir"])
        if not os.path.isdir(watch_dir):
            self.logger.warning(f"监控目录不存在: {watch_dir}")
            return available

        for pattern in self.config["file_patterns"]:
            search_pattern = os.path.join(watch_dir, pattern)
            for filepath in glob.glob(search_pattern, recursive=self.config["recursive"] or False):
                if self.config["ignore_dotfiles"] and os.path.basename(filepath).startswith('.'):
                    continue
                try:
                    mtime = os.path.getmtime(filepath)
                    available[filepath] = mtime
                except OSError:
                    continue
        return available

    def _compare_snapshots(self, current: Dict[str, float]):
        """比较当前快照与上次记录，触发相应回调"""
        with self._lock:
            previous = self._watched_files.copy()

        # 新增或修改的文件
        for path, mtime in current.items():
            if path not in previous:
                self._trigger_callback(self.on_plugin_added, path)
            elif mtime != previous[path]:
                self._trigger_callback(self.on_plugin_modified, path)

        # 被删除的文件
        for path in previous:
            if path not in current:
                self._trigger_callback(self.on_plugin_removed, path)

        # 更新快照
        with self._lock:
            self._watched_files = current

    def _trigger_callback(self, callback: Callable, plugin_path: str):
        """执行回调，包裹异常处理与日志"""
        try:
            callback(plugin_path)
        except Exception as e:
            self.logger.error(f"执行回调时发生异常 [path={plugin_path}]: {e}", exc_info=True)

    # ---------- 监控循环 ----------
    def _monitor_loop(self):
        """后台线程主体，定期扫描文件变化"""
        self.logger.info("热更新监控线程启动")
        while self._running:
            try:
                current_files = self._get_current_plugin_files()
                self._compare_snapshots(current_files)
            except Exception as e:
                self.logger.error(f"监控循环异常: {e}", exc_info=True)
            time.sleep(self.config["watch_interval"])
        self.logger.info("热更新监控线程停止")

    # ---------- 公开控制接口 ----------
    def start(self):
        """启动热更新监控"""
        if self._running:
            self.logger.warning("热更新监控已在运行中")
            return
        self._running = True
        # 首次启动时，建立初始快照（避免将所有已有文件当成新增）
        with self._lock:
            self._watched_files = self._get_current_plugin_files()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True, name="PluginHotReloader")
        self._monitor_thread.start()
        self.logger.info("热更新监控已启动")

    def stop(self):
        """停止热更新监控"""
        self._running = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5.0)
        self.logger.info("热更新监控已停止")

    def is_running(self) -> bool:
        """返回监控是否正在运行"""
        return self._running

    def update_config(self, new_config: Dict[str, Any]):
        """运行时更新配置（仅对后续扫描生效）"""
        self.config.update(new_config)
        self.logger.info(f"配置已更新: {new_config}")


# ---------- 自测与示例 ----------
if __name__ == "__main__":
    import tempfile
    import shutil

    logging.basicConfig(level=logging.DEBUG)

    # 创建临时插件目录用于自测
    test_dir = tempfile.mkdtemp(prefix="novelos_test_plugins_")
    print(f"测试目录: {test_dir}")

    # 自定义回调：模拟真实插件加载/卸载
    loaded_plugins = set()

    def on_add(path):
        print(f"[实际回调] 加载插件: {path}")
        loaded_plugins.add(path)

    def on_mod(path):
        print(f"[实际回调] 重载插件: {path}")
        # 此处可调用 importlib.reload 等操作

    def on_rem(path):
        print(f"[实际回调] 卸载插件: {path}")
        loaded_plugins.discard(path)

    # 初始化热更新器
    config = {
        "watch_dir": test_dir,
        "watch_interval": 1.0,
        "ignore_dotfiles": True,
        "recursive": False
    }
    reloader = PluginHotReloader(config,
                                 on_plugin_added=on_add,
                                 on_plugin_modified=on_mod,
                                 on_plugin_removed=on_rem)

    # 启动监控
    reloader.start()

    try:
        # 模拟新增插件
        time.sleep(1.5)
        plugin_a = os.path.join(test_dir, "plugin_a.py")
        with open(plugin_a, "w") as f:
            f.write("# plugin a")
        print("已创建 plugin_a.py")
        time.sleep(2)

        # 模拟修改插件
        time.sleep(0.5)
        with open(plugin_a, "a") as f:
            f.write("# modified")
        print("已修改 plugin_a.py")
        time.sleep(2)

        # 模拟删除插件
        time.sleep(0.5)
        os.remove(plugin_a)
        print("已删除 plugin_a.py")
        time.sleep(2)

    finally:
        reloader.stop()
        shutil.rmtree(test_dir)
        print("测试结束，清理临时目录")