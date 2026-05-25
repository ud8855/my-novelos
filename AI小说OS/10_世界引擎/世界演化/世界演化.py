# 文件: 10_世界引擎/世界演化/世界演化.py
# 描述: 世界演化模块骨架，可插拔的世界演化策略基类及默认实现
# 层: 10_世界引擎
# 依赖: 仅标准库 (logging, dataclasses)
# 被调用: 由世界引擎主控制器或调度器调用，推动世界状态动态变化

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Protocol, runtime_checkable


# ---------- 配置定义 ----------
@dataclass
class WorldEvolutionConfig:
    """
    世界演化配置类
    所有演化参数集中管理，支持配置热更新（可插拔）
    """
    time_step: int = 1                      # 每次演化的时间步长
    evolution_intensity: float = 0.5        # 演化强度系数
    enable_random_events: bool = True       # 是否启用随机事件
    random_event_probability: float = 0.1   # 随机事件触发概率
    max_iterations: int = 1000              # 单次演化最大迭代次数（安全限制）
    enable: bool = True                     # 是否启用演化功能


# ---------- 演化器协议（接口定义） ----------
@runtime_checkable
class WorldEvolutionProtocol(Protocol):
    """世界演化器协议，定义必须实现的接口"""
    def evolve(self, world_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行一次世界演化
        :param world_state: 当前完整世界状态字典
        :return: 演化后的世界状态字典
        """
        ...

    def shutdown(self) -> None:
        """优雅关闭，清理资源"""
        ...


# ---------- 基类实现 ----------
class BaseWorldEvolution:
    """世界演化基类，实现日志、配置加载等通用功能"""

    def __init__(self, config: Optional[WorldEvolutionConfig] = None):
        """
        初始化演化器
        :param config: 可选配置对象，若未提供则使用默认配置
        """
        self.config = config if config is not None else WorldEvolutionConfig()
        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        self.logger.info("演化器初始化完成，配置：%s", self.config)

    def evolve(self, world_state: Dict[str, Any]) -> Dict[str, Any]:
        """演化入口，子类必须重写"""
        raise NotImplementedError("子类必须实现 evolve 方法")

    def shutdown(self):
        """默认关闭操作，可被子类扩展"""
        self.logger.info("演化器 %s 正在关闭...", self.__class__.__name__)


# ---------- 默认演化器实现（示例/骨架） ----------
class DefaultWorldEvolution(BaseWorldEvolution):
    """默认的世界演化器，基于简单时间推进和示例逻辑"""

    def evolve(self, world_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行默认的世界演化：
        1. 推进世界时间
        2. 可选触发随机事件（根据配置概率）
        """
        self.logger.info("开始世界演化，时间步长=%d", self.config.time_step)

        if not self.config.enable:
            self.logger.info("演化功能已禁用，返回原状态")
            return world_state

        # 浅拷贝状态，避免直接修改原输入
        new_state = world_state.copy()

        # --- 核心演化逻辑占位 ---
        # 1. 时间推进
        current_time = world_state.get("time_elapsed", 0)
        new_state["time_elapsed"] = current_time + self.config.time_step

        # 2. 强度影响（示例：资源变化）
        # 实际业务逻辑可由子类或后续开发填充
        intensity = self.config.evolution_intensity
        new_state["global_stability"] = world_state.get("global_stability", 1.0) * (1 - 0.01 * intensity)

        # 3. 随机事件触发（占位）
        if self.config.enable_random_events:
            import random
            if random.random() < self.config.random_event_probability:
                self.logger.info("触发随机事件（占位逻辑）")
                # 实际事件处理将由事件系统完成
                new_state.setdefault("pending_events", []).append("random_event_placeholder")

        # 安全迭代计数（仅示例，真实场景中防止死循环）
        new_state["evolution_iteration"] = world_state.get("evolution_iteration", 0) + 1
        if new_state["evolution_iteration"] > self.config.max_iterations:
            self.logger.warning("演化迭代次数达到上限 %d，强制停止", self.config.max_iterations)

        self.logger.info("世界演化完成，当前时间刻度：%d", new_state["time_elapsed"])
        return new_state


# ---------- 自测入口 ----------
if __name__ == "__main__":
    # 配置基础日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=== 世界演化模块自测开始 ===")

    # 1. 测试配置类
    config = WorldEvolutionConfig(time_step=2, evolution_intensity=0.3)
    print("配置对象：", config)

    # 2. 测试默认演化器
    evolver = DefaultWorldEvolution(config)

    # 3. 构造初始世界状态
    initial_state = {
        "time_elapsed": 0,
        "regions": ["大陆A", "大陆B"],
        "global_stability": 1.0,
        "pending_events": [],
    }
    print("初始状态：", initial_state)

    # 4. 执行演化
    evolved_state = evolver.evolve(initial_state)
    print("演化后状态：", evolved_state)

    # 5. 再次演化，验证累计效果
    evolved_state2 = evolver.evolve(evolved_state)
    print("二次演化状态：", evolved_state2)

    # 6. 测试关闭
    evolver.shutdown()

    # 7. 测试协议检查
    assert isinstance(evolver, WorldEvolutionProtocol), "未实现WorldEvolutionProtocol协议"
    print("协议检查通过")

    print("=== 自测完成 ===")