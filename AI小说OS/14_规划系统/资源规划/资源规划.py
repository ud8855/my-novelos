# -*- coding: utf-8 -*-
"""
资源规划模块：负责小说创作中涉及的角色、场景、物品等全局资源的统筹规划。
确保资源使用的合理性与一致性，支持可插拔的规划策略。
"""
import logging
import configparser
import os
import importlib
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# 定义资源规划结果数据容器
class ResourcePlan:
    """资源规划结果封装"""
    def __init__(self, plan_id: str = "", resources: Optional[Dict[str, Any]] = None):
        self.plan_id = plan_id
        self.resources = resources if resources else {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "resources": self.resources
        }

    def __repr__(self):
        return f"<ResourcePlan plan_id={self.plan_id}, num_resources={len(self.resources)}>"

# 抽象基类，定义资源规划接口
class ResourcePlanner(ABC):
    """资源规划器抽象基类，所有规划器必须实现该接口"""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config if config else {}
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"Initializing {self.__class__.__name__}")

    @abstractmethod
    def plan_resources(self, novel_outline: Any, constraints: Optional[Dict[str, Any]] = None) -> ResourcePlan:
        """
        根据小说大纲及约束条件生成资源规划。
        :param novel_outline: 小说大纲对象（可序列化）
        :param constraints: 额外约束条件
        :return: ResourcePlan
        """
        pass

    @abstractmethod
    def validate_plan(self, plan: ResourcePlan) -> bool:
        """验证资源规划是否合理有效"""
        pass

    def get_type(self) -> str:
        """返回规划器类型标识，用于配置识别"""
        return self.__class__.__name__

    def __repr__(self):
        return f"<{self.__class__.__name__} config={self.config}>"

# 一个简单的默认实现，用于骨架测试
class DefaultResourcePlanner(ResourcePlanner):
    """默认资源规划器，基于启发式规则进行资源分配"""
    def plan_resources(self, novel_outline: Any, constraints: Optional[Dict[str, Any]] = None) -> ResourcePlan:
        self.logger.info("Starting default resource planning.")
        # 实际逻辑应在此处实现，这里返回一个空规划作为示例
        plan = ResourcePlan(plan_id="default_plan_001")
        plan.resources["characters"] = ["character_1", "character_2"]  # 示例
        plan.resources["locations"] = ["location_1"]
        self.logger.debug(f"Generated plan: {plan}")
        return plan

    def validate_plan(self, plan: ResourcePlan) -> bool:
        # 简单的验证：检查是否有资源
        if not plan.resources:
            self.logger.warning("Empty resource plan.")
            return False
        return True

# 工厂函数，根据配置动态加载规划器
def get_resource_planner(config_file: Optional[str] = None) -> ResourcePlanner:
    """
    从配置文件或环境变量加载指定的资源规划器实例。
    配置文件格式：[resource_planner]
                    class = module_path.ClassName
                    其他参数...
    """
    config = configparser.ConfigParser()
    planner_config = {}
    if config_file and os.path.exists(config_file):
        config.read(config_file, encoding='utf-8')
        if config.has_section('resource_planner'):
            planner_config = dict(config.items('resource_planner'))
    else:
        # 使用默认配置
        planner_config = {'class': '14_规划系统.资源规划.DefaultResourcePlanner'}

    class_path = planner_config.get('class', '14_规划系统.资源规划.DefaultResourcePlanner')
    try:
        module_name, class_name = class_path.rsplit('.', 1)
        module = importlib.import_module(module_name)
        planner_class = getattr(module, class_name)
    except Exception as e:
        logger.error(f"Failed to load planner class {class_path}: {e}")
        raise

    # 构造实例，传递额外的配置参数（排除class键）
    instance_config = {k: v for k, v in planner_config.items() if k != 'class'}
    planner = planner_class(config=instance_config)
    logger.info(f"Loaded resource planner: {planner}")
    return planner

# 自测代码
if __name__ == "__main__":
    print("Running resource planner self-test...")
    # 测试默认规划器直接实例化
    planner = DefaultResourcePlanner()
    outline = {"title": "测试小说", "chapters": []}
    plan = planner.plan_resources(outline)
    print(f"Generated plan: {plan}")
    valid = planner.validate_plan(plan)
    print(f"Plan is valid: {valid}")

    # 测试工厂函数（使用当前模块）
    try:
        # 创建一个临时配置文件测试
        temp_config = "temp_planner_config.ini"
        with open(temp_config, "w", encoding="utf-8") as f:
            f.write("[resource_planner]\nclass = 14_规划系统.资源规划.DefaultResourcePlanner\n")
        factory_planner = get_resource_planner(temp_config)
        plan2 = factory_planner.plan_resources(outline)
        print(f"Factory-generated plan: {plan2}")
        os.remove(temp_config)
    except Exception as e:
        print(f"Factory test failed: {e}")

    print("Self-test completed.")