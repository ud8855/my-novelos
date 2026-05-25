# 文件路径: 31_文档中心/Runtime文档.py
# 层级: 文档中心 (31_文档中心)
# 依赖: 20_模型协同/, 21_API模型/ (若需调用模型), 配置中心, 日志中心
# 被调用: 其他模块需生成运行时文档时调用，例如运行时状态报告、Agent执行报告等
# 解决问题: 提供统一的运行时文档生成接口，支持配置化、插拔式文档模板
# 设计模式: 策略模式，模板可插拔；日志与配置依赖注入

import logging
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
# 假设有公共的配置和日志工具，本项目内可能需要导入
# from 00_系统配置.配置中心 import get_config
# from 00_系统配置.日志中心 import get_logger

class RuntimeDocConfig:
    """运行时文档生成配置"""
    def __init__(self, config_dict: Dict[str, Any] = None):
        self.config = config_dict or self._default_config()
    
    @staticmethod
    def _default_config() -> Dict[str, Any]:
        return {
            "output_dir": "./runtime_docs",
            "default_template": "standard",
            "enable_self_test": True,
            "model": {
                "provider": "openai",
                "model_name": "gpt-4o-mini",
                "temperature": 0.3
            },
            "templates_dir": "./templates",
            "enable_logging": True,
            "max_retries": 3
        }
    
    def get(self, key: str, default=None):
        return self.config.get(key, default)

class BaseDocTemplate:
    """文档模板基类，支持插拔"""
    def __init__(self, name: str, config: RuntimeDocConfig, logger: logging.Logger):
        self.name = name
        self.config = config
        self.logger = logger
    
    def generate(self, context: Dict[str, Any]) -> str:
        """生成文档内容，返回字符串"""
        raise NotImplementedError("Subclasses must implement generate()")

class StandardTemplate(BaseDocTemplate):
    """标准运行时文档模板"""
    def generate(self, context: Dict[str, Any]) -> str:
        # 示例模板，实际应根据context生成结构化文档
        self.logger.info(f"Generating standard runtime doc for context keys: {list(context.keys())}")
        doc = f"# Runtime Document\nGenerated at: {datetime.now().isoformat()}\n\n"
        doc += json.dumps(context, indent=2, ensure_ascii=False)
        return doc

class SummaryTemplate(BaseDocTemplate):
    """摘要型模板"""
    def generate(self, context: Dict[str, Any]) -> str:
        summary = context.get("summary", "No summary provided.")
        return f"## Runtime Summary\n{summary}"

class RuntimeDocGenerator:
    """运行时文档生成器，插拔式模板管理"""
    def __init__(self, config: Optional[RuntimeDocConfig] = None, logger: Optional[logging.Logger] = None):
        self.config = config or RuntimeDocConfig()
        self.logger = logger or self._setup_logger()
        self.templates: Dict[str, BaseDocTemplate] = {}
        self._register_default_templates()
    
    def _setup_logger(self) -> logging.Logger:
        """配置日志"""
        if not self.config.get("enable_logging", True):
            logger = logging.getLogger("RuntimeDoc")
            logger.addHandler(logging.NullHandler())
            return logger
        
        logger = logging.getLogger("RuntimeDoc")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def _register_default_templates(self):
        """注册默认模板"""
        self.register_template(StandardTemplate("standard", self.config, self.logger))
        self.register_template(SummaryTemplate("summary", self.config, self.logger))
        # 可加载外部模板
        self._load_external_templates()
    
    def _load_external_templates(self):
        """从配置的模板目录加载插件模板"""
        templates_dir = Path(self.config.get("templates_dir", "./templates"))
        if templates_dir.exists() and templates_dir.is_dir():
            for py_file in templates_dir.glob("*.py"):
                try:
                    # 这里简化处理，实际可以通过动态导入加载
                    self.logger.info(f"Found external template file: {py_file}")
                    # 真正实现需使用importlib
                except Exception as e:
                    self.logger.error(f"Error loading template {py_file}: {e}")
    
    def register_template(self, template: BaseDocTemplate):
        """注册新模板，实现插拔"""
        self.templates[template.name] = template
        self.logger.info(f"Registered template: {template.name}")
    
    def unregister_template(self, template_name: str):
        """移除模板"""
        if template_name in self.templates:
            del self.templates[template_name]
            self.logger.info(f"Unregistered template: {template_name}")
    
    def generate_doc(self, context: Dict[str, Any], template_name: Optional[str] = None) -> str:
        """
        根据上下文和模板生成文档
        :param context: 文档所需数据，可包含 'summary', 'events' 等
        :param template_name: 模板名称，默认使用配置中的 default_template
        :return: 生成的文档字符串
        """
        template_name = template_name or self.config.get("default_template", "standard")
        if template_name not in self.templates:
            self.logger.error(f"Template '{template_name}' not found. Available: {list(self.templates.keys())}")
            raise ValueError(f"Template '{template_name}' not registered.")
        
        template = self.templates[template_name]
        self.logger.info(f"Generating doc with template '{template_name}'")
        for attempt in range(self.config.get("max_retries", 3)):
            try:
                doc_content = template.generate(context)
                return doc_content
            except Exception as e:
                self.logger.warning(f"Attempt {attempt+1} failed with template '{template_name}': {e}")
                if attempt == self.config.get("max_retries", 3) - 1:
                    raise
        return ""  # unreachable
    
    def save_doc(self, content: str, filename: Optional[str] = None):
        """保存文档到文件"""
        output_dir = Path(self.config.get("output_dir", "./runtime_docs"))
        output_dir.mkdir(parents=True, exist_ok=True)
        if not filename:
            filename = f"runtime_doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = output_dir / filename
        filepath.write_text(content, encoding='utf-8')
        self.logger.info(f"Runtime document saved to {filepath}")
        return str(filepath)
    
    # 自测方法
    def self_test(self):
        """自测，验证基本功能"""
        self.logger.info("Starting self-test...")
        try:
            # 测试生成
            test_context = {"event": "system_start", "timestamp": datetime.now().isoformat(), "summary": "System booted successfully."}
            doc_standard = self.generate_doc(test_context, "standard")
            assert "Runtime Document" in doc_standard
            doc_summary = self.generate_doc(test_context, "summary")
            assert "Runtime Summary" in doc_summary
            assert "System booted" in doc_summary
            # 测试保存
            saved_path = self.save_doc(doc_standard, "self_test.md")
            assert Path(saved_path).exists()
            self.logger.info("Self-test passed.")
        except Exception as e:
            self.logger.error(f"Self-test failed: {e}")
            raise

# 如果直接运行本文件，执行自测
if __name__ == "__main__":
    # 模拟配置
    config_data = {
        "output_dir": "./test_runtime_docs",
        "templates_dir": "./templates",
        "enable_logging": True
    }
    config = RuntimeDocConfig(config_data)
    logger = logging.getLogger("RuntimeDocTest")
    logging.basicConfig(level=logging.INFO)
    generator = RuntimeDocGenerator(config=config, logger=logger)
    generator.self_test()
    print("Manual runtime doc generation test completed.")