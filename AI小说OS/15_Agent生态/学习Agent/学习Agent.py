"""
学习Agent骨架模块
功能：从用户反馈、小说生成历史、风格偏好等数据中持续学习，提升后续创作质量。
所属层：15_Agent生态
依赖：配置管理模块、日志模块、数据分析接口（抽象）、模型调用接口（抽象）
被谁调用：调度中心、其他Agent（如写作Agent请求风格建议）
解决问题：使系统具备自适应学习能力，避免重复错误，捕获用户意图演变
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, Optional, List

# 添加项目根目录到系统路径，保障内部模块导入
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# 假设配置和日志由核心模块提供，这里做可插拔的默认实现
try:
    from 01_内核.config_manager import ConfigManager
except ImportError:
    # 占位：当核心模块未就绪时，使用本地简单配置
    class ConfigManager:
        @staticmethod
        def get_config(section: str, key: str, default=None):
            # 后期替换为真正的配置读取
            _defaults = {
                "learning_agent": {
                    "model_name": "default_learner",
                    "feedback_window": 100,
                    "style_analysis_threshold": 0.7,
                    "logging_level": "INFO"
                }
            }
            return _defaults.get(section, {}).get(key, default)

try:
    from 01_内核.log_manager import LogManager
except ImportError:
    # 占位日志
    class LogManager:
        @staticmethod
        def get_logger(name):
            logger = logging.getLogger(name)
            if not logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                logger.addHandler(handler)
                logger.setLevel(logging.DEBUG)
            return logger

class LearningAgent:
    """
    学习Agent，负责从各种信号中提取知识并更新内部模型/策略。
    可插拔设计：具体学习算法通过策略模式注入，支持运行时替换。
    """
    def __init__(self, agent_id: str = "learning_agent_01", config: Optional[Dict[str, Any]] = None):
        """
        初始化学习Agent
        :param agent_id: 唯一标识符
        :param config: 外部传入的配置字典，若未提供则使用ConfigManager
        """
        self.agent_id = agent_id
        self.logger = LogManager.get_logger(f"LearningAgent.{agent_id}")
        self.config = config if config else self._load_default_config()
        self._validate_config()
        self.model = None           # 内部学习模型，后期替换为具体实现
        self.memory_buffer = []     # 学习样本缓冲区
        self.is_initialized = False
        self.logger.info(f"LearningAgent {agent_id} 实例已创建，等待初始化...")

    def _load_default_config(self) -> Dict[str, Any]:
        """从ConfigManager加载默认配置"""
        return {
            "model_name": ConfigManager.get_config("learning_agent", "model_name", "default_learner"),
            "feedback_window": ConfigManager.get_config("learning_agent", "feedback_window", 100),
            "style_analysis_threshold": ConfigManager.get_config("learning_agent", "style_analysis_threshold", 0.7),
            "logging_level": ConfigManager.get_config("learning_agent", "logging_level", "INFO")
        }

    def _validate_config(self):
        """验证必要配置项存在"""
        required_keys = ["model_name", "feedback_window"]
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"LearningAgent 配置缺少必需项: {key}")

    def initialize(self) -> bool:
        """
        初始化学习Agent，加载模型、分配资源等。
        可热插拔：若模型路径或资源不可用，可降级为规则学习。
        """
        try:
            self.logger.info("开始初始化学习模型...")
            # 这里未来会加载预训练模型或构建空模型
            # 目前骨架：模拟初始化成功
            self.model = {"name": self.config["model_name"], "status": "loaded"}
            self.is_initialized = True
            self.logger.info("学习Agent初始化成功。")
            return True
        except Exception as e:
            self.logger.error(f"初始化失败: {e}")
            self.is_initialized = False
            return False

    def learn_from_feedback(self, feedback_data: Dict[str, Any]) -> bool:
        """
        根据用户反馈学习，调整偏好或修正错误模式。
        :param feedback_data: 包含反馈类型、内容、时间戳等信息的字典
        :return: 学习是否成功执行
        """
        if not self.is_initialized:
            self.logger.warning("Agent未初始化，无法学习。")
            return False
        self.memory_buffer.append(feedback_data)
        if len(self.memory_buffer) > self.config["feedback_window"]:
            # 简单移除最旧数据，实际会进行批处理学习
            self.memory_buffer.pop(0)
        self.logger.debug(f"接收反馈，当前缓冲区大小: {len(self.memory_buffer)}")
        # 这里触发实际的学习更新（骨架中为占位）
        self._update_internal_model(feedback_data)
        return True

    def analyze_style(self, text_sample: str) -> Optional[Dict[str, float]]:
        """
        分析给定文本的风格特征，提取风格向量。
        :param text_sample: 待分析的文本
        :return: 风格特征字典，如 {'流畅度': 0.8, '文采': 0.6}，失败返回None
        """
        if not self.is_initialized:
            self.logger.warning("Agent未初始化，无法分析风格。")
            return None
        # 占位实现：返回模拟特征
        self.logger.debug(f"分析文本风格，长度 {len(text_sample)}")
        return {"fluency": 0.85, "literariness": 0.72}

    def get_recommendation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于历史学习，为其他Agent提供创作建议（如用词、情节方向）。
        :param context: 当前创作上下文
        :return: 建议字典
        """
        if not self.is_initialized:
            self.logger.warning("Agent未初始化，返回空建议。")
            return {}
        # 这里会调用学习到的策略来生成建议
        return {
            "suggested_style": "抒情",
            "avoid_words": ["非常", "突然"],
            "confidence": 0.7
        }

    def _update_internal_model(self, feedback: Dict[str, Any]):
        """
        内部方法：根据新数据更新模型参数/规则。
        目前为占位，实际将实现增量学习、参数调整等。
        """
        self.logger.info(f"内部模型更新被触发，反馈类型: {feedback.get('type', 'unknown')}")
        # TODO: 实现具体的学习算法（强化学习、对比学习等）
        pass

    def shutdown(self):
        """优雅关闭，保存状态，释放资源"""
        self.logger.info("LearningAgent 正在关闭...")
        # 保存模型、清理缓冲区等
        self.memory_buffer.clear()
        self.model = None
        self.is_initialized = False
        self.logger.info("LearningAgent 已安全关闭。")

    # ---------- 自测部分 ----------
    @staticmethod
    def self_test():
        """模块内自测，验证基本功能"""
        print("===== LearningAgent 自测开始 =====")
        # 实例化，使用默认配置
        agent = LearningAgent(agent_id="test_agent")
        # 初始化
        assert agent.initialize() == True, "初始化应成功"
        # 学习反馈
        sample_feedback = {"type": "style_preference", "user_id": "user1", "preference": "幽默"}
        assert agent.learn_from_feedback(sample_feedback) == True, "学习反馈应成功"
        # 分析风格
        style = agent.analyze_style("春风又绿江南岸，明月何时照我还。")
        assert style is not None, "风格分析不应返回None"
        print(f"风格分析结果: {style}")
        # 获取建议
        rec = agent.get_recommendation({"current_plot": "悬疑"})
        print(f"创作建议: {rec}")
        # 关闭
        agent.shutdown()
        print("===== LearningAgent 自测通过 =====")

if __name__ == "__main__":
    LearningAgent.self_test()