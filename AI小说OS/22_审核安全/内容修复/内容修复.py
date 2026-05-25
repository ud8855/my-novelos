"""
内容修复模块
属于：22_审核安全
依赖：20_模型协同（接口）、21_API模型（接口）、23_日志监控（日志接口）
被调用者：审核流程中的内容修复环节
解决问题：当审核模块发现内容存在安全/合规问题时，尝试自动修复内容，使其符合要求。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging
import configparser
import os
import sys
import traceback

# 日志记录器，遵循项目日志规范，优先使用统一日志服务（占位）
try:
    from 23_日志监控.日志服务 import get_logger
except ImportError:
    # 回退到标准 logging
    def get_logger(name):
        logger = logging.getLogger(name)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s] %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.DEBUG)
        return logger


class BaseContentRepairer(ABC):
    """
    内容修复器抽象基类
    所有具体修复策略必须实现此接口，保证可插拔
    """

    def __init__(self, config: Dict[str, Any]):
        """
        :param config: 修复器配置字典
        """
        self.config = config
        self.logger = get_logger(self.__class__.__name__)

    @abstractmethod
    def repair(self, original_content: str, issue_info: Optional[Dict[str, Any]] = None) -> str:
        """
        尝试修复指定内容
        :param original_content: 原始文本
        :param issue_info: 审核检测出的问题描述（可选），如 {'type': 'sensitive_word', 'words': [...]}
        :return: 修复后的文本
        """
        pass


class RuleBasedContentRepairer(BaseContentRepairer):
    """
    基于规则的内容修复器（示例骨架）
    实际业务逻辑待实现
    """

    def repair(self, original_content: str, issue_info: Optional[Dict[str, Any]] = None) -> str:
        self.logger.info("规则修复器开始修复内容...")
        # TODO: 从配置加载规则，执行替换或修正
        try:
            # 占位修复：直接返回原内容
            repaired = original_content
            # 此处应实现规则处理
            self.logger.debug(f"修复完成，输入长度：{len(original_content)}，输出长度：{len(repaired)}")
            return repaired
        except Exception as e:
            self.logger.error(f"规则修复过程异常: {e}\n{traceback.format_exc()}")
            # 异常恢复：根据配置决定返回原内容或抛出
            if self.config.get('fallback_to_original', True):
                self.logger.warning("回退返回原始内容")
                return original_content
            else:
                raise


class LLMContentRepairer(BaseContentRepairer):
    """
    基于大语言模型的内容修复器骨架
    通过 20_模型协同 和 21_API模型 调用模型
    """

    def repair(self, original_content: str, issue_info: Optional[Dict[str, Any]] = None) -> str:
        self.logger.info("LLM修复器开始修复内容...")
        try:
            # TODO: 构造Prompt模板（应从模板文件加载）
            prompt = self._build_prompt(original_content, issue_info)
            # 调用模型协同层处理
            repaired = self._call_model(prompt)
            self.logger.debug(f"LLM修复完成，输入长度：{len(original_content)}，输出长度：{len(repaired)}")
            return repaired
        except Exception as e:
            self.logger.error(f"LLM修复异常: {e}\n{traceback.format_exc()}")
            if self.config.get('fallback_to_original', True):
                self.logger.warning("回退返回原始内容")
                return original_content
            else:
                raise

    def _build_prompt(self, content: str, issue_info: Optional[Dict]) -> str:
        # 从模板文件加载Prompt，此处简化为占位
        # 实际应使用模板引擎，并遵循Prompt模板化管理
        prompt = f"请修复以下内容中存在的问题（{issue_info}）：\n{content}"
        return prompt

    def _call_model(self, prompt: str) -> str:
        # 通过 20_模型协同/ 和 21_API模型/ 进行调用，此处为接口占位
        # 实际调用方式：
        # from 20_模型协同.协同调度 import ModelCoordinator
        # coordinator = ModelCoordinator(config)
        # return coordinator.call(prompt)
        # 这里模拟返回
        self.logger.info("调用模型协同层（占位）")
        return prompt  # 原样返回，仅用于测试


class ContentRepairer:
    """
    内容修复器主类，负责加载配置、选择修复策略、执行修复
    实现可插拔：通过配置文件指定修复器类型，支持热替换策略
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        :param config_path: 配置文件路径，若不提供则使用默认配置
        """
        self.logger = get_logger("ContentRepairer")
        self.config = self._load_config(config_path)
        self.repairer: Optional[BaseContentRepairer] = None
        self._init_repairer()

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """加载配置，支持配置文件缺失时的默认值"""
        defaults = {
            'repairer_type': 'rule_based',  # rule_based 或 llm
            'fallback_to_original': True,
            'max_retries': 1,
            'rule_based': {},   # 规则修复器专用配置
            'llm': {            # LLM修复器专用配置
                'model_name': 'default',
                'temperature': 0.7,
                'prompt_template_path': 'configs/repair_prompts/repair.txt'
            }
        }
        if config_path and os.path.exists(config_path):
            parser = configparser.ConfigParser()
            parser.read(config_path, encoding='utf-8')
            # 合并配置文件中的值
            if parser.has_section('repair'):
                for key in defaults:
                    if key in parser['repair']:
                        defaults[key] = parser['repair'][key]
        return defaults

    def _init_repairer(self):
        """根据配置初始化修复器实例"""
        repairer_type = self.config.get('repairer_type', 'rule_based')
        self.logger.info(f"初始化修复器，类型：{repairer_type}")
        if repairer_type == 'rule_based':
            self.repairer = RuleBasedContentRepairer(self.config.get('rule_based', {}))
        elif repairer_type == 'llm':
            self.repairer = LLMContentRepairer(self.config.get('llm', {}))
        else:
            raise ValueError(f"不支持的修复器类型: {repairer_type}")

    def repair(self, original_content: str, issue_info: Optional[Dict[str, Any]] = None) -> str:
        """
        修复内容入口
        :param original_content: 需要修复的文本
        :param issue_info: 审核问题信息
        :return: 修复后的文本
        """
        if not self.repairer:
            self.logger.error("修复器未初始化，尝试重新初始化")
            self._init_repairer()
        try:
            return self.repairer.repair(original_content, issue_info)
        except Exception as e:
            self.logger.error(f"修复过程致命错误: {e}")
            # 最终兜底：根据配置决定返回原内容或抛出异常
            if self.config.get('fallback_to_original', True):
                return original_content
            raise

    def hot_reload_config(self, config_path: Optional[str] = None):
        """
        热更新配置并重新初始化修复器
        """
        self.logger.info("执行热更新配置...")
        self.config = self._load_config(config_path)
        self._init_repairer()


# 自测部分
if __name__ == "__main__":
    # 设置测试日志
    logging.basicConfig(level=logging.DEBUG)

    # 模拟配置（可创建临时配置文件）
    test_config = {
        'repairer_type': 'rule_based',
        'fallback_to_original': True,
        'rule_based': {},
        'llm': {}
    }

    # 方式1：直接使用配置字典（为演示目的，修改 _load_config 使其返回字典，此处直接注入）
    # 由于 ContentRepairer 从文件加载，可以临时创建一个配置文件或修改构造函数支持字典。
    # 为简化自测，我们直接实例化修复器子类进行测试。
    print("===== RuleBased 修复器自测 =====")
    rep = RuleBasedContentRepairer(test_config['rule_based'])
    result = rep.repair("测试敏感词内容", {'type': 'sensitive', 'words': ['敏感词']})
    print(f"修复结果: {result}")

    print("\n===== LLM修复器自测（占位） =====")
    llm_rep = LLMContentRepairer(test_config['llm'])
    result_llm = llm_rep.repair("测试文本", {'type': 'violence'})
    print(f"LLM修复结果: {result_llm}")

    print("\n===== 主修复器自测（需要配置文件） =====")
    # 创建临时配置文件
    temp_conf = "temp_repair_config.ini"
    with open(temp_conf, 'w', encoding='utf-8') as f:
        f.write("[repair]\n")
        f.write("repairer_type = rule_based\n")
        f.write("fallback_to_original = True\n")
    try:
        cr = ContentRepairer(temp_conf)
        test_content = "这是一段包含不良信息的内容"
        res = cr.repair(test_content, {'type': 'harmful'})
        print(f"主修复器结果: {res}")
    finally:
        os.remove(temp_conf)
    print("自测完成。")