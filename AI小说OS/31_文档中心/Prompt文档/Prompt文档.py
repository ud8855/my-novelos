"""
Prompt文档.py
模块路径: 31_文档中心/Prompt文档
所属层次: 文档中心层
依赖: 无 (可依赖配置中心、日志中心)
被调用: 由各个Agent、Agent工厂、模型协同层获取Prompt模板
职责: Prompt模板的统一管理, 提供模板加载、保存、查询、渲染等接口, 支持热更新、配置化、日志记录

设计原则:
- 单例模式, 全局唯一实例
- 模板文件存储在外部分层目录中, 路径可配置
- 模板必须支持占位符替换
- 所有操作记录日志
- 自测试用if __name__ == "__main__"块
"""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
import json


# 全局配置(可由配置中心覆盖)
DEFAULT_CONFIG = {
    "prompt_dir": "./prompts",               # 默认模板目录
    "default_encoding": "utf-8",             # 模板文件编码
    "cache_enabled": True,                   # 是否缓存模板内容
    "auto_reload": True,                     # 是否自动检测更新并重新加载
    "reload_interval_sec": 30,               # 自动重载检查间隔(秒)
    "placeholder_pattern": r"\{\{(\w+)\}\}"  # 占位符正则模式(未在骨架中使用)
}

class PromptDocumentManager(ABC):
    """Prompt文档管理器抽象基类, 定义所有必需接口, 便于未来插拔替换"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化管理器
        :param config: 用户自定义配置, 将与默认配置合并
        """
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
            
        # 初始化日志
        self.logger = logging.getLogger(self.__class__.__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # 模板缓存: {template_name: content}
        self._cache: Dict[str, str] = {}
        self._last_reload_time: float = 0.0
        
        self.logger.info(f"{self.__class__.__name__} initialized with config: {self.config}")

    @abstractmethod
    def load_template(self, template_name: str) -> Optional[str]:
        """
        从指定存储加载模板内容
        :param template_name: 模板唯一标识符
        :return: 模板字符串, 未找到返回None
        """
        pass

    @abstractmethod
    def save_template(self, template_name: str, content: str) -> bool:
        """
        保存或更新模板内容
        :param template_name: 模板标识符
        :param content: 模板文本
        :return: 操作是否成功
        """
        pass

    @abstractmethod
    def list_templates(self) -> List[str]:
        """
        列出所有可用模板名称
        :return: 模板名称列表
        """
        pass

    @abstractmethod
    def render_template(self, template_name: str, variables: Dict[str, Any]) -> Optional[str]:
        """
        渲染模板: 用变量替换占位符后返回最终prompt
        :param template_name: 模板标识符
        :param variables: 变量名与值的映射
        :return: 渲染后的字符串, 若模板不存在或渲染失败返回None
        """
        pass
    
    def reload_if_needed(self) -> bool:
        """
        根据配置检查是否需要重新加载所有模板(用于热更新)
        :return: 是否执行了重载
        """
        if not self.config.get("auto_reload", False):
            return False
        # 简化实现: 根据时间间隔判断; 生产环境建议监听文件变更
        # 此处仅骨架, 不实现实际文件监控
        self.logger.debug("auto_reload check - not implemented in skeleton")
        return False

    def clear_cache(self) -> None:
        """清空内部缓存"""
        self._cache.clear()
        self.logger.info("Template cache cleared.")

    def get_template_from_cache(self, template_name: str) -> Optional[str]:
        """从缓存获取模板(如果启用)"""
        if self.config.get("cache_enabled", True):
            return self._cache.get(template_name)
        return None

    def update_cache(self, template_name: str, content: str) -> None:
        """更新缓存"""
        if self.config.get("cache_enabled", True):
            self._cache[template_name] = content


# 基于文件系统的默认实现
class FilePromptDocumentManager(PromptDocumentManager):
    """基于文件系统的Prompt文档管理器, 模板存储为.txt文件"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        prompt_dir = Path(self.config.get("prompt_dir", "./prompts"))
        self.prompt_dir = prompt_dir
        # 确保目录存在
        try:
            prompt_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Failed to create prompt directory {prompt_dir}: {e}")
        self.logger.info(f"Prompt directory set to: {prompt_dir.resolve()}")

    def _template_file_path(self, template_name: str) -> Path:
        """获取模板文件的完整路径"""
        # 文件名规范: template_name.txt
        safe_name = template_name.replace("/", "_").replace("\\", "_")
        return self.prompt_dir / f"{safe_name}.txt"

    def load_template(self, template_name: str) -> Optional[str]:
        """从文件加载模板内容, 优先从缓存读取"""
        cached = self.get_template_from_cache(template_name)
        if cached is not None:
            self.logger.debug(f"Loading template '{template_name}' from cache.")
            return cached
        
        filepath = self._template_file_path(template_name)
        self.logger.debug(f"Attempting to load template from: {filepath}")
        try:
            if filepath.exists():
                content = filepath.read_text(encoding=self.config.get("default_encoding", "utf-8"))
                self.update_cache(template_name, content)
                self.logger.info(f"Template '{template_name}' loaded successfully.")
                return content
            else:
                self.logger.warning(f"Template file not found: {filepath}")
                return None
        except Exception as e:
            self.logger.error(f"Error loading template '{template_name}': {e}")
            return None

    def save_template(self, template_name: str, content: str) -> bool:
        """将模板内容写入文件, 同时更新缓存"""
        filepath = self._template_file_path(template_name)
        self.logger.info(f"Saving template '{template_name}' to {filepath}")
        try:
            filepath.write_text(content, encoding=self.config.get("default_encoding", "utf-8"))
            self.update_cache(template_name, content)
            return True
        except Exception as e:
            self.logger.error(f"Failed to save template '{template_name}': {e}")
            return False

    def list_templates(self) -> List[str]:
        """列出prompt_dir下所有.txt文件对应的模板名"""
        templates = []
        try:
            for f in self.prompt_dir.glob("*.txt"):
                if f.is_file():
                    name = f.stem
                    templates.append(name)
            self.logger.debug(f"Listed {len(templates)} templates.")
        except Exception as e:
            self.logger.error(f"Error listing templates: {e}")
        return templates

    def render_template(self, template_name: str, variables: Dict[str, Any]) -> Optional[str]:
        """使用Python字符串format进行简单占位符替换"""
        template_content = self.load_template(template_name)
        if template_content is None:
            self.logger.error(f"Template '{template_name}' not found, rendering aborted.")
            return None
        try:
            rendered = template_content.format(**variables)
            self.logger.info(f"Template '{template_name}' rendered successfully.")
            return rendered
        except KeyError as e:
            self.logger.error(f"Missing variable {e} for template '{template_name}'")
            return None
        except Exception as e:
            self.logger.error(f"Error rendering template '{template_name}': {e}")
            return None


# 自测部分
if __name__ == "__main__":
    # 配置日志输出到控制台
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    test_config = {
        "prompt_dir": "./test_prompts",
        "auto_reload": False
    }
    manager = FilePromptDocumentManager(config=test_config)
    
    # 测试保存模板
    manager.save_template("greeting", "Hello, {{name}}! Welcome to NovelOS.")
    manager.save_template("farewell", "Goodbye, {{name}}.")
    
    # 测试列出模板
    print("Available templates:", manager.list_templates())
    
    # 测试渲染模板
    result = manager.render_template("greeting", {"name": "Developer"})
    print("Rendered greeting:", result)
    
    result2 = manager.render_template("farewell", {"name": "Developer"})
    print("Rendered farewell:", result2)
    
    # 测试缺失变量
    result3 = manager.render_template("greeting", {"wrong_var": "test"})
    print("Rendered with missing variable:", result3)
    
    # 测试不存在的模板
    result4 = manager.render_template("missing", {})
    print("Rendered missing template:", result4)
    
    # 清理测试目录 (可选)
    import shutil
    try:
        shutil.rmtree("./test_prompts")
        print("Test prompts directory cleaned up.")
    except:
        pass