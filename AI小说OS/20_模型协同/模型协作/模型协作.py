#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
20_模型协同/模型协作/模型协作.py
层级: 20_模型协同
依赖: config_loader, 日志系统, 模型注册中心(接口)
被调用: 上层协同引擎, 任务调度器, 对话管理器
解决: 多模型协作的注册、调度、通信与管理
"""

import abc
import logging
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field

# 假设存在一个全局配置加载器，此处仅声明接口
try:
    from config_loader import get_config
except ImportError:
    def get_config():
        return {}

# 日志对象
logger = logging.getLogger(__name__)


# ---------- 配置数据类 ----------
@dataclass
class ModelCapability:
    """单个模型的能力描述"""
    model_id: str
    provider: str
    task_types: List[str] = field(default_factory=list)
    max_context: int = 2048
    priority: int = 0


@dataclass
class CollaborationConfig:
    """协作配置"""
    max_concurrent_models: int = 3
    timeout_seconds: int = 30
    retry_count: int = 2
    enable_monitor: bool = True
    models: Dict[str, ModelCapability] = field(default_factory=dict)


# ---------- 模型协作接口 ----------
class BaseModelAdapter(abc.ABC):
    """模型适配器基类，所有第三方模型封装必须实现"""
    @abc.abstractmethod
    def generate(self, prompt: str, context: Optional[Dict] = None) -> str:
        """执行单次生成"""
        ...

    @abc.abstractmethod
    async def generate_async(self, prompt: str, context: Optional[Dict] = None) -> str:
        """异步生成"""
        ...

    @abc.abstractmethod
    def get_capability(self) -> ModelCapability:
        """返回模型能力描述"""
        ...


class CollaborationBus:
    """
    模型协作总线
    负责注册模型适配器、路由任务、监控状态
    """
    def __init__(self, config: Optional[CollaborationConfig] = None):
        self._lock = threading.RLock()
        self._adapters: Dict[str, BaseModelAdapter] = {}
        self._task_history: List[Dict[str, Any]] = []
        self.config = config or CollaborationConfig()
        logger.info("CollaborationBus 初始化完成")

    def register_adapter(self, model_id: str, adapter: BaseModelAdapter):
        """注册一个模型适配器（热插拔支持）"""
        with self._lock:
            if model_id in self._adapters:
                logger.warning(f"模型 {model_id} 已存在，将覆盖")
            self._adapters[model_id] = adapter
            logger.info(f"模型 {model_id} 注册成功")

    def unregister_adapter(self, model_id: str):
        """注销适配器"""
        with self._lock:
            if model_id in self._adapters:
                del self._adapters[model_id]
                logger.info(f"模型 {model_id} 已注销")

    def get_adapter(self, model_id: str) -> Optional[BaseModelAdapter]:
        """获取适配器"""
        return self._adapters.get(model_id)

    def select_model(self, task_type: str) -> Optional[str]:
        """根据任务类型选择最合适的模型（简单优先级路由）"""
        candidates = []
        for mid, adp in self._adapters.items():
            cap = adp.get_capability()
            if task_type in cap.task_types:
                candidates.append((cap.priority, mid))
        if not candidates:
            logger.error(f"没有可用模型处理任务类型: {task_type}")
            return None
        # 按优先级排序，返回最高优先级
        candidates.sort(reverse=True)
        selected = candidates[0][1]
        logger.debug(f"为任务 {task_type} 选择模型 {selected}")
        return selected

    def execute_collaboration(self, task: Dict[str, Any]) -> Any:
        """
        执行协作任务
        task结构示例:
        {
            "task_type": "outline_generation",
            "payload": {"theme": "...", "length": 1000},
            "collaboration_mode": "sequential" / "parallel"
        }
        """
        mode = task.get("collaboration_mode", "sequential")
        if mode == "sequential":
            return self._run_sequential(task)
        else:
            return self._run_parallel(task)

    def _run_sequential(self, task: Dict[str, Any]) -> List[Any]:
        """顺序执行（一个模型输出作为下个模型输入）"""
        results = []
        steps = task.get("steps", [task])
        for step in steps:
            model_id = self.select_model(step.get("task_type"))
            if not model_id:
                raise RuntimeError(f"无可用模型执行步骤: {step}")
            adapter = self.get_adapter(model_id)
            try:
                output = adapter.generate(
                    prompt=step.get("prompt", ""),
                    context=step.get("context")
                )
                results.append(output)
                # 更新上下文
                step["context"] = {"previous_output": output}
            except Exception as e:
                logger.exception(f"模型 {model_id} 执行失败")
                raise e
        return results

    def _run_parallel(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """并行执行多个子任务（简化版，实际需线程池）"""
        subtasks = task.get("subtasks", [])
        results = {}
        threads = []
        def worker(sub, idx):
            mid = self.select_model(sub.get("task_type"))
            if not mid:
                results[idx] = None
                return
            adapter = self.get_adapter(mid)
            try:
                results[idx] = adapter.generate(
                    prompt=sub.get("prompt", ""),
                    context=sub.get("context")
                )
            except Exception as e:
                logger.error(f"并行子任务 {idx} 失败: {e}")
                results[idx] = None

        for i, sub in enumerate(subtasks):
            t = threading.Thread(target=worker, args=(sub, i))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
        return results

    def health_check(self) -> Dict[str, bool]:
        """检查所有注册模型健康状态"""
        status = {}
        for mid, adp in self._adapters.items():
            try:
                # 简单调用测试
                test_output = adp.generate("ping", {})
                status[mid] = bool(test_output)
            except Exception:
                status[mid] = False
        return status


# ---------- 自测代码 ----------
if __name__ == "__main__":
    import sys

    # 配置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)

    # 模拟一个适配器
    class MockAdapter(BaseModelAdapter):
        def __init__(self, model_id, task_types):
            self._cap = ModelCapability(model_id=model_id, task_types=task_types)

        def generate(self, prompt, context=None):
            logger.debug(f"Mock {self._cap.model_id} 生成中...")
            return f"Mock response from {self._cap.model_id}"

        async def generate_async(self, prompt, context=None):
            return self.generate(prompt, context)

        def get_capability(self):
            return self._cap

    # 创建协作总线
    bus = CollaborationBus()

    # 注册两个模型
    bus.register_adapter("model_A", MockAdapter("model_A", ["outline", "dialogue"]))
    bus.register_adapter("model_B", MockAdapter("model_B", ["revision", "dialogue"]))

    # 选择模型测试
    selected = bus.select_model("outline")
    print(f"选择模型: {selected}")

    # 顺序协作测试
    task = {
        "task_type": "outline",
        "prompt": "生成故事大纲",
        "collaboration_mode": "sequential"
    }
    result = bus.execute_collaboration(task)
    print(f"顺序结果: {result}")

    # 并行测试
    task2 = {
        "collaboration_mode": "parallel",
        "subtasks": [
            {"task_type": "dialogue", "prompt": "对话1"},
            {"task_type": "revision", "prompt": "修订1"}
        ]
    }
    result2 = bus.execute_collaboration(task2)
    print(f"并行结果: {result2}")

    # 健康检查
    print(f"健康状态: {bus.health_check()}")

    # 热插拔: 注销一个模型
    bus.unregister_adapter("model_A")
    print(f"注销后适配器: {list(bus._adapters.keys())}")

    print("模型协作自测完成")