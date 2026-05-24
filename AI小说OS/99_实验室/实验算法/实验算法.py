"""
实验算法模块骨架
定义实验算法的抽象基类，提供配置化、日志、可插拔、自测基础。
所有实验算法必须继承 ExperimentAlgorithm 并实现其抽象方法。
"""

import abc
import json
import logging
import os
from typing import Any, Dict, Optional


class ExperimentAlgorithm(abc.ABC):
    """实验算法抽象基类。
    
    提供：
        - 配置加载（JSON）与更新
        - 日志管理
        - 抽象 run() 与 self_test() 接口
    
    所有实验室中的实验性算法均需继承此类，实现具体逻辑。
    """

    def __init__(self, config_path: Optional[str] = None, **kwargs):
        """初始化算法实例。
        
        Args:
            config_path: 可选，JSON 配置文件路径。若文件存在则自动加载。
            kwargs: 额外配置项，优先级高于文件配置中的同名键。
        """
        self.config: Dict[str, Any] = {}
        self.logger: logging.Logger = self._setup_logging()

        if config_path and os.path.exists(config_path):
            self.load_config(config_path)
        # 动态参数覆盖文件配置
        self.config.update(kwargs)

    def load_config(self, config_path: str) -> None:
        """从 JSON 文件加载配置并合并到 self.config 中。
        
        Args:
            config_path: 配置文件路径。
        
        Raises:
            若文件读取失败或 JSON 解析错误，将记录错误日志并抛出异常。
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.config.update(data)
            self.logger.info("配置已从 %s 加载。", config_path)
        except Exception as e:
            self.logger.error("加载配置失败: %s", e)
            raise

    def _setup_logging(self) -> logging.Logger:
        """创建并配置日志记录器。
        
        Returns:
            logging.Logger: 使用类名命名的 Logger，默认级别为 DEBUG，
            若已存在 handler 则不重复添加。
        """
        logger = logging.getLogger(self.__class__.__name__)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            # 默认级别可通过配置覆盖，例如 self.config.get('log_level', 'DEBUG')
            logger.setLevel(logging.DEBUG)
        return logger

    @abc.abstractmethod
    def run(self, **kwargs) -> Any:
        """执行算法主逻辑（抽象方法）。
        
        Args:
            kwargs: 运行时参数，可用于临时覆盖配置。
        
        Returns:
            算法执行结果，类型由子类定义。
        """
        pass

    @abc.abstractmethod
    def self_test(self) -> bool:
        """算法自测方法（抽象方法）。
        
        Returns:
            bool: True 表示测试通过，False 表示失败。
        """
        pass

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """热更新配置（运行时修改）。
        
        Args:
            new_config: 需合并的新配置字典。
        """
        self.config.update(new_config)
        self.logger.info("配置已动态更新。")

    def set_log_level(self, level: str) -> None:
        """动态调整日志级别。
        
        Args:
            level: 日志级别字符串，如 'DEBUG', 'INFO', 'WARNING', 'ERROR'。
        """
        numeric_level = getattr(logging, level.upper(), None)
        if isinstance(numeric_level, int):
            self.logger.setLevel(numeric_level)
            self.logger.info("日志级别已设置为 %s", level)
        else:
            self.logger.warning("无效的日志级别: %s，已忽略。", level)


# 自测用具体算法（仅用于验证骨架功能）
class DummyTestAlgorithm(ExperimentAlgorithm):
    """一个简单的测试算法，用于验证基类功能。"""

    def run(self, **kwargs) -> str:
        """执行测试：输出当前配置并返回 'test done'。"""
        self.logger.info("DummyTestAlgorithm.run() 被调用，当前配置：%s", self.config)
        return "test done"

    def self_test(self) -> bool:
        """自测：检查配置中是否包含 'test_key' 且其值为 'test_value'。"""
        expected = 'test_value'
        actual = self.config.get('test_key')
        if actual == expected:
            self.logger.info("自测通过：test_key == %s", expected)
            return True
        else:
            self.logger.warning("自测失败：期望 test_key='%s'，实际为 '%s'", expected, actual)
            return False


if __name__ == "__main__":
    """模块自测入口。
    
    创建一个 DummyTestAlgorithm 实例，加载示例配置，运行自测和 run 方法。
    """
    # 准备一个临时配置文件，用于演示配置加载
    test_config = {"test_key": "test_value", "extra": 42}
    config_file = "_dummy_test_config.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(test_config, f)

    print("=== 实验算法骨架自测开始 ===")
    # 实例化并加载配置
    algo = DummyTestAlgorithm(config_path=config_file)
    # 运行自测
    test_result = algo.self_test()
    print(f"self_test 结果: {test_result}")
    # 执行算法
    result = algo.run(param1="hello")
    print(f"run 结果: {result}")
    # 演示热更新
    algo.update_config({"new_key": "new_value"})
    print(f"更新后配置: {algo.config}")
    # 清理临时文件
    os.remove(config_file)
    print("=== 自测结束 ===")