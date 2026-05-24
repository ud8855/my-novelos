import os
import logging
from typing import Any, Dict, Optional

class TXTExporter:
    """
    TXT导出器：负责将小说内容导出为纯文本文件。
    支持配置化（编码、章节标题格式等），可插拔。
    """

    DEFAULT_CONFIG = {
        "encoding": "utf-8",
        "include_chapter_titles": True,
        "chapter_title_prefix": "## ",
        "paragraph_separator": "\n\n",
        "line_ending": "\n",
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None, logger: Optional[logging.Logger] = None):
        """
        初始化导出器
        :param config: 自定义配置字典，将与默认配置合并
        :param logger: 外部日志记录器，若未提供则创建默认
        """
        self.config = self.DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)

        self.logger = logger or logging.getLogger(__name__)
        self._validate_config()

    def _validate_config(self):
        """校验配置合法性"""
        # 简单检查编码是否有效
        try:
            "test".encode(self.config["encoding"])
        except LookupError:
            self.logger.warning(f"无效的编码 {self.config['encoding']}，回退到 utf-8")
            self.config["encoding"] = "utf-8"
        if not isinstance(self.config["include_chapter_titles"], bool):
            self.config["include_chapter_titles"] = True
            self.logger.warning("include_chapter_titles 应为布尔值，已重置为 True")

    def export(self, novel_content: Any, output_path: str) -> bool:
        """
        导出小说内容到 TXT 文件
        :param novel_content: 小说内容，预期为章节列表（List[Dict]）或纯文本
                            章节字典格式：{"title": str, "content": str (段落列表或文本)}
        :param output_path: 输出文件路径
        :return: 导出成功返回 True，否则 False
        """
        try:
            self.logger.info(f"开始导出 TXT 到 {output_path}")
            text = self._build_text(novel_content)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, 'w', encoding=self.config["encoding"]) as f:
                f.write(text)
            self.logger.info("导出成功")
            return True
        except Exception as e:
            self.logger.error(f"导出失败: {str(e)}", exc_info=True)
            return False

    def _build_text(self, novel_content: Any) -> str:
        """
        将小说内容转换为纯文本字符串
        :param novel_content: 原始内容，支持两种格式：
            1. 章节列表：[{"title": "第一章", "content": ["段落1", "段落2"]}, ...]
            2. 字符串：直接作为文本
        :return: 构建好的文本
        """
        if isinstance(novel_content, str):
            return novel_content
        if isinstance(novel_content, list):
            parts = []
            for chapter in novel_content:
                if self.config["include_chapter_titles"]:
                    title = chapter.get("title", "")
                    if title:
                        parts.append(self.config["chapter_title_prefix"] + title)
                content = chapter.get("content", "")
                if isinstance(content, list):
                    # 段落列表
                    parts.append(self.config["paragraph_separator"].join(content))
                elif isinstance(content, str):
                    parts.append(content)
                else:
                    self.logger.warning(f"未知的章节内容类型: {type(content)}")
                # 章节间加空行
                parts.append("")  # 空行作为章节分隔
            return self.config["line_ending"].join(parts).strip()
        else:
            self.logger.error("不支持的 novel_content 类型，仅支持 str 或 List[Dict]")
            return ""

def self_test():
    """自测函数：演示基本用法"""
    # 创建导出器
    exporter = TXTExporter()
    # 模拟小说内容（章节列表）
    sample_novel = [
        {"title": "第一章 开端", "content": ["这是一个测试段落。", "这是第二段落。"]},
        {"title": "第二章 发展", "content": "另一章的内容，直接为字符串。\n换行在这里。"},
    ]
    output_file = "./test_export.txt"
    success = exporter.export(sample_novel, output_file)
    if success:
        print(f"测试导出成功，请查看 {output_file}")
        # 可选：读取并打印前 200 字符
        with open(output_file, 'r', encoding='utf-8') as f:
            print("文件内容预览：")
            print(f.read()[:200])
    else:
        print("导出失败")

if __name__ == "__main__":
    # 配置日志，避免自测时无输出
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    self_test()