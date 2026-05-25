"""
生命周期管理模块 - 内核系统
负责统一管理核心组件的启动、运行、停止、状态监控和优雅降级。
可插拔设计：通过抽象基类定义生命周期接口，支持任意组件注册。
配置化：通过配置字典指定组件列表和参数。
日志：使用标准logging记录所有生命周期事件。
"""
import logging
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from enum import Enum, auto

# 配置默认日志，外部可通过getLogger自定义
logger = logging.getLogger("LifecycleManager")


class LifecycleState(Enum):
    """组件生命周期状态枚举"""
    UNINITIALIZED = auto()
    INITIALIZED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    STOPPED = auto()
    ERROR = auto()


class LifecycleAware(ABC):
    """可插拔组件的生命周期接口定义（抽象基类）。
    任何需要被生命周期管理器接管的组件都必须实现该接口。
    """
    @abstractmethod
    def init(self, config: Dict[str, Any]) -> None:
        """初始化组件，准备资源但不应启动服务"""
        ...

    @abstractmethod
    def start(self) -> None:
        """启动组件，使服务可用"""
        ...

    @abstractmethod
    def stop(self) -> None:
        """停止组件，释放资源，优雅关闭"""
        ...

    @abstractmethod
    def status(self) -> LifecycleState:
        """返回当前组件状态"""
        ...

    @property
    def name(self) -> str:
        """组件名称，用于日志和标识"""
        return self.__class__.__name__


class LifecycleManager:
    """核心生命周期管理器，负责注册、启动、停止、监控所有组件。
    支持配置化加载组件列表，支持热更新和异常恢复策略。
    """
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化管理器
        :param config: 字典配置，必须包含 components 键，格式如：
            {
                "components": [
                    {"name": "MemoryCore", "class": "some.module.ClassName", "params": {...}},
                    ...
                ]
            }
        """
        self._components: Dict[str, LifecycleAware] = {}
        self._states: Dict[str, LifecycleState] = {}
        self._lock = threading.RLock()
        self._config = config or {}
        self._global_state = LifecycleState.UNINITIALIZED
        logger.info("生命周期管理器已创建")

    def load_components_from_config(self) -> None:
        """根据配置动态加载组件实例。要求每个组件类都实现 LifecycleAware 接口。"""
        if not self._config or "components" not in self._config:
            logger.warning("配置中未找到组件定义，跳过加载")
            return

        for comp_cfg in self._config["components"]:
            name = comp_cfg.get("name")
            class_path = comp_cfg.get("class")
            params = comp_cfg.get("params", {})
            if not name or not class_path:
                logger.error(f"组件配置不完整: {comp_cfg}")
                continue
            try:
                # 动态导入类 (示例：不真正执行，此处保持骨架)
                # module_path, class_name = class_path.rsplit(".", 1)
                # mod = __import__(module_path, fromlist=[class_name])
                # cls = getattr(mod, class_name)
                # instance = cls()
                # 由于是骨架，直接抛异常提示开发
                raise NotImplementedError("动态组件加载需实现具体导入逻辑")
                # 假定实例化成功
                instance: LifecycleAware = None  # 占位
                self.register(name, instance)
                logger.info(f"组件 '{name}' 已从配置加载")
            except Exception as e:
                logger.error(f"加载组件 '{name}' 失败: {e}")

    def register(self, name: str, component: LifecycleAware) -> None:
        """注册单个生命周期组件"""
        with self._lock:
            if not isinstance(component, LifecycleAware):
                raise TypeError(f"组件 '{name}' 必须实现 LifecycleAware 接口")
            if name in self._components:
                logger.warning(f"组件 '{name}' 已存在，将被覆盖")
            self._components[name] = component
            self._states[name] = LifecycleState.UNINITIALIZED
            logger.info(f"组件注册成功: {name}")

    def unregister(self, name: str) -> None:
        """移除组件，如果组件正在运行则先停止它"""
        with self._lock:
            if name not in self._components:
                logger.warning(f"组件 '{name}' 不存在，无法注销")
                return
            comp = self._components[name]
            state = self._states[name]
            if state in (LifecycleState.STARTING, LifecycleState.RUNNING):
                self._stop_component(name, comp)
            del self._components[name]
            del self._states[name]
            logger.info(f"组件 '{name}' 已注销")

    def _stop_component(self, name: str, comp: LifecycleAware) -> None:
        """内部停止组件，处理异常"""
        try:
            self._update_state(name, LifecycleState.STOPPING)
            comp.stop()
            self._update_state(name, LifecycleState.STOPPED)
            logger.info(f"组件 '{name}' 已停止")
        except Exception as e:
            self._update_state(name, LifecycleState.ERROR)
            logger.error(f"停止组件 '{name}' 时发生异常: {e}", exc_info=True)

    def _update_state(self, name: str, state: LifecycleState) -> None:
        """更新组件状态，线程安全"""
        with self._lock:
            self._states[name] = state

    def start_all(self) -> None:
        """按顺序启动所有已注册组件（先初始化后启动）"""
        logger.info("开始启动所有组件...")
        if not self._components:
            logger.warning("没有注册任何组件，启动结束")
            return
        self._global_state = LifecycleState.STARTING

        # 为了简单，先全部初始化，再全部启动（实际可能需要依赖顺序，这里骨架不处理）
        for name, comp in self._components.items():
            try:
                logger.info(f"初始化组件: {name}")
                self._update_state(name, LifecycleState.INITIALIZED)
                comp.init(self._config.get("component_params", {}).get(name, {}))
            except Exception as e:
                self._update_state(name, LifecycleState.ERROR)
                logger.error(f"初始化组件 '{name}' 失败: {e}", exc_info=True)
                # 策略：选择继续启动其他组件，但标记全局状态异常
                self._global_state = LifecycleState.ERROR

        for name, comp in self._components.items():
            if self._states[name] == LifecycleState.INITIALIZED:
                try:
                    self._update_state(name, LifecycleState.STARTING)
                    comp.start()
                    self._update_state(name, LifecycleState.RUNNING)
                    logger.info(f"组件 '{name}' 启动成功")
                except Exception as e:
                    self._update_state(name, LifecycleState.ERROR)
                    logger.error(f"启动组件 '{name}' 失败: {e}", exc_info=True)
                    self._global_state = LifecycleState.ERROR

        if self._global_state != LifecycleState.ERROR:
            self._global_state = LifecycleState.RUNNING
            logger.info("所有组件启动完成")

    def stop_all(self, graceful_timeout: float = 5.0) -> None:
        """停止所有运行中的组件，支持超时控制"""
        logger.info("开始停止所有组件...")
        self._global_state = LifecycleState.STOPPING
        # 反向停止？骨架简单顺序停止
        for name in list(self._components.keys()):
            comp = self._components[name]
            state = self._states[name]
            if state == LifecycleState.RUNNING:
                # 可以加入超时逻辑，此处省略
                self._stop_component(name, comp)
        self._global_state = LifecycleState.STOPPED
        logger.info("所有组件已停止")

    def restart(self, name: str = None) -> None:
        """重启指定组件或所有组件"""
        if name:
            with self._lock:
                if name not in self._components:
                    raise KeyError(f"组件 '{name}' 不存在")
                comp = self._components[name]
                state = self._states[name]
                if state == LifecycleState.RUNNING:
                    self._stop_component(name, comp)
                # 重新初始化并启动
                comp.init(self._config.get("component_params", {}).get(name, {}))
                self._update_state(name, LifecycleState.INITIALIZED)
                comp.start()
                self._update_state(name, LifecycleState.RUNNING)
                logger.info(f"组件 '{name}' 重启完成")
        else:
            logger.info("执行全部组件重启")
            self.stop_all()
            self.start_all()

    def status_report(self) -> Dict[str, str]:
        """返回所有组件的状态报告"""
        with self._lock:
            report = {}
            for name, state in self._states.items():
                report[name] = state.name
            report["__global__"] = self._global_state.name
            return report

    def get_component_status(self, name: str) -> LifecycleState:
        """获取单个组件状态"""
        with self._lock:
            if name not in self._states:
                raise KeyError(f"组件 '{name}' 未注册")
            return self._states[name]

    @property
    def global_state(self) -> LifecycleState:
        return self._global_state


# ============ 自测代码 ============
if __name__ == "__main__":
    # 配置日志输出到控制台
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 实现一个简单的测试组件
    class TestComponent(LifecycleAware):
        def __init__(self):
            self._state = LifecycleState.UNINITIALIZED

        def init(self, config: Dict[str, Any]) -> None:
            self._state = LifecycleState.INITIALIZED
            logger.info(f"{self.name} 初始化完成，参数: {config}")

        def start(self) -> None:
            self._state = LifecycleState.RUNNING
            logger.info(f"{self.name} 已启动")

        def stop(self) -> None:
            self._state = LifecycleState.STOPPED
            logger.info(f"{self.name} 已停止")

        def status(self) -> LifecycleState:
            return self._state

        @property
        def name(self) -> str:
            return "TestComponent"

    # 创建管理器并注册组件
    mgr = LifecycleManager({"components": []})  # 不通过配置，手动注册测试
    test_comp = TestComponent()
    mgr.register("test", test_comp)

    # 测试启动
    mgr.start_all()
    print("Status:", mgr.status_report())

    # 测试重启单个组件
    mgr.restart("test")
    print("Status after restart:", mgr.status_report())

    # 测试停止
    mgr.stop_all()
    print("Final status:", mgr.status_report())