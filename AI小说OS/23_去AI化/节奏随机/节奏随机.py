"""
模块：节奏随机 (RhythmRandomizer)
所属层：23_去AI化
依赖：无
被谁调用：去AI化管线，或直接作为处理器
功能：对文本的句子节奏进行随机化处理，模拟人类写作的节奏波动，降低AI痕迹。
设计：可插拔、配置化、日志化、自测。
"""

import json
import logging
import random
from pathlib import Path
from typing import Dict, List, Optional

# ─── 默认配置 ──────────────────────────────────────────
DEFAULT_CONFIG = {
    "sentence_length": {
        "min_chars": 5,            # 最小句子长度（字符数）
        "max_chars": 80,           # 最大句子长度
        "target_mean": 20,         # 目标均值
        "variance": 8              # 随机变动的标准差
    },
    "combine_probability": 0.3,    # 合并两个短句的概率
    "split_probability": 0.2,      # 拆分长句的概率
    "paragraph_break_probability": 0.15,  # 在句号后插入换行的概率
    # 停顿标记随机插入的概率
    "punctuation_variety": {
        "ellipsis_prob": 0.1,      # 插入‘……’的概率
        "exclamation_prob": 0.05,  # 插入‘！’的概率
        "question_prob": 0.03      # 插入‘？’的概率
    }
}


class RhythmRandomizer:
    """
    节奏随机化器
    通过对输入文本随机调整句子长度、合并/拆分句子、插入停顿标点、
    随机分段等方式模拟人类写作习惯，使输出更“自然”。
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化节奏随机器

        Args:
            config_path: 可选，JSON 配置文件路径；若为 None 则使用默认配置
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("初始化节奏随机器")
        self.config = self.load_config(config_path)
        # 设置随机种子为 None 以使用系统熵（需要时可配置成固定值用于复现）
        self.rng = random.Random()

    def load_config(self, config_path: Optional[Path]) -> Dict:
        """
        加载配置：优先使用配置文件，否则用默认配置

        Args:
            config_path: JSON 配置文件路径

        Returns:
            配置字典
        """
        if config_path is not None and config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                self.logger.info(f"已从 {config_path} 加载配置")
                # 合并默认配置（缺少的键使用默认值）
                merged = DEFAULT_CONFIG.copy()
                merged.update(user_config)
                return merged
            except Exception as e:
                self.logger.error(f"加载配置失败: {e}，使用默认配置")
        else:
            self.logger.info("未提供配置文件，使用默认配置")
        return DEFAULT_CONFIG.copy()

    def randomize_rhythm(self, text: str) -> str:
        """
        对输入文本进行节奏随机化

        Args:
            text: 原始文本

        Returns:
            随机化后的文本
        """
        if not text:
            return text

        self.logger.debug(f"开始节奏随机化，输入长度: {len(text)} 字符")

        # 1. 按句号、叹号、问号等切分为原始句子列表（保留标点）
        raw_sentences = self._split_into_sentences(text)

        # 2. 对句子列表进行随机合并/拆分处理
        processed = self._adjust_sentence_length(raw_sentences)

        # 3. 随机调整标点，插入额外停顿符号
        enriched = self._randomize_punctuation(processed)

        # 4. 随机插入段落分隔
        final_text = self._add_random_paragraph_breaks(enriched)

        self.logger.debug(f"节奏随机化完成，输出长度: {len(final_text)} 字符")
        return final_text

    def _split_into_sentences(self, text: str) -> List[str]:
        """
        将文本按常见句子结束标点切分成句子列表，保留标点

        Args:
            text: 文本

        Returns:
            句子列表，每个元素为完整的句子（包含结尾标点）
        """
        import re
        # 使用正则按句子边界切分，并包含分界符
        pattern = r'(?<=[。！？.!?…])'
        parts = re.split(pattern, text)
        # 移除空元素并将分隔符合并到前一句
        sentences = []
        current = ""
        for part in parts:
            if not part:
                continue
            if current and not re.search(r'[。！？.!?…]$', current):
                current += part
            else:
                if current:
                    sentences.append(current)
                current = part
        if current:
            sentences.append(current)
        return [s.strip() for s in sentences if s.strip()]

    def _adjust_sentence_length(self, sentences: List[str]) -> List[str]:
        """
        随机调整句子长度：合并短句或拆分长句

        Args:
            sentences: 原始句子列表

        Returns:
            调整后的句子列表
        """
        cfg = self.config["sentence_length"]
        min_len = cfg["min_chars"]
        max_len = cfg["max_chars"]

        adjusted = []
        i = 0
        while i < len(sentences):
            s = sentences[i]
            length = len(s)

            # 句子太长，且满足拆分概率
            if length > max_len and self.rng.random() < self.config["split_probability"]:
                # 简单拆分：在逗号或空格的合适位置切断
                split_candidates = self._find_split_positions(s)
                if split_candidates:
                    pos = self.rng.choice(split_candidates)
                    part1 = s[:pos].strip()
                    part2 = s[pos:].strip()
                    if part1 and part2:
                        adjusted.append(part1)
                        adjusted.append(part2)
                    else:
                        adjusted.append(s)
                else:
                    adjusted.append(s)
            # 句子太短，且下一句存在且合并概率成立
            elif length < min_len and (i + 1) < len(sentences) and \
                    self.rng.random() < self.config["combine_probability"]:
                next_s = sentences[i + 1]
                combined = s + " " + next_s
                if len(combined) <= max_len:
                    adjusted.append(combined)
                    i += 1  # 跳过下一句
                else:
                    adjusted.append(s)
            else:
                adjusted.append(s)
            i += 1

        return adjusted

    def _find_split_positions(self, sentence: str) -> List[int]:
        """
        寻找句子中合适的分割点（逗号、分号等后）

        Args:
            sentence: 句子

        Returns:
            位置索引列表
        """
        positions = []
        for idx, ch in enumerate(sentence):
            if ch in ',，;；':
                # 分割点放在符号之后
                if idx + 1 < len(sentence):
                    positions.append(idx + 1)
        return positions

    def _randomize_punctuation(self, sentences: List[str]) -> List[str]:
        """
        随机添加/替换结尾标点以产生停顿变化

        Args:
            sentences: 句子列表

        Returns:
            带随机标点的句子列表
        """
        cfg = self.config.get("punctuation_variety", {})
        new_sentences = []
        for s in sentences:
            # 不改变已有问号或感叹号的句子
            if s.endswith('?') or s.endswith('？') or s.endswith('!') or s.endswith('！'):
                new_sentences.append(s)
                continue

            # 句号结尾，可考虑随机替换为省略号、叹号等
            if s.endswith('.') or s.endswith('。'):
                base = s[:-1] if s.endswith('.') else s[:-1]  # 去除末尾标点
                rand = self.rng.random()
                if rand < cfg.get("ellipsis_prob", 0):
                    new_sentences.append(base + "……")
                elif rand < (cfg.get("ellipsis_prob", 0) + cfg.get("exclamation_prob", 0)):
                    new_sentences.append(base + "！")
                elif rand < (cfg.get("ellipsis_prob", 0) + cfg.get("exclamation_prob", 0) + cfg.get("question_prob", 0)):
                    new_sentences.append(base + "？")
                else:
                    # 保持不变
                    new_sentences.append(base + "。")
            else:
                new_sentences.append(s)
        return new_sentences

    def _add_random_paragraph_breaks(self, sentences: List[str]) -> str:
        """
        在句子之间随机插入换行来分段

        Args:
            sentences: 句子列表

        Returns:
            拼接后的文本，可能包含换行分段
        """
        cfg = self.config
        break_prob = cfg.get("paragraph_break_probability", 0.15)
        result = []
        for i, s in enumerate(sentences):
            result.append(s)
            # 在每个句号之后考虑是否换行，且不在最后一个句子后加额外换行
            if i < len(sentences) - 1 and self.rng.random() < break_prob:
                result.append("\n")
        return " ".join(result) if len(result) == 1 else "".join(result)


# ─── 自测代码 ──────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 示例文本
    test_text = (
        "今天天气真好。小猫在院子里玩耍。它一会儿追蝴蝶，一会儿扑落叶。"
        "远处传来悠扬的笛声，让人心旷神怡。仿佛整个世界都安静了下来。"
    )

    # 实例化（使用默认配置）
    randomizer = RhythmRandomizer()
    print("原始文本：")
    print(test_text)
    print("\n" + "=" * 50 + "\n")
    print("随机化后：")
    result = randomizer.randomize_rhythm(test_text)
    print(result)

    # 测试可复现性（固定种子）
    randomizer2 = RhythmRandomizer()
    # 重设随机种子以验证
    randomizer2.rng = random.Random(42)
    print("\n--- 固定种子(42)测试 ---")
    print(randomizer2.randomize_rhythm(test_text))