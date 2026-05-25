import os
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

# 日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SecurityRule")

class RuleInterface(ABC):
    """规则接口，所有可插拔规则必须实现此接口"""
    @abstractmethod
    def check(self, content: str) -> Dict[str, Any]:
        """
        执行规则检查
        :param content: 待检查的文本内容
        :return: 检查结果字典，至少包含 is_safe 字段
        """
        pass

class SecurityRule(RuleInterface):
    """
    安全规则检查器，支持敏感词匹配和正则表达式检查
    可插拔：实现 RuleInterface 接口，支持动态加载
    """

    DEFAULT_CONFIG = {
        "sensitive_words": ["暴力", "色情", "违法"],
        "regex_patterns": [
            r"\d{17}[\dXx]",          # 身份证号简单匹配示例
            r"1[3-9]\d{9}"             # 手机号简单匹配示例
        ],
        "risk_level_threshold": 2,     # 风险等级阈值，超过视为不安全
        "enable_sensitive_words": True,
        "enable_regex_patterns": True,
        "enable_log_details": True
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None):
        """
        初始化安全规则检查器
        :param config: 直接传入的配置字典（优先级最高）
        :param config_path: 配置文件路径（JSON格式）
        """
        self.config = self.DEFAULT_CONFIG.copy()
        if config_path:
            self.load_config(config_path)
        if config:
            self.config.update(config)  # 用户传入的配置覆盖默认和文件配置
        logger.info("SecurityRule 初始化完成，当前配置：%s", self.config)

    def load_config(self, config_path: str) -> None:
        """
        从JSON文件加载配置
        :param config_path: 配置文件路径
        """
        if not os.path.exists(config_path):
            logger.warning("配置文件不存在：%s，使用默认配置", config_path)
            return
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
                self.config.update(file_config)
                logger.info("成功加载配置文件：%s", config_path)
        except Exception as e:
            logger.error("加载配置文件 %s 失败：%s", config_path, e)

    def check(self, content: str) -> Dict[str, Any]:
        """
        检查文本内容是否安全
        :param content: 待检查文本
        :return: 结果字典，包含 is_safe (bool), risk_level (int), matches (List[str]) 等
        """
        if not content or not isinstance(content, str):
            return {"is_safe": True, "risk_level": 0, "matches": [], "reason": "empty content"}

        matches = []
        risk_level = 0

        # 1. 敏感词检查
        if self.config.get("enable_sensitive_words", True):
            sensitive_words = self.config.get("sensitive_words", [])
            for word in sensitive_words:
                if word in content:
                    matches.append(f"sensitive_word:{word}")
                    risk_level += 1
                    if self.config.get("enable_log_details", True):
                        logger.info("检测到敏感词：%s", word)

        # 2. 正则表达式检查
        if self.config.get("enable_regex_patterns", True):
            regex_patterns = self.config.get("regex_patterns", [])
            for pattern in regex_patterns:
                try:
                    regex = re.compile(pattern)
                    found = regex.findall(content)
                    if found:
                        for match in found:
                            matches.append(f"regex_match:{pattern}:{match}")
                            risk_level += 1
                            if self.config.get("enable_log_details", True):
                                logger.info("正则匹配到内容：pattern=%s, match=%s", pattern, match)
                except re.error as e:
                    logger.error("无效的正则表达式 %s: %s", pattern, e)

        # 3. 综合判定
        threshold = self.config.get("risk_level_threshold", 2)
        is_safe = risk_level < threshold

        result = {
            "is_safe": is_safe,
            "risk_level": risk_level,
            "matches": matches,
            "threshold": threshold,
            "content_length": len(content)
        }

        logger.debug("安全检查结果：is_safe=%s, risk_level=%d", is_safe, risk_level)
        return result

# 自测试代码
if __name__ == "__main__":
    # 测试1：默认配置，安全文本
    rule = SecurityRule()
    test_content_safe = "今天天气真好，适合写小说。"
    result = rule.check(test_content_safe)
    print("安全文本测试：", json.dumps(result, ensure_ascii=False, indent=2))

    # 测试2：包含敏感词
    test_content_unsafe = "这部小说涉及暴力情节，请注意。"
    result = rule.check(test_content_unsafe)
    print("敏感词测试：", json.dumps(result, ensure_ascii=False, indent=2))

    # 测试3：包含身份证号样式的文本（正则匹配）
    test_content_id = "我的身份证号是110101199001011234，请保密。"
    result = rule.check(test_content_id)
    print("正则匹配测试：", json.dumps(result, ensure_ascii=False, indent=2))

    # 测试4：使用自定义配置
    custom_config = {
        "sensitive_words": ["测试敏感词"],
        "regex_patterns": [r"\d{4}-\d{2}-\d{2}"],
        "risk_level_threshold": 1
    }
    rule_custom = SecurityRule(config=custom_config)
    test_custom = "包含测试敏感词，日期2023-01-15。"
    result = rule_custom.check(test_custom)
    print("自定义配置测试：", json.dumps(result, ensure_ascii=False, indent=2))

    # 测试5：空文本或非字符串
    print("空文本测试：", json.dumps(rule.check(""), ensure_ascii=False))
    print("非字符串测试：", json.dumps(rule.check(None), ensure_ascii=False))

    # 测试6：从配置文件加载（如果存在）
    config_file = "security_rule_config.json"
    if os.path.exists(config_file):
        rule_file = SecurityRule(config_path=config_file)
        result = rule_file.check("测试内容")
        print("文件配置测试：", json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"配置文件 {config_file} 不存在，跳过文件加载测试。")