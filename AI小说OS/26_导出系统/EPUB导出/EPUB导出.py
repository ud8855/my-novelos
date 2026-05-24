from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

# 假设存在一个统一的导出插件基类，可插拔设计
# 实际项目中此基类可能放置在公共接口层，此处简化直接定义
class BaseExportPlugin:
    """导出插件基类，所有导出格式均需实现此接口"""
    plugin_type = "export"
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(self.__class__.__name__)

    def validate_input(self, data: Any) -> bool:
        """验证输入数据有效性，子类必须重写"""
        raise NotImplementedError

    def export(self, data: Any, output_path: str, **kwargs) -> str:
        """执行导出操作，返回最终文件路径，子类必须重写"""
        raise NotImplementedError

    def get_format_name(self) -> str:
        """返回导出格式标识，如 'epub'"""
        raise NotImplementedError


class EPUBExporter(BaseExportPlugin):
    """
    EPUB 电子书导出模块
    负责将内部小说数据结构转换为符合 EPUB3 标准的电子书文件。
    模块职责：仅处理 EPUB 特定的打包与元数据生成，不涉及业务逻辑。
    
    依赖：无跨层依赖，可通过注入小说内容数据使用。
    被调用：导出服务调度器（位于 26_导出系统 统一出口）。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化 EPUB 导出器

        :param config: 可选的配置字典，用于覆盖默认设置
                       支持字段：
                         - temp_dir: 临时文件目录 (默认: system temp)
                         - cover_path: 封面图片路径
                         - creator: 作者/创作者字段
                         - publisher: 出版社字段
                         - rights: 版权信息
                         - language: 语言代码 (默认: zh-CN)
                         - css_custom: 自定义 CSS 文件路径
                         - split_level: 分章级别 (chapter/scene)
        """
        super().__init__(config)
        # 默认配置
        self.default_config = {
            "temp_dir": None,
            "cover_path": None,
            "creator": "NovelOS",
            "publisher": "NovelOS",
            "rights": "All rights reserved",
            "language": "zh-CN",
            "css_custom": None,
            "split_level": "chapter",
        }
        # 合并配置
        self._merged_config = {**self.default_config, **config} if config else self.default_config
        self.logger.info("EPUBExporter initialized with config: %s", self._merged_config)
        # 可插拔：可以在此注册额外的插件或钩子，例如元数据增强钩子
        self._hooks: Dict[str, callable] = {}

    def get_format_name(self) -> str:
        return "epub"

    def validate_input(self, data: Any) -> bool:
        """
        验证小说数据结构是否满足 EPUB 生成要求
        预期 data 为 dict，包含:
            - title: str 书名
            - author: str 作者
            - chapters: list[dict] 章节列表，每节包含 title, content
            - metadata: dict (可选) 其他元数据
        """
        if not isinstance(data, dict):
            self.logger.error("Invalid input type, expected dict, got %s", type(data))
            return False
        if "title" not in data or "chapters" not in data:
            self.logger.error("Missing required keys: title and chapters")
            return False
        if not isinstance(data["chapters"], list):
            self.logger.error("Chapters must be a list")
            return False
        self.logger.info("Input data validated successfully.")
        return True

    def export(self, data: Any, output_path: str, **kwargs) -> str:
        """
        执行 EPUB 导出主流程

        :param data: 小说数据结构
        :param output_path: 输出文件路径（包含文件名，扩展名为 .epub）
        :param kwargs: 额外参数，可覆盖配置
        :return: 最终生成的文件绝对路径
        """
        self.logger.info("Starting EPUB export to %s", output_path)
        try:
            # 1. 验证输入
            if not self.validate_input(data):
                raise ValueError("Input data validation failed")

            # 2. 准备临时工作目录
            import tempfile
            temp_dir = self._merged_config.get("temp_dir") or tempfile.mkdtemp()
            self.logger.debug("Using temp directory: %s", temp_dir)

            # 3. 生成 EPUB 内部文件结构 (骨架，基于真实库时会完善)
            #    此处模拟生成 content.opf, toc.ncx, 各章节 xhtml 等
            self._generate_mimetype(temp_dir)
            self._generate_container_xml(temp_dir)
            self._generate_content_opf(data, temp_dir)
            self._generate_nav_xhtml(data, temp_dir)
            self._generate_chapters_xhtml(data, temp_dir)

            # 4. 打包为 epub (zip 无压缩 mimetype 特殊处理)
            final_path = self._pack_epub(temp_dir, output_path)

            # 5. 清理临时文件 (如果未设置外部临时目录)
            if not self._merged_config.get("temp_dir"):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                self.logger.debug("Temporary directory cleaned up.")

            self.logger.info("EPUB export completed successfully: %s", final_path)
            return final_path

        except Exception as e:
            self.logger.exception("EPUB export failed")
            raise

    # ---------- 内部生成方法 (骨架，实际需使用专用库如 ebooklib) ----------
    def _generate_mimetype(self, temp_dir: str):
        """写入 mimetype 文件 (application/epub+zip)"""
        mime_path = Path(temp_dir) / "mimetype"
        with open(mime_path, "w", encoding="utf-8") as f:
            f.write("application/epub+zip")
        self.logger.debug("mimetype file created.")

    def _generate_container_xml(self, temp_dir: str):
        """生成 META-INF/container.xml"""
        meta_dir = Path(temp_dir) / "META-INF"
        meta_dir.mkdir(exist_ok=True)
        container_content = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
   <rootfiles>
      <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
   </rootfiles>
</container>'''
        with open(meta_dir / "container.xml", "w", encoding="utf-8") as f:
            f.write(container_content)
        self.logger.debug("container.xml created.")

    def _generate_content_opf(self, data: dict, temp_dir: str):
        """
        生成 OEBPS/content.opf 文件，包含元数据与清单
        实际应使用模板引擎或 xml 库，这里仅骨架示意
        """
        oebps_dir = Path(temp_dir) / "OEBPS"
        oebps_dir.mkdir(exist_ok=True)
        title = data.get("title", "Untitled")
        creator = self._merged_config.get("creator", "Unknown")
        # 简化 OPF 骨架
        opf_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="book-id" version="3.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>{creator}</dc:creator>
    <dc:language>{self._merged_config.get("language", "zh-CN")}</dc:language>
    <dc:identifier id="book-id">urn:uuid:{self._generate_uuid()}</dc:identifier>
  </metadata>
  <manifest>
    <item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
    <!-- 章节项将在实际实现中动态生成 -->
  </manifest>
  <spine>
    <itemref idref="nav"/>
  </spine>
</package>'''
        with open(oebps_dir / "content.opf", "w", encoding="utf-8") as f:
            f.write(opf_content)
        self.logger.debug("content.opf created.")

    def _generate_nav_xhtml(self, data: dict, temp_dir: str):
        """生成导航文档 nav.xhtml"""
        oebps_dir = Path(temp_dir) / "OEBPS"
        nav_content = '''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head><title>Navigation</title></head>
<body>
  <nav epub:type="toc">
    <ol>
      <!-- 章节列表将由实际数据填充 -->
    </ol>
  </nav>
</body>
</html>'''
        with open(oebps_dir / "nav.xhtml", "w", encoding="utf-8") as f:
            f.write(nav_content)
        self.logger.debug("nav.xhtml created.")

    def _generate_chapters_xhtml(self, data: dict, temp_dir: str):
        """生成每个章节的 XHTML 文件（骨架）"""
        oebps_dir = Path(temp_dir) / "OEBPS"
        chapters = data.get("chapters", [])
        for i, chapter in enumerate(chapters):
            chap_id = f"chapter_{i+1}"
            chap_title = chapter.get("title", f"Chapter {i+1}")
            content = chapter.get("content", "")
            xhtml = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{chap_title}</title></head>
<body>
  <h1>{chap_title}</h1>
  <div>{content}</div>
</body>
</html>'''
            filename = f"{chap_id}.xhtml"
            with open(oebps_dir / filename, "w", encoding="utf-8") as f:
                f.write(xhtml)
            self.logger.debug(f"Generated {filename}")
        self.logger.info(f"Generated {len(chapters)} chapter XHTML files.")

    def _generate_uuid(self) -> str:
        """生成简单的 UUID 用于标识符"""
        import uuid
        return str(uuid.uuid4())

    def _pack_epub(self, temp_dir: str, output_path: str) -> str:
        """
        将临时目录内文件打包为合法 EPUB 文件 (zip 特殊处理 mimetype)
        实际生产中建议使用专用库如 zipfile，注意 mimetype 必须为 Stored 方式
        """
        import zipfile
        output_path = os.path.abspath(output_path)
        if not output_path.lower().endswith(".epub"):
            output_path += ".epub"

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as epub_zip:
            # 首先写入不压缩的 mimetype（EPUB规范要求）
            mimetype_path = os.path.join(temp_dir, "mimetype")
            if os.path.exists(mimetype_path):
                epub_zip.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)
            # 再写入其他内容
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    if file == "mimetype":
                        continue
                    arcname = os.path.relpath(full_path, temp_dir)
                    epub_