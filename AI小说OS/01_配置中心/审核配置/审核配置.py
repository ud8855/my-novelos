"""
审核配置模块
负责管理内容审核相关的配置参数，支持热加载、持久化和日志记录。
属于配置中心层，依赖配置加载器，被上层审核服务调用。
"""

import logging
import json
import os
from typing import Dict, Any, Optional

class ReviewConfig:
    """
    审核配置管理类，单例模式，可插拔。
    提供审核开关、敏感词库路径、审核级别等配置项的加载、保存与热更新。
    """
    _instance = None
    _config: Dict[str, Any] = {}
    _config_file: Optional[str] = None

    DEFAULT_CONFIG = {
        "enable_review": True,
        "sensitive_words_file": "data/sensitive_words.txt",
        "review_level": "normal",  # low, normal, high
        "max_text_length": 5000,
        "auto_approve_threshold": 0.8,
        "timeout_seconds": 30,
        "log_review_decisions": True,
    }

    def __new__(cls, config_file: str = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_file: str = None):
        if self._initialized:
            return
        self._initialized = True
        # 初始化日志
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("审核配置模块初始化")
        if config_file:
            self._config_file = config_file
        else:
            self._config_file = os.environ.get("NOVELOS_REVIEW_CONFIG", "config/review_config.json")
        self.load_config()

    def load_config(self) -> None:
        """从配置文件加载审核配置，若文件不存在则使用默认配置并保存。"""
        self.logger.debug(f"开始加载审核配置，文件路径: {self._config_file}")
        if self._config_file and os.path.exists(self._config_file):
            try:
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                # 合并默认配置，确保所有键存在
                self._config = {**self.DEFAULT_CONFIG, **loaded}
                self.logger.info("审核配置加载成功")
            except Exception as e:
                self.logger.error(f"加载审核配置失败: {e}，使用默认配置")
                self._config = self.DEFAULT_CONFIG.copy()
                self.save_config()  # 保存默认配置以修复
        else:
            self.logger.warning("审核配置文件不存在，使用默认配置并创建新文件")
            self._config = self.DEFAULT_CONFIG.copy()
            self.save_config()

    def save_config(self) -> None:
        """将当前审核配置保存到配置文件。"""
        if not self._config_file:
            self.logger.warning("未设置配置文件路径，无法保存配置")
            return
        try:
            os.makedirs(os.path.dirname(self._config_file), exist_ok=True)
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
            self.logger.info(f"审核配置已保存至 {self._config_file}")
        except Exception as e:
            self.logger.error(f"保存审核配置失败: {e}")

    def reload_config(self) -> None:
        """热更新配置：重新从文件加载。"""
        self.logger.info("触发审核配置热更新")
        self.load_config()

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置配置项并立即持久化，实现热更新。"""
        self._config[key] = value
        self.save_config()
        self.logger.info(f"配置项 [{key}] 已更新为: {value}")

    def get_all(self) -> Dict[str, Any]:
        """获取全部配置的副本"""
        return self._config.copy()

    def is_review_enabled(self) -> bool:
        """返回是否启用审核"""
        return self._config.get("enable_review", True)

    def get_sensitive_words_path(self) -> str:
        """返回敏感词文件路径"""
        return self._config.get("sensitive_words_file", "data/sensitive_words.txt")

# 自测代码
if __name__ == "__main__":
    # 配置日志级别以便调试
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    config = ReviewConfig("test_review_config.json")
    print("当前审核配置:", config.get_all())
    print("审核是否启用:", config.is_review_enabled())
    # 修改配置并观察是否保存
    config.set("enable_review", False)
    new_config = ReviewConfig()  # 单例，不会重新初始化，但加载的是刚刚修改后的配置
    print("修改后配置:", new_config.get_all())
    # 清理测试文件
    import os
    if os.path.exists("test_review_config.json"):
        os.remove("test_review_config.json")
        print("测试文件已清理")