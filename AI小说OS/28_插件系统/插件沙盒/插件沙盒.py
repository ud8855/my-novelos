# -*- coding: utf-8 -*-
"""
插件沙盒模块 (Plugin Sandbox)
所属层级: 28_插件系统
依赖: 日志服务 (通用日志), 配置管理 (config)
被调用: 插件管理器 (PluginManager)
解决问题: 提供受限的插件执行环境，隔离插件运行时的资源访问、系统调用，
         确保主系统稳定性与安全性，支持插件热插拔和动态加载。
"""
import sys
import os
import logging
import threading
import traceback
import importlib
from typing import Any, Callable, Dict, Optional

# 默认配置
DEFAULT_CONFIG = {
    "timeout": 5,               # 插件执行超时（秒）
    "max_memory": 256,          # 最大内存限制（MB），暂未实现
    "allowed_modules": [],      # 允许导入的模块白名单，空列表表示允许全部（生产环境需严格限制）
    "allow_file_io": False,     # 是否允许文件读写
    "allow_network": False,     # 是否允许网络访问
    "sandbox_type": "basic",    # 沙盒类型: basic, restricted_python, seccomp（后期扩展）
    "log_level": "INFO",
    "log_format": "[%(asctime)s][%(levelname)s][PluginSandbox] %(message)s"
}

class PluginSandbox:
    """
    插件沙盒核心类
    负责在受控环境下执行插件代码，提供异常捕获、资源限制、日志记录等功能
    """
    def __init__(self, config: Optional[Dict] = None):
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)

        # 初始化日志
        self.logger = logging.getLogger("PluginSandbox")
        self.logger.setLevel(self.config.get("log_level", "INFO"))
        formatter = logging.Formatter(self.config.get("log_format"))
        # 避免重复添加 handler
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # 安全策略扩展点（可插拔）
        self.security_checks: list[Callable] = []  # 安全检查函数注册
        self.resource_limits: dict = {}            # 资源限制策略
        self._initialized = True
        self.logger.debug("PluginSandbox initialized with config: %s", self.config)

    def register_security_check(self, check_func: Callable):
        """
        注册自定义安全检查函数
        执行插件前会依次调用这些检查，任一个返回非零值则拒绝执行
        """
        self.security_checks.append(check_func)
        self.logger.info("Security check registered: %s", check_func.__name__)

    def set_resource_limit(self, resource: str, value: Any):
        """设置资源限制"""
        self.resource_limits[resource] = value
        self.logger.debug("Resource limit set: %s = %s", resource, value)

    def _apply_resource_limits(self):
        """应用当前资源限制（平台相关，可作为扩展点）"""
        # 此处为骨架，实际可集成 resource 模块限制内存、CPU等
        pass

    def _run_with_timeout(self, func: Callable, args: tuple, kwargs: dict, timeout: int) -> Any:
        """在独立线程中执行函数并施加超时"""
        result = []
        exception = []

        def target():
            try:
                res = func(*args, **kwargs)
                result.append(res)
            except Exception as e:
                exception.append(e)

        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            thread.join(0)  # 尝试立即终止（Python线程难以强制终止，实际中需借助进程）
            raise TimeoutError(f"Plugin execution timed out after {timeout} seconds")
        if exception:
            raise exception[0]
        return result[0]

    def execute_plugin_code(self, code: str, globals_dict: Dict = None) -> Any:
        """
        执行一段插件代码（字符串形式），使用受限的全局命名空间
        """
        if not code:
            raise ValueError("Plugin code cannot be empty")

        self.logger.info("Executing plugin code (length=%d)", len(code))
        # 安全检查
        for check in self.security_checks:
            if check(code) != 0:
                raise PermissionError("Plugin code rejected by security check")

        # 构建受限全局域
        safe_globals = {
            "__builtins__": {},  # 默认为空，防止危险操作，实际可按白名单开放
            "__name__": "__plugin__",
            "__file__": "plugin",
        }
        if self.config.get("allowed_modules"):
            # 按白名单导入模块
            for mod in self.config["allowed_modules"]:
                safe_globals[mod] = importlib.import_module(mod)

        if globals_dict:
            safe_globals.update(globals_dict)

        # 应用资源限制
        self._apply_resource_limits()

        # 在时间限制下执行
        def _exec():
            exec(code, safe_globals)

        timeout = self.config.get("timeout", 5)
        self._run_with_timeout(_exec, (), {}, timeout)
        self.logger.info("Plugin code execution finished successfully")
        return safe_globals  # 返回执行后的命名空间，便于获取定义的函数/变量

    def execute_plugin_function(self, func: Callable, *args, **kwargs) -> Any:
        """
        直接执行一个可调用对象（如函数），施加沙盒限制
        """
        if not callable(func):
            raise TypeError("Only callable objects can be executed")
        self.logger.info("Executing plugin function: %s", getattr(func, '__name__', repr(func)))
        timeout = self.config.get("timeout", 5)
        self._apply_resource_limits()
        return self._run_with_timeout(func, args, kwargs, timeout)

    def load_plugin_module(self, module_path: str, reload: bool = False) -> Any:
        """
        动态加载插件模块（文件路径形式）
        返回加载的模块对象，供后续调用
        """
        self.logger.info("Loading plugin module: %s", module_path)
        module_name = os.path.splitext(os.path.basename(module_path))[0]
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None:
            raise ImportError(f"Could not load spec for module at {module_path}")
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            self.logger.error("Failed to load plugin module %s: %s", module_path, str(e))
            raise
        self.logger.info("Module loaded: %s", module_name)
        return module

    def shutdown(self):
        """清理资源（预留扩展）"""
        self.logger.info("PluginSandbox shutting down.")
        # 可在此清理线程、临时文件等
        self._initialized = False

# 自测代码
if __name__ == "__main__":
    # 配置测试日志
    logging.basicConfig(level=logging.DEBUG)

    # 创建沙盒实例
    sandbox = PluginSandbox({"timeout": 3, "log_level": "DEBUG"})

    # 测试1：执行简单代码
    try:
        namespace = sandbox.execute_plugin_code("x = 1 + 2")
        assert namespace["x"] == 3
        print("Test 1 passed: basic code execution")
    except Exception as e:
        print("Test 1 failed:", e)

    # 测试2：执行带超时的代码
    try:
        sandbox.execute_plugin_code("import time; time.sleep(10)")
    except TimeoutError:
        print("Test 2 passed: timeout works")
    except Exception as e:
        print("Test 2 unexpected error:", e)

    # 测试3：执行可调用对象
    def sample_add(a, b):
        return a + b

    try:
        res = sandbox.execute_plugin_function(sample_add, 3, 4)
        assert res == 7
        print("Test 3 passed: function execution")
    except Exception as e:
        print("Test 3 failed:", e)

    # 测试4：安全策略注册（模拟拒绝）
    def deny_all(code):
        return 1  # 非零表示拒绝

    sandbox.register_security_check(deny_all)
    try:
        sandbox.execute_plugin_code("print('hello')")
    except PermissionError:
        print("Test 4 passed: security check rejection")
    except Exception as e:
        print("Test 4 unexpected error:", e)

    # 测试5：动态模块加载（需存在临时文件）
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w") as tmp_file:
        tmp_file.write("def greet(name):\n    return f'Hello, {name}'\n")
        temp_path = tmp_file.name
    try:
        mod = sandbox.load_plugin_module(temp_path)
        greeting = mod.greet("World")
        assert greeting == "Hello, World"
        print("Test 5 passed: dynamic module load")
    except Exception as e:
        print("Test 5 failed:", e)
    finally:
        os.unlink(temp_path)

    sandbox.shutdown()
    print("All self-tests completed.")