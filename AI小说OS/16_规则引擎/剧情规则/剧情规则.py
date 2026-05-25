"""
模块路径: 16_规则引擎/剧情规则/剧情规则.py
功能: 定义剧情规则接口和基础实现，支持可插拔的剧情规则检查，提供日志、配置化支持。
依赖: 基础工具包（logging, config），可能依赖 20_模型协同/ 或 21_API模型/ 但这里只是骨架，不真正调用。
被调用者: 上层剧情检查模块、生成控制模块等。
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class PlotRule(ABC):
    """
    剧情规则抽象基类。
    所有具体的剧情规则必须继承此类并实现 check 方法。
    """

    def __init__(self, rule_id: str, config: Optional[Dict[str, Any]] = None):
        """
        :param rule_id: 规则唯一标识
        :param config: 规则配置参数字典，可选项
        """
        self.rule_id = rule_id
        self.config = config if config else {}
        self._init_logging()

    def _init_logging(self):
        level = self.config.get('log_level', 'INFO')
        logger.setLevel(level)

    @abstractmethod
    def check(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        检查给定上下文是否符合本规则。
        :param context: 包含剧情片段、元数据等的字典
        :return: 检查结果字典，至少包含 'status' ('PASS'/'FAIL') 和 'message'
        """
        pass

    def validate_context(self, context: Dict[str, Any]) -> bool:
        if 'plot_node' not in context:
            logger.warning(f"规则 {self.rule_id}: 上下文中缺少 'plot_node'")
            return False
        return True

    def log_result(self, context: Dict[str, Any], result: Dict[str, Any]):
        status = result.get('status', 'UNKNOWN')
        node_id = context.get('plot_node', {}).get('id', 'N/A')
        logger.info(f"规则 {self.rule_id} 对节点 {node_id} 检查结果: {status} - {result.get('message', '')}")

    def __call__(self, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate_context(context):
            return {'status': 'FAIL', 'message': f'规则 {self.rule_id} 上下文验证失败'}
        try:
            result = self.check(context)
            self.log_result(context, result)
            return result
        except Exception as e:
            logger.error(f"规则 {self.rule_id} 执行异常: {str(e)}")
            return {'status': 'FAIL', 'message': str(e)}


class ConflictRule(PlotRule):
    """
    具体剧情规则：检查剧情冲突是否合理（示例）。
    """
    def check(self, context: Dict[str, Any]) -> Dict[str, Any]:
        plot_node = context['plot_node']
        if plot_node.get('event_type') == 'conflict' and 'conflict_level' not in plot_node:
            return {'status': 'FAIL', 'message': '冲突事件缺少冲突等级定义'}
        return {'status': 'PASS', 'message': '剧情冲突检查通过'}


class RuleRegistry:
    """
    规则注册表，用于管理可插拔的规则集合。
    """
    def __init__(self):
        self._rules: Dict[str, PlotRule] = {}

    def register(self, rule: PlotRule):
        if rule.rule_id in self._rules:
            logger.warning(f"规则 {rule.rule_id} 已被覆盖")
        self._rules[rule.rule_id] = rule
        logger.info(f"规则 {rule.rule_id} 已注册")

    def remove(self, rule_id: str):
        if rule_id in self._rules:
            del self._rules[rule_id]
            logger.info(f"规则 {rule_id} 已移除")

    def get(self, rule_id: str) -> Optional[PlotRule]:
        return self._rules.get(rule_id)

    def apply_all(self, context: Dict[str, Any]) -> Dict[str, Any]:
        results = {}
        for rule_id, rule in self._rules.items():
            result = rule(context)
            results[rule_id] = result
        fail_rules = [rid for rid, res in results.items() if res.get('status') == 'FAIL']
        if fail_rules:
            return {
                'status': 'FAIL',
                'message': f'以下规则未通过: {fail_rules}',
                'details': results
            }
        return {'status': 'PASS', 'message': '所有剧情规则通过', 'details': results}

    def get_all_rule_ids(self) -> List[str