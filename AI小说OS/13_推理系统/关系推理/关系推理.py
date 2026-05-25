"""13_推理系统/关系推理/关系推理.py

所属层：推理子系统
依赖：日志模块、配置管理模块（通过接口注入）
被谁调用：剧情管理器、角色管理器、冲突检测器等需要推断角色/事件之间关系的模块
解决问题：根据输入实体集合和上下文信息，推理并输出关系类型、强度、方向，支持可插拔的多种关系推理策略
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

# 默认配置
DEFAULT_CONFIG = {
    "log_level": "INFO",
    "relation_types": ["亲属", "敌对", "盟友", "师徒", "恋人", "利用", "未知"],
    "min_confidence": 0.6,
    "inference_method": "rule_based",  # 可扩展: "llm", "hybrid"
}


class RelationalInference:
    """关系推理器主类，负责根据剧情上下文推断实体间的关系。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化关系推理器。

        :param config: 配置字典，若为None则使用默认配置
        """
        self.config = config if config is not None else DEFAULT_CONFIG.copy()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup_logging()
        self.logger.info("关系推理模块初始化完成")

    def _setup_logging(self) -> None:
        """根据配置设置日志级别和格式，确保日志可插拔。"""
        log_level = self.config.get("log_level", "INFO").upper()
        self.logger.setLevel(getattr(logging, log_level, logging.INFO))
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def infer_relations(
        self,
        entities: List[Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        主推理入口，返回实体间的关系列表。

        :param entities: 参与推理的实体列表（至少两个实体）
        :param context: 可选的上下文信息（场景描述、对话等）
        :return: 关系字典列表，每个字典包含 source, target, type, confidence 等字段
        """
        if len(entities) < 2:
            self.logger.warning("实体数量不足，无法推断关系")
            return []

        self.logger.debug(f"开始推理关系，实体数量: {len(entities)}, 上下文: {bool(context)}")

        # 根据配置调用不同的推理策略
        method = self.config.get("inference_method", "rule_based")
        if method == "rule_based":
            results = self._rule_based_inference(entities, context)
        elif method == "llm":
            results = self._llm_based_inference(entities, context)
        elif method == "hybrid":
            results = self._hybrid_inference(entities, context)
        else:
            self.logger.error(f"未知的推理方法: {method}")
            return []

        # 过滤低置信度关系
        min_conf = self.config.get("min_confidence", 0.6)
        filtered = [r for r in results if r.get("confidence", 0.0) >= min_conf]

        self.logger.info(f"推断出 {len(filtered)} 个高置信度关系")
        return filtered

    def _rule_based_inference(
        self,
        entities: List[Any],
        context: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        基于规则的关系推理（占位实现）。
        在实际系统中可从知识库或规则引擎获取关系，此处返回空列表示例。
        """
        self.logger.debug("使用基于规则的推理")
        # TODO: 实现实际规则匹配逻辑
        return []

    def _llm_based_inference(
        self,
        entities: List[Any],
        context: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        基于大语言模型的关系推理（占位实现）。
        依赖 21_API模型/ 和 20_模型协同/，此处仅返回空列表。
        """
        self.logger.debug("使用 LLM 推理")
        # TODO: 集成模型调用接口
        return []

    def _hybrid_inference(
        self,
        entities: List[Any],
        context: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        混合推理：先规则，无法确定时调用LLM（占位实现）。
        """
        self.logger.debug("使用混合推理")
        # TODO: 组合规则和LLM结果
        return []

    def add_relation_type(self, new_type: str) -> None:
        """
        热插拔：动态添加新的关系类型。
        """
        if new_type not in self.config["relation_types"]:
            self.config["relation_types"].append(new_type)
            self.logger.info(f"添加新关系类型: {new_type}")

    def reload_config(self, new_config: Dict[str, Any]) -> None:
        """
        热更新：重新加载配置，无需重启模块。
        """
        self.config.update(new_config)
        self._setup_logging()
        self.logger.info("配置已热更新")


if __name__ == "__main__":
    # ------------------ 自测 ------------------
    # 配置简单的日志输出
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # 创建推理器实例
    rel_infer = RelationalInference()
    print("--- 测试1：实体不足 ---")
    res1 = rel_infer.infer_relations(["张三"])
    print("结果:", res1)

    print("\n--- 测试2：正常推理（规则占位） ---")
    entities = ["主角", "反派首领"]
    context = {"场景": "悬赏令发布现场", "对话": "你欠我的，迟早要还"}
    res2 = rel_infer.infer_relations(entities, context)
    print("结果:", res2)

    print("\n--- 测试3：热添加关系类型 ---")
    rel_infer.add_relation_type("伪装")
    print("当前关系类型:", rel_infer.config["relation_types"])

    print("\n--- 测试4：配置热更新 ---")
    rel_infer.reload_config({"min_confidence": 0.8})
    print("新最低置信度:", rel_infer.config["min_confidence"])

    print("\n自测完成，模块工作正常。")