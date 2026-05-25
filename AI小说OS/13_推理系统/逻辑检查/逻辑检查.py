"""
逻辑检查模块
位置：13_推理系统/逻辑检查
职责：对小说文本进行逻辑一致性检查，如人物行为矛盾、时间线错误、情节冲突等。
依赖：配置模块（读取检查规则），日志模块
被调用：推理系统主流程，或直接作为插件被其他模块调用
可插拔：实现 LogicChecker 接口，可通过配置动态加载不同检查器
配置化：检查规则、启用的检查项、严重程度等均可配置
日志：记录检查过程、警告、错误
"""
import logging
import configparser
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path

# 配置默认日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("LogicChecker")

class CheckResult:
    """单一逻辑检查结果"""
    def __init__(self, category: str, severity: str, message: str, suggestion: str = ""):
        """
        category: 检查类别，如 "character_consistency", "timeline_conflict"
        severity: "error", "warning", "info"
        message: 问题描述
        suggestion: 修改建议
        """
        self.category = category
        self.severity = severity
        self.message = message
        self.suggestion = suggestion

    def to_dict(self) -> Dict[str, str]:
        return {
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "suggestion": self.suggestion
        }

    def __repr__(self):
        return f"CheckResult(category={self.category}, severity={self.severity})"

class LogicChecker(ABC):
    """逻辑检查器抽象基类，所有具体检查器必须实现"""

    def __init__(self, config_section: str = "DEFAULT"):
        self.config_section = config_section
        self.config = self._load_config()
        self.name = self.__class__.__name__
        logger.info(f"逻辑检查器 '{self.name}' 初始化完成 (配置节: {config_section})")

    @abstractmethod
    def check(self, novel_content: str, context: Optional[Dict[str, Any]] = None) -> List[CheckResult]:
        """
        执行逻辑检查
        :param novel_content: 小说文本（可能是一个章节的纯文本）
        :param context: 可选的上下文信息，如人物列表、时间线等
        :return: 检查结果列表
        """
        pass

    def _load_config(self) -> Dict[str, Any]:
        """
        从配置文件加载本检查器的参数
        默认配置文件路径为 config/13_推理系统/逻辑检查.ini，若无则使用内置默认值
        """
        config = {}
        default_config_path = Path(__file__).parent.parent.parent / "config" / "13_推理系统" / "逻辑检查.ini"
        try:
            if default_config_path.exists():
                parser = configparser.ConfigParser()
                parser.read(default_config_path, encoding='utf-8')
                if self.config_section in parser:
                    config = dict(parser[self.config_section])
                else:
                    logger.warning(f"配置文件中未找到节 '{self.config_section}'，使用默认配置")
            else:
                logger.info(f"配置文件不存在: {default_config_path}，使用默认配置")
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")

        # 设置默认值（可被子类覆盖）
        config.setdefault("enabled", "True")
        config.setdefault("severity_threshold", "warning")
        return config

    def is_enabled(self) -> bool:
        """检查器是否启用"""
        return self.config.get("enabled", "True").lower() in ("true", "1", "yes")

    def log_check_info(self, text_summary: str = ""):
        """记录检查开始信息"""
        if self.is_enabled():
            logger.info(f"执行检查器 '{self.name}'")
            if text_summary:
                logger.debug(f"检查文本摘要: {text_summary[:100]}...")
        else:
            logger.info(f"检查器 '{self.name}' 已禁用")

# 一个简单的示例检查器，可被替换，不包含实际业务逻辑
class PlaceholderLogicChecker(LogicChecker):
    """占位逻辑检查器，用于骨架演示，不做实质性检查"""
    def check(self, novel_content: str, context: Optional[Dict[str, Any]] = None) -> List[CheckResult]:
        self.log_check_info(novel_content[:100])
        # 仅示例：返回一个空列表，实际实现需替换
        return []

# 通过注册表动态加载检查器
def load_enabled_checkers(config_path: Optional[str] = None) -> List[LogicChecker]:
    """
    根据配置文件加载所有启用的逻辑检查器实例。
    此处为骨架版本，直接返回占位检查器。
    实际实现应从配置中读取类名并动态导入。
    """
    # 模拟从配置获取检查器列表
    # 后续可实现为：读取配置文件中的 [checkers] enabled = PlaceholderLogicChecker, ...
    # 使用 importlib 动态导入
    checkers = []
    # 由于是骨架，固定一个
    checker = PlaceholderLogicChecker()
    if checker.is_enabled():
        checkers.append(checker)
    return checkers

def run_checks(novel_content: str, context: Optional[Dict[str, Any]] = None) -> List[CheckResult]:
    """对所有启用的逻辑检查器运行检查，汇总结果"""
    all_results = []
    checkers = load_enabled_checkers()
    for checker in checkers:
        try:
            results = checker.check(novel_content, context)
            all_results.extend(results)
        except Exception as e:
            logger.exception(f"检查器 '{checker.name}' 执行时发生异常: {e}")
    logger.info(f"逻辑检查完成，共发现 {len(all_results)} 个问题")
    return all_results

if __name__ == "__main__":
    # 自测：运行逻辑检查骨架
    logger.info("=== 逻辑检查模块自测 ===")
    test_text = "这是一段测试文本。主角小明在第一章中说过自己讨厌吃鱼，但在第三章中却大赞鱼汤美味。"
    context = {"characters": {"小明": {"traits": ["讨厌吃鱼"]}}, "chapters": [1, 3]}
    results = run_checks(test_text, context)
    if not results:
        logger.info("未发现逻辑问题（占位检查器无实际检查逻辑）")
    else:
        for r in results:
            print(f"[{r.severity.upper()}] {r.category}: {r.message}")
    logger.info("自测完成")