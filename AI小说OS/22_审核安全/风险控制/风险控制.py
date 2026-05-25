""" 
22_审核安全/风险控制/风险控制.py
属于：审核安全层 - 风险控制模块
依赖：无外部（可后续依赖规则引擎、日志工具、配置加载器）
被调用：审核模块主控、Agent工作流（在需要风险检查时调用）
解决：根据可配置的规则对内容进行风险评分和判断，支持热插拔规则，提供日志记录和异常恢复。
"""

import logging
import json
import os
from typing import List, Dict, Any, Optional, Callable

# 配置模块默认路径 (可配置)
DEFAULT_CONFIG_PATH = "config/risk_control.json"

class RiskController:
    """
    风险控制器：负责加载规则，对内容进行风险检查，返回结果。
    支持插件式规则，通过配置文件动态加载规则函数。
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化风险控制器
        :param config_path: 配置文件路径，默认使用 DEFAULT_CONFIG_PATH
        """
        self.config = {}
        self.rules = []  # 存储规则函数
        self.logger = logging.getLogger(self.__class__.__name__)
        self._load_default_config()
        if config_path:
            self.load_config(config_path)
        self._init_rules()

    def _load_default_config(self) -> None:
        """加载默认配置（硬编码兜底）"""
        self.config = {
            "risk_threshold": 0.7,  # 风险阈值，超过则拒绝
            "rules": []
        }

    def load_config(self, config_path: str) -> None:
        """
        从文件加载配置，合并到现有配置
        :param config_path: 配置文件路径
        """
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    new_config = json.load(f)
                self.config.update(new_config)
                self.logger.info(f"配置已加载: {config_path}")
            else:
                self.logger.warning(f"配置文件不存在: {config_path}")
        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")

    def _init_rules(self) -> None:
        """初始化规则集。默认从配置中读取规则名称并动态加载插件（此处为骨架，仅示例）"""
        # 实际生产环境下，可通过配置中的"rules"字段动态导入外部规则模块
        # 这里演示添加内置简单规则
        rule_names = self.config.get("rules", [])
        if not rule_names:
            # 默认添加空规则占位
            self.logger.info("未发现自定义规则，使用默认空规则集")
        else:
            # 尝试动态加载规则
            for rule_name in rule_names:
                rule_func = self._load_rule_function(rule_name)
                if rule_func:
                    self.rules.append(rule_func)
                    self.logger.info(f"已加载规则: {rule_name}")
                else:
                    self.logger.warning(f"规则加载失败: {rule_name}")

    def _load_rule_function(self, rule_name: str) -> Optional[Callable]:
        """
        根据规则名称动态加载规则函数（插件机制）
        实际使用时，可约定规则存放在 '22_审核安全/风险控制/rules/' 下，
        每个文件导出一个 check(content, config) -> (risk_score, details) 的函数
        """
        # 此处仅为骨架示例，实际可扩展为动态导入
        # 例如: module = importlib.import_module(f"rules.{rule_name}")
        # 返回模块中的check函数
        # 这里返回一个简单的模拟函数用于测试
        if rule_name == "sensitive_words":
            # 返回一个内置的敏感词检查函数
            return self._rule_sensitive_words
        return None

    @staticmethod
    def _rule_sensitive_words(content: str, config: Dict[str, Any]) -> float:
        """敏感词规则示例：检查内容中是否包含敏感词列表"""
        sensitive_list = config.get("sensitive_words", [])
        if not sensitive_list:
            return 0.0
        content_lower = content.lower()
        for word in sensitive_list:
            if word.lower() in content_lower:
                return 1.0  # 发现即高风险
        return 0.0

    def check_content(self, content: str) -> Dict[str, Any]:
        """
        对内容进行风险检查
        :param content: 待检查的文本内容
        :return: 字典包含 risk_score (0-1), is_blocked (bool), details (list of rule results)
        """
        risk_score = 0.0
        details = []
        rule_count = len(self.rules)

        if rule_count == 0:
            self.logger.warning("没有激活的风险规则，默认通过")
            return {"risk_score": 0.0, "is_blocked": False, "details": []}

        for rule in self.rules:
            try:
                # 规则调用传入内容和配置
                rule_score = rule(content, self.config)
                details.append({
                    "rule": rule.__name__,
                    "score": rule_score
                })
                risk_score = max(risk_score, rule_score)  # 采用最高风险得分
            except Exception as e:
                self.logger.error(f"规则 {rule.__name__} 执行异常: {e}", exc_info=True)
                # 单个规则异常不影响整体，记录并继续
                details.append({
                    "rule": rule.__name__,
                    "error": str(e)
                })

        threshold = self.config.get("risk_threshold", 0.7)
        is_blocked = risk_score >= threshold
        self.logger.info(f"内容检查完成，风险得分: {risk_score}, 是否拦截: {is_blocked}")
        return {
            "risk_score": risk_score,
            "is_blocked": is_blocked,
            "details": details
        }

    def add_rule(self, rule_func: Callable[[str, Dict[str, Any]], float]) -> None:
        """
        动态添加规则函数（用于热插拔）
        :param rule_func: 规则函数，接收 content, config 返回 risk_score (0-1)
        """
        if not callable(rule_func):
            raise ValueError("规则必须是可调用对象")
        self.rules.append(rule_func)
        self.logger.info(f"动态添加规则: {rule_func.__name__}")

    def remove_rule(self, rule_func: Callable) -> bool:
        """
        动态移除规则
        :param rule_func: 规则函数对象
        :return: 是否成功移除
        """
        if rule_func in self.rules:
            self.rules.remove(rule_func)
            self.logger.info(f"已移除规则: {rule_func.__name__}")
            return True
        return False

    def reload_config(self, config_path: str) -> None:
        """
        重新加载配置并重新初始化规则（热更新）
        :param config_path: 配置文件路径
        """
        self.load_config(config_path)
        self.rules.clear()
        self._init_rules()
        self.logger.info("配置和规则已热更新")


# 自测代码
if __name__ == "__main__":
    # 设置基本日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    print("=== 风险控制模块自测 ===")
    rc = RiskController()
    # 临时添加敏感词规则进行测试
    # 模拟配置文件
    test_config = {
        "risk_threshold": 0.7,
        "sensitive_words": ["violence", "illegal"]
    }
    # 创建一个使用上述配置的控制器
    rc2 = RiskController()
    rc2.config = test_config
    # 手动添加敏感词规则
    rc2.add_rule(RiskController._rule_sensitive_words)

    # 测试文本
    safe_text = "This is a normal story."
    risky_text = "This story contains violence and illegal activities."

    result_safe = rc2.check_content(safe_text)
    result_risky = rc2.check_content(risky_text)

    print(f"安全文本结果: {result_safe}")
    print(f"风险文本结果: {result_risky}")

    # 测试动态移除规则
    rc2.remove_rule(RiskController._rule_sensitive_words)
    result_after_remove = rc2.check_content(risky_text)
    print(f"移除规则后风险检测: {result_after_remove}")
    print("=== 自测完成 ===")