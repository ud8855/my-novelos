"""模块路径：30_测试系统/集成测试/集成测试.py
层级：测试系统层
依赖：无（测试框架自身），但会调用系统其他模块（通过接口）
被谁调用：测试运行时、CI/CD流水线、开发者手动执行
解决的问题：验证多个模块协作时的端到端流程是否正确，确保整体功能稳定
"""

import importlib
import logging
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional

# 配置化：可以从外部配置文件读取
DEFAULT_CONFIG = {
    "log_level": "INFO",
    "test_timeout": 60,  # 秒
    "retry_count": 0,
    "report_format": "text",  # text / json
    "enable_parallel": False,
}

class IntegrationTestRunner:
    """集成测试运行器：加载、执行测试用例并生成报告"""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(self.config.get("log_level", "INFO").upper())
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter("[%(asctime)s][%(levelname)s][%(name)s] %(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        self.test_modules: List[Any] = []
        self.results: List[Dict[str, Any]] = []

    def discover_and_load(self, test_dir: str = "tests") -> None:
        """从指定目录发现并加载所有集成测试模块
        注意：真正的发现逻辑应在基类或工具中实现，这里仅为骨架
        """
        # 骨架实现：假设test_dir下每个.py文件是一个测试模块
        discovered = []
        p = Path(test_dir)
        if not p.exists():
            self.logger.warning(f"测试目录不存在: {test_dir}")
            return
        for f in p.glob("*.py"):
            if f.stem == "__init__":
                continue
            module_name = f.stem
            try:
                spec = importlib.util.spec_from_file_location(module_name, f)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                discovered.append(module)
                self.logger.debug(f"发现测试模块: {module_name}")
            except Exception as e:
                self.logger.error(f"加载测试模块失败: {module_name}, 错误: {e}")
        self.test_modules = discovered

    def run_all(self) -> None:
        """运行所有已加载的测试模块中的测试用例"""
        self.results.clear()
        for module in self.test_modules:
            module_name = module.__name__
            # 查找模块中以 test_ 开头的可调用对象（函数或方法）
            for attr_name in dir(module):
                if not attr_name.startswith("test_"):
                    continue
                test_func = getattr(module, attr_name)
                if not callable(test_func):
                    continue
                self.run_single_test(module_name, attr_name, test_func)

    def run_single_test(self, module_name: str, test_name: str, test_func: callable) -> None:
        """运行单个测试用例并记录结果"""
        test_id = f"{module_name}.{test_name}"
        self.logger.info(f"开始执行集成测试: {test_id}")
        result = {
            "module": module_name,
            "name": test_name,
            "id": test_id,
            "status": "PENDING",
            "message": "",
            "duration": 0,
        }
        start_time = time.time()
        try:
            # 可插拔：可在此添加前置/后置钩子
            test_func()
            result["status"] = "PASSED"
            self.logger.info(f"测试通过: {test_id}")
        except AssertionError as e:
            result["status"] = "FAILED"
            result["message"] = str(e)
            self.logger.error(f"测试失败: {test_id} - {e}")
        except Exception as e:
            result["status"] = "ERROR"
            result["message"] = traceback.format_exc()
            self.logger.exception(f"测试异常: {test_id}")
        finally:
            result["duration"] = time.time() - start_time
        self.results.append(result)

    def generate_report(self) -> str:
        """生成测试报告（文本或JSON）"""
        if self.config.get("report_format") == "json":
            import json
            return json.dumps(self.results, indent=2, ensure_ascii=False)
        else:
            # 文本报告
            lines = ["====== 集成测试报告 ======"]
            total = len(self.results)
            passed = sum(1 for r in self.results if r["status"] == "PASSED")
            failed = sum(1 for r in self.results if r["status"] == "FAILED")
            errors = sum(1 for r in self.results if r["status"] == "ERROR")
            lines.append(f"总计: {total}, 通过: {passed}, 失败: {failed}, 错误: {errors}")
            lines.append("")
            for r in self.results:
                status_char = {"PASSED": "✓", "FAILED": "✗", "ERROR": "!"}.get(r["status"], "?")
                lines.append(f"[{status_char}] {r['id']} (耗时: {r['duration']:.3f}s)")
                if r["message"]:
                    lines.append(f"   {r['message']}")
            lines.append("=========================")
            return "\n".join(lines)

    def print_report(self) -> None:
        """打印报告到控制台"""
        report = self.generate_report()
        print(report)


def self_test() -> None:
    """自测：验证集成测试运行器基本流程"""
    import tempfile

    # 创建一个临时测试目录和一个示例测试模块
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir) / "tests"
        test_dir.mkdir()
        # 写入一个简单的测试模块
        test_module_content = """
def test_addition():
    assert 1 + 1 == 2

def test_failing():
    assert False, "故意失败"

def test_error():
    raise RuntimeError("内部错误")
"""
        module_file = test_dir / "sample_integration.py"
        module_file.write_text(test_module_content, encoding="utf-8")

        runner = IntegrationTestRunner({"log_level": "DEBUG"})
        runner.logger.info("开始自我测试...")
        runner.discover_and_load(str(test_dir))
        assert len(runner.test_modules) == 1, "应该发现一个测试模块"
        runner.run_all()
        assert len(runner.results) == 3, "应该有3个测试用例"
        statuses = [r["status"] for r in runner.results]
        assert "PASSED" in statuses
        assert "FAILED" in statuses
        assert "ERROR" in statuses
        runner.print_report()
        print("自我测试通过！")


if __name__ == "__main__":
    import time
    self_test()
else:
    # 当作为模块导入时，可以进行自测
    pass