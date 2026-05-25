"""
爽点规划模块
层级：14_规划系统/爽点规划
依赖：基础配置与日志模块（config.py, logger.py），可能依赖 82_爽点库/ 和 剧情管理器（15_剧情系统/）
被调用者：上游规划模块（如剧情大纲生成、节奏控制），在生成具体章节或段落时调用，确保爽点密度和类型满足需求。
解决问题：根据小说类型、当前上下文、读者偏好，规划爽点的类型、位置、强度和组合，输出爽点计划，供后续写作执行。
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import yaml
import os

# 默认配置（可通过外部yaml覆盖）
DEFAULT_CONFIG = {
    "log_level": "INFO",
    "default_pleasure_density": 3,  # 每千字爽点数量
    "pleasure_types": ["打脸", "升级", "获得宝物", "感情互动", "冲突爆发", "隐藏伏笔揭示"],
    "default_type_weights": {
        "打脸": 0.3,
        "升级": 0.2,
        "获得宝物": 0.15,
        "感情互动": 0.15,
        "冲突爆发": 0.1,
        "隐藏伏笔揭示": 0.1
    },
    "emotional_curve": "standard",  # 标准情绪曲线类型
    "allow_auto_adjust": True
}

class IPleasurePointPlanner(ABC):
    """爽点规划器抽象接口，实现可插拔"""
    
    @abstractmethod
    def load_config(self, config_path: Optional[str] = None) -> None:
        """加载配置"""
        pass
    
    @abstractmethod
    def plan(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        根据上下文规划爽点序列
        :param context: 包含小说类型、章节概要、当前字数、已有情节、目标读者等信息
        :return: 爽点计划列表，每个爽点包括类型、强度、位置（字数范围）、可能梗概等
        """
        pass
    
    @abstractmethod
    def adjust_dynamically(self, current_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        根据写作进度和反馈动态调整爽点计划
        """
        pass

class PleasurePointPlanner(IPleasurePointPlanner):
    """爽点规划标准实现"""
    
    def __init__(self, config: Optional[Dict] = None, logger: Optional[logging.Logger] = None):
        """
        初始化规划器
        :param config: 配置字典，若为None则使用默认配置
        :param logger: 外部传入的logger，若为None则自己创建
        """
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        self._init_logger(logger)
        self.logger.info("PleasurePointPlanner 初始化完成")
    
    def _init_logger(self, logger: Optional[logging.Logger] = None):
        """配置日志"""
        if logger:
            self.logger = logger
        else:
            self.logger = logging.getLogger(self.__class__.__name__)
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                self.logger.setLevel(getattr(logging, self.config.get("log_level", "INFO")))
    
    def load_config(self, config_path: Optional[str] = None) -> None:
        """从yaml文件加载配置并合并到当前配置"""
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    loaded = yaml.safe_load(f)
                if loaded:
                    self.config.update(loaded)
                    self.logger.info(f"配置已从 {config_path} 加载并合并")
                else:
                    self.logger.warning("配置文件为空，使用现有配置")
            except Exception as e:
                self.logger.error(f"加载配置文件失败: {e}，使用现有配置")
        elif config_path:
            self.logger.warning(f"配置文件 {config_path} 不存在，使用现有配置")
    
    def plan(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        爽点规划主逻辑
        基于上下文信息，按照配置的密度和权重生成爽点序列
        """
        self.logger.info("开始爽点规划")
        self.logger.debug(f"输入上下文: {context}")
        
        # 从配置获取参数
        density = context.get("pleasure_density", self.config["default_pleasure_density"])
        type_weights = context.get("type_weights", self.config["default_type_weights"])
        types = self.config["pleasure_types"]
        emotional_curve = context.get("emotional_curve", self.config["emotional_curve"])
        word_count = context.get("total_words", 3000)  # 假设本章节字数
        
        # 简单规划算法：根据密度和字数计算爽点数量，按权重分配类型
        number_of_points = max(1, int(word_count / 1000 * density))
        plan = []
        
        # 根据类型权重随机选择爽点类型（简化版，实际应更复杂）
        import random
        for i in range(number_of_points):
            # 简单随机按权重选类型
            chosen_type = self._weighted_choice(type_weights)
            position = (i * word_count // number_of_points, (i + 1) * word_count // number_of_points)
            point = {
                "index": i,
                "type": chosen_type,
                "intensity": random.uniform(0.5, 1.0),  # 强度随机，后续可优化
                "position": position,  # 字数范围
                "description": f"{chosen_type}爽点",
                "status": "planned"
            }
            plan.append(point)
        
        self.logger.info(f"规划完成，共生成 {len(plan)} 个爽点")
        return plan
    
    def adjust_dynamically(self, current_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """动态调整爽点计划（占位实现）"""
        self.logger.info("动态调整爽点计划")
        if not self.config.get("allow_auto_adjust", True):
            self.logger.info("自动调整已禁用")
            return current_state.get("existing_plan", [])
        
        # TODO: 根据当前写作进度、读者反馈、情绪曲线实现增量调整
        # 目前只是返回原计划，等待后续完善
        return current_state.get("existing_plan", [])
    
    def _weighted_choice(self, weights: Dict[str, float]) -> str:
        """根据权重字典随机返回一个键"""
        import random
        total = sum(weights.values())
        r = random.uniform(0, total)
        upto = 0.0
        for choice, weight in weights.items():
            upto += weight
            if upto >= r:
                return choice
        # fallback
        return list(weights.keys())[-1]

# 自测代码
if __name__ == "__main__":
    # 设置基础日志
    logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')
    
    planner = PleasurePointPlanner()
    # 加载外部配置（可选）
    planner.load_config("conf/pleasure_planner.yaml")  # 不存在则忽略
    
    # 模拟上下文
    test_context = {
        "total_words": 5000,
        "pleasure_density": 4,
        "type_weights": {
            "打脸": 0.4,
            "升级": 0.2,
            "获得宝物": 0.1,
            "感情互动": 0.1,
            "冲突爆发": 0.1,
            "隐藏伏笔揭示": 0.1
        },
        "emotional_curve": "rising"
    }
    
    plan = planner.plan(test_context)
    for p in plan:
        print(f"爽点{p['index']}: 类型={p['type']}, 位置={p['position']}, 强度={p['intensity']:.2f}")
    
    # 动态调整测试
    adjust_state = {
        "existing_plan": plan,
        "current_progress": {"written_words": 1500, "last_pleasure_point": 0}
    }
    adjusted = planner.adjust_dynamically(adjust_state)
    print("\n调整后的计划:", adjusted)