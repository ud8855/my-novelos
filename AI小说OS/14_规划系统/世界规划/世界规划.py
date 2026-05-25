import logging
import abc
import os
import json
from typing import Dict, Any, Optional

# ------------------------------
# 日志配置
# ------------------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)  # 可在配置中覆盖


class WorldPlannerBase(abc.ABC):
    """
    世界规划抽象基类，所有世界规划器必须实现此接口。
    保证可插拔：通过配置动态加载具体子类。
    """
    def __init__(self, config: dict):
        self.config = config
        self._initialized = False
        self._world_plan = None
        logger.info("WorldPlannerBase initialized with config keys: %s", list(config.keys()))

    @abc.abstractmethod
    def initialize(self) -> bool:
        """
        初始化世界规划器，加载必要的资源、预置等。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def plan_world(self, requirements: dict) -> dict:
        """
        根据需求生成/更新世界规划。
        :param requirements: 需求描述，包含类型、约束等
        :return: 世界规划数据结构
        """
        raise NotImplementedError

    @abc.abstractmethod
    def update_plan(self, delta: dict) -> bool:
        """
        增量更新世界规划。
        :param delta: 变更内容
        :return: 是否成功
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_plan(self) -> dict:
        """
        获取当前世界规划快照。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def save_plan(self, path: str) -> bool:
        """
        持久化世界规划到文件。
        """
        raise NotImplementedError

    @abc.abstractmethod
    def load_plan(self, path: str) -> bool:
        """
        从文件加载世界规划。
        """
        raise NotImplementedError

    def reload_config(self, new_config: dict):
        """热更新配置（运行时替换配置）"""
        logger.info("Reloading config...")
        self.config = new_config
        # 子类可以重写以实现深层重载
        logger.info("Config reloaded successfully.")

    def shutdown(self):
        """释放资源"""
        logger.info("Shutting down WorldPlannerBase...")
        self._initialized = False


class DefaultWorldPlanner(WorldPlannerBase):
    """
    默认世界规划器实现。当前为骨架，仅定义必要的方法占位。
    后续将接入 20_模型协同 和 21_API模型 完成实际逻辑。
    """
    def __init__(self, config: dict):
        super().__init__(config)
        self._preloaded_data = {}  # 可缓存的基础数据
        logger.debug("DefaultWorldPlanner instance created.")

    def initialize(self) -> bool:
        try:
            # TODO: 加载预设库、地图模板、文化数据库等
            logger.info("DefaultWorldPlanner initializing...")
            # 模拟耗时的初始化
            # 例如从配置文件读取路径，加载json文件
            self._initialized = True
            logger.info("DefaultWorldPlanner initialized successfully.")
            return True
        except Exception as e:
            logger.error("Initialization failed: %s", str(e))
            return False

    def plan_world(self, requirements: dict) -> dict:
        """
        根据需求规划世界。当前返回占位数据结构。
        实际将调用模型协同层生成世界观设定。
        """
        if not self._initialized:
            logger.warning("World planner not initialized, auto-initializing...")
            if not self.initialize():
                raise RuntimeError("Failed to initialize world planner")

        logger.info("Planning world with requirements: %s", json.dumps(requirements, ensure_ascii=False))
        # TODO: 组装prompt，调用 20_模型协同/世界规划协同 或 21_API模型/具体模型
        # 此处返回占位结果
        placeholder_plan = {
            "world_name": requirements.get("world_name", "Untitled"),
            "era": requirements.get("era", "unknown"),
            "geography": {
                "continents": ["placeholder_continent_1"],
                "climate": "temperate"
            },
            "cultures": [],
            "history": [],
            "magic_system": None,
            "status": "draft"
        }
        self._world_plan = placeholder_plan
        logger.info("World plan generated (placeholder).")
        return placeholder_plan

    def update_plan(self, delta: dict) -> bool:
        if self._world_plan is None:
            logger.error("No world plan loaded. Cannot update.")
            return False
        try:
            # 简单合并更新（占位），真实场景需要更智能的融合
            self._world_plan.update(delta)
            logger.info("World plan updated with delta: %s", json.dumps(delta, ensure_ascii=False))
            return True
        except Exception as e:
            logger.exception("Update plan failed: %s", str(e))
            return False

    def get_plan(self) -> dict:
        if self._world_plan is None:
            logger.warning("No plan in memory, returning empty dict.")
            return {}
        return self._world_plan.copy()

    def save_plan(self, path: str) -> bool:
        try:
            plan = self.get_plan()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(plan, f, indent=2, ensure_ascii=False)
            logger.info("World plan saved to %s", path)
            return True
        except Exception as e:
            logger.exception("Failed to save plan: %s", str(e))
            return False

    def load_plan(self, path: str) -> bool:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self._world_plan = json.load(f)
            logger.info("World plan loaded from %s", path)
            return True
        except Exception as e:
            logger.exception("Failed to load plan: %s", str(e))
            return False


# ------------------------------
# 工厂函数，实现可插拔加载
# ------------------------------
def get_world_planner(config: Optional[dict] = None) -> WorldPlannerBase:
    """
    根据配置获取世界规划器实例。
    若未提供配置，从默认配置文件读取。
    """
    if config is None:
        # 默认配置文件路径，可以根据环境变量调整
        config_path = os.environ.get('WORLD_PLANNER_CONFIG', os.path.join(os.path.dirname(__file__), 'world_planner_config.json'))
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info("Configuration loaded from %s", config_path)
        except FileNotFoundError:
            logger.warning("Config file %s not found, using fallback config.", config_path)
            config = {"planner_type": "DefaultWorldPlanner"}

    planner_type = config.get("planner_type", "DefaultWorldPlanner")
    if planner_type == "DefaultWorldPlanner":
        return DefaultWorldPlanner(config)
    # 扩展其他规划器只需添加 elif
    else:
        raise ValueError(f"Unknown world planner type: {planner_type}")


# ------------------------------
# 自测
# ------------------------------
if __name__ == "__main__":
    # 设置测试日志
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(name)s: %(message)s')

    print("=== 自测：世界规划器 ===\n")

    # 1. 使用默认配置创建规划器
    planner = get_world_planner()
    assert isinstance(planner, DefaultWorldPlanner), "类型应为 DefaultWorldPlanner"

    # 2. 初始化
    success = planner.initialize()
    assert success, "初始化失败"
    print("初始化成功\n")

    # 3. 生成世界规划
    requirements = {"world_name": "测试大陆", "era": "魔法中世纪", "detail_level": "概要"}
    plan = planner.plan_world(requirements)
    assert "world_name" in plan, "计划缺少世界名称"
    print("生成的规划:", json.dumps(plan, indent=2, ensure_ascii=False), "\n")

    # 4. 更新规划
    delta = {"magic_system": {"type": "元素魔法", "elements": ["火","水","风","土"]}}
    updated = planner.update_plan(delta)
    assert updated, "更新失败"
    updated_plan = planner.get_plan()
    print("更新后的规划:", json.dumps(updated_plan, indent=2, ensure_ascii=False), "\n")

    # 5. 保存到临时文件
    temp_file = "temp_world_plan.json"
    saved = planner.save_plan(temp_file)
    assert saved and os.path.exists(temp_file), "保存失败"
    print(f"规划已保存至 {temp_file}\n")

    # 6. 加载回另一个实例
    planner2 = get_world_planner()
    loaded = planner2.load_plan(temp_file)
    assert loaded, "加载失败"
    loaded_plan = planner2.get_plan()
    assert loaded_plan == updated_plan, "加载的规划与原规划不一致"
    print("加载验证通过\n")

    # 7. 热更新配置
    planner2.reload_config({"planner_type": "DefaultWorldPlanner", "depth": 3})
    print("配置热更新完成\n")

    # 清理
    planner.shutdown()
    planner2.shutdown()
    if os.path.exists(temp_file):
        os.remove(temp_file)

    print("=== 所有自测通过 ===")