"""沙盒测试模块 - 提供安全隔离的测试环境，用于验证新功能、模块或修复。
属于：99_实验室 -> 沙盒测试
依赖：仅标准库（logging, os, json等）、项目配置加载器（预留接口）
被调用：可由其他模块在开发阶段调用，也可通过 CLI 或自动化测试框架触发
解决：在不影响核心系统的情况下，运行临时测试、回放场景、异常注入等
"""
import json
import logging
import sys
import time
from typing import Any, Callable, Dict, Optional

# 日志配置（可从外部配置注入）
_DEFAULT_LOG_CONFIG = {
    "level": logging.DEBUG,
    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    "datefmt": "%Y-%m-%d %H:%M:%S"
}

# 沙盒测试配置结构
_DEFAULT_SANDBOX_CONFIG: Dict[str, Any] = {
    "timeout_seconds": 30,
    "allow_network": False,          # 是否允许外部网络调用
    "allow_file_write": True,       # 是否允许写入文件（仅限临时目录）
    "temp_directory": "./sandbox_tmp",
    "enable_log_capture": True,     # 是否捕获子模块日志
    "report_format": "json"
}


class SandboxTestRunner:
    """可插拔的沙盒测试运行器基类 - 所有沙盒测试必须继承此类并实现 run() 方法。"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, logger: Optional[logging.Logger] = None):
        """
        初始化测试运行器
        :param config: 沙盒配置字典，若为 None 则使用默认配置
        :param logger: 外部传入的日志记录器，若为 None 则内部创建
        """
        self.config = _DEFAULT_SANDBOX_CONFIG.copy()
        if config:
            self.config.update(config)
        
        # 日志设置
        if logger is None:
            self.logger = logging.getLogger(self.__class__.__name__)
            # 避免重复添加handler
            if not self.logger.handlers:
                self._setup_default_logger()
        else:
            self.logger = logger
        
        self._test_start_time: float = 0.0
        self._test_end_time: float = 0.0
        self._result: Dict[str, Any] = {}
    
    def _setup_default_logger(self):
        """使用默认配置初始化日志记录器。"""
        config = self.config.get("log_config", _DEFAULT_LOG_CONFIG)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(config.get("format"), config.get("datefmt"))
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(config.get("level", logging.DEBUG))
        # 如果不需要根logger传播，可设置 propagate = False
        self.logger.propagate = False
    
    def pre_run(self):
        """运行前准备：创建临时目录、网络限制检查等（在此可扩展）。"""
        self.logger.info("沙盒测试准备开始...")
        # 创建临时目录（如果需要）
        temp_dir = self.config.get("temp_directory", "./sandbox_tmp")
        if self.config.get("allow_file_write") and not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
            self.logger.debug(f"临时目录已创建/确认: {temp_dir}")
        self._test_start_time = time.time()
    
    def run(self) -> Dict[str, Any]:
        """
        核心测试逻辑，子类必须实现。
        返回一个包含测试结果的字典，必须包含 'status' 字段 (success/failure/error)
        """
        raise NotImplementedError("子类必须实现 run() 方法")
    
    def post_run(self, result: Dict[str, Any]):
        """
        运行后处理：清理资源、生成报告等。
        :param result: run() 方法返回的结果字典
        """
        self._test_end_time = time.time()
        duration = self._test_end_time - self._test_start_time
        result["duration_seconds"] = round(duration, 3)
        result.setdefault("timestamp", time.strftime("%Y-%m-%dT%H:%M:%S"))
        self._result = result
        
        self.logger.info(f"沙盒测试完成，耗时 {duration:.3f} 秒，状态: {result.get('status', 'unknown')}")
        # 生成报告
        if self.config.get("enable_log_capture"):
            self._save_report(result)
    
    def _save_report(self, result: Dict[str, Any]):
        """将测试结果写入报告文件（JSON格式），以供后续分析。"""
        report_format = self.config.get("report_format", "json")
        if report_format == "json":
            report_path = os.path.join(self.config.get("temp_directory", "."), f"sandbox_report_{int(time.time())}.json")
            try:
                with open(report_path, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                self.logger.info(f"测试报告已保存至: {report_path}")
            except Exception as e:
                self.logger.error(f"保存报告失败: {e}")
    
    def run_with_lifecycle(self) -> Dict[str, Any]:
        """
        完整的生命周期管理：pre_run -> run -> post_run，并处理异常和超时。
        该方法是外部调用的入口，不建议被子类覆盖。
        """
        timeout = self.config.get("timeout_seconds", 30)
        try:
            self.pre_run()
            # 超时控制（简化版，使用 signal 或线程，此处预留接口）
            # 实际实现可以引入 signal 或 concurrent.futures
            result = self.run()
        except NotImplementedError:
            self.logger.error("run() 方法未实现，请继承 SandboxTestRunner 并实现 run()")
            result = {"status": "error", "message": "run() 方法未实现"}
        except Exception as e:
            self.logger.error(f"测试执行中发生未捕获异常: {e}", exc_info=True)
            result = {"status": "error", "message": str(e)}
        else:
            if not isinstance(result, dict):
                self.logger.warning("run() 未返回字典，已自动包装")
                result = {"status": "success", "data": result}
        finally:
            self.post_run(result)
        return result


# 示例定制测试（用于验证框架）
class DemoTest(SandboxTestRunner):
    """演示用测试 - 用于自测框架是否正常工作"""
    def run(self) -> Dict[str, Any]:
        self.logger.info("执行演示测试逻辑...")
        # 模拟一个简单测试
        test_value = 2 + 2
        if test_value == 4:
            return {"status": "success", "details": "2+2=4 验证通过"}
        else:
            return {"status": "failure", "details": f"计算错误: 2+2={test_value}"}


# 自测入口
if __name__ == "__main__":
    # 基础自测：使用默认配置运行演示测试
    print("=== 沙盒测试模块自测 ===")
    
    # 创建演示测试实例
    tester = DemoTest()
    # 运行完整生命周期
    report = tester.run_with_lifecycle()
    
    # 打印简要结果
    print(f"\n最终状态: {report.get('status')}")
    print(f"详情: {report.get('details', '无')}")
    print(f"耗时: {report.get('duration_seconds', '?')} 秒")
    
    # 验证可插拔性：可以传入自定义配置
    custom_config = {
        "timeout_seconds": 5,
        "allow_network": True,
        "temp_directory": "./custom_sandbox_tmp"
    }
    custom_logger = logging.getLogger("CustomLogger")
    custom_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[Custom] %(message)s"))
    custom_logger.addHandler(handler)
    
    custom_tester = DemoTest(config=custom_config, logger=custom_logger)
    custom_tester.run_with_lifecycle()
    
    print("\n自测完成。")