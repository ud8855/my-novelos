"""
逻辑检测模块 - 负责检测小说内容中的逻辑矛盾与不一致

功能：
- 提供可插拔的逻辑检测器抽象接口
- 管理检测器的加载与执行
- 支持配置化开关，日志记录
- 自测示例
"""

import logging
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pathlib import Path

# 配置日志
logger = logging.getLogger(__name__)

# 默认配置文件路径
DEFAULT_CONFIG_PATH = Path(__file__).parent / "logic_check_config.json"

class LogicCheckResult:
    """逻辑检测结果"""
    def __init__(self, checker_name: str, passed: bool, message: str = "", details: Dict[str, Any] = None):
        self.checker_name = checker_name
        self.passed = passed
        self.message = message
        self.details = details or {}
    
    def __repr__(self):
        return f"LogicCheckResult({self.checker_name}, passed={self.passed}, message='{self.message}')"

class BaseLogicChecker(ABC):
    """逻辑检测器抽象基类，所有检测器需继承此类"""
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        logger.info(f"初始化逻辑检测器: {self.name}")
    
    @abstractmethod
    def check(self, chapter_content: str, context: Dict[str, Any] = None) -> LogicCheckResult:
        """执行逻辑检测
        
        Args:
            chapter_content: 待检测的章节内容
            context: 上下文信息（如前文总结、角色状态等）
        
        Returns:
            LogicCheckResult: 检测结果
        """
        pass
    
    def validate_config(self) -> bool:
        """验证检测器配置是否合法"""
        # 默认合法，子类可重写
        return True

class LogicDetectionManager:
    """逻辑检测管理器，负责加载、注册和执行检测器"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config = self._load_config(config_path or DEFAULT_CONFIG_PATH)
        self.checkers: List[BaseLogicChecker] = []
        self._register_default_checkers()
        logger.info("逻辑检测管理器初始化完成")
    
    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """加载配置文件"""
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                logger.info(f"加载逻辑检测配置: {config_path}")
                return config
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}, 使用默认配置")
        else:
            logger.warning(f"配置文件不存在: {config_path}, 使用默认配置")
        
        # 默认配置
        return {
            "enabled_checkers": [],  # 启用的检测器名称列表
            "global_params": {}
        }
    
    def _register_default_checkers(self):
        """注册默认检测器（目前为空，可后续扩展）"""
        enabled_names = self.config.get("enabled_checkers", [])
        for name in enabled_names:
            # 这里通过插件机制动态加载检测器
            # 骨架中仅记录日志
            logger.info(f"待注册检测器: {name} (未实现动态加载)")
        # 实际预留扩展点
        pass
    
    def register_checker(self, checker: BaseLogicChecker):
        """手动注册检测器"""
        if any(c.name == checker.name for c in self.checkers):
            logger.warning(f"检测器 '{checker.name}' 已存在，跳过注册")
            return
        self.checkers.append(checker)
        logger.info(f"注册检测器: {checker.name}")
    
    def unregister_checker(self, checker_name: str):
        """注销检测器"""
        self.checkers = [c for c in self.checkers if c.name != checker_name]
        logger.info(f"注销检测器: {checker_name}")
    
    def check(self, chapter_content: str, context: Dict[str, Any] = None) -> List