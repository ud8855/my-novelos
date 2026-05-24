#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
临时实验代码骨架
位置：99_实验室/临时代码/临时代码.py
用途：用于快速原型、一次性测试、实验性逻辑
注意：此代码为临时性质，不应包含核心业务逻辑，但必须遵守日志、配置、可插拔原则
"""

import logging
import os
import sys
from typing import Optional

# ---------- 日志配置 ----------
def setup_logging(log_file: Optional[str] = None) -> logging.Logger:
    """
    配置日志系统
    Args:
        log_file: 日志文件路径，若为None则仅输出到控制台
    Returns:
        logger 实例
    """
    logger = logging.getLogger("TemporaryCode")
    logger.setLevel(logging.DEBUG)

    # 清除已有handlers以避免重复
    if logger.handlers:
        logger.handlers.clear()

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger

# ---------- 配置管理 ----------
class TempConfig:
    """
    临时配置类，支持从字典或文件加载配置
    遵循可插拔原则，可替换实现
    """
    def __init__(self, config: Optional[dict] = None):
        self._config = config or {}

    @classmethod
    def from_json(cls, json_path: str) -> 'TempConfig':
        """
        从JSON文件加载配置
        Args:
            json_path: JSON配置文件路径
        Returns:
            TempConfig实例
        """
        import json
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"配置文件不存在: {json_path}")
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(data)

    def get(self, key: str, default=None):
        """获取配置项"""
        return self._config.get(key, default)

    def set(self, key: str, value):
        """设置配置项"""
        self._config[key] = value

    def __repr__(self):
        return f"TempConfig({self._config})"

# ---------- 可插拔实验主体 ----------
class TemporaryExperiment:
    """
    临时实验类
    每个临时实验应继承此类，并实现 run() 方法
    """
    def __init__(self, config: TempConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def setup(self):
        """实验前准备（可重写）"""
        self.logger.info("实验初始化完成")

    def run(self):
        """
        实验主逻辑（必须重写）
        Raises:
            NotImplementedError
        """
        raise NotImplementedError("子类必须实现 run 方法")

    def teardown(self):
        """实验后清理（可重写）"""
        self.logger.info("实验资源清理完成")

    def execute(self):
        """模板方法：顺序执行 setup -> run -> teardown"""
        try:
            self.setup()
            self.run()
        except Exception as e:
            self.logger.exception("实验执行异常")
            raise
        finally:
            self.teardown()

# ---------- 自测 ----------
class DummyExperiment(TemporaryExperiment):
    """用于自测的简单实验"""
    def run(self):
        self.logger.info("开始执行DummyExperiment")
        self.logger.debug(f"当前配置: {self.config}")
        self.logger.info("DummyExperiment执行完成")

def main():
    """主函数：用于自测"""
    # 初始化日志
    logger = setup_logging(log_file="./temp_experiment.log")

    # 加载配置（示例使用硬编码，实际可从文件加载）
    config = TempConfig({
        "experiment_name": "hello_world",
        "max_retries": 3,
        "output_dir": "./output"
    })
    # 也可从文件加载：config = TempConfig.from_json("config.json")

    # 创建实验并执行
    experiment = DummyExperiment(config, logger)
    logger.info("开始临时实验自测")
    experiment.execute()
    logger.info("临时实验自测结束")

if __name__ == "__main__":
    # 确保项目根目录在路径中（如需调用其他模块）
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    main()