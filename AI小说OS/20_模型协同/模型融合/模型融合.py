"""模型融合模块 - 模型协同层

功能：融合多个模型的输出生成最终回答，支持多种融合策略（投票、加权、链式等）。
所属层：20_模型协同/（模型协同层）
依赖：无直接底层依赖，接收上层传入的模型输出列表；可能依赖配置模块。
被调用者：调度器或协同管理器，负责调用此模块融合多个模型的推理结果。
解决的问题：提高回答质量，整合不同模型优势，输出更可靠、丰富的最终结果。
设计原则：可插拔（策略类通过配置动态加载），日志记录，配置化（策略参数从配置读取）。
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import json
import os

# 获取当前模块的日志记录器
logger = logging.getLogger(__name__)


class ModelFusionBase(ABC):
    """模型融合抽象基类，定义融合接口"""

    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化融合策略
        :param config: 策略相关配置字典
        """
        self.config = config or {}
        logger.info(f"初始化融合策略: {self.__class__.__name__}, 配置: {self.config}")

    @abstractmethod
    def fuse(self, model_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        融合多个模型的输出
        :param model_outputs: 模型输出列表，每个元素为字典，至少包含 'model_name', 'output' 字段
        :return: 融合后的输出字典，结构由具体策略定义，通常包含 'final_output' 字段
        """
        pass


class VotingFusion(ModelFusionBase):
    """投票融合策略：对离散输出采用多数投票，对连续值可采用平均值等"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        # 可从配置读取投票方式，默认为"majority"
        self.voting_method = self.config.get("voting_method", "majority")

    def fuse(self, model_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        logger.info(f"VotingFusion 开始融合，模型数量: {len(model_outputs)}, 投票方式: {self.voting_method}")
        # 简单的实现：假设输出都是字符串，直接多数投票
        # 实际实现需根据输出类型做更复杂处理，这里给出骨架
        outputs = [item.get("output", "") for item in model_outputs]
        if self.voting_method == "majority":
            # 统计出现次数最多的输出
            from collections import Counter
            counter = Counter(outputs)
            most_common = counter.most_common(1)
            if most_common:
                final_output = most_common[0][0]
            else:
                final_output = ""
        else:
            # 其他投票方法，例如平均（如果是数值）暂不实现
            final_output = " ".join(outputs)  # 简单拼接

        logger.debug(f"VotingFusion 融合结果: {final_output[:50]}...")
        return {"final_output": final_output, "method": "voting"}


class WeightedFusion(ModelFusionBase):
    """加权融合策略：每个模型输出有不同权重，组合生成最终输出"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        # 从配置中读取模型权重，如果未提供则等权重
        self.weights = self.config.get("weights", None)
        # 权重应该是一个字典：{model_name: weight}

    def fuse(self, model_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        logger.info(f"WeightedFusion 开始融合，模型数量: {len(model_outputs)}")
        # 如果没有提供权重，默认平均
        if self.weights is None:
            logger.debug("未指定权重，使用等权重")
            # 简单拼接，实际可能embedding加权等
            combined = " [SEP] ".join([item.get("output", "") for item in model_outputs])
        else:
            # 根据权重组合，此处演示字符串拼接（真实应用可能是向量加权和）
            weighted_parts = []
            for item in model_outputs:
                model_name = item.get("model_name", "unknown")
                weight = self.weights.get(model_name, 0)
                if weight > 0:
                    weighted_parts.append(item.get("output", "") * weight)  # 简单重复字符串表示加权
            combined = " ".join(weighted_parts)
        logger.debug(f"WeightedFusion 融合结果: {combined[:50]}...")
        return {"final_output": combined, "method": "weighted"}


class ChainFusion(ModelFusionBase):
    """链式融合策略：按顺序将前一个模型的输出作为下一个模型的输入（需模型支持），但在此骨架中仅演示顺序组合输出"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.chain_order = self.config.get("chain_order", [])  # 模型名称顺序列表

    def fuse(self, model_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        logger.info(f"ChainFusion 开始融合，链式顺序: {self.chain_order}")
        # 按照chain_order排列输出，然后串联
        ordered_outputs = []
        model_map = {item.get("model_name"): item for item in model_outputs}
        for model_name in self.chain_order:
            if model_name in model_map:
                ordered_outputs.append(model_map[model_name].get("output", ""))
            else:
                logger.warning(f"链中模型 {model_name} 不在输入中，跳过")
        # 用特殊分隔符连接，模拟逐步增强
        final_output = " -> ".join(ordered_outputs)
        logger.debug(f"ChainFusion 融合结果: {final_output[:50]}...")
        return {"final_output": final_output, "method": "chained"}


# 融合策略工厂，支持从配置动态加载
FUSION_STRATEGY_MAP = {
    "voting": VotingFusion,
    "weighted": WeightedFusion,
    "chain": ChainFusion,
}


def create_fusion(strategy_name: str, strategy_config: Optional[Dict[str, Any]] = None) -> ModelFusionBase:
    """
    根据名称和配置创建融合策略实例
    :param strategy_name: 融合策略名称，如 'voting', 'weighted', 'chain'
    :param strategy_config: 该策略的具体配置字典
    :return: 融合策略实例
    """
    if strategy_name not in FUSION_STRATEGY_MAP:
        logger.error(f"未知的融合策略: {strategy_name}, 可用策略: {list(FUSION_STRATEGY_MAP.keys())}")
        raise ValueError(f"未知融合策略: {strategy_name}")
    strategy_class = FUSION_STRATEGY_MAP[strategy_name]
    instance = strategy_class(config=strategy_config or {})
    logger.info(f"成功创建融合策略: {strategy_name}")
    return instance


# 配置加载辅助函数（可选，实际使用时系统应有统一配置加载）
def load_fusion_config_from_file(config_path: str) -> Dict[str, Any]:
    """
    从JSON文件读取融合相关配置
    :param config_path: 配置文件路径
    :return: 配置字典
    """
    if not os.path.exists(config_path):
        logger.warning(f"配置文件不存在: {config_path}，使用默认配置")
        return {}
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"成功加载融合配置: {config_path}")
        return config.get("model_fusion", {})
    except Exception as e:
        logger.error(f"加载配置文件出错: {e}")
        return {}


def get_fusion_strategy(config: Dict[str, Any]) -> ModelFusionBase:
    """
    从配置字典中获取融合策略实例
    期望 config 包含 "type" 字段指定策略名称，以及该策略的参数
    """
    strategy_type = config.get("type", "voting")
    strategy_params = config.get("params", {})
    return create_fusion(strategy_type, strategy_params)


# 自测代码
if __name__ == "__main__":
    # 设置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 模拟模型输出
    mock_outputs = [
        {"model_name": "model_a", "output": "今天天气很好，适合出去散步。"},
        {"model_name": "model_b", "output": "今天天气很好，适宜户外活动。"},
        {"model_name": "model_c", "output": "天气晴朗，可以外出。"}
    ]

    # 测试1：投票融合
    print("=== 测试 VotingFusion ===")
    voting_config = {"type": "voting", "params": {"voting_method": "majority"}}
    fusion = get_fusion_strategy(voting_config)
    result = fusion.fuse(mock_outputs)
    print(f"最终输出: {result['final_output']}\n")

    # 测试2：加权融合（未提供权重，等权）
    print("=== 测试 WeightedFusion (等权) ===")
    weighted_config = {"type": "weighted", "params": {}}
    fusion = get_fusion_strategy(weighted_config)
    result = fusion.fuse(mock_outputs)
    print(f"最终输出: {result['final_output']}\n")

    # 测试3：链式融合
    print("=== 测试 ChainFusion ===")
    chain_config = {
        "type": "chain",
        "params": {"chain_order": ["model_a", "model_b", "model_c"]}
    }
    fusion = get_fusion_strategy(chain_config)
    result = fusion.fuse(mock_outputs)
    print(f"最终输出: {result['final_output']}\n")

    # 测试4：动态加载未定义策略（应报错）
    print("=== 测试未知策略 ===")
    try:
        create_fusion("unknown")
    except ValueError as e:
        print(f"预期错误: {e}")

    print("模型融合模块自测完成。")