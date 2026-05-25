#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NovelOS - 审核安全层：暴力检测模块

功能：
    检测文本中的暴力、血腥、攻击性内容，返回风险等级与细节。
    遵循审核安全子系统的可插拔设计，支持配置化关键词/正则规则库、
    模型增强检测（预留接口），以及热更新规则文件。

设计原则：
    - 单一职责：仅负责暴力内容判定，不涉及色情、政治等其他类别。
    - 可插拔：继承自审核安全基类（若存在）或提供统一检测接口。
    - 日志记录：关键步骤及异常均通过 logging 记录。
    - 配置化：检测阈值、规则文件路径、模型开关等均从配置读取。

依赖关系：
    - 本模块属于审核安全层（22_审核安全），可能被上层调度器或API调用。
    - 依赖日志模块（标准 logging）与配置解析工具（如 yaml/json）。
    - 预留与模型协同层（20_模型协同）的接口，但当前阶段仅为骨架。
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ------------------------------------------------------------------------------
# 配置默认值
# ------------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "enabled": True,
    "rule_file": "violence_rules.json",          # 相对于本模块目录的规则文件
    "threshold": 0.7,                            # 风险阈值，超过则判定为违规
    "use_model": False,                          # 是否启用 NLP 模型辅助检测
    "model_name": "violence_detection_model",    # 模型协同层中的模型标识
    "log_level": "INFO",
}

# 日志记录器，按照 NovelOS 约定使用模块全限定名
logger = logging.getLogger(__name__)

class ViolenceDetector:
    """
    暴力内容检测器

    使用方式：
        detector = ViolenceDetector(config_path=None)  # 使用默认配置
        risk, detail = detector.detect(text)
        if risk >= detector.threshold:
            print("检测到暴力内容")
    """

    # --------------------------------------------------------------------------
    # 初始化与配置加载
    # --------------------------------------------------------------------------
    def __init__(self, config_path: Optional[str] = None):
        """
        :param config_path: 配置文件路径，若为 None 则使用默认配置。
        """
        self.config: Dict[str, Any] = DEFAULT_CONFIG.copy()
        self.rules: Dict[str, List[str]] = {"keywords": [], "patterns": []}
        self._initialized = False

        # 加载外部配置文件
        if config_path is not None:
            self._load_config_file(config_path)

        # 应用配置中的日志级别
        self._configure_logging()

        # 加载暴力检测规则（关键词、正则）
        self._load_rules()

        self._initialized = True
        logger.info("ViolenceDetector 初始化完成，规则数量：关键词 %d，正则 %d",
                    len(self.rules["keywords"]), len(self.rules["patterns"]))

    def _load_config_file(self, config_path: str):
        """从 JSON 或 YAML 配置文件载入配置项，合并到默认配置上。"""
        path = Path(config_path)
        if not path.is_file():
            logger.warning("配置文件不存在: %s，使用默认配置", config_path)
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                external_config = json.load(f)          # 假设 JSON 格式
            self.config.update(external_config)
            logger.info("已加载外部配置文件: %s", config_path)
        except Exception as e:
            logger.error("配置文件解析失败: %s，错误: %s", config_path, e)

    def _configure_logging(self):
        """根据配置调整日志等级。"""
        level = self.config.get("log_level", "INFO").upper()
        try:
            logger.setLevel(level)
        except ValueError:
            logger.warning("无效的日志级别 '%s'，保持默认", level)

    def _load_rules(self):
        """
        加载暴力检测规则文件。
        规则文件应包含两类字段：
            keywords: 敏感词列表
            patterns: 正则表达式模式列表
        若文件不存在或格式错误，则使用空规则并告警。
        """
        rule_file = self.config.get("rule_file", "violence_rules.json")
        rule_path = Path(__file__).parent / rule_file

        if not rule_path.is_file():
            logger.warning("规则文件不存在: %s，暴力检测将仅依赖模型（如有）", rule_path)
            return

        try:
            with open(rule_path, 'r', encoding='utf-8') as f:
                raw_rules = json.load(f)

            keywords = raw_rules.get("keywords", [])
            patterns = raw_rules.get("patterns", [])

            # 基本合法性校验
            if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
                logger.error("规则文件中的 keywords 字段格式错误，应为字符串列表")
                return
            if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
                logger.error("规则文件中的 patterns 字段格式错误，应为字符串列表")
                return

            self.rules["keywords"] = keywords
            self.rules["patterns"] = patterns
        except Exception as e:
            logger.error("加载规则文件失败: %s，错误: %s", rule_path, e)

    # --------------------------------------------------------------------------
    # 核心检测接口
    # --------------------------------------------------------------------------
    def detect(self, text: str) -> Tuple[float, Dict[str, Any]]:
        """
        检测给定文本的暴力风险。

        :param text: 待检测文本（已清理或原始，由调用方决定）
        :return: (risk_score, detail_dict)
            risk_score: 0.0 ~ 1.0 浮点数，1.0 表示极高暴力风险
            detail_dict: 包含匹配到的关键词、正则、模型补充信息等
        """
        if not self._initialized:
            logger.warning("ViolenceDetector 尚未完成初始化，返回默认零风险")
            return 0.0, {"error": "detector not initialized"}

        risk_score = 0.0
        detail: Dict[str, Any] = {
            "matched_keywords": [],
            "matched_patterns": [],
            "model_risk": None,
        }

        # 1. 关键词匹配（简单计分，每个关键词增加0.1，上限由阈值控制）
        keyword_matches = self._match_keywords(text)
        if keyword_matches:
            detail["matched_keywords"] = keyword_matches
            risk_score = min(1.0, len(keyword_matches) * 0.1)

        # 2. 正则模式匹配（命中一个正则视为高风险，直接拉满风险分）
        pattern_matches = self._match_patterns(text)
        if pattern_matches:
            detail["matched_patterns"] = pattern_matches
            risk_score = 1.0

        # 3. 如果启用了模型，则调用模型协同层（预留接口）
        if self.config.get("use_model", False):
            model_risk = self._model_detect(text)
            detail["model_risk"] = model_risk
            if model_risk is not None:
                # 取模型分与规则分的最大值
                risk_score = max(risk_score, model_risk)

        # 4. 若风险分超过阈值，记录日志
        threshold = self.config.get("threshold", 0.7)
        if risk_score >= threshold:
            logger.info("检测到暴力内容，风险分: %.3f, 关键词: %s, 正则: %s",
                        risk_score, keyword_matches, pattern_matches)

        return risk_score, detail

    def _match_keywords(self, text: str) -> List[str]:
        """返回匹配到的关键词列表（去重）。"""
        matched = []
        lower_text = text.lower()
        for kw in self.rules.get("keywords", []):
            if kw.lower() in lower_text:
                matched.append(kw)
        return matched

    def _match_patterns(self, text: str) -> List[str]:
        """返回匹配到的正则模式名（使用模式本身作为标识）。"""
        matched = []
        for pattern_str in self.rules.get("patterns", []):
            try:
                if re.search(pattern_str, text):
                    matched.append(pattern_str)
            except re.error as e:
                logger.error("无效的正则表达式 '%s': %s", pattern_str, e)
        return matched

    def _model_detect(self, text: str) -> Optional[float]:
        """
        调用模型协同层进行暴力检测。
        当前为占位实现，未来会通过 20_模型协同/ 或 21_API模型/ 调用真实模型。
        :return: 模型返回的风险分，暂时返回 None 表示未实现。
        """
        # TODO: 实现与模型协同层的集成
        # 示例：
        # model = model_coordinator.get_model(self.config["model_name"])
        # return model.predict_violence(text)
        logger.debug("模型暴力检测未实现，跳过")
        return None

    # --------------------------------------------------------------------------
    # 可插拔支持：提供静态注册与发现机制
    # --------------------------------------------------------------------------
    @staticmethod
    def plugin_name() -> str:
        """返回该检测器的插件名称，用于审核引擎动态加载。"""
        return "violence_detector"

    @staticmethod
    def plugin_version() -> str:
        return "0.1.0"

    def get_info(self) -> Dict[str, Any]:
        """返回检测器的元信息（用于监控面板）。"""
        return {
            "name": self.plugin_name(),
            "version": self.plugin_version(),
            "enabled": self.config.get("enabled", True),
            "threshold": self.config.get("threshold", 0.7),
            "rules_loaded": bool(self.rules["keywords"] or self.rules["patterns"]),
        }

    # --------------------------------------------------------------------------
    # 优雅关闭（预留热更新时的资源释放）
    # --------------------------------------------------------------------------
    def shutdown(self):
        """释放资源，例如关闭模型连接等。"""
        logger.info("ViolenceDetector 正在关闭...")
        # 如果有模型实例，在此释放
        self._initialized = False


# ------------------------------------------------------------------------------
# 自测代码（仅在直接运行本文件时执行）
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # 设置一个简单的控制台日志输出
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=== 暴力检测模块自测 ===")

    # 自动创建一个测试用的规则文件（临时）
    test_rule_file = Path(__file__).parent / "test_violence_rules.json"
    test_rules = {
        "keywords": ["杀死", "血腥", "虐待", "爆炸"],
        "patterns": [r"砍杀.*人", r"虐杀[了着]"],
    }
    with open(test_rule_file, 'w', encoding='utf-8') as f:
        json.dump(test_rules, f, ensure_ascii=False, indent=2)

    # 实例化检测器（使用默认配置，但指定规则文件）
    detector = ViolenceDetector(config_path=None)
    detector.config["rule_file"] = str(test_rule_file)
    detector._load_rules()   # 重新加载

    # 测试用例
    test_texts = [
        "今天天气真好，我们去散步吧。",
        "他残忍地杀死了那只猫。",
        "新闻里报道了一起爆炸案，多人受伤。",
        "这篇文章包含血腥的虐杀描写，砍杀了一个人。",
    ]

    for txt in test_texts:
        risk, detail = detector.detect(txt)
        print(f"\n文本: {txt}")
        print(f"风险分: {risk:.2f} (阈值: {detector.config['threshold']})")
        print(f"匹配关键词: {detail['matched_keywords']}")
        print(f"匹配正则: {detail['matched_patterns']}")
        if risk >= detector.config['threshold']:
            print(">>> 判定为暴力内容！")

    # 清理测试文件
    test