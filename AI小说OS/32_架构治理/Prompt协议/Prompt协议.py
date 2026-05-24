# -*- coding: utf-8 -*-
"""
Prompt协议模块

本模块定义了 NovelOS 中所有 Prompt 模板的标准化协议，
确保 Prompt 可模板化、版本化、可验证、可插拔。

层级定位：架构治理层（32_架构治理）
依赖：无外部模块依赖
被调用：模型协同层（20_模型协同）、API模型层（21_API模型）或任何需要构造 Prompt 的模块
功能：定义 Prompt 模板的规范、存储、验证与热插拔接口
"""

import logging
import json
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

# -------------------- 日志配置 --------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
_ch = logging.StreamHandler()
_ch.setLevel(logging.DEBUG)
_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_ch.setFormatter(_formatter)
if not logger.handlers:
    logger.addHandler(_ch)

# -------------------- 配置化基础 --------------------
DEFAULT_CONFIG = {
    "prompt_templates_dir": "config/prompts",  # 模板文件存放目录
    "strict_validation": True,                # 是否严格验证参数完整性
    "version_format": "semver",               # 版本格式：semver, integer, date
    "allowed_extensions": [".json", ".yaml"],  # 模板文件后缀
}

class PromptConfig:
    """Prompt协议全局配置管理"""
    def __init__(self, config: Dict[str, Any] = None):
        self._config = DEFAULT_CONFIG.copy()
        if config:
            self.update(config)
    
    def update(self, config: Dict[str, Any]):
        for k, v in config.items():
            if k in self._config:
                logger.info("PromptConfig update: %s = %s", k, v)
                self._config[k] = v
            else:
                logger.warning("Unknown config key ignored: %s", k)
    
    def get(self, key: str, default=None):
        return self._config.get(key, default)

# -------------------- 数据结构定义 --------------------
@dataclass
class PromptTemplate:
    """
    标准化 Prompt 模板数据结构
    """
    name: str                      # 模板唯一标识
    version: str                   # 版本号（遵循 config 中的 version_format）
    description: str               # 用途描述
    content: str                   # 模板内容，可包含占位符 {param_name}
    parameters: List[str]          # 需要的参数列表
    metadata: Dict[str, Any]       # 扩展元数据（如作者、标签等）
    format: str = "plain"          # 内容格式：plain / f-string / jinja2 等
    
    def validate(self) -> bool:
        """自检模板是否合法"""
        if not self.name or not self.version or not self.content:
            logger.error("Template %s: missing required fields", self.name)
            return False
        # 检查参数是否在 content 中出现（简单检查）
        for param in self.parameters:
            if "{" + param + "}" not in self.content:
                logger.warning("Template %s: parameter '%s' not found in content", self.name, param)
        logger.debug("Template %s validated successfully", self.name)
        return True

# -------------------- Prompt协议核心接口 --------------------
class IPromptRegistry(ABC):
    """Prompt模板注册中心的抽象接口，实现可插拔"""
    
    @abstractmethod
    def register(self, template: PromptTemplate) -> bool:
        """注册一个模板，返回是否成功"""
        pass
    
    @abstractmethod
    def unregister(self, name: str, version: Optional[str] = None) -> bool:
        """注销模板，如指定版本则仅注销该版本"""
        pass
    
    @abstractmethod
    def get(self, name: str, version: Optional[str] = None) -> Optional[PromptTemplate]:
        """获取模板，不指定版本则返回最新版本"""
        pass
    
    @abstractmethod
    def list_all(self) -> List[str]:
        """列出所有模板名称"""
        pass
    
    @abstractmethod
    def list_versions(self, name: str) -> List[str]:
        """列出某模板的所有版本"""
        pass

class MemoryPromptRegistry(IPromptRegistry):
    """基于内存的模板注册实现（默认可插拔实现）"""
    
    def __init__(self, config: PromptConfig = None):
        self.config = config or PromptConfig()
        self._templates: Dict[str, Dict[str, PromptTemplate]] = {}  # name -> version -> template
        logger.info("MemoryPromptRegistry initialized")
    
    def register(self, template: PromptTemplate) -> bool:
        if not template.validate():
            logger.error("Template %s validation failed, not registered", template.name)
            return False
        name = template.name
        version = template.version
        if name not in self._templates:
            self._templates[name] = {}
        if version in self._templates[name]:
            logger.warning("Template %s version %s already exists, overwriting", name, version)
        self._templates[name][version] = template
        logger.info("Template registered: %s v%s", name, version)
        return True
    
    def unregister(self, name: str, version: Optional[str] = None) -> bool:
        if name not in self._templates:
            logger.warning("Template %s not found for unregister", name)
            return False
        if version:
            if version in self._templates[name]:
                del self._templates[name][version]
                logger.info("Unregistered template %s v%s", name, version)
                if not self._templates[name]:
                    del self._templates[name]
                return True
            else:
                logger.warning("Version %s not found for template %s", version, name)
                return False
        else:
            del self._templates[name]
            logger.info("Unregistered all versions of template %s", name)
            return True
    
    def get(self, name: str, version: Optional[str] = None) -> Optional[PromptTemplate]:
        if name not in self._templates:
            logger.debug("Template %s not found", name)
            return None
        if not version:
            # 返回最新版本（按字符串排序假设版本号可比较）
            sorted_versions = sorted(self._templates[name].keys())
            latest = sorted_versions[-1] if sorted_versions else None
            if latest:
                return self._templates[name][latest]
            return None
        return self._templates[name].get(version)
    
    def list_all(self) -> List[str]:
        return list(self._templates.keys())
    
    def list_versions(self, name: str) -> List[str]:
        if name in self._templates:
            return list(self._templates[name].keys())
        return []

# -------------------- 模板加载器（可插拔） --------------------
class ITemplateLoader(ABC):
    """从外部存储加载模板的抽象接口"""
    
    @abstractmethod
    def load(self, source: str) -> Optional[PromptTemplate]:
        """从来源加载单个模板"""
        pass

class JsonFileTemplateLoader(ITemplateLoader):
    """从JSON文件加载模板"""
    
    def __init__(self, config: PromptConfig = None):
        self.config = config or PromptConfig()
    
    def load(self, source: str) -> Optional[PromptTemplate]:
        try:
            with open(source, 'r', encoding='utf-8') as f:
                data = json.load(f)
            template = PromptTemplate(**data)
            if not template.validate():
                return None
            logger.info("Loaded template %s from %s", template.name, source)
            return template
        except Exception as e:
            logger.exception("Failed to load template from %s: %s", source, e)
            return None

# -------------------- Prompt协议管理器（对外唯一接口） --------------------
class PromptProtocolManager:
    """
    Prompt协议管理器
    整合注册中心、加载器、配置，提供统一的管理入口。
    所有模型调用方应通过此管理器获取 Prompt 模板，以遵守模板化协议。
    """
    
    def __init__(self, registry: Optional[IPromptRegistry] = None,
                       loader: Optional[ITemplateLoader] = None,
                       config: Optional[Dict[str, Any]] = None):
        self.config = PromptConfig(config)
        self.registry = registry if registry is not None else MemoryPromptRegistry(self.config)
        self.loader = loader if loader is not None else JsonFileTemplateLoader(self.config)
        logger.info("PromptProtocolManager initialized")
    
    def load_and_register(self, source: str) -> bool:
        """从来源加载模板并注册到中心"""
        template = self.loader.load(source)
        if template:
            return self.registry.register(template)
        return False
    
    def get_template(self, name: str, version: Optional[str] = None) -> Optional[PromptTemplate]:
        return self.registry.get(name, version)
    
    def render(self, name: str, parameters: Dict[str, Any], version: Optional[str] = None) -> Optional[str]:
        """
        渲染 Prompt 模板，填充参数，返回最终提示词。
        """
        template = self.get_template(name, version)
        if not template:
            logger.error("Cannot render: template %s not found", name)
            return None
        
        # 简单参数检查
        missing = [p for p in template.parameters if p not in parameters]
        if missing and self.config.get("strict_validation", True):
            logger.error("Missing parameters for template %s: %s", name, missing)
            return None
        
        try:
            # 简单占位符替换
            rendered = template.content
            for param, value in parameters.items():
                rendered = rendered.replace("{" + param + "}", str(value))
            logger.info("Rendered template %s", name)
            return rendered
        except Exception as e:
            logger.exception("Rendering failed for template %s: %s", name, e)
            return None

# -------------------- 自测代码 --------------------
def self_test():
    """Prompt协议模块自测"""
    import textwrap
    
    print("=== Prompt协议模块自测开始 ===")
    
    # 1. 手动创建模板并注册
    registry = MemoryPromptRegistry()
    loader = JsonFileTemplateLoader()
    manager = PromptProtocolManager(registry=registry, loader=loader)
    
    template = PromptTemplate(
        name="test_greeting",
        version="1.0.0",
        description="A test greeting template",
        content="Hello, {name}! How are you today?",
        parameters=["name"],
        metadata={"author": "test"}
    )
    
    assert registry.register(template), "Register failed"
    assert manager.get_template("test_greeting") is not None
    
    # 2. 渲染测试
    rendered = manager.render("test_greeting", {"name": "World"})
    assert rendered == "Hello, World! How are you today?", f"Unexpected render: {rendered}"
    print("Render test passed:", rendered)
    
    # 3. 版本管理测试
    template_v2 = PromptTemplate(
        name="test_greeting",
        version="2.0.0",
        description="Improved greeting",
        content="Greetings, {name}.",
        parameters=["name"],
        metadata={"author": "test"}
    )
    registry.register(template_v2)
    latest = registry.get("test_greeting")  # 应返回最新版本2.0.0
    assert latest.version == "2.0.0"
    print("Version test passed, latest:", latest.version)
    
    # 4. 注销测试
    registry.unregister("test_greeting", "1.0.0")
    assert registry.get("test_greeting", "1.0.0") is None
    assert registry.get("test_greeting") is not None  # 2.0.0仍然存在