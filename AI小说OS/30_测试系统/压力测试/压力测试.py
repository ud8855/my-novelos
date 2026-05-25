"""压力测试模块骨架
属于: 30_测试系统/压力测试
依赖: 标准库logging, configparser; 可能依赖项目内的配置管理模块（但在此骨架中用json文件模拟）
被调用: 可由测试调度器或命令行调用
解决问题: 对NovelOS系统各模块进行压力测试，验证高负载下的稳定性、性能及资源使用
"""

import json
import logging
import logging.config
import os
import time
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable

# ----------------------------
# 日志配置 (默认使用basicConfig，可替换为文件配置)
# ----------------------------
LOG = logging.getLogger("PressureTest")
if not LOG.handlers:
    LOG.setLevel(logging.DEBUG)
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    LOG.addHandler(_handler)

# ----------------------------
# 配置管理 (简易实现，可替换为项目统一的配置模块)
# ----------------------------
class PressureTestConfig:
    """压力测试配置类，负责加载和提供配置参数"""
    
    DEFAULT_CONFIG = {
        "concurrency": 10,          # 并发数
        "duration_seconds": 60,     # 持续时间(秒)
        "ramp_up_seconds": 10,      # 预热时间(秒)
        "task_class": "pressure_test.tasks.ExampleTask",  # 任务类全路径
        "task_params": {},          # 传递给任务的参数
        "log_level": "INFO",
        "output_dir": "./test_results/pressure"
    }
    
    def __init__(self, config_path: Optional[str] = None):
        self._config = self.DEFAULT_CONFIG.copy()
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                self._config.update(user_config)
        # 设置日志级别
        level = getattr(logging, self._config.get("log_level", "INFO"), logging.INFO)
        LOG.setLevel(level)
        LOG.debug("压力测试配置加载完成: %s", self._config)
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        return dict(self._config)

# ----------------------------
# 抽象压力测试任务
# ----------------------------
class AbstractPressureTask(ABC):
    """压力测试任务抽象基类，所有具体任务需继承并实现execute方法"""
    
    def __init__(self, params: Dict[str, Any]):
        self.params = params
        self.logger = LOG.getChild(self.__class__.__name__)
        self.stats = {
            "success_count": 0,
            "failure_count": 0,
            "total_requests": 0,
            "average_response_time": 0.0
        }
        self._lock = threading.Lock()
    
    @abstractmethod
    def setup(self) -> bool:
        """测试准备，返回True表示成功"""
        pass
    
    @abstractmethod
    def execute(self) -> bool:
        """执行一次测试操作，返回True表示成功，False表示失败"""
        pass
    
    @abstractmethod
    def teardown(self) -> bool:
        """测试清理"""
        pass
    
    def record(self, success: bool, response_time: float = 0.0):
        """记录本次操作结果（线程安全）"""
        with self._lock:
            self.stats["total_requests"] += 1
            if success:
                self.stats["success_count"] += 1
            else:
                self.stats["failure_count"] += 1
            # 更新平均响应时间 (简单移动平均)
            n = self.stats["total_requests"]
            prev_avg = self.stats["average_response_time"]
            self.stats["average_response_time"] = prev_avg + (response_time - prev_avg) / n if n > 0 else response_time
    
    def get_stats(self) -> Dict[str, Any]:
        """获取当前统计信息（线程安全）"""
        with self._lock:
            return dict(self.stats)

# ----------------------------
# 压力测试执行器
# ----------------------------
class PressureTestRunner:
    """压力测试运行器，负责调度任务、管理线程、收集统计"""
    
    def __init__(self, config: PressureTestConfig):
        self.config = config
        self.logger = LOG.getChild("Runner")
        self.task_class_path = config.get("task_class")
        self.concurrency = config.get("concurrency")
        self.duration = config.get("duration_seconds")
        self.ramp_up = config.get("ramp_up_seconds")
        self.task_params = config.get("task_params", {})
        self.output_dir = config.get("output_dir")
        self.task_instance: Optional[AbstractPressureTask] = None
        self.threads: List[threading.Thread] = []
        self.stop_event = threading.Event()
        self._stats_lock = threading.Lock()
        self.aggregated_stats = {}
    
    def _load_task_class(self) -> Optional[AbstractPressureTask]:
        """根据配置动态加载任务类（可插拔）"""
        try:
            parts = self.task_class_path.rsplit('.', 1)
            if len(parts) == 2:
                module_name, class_name = parts
                import importlib
                module = importlib.import_module(module_name)
                task_cls = getattr(module, class_name)
            else:
                # 直接使用类名，假设在当前模块或已导入
                task_cls = globals().get(self.task_class_path)
                if not task_cls:
                    task_cls = __import__(self.task_class_path, fromlist=[self.task_class_path])
            
            if not issubclass(task_cls, AbstractPressureTask):
                self.logger.error("加载的任务类未继承 AbstractPressureTask: %s", self.task_class_path)
                return None
            return task_cls
        except Exception as e:
            self.logger.error("加载任务类失败: %s", str(e))
            return None
    
    def _worker(self, task: AbstractPressureTask, task_id: int):
        """工作线程函数"""
        self.logger.debug("工作线程 %d 启动", task_id)
        local_success = 0
        local_failure = 0
        start_time = time.time()
        while not self.stop_event.is_set():
            try:
                t0 = time.time()
                success = task.execute()
                elapsed = time.time() - t0
                task.record(success, elapsed)
                if success:
                    local_success += 1
                else:
                    local_failure += 1
            except Exception as e:
                self.logger.error("线程 %d 执行异常: %s", task_id, str(e))
                task.record(False, 0)
                local_failure += 1
        self.logger.debug("工作线程 %d 退出, 成功:%d, 失败:%d", task_id, local_success, local_failure)
    
    def run(self) -> Dict[str, Any]:
        """执行压力测试"""
        self.logger.info("开始压力测试，配置: %s", self.config.to_dict())
        
        # 加载任务类
        task_cls = self._load_task_class()
        if not task_cls:
            return {"error": "任务类加载失败"}
        
        # 创建任务实例
        self.task_instance = task_cls(self.task_params)
        if not self.task_instance.setup():
            self.logger.error("任务初始化失败")
            return {"error": "任务初始化失败"}
        
        # 启动工作线程
        self.stop_event.clear()
        self.threads = []
        # 可选的预热阶段：逐步增加线程
        if self.ramp_up > 0 and self.concurrency > 1:
            threads_per_step = max(1, self.concurrency // max(1, int(self.ramp_up / 2)))
            for i in range(self.concurrency):
                t = threading.Thread(target=self._worker, args=(self.task_instance, i+1))
                self.threads.append(t)
                t.start()
                if (i+1) % threads_per_step == 0 and i+1 < self.concurrency:
                    time.sleep(2)  # 每步间隔2秒
        else:
            for i in range(self.concurrency):
                t = threading.Thread(target=self._worker, args=(self.task_instance, i+1))
                self.threads.append(t)
                t.start()
        
        # 等待持续时间
        self.logger.info("压力测试运行中，预计持续 %d 秒...", self.duration)
        time.sleep(self.duration)
        
        # 停止所有线程
        self.stop_event.set()
        for t in self.threads:
            t.join(timeout=5)
        
        # 收集结果
        self.aggregated_stats = self.task_instance.get_stats()
        
        # 清理
        self.task_instance.teardown()
        
        # 输出到文件
        self._save_results()
        
        self.logger.info("压力测试结束，统计: %s", self.aggregated_stats)
        return self.aggregated_stats
    
    def _save_results(self):
        """保存测试结果到文件"""
        if not self.output_dir:
            return
        os.makedirs(self.output_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        result_file = os.path.join(self.output_dir, f"pressure_result_{timestamp}.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump({
                "config": self.config.to_dict(),
                "stats": self.aggregated_stats,
                "timestamp": timestamp
            }, f, indent=2, ensure_ascii=False)
        self.logger.info("结果已保存到 %s", result_file)
    
    def stop(self):
        """外部停止压力测试"""
        self.stop_event.set()
        self.logger.info("收到停止信号，正在停止压力测试...")

# ----------------------------
# 示例具体任务 (用于自测)
# ----------------------------
class ExampleTask(AbstractPressureTask):
    """示例压力测试任务，模拟一个简单的操作"""
    
    def setup(self) -> bool:
        LOG.info("ExampleTask 初始化完成")
        return True
    
    def execute(self) -> bool:
        # 模拟一个耗时操作，成功概率90%
        time.sleep(0.05)
        import random
        return random.random() < 0.9
    
    def teardown(self) -> bool:
        LOG.info("ExampleTask 清理完成")
        return True

# ----------------------------
# 自测与入口
# ----------------------------
def _self_test():
    """自测函数，使用示例任务进行简单压力测试"""
    print("=" * 50)
    print("执行压力测试模块自测...")
    # 准备配置
    test_config_data = {
        "concurrency": 5,
        "duration_seconds": 5,
        "ramp_up_seconds": 0,
        "task_class": "ExampleTask",
        "task_params": {},
        "log_level": "DEBUG",
        "output_dir": "./test_results/pressure_self_test"
    }
    # 写入临时配置文件
    config_path = "./pressure_test_config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(test_config_data, f, indent=2)
    
    try:
        config = PressureTestConfig(config_path)
        runner = PressureTestRunner(config)
        results = runner.run()
        print("自测完成，结果:", results)
        assert results.get("total_requests", 0) > 0, "自测失败：没有执行任何请求"
        print("自测通过！")
    except Exception as e:
        print("自测异常:", e)
    finally:
        if os.path.exists(config_path):
            os.remove(config_path)

if __name__ == "__main__":
    # 可通过命令行参数扩展，这里直接运行自测
    _self_test()