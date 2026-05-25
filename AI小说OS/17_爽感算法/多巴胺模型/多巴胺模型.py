"""
多巴胺模型 - 小说爽感量化评估算法
层：17_爽感算法
依赖：无（纯算法层），可被叙事引擎调用
被谁调用：上层编排器（如18_叙事引擎）
解决：将文本快感度抽象为可插拔的评估器，支持配置权重、关键词与复合策略
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any

# ----------------------------
# 日志配置
# ----------------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

# ----------------------------
# 基础抽象类
# ----------------------------
class DopamineModelBase(ABC):
    """
    多巴胺模型抽象基类
    所有爽感评估器必须实现此接口，保证可插拔性。
    """

    @abstractmethod
    def evaluate(self, text: str, context: Optional[Dict[str, Any]] = None) -> float:
        """
        评估文本的爽感指数
        :param text: 待评估文本
        :param context: 可选上下文信息（如章节元数据）
        :return: 爽感分数，范围 [0.0, 1.0]，越高越爽
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """重置模型内部状态（如存在）"""
        pass

# ----------------------------
# 默认实现：关键词+规则混合模型
# ----------------------------
class DefaultDopamineModel(DopamineModelBase):
    """
    基于关键词和简单规则的多巴胺模型
    支持配置关键词及其爽感权重，结合长度衰减、重复惩罚等规则。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化模型
        :param config: 配置字典，可包含：
            - keywords: List[Dict], 每个元素含 word (str), weight (float)
            - default_weight: 默认权重（找不到关键字时的基准衰减因子）
            - decay_factor: 长度衰减系数（越长的文本单点爽感越被稀释）
            - boost_repeat: 同一关键字重复出现是否加成（bool）
            - repeat_boost_max: 重复加成上限
        """
        self.config = self._load_default_config()
        if config:
            self.config.update(config)
        self.keywords = self._build_keyword_map(self.config.get('keywords', []))
        logger.info(f"DefaultDopamineModel 初始化完成，关键词数量：{len(self.keywords)}")

    def _load_default_config(self) -> Dict[str, Any]:
        """提供默认配置，确保模型零参数也可运行"""
        return {
            "keywords": [
                {"word": "突破", "weight": 0.3},
                {"word": "升级", "weight": 0.4},
                {"word": "觉醒", "weight": 0.5},
                {"word": "金手指", "weight": 0.6},
                {"word": "碾压", "weight": 0.4},
                {"word": "打脸", "weight": 0.35},
                {"word": "奇遇", "weight": 0.3},
                {"word": "大神", "weight": 0.2},
            ],
            "default_weight": 0.1,
            "decay_factor": 0.001,  # 每1000字衰减0.1
            "boost_repeat": True,
            "repeat_boost_max": 1.5,
            "base_score": 0.2,
        }

    def _build_keyword_map(self, keyword_list: List[Dict[str, Any]]) -> Dict[str, float]:
        """将关键字列表转为映射表，便于快速查找"""
        kmap = {}
        for item in keyword_list:
            word = item.get("word", "")
            weight = item.get("weight", 0.0)
            if word:
                kmap[word] = weight
        return kmap

    def evaluate(self, text: str, context: Optional[Dict[str, Any]] = None) -> float:
        """
        评估爽感：
        1. 统计所有匹配的关键字，根据出现次数和权重计算原始爽感分；
        2. 应用长度衰减、重复加成；
        3. 返回裁剪到 [0.0, 1.0] 的最终分。
        """
        if not text:
            return 0.0

        text_length = len(text)
        base_score = self.config.get("base_score", 0.2)
        decay_factor = self.config.get("decay_factor", 0.001)
        boost_repeat = self.config.get("boost_repeat", True)
        repeat_boost_max = self.config.get("repeat_boost_max", 1.5)

        # 统计关键词出现次数和加权和
        word_hits = {}
        raw_score = 0.0
        for word, weight in self.keywords.items():
            # 简单子串匹配（后续可替换为更精准的分词匹配）
            count = text.count(word)
            if count > 0:
                word_hits[word] = count
                # 出现一次得基础权重，出现多次可选加成
                if boost_repeat:
                    # 线性加成，但设置上限
                    boost = min(1.0 + 0.1 * (count - 1), repeat_boost_max)
                else:
                    boost = 1.0
                raw_score += weight * count * boost

        # 长度衰减：文本越长，单位爽感被稀释（模拟读者注意力分散）
        length_penalty = 1.0 / (1.0 + decay_factor * text_length)

        # 最终分数 = 基础分 + 加权关键词分 * 衰减因子
        final_score = base_score + raw_score * length_penalty

        # 裁剪到 [0,1]
        final_score = max(0.0, min(1.0, final_score))

        logger.debug(
            f"评估文本长{text_length}，关键词命中{word_hits}，原始分{raw_score:.3f}，"
            f"衰减系数{length_penalty:.3f}，最终分{final_score:.3f}"
        )
        return final_score

    def reset(self) -> None:
        """默认模型无状态，无需重置"""
        pass

# ----------------------------
# 工厂函数（可插拔入口）
# ----------------------------
def create_dopamine_model(model_type: str = "default", config: Optional[Dict[str, Any]] = None) -> DopamineModelBase:
    """
    模型工厂，根据类型返回对应实例
    :param model_type: 模型类型标识，当前仅支持 "default"
    :param config: 配置字典
    :return: DopamineModelBase 实例
    """
    if model_type == "default":
        return DefaultDopamineModel(config)
    else:
        logger.error(f"未知的多巴胺模型类型: {model_type}")
        raise ValueError(f"Unsupported model type: {model_type}")

# ----------------------------
# 自测代码（仅在直接运行时执行）
# ----------------------------
if __name__ == "__main__":
    # 设置日志级别，方便自测观察
    logging.getLogger().setLevel(logging.DEBUG)

    print("=== 多巴胺模型自测 ===")
    model = create_dopamine_model("default")

    test_texts = [
        "主角正在走路，突然掉进山洞获得金手指，从此一路突破升级，碾压所有对手。",
        "少年觉醒神秘力量，打脸所有看不起他的人，感觉自己就是这个世界的大神。",
        "今天天气真好，我去菜市场买了西红柿和鸡蛋。",
        "他低头看了一眼手机，然后抬起头，默默离开了。",
    ]

    for text in test_texts:
        score = model.evaluate(text)
        print(f"\n文本：{text[:40]}...")
        print(f"爽感指数：{score:.4f}")

    # 测试重置
    model.reset()
    print("\n模型重置完成（无状态模型无明显效果）")