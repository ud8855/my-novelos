"""
生态生成模块
隶属于 NovelOS 创世系统 (24_创世系统)，负责小说世界的生态架构生成与演化。
遵循可插拔、配置化、日志记录原则，提供生态元素创建、关系构建和生态平衡检查等基础能力。
"""

import json
import logging
import os
from typing import Dict, List, Optional, Any, Callable

# 配置默认值
DEFAULT_CONFIG = {
    "log_level": "INFO",
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "default_biomes": ["森林", "草原", "沙漠", "海洋", "山脉"],
    "default_creatures": ["人类", "精灵", "矮人", "兽人"],
    "balance_factor": 0.3,
}

class EcosystemGenerator:
    """
    生态生成器，负责创建和管理小说世界的生物群落、物种关系及生态平衡。
    通过配置文件驱动，支持热插入新生态组件。
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化生态生成器。
        :param config_path: 可选配置文件路径，JSON格式。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self._load_config(config_path)
        self._setup_logging()
        self.biomes: Dict[str, Any] = {}
        self.creatures: Dict[str, Any] = {}
        self.relationships: List[Dict[str, Any]] = []
        self.plugins: Dict[str, Callable] = {}
        self.logger.info("EcosystemGenerator initialized.")

    def _load_config(self, config_path: Optional[str] = None) -> None:
        """加载配置，若未提供路径则使用默认配置。"""
        self.config = DEFAULT_CONFIG.copy()
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                    self.config.update(user_config)
                    self.logger.debug(f"Config loaded from {config_path}")
            except Exception as e:
                self.logger.error(f"Failed to load config: {e}")
        else:
            self.logger.debug("Using default configuration.")

    def _setup_logging(self) -> None:
        """配置日志输出。"""
        log_level = getattr(logging, self.config.get("log_level", "INFO").upper(), logging.INFO)
        self.logger.setLevel(log_level)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(self.config.get("log_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        self.logger.debug("Logging configured.")

    def add_biome(self, biome_id: str, properties: Dict[str, Any]) -> bool:
        """
        添加或更新一个生物群落。
        :param biome_id: 群落唯一标识。
        :param properties: 群落属性字典（如气候、资源、面积等）。
        :return: 成功返回True，否则False。
        """
        try:
            self.biomes[biome_id] = properties
            self.logger.info(f"Biome '{biome_id}' added/updated.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to add biome '{biome_id}': {e}")
            return False

    def remove_biome(self, biome_id: str) -> bool:
        """
        移除一个生物群落，并清理相关关系。
        :param biome_id: 群落标识。
        :return: 成功返回True。
        """
        if biome_id in self.biomes:
            del self.biomes[biome_id]
            # 清理与该群落相关的物种关系
            self.relationships = [rel for rel in self.relationships 
                                  if rel.get("biome") != biome_id]
            self.logger.info(f"Biome '{biome_id}' removed.")
            return True
        self.logger.warning(f"Biome '{biome_id}' not found.")
        return False

    def add_creature(self, creature_id: str, properties: Dict[str, Any]) -> bool:
        """
        添加或更新一个生物物种。
        :param creature_id: 物种唯一标识。
        :param properties: 生物属性（栖息地偏好、食物链位置等）。
        :return: 成功返回True。
        """
        try:
            self.creatures[creature_id] = properties
            self.logger.info(f"Creature '{creature_id}' added/updated.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to add creature '{creature_id}': {e}")
            return False

    def remove_creature(self, creature_id: str) -> bool:
        """
        移除一个生物物种。
        :param creature_id: 物种标识。
        :return: 成功返回True。
        """
        if creature_id in self.creatures:
            del self.creatures[creature_id]
            # 清理相关关系
            self.relationships = [rel for rel in self.relationships 
                                  if (rel.get("predator") != creature_id and 
                                      rel.get("prey") != creature_id)]
            self.logger.info(f"Creature '{creature_id}' removed.")
            return True
        self.logger.warning(f"Creature '{creature_id}' not found.")
        return False

    def define_relationship(self, predator: str, prey: str, 
                            biome: Optional[str] = None,
                            relationship_type: str = "捕食") -> bool:
        """
        定义两个物种之间的生态关系（捕食、共生、竞争等）。
        :param predator: 捕食者标识。
        :param prey: 被捕食者标识。
        :param biome: 限定群落，若为None则全局。
        :param relationship_type: 关系类型。
        :return: 成功返回True。
        """
        if predator not in self.creatures or prey not in self.creatures:
            self.logger.error("Both creatures must exist.")
            return False
        if biome and biome not in self.biomes:
            self.logger.error(f"Biome '{biome}' does not exist.")
            return False

        rel = {
            "predator": predator,
            "prey": prey,
            "biome": biome,
            "type": relationship_type
        }
        self.relationships.append(rel)
        self.logger.info(f"Relationship defined: {predator} -> {prey} ({relationship_type}) in {biome or 'global'}")
        return True

    def check_balance(self) -> Dict[str, Any]:
        """
        进行简单的生态平衡检查。
        基于配置中的 balance_factor 评估是否过度捕食。
        :return: 包含状态和建议的字典。
        """
        result = {
            "status": "导常",
            "warnings": [],
            "suggestions": []
        }
        # 统计每个物种作为被捕食者的次数
        prey_count: Dict[str, int] = {}
        for rel in self.relationships:
            prey = rel["prey"]
            prey_count[prey] = prey_count.get(prey, 0) + 1

        # 假设 threshold = balance_factor * 某个基数
        threshold = max(1, int(len(self.relationships) * self.config["balance_factor"]))
        for prey_id, count in prey_count.items():
            if count > threshold:
                result["warnings"].append(f"Creature '{prey_id}' is over-predated ({count} times).")
        if not result["warnings"]:
            result["status"] = "平衡"
        else:
            result["suggestions"].append("Consider reducing predation pressure or adding refuges.")
        self.logger.info(f"Ecological balance checked: {result['status']}")
        return result

    def register_plugin(self, plugin_name: str, plugin_func: Callable) -> bool:
        """
        注册一个生态生成插件，用于扩展生态逻辑（如气候模拟、灾难事件）。
        :param plugin_name: 插件名。
        :param plugin_func: 插件可调用对象，必须接受 ecosystem_instance 作为参数。
        :return: 注册成功返回True。
        """
        if plugin_name in self.plugins:
            self.logger.warning(f"Plugin '{plugin_name}' already exists. Overwriting.")
        self.plugins[plugin_name] = plugin_func
        self.logger.info(f"Plugin '{plugin_name}' registered.")
        return True

    def execute_plugin(self, plugin_name: str, *args, **kwargs) -> Any:
        """
        执行已注册的插件。
        :param plugin_name: 插件名。
        :param args: 传递给插件的位置参数。
        :param kwargs: 关键字参数。
        :return: 插件返回值。
        """
        plugin = self.plugins.get(plugin_name)
        if not plugin:
            self.logger.error(f"Plugin '{plugin_name}' not found.")
            return None
        try:
            return plugin(*args, **kwargs)
        except Exception as e:
            self.logger.error(f"Plugin '{plugin_name}' execution failed: {e}")
            return None

    def export_state(self) -> Dict[str, Any]:
        """
        导出整个生态系统的状态，便于序列化或热更新。
        :return: 包含生物群落、物种、关系的字典。
        """
        state = {
            "biomes": self.biomes,
            "creatures": self.creatures,
            "relationships": self.relationships
        }
        self.logger.debug("Ecosystem state exported.")
        return state

    def import_state(self, state: Dict[str, Any]) -> bool:
        """
        从状态字典导入生态系统，恢复之前的状态。
        :param state: 包含 biomes, creatures, relationships 的字典。
        :return: 成功返回True。
        """
        try:
            self.biomes = state.get("biomes", {})
            self.creatures = state.get("creatures", {})
            self.relationships = state.get("relationships", [])
            self.logger.info("Ecosystem state imported successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to import state: {e}")
            return False


# ------------------ 自测部分 ------------------
if __name__ == "__main__":
    # 设置基础日志级别为 DEBUG 以便观察
    logging.basicConfig(level=logging.DEBUG)
    
    # 实例化生成器
    gen = EcosystemGenerator()
    
    # 添加一些生物群落
    gen.add_biome("dark_forest", {"temperature": "cool", "humidity": "high", "resources": ["wood", "herbs"]})
    gen.add_biome("plains", {"temperature": "mild", "humidity": "medium", "resources": ["grains", "water"]})
    
    # 添加物种
    gen.add_creature("wolf", {"diet": "carnivore", "habitat": "dark_forest", "size": "medium"})
    gen.add_creature("rabbit", {"diet": "herbivore", "habitat": "plains", "size": "small"})
    gen.add_creature("deer", {"diet": "herbivore", "habitat": "dark_forest", "size": "large"})
    
    # 定义关系
    gen.define_relationship("wolf", "rabbit", "dark_forest")
    gen.define_relationship("wolf", "deer", "dark_forest")
    
    # 平衡检查
    balance = gen.check_balance()
    print("Balance result:", balance)
    
    # 测试插件机制
    def climate_event(ecosystem, event_type):
        print(f"Climate event '{event_type}' triggered.")
        # 可以修改生态系统状态
        return "Climate event executed"
    
    gen.register_plugin("climate_change", climate_event)
    result = gen.execute_plugin("climate_change", gen, "volcanic_winter")
    print("Plugin result:", result)
    
    # 导入导出
    state = gen.export_state()
    gen2 = EcosystemGenerator()
    gen2.import_state(state)
    print("Imported biomes:", gen2.biomes.keys())
    
    print("自测完成。")