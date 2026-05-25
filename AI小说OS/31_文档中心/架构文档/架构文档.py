# -*- coding: utf-8 -*-
"""
NovelOS - 架构文档生成模块

模块位置：31_文档中心/架构文档/架构文档.py
功能：根据系统架构元数据生成架构文档（支持多种输出格式）。
遵循：可插拔、配置化、日志、中文注释/英文标识符。

当前阶段：定义接口与协议，实现基础骨架。
"""

import logging
from typing import Dict, Any, Optional

# 配置类
class ArchDocConfig:
    """架构文档生成配置"""
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        # 默认配置
        self.output_format = "markdown"  # 输出格式：markdown, html, pdf等
        self.include_diagrams = True     # 是否包含图表
        self.template_path = None        # 模板路径
        # 从传入配置更新
        if config:
            self.__dict__.update(config)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

# 日志
logger = logging.getLogger("novelos.archdoc")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(name)s %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# 架构文档生成器
class ArchitectureDocGenerator:
    """架构文档生成器，根据系统架构元数据生成文档"""
    
    def __init__(self, config: Optional[ArchDocConfig] = None):
        self.config = config if config else ArchDocConfig()
        logger.info("ArchitectureDocGenerator initialized with config: %s", self.config.to_dict())

    def generate(self, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        生成架构文档。
        
        参数:
            metadata: 架构元数据，例如系统组件、依赖关系、数据流等。
                      如果为None，则尝试从系统注册表获取（当前阶段返回占位文档）。
        
        返回:
            生成的文档字符串。
        """
        logger.info("Starting architecture document generation")
        if metadata is None:
            # 占位：未来从系统元数据服务获取
            metadata = self._get_placeholder_metadata()
        # 根据配置渲染文档
        doc = self._render_document(metadata)
        logger.info("Architecture document generation completed")
        return doc

    def _get_placeholder_metadata(self) -> Dict[str, Any]:
        """获取占位元数据（当前阶段）"""
        return {
            "system_name": "NovelOS",
            "version": "0.1.0",
            "layers": [
                {"name": "10_核心引擎", "purpose": "系统核心运行时"},
                {"name": "20_模型协同", "purpose": "模型协同层"},
                {"name": "21_API模型", "purpose": "API模型封装"},
                {"name": "30_服务层", "purpose": "业务服务"},
                {"name": "31_文档中心", "purpose": "文档生成与管理"},
            ],
            "data_flow": "UI -> Runtime -> Agent -> Model -> Response",
            "components": []
        }

    def _render_document(self, metadata: Dict[str, Any]) -> str:
        """根据元数据和配置渲染文档"""
        if self.config.output_format == "markdown":
            return self._render_markdown(metadata)
        else:
            # 其他格式暂未实现
            logger.warning(f"Output format '{self.config.output_format}' not fully supported, falling back to plain text")
            return str(metadata)

    def _render_markdown(self, metadata: Dict[str, Any]) -> str:
        """渲染Markdown格式的架构文档"""
        lines = []
        lines.append(f"# {metadata.get('system_name', 'NovelOS')} 架构文档")
        lines.append(f"版本: {metadata.get('version', 'N/A')}\n")
        lines.append("## 系统分层\n")
        for layer in metadata.get("layers", []):
            lines.append(f"- **{layer['name']}**: {layer['purpose']}")
        lines.append(f"\n## 数据流\n{metadata.get('data_flow', 'N/A')}\n")
        lines.append("---")
        lines.append("*此文档由架构文档生成器自动生成（骨架版本）*")
        return "\n".join(lines)

# 自测
if __name__ == "__main__":
    # 测试配置
    test_config = ArchDocConfig({
        "output_format": "markdown",
        "include_diagrams": False
    })
    # 实例化生成器
    generator = ArchitectureDocGenerator(test_config)
    # 生成文档
    doc = generator.generate()
    print(doc)
    logger.info("Self-test completed.")