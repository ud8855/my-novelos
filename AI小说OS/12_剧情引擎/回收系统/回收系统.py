""" 
模块路径：12_剧情引擎/回收系统/回收系统.py
层级：剧情引擎层（Layer 12）
依赖：本层无外部依赖，可使用基础日志和配置模块
被调用方：12_剧情引擎内部其他模块，如剧情流管理器或节点处理器
功能：提供剧情元素回收、上下文清理、资源重置等可插拔服务
设计原则：可插拔（通过统一接口实现可替换）、配置化（通过配置字典控制行为）、
          日志记录、异常恢复、支持热更新重载
"""

import logging
import traceback
from typing import Any, Dict, Optional

class RecycleSystem:
    """
    剧情回收系统
    负责清理不再需要的剧情节点、重置上下文状态、回收资源，
    以维持剧情引擎长期稳定运行。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化回收系统
        :param config: 配置字典，可包含：
            - log_level: 日志级别，默认 INFO
            - recycle_threshold: 触发回收的阈值（如节点数量），默认 1000
            - enable_auto_recycle: 是否启用自动回收，默认 False
            - hot_reload: 是否支持热更配置重载，默认 True
        """
        self._config = config or {}
        self._validate_config()
        self._setup_logging()
        self._status = {
            "recycled_count": 0,
            "last_recycle_time": None,
            "is_active": bool(self._config.get("enable_auto_recycle", False))
        }
        self.logger.info("回收系统初始化完成，配置：%s", self._config)

    def _validate_config(self):
        """配置合法性校验与默认值填充"""
        defaults = {
            "log_level": "INFO",
            "recycle_threshold": 1000,
            "enable_auto_recycle": False,
            "hot_reload": True
        for key, value in defaults.items():
            self._config.setdefault(key, value)

    def _setup_logging(self):
        """配置日志记录器"""
        self.logger = logging.getLogger(f"{__name__}.RecycleSystem")
        level = getattr(logging, self._config.get("log_level", "INFO"), logging.INFO)
        self.logger.setLevel(level)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def recycle(self, target: Optional[Any] = None) -> bool:
        """
        执行回收操作
        :param target: 可选回收目标，若为None则全局回收
        :return: 是否回收成功
        """
        try:
            self.logger.info("开始回收操作，目标：%s", target if target else "全局")
            # 实际回收逻辑占位（未来实现）
            # 模拟回收过程
            self._status["recycled_count"] += 1
            self._status["last_recycle_time"] = "now_placeholder"
            self.logger.info("回收操作完成")
            return True
        except Exception as e:
            self.logger.error("回收操作失败: %s\n%s", e, traceback.format_exc())
            return False

    def reset(self):
        """重置系统内部状态（例如清空回收计数器）"""
        self.logger.info("重置回收系统状态")
        self._status["recycled_count"] = 0
        self._status["last_recycle_time"] = None

    def get_status(self) -> Dict[str, Any]:
        """返回当前回收系统状态"""
        return self._status.copy()

    def reload_config(self, new_config: Dict[str, Any]):
        """
        热更新配置，重新初始化部分参数
        :param new_config: 新的配置字典
        """
        if self._config.get("hot_reload", False):
            self.logger.info("热更新配置...")
            self._config.update(new_config)
            self._validate_config()
            self._setup_logging()
            self.logger.info("配置热更新完成")
        else:
            self.logger.warning("热更新未启用，配置未生效")

    def __repr__(self):
        return f"<RecycleSystem status={self._status}>"

# 自测
if __name__ == "__main__":
    # 测试1：默认初始化
    sys_recycle = RecycleSystem()
    print("初始状态：", sys_recycle.get_status())

    # 测试2：回收操作
    success = sys_recycle.recycle("test_node")
    print("回收结果：", success)
    print("回收后状态：", sys_recycle.get_status())

    # 测试3：重置
    sys_recycle.reset()
    print("重置后状态：", sys_recycle.get_status())

    # 测试4：配置化与热更新
    config = {
        "log_level": "DEBUG",
        "recycle_threshold": 500,
        "enable_auto_recycle": True,
        "hot_reload": True
    }
    sys_recycle2 = RecycleSystem(config)
    sys_recycle2.recycle()
    # 热更新
    new_config = {"log_level": "WARNING"}
    sys_recycle2.reload_config(new_config)
    print("热更新后配置：", sys_recycle2._config)