"""Agent测试.py - Agent测试框架

所属层: 30_测试系统 (Testing System)
依赖: 基类可能依赖 10_核心基础/配置管理器, 10_核心基础/日志管理器, 可能依赖 30_测试系统/基础测试框架
被调用者: 开发者编写测试用例时继承此框架，由测试运行器调用
解决问题: 提供统一的Agent测试接口、生命周期管理、断言工具、日志记录、配置加载，确保Agent模块可独立验证
"""

import logging
import inspect
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
import sys
import os

# 假设系统路径已正确设置，可以导入核心模块
# 但为了自包含，提供默认的日志和配置加载器（可在实际环境中替换）
try:
    from core.log_manager import LogManager
    from core.config_manager import ConfigManager
except ImportError:
    # 默认实现，便于独立测试
    class LogManager:
        @staticmethod
        def get_logger(name):
            return logging.getLogger(name)

    class ConfigManager:
        @staticmethod
        def get_config(section, key, default=None):
            # 简易配置读取，实践中由系统注入
            return os.environ.get(f"NOVELOS_{section}_{key}", default)


class AgentTestException(Exception):
    """Agent测试专用异常"""
    pass


class AgentTestResult:
    """Agent测试结果容器"""
    def __init__(self, test_name: str):
        self.test_name = test_name
        self.passed = False
        self.messages: List[str] = []
        self.duration: float = 0.0
        self.exception: Optional[Exception] = None

    def set_passed(self, message: str = ""):
        self.passed = True
        self.messages.append(f"PASS: {message}")

    def set_failed(self, message: str, exception: Optional[Exception] = None):
        self.passed = False
        self.messages.append(f"FAIL: {message}")
        if exception:
            self.exception = exception
            self.messages.append(f"Exception: {str(exception)}")

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.test_name} ({self.duration:.3f}s): " + "; ".join(self.messages)


class AgentTestBase(ABC):
    """
    Agent测试基类，所有Agent测试用例必须继承此类

    使用方式:
    1. 继承 AgentTestBase
    2. 实现 configure() 方法加载所需配置
    3. 实现 setup() 方法准备测试环境
    4. 实现多个 test_xxx() 方法
    5. 实现 teardown() 方法清理资源
    6. 调用 run() 执行所有测试方法

    配置化: 通过 self.config 访问配置项
    日志: 通过 self.logger 记录日志
    可插拔: 通过 test_agent_config 控制被测Agent的模拟或真实注入
    """
    def __init__(self, test_name: Optional[str] = None, config: Optional[Dict] = None):
        self.test_name = test_name or self.__class__.__name__
        self.config = config or {}
        self.logger = LogManager.get_logger(f"AgentTest.{self.test_name}")

        # 被测Agent相关属性，由子类在configure或setup中设置
        self.agent_instance = None
        self.mock_services: Dict[str, Any] = {}  # 可注入的模拟服务

        # 测试结果集合
        self.results: List[AgentTestResult] = []

        # 配置初始化
        self._load_default_config()
        self.configure()

    def _load_default_config(self):
        """从配置管理器加载默认配置，可被子类覆盖"""
        # 示例: 读取Agent测试通用配置
        default_timeout = ConfigManager.get_config("agent_test", "default_timeout", 10)
        self.config.setdefault("default_timeout", int(default_timeout))

    @abstractmethod
    def configure(self):
        """
        加载测试所需的配置，例如: 被测Agent的ID、模拟参数等
        子类必须实现
        """
        pass

    @abstractmethod
    def setup(self):
        """
        初始化测试环境，包括创建Agent实例、连接模拟服务等
        子类必须实现
        """
        pass

    @abstractmethod
    def teardown(self):
        """
        清理测试资源，例如关闭Agent、断开连接等
        子类必须实现
        """
        pass

    def run(self) -> List[AgentTestResult]:
        """
        运行所有测试方法 (方法名以 test_ 开头)
        返回测试结果列表
        """
        self.logger.info(f"Running tests for {self.test_name}...")
        self.results.clear()

        # 收集 test_ 开头的公共方法
        test_methods = [method_name for method_name, _ in inspect.getmembers(self, predicate=inspect.ismethod)
                        if method_name.startswith("test_") and callable(getattr(self, method_name))]

        if not test_methods:
            self.logger.warning(f"No test methods found (must start with 'test_') in {self.test_name}")
            return self.results

        # 测试前环境准备
        try:
            self.setup()
        except Exception as e:
            self.logger.exception(f"Setup failed for {self.test_name}: {e}")
            result = AgentTestResult("__setup__")
            result.set_failed("Setup failed", e)
            self.results.append(result)
            return self.results

        # 逐个执行测试方法
        import time
        for test_method in test_methods:
            result = AgentTestResult(test_method)
            start_time = time.time()
            try:
                getattr(self, test_method)()  # 执行测试
                result.set_passed()
            except AssertionError as e:
                result.set_failed(str(e), e)
            except Exception as e:
                result.set_failed(f"Unexpected error: {str(e)}", e)
            finally:
                result.duration = time.time() - start_time
                self.results.append(result)
                self.logger.info(str(result))

        # 测试后清理
        try:
            self.teardown()
        except Exception as e:
            self.logger.error(f"Teardown failed: {e}")
            # 不标记测试失败，因为清理失败不算测试失败，但记录

        # 打印汇总
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        self.logger.info(f"Test summary for {self.test_name}: {passed}/{total} passed.")
        return self.results

    def assert_true(self, condition: bool, message: str = ""):
        """断言条件为真，否则抛出AssertionError"""
        if not condition:
            raise AssertionError(f"Expected True, got False. {message}")

    def assert_false(self, condition: bool, message: str = ""):
        """断言条件为假"""
        if condition:
            raise AssertionError(f"Expected False, got True. {message}")

    def assert_equal(self, first, second, message: str = ""):
        """断言相等"""
        if first != second:
            raise AssertionError(f"{first} != {second}. {message}")

    def assert_not_equal(self, first, second, message: str = ""):
        """断言不相等"""
        if first == second:
            raise AssertionError(f"{first} == {second}. {message}")

    def assert_in(self, member, container, message: str = ""):
        """断言成员在容器中"""
        if member not in container:
            raise AssertionError(f"{member} not in {container}. {message}")

    def assert_not_in(self, member, container, message: str = ""):
        """断言成员不在容器中"""
        if member in container:
            raise AssertionError(f"{member} in {container}. {message}")

    def assert_raises(self, exc_type, callable_obj, *args, **kwargs):
        """断言调用会引发特定异常"""
        try:
            callable_obj(*args, **kwargs)
        except exc_type:
            return
        except Exception as e:
            raise AssertionError(f"Expected {exc_type.__name__}, but got {type(e).__name__}: {e}")
        raise AssertionError(f"Expected {exc_type.__name__} to be raised, but no exception occurred.")

    def log_info(self, msg: str):
        self.logger.info(msg)

    def log_debug(self, msg: str):
        self.logger.debug(msg)

    def log_warning(self, msg: str):
        self.logger.warning(msg)

    def log_error(self, msg: str):
        self.logger.error(msg)

    # 可插拔支持：允许注入模拟服务
    def inject_mock(self, service_name: str, mock_instance):
        """注入一个模拟服务，供Agent使用"""
        self.mock_services[service_name] = mock_instance
        self.logger.debug(f"Injected mock service: {service_name}")


# ========== 自测部分 ==========
class _SelfTestAgentTest(AgentTestBase):
    """内部自测，验证框架功能是否正常"""
    def configure(self):
        self.config["test_key"] = "test_value"

    def setup(self):
        self.mock_services["test_service"] = "mocked"

    def teardown(self):
        self.mock_services.clear()

    def test_assert_true(self):
        self.assert_true(1 == 1, "1 should equal 1")

    def test_assert_false(self):
        self.assert_false(1 == 2, "1 should not equal 2")

    def test_assert_equal(self):
        self.assert_equal("hello", "hello", "strings should match")

    def test_assert_not_equal(self):
        self.assert_not_equal(1, 2, "numbers should differ")

    def test_assert_in(self):
        self.assert_in(3, [1, 2, 3], "3 should be in list")

    def test_assert_not_in(self):
        self.assert_not_in(4, [1, 2, 3], "4 should not be in list")

    def test_assert_raises(self):
        def func():
            raise ValueError("error")
        self.assert_raises(ValueError, func)

    def test_assert_raises_wrong_exception(self):
        # 这个测试应该失败，因为抛出错误类型不匹配
        def func():
            raise TypeError("error")
        self.assert_raises(ValueError, func)  # 预期失败

    def test_assert_raises_no_exception(self):
        # 应该失败，因为没有异常
        def func():
            pass
        self.assert_raises(ValueError, func)

    def test_failing(self):
        # 故意失败
        self.assert_true(False, "intended failure")


def self_test():
    """运行框架自测，验证基本功能"""
    tester = _SelfTestAgentTest(test_name="SelfTest")
    results = tester.run()
    print("Self-test results:")
    for r in results:
        print(f"  {r}")
    # 检查预期通过/失败
    expected_passes = ["test_assert_true", "test_assert_false", "test_assert_equal",
                       "test_assert_not_equal", "test_assert_in", "test_assert_not_in",
                       "test_assert_raises"]
    expected_fails = ["test_assert_raises_wrong_exception", "test_assert_raises_no_exception", "test_failing"]

    for r in results:
        if r.test_name in expected_passes:
            if not r.passed:
                print(f"ERROR: {r.test_name} was expected to pass but failed.")
        elif r.test_name in expected_fails:
            if r.passed:
                print(f"ERROR: {r.test_name} was expected to fail but passed.")
        else:
            print(f"WARNING: Unexpected test method {r.test_name}.")


if __name__ == "__main__":
    # 配置基本日志以便自测查看
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    self_test()