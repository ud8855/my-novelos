"""
爽文规则引擎骨架模块
职责：提供可插拔的爽文套路检测/生成规则，支持配置、日志与热插拔。
依赖：配置管理器、日志工具
被调用：情节生成器、编辑器、评审模块
"""

import logging
from typing import Dict, List, Any, Optional, Callable

# 初始化模块级日志记录器
logger = logging.getLogger(__name__)

class ShuangwenRule:
    """
    单条爽文规则，包含规则ID、名称、描述、检测函数、权重等。
    """
    def __init__(self, rule_id: str, name: str, description: str,
                 check_func: Callable[[Dict[str, Any]], bool],
                 weight: float = 1.0, enabled: bool = True):
        self.rule_id = rule_id
        self.name = name
        self.description = description
        self._check_func = check_func
        self.weight = weight
        self.enabled = enabled

    def check(self, context: Dict[str, Any]) -> bool:
        """检查上下文是否满足该规则"""
        if not self.enabled:
            return False
        try:
            result = self._check_func(context)
            logger.debug(f"规则 '{self.rule_id}' 检测结果: {result}")
            return result
        except Exception as e:
            logger.error(f"规则 '{self.rule_id}' 执行异常: {e}")
            return False

class ShuangwenRuleEngine:
    """
    爽文规则引擎，管理所有爽文规则并提供统一的检测接口。
    支持动态加载、热插拔、配置化。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.rules: Dict[str, ShuangwenRule] = {}
        self._initialize_from_config()

    def _initialize_from_config(self):
        """根据配置初始化规则集，支持默认规则和自定义规则"""
        rule_configs = self.config.get("rules", [])
        for rc in rule_configs:
            self.register_rule_from_config(rc)
        logger.info(f"初始加载 {len(self.rules)} 条规则")

    def register_rule(self, rule: ShuangwenRule):
        """注册一条规则（热插拔入口）"""
        if rule.rule_id in self.rules:
            logger.warning(f"规则ID '{rule.rule_id}' 已存在，将被覆盖")
        self.rules[rule.rule_id] = rule
        logger.info(f"规则 '{rule.rule_id}' 已注册")

    def unregister_rule(self, rule_id: str):
        """注销一条规则"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            logger.info(f"规则 '{rule_id}' 已注销")
        else:
            logger.warning(f"尝试注销不存在的规则 '{rule_id}'")

    def register_rule_from_config(self, config: Dict[str, Any]):
        """
        从配置字典注册一条规则。
        配置示例:
        {
            "id": "revenge_plot",
            "name": "复仇情节",
            "description": "检测是否存在经典的复仇起点",
            "check_func": "module.path.to.function",  # 真实使用时动态加载
            "weight": 1.2,
            "enabled": True
        }
        """
        # 此处仅为骨架，实际应动态导入check_func
        # 模拟一个简单的检测函数，可以通过配置指定字符串后动态加载
        check_func = config.get("check_func", lambda ctx: True)
        if isinstance(check_func, str):
            # 实际应通过importlib动态导入，这里省略
            logger.warning(f"check_func 为字符串，需要实现动态加载: {check_func}")
            # 暂时设为恒真作为占位
            def dummy_func(ctx):
                return True
            check_func = dummy_func

        rule = ShuangwenRule(
            rule_id=config["id"],
            name=config.get("name", config["id"]),
            description=config.get("description", ""),
            check_func=check_func,
            weight=config.get("weight", 1.0),
            enabled=config.get("enabled", True)
        )
        self.register_rule(rule)

    def check_all_rules(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        对当前上下文执行所有已注册的规则，返回触发的规则信息列表。
        """
        triggered = []
        for rule_id, rule in self.rules.items():
            if rule.check(context):
                triggered.append({
                    "rule_id": rule.rule_id,
                    "name": rule.name,
                    "weight": rule.weight,
                    "description": rule.description
                })
        logger.info(f"规则检测完成，触发 {len(triggered)} 条")
        return triggered

    def get_dominant_rule(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取权重最高的触发规则"""
        triggered = self.check_all_rules(context)
        if not triggered:
            return None
        # 按权重降序排序，取第一个
        triggered.sort(key=lambda r: r["weight"], reverse=True)
        dominant = triggered[0]
        logger.debug(f"主导规则: {dominant['rule_id']}")
        return dominant

    def reload_config(self, new_config: Dict[str, Any]):
        """热更新配置，重新加载规则"""
        self.config = new_config
        self.rules.clear()
        self._initialize_from_config()
        logger.info("规则引擎配置已热更新")

    def get_rule_list(self) -> List[Dict[str, Any]]:
        """获取当前所有规则的元信息"""
        return [{
            "rule_id": r.rule_id,
            "name": r.name,
            "weight": r.weight,
            "enabled": r.enabled,
            "description": r.description
        } for r in self.rules.values()]

# 自测代码
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 创建测试用规则函数
    def revenge_check(ctx):
        """简单的复仇情节检测：上下文是否包含'复仇'关键词"""
        content = ctx.get("content", "")
        return "复仇" in content

    def genius_check(ctx):
        """检测是否出现天才设定"""
        content = ctx.get("content", "")
        return "天才" in content

    def adventure_check(ctx):
        """检测冒险元素"""
        content = ctx.get("content", "")
        return "冒险" in content

    # 构造规则配置
    test_config = {
        "rules": [
            {
                "id": "revenge",
                "name": "复仇情节",
                "description": "主角背负血海深仇，奠定逆袭动力",
                "check_func": revenge_check,
                "weight": 1.5,
                "enabled": True
            },
            {
                "id": "genius",
                "name": "天才出世",
                "description": "主角拥有超凡天赋或神秘背景",
                "check_func": genius_check,
                "weight": 1.2,
                "enabled": True
            },
            {
                "id": "adventure",
                "name": "冒险旅程",
                "description": "经典冒险叙事结构",
                "check_func": adventure_check,
                "weight": 0.8,
                "enabled": False  # 演示禁用规则
            }
        ]
    }

    # 实例化引擎
    engine = ShuangwenRuleEngine(test_config)
    print("当前规则列表：", engine.get_rule_list())

    # 模拟文本上下文
    context = {
        "content": "少年身负血海深仇，却意外获得天才传承，从此踏上冒险之旅。",
        "metadata": {"genre": "xianxia"}
    }

    # 执行检测
    triggered_rules = engine.check_all_rules(context)
    print("触发的规则：", triggered_rules)

    dominant = engine.get_dominant_rule(context)
    print("主导规则：", dominant)

    # 测试热插拔
    engine.unregister_rule("revenge")
    print("注销revenge后触发的规则：", engine.check_all_rules(context))

    # 注册新规则
    new_rule = ShuangwenRule("new_rule", "测试规则", "仅测试", lambda ctx: True, weight=2.0)
    engine.register_rule(new_rule)
    print("注册新规则后触发的规则：", engine.check_all_rules(context))
    print("主导规则：", engine.get_dominant_rule(context))

    # 热更新配置
    engine.reload_config(test_config)
    print("配置重载后规则列表：", engine.get_rule_list())

    logger.info("自测完成")