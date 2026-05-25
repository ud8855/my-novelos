import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class BattleRules:
    """战斗规则引擎，负责加载和管理战斗规则，提供战斗逻辑处理接口。
    支持热插拔注册、配置化、异常恢复与日志记录。
    """
    _registered_engines = []

    def __init__(self, config_path=None):
        """初始化战斗规则引擎
        
        Args:
            config_path: 配置文件路径，若为None则使用默认路径
        """
        self.config = {}
        self.config_path = config_path or self._default_config_path()
        self.load_config()
        logger.info("BattleRules 初始化完成")

    @staticmethod
    def _default_config_path():
        """获取默认配置文件路径（与当前模块同级）"""
        return Path(__file__).parent / "battle_rules_config.json"

    def load_config(self, config_path=None):
        """加载配置文件
        
        Args:
            config_path: 覆盖实例的配置文件路径，用于重新加载
        """
        path = config_path or self.config_path
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            logger.info(f"战斗规则配置加载成功: {path}")
        except FileNotFoundError:
            logger.warning(f"战斗规则配置文件未找到: {path}，使用空配置")
            self.config = {}
        except json.JSONDecodeError as e:
            logger.error(f"战斗规则配置文件格式错误: {path}，错误: {e}")
            self.config = {}

    def get_rule(self, rule_name):
        """获取指定名称的规则
        
        Args:
            rule_name: 规则键名
        
        Returns:
            规则内容（通常为字典或列表），若不存在则返回None
        """
        return self.config.get(rule_name, None)

    def apply_combat(self, combat_context):
        """应用战斗规则到给定的战斗上下文，返回处理后的上下文。
        这是核心接口，具体逻辑由子类或扩展实现。
        
        Args:
            combat_context: 战斗上下文数据，可以是字典或自定义对象
        
        Returns:
            处理后的战斗上下文
        """
        logger.debug("应用战斗规则至上下文...")
        # TODO: 依据配置中的规则对combat_context进行处理
        # 例如：伤害计算、状态判定等
        return combat_context

    def register(self):
        """将当前战斗规则引擎注册到全局规则引擎列表，支持热插拔"""
        if self not in BattleRules._registered_engines:
            BattleRules._registered_engines.append(self)
            logger.info("BattleRules 已注册到规则引擎列表")
        else:
            logger.warning("尝试重复注册相同的 BattleRules 实例")

    def unregister(self):
        """从全局规则引擎列表注销当前实例"""
        if self in BattleRules._registered_engines:
            BattleRules._registered_engines.remove(self)
            logger.info("BattleRules 已从规则引擎列表注销")
        else:
            logger.warning("尝试注销未注册的 BattleRules 实例")

    @classmethod
    def get_registered_engines(cls):
        """获取所有已注册的战斗规则引擎实例"""
        return cls._registered_engines

    def self_test(self):
        """自测：验证基本功能，如配置加载、规则访问等"""
        logger.info("开始自测 BattleRules ...")
        print(f"已加载规则数量: {len(self.config)}")
        print(f"规则内容: {self.config}")
        # 尝试获取一个示例规则
        sample_rule = self.get_rule('damage_formula')
        print(f"获取规则 'damage_formula': {sample_rule}")
        # 模拟应用战斗规则
        dummy_context = {"actor": "主角", "action": "攻击", "target": "小怪"}
        result = self.apply_combat(dummy_context)
        print(f"应用战斗规则后上下文: {result}")
        logger.info("自测完成")

if __name__ == "__main__":
    # 设置日志级别以便观察输出
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    print("=== BattleRules 骨架自测 ===")
    engine = BattleRules()
    engine.register()
    print("已注册引擎列表:", BattleRules.get_registered_engines())
    engine.self_test()
    engine.unregister()
    print("注销后引擎列表:", BattleRules.get_registered_engines())
    print("=== 自测结束 ===")