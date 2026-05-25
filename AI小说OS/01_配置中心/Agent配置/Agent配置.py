"""Agent配置.py - Agent配置管理模块

职责：管理AI小说创作系统中所有Agent的配置信息。
功能：加载、保存、验证、热更新Agent配置，提供查询接口。
层级：配置中心（01_配置中心）
依赖：标准库（json, os, logging）
被调用：其他模块需要Agent配置时通过本模块获取，如任务调度器、Agent工厂等。
设计原则：单一职责、可插拔、配置驱动、日志记录、异常恢复、默认配置兜底。
"""

import json
import logging
import os
from typing import Dict, List, Any, Optional
from copy import deepcopy

# 配置日志，输出到控制台和文件（如果存在logs目录）
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
# 避免重复添加handler
if not logger.handlers:
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # 控制台handler
    ch = logging.StreamHandler()
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    # 文件handler（尝试创建log目录）
    try:
        if not os.path.exists('logs'):
            os.makedirs('logs')
        fh = logging.FileHandler('logs/agent_config.log', encoding='utf-8')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception as e:
        logger.warning(f"无法创建日志文件处理程序: {e}")

# ---------- 数据类定义 ----------

class AgentConfig:
    """单个Agent配置数据容器，提供默认值、校验和序列化"""
    def __init__(self, name: str = "default_agent", **kwargs):
        # 核心属性，支持默认值
        self.name: str = name                     # Agent唯一标识
        self.display_name: str = kwargs.get("display_name", name)  # 显示名称
        self.role: str = kwargs.get("role", "assistant")          # 角色描述
        self.model_name: str = kwargs.get("model_name", "gpt-3.5-turbo")  # 使用的模型
        self.prompt_template: str = kwargs.get("prompt_template", "")     # 提示词模板
        self.parameters: Dict[str, Any] = kwargs.get("parameters", {})    # 额外参数
        self.enabled: bool = kwargs.get("enabled", True)                  # 是否启用
        self.description: str = kwargs.get("description", "")             # 描述
        # 预留扩展字段
        self.metadata: Dict[str, Any] = kwargs.get("metadata", {})

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "role": self.role,
            "model_name": self.model_name,
            "prompt_template": self.prompt_template,
            "parameters": self.parameters,
            "enabled": self.enabled,
            "description": self.description,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentConfig":
        """从字典创建实例"""
        return cls(**data)

    def validate(self) -> bool:
        """
        校验配置有效性，返回True表示通过。
        可扩展核心校验规则。
        """
        try:
            assert isinstance(self.name, str) and len(self.name) > 0, "name 必须是非空字符串"
            # 模型名称基本校验
            assert isinstance(self.model_name, str) and len(self.model_name) > 0, "model_name 不能为空"
            # 参数类型校验
            assert isinstance(self.parameters, dict), "parameters 必须是字典"
            # 可以添加更多具体校验，此处为骨架保留扩展点
            logger.debug(f"Agent配置 {self.name} 校验通过")
            return True
        except AssertionError as e:
            logger.error(f"Agent配置 {self.name} 校验失败: {e}")
            return False

    def __repr__(self) -> str:
        return f"AgentConfig(name={self.name}, role={self.role}, model={self.model_name})"

# ---------- Agent配置管理器 ----------

class AgentConfigManager:
    """
    Agent配置管理器，负责加载、存储、热更新、批量管理和查询。
    支持从配置文件目录或单文件加载，提供配置中心统一接口。
    采用单例思路保证全局一致，但这里实现为正常类，使用时自行维护实例。
    """

    DEFAULT_CONFIG_DIR = "config/agents"  # 默认配置目录

    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化管理器
        :param config_dir: 配置文件目录路径，留空则使用默认
        """
        self._configs: Dict[str, AgentConfig] = {}  # name -> AgentConfig
        self.config_dir = config_dir or self.DEFAULT_CONFIG_DIR
        logger.info(f"Agent配置管理器初始化，配置目录: {self.config_dir}")

    def load_all(self) -> int:
        """
        从配置目录加载所有JSON配置文件，每个文件一个Agent配置。
        遵循：文件名即Agent名称，或从JSON内取name。
        返回成功加载的数量。
        """
        if not os.path.exists(self.config_dir):
            logger.warning(f"配置目录不存在: {self.config_dir}，跳过加载")
            return 0
        count = 0
        for filename in os.listdir(self.config_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.config_dir, filename)
                conf = self._load_single_file(filepath)
                if conf:
                    self._configs[conf.name] = conf
                    count += 1
        logger.info(f"从目录加载了 {count} 个Agent配置")
        return count

    def _load_single_file(self, filepath: str) -> Optional[AgentConfig]:
        """加载单个JSON文件并返回AgentConfig对象"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 支持两种格式：直接是Agent配置字段，或包含"agent"键
            if "name" in data:
                agent_data = data
            elif "agent" in data and isinstance(data["agent"], dict):
                agent_data = data["agent"]
            else:
                logger.error(f"配置文件 {filepath} 格式错误，缺少'name'或'agent'字段")
                return None
            config = AgentConfig.from_dict(agent_data)
            if not config.validate():
                logger.error(f"配置文件 {filepath} 校验失败，跳过")
                return None
            logger.debug(f"成功加载Agent配置: {config.name} 来自 {filepath}")
            return config
        except Exception as e:
            logger.error(f"加载配置文件 {filepath} 时出错: {e}", exc_info=True)
            return None

    def save_config(self, config: AgentConfig, filename: Optional[str] = None):
        """
        保存单个Agent配置到文件。
        :param config: AgentConfig实例
        :param filename: 保存的文件名，默认使用 {config.name}.json
        """
        if not filename:
            filename = f"{config.name}.json"
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        filepath = os.path.join(self.config_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)
            logger.info(f"Agent配置 {config.name} 已保存到 {filepath}")
        except Exception as e:
            logger.error(f"保存Agent配置失败: {e}", exc_info=True)

    def get_config(self, name: str) -> Optional[AgentConfig]:
        """根据名称获取配置深拷贝，避免外部意外修改"""
        cfg = self._configs.get(name)
        if cfg:
            return deepcopy(cfg)
        return None

    def list_configs(self) -> List[str]:
        """列出所有已加载Agent名称"""
        return list(self._configs.keys())

    def add_config(self, config: AgentConfig, persistent: bool = False, filename: Optional[str] = None):
        """
        动态添加Agent配置（热插拔）。
        :param config: AgentConfig实例
        :param persistent: 是否持久化保存到文件
        :param filename: 持久化时的文件名
        """
        if not config.validate():
            logger.error(f"添加配置失败: {config.name} 校验未通过")
            raise ValueError(f"Agent配置 {config.name} 无效")
        self._configs[config.name] = config
        if persistent:
            self.save_config(config, filename)
        logger.info(f"Agent配置 {config.name} 已注册到管理器")

    def remove_config(self, name: str, delete_file: bool = False):
        """
        移除Agent配置。
        :param name: Agent名称
        :param delete_file: 是否同时删除配置文件
        """
        if name in self._configs:
            del self._configs[name]
            if delete_file:
                filepath = os.path.join(self.config_dir, f"{name}.json")
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.info(f"已删除配置文件: {filepath}")
            logger.info(f"Agent配置 {name} 已移除")
        else:
            logger.warning(f"未找到要移除的Agent配置: {name}")

    def reload_config(self, name: Optional[str] = None):
        """
        热重载配置：重新从文件加载指定Agent或所有Agent。
        :param name: 若指定，则重载单个；否则重载全部。
        """
        if name is None:
            logger.info("开始重载所有Agent配置")
            self._configs.clear()
            self.load_all()
        else:
            logger.info(f"重载Agent配置: {name}")
            filepath = os.path.join(self.config_dir, f"{name}.json")
            if os.path.exists(filepath):
                conf = self._load_single_file(filepath)
                if conf:
                    self._configs[conf.name] = conf
                else:
                    logger.error(f"重载失败，配置无效: {name}")
            else:
                logger.warning(f"配置文件不存在: {filepath}")

    def get_enabled_configs(self) -> List[AgentConfig]:
        """获取所有已启用且有效的Agent配置列表"""
        return [deepcopy(cfg) for cfg in self._configs.values() if cfg.enabled and cfg.validate()]

    def update_config(self, name: str, updates: Dict[str, Any], persistent: bool = False):
        """
        动态更新部分配置字段，实现热更新。
        :param name: Agent名称
        :param updates: 包含要更新字段的字典
        :param persistent: 是否保存到文件
        """
        cfg = self._configs.get(name)
        if not cfg:
            raise KeyError(f"Agent配置 {name} 不存在")
        allowed_fields = {"display_name", "role", "model_name", "prompt_template", "parameters", "enabled", "description", "metadata"}
        for key, value in updates.items():
            if key in allowed_fields:
                setattr(cfg, key, value)
            else:
                logger.warning(f"忽略未知字段更新: {key}")
        if not cfg.validate():
            logger.error(f"更新后的配置 {name} 校验失败，回滚？此处简单抛出异常")
            # 简单起见，这里不做回滚，外部可捕获
            raise ValueError("更新后配置无效")
        if persistent:
            self.save_config(cfg)
        logger.info(f"Agent配置 {name} 已动态更新")

# ---------- 自测代码 ----------

def test_self():
    """
    自测方法：创建临时配置，测试加载、保存、增删改查、热加载等。
    仅用于开发阶段验证模块基本功能。
    """