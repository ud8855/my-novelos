from __future__ import annotations
import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from configparser import ConfigParser

# ============================================================
# 模块路径: 31_文档中心/API文档
# 层级说明: 文档中心层，负责系统API文档的生成、结构化管理
# 依赖: 无强依赖，可独立运行
# 被调用: 可由系统管理模块、定时任务或手动触发
# 解决问题: 根据系统已注册的API接口，自动生成标准格式的API文档
# ============================================================

class APIDocGenerator(ABC):
    """API文档生成器抽象基类，实现可插拔的生成策略"""

    @abstractmethod
    def generate(self, api_info: Dict[str, Any]) -> str:
        """根据API信息生成文档内容，返回文档字符串"""
        ...

    @abstractmethod
    def output_format(self) -> str:
        """返回生成器支持的文件格式，如 'json', 'markdown', 'html'"""
        ...

class JSONDocGenerator(APIDocGenerator):
    """JSON格式API文档生成器"""

    def generate(self, api_info: Dict[str, Any]) -> str:
        return json.dumps(api_info, ensure_ascii=False, indent=2)

    def output_format(self) -> str:
        return "json"

class MarkdownDocGenerator(APIDocGenerator):
    """Markdown格式API文档生成器"""

    def generate(self, api_info: Dict[str, Any]) -> str:
        # 简化的Markdown生成示例
        lines = [f"# {api_info.get('name', 'API Endpoint')}"]
        lines.append(f"**Method:** {api_info.get('method', 'GET')}")
        lines.append(f"**Path:** {api_info.get('path', '/')}")
        lines.append(f"**Description:** {api_info.get('description', '')}")
        if 'parameters' in api_info:
            lines.append("## Parameters")
            for param in api_info['parameters']:
                lines.append(f"- `{param['name']}` ({param['type']}): {param.get('description', '')}")
        if 'response' in api_info:
            lines.append("## Response Example")
            lines.append("```json")
            lines.append(json.dumps(api_info['response'], indent=2, ensure_ascii=False))
            lines.append("```")
        return "\n".join(lines)

    def output_format(self) -> str:
        return "md"

class APIDocumenter:
    """
    API文档核心类，负责加载配置、管理生成器、收集API信息并生成文档。
    支持热插拔生成器，通过配置指定输出格式和路径。
    """

    def __init__(self, config_path: Optional[str] = None):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = self._load_config(config_path or "api_doc_config.ini")
        self._setup_logging()
        self.generators: Dict[str, APIDocGenerator] = {}
        self._register_default_generators()

    def _load_config(self, config_path: str) -> ConfigParser:
        config = ConfigParser()
        # 如果文件不存在则使用默认配置
        if Path(config_path).exists():
            config.read(config_path, encoding='utf-8')
        else:
            self.logger.warning(f"配置文件 {config_path} 不存在，使用默认配置")
            config.read_dict({
                'DEFAULT': {
                    'output_dir': './api_docs',
                    'default_format': 'json',
                    'log_level': 'INFO',
                    'include_internal': 'False'
                }
            })
        return config

    def _setup_logging(self):
        level = getattr(logging, self.config.get('DEFAULT', 'log_level', fallback='INFO'), logging.INFO)
        logging.basicConfig(level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger.setLevel(level)

    def _register_default_generators(self):
        """注册内置的文档生成器"""
        self.register_generator(JSONDocGenerator())
        self.register_generator(MarkdownDocGenerator())

    def register_generator(self, generator: APIDocGenerator):
        """注册新的文档生成器，实现热插拔"""
        fmt = generator.output_format()
        self.generators[fmt] = generator
        self.logger.info(f"已注册生成器: {generator.__class__.__name__} (格式: {fmt})")

    def unregister_generator(self, fmt: str):
        """移除生成器"""
        if fmt in self.generators:
            del self.generators[fmt]
            self.logger.info(f"已移除格式为 {fmt} 的生成器")

    def collect_api_info(self) -> List[Dict[str, Any]]:
        """
        收集系统内所有API的信息。
        此处为示例实现，实际可能从路由注册表、反射或配置文件获取。
        """
        # 示例API数据，实际应动态获取
        apis = [
            {
                "name": "Create Novel",
                "method": "POST",
                "path": "/api/novel/create",
                "description": "创建一本新小说",
                "parameters": [
                    {"name": "title", "type": "string", "description": "小说标题"},
                    {"name": "genre", "type": "string", "description": "小说类型"}
                ],
                "response": {"id": "novel_123", "status": "created"}
            },
            {
                "name": "Generate Chapter",
                "method": "POST",
                "path": "/api/chapter/generate",
                "description": "根据提示生成章节内容",
                "parameters": [
                    {"name": "prompt", "type": "string", "description": "生成提示"}
                ],
                "response": {"content": "第一章内容..."}
            }
        ]
        self.logger.debug(f"收集到 {len(apis)} 个API接口")
        return apis

    def generate_documentation(self, fmt: Optional[str] = None) -> Dict[str, str]:
        """
        生成所有API的文档，返回 {格式: 文档内容} 的字典。
        如果未指定格式，则使用配置文件中的默认格式。
        """
        target_format = fmt or self.config.get('DEFAULT', 'default_format', fallback='json')
        generator = self.generators.get(target_format)
        if not generator:
            raise ValueError(f"不支持的文档格式: {target_format}，可用格式: {list(self.generators.keys())}")

        apis = self.collect_api_info()
        include_internal = self.config.getboolean('DEFAULT', 'include_internal', fallback=False)
        if not include_internal:
            # 过滤掉内部/调试接口（示例按名称过滤）
            apis = [api for api in apis if not api.get('internal', False)]

        docs = {}
        for api in apis:
            doc_str = generator.generate(api)
            docs[api['name']] = doc_str
            self.logger.debug(f"已生成 {api['name']} 的文档")

        return docs

    def save_documentation(self, fmt: Optional[str] = None):
        """生成文档并保存到文件"""
        output_dir = Path(self.config.get('DEFAULT', 'output_dir', fallback='./api_docs'))
        output_dir.mkdir(parents=True, exist_ok=True)

        target_format = fmt or self.config.get('DEFAULT', 'default_format', fallback='json')
        docs = self.generate_documentation(fmt=target_format)

        for name, content in docs.items():
            safe_name = name.replace(' ', '_').lower()
            file_path = output_dir / f"{safe_name}.{target_format}"
            file_path.write_text(content, encoding='utf-8')
            self.logger.info(f"文档已保存至: {file_path}")

        self.logger.info(f"所有API文档已生成至 {output_dir}")

# ============================================================
# 自测试代码
# ============================================================
if __name__ == "__main__":
    print("=== API文档模块自测开始 ===")
    # 创建实例（无配置文件则使用默认）
    docer = APIDocumenter()
    
    # 测试生成JSON文档
    print("测试生成JSON格式文档...")
    json_docs = docer.generate_documentation(fmt='json')
    for name, doc in json_docs.items():
        print(f"API: {name}")
        print(doc[:200])
        print("---")
    
    # 测试生成Markdown文档
    print("测试生成Markdown格式文档...")
    md_docs = docer.generate_documentation(fmt='md')
    for name, doc in md_docs.items():
        print(f"API: {name}")
        print(doc[:200])
        print("---")
    
    # 测试保存到文件
    print("测试保存文档到文件...")
    docer.save_documentation(fmt='json')
    docer.save_documentation(fmt='md')
    
    # 测试热插拔：动态注册新的生成器
    class HTMLDocGenerator(APIDocGenerator):
        def generate(self, api_info):
            return f"<html><body><h1>{api_info['name']}</h1></body></html>"
        def output_format(self):
            return "html"
    
    docer.register_generator(HTMLDocGenerator())
    html_docs = docer.generate_documentation(fmt='html')
    print("HTML文档示例:", list(html_docs.values())[0][:100])
    
    # 测试卸载生成器
    docer.unregister_generator('html')
    try:
        docer.generate_documentation(fmt='html')
    except ValueError as e:
        print(f"预期异常: {e}")
    
    print("=== 自测完成 ===")