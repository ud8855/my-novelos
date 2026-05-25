"""
部署文档生成器模块

职责：
- 根据系统配置和运行时信息生成标准化的部署文档
- 支持多种输出格式（Markdown/HTML等）
- 可插拔设计，通过继承或配置切换生成策略
- 所有操作配置化、日志记录、异常恢复

依赖：
- 配置管理模块（20_模型协同/配置 或全局配置）
- 日志模块（标准库 logging）
- 文件系统工具（内置）

被调用：
- 文档中心主控（31_文档中心/文档中心协调器）
- 部署工具链（如CI/CD脚本）
"""

import logging
import os
from typing import Dict, Any, Optional

# 配置日志
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())  # 避免未配置时无输出，实际环境由上层配置


class DeploymentDocGenerator:
    """
    部署文档生成器基类
    遵循可插拔原则：子类可重写 _build_content 实现具体文档内容生成逻辑
    """

    # 默认配置项（可被子类覆盖或通过实例化时传入的配置字典修改）
    DEFAULT_CONFIG = {
        "output_dir": "docs/deployment",
        "output_format": "md",  # md, html, rst
        "template_path": "templates/deployment_template.md",
        "doc_title": "NovelOS 部署文档",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化生成器

        Args:
            config: 生成器配置字典，用于覆盖默认配置
        """
        self.config = self.DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        logger.info("部署文档生成器初始化完成，配置: %s", self.config)

    def generate(self, output_path: Optional[str] = None) -> str:
        """
        生成部署文档并写入文件

        Args:
            output_path: 输出文件路径，若未提供则使用配置的默认路径

        Returns:
            生成的文档文件完整路径

        Raises:
            IOError: 文件写入失败时抛出
        """
        if output_path is None:
            output_dir = self.config["output_dir"]
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"deployment_doc.{self.config['output_format']}")

        logger.info("开始生成部署文档，输出路径: %s", output_path)

        try:
            content = self._build_content()
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("部署文档生成成功，保存至: %s", output_path)
            return output_path
        except Exception as e:
            logger.exception("部署文档生成失败: %s", e)
            raise

    def _build_content(self) -> str:
        """
        构建文档内容（骨架方法，子类需重写以提供实际内容）

        Returns:
            生成的文档字符串
        """
        # 默认返回基础模板内容，子类应重写此方法实现具体内容生成
        logger.debug("使用默认内容构建方法")
        return f"# {self.config['doc_title']}\n\n> 部署文档生成器默认输出，请覆盖 _build_content 方法实现具体内容。\n"


# 自测代码
if __name__ == "__main__":
    # 配置临时日志输出到控制台
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("=" * 50)
    print("部署文档生成器自测")
    print("=" * 50)

    # 测试1: 使用默认配置生成文档
    print("\n[测试1] 默认配置生成文档...")
    gen = DeploymentDocGenerator()
    output_file = gen.generate("test_deployment_doc.md")
    print(f"文档已生成: {output_file}")
    with open(output_file, "r", encoding="utf-8") as f:
        print("内容预览:")
        print(f.read()[:200])

    # 测试2: 覆盖配置生成HTML文档
    print("\n[测试2] 自定义配置生成HTML文档...")
    custom_config = {
        "output_format": "html",
        "doc_title": "NovelOS 部署指南"
    }
    gen2 = DeploymentDocGenerator(custom_config)
    output_file2 = gen2.generate("test_deployment_doc.html")
    print(f"文档已生成: {output_file2}")

    # 清理测试文件（可选，保留以便检查）
    # os.remove(output_file)
    # os.remove(output_file2)

    print("\n自测完成。")