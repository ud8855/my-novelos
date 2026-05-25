# 23_去AI化/去模板化/去模板化.py
# 功能：检测并消除AI生成文本中的模板化痕迹，提升小说创作的自然度与个性化。
# 层级：23_去AI化层
# 依赖：无外部模块，仅标准库（未来可扩展引入NLP工具）
# 被调用：由上游处理流水线（如21_API模型输出后处理）调用
# 解决问题：AI文本容易陷入固定句式、重复表达，此模块提供规则化+可扩展的去模板化处理

import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

# ---------- 配置管理 ----------
class DetemplaterConfig:
    """去模板化配置（可插拔，可通过JSON文件或字典加载）"""
    def __init__(self, config_path: Optional[str] = None):
        # 默认配置
        self.enabled: bool = True
        self.rules_file: str = "detemplate_rules.json"  # 规则文件路径，相对于本模块目录
        self.default_rules: List[Dict] = [
            {
                "name": "remove_cliche_openings",
                "pattern": r"(?i)(众所周知|毫无疑问|在当今时代|随着.*的发展)",
                "replacement": "",  # 直接删除
                "description": "去除陈词滥调的开头"
            },
            {
                "name": "remove_redundant_phrases",
                "pattern": r"(?i)(可以这么说|换句话说|值得一提的是)",
                "replacement": "",
                "description": "去除冗余口头禅"
            },
            {
                "name": "vn_style_endings",
                "pattern": r"[。！？](?![。！？\n])",  # 简单示例，后期替换为真实规则
                "replacement": "",
                "description": "去除不自然的句尾重复"
            }
        ]
        self.case_sensitive: bool = False
        self.log_level: str = "INFO"
        
        # 从文件加载配置（如果提供路径）
        if config_path:
            self.load_from_file(config_path)
        else:
            # 尝试从默认路径加载
            default_cfg = Path(__file__).parent / "detemplate_config.json"
            if default_cfg.exists():
                self.load_from_file(str(default_cfg))

    def load_from_file(self, path: str):
        """从JSON配置文件加载"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 更新属性
            self.enabled = data.get("enabled", self.enabled)
            self.rules_file = data.get("rules_file", self.rules_file)
            self.case_sensitive = data.get("case_sensitive", self.case_sensitive)
            self.log_level = data.get("log_level", self.log_level)
            # 规则文件单独加载，不覆盖内置默认，但可以覆盖规则文件路径
            logging.info(f"Detemplater config loaded from {path}")
        except Exception as e:
            logging.warning(f"Failed to load config from {path}: {e}. Using defaults.")

    def load_rules_from_file(self, rules_path: Optional[str] = None) -> List[Dict]:
        """从规则JSON文件加载规则列表"""
        if rules_path is None:
            rules_path = str(Path(__file__).parent / self.rules_file)
        try:
            with open(rules_path, 'r', encoding='utf-8') as f:
                rules = json.load(f)
            if not isinstance(rules, list):
                raise ValueError("Rules file must contain a list of rule objects.")
            logging.info(f"Loaded {len(rules)} rules from {rules_path}")
            return rules
        except FileNotFoundError:
            logging.info(f"Rules file not found at {rules_path}, using default rules.")
            return self.default_rules
        except Exception as e:
            logging.error(f"Error loading rules from {rules_path}: {e}")
            return self.default_rules


# ---------- 日志设置 ----------
def setup_logging(level_name: str = "INFO"):
    """配置模块日志"""
    logger = logging.getLogger("Detemplater")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, level_name.upper(), logging.INFO))
    return logger


# ---------- 核心去模板化类 ----------
class Detemplater:
    """去模板化处理器，支持规则加载、应用、扩展"""
    def __init__(self, config: Optional[DetemplaterConfig] = None):
        self.config = config or DetemplaterConfig()
        self.logger = setup_logging(self.config.log_level)
        self.rules: List[Dict] = []
        self.compiled_patterns: List[re.Pattern] = []
        self.replacements: List[str] = []
        self._load_rules()

    def _load_rules(self):
        """加载规则并编译正则表达式"""
        self.rules = self.config.load_rules_from_file()
        self.compiled_patterns = []
        self.replacements = []
        flags = 0 if self.config.case_sensitive else re.IGNORECASE
        for rule in self.rules:
            try:
                pat = re.compile(rule["pattern"], flags)
                self.compiled_patterns.append(pat)
                self.replacements.append(rule.get("replacement", ""))
            except re.error as e:
                self.logger.error(f"Invalid pattern in rule '{rule.get('name', 'unknown')}': {e}")
        self.logger.info(f"Detemplater initialized with {len(self.compiled_patterns)} active rules.")

    def reload_rules(self, rules_path: Optional[str] = None):
        """热更新规则：重新加载并编译"""
        self.config.rules_file = rules_path or self.config.rules_file
        self._load_rules()
        self.logger.info("Rules reloaded successfully.")

    def detemplate(self, text: str) -> str:
        """对文本应用所有去模板化规则，返回处理后的文本"""
        if not self.config.enabled or not text:
            return text

        original_length = len(text)
        processed = text
        for pattern, replacement in zip(self.compiled_patterns, self.replacements):
            processed = pattern.sub(replacement, processed)
        self.logger.debug(f"Detemplate: {original_length} -> {len(processed)} chars")
        return processed

    def add_rule(self, rule: Dict, compile_now: bool = True):
        """动态添加规则（可插拔扩展），可选择立即编译加入活跃规则"""
        if not isinstance(rule, dict) or "pattern" not in rule:
            self.logger.error("Invalid rule format. Must contain 'pattern' key.")
            return
        self.rules.append(rule)
        if compile_now:
            flags = 0 if self.config.case_sensitive else re.IGNORECASE
            try:
                pat = re.compile(rule["pattern"], flags)
                self.compiled_patterns.append(pat)
                self.replacements.append(rule.get("replacement", ""))
                self.logger.info(f"Rule '{rule.get('name', 'unamed')}' added and compiled.")
            except re.error as e:
                self.logger.error(f"Failed to compile added rule: {e}")

    def remove_rule_by_name(self, name: str):
        """通过规则名移除规则，支持热拔"""
        for i, rule in enumerate(self.rules):
            if rule.get("name") == name:
                del self.rules[i]
                if i < len(self.compiled_patterns):
                    del self.compiled_patterns[i]
                    del self.replacements[i]
                self.logger.info(f"Rule '{name}' removed.")
                return
        self.logger.warning(f"Rule '{name}' not found.")


# ---------- 自测 ----------
def self_test():
    """模块自测：验证基本功能"""
    print("=== Detemplater Self-Test ===")
    config = DetemplaterConfig()
    detemplater = Detemplater(config)
    
    # 测试文本
    test_text = "众所周知，在当今时代，AI写作工具层出不穷。可以这么说，这是一个伟大的时代。值得一提的是，我们需要谨慎使用。"
    expected_removed = ["众所周知", "在当今时代", "可以这么说", "值得一提的是"]
    
    result = detemplater.detemplate(test_text)
    print(f"Original: {test_text}")
    print(f"Processed: {result}")
    
    # 简单检查是否移除了部分词汇
    for phrase in expected_removed:
        if phrase in result:
            print(f"Warning: '{phrase}' was not removed!")
        else:
            print(f"OK: '{phrase}' removed.")
    
    # 测试热插拔
    print("\n--- Testing dynamic rule addition ---")
    detemplater.add_rule({
        "name": "remove_test",
        "pattern": r"测试",
        "replacement": "试验"
    })
    test2 = "这是一个测试句子。"
    res2 = detemplater.detemplate(test2)
    print(f"After adding rule: {res2}")  # 期望：这是一个试验句子。
    
    # 移除规则
    detemplater.remove_rule_by_name("remove_test")
    res3 = detemplater.detemplate(test2)
    print(f"After removing rule: {res3}")  # 应为原句
    
    print("=== Self-Test Completed ===")


if __name__ == "__main__":
    self_test()