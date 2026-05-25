"""
审核Agent模块 - 负责对生成内容进行合规性、质量等审核
依赖：20_模型协同/审核协调器，21_API模型/具体API（通过协调器调用）
被调用：由任务调度器或工作流引擎调用
解决：确保生成内容符合内容政策、质量标准、风格一致性等
"""

import logging
import json
from typing import Dict, Any, Optional

# 假设的Agent基类，实际项目中从agent_base模块导入
try:
    from agent_base import BaseAgent
except ImportError:
    # 如果基类不存在，定义简单的基类以便独立运行
    class BaseAgent:
        def __init__(self, config: Dict[str, Any] = None):
            self.config = config or {}
            self.logger = logging.getLogger(self.__class__.__name__)

        def run(self, *args, **kwargs):
            raise NotImplementedError


class ReviewAgent(BaseAgent):
    """审核Agent，可插拔的审核功能模块"""

    def __init__(self, config: Dict[str, Any] = None, model_coordinator: Any = None):
        """
        初始化审核Agent
        :param config: 配置字典，包含审核规则、阈值等
        :param model_coordinator: 模型协调器，用于调用审核模型（20_模型协同/审核协调器）
        """
        super().__init__(config)
        self.logger = logging.getLogger(__name__)
        self.model_coordinator = model_coordinator  # 注入依赖，符合跨层调用规范
        # 从配置加载审核规则，若缺失则使用默认
        self.rules = self._load_rules()
        self.logger.info("审核Agent初始化完成，加载 %d 条审核规则", len(self.rules))

    def _load_rules(self) -> Dict[str, Any]:
        """从配置加载审核规则，支持热更新"""
        default_rules = {
            "prohibited_keywords": [],
            "min_quality_score": 0.6,
            "style_consistency_threshold": 0.8,
            "max_repetition_ratio": 0.3,
        }
        if self.config and "review_rules" in self.config:
            rules = self.config["review_rules"]
            # 可扩展：从文件加载规则
            if isinstance(rules, str):
                try:
                    with open(rules, 'r', encoding='utf-8') as f:
                        rules = json.load(f)
                except Exception as e:
                    self.logger.error("加载审核规则文件失败: %s, 使用默认规则", e)
                    rules = default_rules
            return rules
        return default_rules

    def update_rules(self, new_rules: Dict[str, Any]):
        """热更新规则，无需重启Agent"""
        self.rules.update(new_rules)
        self.logger.info("审核规则已更新，当前规则: %s", self.rules)

    def