"""ProhibitedBehaviorEnforcer: Architecture Governance - Forbidden Actions Enforcement

This module detects and prohibits predefined forbidden behaviors at runtime.
It supports pluggable configuration, logging, and hot-reloading.
"""

import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Optional, Any

# 默认日志配置
DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DEFAULT_LOG_LEVEL = logging.WARNING

class ProhibitedBehaviorEnforcer:
    """
    禁止行为执行器
    职责：加载禁止行为列表，检查给定行为是否被禁止，并可记录日志或抛出异常。
    可插拔：通过替换配置文件或实现不同的加载器。
    """

    def __init__(self, config_path: Optional[str] = None, logger: Optional[logging.Logger] = None):
        """
        初始化执行器
        :param config_path: 配置文件路径（JSON格式），若为None则使用默认路径
        :param logger: 外部传入的日志记录器，若为None则创建独立logger
        """
        self._forbidden_actions: List[str] = []
        self._context_keys: List[str] = []  # 可选：需要校验的上下文键
        self.config_path = config_path or self._default_config_path()
        self.logger = logger or self._setup_logger()
        self.load_config()

    def _default_config_path(self) -> str:
        """获取默认配置文件路径（相对于当前模块）"""
        base_dir = Path(__file__).parent
        return str(base_dir / "prohibited_behaviors.json")

    def _setup_logger(self) -> logging.Logger:
        """配置并返回独立日志记录器"""
        logger = logging.getLogger("ProhibitedBehaviorEnforcer")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(DEFAULT_LOG_FORMAT)
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(DEFAULT_LOG_LEVEL)
        return logger

    def load_config(self, config_path: Optional[str] = None) -> None:
        """
        加载禁止行为配置
        配置文件格式:
        {
            "forbidden_actions": ["action_a", "action_b", ...],
            "context_keys": ["key1", "key2"]  // 可选，用于检查上下文
        }
        :param config_path: 若提供则更新self.config_path并重新加载
        """
        if config_path:
            self.config_path = config_path
        path = Path(self.config_path)
        if not path.exists():
            self.logger.warning(f"Config file not found: {self.config_path}. Using empty forbidden list.")
            self._forbidden_actions = []
            self._context_keys = []
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._forbidden_actions = [str(a).strip().lower() for a in data.get("forbidden_actions", [])]
            self._context_keys = data.get("context_keys", [])
            self.logger.info(f"Loaded {len(self._forbidden_actions)} forbidden actions from {self.config_path}")
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}", exc_info=True)
            # 保持旧配置不变，避免系统崩溃
            # 可以在这里实现fallback策略
            raise

    def reload_config(self) -> None:
        """热加载配置（供外部定时调用）"""
        self.load_config(self.config_path)

    def check_action(self, action: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        检查指定行为是否被禁止
        :param action: 行为标识（字符串）
        :param context: 可选的上下文信息（dict），用于更精细的检查
        :return: True 表示行为被禁止，False 表示允许
        """
        if not action:
            return False
        action_key = action.strip().lower()
        is_forbidden = action_key in self._forbidden_actions
        if is_forbidden:
            self.logger.warning(f"Prohibited action detected: '{action}' (context: {context})")
        return is_forbidden

    def enforce(self, action: str, context: Optional[Dict[str, Any]] = None) -> None:
        """
        强制执行检查，若行为被禁止则抛出 RuntimeError 异常。
        调用者应捕获此异常并决定是否终止操作。
        :param action: 行为标识
        :param context: 上下文
        :raises RuntimeError: 如果行为被禁止
        """
        if self.check_action(action, context):
            raise RuntimeError(f"Prohibited action '{action}' is not allowed.")

    def get_forbidden_actions(self) -> List[str]:
        """返回当前禁止的行为列表（小写）"""
        return self._forbidden_actions.copy()

    def add_forbidden_action(self, action: str) -> None:
        """
        动态添加禁止行为（运行时修改，不会持久化到配置文件）
        :param action: 行为标识
        """
        action_key = action.strip().lower()
        if action_key and action_key not in self._forbidden_actions:
            self._forbidden_actions.append(action_key)
            self.logger.info(f"Temporarily added forbidden action: '{action_key}'")

    def remove_forbidden_action(self, action: str) -> None:
        """
        动态移除禁止行为
        :param action: 行为标识
        """
        action_key = action.strip().lower()
        if action_key in self._forbidden_actions:
            self._forbidden_actions.remove(action_key)
            self.logger.info(f"Temporarily removed forbidden action: '{action_key}'")


# ----------------------------------------------------------------------
# 自测部分
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import tempfile

    # 创建临时配置文件用于测试
    test_config = {
        "forbidden_actions": [
            "direct_database_access",
            "cross_layer_call",
            "redefine_constants"
        ],
        "context_keys": ["caller", "layer"]
    }

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        json.dump(test_config, f)
        tmp_config_path = f.name

    print(f"Test config file: {tmp_config_path}")

    # 创建执行器并加载临时配置
    enforcer = ProhibitedBehaviorEnforcer(config_path=tmp_config_path)
    enforcer.logger.setLevel(logging.DEBUG)  # 测试时打印详细日志

    # 测试1：正常行为
    assert not enforcer.check_action("read_novel"), "read_novel should be allowed"
    print("Test 1 passed: normal action allowed.")

    # 测试2：禁止行为
    assert enforcer.check_action("direct_database_access"), "direct_database_access should be forbidden"
    print("Test 2 passed: forbidden action detected.")

    # 测试3：enforce 应抛出异常
    try:
        enforcer.enforce("cross_layer_call", {"caller": "UI", "layer": "data"})
    except RuntimeError as e:
        print(f"Test 3 passed: RuntimeError raised - {e}")
    else:
        assert False, "Expected RuntimeError"

    # 测试4：热加载（修改文件内容）
    with open(tmp_config_path, 'w') as f:
        new_config = {"forbidden_actions": ["new_forbidden"]}
        json.dump(new_config, f)
    enforcer.reload_config()
    assert enforcer.check_action("new_forbidden"), "Should detect newly added forbidden action"
    assert not enforcer.check_action("direct_database_access"), "Previously forbidden action should now be allowed"
    print("Test 4 passed: hot reload works.")

    # 清理临时文件
    os.unlink(tmp_config_path)
    print("All tests passed.")