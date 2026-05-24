# -*- coding: utf-8 -*-
"""
实验Agent骨架 - 用于NovelOS实验室中临时性、探索性功能的快速验证
所属层级：99_实验室/实验Agent
依赖：无核心模块硬依赖，通过配置注入外部能力
被调用：实验平台、其他开发者手动测试
功能：提供可插拔的实验性功能运行环境，支持独立配置、日志隔离、热插拔
"""
import logging
import sys
from typing import Any, Dict, Optional, Callable

# 默认配置路径（可外部传入）
DEFAULT_CONFIG = {
    "experiment_name": "default_experiment",
    "log_level": "INFO",
    "max_retries": 3,
    "timeout_seconds": 60,
    "enable_hotplug": True,
}

class ExperimentAgent:
    """实验Agent基类，所有临时实验均继承或实例化本类"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化实验Agent
        :param config: 自定义配置字典，与默认配置合并
        """
        # 配置加载与合并
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)

        # 初始化独立日志记录器
        self.logger = self._setup_logger()

        # 热插拔状态
        self.active = False

        # 实验任务执行器（可由外部注入）
        self.task_handler: Optional[Callable] = None

        self.logger.info(f"实验Agent初始化完成，实验名称: {self.config['experiment_name']}")

    def _setup_logger(self) -> logging.Logger:
        """配置独立日志记录器，支持日志隔离"""
        logger = logging.getLogger(f"experiment_{self.config['experiment_name']}")
        logger.setLevel(getattr(logging, self.config.get("log_level", "INFO")))

        # 避免重复添加处理器
        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                f"[{self.config['experiment_name']}][%(asctime)s][%(levelname)s] %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def activate(self) -> bool:
        """激活实验Agent，注册待监听的事件或启动资源"""
        if not self.active:
            self.active = True
            self.logger.info("实验Agent已激活")
            # 预留：在此添加激活逻辑，如启动后台线程、注册钩子等
            if self.config.get("enable_hotplug"):
                self._register_hotplug_handlers()
        return self.active

    def deactivate(self) -> bool:
        """停用实验Agent，释放资源"""
        if self.active:
            self.active = False
            self.logger.info("实验Agent已停用")
            # 预留：在此添加清理逻辑
            if self.config.get("enable_hotplug"):
                self._unregister_hotplug_handlers()
        return not self.active

    def _register_hotplug_handlers(self):
        """注册热插拔回调（占位）"""
        self.logger.debug("注册热插拔相关处理器")

    def _unregister_hotplug_handlers(self):
        """注销热插拔回调（占位）"""
        self.logger.debug("注销热插拔处理器")

    def run_experiment(self, input_data: Any, **kwargs) -> Dict[str, Any]:
        """
        执行实验任务
        :param input_data: 输入数据
        :param kwargs: 额外参数
        :return: 实验结果字典，包含状态、数据、错误信息等
        """
        if not self.active:
            self.logger.warning("实验Agent未激活，自动激活后继续执行")
            self.activate()

        self.logger.info(f"开始执行实验，输入: {str(input_data)[:200]}")
        result = {"success": False, "data": None, "error": None}

        try:
            # 如果外部注入了自定义任务处理器，则调用
            if self.task_handler:
                processed = self.task_handler(input_data, **kwargs)
            else:
                # 默认处理器：简单回显
                processed = self._default_handler(input_data, **kwargs)

            result["success"] = True
            result["data"] = processed
            self.logger.info("实验执行成功")
        except Exception as e:
            result["error"] = str(e)
            self.logger.error(f"实验执行失败: {e}", exc_info=True)

        return result

    def _default_handler(self, input_data: Any, **kwargs) -> Any:
        """默认实验任务处理（占位）"""
        self.logger.debug("调用默认实验处理器")
        # 此处可添加简单的实验逻辑，如数据转换
        return {"echo": input_data, "params": kwargs}

    def set_task_handler(self, handler: Callable):
        """
        动态注入实验任务处理函数，实现热插拔
        :param handler: 接受 input_data 和 kwargs 的可调用对象
        """
        self.task_handler = handler
        self.logger.info("已更新实验任务处理器")

    def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "active": self.active,
            "experiment_name": self.config["experiment_name"],
            "handler_attached": self.task_handler is not None,
        }


# ================= 自测部分 =================
if __name__ == "__main__":
    """自测执行示例，不依赖外部系统"""
    # 实例化实验Agent
    agent = ExperimentAgent({"experiment_name": "quick_test", "log_level": "DEBUG"})

    # 输出健康状态
    print("初始健康状态:", agent.health_check())

    # 激活
    agent.activate()

    # 执行默认实验
    res1 = agent.run_experiment("Hello NovelOS")
    print("默认实验返回:", res1)

    # 注入自定义处理函数
    def my_handler(data, **kwargs):
        return f"自定义处理: {data}, 附加参数: {kwargs}"

    agent.set_task_handler(my_handler)

    res2 = agent.run_experiment("Custom Injection", extra="param_value")
    print("注入后实验返回:", res2)

    # 停用
    agent.deactivate()

    # 再次执行（应自动激活）
    res3 = agent.run_experiment("After deactivate")
    print("自动激活后返回:", res3)

    print("最终健康状态:", agent.health_check())