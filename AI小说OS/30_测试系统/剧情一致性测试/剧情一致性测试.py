#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
剧情一致性测试模块
属于测试系统层 (30_测试系统/剧情一致性测试)
职责：对剧本/小说的剧情逻辑一致性进行自动化测试
依赖：无外部业务模块依赖；仅依赖基础库和配置
被调用者：测试框架、持续集成、开发者自测
设计：可插拔、配置化、完整日志、单一职责
"""

import abc
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# 默认配置路径（相对于本项目根目录）
DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "plot_consistency_test.json"

# 日志格式
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class TestModule(abc.ABC):
    """所有测试模块的抽象基类，实现可插拔架构"""
    
    def __init__(self, name: str, config: dict, logger: logging.Logger):
        self.name = name
        self.config = config
        self.logger = logger
    
    @abc.abstractmethod
    def run(self, *args, **kwargs) -> Dict[str, Any]:
        """运行测试，返回结果字典，必须包含'passed' (bool) 和 'details' (str)字段"""
        ...


class PlotConsistencyTest(TestModule):
    """
    剧情一致性测试
    检查小说/剧本中剧情要素是否前后一致，包括但不限于：
    - 角色性格一致性
    - 情节逻辑闭合性
    - 时间线冲突
    - 物品/能力设定冲突
    """
    
    TEST_NAME = "PlotConsistencyTest"
    
    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        # 加载配置
        config = self._load_config(config_path)
        # 初始化日志
        logger = self._setup_logger(config.get("logging", {}))
        super().__init__(self.TEST_NAME, config, logger)
        # 插件式检查器列表（可动态扩展）
        self.checkers: List[Any] = []
        self._init_checkers()
        self.logger.info(f"{self.TEST_NAME} 初始化完成")
    
    def _load_config(self, config_path: Optional[Union[str, Path]] = None) -> dict:
        """加载配置文件（JSON格式），失败时返回默认配置"""
        default_config = {
            "logging": {
                "level": "INFO",
                "file": None,          # None表示只用控制台输出
                "format": LOG_FORMAT,
                "date_format": LOG_DATE_FORMAT
            },
            "test": {
                "max_episode_length": 5000,
                "enable_timeline_check": True,
                "enable_character_consistency": True,
                "enable_logic_consistency": True,
                "ignore_minor_conflicts": True
            }
        }
        if config_path is None:
            config_path = DEFAULT_CONFIG_PATH
        if not os.path.exists(config_path):
            # 配置文件不存在时使用默认配置并记录警告（稍后记录，此时日志尚未初始化）
            print(f"警告: 配置文件不存在 {config_path}，使用默认配置。")
            return default_config
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            # 合并默认配置，确保所有键存在
            merged = default_config.copy()
            merged.update(loaded)
            return merged
        except Exception as e:
            print(f"错误: 加载配置文件失败 {config_path}: {e}，使用默认配置。")
            return default_config
    
    def _setup_logger(self, logging_conf: dict) -> logging.Logger:
        """根据配置初始化logger"""
        logger = logging.getLogger(self.TEST_NAME)
        logger.setLevel(logging_conf.get("level", "INFO"))
        formatter = logging.Formatter(
            logging_conf.get("format", LOG_FORMAT),
            datefmt=logging_conf.get("date_format", LOG_DATE_FORMAT)
        )
        # 清除已有的处理器（防止重复添加）
        if logger.hasHandlers():
            logger.handlers.clear()
        # 控制台输出
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        # 如果指定了文件输出
        log_file = logging_conf.get("file")
        if log_file:
            try:
                file_handler = logging.FileHandler(log_file, encoding="utf-8")
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
            except Exception as e:
                logger.error(f"无法创建日志文件 {log_file}: {e}")
        return logger
    
    def _init_checkers(self):
        """初始化可插拔的检查器（空实现，留给扩展）"""
        # 可以在此处加载外部插件或动态导入
        # 例如：扫描plugins目录下的检查器并注册
        self.checkers = []
        self.logger.debug("初始化检查器列表为空，待扩展。")
    
    def add_checker(self, checker: Any):
        """动态添加一致性检查器（热插拔）"""
        if not hasattr(checker, "check"):
            self.logger.warning(f"添加的检查器 {checker} 没有 'check' 方法，将被忽略")
            return
        self.checkers.append(checker)
        self.logger.info(f"注册检查器: {getattr(checker, 'name', 'unnamed')}")
    
    def remove_checker(self, checker_name: str):
        """根据名称移除检查器"""
        before_count = len(self.checkers)
        self.checkers = [c for c in self.checkers if getattr(c, 'name', '') != checker_name]
        if len(self.checkers) < before_count:
            self.logger.info(f"已移除检查器: {checker_name}")
        else:
            self.logger.warning(f"未找到要移除的检查器: {checker_name}")
    
    def run(self, plot_data: Any, **kwargs) -> Dict[str, Any]:
        """
        运行剧情一致性测试
        :param plot_data: 剧情数据，格式由检查器定义
        :return: 测试结果字典
        """
        self.logger.info("开始剧情一致性测试...")
        result = {
            "test_name": self.name,
            "passed": True,
            "details": [],
            "suggestions": []
        }
        
        if not self.checkers:
            self.logger.warning("没有注册任何检查器，测试将返回通过但无实际检查。")
        
        for checker in self.checkers:
            checker_name = getattr(checker, 'name', type(checker).__name__)
            try:
                self.logger.debug(f"执行检查器: {checker_name}")
                check_result = checker.check(plot_data, config=self.config)
                if not check_result.get("passed", True):
                    result["passed"] = False
                    issue = check_result.get("issue", f"{checker_name} 检查未通过")
                    result["details"].append(issue)
                    self.logger.warning(f"一致性冲突: {issue}")
                    if "suggestion" in check_result:
                        result["suggestions"].append(check_result["suggestion"])
                else:
                    self.logger.debug(f"{checker_name} 检查通过")
            except Exception as e:
                self.logger.error(f"检查器 {checker_name} 执行异常: {e}", exc_info=True)
                result["passed"] = False
                result["details"].append(f"检查器 {checker_name} 异常: {str(e)}")
        
        if result["passed"]:
            self.logger.info("剧情一致性测试全部通过。")
        else:
            self.logger.warning(f"剧情一致性测试未通过，发现 {len(result['details'])} 个问题。")
        
        return result


# ====================================
# 以下为示例检查器（可随时替换或扩展）
# ====================================

class ExampleCheck:
    """示例检查器：仅检查剧情数据非空"""
    name = "ExampleNonEmptyCheck"
    def check(self, plot_data, config=None):
        if plot_data:
            return {"passed": True}
        else:
            return {"passed": False, "issue": "剧情数据为空"}
    
class AnotherExample:
    name = "AnotherExampleCheck"
    def check(self, plot_data, config=None):
        # 模拟一个失败的情况
        if isinstance(plot_data, str) and "矛盾" in plot_data:
            return {"passed": False, "issue": "检测到矛盾关键词", "suggestion": "请检查相关情节"}
        return {"passed": True}


def self_test():
    """模块自测函数"""
    print("执行剧情一致性测试模块自测...")
    # 构造测试实例，使用默认配置（不依赖外部文件）
    test = PlotConsistencyTest(config_path=None)
    # 注册示例检查器
    test.add_checker(ExampleCheck())
    test.add_checker(AnotherExample())
    
    # 测试用例1：正常剧情
    result1 = test.run("这是一个正常的故事。")
    print(f"测试1 结果: {'通过' if result1['passed'] else '失败'}, 详情: {result1['details']}")
    
    # 测试用例2：含矛盾关键词的剧情
    result2 = test.run("故事中存在严重的矛盾。")
    print(f"测试2 结果: {'通过' if result2['passed'] else '失败'}, 详情: {result2['details']}")
    
    # 测试用例3：空数据
    result3 = test.run("")
    print(f"测试3 结果: {'通过' if result3['passed'] else '失败'}, 详情: {result3['details']}")
    
    # 测试热插拔：移除检查器
    test.remove_checker("AnotherExampleCheck")
    result4 = test.run("矛盾还存在吗？")
    print(f"移除检查器后测试: {'通过' if result4['passed'] else '失败'}, 详情: {result4['details']}")
    
    # 测试异常恢复：添加一个会抛异常的检查器
    class FaultyCheck:
        name = "FaultyCheck"
        def check(self, data, config=None):
            raise RuntimeError("模拟检查器崩溃")
    test.add_checker(FaultyCheck())
    result5 = test.run("任意数据")
    print(f"异常检查器测试: {'通过' if result5['passed'] else '失败'}, 详情: {result5['details']}")
    
    print("自测完成。")


if __name__ == "__main__":
    self_test()