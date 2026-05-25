"""30_测试系统/Runtime测试/Runtime测试.py - Runtime层测试执行器骨架
功能：加载和运行Runtime模块的测试用例，收集结果并生成报告。
依赖：Runtime核心模块（测试目标），本模块仅测试概念，不包含业务逻辑。
被调用：由测试系统调度层或直接命令行调用。
解决：确保Runtime各组件在变更后仍符合预期，支持回归测试。
"""

import logging
import time
import json
import importlib
from typing import Callable, Dict, Any, List, Optional

# ---------------------------- 配置管理 ----------------------------
class TestConfig:
    """测试配置，支持从字典或JSON文件加载，默认值"""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.data = {
            "log_level": "INFO",
            "log_file": None,            # None表示仅控制台输出
            "test_timeout": 30,          # 单个测试超时秒数
            "report_format": "json",     # 报告输出格式: json / console
            "enable_parallel": False,    # 是否并行执行（预留）
            "test_module_dirs": ["30_测试系统/Runtime测试/test_cases"],  # 测试用例包路径
        }
        if config:
            self.data.update(config)
        self._apply_logging()

    def _apply_logging(self):
        """根据配置初始化日志系统"""
        log_level = getattr(logging, self.data["log_level"].upper(), logging.INFO)
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        handlers = [logging.StreamHandler()]
        if self.data["log_file"]:
            handlers.append(logging.FileHandler(self.data["log_file"], encoding='utf-8'))
        logging.basicConfig(level=log_level, format=log_format, handlers=handlers)
        self.logger = logging.getLogger("RuntimeTest")

    def get(self, key: str, default=None):
        return self.data.get(key, default)

# ---------------------------- 测试用例基类 ----------------------------
class TestCase:
    """测试用例基类，所有Runtime测试用例需继承此类"""
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.logger = logging.getLogger(f"RuntimeTest.{self.name}")

    def setup(self):
        """测试前置准备"""
        pass

    def teardown(self):
        """测试后置清理"""
        pass

    def run(self) -> Dict[str, Any]:
        """执行测试，返回包含状态和信息的字典"""
        result = {"name": self.name, "status": "UNKNOWN", "message": "",
                  "start_time": None, "end_time": None, "duration": 0}
        try:
            self.setup()
            result["start_time"] = time.time()
            # 实际测试逻辑由子类实现（此处为抽象方法）
            self.execute_test()
            result["status"] = "PASS"
        except AssertionError as e:
            result["status"] = "FAIL"
            result["message"] = str(e)
        except Exception as e:
            result["status"] = "ERROR"
            result["message"] = f"Unexpected error: {str(e)}"
        finally:
            result["end_time"] = time.time()
            if result["start_time"]:
                result["duration"] = round(result["end_time"] - result["start_time"], 4)
            self.teardown()
        return result

    def execute_test(self):
        """子类必须实现测试逻辑，使用断言"""
        raise NotImplementedError("Subclass must implement execute_test()")

# ---------------------------- 测试运行器 ----------------------------
class RuntimeTestRunner:
    """Runtime测试运行器，负责收集用例、执行、生成报告"""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = TestConfig(config)
        self.logger = self.config.logger
        self.test_cases: List[TestCase] = []
        self.results: List[Dict[str, Any]] = []

    def register_test_case(self, test_case: TestCase):
        """注册单个测试用例"""
        if not isinstance(test_case, TestCase):
            raise TypeError("Only TestCase instances can be registered")
        self.test_cases.append(test_case)
        self.logger.debug(f"Registered test case: {test_case.name}")

    def discover_test_cases(self, module_path: str):
        """从指定Python模块路径动态加载TestCase子类（示例：'30_测试系统.Runtime测试.test_cases'）"""
        try:
            module = importlib.import_module(module_path)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, TestCase) and attr is not TestCase:
                    test_case = attr()
                    self.register_test_case(test_case)
                    self.logger.info(f"Discovered test case: {test_case.name} from {module_path}")
        except ModuleNotFoundError:
            self.logger.warning(f"Test module not found: {module_path}")
        except Exception as e:
            self.logger.error(f"Error discovering tests in {module_path}: {e}")

    def run_all(self) -> List[Dict[str, Any]]:
        """运行所有注册的测试用例，返回结果列表"""
        if not self.test_cases:
            self.logger.warning("No test cases registered. Run aborted.")
            return []
        self.logger.info(f"Starting {len(self.test_cases)} Runtime test(s)...")
        self.results = []
        for test in self.test_cases:
            self.logger.info(f"Running: {test.name}")
            result = test.run()
            self.results.append(result)
            self.logger.info(f"Result: {result['name']} -> {result['status']} (took {result['duration']}s)")
        self._generate_report()
        return self.results

    def _generate_report(self):
        """根据配置生成测试报告"""
        report_format = self.config.get("report_format", "console")
        if report_format == "json":
            report = {
                "total": len(self.results),
                "pass": sum(1 for r in self.results if r["status"] == "PASS"),
                "fail": sum(1 for r in self.results if r["status"] == "FAIL"),
                "error": sum(1 for r in self.results if r["status"] == "ERROR"),
                "results": self.results,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
            }
            report_json = json.dumps(report, indent=2, ensure_ascii=False)
            self.logger.info("--- Test Report (JSON) ---\n" + report_json)
        else:
            # console格式
            self.logger.info("=== Runtime Test Report ===")
            for r in self.results:
                self.logger.info(f"{r['name']}: {r['status']} ({r['duration']}s) - {r['message']}")

# ---------------------------- 自测 ----------------------------
class DummyRuntimeTest(TestCase):
    """用于自测的示例测试用例，模拟Runtime组件"""
    def __init__(self):
        super().__init__("RuntimeBasicTest", "检查Runtime基础功能")

    def execute_test(self):
        # 模拟一个简单的Runtime操作，例如获取状态
        # 此处仅做示范，实际应导入Runtime模块
        sample_output = "OK"
        assert sample_output == "OK", "Runtime basic check failed"
        self.logger.info("Runtime basic check passed")

if __name__ == "__main__":
    # 自测：创建运行器，注册示例用例并执行
    runner = RuntimeTestRunner({"log_level": "DEBUG"})
    # 手动注册一个示例用例
    runner.register_test_case(DummyRuntimeTest())
    # 运行测试
    results = runner.run_all()
    # 简单断言自测状态
    failed = [r for r in results if r["status"] != "PASS"]
    if failed:
        print("Self-test failed:", failed)
        exit(1)
    else:
        print("Self-test passed.")