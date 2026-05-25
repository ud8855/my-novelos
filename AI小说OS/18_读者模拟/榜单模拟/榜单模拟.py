"""榜单模拟模块
层级：18_读者模拟/榜单模拟
依赖：外部配置(settings)、日志(logging)、可选依赖：模型协同层(未来)
功能：模拟读者在不同榜单(如畅销榜、推荐榜)下的行为反应，为小说创作提供读者视角的数据支撑。
可插拔设计：通过继承基类或实现接口来扩展具体榜单模拟逻辑，当前为骨架。
"""

import logging
from typing import Any, Dict, List, Optional, Type

# 配置相关的占位，实际中应从核心配置模块导入
class ConfigManager:
    """配置管理器占位，实际替换为统一配置模块"""
    @staticmethod
    def get(key: str, default=None):
        config = {
            "reader_agent_count": 100,
            "simulation_enabled": True,
            "ranking_types": ["bestseller", "recommendation"],
        }
        return config.get(key, default)

logger = logging.getLogger(__name__)

class RankingSimulator:
    """榜单模拟器基类，提供可插拔的榜单模拟能力"""

    def __init__(self, ranking_type: str, config: Optional[Dict[str, Any]] = None):
        self.ranking_type = ranking_type
        self.config = config or {}
        self.is_initialized = False
        self._init_config()
        self._setup_logging()
        self._initialize()

    def _init_config(self):
        """从配置文件中加载默认参数"""
        self.reader_count = self.config.get("reader_count", ConfigManager.get("reader_agent_count", 100))
        self.simulation_enabled = self.config.get("enabled", ConfigManager.get("simulation_enabled", True))
        logger.info(f"Config loaded for {self.ranking_type}: reader_count={self.reader_count}, enabled={self.simulation_enabled}")

    def _setup_logging(self):
        """配置日志记录器"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        if not logger.handlers:
            logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if self.config.get("debug", False) else logging.INFO)

    def _initialize(self):
        """子类可重写：执行特定榜单的初始化操作"""
        if self.simulation_enabled:
            self.is_initialized = True
            logger.info(f"RankingSimulator for '{self.ranking_type}' initialized.")
        else:
            logger.warning(f"Simulation is disabled for {self.ranking_type}.")

    def simulate(self, ranking_data: List[Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """核心模拟方法，必须被子类实现
        Args:
            ranking_data: 榜单数据，如小说列表及评分/销量等
            context: 额外上下文，例如当前时间、读者画像分布等
        Returns:
            模拟结果字典，包含行为统计等信息
        """
        if not self.is_initialized:
            raise RuntimeError("Simulator not initialized. Call _initialize() first.")
        logger.info(f"Simulating reader behavior for {self.ranking_type}...")
        # 这里仅返回空结果作为骨架，具体逻辑由子类覆盖
        return {
            "clicks": {},
            "read_ratio": {},
            "feedback": {}
        }

    def update_config(self, new_config: Dict[str, Any]):
        """热更新配置"""
        self.config.update(new_config)
        self._init_config()
        logger.info("Config updated via hot reload.")

    def shutdown(self):
        """清理资源，如关闭连接等"""
        logger.info(f"RankingSimulator '{self.ranking_type}' shutting down.")
        self.is_initialized = False


class BestsellerSimulator(RankingSimulator):
    """畅销榜模拟器实例，继承自RankingSimulator"""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("bestseller", config)

    def simulate(self, ranking_data: List[Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.is_initialized:
            raise RuntimeError("BestsellerSimulator not initialized.")
        logger.debug("Running bestseller simulation logic...")
        # TODO: 接入模型协同层生成模拟数据
        return super().simulate(ranking_data, context)


class RecommendationSimulator(RankingSimulator):
    """推荐榜模拟器实例"""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("recommendation", config)


# 自测代码
if __name__ == "__main__":
    # 测试基础骨架
    sim = BestsellerSimulator({"reader_count": 50, "debug": True})
    if sim.is_initialized:
        result = sim.simulate([{"novel_id": 1, "score": 9.5}])
        print("Simulation result:", result)
    # 测试热更新
    sim.update_config({"reader_count": 200})
    print(f"Updated reader_count: {sim.reader_count}")
    sim.shutdown()