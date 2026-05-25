""" 
自动优化模块 - AutoOptimizer
位于：29_自学习系统/自动优化
职责：收集使用反馈、分析性能数据、生成优化建议、自动调整内部参数
依赖：配置中心、日志系统、数据库适配器、事件总线
被调用：Runtime调度器定时激发，或事件触发
"""
import logging
import threading
from typing import Dict, Any, Optional, List

# 配置默认值（可通过外部配置覆盖）
DEFAULT_CONFIG = {
    "enable_auto_optimize": True,
    "optimize_interval_minutes": 60,
    "max_feedback_samples": 1000,
    "analysis_threshold": 100,
    "optimizer_type": "basic",  # basic, advanced, ml
    "log_level": "INFO"
}

class AutoOptimizer:
    """自学习系统：自动优化引擎"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, event_bus=None, db_adapter=None):
        """
        初始化自动优化器
        :param config: 覆盖默认配置的字典
        :param event_bus: 事件总线（用于订阅/发布事件）
        :param db_adapter: 数据库适配器（用于存储反馈和状态）
        """
        self._config = DEFAULT_CONFIG.copy()
        if config:
            self._config.update(config)
        self._event_bus = event_bus
        self._db = db_adapter
        self._feedback_queue = []
        self._lock = threading.Lock()
        self._optimization_running = False
        self._thread = None
        
        # 配置日志
        self._logger = logging.getLogger("AutoOptimizer")
        log_level = getattr(logging, self._config["log_level"].upper(), logging.INFO)
        self._logger.setLevel(log_level)
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
            
        self._logger.info("自动优化器初始化完成，配置：%s", self._config)
        
        # 注册事件监听（如果有事件总线）
        if self._event_bus:
            self._event_bus.subscribe("user_feedback", self.on_user_feedback)
            self._event_bus.subscribe("generation_metrics", self.on_generation_metrics)
            self._event_bus.subscribe("system_health", self.on_system_health_check)
        
        # 如果启用自动优化，启动定时器
        if self._config["enable_auto_optimize"]:
            self.start_optimization_scheduler()
    
    # ---------- 核心接口 ----------
    
    def record_feedback(self, feedback_type: str, data: Dict[str, Any]) -> bool:
        """
        记录一条反馈数据（用户反馈、内部指标等）
        :param feedback_type: 反馈类型，如 "rating", "correction", "latency"
        :param data: 反馈数据体
        :return: 是否成功记录
        """
        with self._lock:
            entry = {"type": feedback_type, "data": data, "timestamp": logging.Formatter().formatTime(logging.LogRecord("","",0,0,"",(),None))}
            self._feedback_queue.append(entry)
            # 保持最大样本量
            if len(self._feedback_queue) > self._config["max_feedback_samples"]:
                self._feedback_queue.pop(0)
        self._logger.debug("记录反馈：类型=%s，数据=%s", feedback_type, data)
        if self._db:
            try:
                self._db.insert_feedback(feedback_type, data)
            except Exception as e:
                self._logger.warning("持久化反馈失败：%s", e)
        return True
    
    def analyze(self) -> Dict[str, Any]:
        """
        分析当前累积的反馈数据，生成统计报告与优化建议
        :return: 分析结果字典
        """
        with self._lock:
            queue = list(self._feedback_queue)
        if len(queue) < self._config["analysis_threshold"]:
            return {"status": "insufficient_data", "samples": len(queue)}
        
        # 简单分析示例（可根据优化器类型扩展）
        analysis = {
            "total_samples": len(queue),
            "types_distribution": {},
            "average_metrics": {},
            "recommendations": []
        }
        type_counts = {}
        for entry in queue:
            t = entry["type"]
            type_counts[t] = type_counts.get(t, 0) + 1
        analysis["types_distribution"] = type_counts
        
        # 根据优化器类型进行更深入分析
        if self._config["optimizer_type"] == "basic":
            # 基础分析：仅统计分布
            analysis["recommendations"] = self._basic_recommendations(queue)
        elif self._config["optimizer_type"] == "advanced":
            # 高级分析：可引入加权、趋势等
            analysis["recommendations"] = self._advanced_recommendations(queue)
        elif self._config["optimizer_type"] == "ml":
            # 机器学习分析：加载外部模型（未来扩展）
            analysis["recommendations"] = self._ml_recommendations(queue)
        
        self._logger.info("反馈分析完成：%d 样本", len(queue))
        return analysis
    
    def optimize(self) -> bool:
        """
        根据分析结果执行优化动作（例如调整内部参数）
        :return: 是否执行了优化
        """
        if self._optimization_running:
            self._logger.warning("优化已在运行中，拒绝重复触发")
            return False
        
        self._optimization_running = True
        try:
            analysis = self.analyze()
            if analysis.get("status") == "insufficient_data":
                self._logger.info("数据不足，跳过优化")
                return False
            
            # 获取建议并应用
            recommendations = analysis.get("recommendations", [])
            applied = False
            for rec in recommendations:
                if self._apply_recommendation(rec):
                    applied = True
            if applied:
                self._logger.info("优化执行完毕")
                # 发布优化完成事件
                if self._event_bus:
                    self._event_bus.publish("optimization_completed", {"recommendations": recommendations})
            return applied
        except Exception as e:
            self._logger.error("优化过程异常：%s", e, exc_info=True)
            return False
        finally:
            self._optimization_running = False
    
    def start_optimization_scheduler(self):
        """启动定时优化计划"""
        if self._thread and self._thread.is_alive():
            self._logger.info("优化调度器已在运行")
            return
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True, name="OptimizationScheduler")
        self._thread.start()
        self._logger.info("优化调度器已启动，间隔 %d 分钟", self._config["optimize_interval_minutes"])
    
    def stop_optimization_scheduler(self):
        """停止定时优化"""
        self._config["enable_auto_optimize"] = False
        self._logger.info("优化调度器已请求停止")
    
    def get_status(self) -> Dict[str, Any]:
        """获取优化器当前状态"""
        return {
            "active": self._config["enable_auto_optimize"],
            "queue_size": len(self._feedback_queue),
            "config": self._config
        }
    
    # ---------- 事件处理 ----------
    
    def on_user_feedback(self, event_data: Dict[str, Any]):
        """事件回调：用户反馈"""
        self.record_feedback("user_feedback", event_data)
    
    def on_generation_metrics(self, event_data: Dict[str, Any]):
        """事件回调：生成指标"""
        self.record_feedback("generation_metrics", event_data)
    
    def on_system_health_check(self, event_data: Dict[str, Any]):
        """事件回调：系统健康状态"""
        self.record_feedback("system_health", event_data)
    
    # ---------- 内部方法 ----------
    
    def _scheduler_loop(self):
        """定时器循环"""
        import time
        while self._config["enable_auto_optimize"]:
            next_interval = self._config["optimize_interval_minutes"] * 60
            time.sleep(next_interval)
            if self._config["enable_auto_optimize"]:
                self._logger.debug("定时优化触发")
                self.optimize()
    
    def _basic_recommendations(self, queue: List[Dict]) -> List[str]:
        """基础推荐：示例实现，可被重写"""
        return ["basic_optimization_default"]
    
    def _advanced_recommendations(self, queue: List[Dict]) -> List[str]:
        """高级推荐：示例实现"""
        # 这里可以引入更复杂的统计
        return ["advanced_optimization_placeholder"]
    
    def _ml_recommendations(self, queue: List[Dict]) -> List[str]:
        """机器学习推荐：未来扩展"""
        # 可加载外部模型进行预测
        return ["ml_optimization_not_implemented"]
    
    def _apply_recommendation(self, recommendation: str) -> bool:
        """
        应用一条优化建议（示例）
        :return: 是否应用成功
        """
        self._logger.info("正在应用优化建议：%s", recommendation)
        # 这里根据建议键，修改对应系统参数
        # 实际实现需要与配置管理模块交互
        return True


# ---------- 自测代码 ----------
if __name__ == "__main__":
    # 配置日志输出
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 创建优化器实例（无真实依赖，使用默认配置）
    optimizer = AutoOptimizer(config={"optimize_interval_minutes": 0.1, "analysis_threshold": 5})
    
    # 模拟记录反馈
    for i in range(6):
        optimizer.record_feedback("rating", {"score": 4, "chapter": f"ch_{i}"})
    optimizer.record_feedback("latency", {"value": 0.23})
    
    # 手动触发分析
    analysis = optimizer.analyze()
    print("分析结果：", analysis)
    
    # 触发一次优化
    optimizer.optimize()
    
    # 获取状态
    print("状态：", optimizer.get_status())
    
    # 停止调度（自测中不会真正阻塞，因为daemon线程）
    optimizer.stop_optimization_scheduler()
    print("自测完成")