# 模块：20_模型协同/推理链协调/推理链协调.py
# 层级：模型协同层
# 依赖：配置模块、日志模块、模型调用接口（抽象）
# 被调用：任务协调器、小说生成流程等
# 功能：协调多个模型调用，形成推理链（Chain-of-Thought），支持步骤定义、上下文传递、异常恢复、日志记录。

import logging
import configparser
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

# ------------------------------ 配置加载 ------------------------------
def load_config_from_file(config_path: str) -> dict:
    """从配置文件加载推理链协调配置，返回字典。"""
    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')
    chain_config = {}
    if config.has_section('ReasoningChain'):
        chain_config = dict(config.items('ReasoningChain'))
    return chain_config

# ------------------------------ 日志设置 ------------------------------
def setup_logger(name: str = "ReasoningChainCoordinator", level: int = logging.INFO) -> logging.Logger:
    """设置日志记录器，支持文件和控制台输出。"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        ch = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        # 可扩展文件handler：fh = logging.FileHandler('logs/reasoning_chain.log')
    return logger

# ------------------------------ 基类/接口 ------------------------------
class BaseReasoningChainCoordinator(ABC):
    """推理链协调器抽象基类，定义标准接口，实现可插拔。"""

    @abstractmethod
    def __init__(self, config: dict):
        """初始化协调器，传入配置字典。"""
        pass

    @abstractmethod
    def create_chain(self, steps