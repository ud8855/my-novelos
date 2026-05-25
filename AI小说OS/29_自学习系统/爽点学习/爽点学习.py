import os
import json
import logging
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from configparser import ConfigParser
from datetime import datetime

# 日志配置默认值
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DEFAULT_LOG_FILE = 'logs/pleasure_learning.log'

class BasePleasureLearner(ABC):
    """爽点学习器抽象基类，定义标准接口，确保可插拔性"""
    @abstractmethod
    def learn(self, feedback_data: Dict[str, Any]) -> bool:
        """从反馈数据中学习爽点模式"""
        pass

    @abstractmethod
    def predict(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """根据当前写作上下文预测应使用的爽点策略"""
        pass

    @abstractmethod
    def save_state(self, path: str) -> bool:
        """持久化学习状态"""
        pass

    @abstractmethod
    def load_state(self, path: str) -> bool:
        """加载学习状态"""
        pass


class PleasurePointLearner(BasePleasureLearner):
    """
    爽点学习器
    职责：通过收集用户反馈、评分、修改行为等数据，学习个性化的爽点偏好，
         为生成模块提供动态调整的策略建议。
    依赖：20_模型协同/ 和 21_API模型/（通过抽象接口，避免直接调用）
    被调用：小说生成调度模块、用户交互采集模块
    """
    def __init__(self, config_path: str = "config/pleasure_learning.ini"):
        self.config = self._load_config(config_path)
        self.logger = self._setup_logger()
        self.model = None          # 学习模型实例，未来可注入不同算法
        self._state_version = "0.1.0"

        self.logger.info("PleasurePointLearner initialized (stub mode)")

    def _load_config(self, config_path: str) -> ConfigParser:
        """加载配置文件，若文件不存在则使用默认配置"""
        config = ConfigParser()
        # 默认配置
        config['DEFAULT'] = {
            'learning_rate': '0.01',
            'min_feedback_count': '10',
            'model_save_interval_hours': '24',
            'log_level': 'INFO',
            'log_file': DEFAULT_LOG_FILE,
        }
        if os.path.exists(config_path):
            config.read(config_path, encoding='utf-8')
            self._log_config_loaded(config_path)
        else:
            # 记录使用默认配置
            print(f"Config file {config_path} not found. Using default settings.")
        return config

    def _log_config_loaded(self, path: str):
        """将配置加载事件记录到日志（如果logger尚未建立，则先暂存）"""
        if hasattr(self, 'logger') and self.logger:
            self.logger.info(f"Configuration loaded from {path}")
        else:
            # 初始化阶段记录到临时文件或标准输出（由_setup_logger后续处理）
            with open("logs/startup.log", "a", encoding='utf-8') as f:
                f.write(f"{datetime.now()} - PleasurePointLearner - INFO - Config loaded from {path}\n")

    def _setup_logger(self) -> logging.Logger:
        """配置日志系统，支持控制台和文件输出"""
        logger = logging.getLogger('PleasurePointLearner')
        log_level_str = self.config.get('DEFAULT', 'log_level', fallback='INFO')
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)
        logger.setLevel(log_level)

        # 避免重复添加handler
        if not logger.handlers:
            # 控制台输出
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_formatter = logging.Formatter(DEFAULT_LOG_FORMAT)
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

            # 文件输出
            log_file = self.config.get('DEFAULT', 'log_file', fallback=DEFAULT_LOG_FILE)
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(log_level)
            file_formatter = logging.Formatter(DEFAULT_LOG_FORMAT)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        return logger

    def learn(self, feedback_data: Dict[str, Any]) -> bool:
        """
        学习接口：接收结构化反馈数据，更新内部模型
        :param feedback_data: 包含用户对生成片段的评分、选择、修改等信息的字典
        :return: 是否学习成功
        """
        self.logger.info(f"Learning from feedback: {json.dumps(feedback_data, ensure_ascii=False)[:200]}...")
        # 【TODO】实际学习逻辑，需要调用20_模型协同/ 和21_API模型/
        # 当前仅为骨架，模拟成功
        self.logger.debug("Learning completed (stub).")
        return True

    def predict(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        预测接口：根据当前上下文返回推荐的爽点策略列表
        :param context: 当前小说写作的状态信息（章节、情节、角色、情绪等）
        :return: 爽点策略列表，每个策略为一个字典，包含名称、参数、权重等
        """
        self.logger.info(f"Predicting pleasure points for context: {json.dumps(context, ensure_ascii=False)[:200]}...")
        # 【TODO】调用训练好的模型进行预测，返回可用的爽点策略
        self.logger.debug("Prediction completed (stub). Returning empty list.")
        return []

    def save_state(self, path: str) -> bool:
        """
        保存当前学习状态到文件
        :param path: 保存路径（通常为模型或状态文件）
        :return: 是否保存成功
        """
        self.logger.info(f"Saving learner state to {path}")
        # 确保目录存在
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            # 【TODO】实际序列化逻辑
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({
                    "state_version": self._state_version,
                    "timestamp": datetime.now().isoformat(),
                    "model_info": "stub - placeholder for real model parameters"
                }, f, ensure_ascii=False, indent=2)
            self.logger.info(f"State saved successfully to {path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}", exc_info=True)
            return False

    def load_state(self, path: str) -> bool:
        """
        从文件加载学习状态
        :param path: 状态文件路径
        :return: 是否加载成功
        """
        self.logger.info(f"Loading learner state from {path}")
        if not os.path.exists(path):
            self.logger.warning(f"State file not found: {path}")
            return False
        try:
            with open(path, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            # 【TODO】实际反序列化逻辑，恢复模型参数
            self._state_version = state_data.get("state_version", "0.0.0")
            self.logger.info(f"State loaded successfully, version: {self._state_version}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to load state: {e}", exc_info=True)
            return False

    def self_test(self) -> bool:
        """自测函数，验证模块基本功能"""
        self.logger.info("Starting self-test...")
        try:
            # 1. 测试学习接口
            test_feedback = {"rating": 5, "selected_segment": "fight_scene_1", "timestamp": datetime.now().isoformat()}
            assert self.learn(test_feedback), "Learn method failed"

            # 2. 测试预测接口
            test_context = {"current_chapter": 3, "genre": "xianxia", "mood": "tense"}
            prediction = self.predict(test_context)
            assert isinstance(prediction, list), "Predict should return a list"

            # 3. 测试状态保存与加载
            temp_path = "temp_test_state.json"
            assert self.save_state(temp_path), "Save state failed"
            assert self.load_state(temp_path), "Load state failed"
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)

            self.logger.info("Self-test passed successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Self-test failed: {e}", exc_info=True)
            return False


if __name__ == "__main__":
    # 模块自测入口
    learner = PleasurePointLearner()
    if learner.self_test():
        print("Self-test completed successfully.")
    else:
        print("Self-test encountered errors. Check logs for details.")