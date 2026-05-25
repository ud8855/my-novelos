from __future__ import annotations
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

# 添加项目根目录到 sys.path 以便导入共享模块（如日志配置）
_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.normpath(os.path.join(_this_dir, '..', '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 假设存在一个统一的日志配置工具
from _global_utils.logger import get_logger  # type: ignore


class PoliticalDetector:
    """
    政治敏感内容检测器。
    职责：对输入文本进行政治合规性检查，返回检测结果与置信度。
    特点：可插拔（通过继承或注册机制替换）、配置驱动、完整日志记录。
    """

    # 默认配置文件路径（相对于本模块目录）
    DEFAULT_CONFIG_PATH = os.path.join(_this_dir, 'political_detect_config.json')

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化检测器。
        :param config_path: 配置文件路径，若为 None 则使用默认路径。
        """
        self._config: Dict[str, Any] = {}
        self._logger: logging.Logger = get_logger(self.__class__.__name__)
        self._load_config(config_path or self.DEFAULT_CONFIG_PATH)
        self._sensitive_keywords: List[str] = self._config.get('sensitive_keywords', [])
        self._logger.info(f"PoliticalDetector initialized with {len(self._sensitive_keywords)} keywords.")

    # ------------------------------------------------------------------
    # 配置管理
    # ------------------------------------------------------------------
    def _load_config(self, config_path: str) -> None:
        """加载配置文件，若不存在则使用默认配置。"""
        if not os.path.exists(config_path):
            self._logger.warning(f"Config file not found: {config_path}, using default empty keywords.")
            self._config = {'sensitive_keywords': []}
            return
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            self._logger.info(f"Config loaded from {config_path}")
        except Exception as e:
            self._logger.error(f"Failed to load config: {e}, using empty keywords.")
            self._config = {'sensitive_keywords': []}

    def reload_config(self, config_path: Optional[str] = None) -> None:
        """热更新：重新加载配置。"""
        path = config_path or self.DEFAULT_CONFIG_PATH
        self._load_config(path)
        self._sensitive_keywords = self._config.get('sensitive_keywords', [])
        self._logger.info("Configuration reloaded.")

    # ------------------------------------------------------------------
    # 核心检测逻辑
    # ------------------------------------------------------------------
    def detect(self, text: str) -> Dict[str, Any]:
        """
        对输入文本进行政治合规检测。
        :param text: 待检测文本
        :return: 字典，包含 is_political_sensitive (bool) 和 confidence (float) 等字段
        """
        if not isinstance(text, str):
            self._logger.error(f"Invalid input type: {type(text)}, expected str.")
            return {'is_political_sensitive': False, 'confidence': 0.0, 'error': 'Invalid input type'}

        self._logger.debug(f"Detecting text (len={len(text)}): {text[:50]}...")

        # 骨架实现：仅做简单的关键词匹配
        text_lower = text.lower()
        matched_keywords = [kw for kw in self._sensitive_keywords if kw.lower() in text_lower]

        is_sensitive = len(matched_keywords) > 0
        # 置信度简单按命中关键词比例计算（最大1.0）
        confidence = min(1.0, len(matched_keywords) / max(1, len(self._sensitive_keywords)))

        result = {
            'is_political_sensitive': is_sensitive,
            'confidence': round(confidence, 4),
            'matched_keywords': matched_keywords,
            'text_length': len(text)
        }
        self._logger.info(f"Detection result: {result['is_political_sensitive']}, confidence={result['confidence']}")
        return result

    # ------------------------------------------------------------------
    # 批量检测（可扩展）
    # ------------------------------------------------------------------
    def batch_detect(self, texts: List[str]) -> List[Dict[str, Any]]:
        """批量检测多个文本。"""
        results = []
        for i, text in enumerate(texts):
            try:
                res = self.detect(text)
            except Exception as e:
                self._logger.error(f"Error at index {i}: {e}")
                res = {'is_political_sensitive': False, 'confidence': 0.0, 'error': str(e)}
            results.append(res)
        return results

    # ------------------------------------------------------------------
    # 状态查询（便于监控）
    # ------------------------------------------------------------------
    def get_status(self) -> Dict[str, Any]:
        """返回检测器状态信息。"""
        return {
            'keyword_count': len(self._sensitive_keywords),
            'config_loaded': bool(self._config),
            'example_keywords': self._sensitive_keywords[:5]
        }


# ----------------------------------------------------------------------
# 自测（运行 `python 政治检测.py` 即可）
# ----------------------------------------------------------------------
if __name__ == '__main__':
    # 临时配置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 准备测试配置文件
    test_config_path = os.path.join(_this_dir, 'political_detect_config.json')
    if not os.path.exists(test_config_path):
        default_config = {
            "sensitive_keywords": ["敏感词A", "敏感词B", "controversial_term", "禁止讨论事件"],
            "model_settings": {}  # 预留扩展
        }
        with open(test_config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=2)

    # 实例化检测器
    detector = PoliticalDetector()

    # 测试单个文本
    test_texts = [
        "这是一段普通的描述文字。",
        "有敏感词A和敏感词B的内容",
        "CONTROVERSIAL_TERM 出现了",
        "纯英文测试"
    ]
    for t in test_texts:
        res = detector.detect(t)
        print(f"\nInput: {t[:30]}")
        print(f"Result: {json.dumps(res, ensure_ascii=False)}")

    # 测试批量
    batch_res = detector.batch_detect(test_texts)
    print("\nBatch results:", json.dumps(batch_res, ensure_ascii=False, indent=2))

    # 测试热更新
    print("\n--- Reloading config ---")
    detector.reload_config()
    print("Status:", detector.get_status())