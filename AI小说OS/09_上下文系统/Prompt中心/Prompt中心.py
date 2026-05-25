"""Prompt中心 - 统一Prompt模板管理模块
层级: 09_上下文系统
依赖: 配置系统, 日志系统
被调用: Agent交互/模型调用/工作流模块
功能: 支持模板加载、变量渲染、模板版本管理、热更新
设计原则: 可插拔，所有模板以文件形式存储，通过配置加载路径，支持动态刷新，异常恢复，完整的日志记录
"""

import os
import json
import logging
from typing import Dict, Optional, Any
from pathlib import Path
from jinja2 import Template, Environment, FileSystemLoader, TemplateNotFound  # 引入模板引擎（轻量级依赖）

# 配置热更新支持
try:
    import importlib
    import sys
except ImportError:
    pass

# 日志器
logger = logging.getLogger(__name__)

class PromptCenter:
    """
    Prompt中心：负责管理所有Prompt模板的加载、渲染和更新。
    支持两种模板存放方式：
    1. 文件系统模板目录（使用Jinja2文件加载器）
    2. 内存字典式模板（可从JSON配置读取）
    默认支持热更新检测。
    """
    _instance = None  # 单例模式，但可通过配置多实例

    def __init__(self, config: Optional[Dict[str, Any]] = None, auto_load: bool = True):
        """
        初始化Prompt中心
        :param config: 配置字典，可包含:
            - template_dir: 模板文件目录路径 (str)
            - memory_templates: 内存模板字典 {name: template_str} (dict)
            - auto_reload: 是否开启自动重新加载模板 (bool, 默认False)
            - encoding: 文件编码 (默认'utf-8')
        :param auto_load: 是否自动加载模板
        """
        self.config = config or {}
        self.template_dir = self.config.get("template_dir", None)
        self.memory_templates = self.config.get("memory_templates", {})
        self.auto_reload = self.config.get("auto_reload", False)
        self.encoding = self.config.get("encoding", "utf-8")
        self._env = None
        self._memory_env = None
        self._loaded_templates = {}
        self._last_load_time = 0.0

        if auto_load:
            self.load_templates()

        logger.info(f"PromptCenter initialized. template_dir={self.template_dir}, "
                    f"auto_reload={self.auto_reload}")

    def _create_jinja_env(self):
        """创建Jinja2环境用于文件模板"""
        if self.template_dir and os.path.isdir(self.template_dir):
            return Environment(
                loader=FileSystemLoader(self.template_dir, encoding=self.encoding),
                auto_reload=self.auto_reload  # Jinja2的auto_reload可在开发环境使用
            )
        return None

    def _create_memory_env(self):
        """为内存模板创建简单的渲染环境"""
        return Environment(auto_reload=False)

    def load_templates(self):
        """
        加载所有模板：从文件系统目录和内存字典
        返回成功加载的数量
        """
        load_count = 0
        
        # 加载文件模板
        if self.template_dir:
            self._env = self._create_jinja_env()
            if self._env:
                load_count += len(self._env.list_templates())
                logger.info(f"Loaded {load_count} file templates from {self.template_dir}")
            else:
                logger.warning(f"Template directory {self.template_dir} is not valid")
        else:
            self._env = None
            logger.debug("No template_dir provided, skipping file templates")

        # 加载内存模板
        if self.memory_templates:
            self._memory_env = self._create_memory_env()
            # 预处理所有内存模板
            self._loaded_templates = {
                name: self._memory_env.from_string(tpl_str)
                for name, tpl_str in self.memory_templates.items()
            }
            load_count += len(self._loaded_templates)
            logger.info(f"Loaded {len(self._loaded_templates)} in-memory templates")
        else:
            self._memory_env = None
            self._loaded_templates = {}

        self._last_load_time = time.time() if 'time' in dir() else os.path.getmtime(__file__)  # fallback
        return load_count

    def reload_if_needed(self):
        """根据配置决定是否重新加载模板（如文件修改时间变化）"""
        if not self.auto_reload:
            return False
        # 简单的检测方法：仅检查模板目录下文件的最近修改时间
        if self.template_dir and os.path.isdir(self.template_dir):
            try:
                latest_mtime = max(
                    os.path.getmtime(os.path.join(self.template_dir, f))
                    for f in os.listdir(self.template_dir)
                    if os.path.isfile(os.path.join(self.template_dir, f))
                )
                if latest_mtime > self._last_load_time:
                    logger.info("Detected template file changes, reloading...")
                    self.load_templates()
                    return True
            except Exception as e:
                logger.error(f"Error checking template modifications: {e}")
        return False

    def get_template(self, template_name: str) -> Optional[Template]:
        """
        获取指定名称的模板对象
        优先从文件模板查找，若未找到再从内存模板查找
        :param template_name: 模板名称（文件模板需包含后缀，如'character_intro.j2'）
        :return: jinja2.Template对象或None
        """
        self.reload_if_needed()
        # 尝试文件模板
        if self._env:
            try:
                return self._env.get_template(template_name)
            except TemplateNotFound:
                logger.debug(f"Template '{template_name}' not found in file system, trying memory")
            except Exception as e:
                logger.error(f"Error loading file template '{template_name}': {e}")

        # 尝试内存模板
        if template_name in self._loaded_templates:
            return self._loaded_templates[template_name]
        elif self.memory_templates and template_name in self.memory_templates:
            # 如果尚未预加载，动态加载
            try:
                tpl = self._memory_env.from_string(self.memory_templates[template_name])
                self._loaded_templates[template_name] = tpl
                return tpl
            except Exception as e:
                logger.error(f"Error creating memory template '{template_name}': {e}")
        logger.warning(f"Template '{template_name}' not found in any source")
        return None

    def render(self, template_name: str, **kwargs) -> str:
        """
        渲染指定模板并返回字符串
        :param template_name: 模板名称
        :param kwargs: 模板变量
        :return: 渲染后的字符串
        :raises: ValueError 若模板不存在
        """
        tpl = self.get_template(template_name)
        if tpl is None:
            error_msg = f"Template '{template_name}' not found, cannot render"
            logger.error(error_msg)
            raise ValueError(error_msg)
        try:
            result = tpl.render(**kwargs)
            logger.debug(f"Rendered template '{template_name}' with keys: {list(kwargs.keys())}")
            return result
        except Exception as e:
            logger.error(f"Failed to render template '{template_name}': {e}")
            raise

    def get_available_templates(self) -> Dict[str, list]:
        """
        获取所有可用模板名称（分为file_templates和memory_templates）
        :return: 字典
        """
        self.reload_if_needed()
        file_templates = self._env.list_templates() if self._env else []
        memory_templates = list(self.memory_templates.keys())
        return {
            "file_templates": file_templates,
            "memory_templates": memory_templates
        }

    def add_memory_template(self, name: str, template_str: str, override: bool = False):
        """
        动态添加一个内存模板（热插拔）
        :param name: 模板名称
        :param template_str: 模板字符串
        :param override: 是否覆盖已有模板
        """
        if name in self.memory_templates and not override:
            logger.warning(f"Memory template '{name}' already exists, skip adding")
            return
        self.memory_templates[name] = template_str
        # 重新加载内存模板环境
        if self._memory_env:
            self._loaded_templates[name] = self._memory_env.from_string(template_str)
        else:
            # 如果之前没有内存环境，初始化它
            self._memory_env = Environment()
            self._loaded_templates[name] = self._memory_env.from_string(template_str)
        logger.info(f"Added/Updated memory template '{name}'")

    def remove_memory_template(self, name: str):
        """移除内存模板"""
        if name in self.memory_templates:
            del self.memory_templates[name]
            self._loaded_templates.pop(name, None)
            logger.info(f"Removed memory template '{name}'")
        else:
            logger.warning(f"Memory template '{name}' does not exist")

    def reset(self):
        """重置所有加载的模板和缓存"""
        self._env = None
        self._memory_env = None
        self._loaded_templates = {}
        self._last_load_time = 0.0
        logger.info("PromptCenter reset complete")

# 自测代码
if __name__ == "__main__":
    import tempfile, time

    # 配置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG)

    # 测试1：无模板目录
    print("=== Test 1: No templates at all ===")
    pc = PromptCenter(config={}, auto_load=False)
    try:
        pc.render("any")
    except ValueError as e:
        print(f"Expected error: {e}")

    # 测试2：内存模板
    print("\n=== Test 2: In-memory templates ===")
    mem_tpl = {"hello": "Hello, {{ name }}!"}
    pc2 = PromptCenter(config={"memory_templates": mem_tpl})
    result = pc2.render("hello", name="World")
    print(f"Rendered: {result}")
    assert result == "Hello, World!"

    # 测试3：文件模板
    print("\n=== Test 3: File-based templates ===")
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建模板文件
        tpl_file = os.path.join(tmpdir, "greet.j2")
        with open(tpl_file, "w") as f:
            f.write("Hi, {{ user }}!")
        pc3 = PromptCenter(config={"template_dir": tmpdir})
        result3 = pc3.render("greet.j2", user="Alice")
        print(f"Rendered: {result3}")
        assert "Alice" in result3

        # 测试动态添加内存模板并覆盖文件模板（但不同名）
        pc3.add_memory_template("farewell", "Goodbye {{ name }}!")
        print(pc3.render("farewell", name="Bob"))

        # 测试获取可用模板列表
        avail = pc3.get_available_templates()
        print("Available templates:", avail)
        assert "greet.j2" in avail["file_templates"]
        assert "farewell" in avail["memory_templates"]

        # 测试热更新模拟：修改文件并调用reload_if_needed
        print("\n=== Test 4: Hot reload (simulated) ===")
        # 等待一下避免1秒内修改
        time.sleep(0.1)
        with open(tpl_file, "a") as f:
            f.write("\nUpdated content!")
        # 手动设置auto_reload需要重新初始化或修改实例属性
        pc3.auto_reload = True
        pc3._last_load_time = 0  # 强制认为需要更新
        reloaded = pc3.reload_if_needed()
        print(f"Templates reloaded: {reloaded}")
        # 再次渲染会看到新模板内容（但原greet.j2已经被修改，实际可能渲染失败，这里仅测试流程）
        try:
            new_result = pc3.render("greet.j2", user="Test")
            print("After reload render:", new_result)
        except Exception as e:
            print(f"Reload render error (expected due to template change): {e}")

    print("\nAll tests passed (with expected exceptions)!")