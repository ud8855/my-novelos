"""
全局配置模块
位置：01_配置中心/全局配置
依赖：标准库（json, logging, pathlib, threading）
被调用：系统各模块需要读取配置时调用
功能：提供统一的配置读取、写入、热更新能力，支持插拔式配置后端（默认JSON）
"""

import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, Optional

# 模块日志
logger = logging.getLogger(__name__)

# 默认配置文件路径（相对于项目根目录）
DEFAULT_CONFIG_PATH = Path(__file__).parent / "config.json"


class ConfigManager:
    """
    全局配置管理器（单例模式）
    支持：
      - 从JSON文件加载配置
      - 获取/设置配置项（键值点分隔，如"section.key"）
      - 保存配置到文件
      - 热重载（线程安全）
    可插拔：子类化可重写 _load, _save 方法以支持其他后端
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, config_path: Optional[Path] = None):
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                cls._instance = instance
        return cls._instance

    def __init__(self, config_path: Optional[Path] = None):
        # 防止重复初始化
        if hasattr(self, '_initialized') and self._initialized:
            return
        self._initialized = True
        self._config: Dict[str, Any] = {}
        self._config_path = config_path or DEFAULT_CONFIG_PATH
        self._runtime_lock = threading.RLock()  # 配置读写的锁
        self.load()
        logger.info(f"全局配置初始化完成，配置文件：{self._config_path}")

    def load(self) -> None:
        """从配置文件加载（热更新入口）"""
        try:
            if not self._config_path.exists():
                logger.warning(f"配置文件不存在：{self._config_path}，使用空配置")
                self._config = {}
                return
            with open(self._config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            logger.info(f"成功加载配置：{len(self._config)} 个顶级键")
        except Exception as e:
            logger.exception(f"加载配置文件失败：{e}")
            # 保持原有配置（如果有）或使用空字典
            if not self._config:
                self._config = {}

    def reload(self) -> None:
        """热重载配置，线程安全"""
        with self._runtime_lock:
            logger.info("正在重载配置...")
            self.load()

    def save(self) -> None:
        """将当前配置保存回文件"""
        try:
            with self._runtime_lock:
                with open(self._config_path, 'w', encoding='utf-8') as f:
                    json.dump(self._config, f, indent=4, ensure_ascii=False)
            logger.info(f"配置已保存至 {self._config_path}")
        except Exception as e:
            logger.exception(f"保存配置失败：{e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项，支持点号分隔的键，例如 'llm.model'
        """
        keys = key.split('.')
        value = self._config
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            logger.debug(f"配置键 {key} 不存在，返回默认值 {default}")
            return default

    def set(self, key: str, value: Any) -> None:
        """
        设置配置项，支持点号分隔，会自动创建中间字典
        """
        keys = key.split('.')
        with self._runtime_lock:
            target = self._config
            for k in keys[:-1]:
                if k not in target or not isinstance(target[k], dict):
                    target[k] = {}
                target = target