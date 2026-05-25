import logging
import json
import os
from typing import List, Set, Optional, Union


class SensitiveWordDetector:
    """
    敏感词检测器（可插拔、配置化、支持热更新）
    - 负责从配置文件加载敏感词库
    - 提供文本敏感词检测
    - 日志记录所有关键操作及异常恢复
    - 供上层审核模块或内容安全管道调用
    """
    CONFIG_KEY = "sensitive_word_list_path"          # 配置中词库文件路径的键
    DEFAULT_CONFIG_PATH = "config/sensitive_words.json"

    def __init__(self, config: Optional[dict] = None):
        """
        :param config: 配置字典，至少包含 sensitive_word_list_path 字段
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self._config = config or {}
        self._word_set: Set[str] = set()               # 敏感词集合（去重，用于快速查找）
        self._words_loaded = False
        self._load_config()                            # 初始化加载

    # --------------------- 配置加载与热更新 ---------------------
    def _load_config(self) -> None:
        """根据当前配置加载敏感词库（内部方法，含异常恢复）"""
        path = self._config.get(self.CONFIG_KEY, self.DEFAULT_CONFIG_PATH)
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                words = data.get("words", [])
                self._word_set = set(w.strip() for w in words if w and isinstance(w, str))
                self._words_loaded = True
                self.logger.info("成功加载敏感词库: %s, 共 %d 个词", path, len(self._word_set))
            else:
                self.logger.warning("敏感词配置文件不存在: %s, 使用空集合", path)
                self._word_set = set()
                self._words_loaded = False
        except (json.JSONDecodeError, IOError) as e:
            self.logger.error("加载敏感词配置失败 (%s): %s, 将使用空集合", path, e)
            self._word_set = set()
            self._words_loaded = False

    def reload(self) -> bool:
        """
        热更新：重新从配置文件加载敏感词库
        :return: 是否成功加载
        """
        self.logger.info("开始热更新敏感词库...")
        self._load_config()
        return self._words_loaded

    # --------------------- 核心检测接口 ---------------------
    def detect(self, text: str, return_words: bool = False) -> Union[bool, List[str]]:
        """
        检测文本是否包含敏感词
        :param text: 待检测文本
        :param return_words: 是否返回匹配到的敏感词列表（默认只返回布尔值）
        :return: 若包含敏感词，返回 True 或匹配词列表；否则返回 False 或空列表
        """
        if not text or not isinstance(text, str):
            self.logger.debug("输入文本为空或非字符串")
            return False if not return_words else []

        found_words = [w for w in self._word_set if w in text]
        has_sensitive = len(found_words) > 0

        if has_sensitive:
            self.logger.info("检测到敏感词: %s", found_words)

        if return_words:
            return found_words
        return has_sensitive

    def get_words(self) -> List[str]:
        """获取当前加载的所有敏感词（只读）"""
        return sorted(self._word_set)

    def add_word(self, word: str) -> None:
        """动态添加单个敏感词（运行时更新）"""
        word = word.strip()
        if not word:
            return
        before = len(self._word_set)
        self._word_set.add(word)
        if len(self._word_set) > before:
            self.logger.info("动态添加敏感词: %s", word)

    def remove_word(self, word: str) -> None:
        """动态移除单个敏感词"""
        word = word.strip()
        if word in self._word_set:
            self._word_set.remove(word)
            self.logger.info("动态移除敏感词: %s", word)

    # --------------------- 自检与健康状态 ---------------------
    def is_healthy(self) -> bool:
        """检查检测器是否处于可用状态（词库已加载，非空等）"""
        return self._words_loaded

    def status(self) -> dict:
        """返回检测器状态摘要，便于监控"""
        return {
            "words_loaded": self._words_loaded,
            "word_count": len(self._word_set),
            "config_path": self._config.get(self.CONFIG_KEY, self.DEFAULT_CONFIG_PATH)
        }


# ------------------------ 自测（仅模块内） ------------------------
if __name__ == "__main__":
    # 基本日志配置
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # 准备一个临时配置文件
    test_config_file = "test_sensitive_words.json"
    test_words = {"words": ["测试", "敏感", "违规", "badword"]}
    with open(test_config_file, 'w', encoding='utf-8') as f:
        json.dump(test_words, f, ensure_ascii=False)

    # 使用临时配置
    config = {"sensitive_word_list_path": test_config_file}
    detector = SensitiveWordDetector(config)
    print("状态:", detector.status())

    # 测试检测
    text_ok = "这是一段正常文本"
    text_bad = "这是一段包含违规内容的文本"
    print(f"正常文本检测: {detector.detect(text_ok)}")
    print(f"违规文本检测: {detector.detect(text_bad)}")
    print(f"违规文本返回词: {detector.detect(text_bad, return_words=True)}")

    # 测试热更新
    new_words = {"words": ["新词", "badword"]}
    with open(test_config_file, 'w', encoding='utf-8') as f:
        json.dump(new_words, f, ensure_ascii=False)
    success = detector.reload()
    print(f"热更新结果: {success}, 新词数量: {len(detector.get_words())}")
    print(f"热更新后检测'badword': {detector.detect('badword')}")
    print(f"热更新后检测'测试': {detector.detect('测试')}")

    # 动态增删
    detector.add_word("动态")
    print(f"添加后检测'动态': {detector.detect('动态')}")
    detector.remove_word("动态")
    print(f"移除后检测'动态': {detector.detect('动态')}")

    # 清理临时文件
    try:
        os.remove(test_config_file)
    except:
        pass