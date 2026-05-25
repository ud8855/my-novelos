"""
社会规则模块
提供小说世界中社会规范、人际关系等规则的验证与约束。
可插拔规则架构，支持热加载和配置化。
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

# 配置日志
logger = logging.getLogger(__name__)

class BaseSocialRule(ABC):
    """社会规则基类，所有具体规则需继承此类，实现 validate 方法。"""
    def __init__(self, name: str, config: Optional[Dict] = None):
        self.name = name
        self.config = config or {}
        logger.debug(f"规则 {self.name} 初始化，配置: {self.config}")

    @abstractmethod
    def validate(self, context: Dict[str, Any]) -> bool:
        """
        验证给定情境是否符合该社会规则。
        返回 True 表示合规，False 表示违反规则。
        """
        pass

class SocialRuleEngine:
    """社会规则引擎，负责管理规则、执行验证。"""
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.rules: Dict[str, BaseSocialRule] = {}
        logger.info("社会规则引擎初始化，配置: %s", self.config)

    def add_rule(self, rule: BaseSocialRule):
        """注册一条社会规则。"""
        if rule.name in self.rules:
            logger.warning(f"规则 {rule.name} 已存在，将被覆盖。")
        self.rules[rule.name] = rule
        logger.info(f"已注册规则: {rule.name}")

    def remove_rule(self, rule_name: str):
        """移除一条社会规则。"""
        if rule_name in self.rules:
            del self.rules[rule_name]
            logger.info(f"已移除规则: {rule_name}")
        else:
            logger.warning(f"尝试移除不存在的规则: {rule_name}")

    def validate(self, context: Dict[str, Any]) -> Dict[str, bool]:
        """
        对所有已注册的规则进行验证，返回每条规则的验证结果。
        """
        results = {}
        for name, rule in self.rules.items():
            try:
                valid = rule.validate(context)
                results[name] = valid
                logger.debug(f"规则 {name} 验证结果: {valid}")
            except Exception as e:
                logger.exception(f"规则 {name} 验证时发生异常")
                results[name] = False  # 异常时视为不通过
        return results

    def get_violations(self, context: Dict[str, Any]) -> List[str]:
        """获取所有违反的规则名称列表。"""
        results = self.validate(context)
        violations = [name for name, passed in results.items() if not passed]
        logger.info(f"违规规则: {violations}")
        return violations


# 示例规则实现：亲属关系规则
class KinshipRule(BaseSocialRule):
    """亲属关系规则：禁止直系亲属恋爱等社会规范。"""
    def validate(self, context: Dict[str, Any]) -> bool:
        character_a = context.get("character_a")
        character_b = context.get("character_b")
        relationship = context.get("relationship")
        # 简单逻辑：如果 relationship 为 "direct_family" 且期望恋爱行为则禁止
        if relationship == "direct_family" and context.get("action") == "love":
            logger.warning(f"直系亲属之间不允许恋爱: {character_a} 与 {character_b}")
            return False
        return True


# ---------- 自测 ----------
if __name__ == "__main__":
    # 配置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 创建社会规则引擎
    engine = SocialRuleEngine(config={"enable_logging": True})

    # 添加示例规则
    kinship_rule = KinshipRule(name="kinship", config={"strict": True})
    engine.add_rule(kinship_rule)

    # 测试场景1：正常关系
    context1 = {
        "character_a": "Alice",
        "character_b": "Bob",
        "relationship": "friends",
        "action": "love"
    }
    print("场景1验证结果:", engine.validate(context1))

    # 测试场景2：直系亲属恋爱（违规）
    context2 = {
        "character_a": "Alice",
        "character_b": "Charlie",
        "relationship": "direct_family",
        "action": "love"
    }
    print("场景2验证结果:", engine.validate(context2))

    # 获取违规列表
    print("场景2违规规则:", engine.get_violations(context2))

    # 移除规则
    engine.remove_rule("kinship")
    print("移除后规则数量:", len(engine.rules))