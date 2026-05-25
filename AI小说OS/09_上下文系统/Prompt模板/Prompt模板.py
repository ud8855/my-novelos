import logging
import os
import json
from typing import Dict, Optional, Any

# 配置化：模板配置（可从外部注入或读取环境变量）
DEFAULT_TEMPLATE_DIR = os.environ.get("PROMPT_TEMPLATE_DIR", "./templates/prompts")
DEFAULT_TEMPLATE_EXT = ".json"


class PromptTemplateManager:
    """
    Prompt模板管理器
    职责：加载、存储、检索、渲染Prompt模板
    可插拔：通过配置指定模板存储方式（文件/数据库），可替换模板引擎
    """

    def __init__(self, template_dir: Optional[str] = None):
        """
        初始化管理器
        :param template_dir: 模板文件目录，若为None则使用默认配置
        """
        self._templates: Dict[str, str] = {}  # name -> template_string
        self.template_dir = template_dir or DEFAULT_TEMPLATE_DIR
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"PromptTemplateManager initialized with dir={self.template_dir}")

    def load_templates(self, directory: Optional[str] = None) -> None:
        """
        从指定目录加载所有JSON格式的模板文件
        每个文件应包含一个JSON对象，键为模板名，值为模板字符串
        :param directory: 模板目录，若为None则使用实例属性
        """
        path = directory or self.template_dir
        if not os.path.isdir(path):
            self.logger.warning(f"Template directory does not exist: {path}")
            return

        for filename in os.listdir(path):
            if filename.endswith(DEFAULT_TEMPLATE_EXT):
                file_path = os.path.join(path, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            self._templates.update(data)
                            self.logger.debug(f"Loaded templates from {file_path}: {list(data.keys())}")
                except Exception as e:
                    self.logger.error(f"Failed to load template file {file_path}: {e}")

    def add_template(self, name: str, template: str) -> None:
        """
        手动添加或覆盖一个模板
        :param name: 模板唯一标识
        :param template: 模板字符串，包含占位符如 {variable}
        """
        self._templates[name] = template
        self.logger.debug(f"Template added: {name}")

    def remove_template(self, name: str) -> bool:
        """
        移除指定模板
        :param name: 模板名
        :return: 是否成功移除
        """
        if name in self._templates:
            del self._templates[name]
            self.logger.debug(f"Template removed: {name}")
            return True
        self.logger.warning(f"Attempt to remove non-existent template: {name}")
        return False

    def get_template(self, name: str) -> Optional[str]:
        """
        获取模板字符串
        :param name: 模板名
        :return: 模板字符串或None
        """
        template = self._templates.get(name)
        if template is None:
            self.logger.warning(f"Template not found: {name}")
        return template

    def render(self, name: str, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        使用上下文渲染模板
        :param name: 模板名
        :param context: 变量上下文字典
        :return: 渲染后的字符串或None（若模板不存在）
        """
        template = self.get_template(name)
        if template is None:
            return None
        context = context or {}
        try:
            rendered = template.format(**context)
            self.logger.debug(f"Rendered template '{name}' with context {context}")
            return rendered
        except KeyError as e:
            self.logger.error(f"Missing key in template context: {e}")
            # 可扩展：支持默认值或异常恢复策略
            return None
        except Exception as e:
            self.logger.error(f"Failed to render template '{name}': {e}")
            return None

    def list_templates(self) -> list:
        """返回所有已加载的模板名"""
        return list(self._templates.keys())


# 自测代码
if __name__ == "__main__":
    # 配置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # 测试管理器
    mgr = PromptTemplateManager()
    # 添加测试模板
    mgr.add_template("greeting", "Hello, {name}! Welcome to NovelOS.")
    mgr.add_template("chapter_start", "Chapter {number}: {title}")

    # 渲染测试
    rendered1 = mgr.render("greeting", {"name": "Alice"})
    assert rendered1 == "Hello, Alice! Welcome to NovelOS."
    print("Test 1 passed:", rendered1)

    rendered2 = mgr.render("chapter_start", {"number": 1, "title": "The Beginning"})
    assert rendered2 == "Chapter 1: The Beginning"
    print("Test 2 passed:", rendered2)

    # 测试缺少模板
    rendered3 = mgr.render("unknown", {})
    assert rendered3 is None
    print("Test 3 passed: None returned for missing template.")

    # 测试模板列表
    print("Loaded templates:", mgr.list_templates())

    # 测试文件加载（如果存在默认目录）
    mgr.load_templates()
    print("After load_templates:", mgr.list_templates())