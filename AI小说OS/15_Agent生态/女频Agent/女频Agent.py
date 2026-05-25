# -*- coding: utf-8 -*-
"""
女频Agent (FemaleFrequencyAgent)
所属层: 15_Agent生态
依赖: BaseAgent (15_Agent生态/BaseAgent), 配置加载模块, 日志模块
被调用: 由Agent管理器(如AgentOrchestrator)调用, 或通过任务分发系统调用
解决问题: 专门处理女频小说创作任务, 包括生成大纲、章节、人物等, 可根据配置选择不同模型和风格
"""

import logging
import os
from typing import Any, Dict, Optional

# 导入基类 (假设基类在同级目录的BaseAgent.py中)
from .BaseAgent import BaseAgent
from .config_loader import load_agent_config  # 假定的配置加载工具

logger = logging.getLogger(__name__)


class FemaleFrequencyAgent(BaseAgent):
    """
    女频创作Agent
    负责处理女频相关的小说创作请求, 支持多种女频子类型(言情、耽美、百合等),
    通过配置可灵活指定使用的模型、参数及创作策略.
    实现可插拔、可配置、可观测.
    """

    # 默认配置 (当外部未提供时使用)
    DEFAULT_CONFIG = {
        "agent_name": "FemaleFrequencyAgent",
        "agent_type": "female_frequency",
        "model": {
            "provider": "openai",          # 模型提供商, 如 openai / local
            "model_name": "gpt-4",         # 具体模型名称
            "temperature": 0.8,
            "max_tokens": 2048,
        },
        "styles": ["modern_romance", "ancient_romance", "bl", "gl", "rebirth"],
        "default_style": "modern_romance",
        "retry": {
            "max_attempts": 3,
            "backoff_factor": 0.5,
        },
        "enable_cache": False,
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None, agent_id: Optional[str] = None):
        """
        初始化女频Agent
        :param config: 外部传入的配置字典, 会合并到默认配置上
        :param agent_id: Agent的唯一标识, 如果不提供则自动生成
        """
        # 合并配置: 默认配置为底, 外部配置覆盖
        self.config = self.DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)

        # 调用基类初始化
        super().__init__(agent_id=agent_id, config=self.config)

        # 从配置中提取常用参数
        self.model_config = self.config.get("model", {})
        self.styles = self.config.get("styles", ["modern_romance"])
        self.default_style = self.config.get("default_style", "modern_romance")

        # 内部状态
        self._is_initialized = False
        self._model_connector = None  # 模型连接器, 初始化时建立
        logger.info(f"[{self.agent_id}] 女频Agent实例创建成功, 配置: {self.config}")

    def initialize(self) -> bool:
        """
        初始化Agent资源: 建立模型连接, 检查配置有效性等
        :return: 是否初始化成功
        """
        try:
            # 检查模型配置是否完整
            required_model_keys = ["provider", "model_name"]
            for key in required_model_keys:
                if key not in self.model_config:
                    raise ValueError(f"模型配置缺少必要字段: {key}")

            # 模拟建立模型连接 (实际项目应连接真实的模型服务)
            # 这里为了骨架演示, 仅设置标记
            self._model_connector = f"ModelConnector({self.model_config['provider']}:{self.model_config['model_name']})"
            self._is_initialized = True
            logger.info(f"[{self.agent_id}] 初始化成功, 模型连接器: {self._model_connector}")
            return True
        except Exception as e:
            logger.error(f"[{self.agent_id}] 初始化失败: {e}", exc_info=True)
            return False

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行女频创作任务
        任务格式示例:
        {
            "task_type": "outline" / "chapter" / "character",
            "style": "modern_romance",  # 可选, 默认使用default_style
            "parameters": { ... }  # 具体创作参数
        }
        :param task: 任务字典
        :return: 执行结果
        """
        if not self._is_initialized:
            self.initialize()
            if not self._is_initialized:
                return {"error": "Agent未初始化, 无法执行任务"}

        task_type = task.get("task_type")
        style = task.get("style", self.default_style)
        params = task.get("parameters", {})

        if style not in self.styles:
            logger.warning(f"[{self.agent_id}] 不支持的风格 {style}, 使用默认风格 {self.default_style}")
            style = self.default_style

        logger.info(f"[{self.agent_id}] 收到任务: type={task_type}, style={style}, params={params}")

        # 根据任务类型分发处理
        try:
            if task_type == "outline":
                result = self._generate_outline(style, params)
            elif task_type == "chapter":
                result = self._generate_chapter(style, params)
            elif task_type == "character":
                result = self._generate_character(style, params)
            else:
                raise ValueError(f"未知任务类型: {task_type}")

            logger.info(f"[{self.agent_id}] 任务执行成功, 结果摘要: {str(result)[:100]}...")
            return {"status": "success", "data": result, "agent_id": self.agent_id}
        except Exception as e:
            logger.error(f"[{self.agent_id}] 任务执行异常: {e}", exc_info=True)
            return {"status": "error", "message": str(e), "agent_id": self.agent_id}

    def _generate_outline(self, style: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成故事大纲 (占位实现)
        :param style: 风格
        :param params: 参数, 如主角设定、梗概等
        :return: 生成的大纲
        """
        # 模拟调用模型生成大纲
        logger.debug(f"生成 {style} 风格大纲, 参数: {params}")
        # 实际代码: 通过 20_模型协同/ 和 21_API模型/ 调用模型
        return {
            "title": f"{style} 示例标题",
            "summary": "这是一个女频故事的示例大纲...",
            "chapters": ["第一章开头", "第二章发展", "第三章高潮", "第四章结局"]
        }

    def _generate_chapter(self, style: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成章节内容 (占位实现)
        :param style: 风格
        :param params: 章节参数 (章节号, 上下文等)
        :return: 生成的章节
        """
        logger.debug(f"生成 {style} 章节, 参数: {params}")
        return {
            "chapter_number": params.get("chapter_number", 1),
            "content": "这是章节内容示例。女主角在雨夜走进了那家咖啡馆..."
        }

    def _generate_character(self, style: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成角色设定 (占位实现)
        :param style: 风格
        :param params: 角色参数 (性别、性格倾向等)
        :return: 角色设定
        """
        logger.debug(f"生成 {style} 角色, 参数: {params}")
        return {
            "name": "示例角色名",
            "description": "温柔的世家千金，内心却隐藏着叛逆",
            "traits": ["善良", "倔强", "聪慧"]
        }

    def health_check(self) -> bool:
        """
        健康检查: 检查模型连接是否正常, 配置是否有效
        :return: 健康状态
        """
        if not self._is_initialized:
            return False
        # 可扩展更多检查, 例如 ping 模型服务
        return self._model_connector is not None

    def shutdown(self) -> bool:
        """
        关闭Agent, 释放资源 (如断开模型连接等)
        :return: 是否成功关闭
        """
        try:
            self._model_connector = None
            self._is_initialized = False
            logger.info(f"[{self.agent_id}] 女频Agent已关闭")
            return True
        except Exception as e:
            logger.error(f"[{self.agent_id}] 关闭时异常: {e}")
            return False

    # ---------- 配置热更新支持 ----------
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """
        在运行时更新配置 (热更新)
        :param new_config: 新的配置字典 (部分更新)
        """
        self.config.update(new_config)
        self.model_config = self.config.get("model", {})
        self.styles = self.config.get("styles", self.styles)
        self.default_style = self.config.get("default_style", self.default_style)
        logger.info(f"[{self.agent_id}] 配置已热更新: {new_config}")
        # 可选: 重新初始化模型连接等
        self._is_initialized = False
        self.initialize()


# ---------- 自测代码 ----------
if __name__ == "__main__":
    # 配置日志输出
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 1. 使用默认配置创建Agent
    agent = FemaleFrequencyAgent()
    print(f"Agent ID: {agent.agent_id}")
    print(f"健康检查: {agent.health_check()}")

    # 2. 初始化Agent
    init_success = agent.initialize()
    if not init_success:
        print("初始化失败, 退出")
        exit(1)

    # 3. 测试任务执行
    task_outline = {
        "task_type": "outline",
        "style": "ancient_romance",
        "parameters": {"protagonist": "官家小姐", "theme": "重生复仇"}
    }
    result = agent.execute(task_outline)
    print("任务结果:", result)

    task_chapter = {
        "task_type": "chapter",
        "style": "bl",
        "parameters": {"chapter_number": 5, "previous_summary": "两位男主在书院初遇"}
    }
    result_chapter = agent.execute(task_chapter)
    print("章节结果:", result_chapter)

    # 4. 测试健康检查
    print("健康状态:", agent.health_check())

    # 5. 测试热更新配置
    agent.update_config({"default_style": "gl", "model": {"temperature": 0.9}})
    print("更新后默认风格:", agent.default_style)

    # 6. 关闭
    agent.shutdown()
    print("关闭后健康状态:", agent.health_check())