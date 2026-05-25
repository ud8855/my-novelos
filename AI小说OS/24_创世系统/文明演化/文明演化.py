# -*- coding: utf-8 -*-
"""
模块：文明演化
路径：24_创世系统/文明演化/文明演化.py
职责：定义文明演化的核心骨架，负责调度演化策略，记录演化日志，提供可插拔的扩展机制。
依赖：配置模块（若需要），日志系统（内建logging）
被调用：创世系统主流程、世界推进服务
解决：为AI小说生成动态的文明发展过程，避免硬编码，支持策略热插拔和配置化驱动。
"""

import logging
import importlib
from typing import Dict, List, Callable, Optional

class CivilizationEvolution:
    """文明演化引擎，可配置、可插拔、支持日志记录。"""

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化演化引擎
        :param config: 配置字典，可包含日志级别、策略列表、演化参数等
        """
        self.config = config if config else {}
        self.logger = self._setup_logger()
        self.strategies: List[Callable] = []
        self._load_strategies()
        self.logger.info("文明演化引擎初始化完成")

    def _setup_logger(self) -> logging.Logger:
        """配置日志记录器"""
        log_level = self.config.get("log_level", logging.INFO)
        logger = logging.getLogger("CivilizationEvolution")
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        if not logger.handlers:
            logger.addHandler(handler)
        logger.setLevel(log_level)
        return logger

    def _load_strategies(self):
        """
        从配置加载演化策略。
        配置中应包含 "strategies" 键，值为策略模块路径列表（字符串）。
        例：["24_创世系统.文明演化.strategies.科技跃进", "24_创世系统.文明演化.strategies.文化传播"]
        动态导入并实例化策略函数（预期为无参的可调用对象）。
        """
        strategy_paths = self.config.get("strategies", [])
        for path in strategy_paths:
            try:
                module_path, func_name = path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                strategy_func = getattr(module, func_name)
                if not callable(strategy_func):
                    self.logger.warning(f"策略 {path} 不是可调用对象，跳过")
                    continue
                self.strategies.append(strategy_func)
                self.logger.info(f"加载演化策略: {path}")
            except Exception as e:
                self.logger.error(f"加载策略 {path} 失败: {e}")

    def evolve(self, civilization_state: Dict) -> Dict:
        """
        执行文明演化流程

        :param civilization_state: 当前文明状态字典，包含科技、文化、经济、政治等指标
        :return: 演化后的文明状态字典（输入状态会被深度拷贝或原地修改取决于实现）
        """
        self.logger.debug("开始文明演化环节")
        original_state = civilization_state.copy()  # 保持原状态不变，生成新状态
        current_state = original_state

        for idx, strategy in enumerate(self.strategies):
            try:
                self.logger.debug(f"执行策略 {idx+1}/{len(self.strategies)}")
                # 策略函数签名: (state: Dict) -> Dict
                current_state = strategy(current_state)
                self.logger.debug(f"策略 {idx+1} 执行完毕")
            except Exception as e:
                self.logger.error(f"策略 {idx+1} 执行异常: {e}，跳过并继续")
                continue

        self.logger.info("文明演化完成")
        return current_state

    def add_strategy(self, strategy: Callable):
        """运行时动态添加演化策略（热插拔）"""
        if callable(strategy):
            self.strategies.append(strategy)
            self.logger.info(f"动态添加策略: {strategy.__name__}")
        else:
            self.logger.warning("尝试添加非可调用对象为策略，已忽略")

    def remove_strategy(self, strategy_name: str):
        """运行时移除演化策略（通过函数名）"""
        before = len(self.strategies)
        self.strategies = [s for s in self.strategies if getattr(s, "__name__", "") != strategy_name]
        if len(self.strategies) < before:
            self.logger.info(f"移除策略: {strategy_name}")
        else:
            self.logger.warning(f"未找到策略: {strategy_name}")


# ------------------ 自测代码 ------------------
if __name__ == "__main__":
    # 模拟配置
    config = {
        "log_level": logging.DEBUG,
        "strategies": []  # 初始无策略，演示动态添加
    }

    # 定义简单的测试策略（实际应从外部模块加载）
    def demo_tech_boost(state: Dict) -> Dict:
        """测试策略：科技增长"""
        state["technology"] = state.get("technology", 0) + 1
        return state

    def demo_culture_spread(state: Dict) -> Dict:
        """测试策略：文化传播"""
        state["culture"] = state.get("culture", 0) + 2
        return state

    # 创建演化引擎
    evo = CivilizationEvolution(config)

    # 初始文明状态
    initial_state = {
        "name": "测试文明",
        "technology": 5,
        "culture": 3,
        "population": 1000
    }
    print("初始状态:", initial_state)

    # 动态添加策略
    evo.add_strategy(demo_tech_boost)
    evo.add_strategy(demo_culture_spread)

    # 执行演化
    new_state = evo.evolve(initial_state)
    print("演化后状态:", new_state)

    # 测试移除策略
    evo.remove_strategy("demo_tech_boost")
    print("移除科技策略后:", evo.strategies)

    # 再次演化
    state2 = evo.evolve({"technology": 10, "culture": 5})
    print("仅文化演化后:", state2)