#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
总导演Agent (DirectorAgent) 骨架代码
所属层级：15_Agent生态
职责：协调、调度、监控、恢复所有子Agent，作为Agent系统的中央指挥
依赖：仅依赖Python标准库 (可插拔设计，运行时动态加载Agent模块)
被调用者：更上层（如业务编排层、API层）通过实例化DirectorAgent来使用
解决：Agent生命周期管理、任务分发、异常处理、热插拔
可扩展性：使用注册表模式，支持新的Agent按配置自动加载
"""

import os
import sys
import json
import logging
import configparser
import importlib
import traceback
from typing import Dict, Any, Optional, List, Callable, Type, Union
from pathlib import Path


# ==================== 基础Agent协议定义 (仅用于类型提示和自测) ====================
class AgentProtocol:
    """
    Agent最小接口协议（并非实际基类，仅用于定义代理的预期行为）
    实际的Agent类应实现此协议中的方法，总导演不关心具体实现
    """
    def run(self, task_input: Any) -> Any:
        raise NotImplementedError

    def status(self) -> Dict[str, Any]:
        raise NotImplementedError

    def shutdown(self) -> None:
        raise NotImplementedError


# ==================== 总导演Agent主类 ====================
class DirectorAgent:
    """
    总导演Agent，负责Agent的注册、调度、监控与恢复。
    配置化驱动，支持热加载Agent模块。
    """

    def __init__(self, config_path: str = "config/director_config.ini"):
        """
        初始化总导演Agent

        Args:
            config_path: 配置文件路径，支持.ini或.json格式
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.agent_registry: Dict[str, Type[AgentProtocol]] = {}  # 存储Agent类
        self.agent_instances: Dict[str, AgentProtocol] = {}       # 实例化后的Agent
        self.logger: Optional[logging.Logger] = None

        # 启动流程
        self._load_config()
        self._setup_logging()
        self._load_agents_from_config()
        self.logger.info("总导演Agent初始化完成")

    def _load_config(self) -> None:
        """
        加载配置文件，支持.ini和.json两种格式
        inp: 根据config_path自动识别格式并解析
        """
        if not os.path.exists(self.config_path):
            # 默认配置
            self.config = {
                "logging": {
                    "level": "INFO",
                    "format": "[%(asctime)s] %(name)-12s %(levelname)-8s %(message)s",
                    "file": "logs/director.log"
                },
                "agents": {
                    "module_paths": []  # 例如 ["agents.text_agent.TextAgent"]
                },
                "pipeline": {
                    "default_sequence": []
                }
            }
            os.makedirs(os.path.dirname(self.config_path) or ".", exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                if self.config_path.endswith('.json'):
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
                else:
                    config = configparser.ConfigParser()
                    config.read_dict(self.config)
                    config.write(f)
            self.logger = logging.getLogger('Director')
            self.logger.warning(f"配置文件不存在，已生成默认配置: {self.config_path}")
        else:
            if self.config_path.endswith('.json'):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                parser = configparser.ConfigParser()
                parser.read(self.config_path, encoding='utf-8')
                self.config = {section: dict(parser.items(section)) for section in parser.sections()}
                # 特殊处理列表类型的配置（手动解析逗号分隔）
                if 'agents' in self.config and 'module_paths' in self.config['agents']:
                    paths_str = self.config['agents']['module_paths']
                    if isinstance(paths_str, str):
                        self.config['agents']['module_paths'] = [p.strip() for p in paths_str.split(',') if p.strip()]
                if 'pipeline' in self.config and 'default_sequence' in self.config['pipeline']:
                    seq_str = self.config['pipeline']['default_sequence']
                    if isinstance(seq_str, str):
                        self.config['pipeline']['default_sequence'] = [s.strip() for s in seq_str.split(',') if s.strip()]

    def _setup_logging(self) -> None:
        """
        配置日志系统，输出到控制台和文件
        """
        log_config = self.config.get('logging', {})
        level_str = log_config.get('level', 'INFO')
        log_format = log_config.get('format', '[%(asctime)s] %(name)-12s %(levelname)-8s %(message)s')
        log_file = log_config.get('file', 'logs/director.log')

        level = getattr(logging, level_str.upper(), logging.INFO)
        logger = logging.getLogger('Director')
        logger.setLevel(level)
        # 避免重复添加handler
        logger.handlers.clear()

        # 控制台handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)
        formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
        ch.setFormatter(formatter)
        logger.addHandler(ch)

        # 文件handler
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        self.logger = logger

    def _load_agents_from_config(self) -> None:
        """
        从配置中动态加载Agent模块，并注册到注册表
        支持热插拔：通过模块路径字符串导入Agent类
        """
        agent_paths = self.config.get('agents', {}).get('module_paths', [])
        if not agent_paths:
            self.logger.info("配置中未定义任何Agent模块，跳过自动加载")
            return

        for path in agent_paths:
            try:
                # 路径格式应为 "package.module.ClassName"
                module_name, class_name = path.rsplit('.', 1)
                module = importlib.import_module(module_name)
                agent_class = getattr(module, class_name)
                self.register_agent(class_name, agent_class)
                self.logger.info(f"成功加载Agent: {class_name} 来自 {module_name}")
            except Exception as e:
                self.logger.error(f"加载Agent失败 [{path}]: {e}\n{traceback.format_exc()}")

    def register_agent(self, agent_name: str, agent_class: Type[AgentProtocol]) -> None:
        """
        手工注册一个Agent类（可插拔接口）

        Args:
            agent_name: Agent唯一标识名称
            agent_class: 实现了AgentProtocol协议的类
        """
        if agent_name in self.agent_registry:
            self.logger.warning(f"Agent [{agent_name}] 已存在，将被覆盖")
        self.agent_registry[agent_name] = agent_class
        self.logger.info(f"Agent已注册: {agent_name} -> {agent_class.__name__}")

    def deregister_agent(self, agent_name: str) -> bool:
        """
        移除Agent注册（热卸载）
        Args:
            agent_name: 要移除的Agent名称
        Returns:
            是否成功移除
        """
        if agent_name in self.agent_registry:
            # 如果已有实例，先尝试关闭
            if agent_name in self.agent_instances:
                try:
                    self.logger.info(f"正在关闭Agent实例: {agent_name}")
                    self.agent_instances[agent_name].shutdown()
                except Exception as e:
                    self.logger.error(f"关闭Agent实例时出错: {e}")
                del self.agent_instances[agent_name]
            del self.agent_registry[agent_name]
            self.logger.info(f"Agent [{agent_name}] 已注销")
            return True
        return False

    def get_agent_instance(self, agent_name: str) -> Optional[AgentProtocol]:
        """
        获取或创建Agent实例（延迟实例化，支持单例复用）

        Args:
            agent_name: Agent名称
        Returns:
            Agent实例，若不存在则返回None
        """
        if agent_name in self.agent_instances:
            return self.agent_instances[agent_name]
        if agent_name in self.agent_registry:
            try:
                agent_class = self.agent_registry[agent_name]
                instance = agent_class()
                self.agent_instances[agent_name] = instance
                self.logger.info(f"Agent实例化成功: {agent_name}")
                return instance
            except Exception as e:
                self.logger.error(f"实例化Agent [{agent_name}] 失败: {e}")
                return None
        self.logger.error(f"Agent [{agent_name}] 未注册")
        return None

    def assign_task(self, agent_name: str, task_data: Any) -> Optional[Any]:
        """
        将任务分配给指定Agent执行

        Args:
            agent_name: 目标Agent名称
            task_data: 任务数据（根据需要传递）
        Returns:
            Agent执行结果，或执行失败时返回None
        """
        agent = self.get_agent_instance(agent_name)
        if not agent:
            return None
        try:
            self.logger.info(f"分配任务给 [{agent_name}]，任务类型: {type(task_data).__name__}")
            result = agent.run(task_data)
            self.logger.info(f"Agent [{agent_name}] 执行成功")
            return result
        except Exception as e:
            self.logger.error(f"Agent [{agent_name}] 执行失败: {e