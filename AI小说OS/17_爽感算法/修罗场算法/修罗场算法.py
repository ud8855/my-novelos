import logging
import json
from typing import Dict, Any, Optional, List

# ============================================================================
# 17_爽感算法/修罗场算法
# 层归属：算法层 (17_爽感算法)，提供剧情爽感计算中的修罗场场景量化评分
# 依赖：无直接UI/Runtime/数据库依赖，仅依赖标准抽象（可注入外部上下文提供器）
# 被调用：由上层剧情生成调度器（如15_剧情生成器）调用，用于评估情节冲撞程度
# 解决问题：将“修罗场”这一抽象叙事元素转化为可计算的冲突度、紧张感数值，
#          为 AI 写修罗场剧情提供量化指导
# 设计原则：可插拔、配置化、日志、异常恢复、单一职责
# ============================================================================

class AsuraFieldAlgorithm:
    """
    修罗场算法核心类。
    根据当前剧情上下文（人物关系、场景冲突线索等）计算修罗场指数。
    可插拔：通过统一接口 evaluate() 工作，实例化时注入配置，支持动态替换。
    """

    # ------------------------------------------------------------------
    # 默认配置（可被外部配置覆盖）
    # ------------------------------------------------------------------
    DEFAULT_CONFIG = {
        "conflict_threshold": 0.7,       # 冲突触发阈值，高于此值视为修罗场成立
        "character_count_penalty": 0.2,  # 角色数量惩罚系数（人越多越容易修罗场）
        "relation_weights": {            # 人物关系类型基础权重
            "爱人": 1.0,
            "前任": 0.8,
            "情敌": 0.9,
            "闺蜜": 0.6,
            "普通朋友": 0.3,
        },
        "history_impact_factor": 0.5,    # 历史冲突对当前影响的衰减因子
        "max_score": 1.0,                # 最大评分上限
        "min_score": 0.0                 # 最小评分下限
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None, logger: Optional[logging.Logger] = None):
        """
        初始化修罗场算法。

        :param config: 用户自定义配置字典，与 DEFAULT_CONFIG 合并。
        :param logger: 注入的日志记录器，若为 None 则内部创建默认 logger。
        """
        # 合并配置
        if config is None:
            self.config = self.DEFAULT_CONFIG.copy()
        else:
            self.config = {**self.DEFAULT_CONFIG, **config}

        # 日志：优先使用外部注入，否则创建独立 logger（可被外部统一管理）
        if logger is None:
            self.logger = logging.getLogger(self.__class__.__name__)
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                fmt = logging.Formatter(
                    '[%(asctime)s] [%(levelname)s] %(name)s:%(lineno)d - %(message)s'
                )
                handler.setFormatter(fmt)
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.DEBUG)
        else:
            self.logger = logger

        self.logger.info("修罗场算法初始化完毕，配置：%s", json.dumps(self.config, ensure_ascii=False))

        # 可扩展：未来可加载模型协同器、情感分析器等，但请勿直接依赖，通过接口注入
        self.external_services = {}  # 预留外部服务插槽

    def evaluate(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估当前剧情上下文中的修罗场程度。

        :param context: 输入上下文，必须包含：
            - characters: List[Dict]  人物列表，每人含 'name', 'relations' (关系列表，含'type'与'with'等)
            - scene_keywords: List[str] 场景关键词
            - previous_conflict_score: float 历史修罗场分数（可选）
        :return: 结果字典，包含：
            - asura_score: float 修罗场综合评分 [0,1]
            - triggered: bool 是否触发修罗场（超过阈值）
            - sub_scores: Dict 各子项评分细节
        """
        self.logger.info("开始评估修罗场，上下文摘要：角色数=%d", len(context.get('characters', [])))
        try:
            # 参数校验
            if not isinstance(context, dict):
                raise ValueError("context 必须是字典类型")
            characters = context.get('characters', [])
            if not isinstance(characters, list):
                raise ValueError("characters 必须是列表")

            # -------------------------
            # 骨架计算逻辑（仅示意，后续实现）
            # -------------------------
            # 1. 关系冲突度
            relation_conflict = self._calc_relation_conflict(characters)
            # 2. 场景催化剂
            scene_catalyst = self._calc_scene_catalyst(context.get('scene_keywords', []))
            # 3. 历史影响
            previous_score = context.get('previous_conflict_score', 0.0)
            history_boost = previous_score * self.config['history_impact_factor']

            # 综合评分（骨架简单加权）
            raw_score = (relation_conflict * 0.5) + (scene_catalyst * 0.3) + history_boost
            raw_score = max(self.config['min_score'], min(self.config['max_score'], raw_score))

            # 判断触发
            triggered = raw_score >= self.config['conflict_threshold']

            result = {
                'asura_score': round(raw_score, 4),
                'triggered': triggered,
                'sub_scores': {
                    'relation_conflict': relation_conflict,
                    'scene_catalyst': scene_catalyst,
                    'history_boost': history_boost
                }
            }
            self.logger.info("修罗场评估完成，得分：%.4f，触发：%s", result['asura_score'], result['triggered'])
            return result

        except Exception as e:
            self.logger.error("修罗场评估失败：%s", str(e), exc_info=True)
            # 异常恢复：返回无冲突默认结果
            return {
                'asura_score': 0.0,
                'triggered': False,
                'sub_scores': {},
                'error': str(e)
            }

    # ------------------------------------------------------------------
    # 内部计算方法（骨架占位，后续具体算法在此扩展）
    # ------------------------------------------------------------------
    def _calc_relation_conflict(self, characters: List[Dict]) -> float:
        """
        基于人物关系计算冲突度。
        当前仅实现关系权重累加骨架，具体业务逻辑待后续填充。
        """
        if not characters:
            return 0.0

        conflict = 0.0
        relation_weights = self.config['relation_weights']
        # 人物数量影响（骨架）
        count_penalty = len(characters) * self.config['character_count_penalty']

        for char in characters:
            relations = char.get('relations', [])
            for rel in relations:
                rel_type = rel.get('type', '')
                # 获取关系权重
                weight = relation_weights.get(rel_type, 0.0)
                conflict += weight * 0.1  # 示意系数

        # 归一化（暂简单截断）
        conflict = min(1.0, conflict + count_penalty)
        return conflict

    def _calc_scene_catalyst(self, keywords: List[str]) -> float:
        """
        场景关键词对修罗场的催化效果。
        目前仅返回固定值，实际将根据关键词库加权计算。
        """
        # 预留关键词强度映射
        catalyst_keywords = {
            "误会": 0.3,
            "撞见": 0.5,
            "表白": 0.4,
            "囚禁": 0.7,
            "修罗场": 1.0
        }
        score = 0.0
        for kw in keywords:
            score += catalyst_keywords.get(kw, 0.1)
        return min(1.0, score)

    # ------------------------------------------------------------------
    # 可插拔支持：动态重载配置、重置状态等
    # ------------------------------------------------------------------
    def update_config(self, new_config: Dict[str, Any]):
        """运行时更新配置，实现热更新"""
        self.config.update(new_config)
        self.logger.info("配置已更新：%s", json.dumps(new_config, ensure_ascii=False))

    def reset(self):
        """重置内部状态（若有缓存）"""
        self.logger.debug("重置内部状态（目前无状态）")

    def load_external_service(self, name: str, service: Any):
        """注入外部服务（如情感分析器、模型协同器），保持可插拔"""
        self.external_services[name] = service
        self.logger.info("已加载外部服务：%s", name)


# ============================================================================
# 自测部分（仅在直接执行此脚本时运行）
# ============================================================================
if __name__ == "__main__":
    # 构造测试上下文
    test_context = {
        'characters': [
            {
                'name': '苏绫',
                'relations': [
                    {'type': '爱人', 'with': '陆霆'},
                    {'type': '情敌', 'with': '白若'}
                ]
            },
            {
                'name': '白若',
                'relations': [
                    {'type': '爱慕', 'with': '陆霆'},
                    {'type': '情敌', 'with': '苏绫'}
                ]
            },
            {
                'name': '陆霆',
                'relations': [
                    {'type': '爱人', 'with': '苏绫'},
                    {'type': '前任', 'with': '白若'}
                ]
            }
        ],
        'scene_keywords': ['撞见', '误会', '修罗场'],
        'previous_conflict_score': 0.4
    }

    # 测试默认算法
    algo = AsuraFieldAlgorithm()
    result = algo.evaluate(test_context)
    print("==== 测试结果 ====")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 测试自定义配置
    custom_config = {"conflict_threshold": 0.5}
    algo2 = AsuraFieldAlgorithm(config=custom_config)
    result2 = algo2.evaluate(test_context)
    print("==== 采用自定义阈值0.5 ====")
    print(json.dumps(result2, indent=2, ensure_ascii=False))

    # 测试热更新配置
    algo.update_config({"character_count_penalty": 0.5})
    result3 = algo.evaluate(test_context)
    print("==== 热更新后（惩罚系数0.5） ====")
    print(json.dumps(result3, indent=2, ensure_ascii=False))

    print("自测完成。")