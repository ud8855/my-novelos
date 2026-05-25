# -*- coding: utf-8 -*-
"""
模块路径：22_审核安全/安全审查.py
层定位：审核安全层 —— 内容安全审查
依赖关系：
    - 依赖：20_模型协同/ (AbstractModelCoordinator)
          21_API模型/ (AbstractAPIModel)
    - 被调用：13_写作流程/、14_编辑流程/ 等核心业务流程，在生成或修改内容后进行安全审查
功能职责：
    - 提供可插拔的内容安全审查接口
    - 支持热嵌入多种审查策略（关键词、模型判断、规则引擎）
    - 审查结果标准化输出（通过/拦截/需人工复核）
    - 记录审查日志、支持配置化管理敏感词库/模型参数
设计原则：
    - 单一职责：仅负责安全判断，不涉及内容改写或流程控制
    - 可插拔：通过抽象基类定义协议，支持动态注册/替换审查器
    - 配置化：所有阈值、词库路径、模型端点均从配置加载
    - 异常恢复：审查异常时提供默认安全策略（默认拦截或放行可配置）
"""

import logging
import abc
from typing import Dict, Any, List, Optional

# ------------------------------
# 日志配置（可插拔：生产环境可替换为分布式日志采集）
# ------------------------------
logger = logging.getLogger("novelos.security_review")
logger.setLevel(logging.DEBUG)
_ch = logging.StreamHandler()
_ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
if not logger.handlers:
    logger.addHandler(_ch)

# ------------------------------
# 配置占位（实际应从 configs/security.yaml 加载，此处用类属性模拟）
# ------------------------------
class SafetyConfig:
    """
    安全审查配置容器
    支持通过字典加载，可扩展为从文件/远程配置中心读取
    """
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        default_config = {
            "default_reviewer": "DefaultSafetyReviewer",
            "fail_open": False,  # 审查异常时是否放行（True=放行，False=拦截）
            "sensitive_words_path": "data/sensitive_words.txt",
            "model_coordinator_name": "content_safety",
            "log_reviews": True,
        }
        self._data = {**default_config, **(config_dict or {})}

    def __getattr__(self, item):
        if item in self._data:
            return self._data[item]
        raise AttributeError(f"Config key '{item}' not found")

    @classmethod
    def from_yaml(cls, path: str) -> 'SafetyConfig':
        # 预留 YAML 加载接口，实际实现时期补充
        raise NotImplementedError("YAML loading not yet implemented")

# ------------------------------
# 审查结果数据类
# ------------------------------
class ReviewResult:
    """
    标准化审查结果
    action: "pass" | "block" | "manual_review"
    reason: 审查原因说明
    score: 风险评分（0~1），某些策略需要
    details: 详细违规词/句子信息
    """
    def __init__(self, action: str, reason: str = "", score: float = 0.0, details: Optional[Dict] = None):
        self.action = action
        self.reason = reason
        self.score = score
        self.details = details or {}

    def __repr__(self):
        return f"ReviewResult(action={self.action}, reason={self.reason}, score={self.score})"

# ------------------------------
# 抽象审查器（定义协议，实现可插拔）
# ------------------------------
class AbstractSafetyReviewer(abc.ABC):
    """内容安全审查器抽象基类，所有具体审查器必须实现此接口"""

    @abc.abstractmethod
    def review(self, content: str, context: Optional[Dict[str, Any]] = None) -> ReviewResult:
        """
        对给定内容执行安全审查
        :param content: 待审查文本
        :param context: 上下文信息（如章节ID、作者设定、历史审查结果等）
        :return: ReviewResult 审查结果
        """
        pass

    @abc.abstractmethod
    def name(self) -> str:
        """返回审查器唯一标识名，用于注册和配置选择"""
        pass

    def on_load(self):
        """审查器加载时的初始化（可被子类重写），例如加载敏感词库到内存"""
        logger.info(f"Reviewer '{self.name()}' loaded.")

    def on_shutdown(self):
        """审查器卸载时的清理（可被子类重写）"""
        logger.info(f"Reviewer '{self.name()}' shutting down.")

# ------------------------------
# 默认安全审查器（示例实现，基于简单关键词）
# ------------------------------
class DefaultSafetyReviewer(AbstractSafetyReviewer):
    """
    默认安全审查器实现
    1. 基于敏感词列表的快速匹配
    2. 预留模型审查接口（调用20_模型协同/）
    """
    def __init__(self, config: SafetyConfig):
        self.config = config
        self.sensitive_words: List[str] = []
        self._load_sensitive_words()

    def name(self) -> str:
        return "DefaultSafetyReviewer"

    def _load_sensitive_words(self):
        """从配置的路径加载敏感词列表（可热更新）"""
        try:
            # 骨架阶段仅演示路径，不实际读取文件，实际开发时替换
            logger.info(f"Loading sensitive words from {self.config.sensitive_words_path}")
            # with open(self.config.sensitive_words_path, 'r', encoding='utf-8') as f:
            #     self.sensitive_words = [line.strip() for line in f if line.strip()]
            self.sensitive_words = ["暴力", "欺诈", "违禁示例"]  # 示例占位
        except Exception as e:
            logger.error(f"Failed to load sensitive words: {e}", exc_info=True)
            # 使用内置兜底列表
            self.sensitive_words = ["暴力", "色情"]

    def review(self, content: str, context: Optional[Dict[str, Any]] = None) -> ReviewResult:
        """
        审查流程：
        1. 关键词快速匹配
        2. (未来) 调用模型深度审查
        """
        logger.debug(f"Reviewing content (length={len(content)}) with context={context}")
        try:
            # 阶段1：关键词匹配
            for word in self.sensitive_words:
                if word in content:
                    return ReviewResult(
                        action="block",
                        reason=f"敏感词命中: {word}",
                        score=1.0,
                        details={"matched_word": word}
                    )
            # 阶段2：模型审查占位（调用20_模型协同/）
            # result = self._model_review(content)
            # if result.score > 0.7: ...

            # 默认通过
            return ReviewResult(action="pass", reason="内容安全")
        except Exception as e:
            logger.error(f"Error during review: {e}", exc_info=True)
            # 异常时根据配置决定：fail_open=True 放行，否则拦截
            if self.config.fail_open:
                return ReviewResult(action="pass", reason="审查异常，配置为放行")
            else:
                return ReviewResult(action="block", reason="审查器异常，拦截")

    def _model_review(self, content: str) -> ReviewResult:
        """
        预留调用模型审查的接口，依赖 20_模型协同/ 和 21_API模型/
        实际实现阶段填充
        """
        # TODO: 在功能实现阶段接入模型协调器
        raise NotImplementedError("Model review not yet integrated")

# ------------------------------
# 审查器注册/工厂（支持热插拔）
# ------------------------------
class ReviewerRegistry:
    """审查器注册表，支持动态添加/移除审查器实例"""

    def __init__(self):
        self._reviewers: Dict[str, AbstractSafetyReviewer] = {}

    def register(self, reviewer: AbstractSafetyReviewer):
        """注册审查器，若同名则覆盖，实现热更新"""
        logger.info(f"Registering reviewer: {reviewer.name()}")
        self._reviewers[reviewer.name()] = reviewer

    def unregister(self, name: str):
        logger.info(f"Unregistering reviewer: {name}")
        self._reviewers.pop(name, None)

    def get(self, name: str) -> Optional[AbstractSafetyReviewer]:
        return self._reviewers.get(name)

    def list_names(self) -> List[str]:
        return list(self._reviewers.keys())

    def default_reviewer(self) -> AbstractSafetyReviewer:
        """返回默认审查器，可在配置中指定"""
        default_name = SafetyConfig().__getattr__("default_reviewer")
        reviewer = self._reviewers.get(default_name)
        if reviewer is None:
            raise RuntimeError(f"Default reviewer '{default_name}' not registered")
        return reviewer

# 全局注册表（单例模式用模块级变量，也可后续改为配置注入）
reviewer_registry = ReviewerRegistry()

def create_and_register_default(config: SafetyConfig):
    """工厂方法：创建默认审查器并注册到全局注册表"""
    default_reviewer = DefaultSafetyReviewer(config)
    reviewer_registry.register(default_reviewer)
    return default_reviewer

# ------------------------------
# 便捷审查函数（供外部直接调用）
# ------------------------------
def review_content(content: str, context: Optional[Dict] = None) -> ReviewResult:
    """
    对内容执行安全审查的便捷入口
    若注册表未初始化，自动使用默认配置创建审查器
    """
    try:
        reviewer = reviewer_registry.default_reviewer()
    except RuntimeError:
        logger.warning("No reviewer registered, auto-creating default with default config.")
        config = SafetyConfig()
        create_and_register_default(config)
        reviewer = reviewer_registry.default_reviewer()
    return reviewer.review(content, context)

# ------------------------------
# 自测代码（仅在直接运行本模块时执行）
# ------------------------------
if __name__ == "__main__":
    print("=== 安全审查模块自测开始 ===")
    # 初始化配置
    test_config = SafetyConfig({
        "sensitive_words_path": "data/test_words.txt",
        "fail_open": False
    })
    # 创建并注册默认审查器
    reviewer = DefaultSafetyReviewer(test_config)
    reviewer_registry.register(reviewer)

    # 测试用例
    test_cases = [
        ("这是一段普通文本，没有敏感词。", "pass"),
        ("这里提到了暴力行为。", "block"),
        ("", "pass"),
    ]
    for text, expected_action in test_cases:
        result = review_content(text)
        status = "✓" if result.action == expected_action else "✗"
        print(f"{status} 输入: {text[:20]}... -> 动作: {result.action} (期望: {expected_action}) | 原因: {result.reason}")
        assert result.action == expected_action, f"Test failed for input: {text}"

    # 测试异常容错：模拟审查异常