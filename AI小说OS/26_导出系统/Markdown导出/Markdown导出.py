"""
Module: Markdown导出
Layer: 导出系统 (26_导出系统)
Dependencies: 无
Called by: 导出管理器 (26_导出系统/导出管理器.py) 或直接调用
Description: 将小说内容导出为 Markdown 格式文件。支持可插拔设计、配置化参数以及完整的日志记录。
"""

import json
import logging
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

# 初始化日志记录器
logger = logging.getLogger(__name__)


class BaseExporter(ABC):
    """导出器抽象基类，定义导出接口"""

    @abstractmethod
    def export(self, novel_data: Dict[str, Any], output_path: str, **kwargs) -> bool:
        """
        导出小说数据到指定文件路径
        Args:
            novel_data: 小说结构化数据字典
            output_path: 输出文件路径（包含文件名）
            **kwargs: 其他导出选项
        Returns:
            bool: 导出成功返回 True，失败返回 False
        """
        pass


class MarkdownExporter(BaseExporter):
    """Markdown 格式导出器，将小说内容转换为 Markdown 文件"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化导出器，加载配置
        Args:
            config: 可选的配置字典，支持以下键：
                - include_metadata (bool): 是否导出标题、作者等元信息，默认 True
                - chapter_level_offset (int): 章节标题额外层级偏移量，默认 0
        """
        self.config = config if config is not None else {}
        self.include_metadata = self.config.get("include_metadata", True)
        self.chapter_level_offset = self.config.get("chapter_level_offset", 0)
        logger.info("MarkdownExporter 初始化完成，配置: %s", self.config)

    def export(self, novel_data: Dict[str, Any], output_path: str, **kwargs) -> bool:
        """
        执行 Markdown 导出
        Args:
            novel_data: 包含 title, author, chapters 等字段的小说数据字典
            output_path: 目标 Markdown 文件路径
        Returns:
            bool: 导出结果
        """
        logger.info("开始导出 Markdown 文件: %s", output_path)
        try:
            # 构建 Markdown 文本
            md_content = self._build_markdown(novel_data)
            # 确保输出目录存在
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            # 写入文件
            output_file.write_text(md_content, encoding="utf-8")
            logger.info("Markdown 导出成功: %s", output_path)
            return True
        except Exception as e:
            logger.exception("Markdown 导出过程中发生异常")
            return False

    def _build_markdown(self, novel_data: Dict[str, Any]) -> str:
        """
        根据小说数据构建 Markdown 格式字符串
        Args:
            novel_data: 小说结构化数据
        Returns:
            str: 完整的 Markdown 内容
        """
        lines = []

        # ---- 元数据块 ----
        if self.include_metadata:
            title = novel_data.get("title", "Untitled")
            author = novel_data.get("author", "Unknown")
            lines.append(f"# {title}")
            lines.append(f"> 作者: {author}")
            lines.append("")  # 空行

        # ---- 章节块 ----
        chapters = novel_data.get("chapters", [])
        for idx, chapter in enumerate(chapters):
            # 章节标题
            title = chapter.get("title", f"第{idx+1}章")
            heading_level = 2 + self.chapter_level_offset  # 默认 ## 开头的章节
            lines.append(f"{'#' * heading_level} {title}")
            lines.append("")

            # 章节正文
            content = chapter.get("content", "")
            if isinstance(content, list):
                # 如果内容为段落列表，逐行添加
                lines.extend(content)
            else:
                lines.append(str(content))
            lines.append("")  # 章节之间空行

        return "\n".join(lines)


# 自测代码
if __name__ == "__main__":
    # 配置标准日志输出
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # 模拟小说数据
    sample_novel = {
        "title": "测试小说",
        "author": "NovelOS 框架",
        "chapters": [
            {
                "title": "第一章 初入江湖",
                "content": "少年背剑，走入雨夜。"
            },
            {
                "title": "第二章 风云再起",
                "content": [
                    "江湖中流传着一个预言。",
                    "每隔百年，星辰倒转。"
                ]
            }
        ]
    }

    # 实例化导出器（可传入自定义配置）
    exporter = MarkdownExporter(
        config={"include_metadata": True, "chapter_level_offset": 0}
    )

    # 执行导出
    output_path = "test_output.md"
    success = exporter.export(sample_novel, output_path)

    if success:
        print(f"导出成功，生成文件: {output_path}")
    else:
        print("导出失败，请检查日志。")