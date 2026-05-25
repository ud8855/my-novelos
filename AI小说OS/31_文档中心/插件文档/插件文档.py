"""
模块：插件文档 (Plugin Documentation)
所属层：文档中心（31_文档中心）
依赖：配置管理模块、日志模块（均为本层或公共层）
被调用：UI层、Agent层需要获取插件文档时调用
功能：根据插件元数据生成标准化的操作文档，支持多格式输出（html, markdown等），可插拔启用

设计原则：
- 单一职责：仅负责插件文档的生成与查询，不涉及插件管理或执行
- 可插拔：通过配置项 ENABLE_PLUGIN_DOC 控制启用/禁用
- 配置化：所有输出模板、格式、路径等均可配置
- 中文注释/英文标识符
"""

import logging
import json
import os
from typing import Dict, Any, List, Optional

# ------------------- 日志配置 -------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # 实际使用时从总配置读取

# ------------------- 可插拔配置 -------------------
DEFAULT_CONFIG = {
    "ENABLE_PLUGIN_DOC": True,               # 是否启用插件文档生成
    "OUTPUT_FORMAT": "markdown",             # 默认输出格式：html, markdown, json
    "TEMPLATE_DIR": "./templates/plugin_doc",# 文档模板目录
    "OUTPUT_DIR": "./docs/plugins",          # 生成文档存放目录
    "MAX_DESC_LENGTH": 500,                  # 描述最大长度
    "INCLUDE_EXAMPLES": True,                 # 是否包含示例
}

class PluginDocumenter:
    """
    插件文档生成器
    负责根据插件信息生成标准化文档，支持热插拔和配置驱动
    """
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化文档生成器
        :param config: 自定义配置，若未提供则使用默认配置
        """
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)

        # 检查是否启用
        if not self.config.get("ENABLE_PLUGIN_DOC", True):
            logger.info("插件文档模块已被配置为禁用")
            self.enabled = False
        else:
            self.enabled = True
            # 确保输出目录存在
            output_dir = self.config["OUTPUT_DIR"]
            os.makedirs(output_dir, exist_ok=True)
            logger.info("插件文档模块已启用，输出目录: %s", output_dir)

    def generate_documentation(self, plugin_info: Dict[str, Any], format: Optional[str] = None) -> str:
        """
        为单个插件生成文档内容（字符串形式）
        :param plugin_info: 插件元数据字典，需包含 name, version, description, author 等
        :param format: 输出格式，覆盖配置
        :return: 生成的文档字符串
        """
        if not self.enabled:
            logger.warning("插件文档模块未启用，返回空文档")
            return ""

        # 参数校验
        required_fields = ["name", "version", "description", "author"]
        for field in required_fields:
            if field not in plugin_info:
                raise ValueError(f"插件信息缺少必要字段: {field}")

        # 确定输出格式
        output_format = format or self.config["OUTPUT_FORMAT"]

        logger.info("开始生成插件文档: %s (格式: %s)", plugin_info.get("name"), output_format)

        # 根据格式调用对应的生成方法（骨架留空，具体实现待填充）
        doc_content = ""
        if output_format == "markdown":
            doc_content = self._generate_markdown(plugin_info)
        elif output_format == "html":
            doc_content = self._generate_html(plugin_info)
        elif output_format == "json":
            doc_content = json.dumps(plugin_info, ensure_ascii=False, indent=2)
        else:
            logger.error("不支持的输出格式: %s", output_format)
            raise ValueError(f"不支持的输出格式: {output_format}")

        # 裁剪描述长度（示例）
        if len(doc_content) > self.config["MAX_DESC_LENGTH"] * 10:  # 粗糙限制
            logger.warning("文档内容过长，可能需要进行裁剪")

        logger.info("插件文档生成完毕")
        return doc_content

    def save_documentation(self, plugin_info: Dict[str, Any], file_name: Optional[str] = None, format: Optional[str] = None) -> str:
        """
        生成并保存插件文档到文件
        :param plugin_info: 插件元数据
        :param file_name: 保存的文件名（不含后缀），默认使用插件名+版本
        :param format: 输出格式
        :return: 保存的完整文件路径
        """
        if not self.enabled:
            return ""

        doc = self.generate_documentation(plugin_info, format)
        if not doc:
            return ""

        # 默认文件名
        if not file_name:
            file_name = f"{plugin_info['name']}_v{plugin_info['version']}"

        output_format = format or self.config["OUTPUT_FORMAT"]
        suffix_map = {"markdown": ".md", "html": ".html", "json": ".json"}
        suffix = suffix_map.get(output_format, ".txt")
        file_path = os.path.join(self.config["OUTPUT_DIR"], f"{file_name}{suffix}")

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(doc)
            logger.info("文档已保存至: %s", file_path)
            return file_path
        except Exception as e:
            logger.exception("保存文档失败: %s", e)
            raise

    def batch_generate(self, plugin_list: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        批量生成多个插件的文档字符串，返回 {插件名: 文档内容} 的字典
        """
        if not self.enabled:
            return {}

        results = {}
        for p_info in plugin_list:
            try:
                doc = self.generate_documentation(p_info)
                results[p_info.get("name", "unnamed")] = doc
            except Exception as e:
                logger.error("生成插件 '%s' 文档时出错: %s", p_info.get("name"), e)
                results[p_info.get("name", "unnamed")] = f"生成失败: {e}"
        return results

    def _generate_markdown(self, info: Dict[str, Any]) -> str:
        """生成Markdown格式的文档（骨架）"""
        # 实际实现：使用模板渲染，可调用模型生成详细说明
        return f"""# {info.get('name')} 插件文档

**版本**: {info.get('version')}  
**作者**: {info.get('author')}  
**描述**: {info.get('description')}

## 功能说明
（待填充）

## 使用方法
（待填充）

## 示例
{'包含示例' if self.config.get('INCLUDE_EXAMPLES') else '（暂无）'}

## 配置参数
（待填充）

## 依赖
（待填充）

## 更新日志
（待填充）
"""

    def _generate_html(self, info: Dict[str, Any]) -> str:
        """生成HTML格式的文档（骨架）"""
        return f"""<!DOCTYPE html>
<html>
<head><title>{info.get('name')} 文档</title></head>
<body>
    <h1>{info.get('name')}</h1>
    <p><strong>版本:</strong> {info.get('version')}</p>
    <p><strong>作者:</strong> {info.get('author')}</p>
    <p>{info.get('description')}</p>
    <!-- 其它内容待扩展 -->
</body>
</html>"""


# ------------------- 自测模块 -------------------
if __name__ == "__main__":
    # 配置控制台日志输出
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 测试用插件信息
    test_plugin = {
        "name": "示例插件",
        "version": "1.0.0",
        "description": "这是一个用于测试的示例插件，提供了简单的文本处理功能。",
        "author": "测试团队",
        "category": "工具",
        "dependencies": [],
        "parameters": {"threshold": 0.7}
    }

    # 实例化文档生成器（使用默认配置，可覆盖）
    doc_generator = PluginDocumenter({"ENABLE_PLUGIN_DOC": True})

    if doc_generator.enabled:
        # 生成 Markdown 文档
        md_doc = doc_generator.generate_documentation(test_plugin, format="markdown")
        print("=== Markdown 文档 ===\n", md_doc)

        # 生成并保存 HTML 文档
        saved_path = doc_generator.save_documentation(test_plugin, format="html")
        print(f"\nHTML 文档已保存至: {saved_path}")

        # 批量生成测试
        batch_result = doc_generator.batch_generate([test_plugin])
        print("\n批量生成结果:", list(batch_result.keys()))
    else:
        print("插件文档模块已禁用，跳过自测")