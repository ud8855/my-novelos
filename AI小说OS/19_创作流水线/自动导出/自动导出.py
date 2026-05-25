"""
自动导出模块
功能：在创作流水线完成后，自动将生成内容导出为文件（如txt, epub等）。
所属层：19_创作流水线
依赖：无
被调用：创作流水线管理模块，在生成内容后调用。
"""
import os
import logging
from datetime import datetime

# 如果项目有自己的日志系统，可以使用统一的日志，这里简单配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('AutoExporter')

class AutoExporter:
    """
    自动导出器，负责将生成的小说内容导出到文件。
    """
    def __init__(self, config=None):
        """
        初始化自动导出器
        :param config: dict, 配置项，包括：
            - output_dir: 输出目录
            - export_format: 导出格式 (如 'txt')
            - auto_export: 是否自动导出 (bool)
            - encoding: 文件编码
        """
        self.config = config if config else {}
        self.output_dir = self.config.get('output_dir', './export')
        self.export_format = self.config.get('export_format', 'txt')
        self.auto_export = self.config.get('auto_export', True)
        self.encoding = self.config.get('encoding', 'utf-8')
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)

    def export(self, content, metadata=None):
        """
        导出内容到文件
        :param content: str, 要导出的文本内容
        :param metadata: dict, 元数据，如 {'title': '章节标题', 'chapter_index': 1}
        :return: 文件路径，如果成功；否则None
        """
        if not self.auto_export:
            logger.info("自动导出已关闭，跳过导出")
            return None

        if not content:
            logger.warning("导出内容为空，取消导出")
            return None

        try:
            file_path = self._get_output_path(metadata)
            self._write_file(content, file_path)
            logger.info(f"导出成功: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"导出失败: {e}")
            return None

    def _get_output_path(self, metadata=None):
        """
        根据元数据生成输出文件路径
        """
        # 生成文件名：使用标题 + 时间戳，确保唯一
        title = metadata.get('title', 'untitled') if metadata else 'untitled'
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_')).rstrip()
        file_name = f"{safe_title}_{timestamp}.{self.export_format}"
        return os.path.join(self.output_dir, file_name)

    def _write_file(self, text, path):
        """
        写入文本到文件
        """
        with open(path, 'w', encoding=self.encoding) as f:
            f.write(text)
        logger.debug(f"文件已写入: {path}")

# 模块级别自测
if __name__ == "__main__":
    print("自测 AutoExporter...")
    # 创建临时输出目录
    test_dir = "test_export_output"
    config = {
        'output_dir': test_dir,
        'export_format': 'txt',
        'auto_export': True,
        'encoding': 'utf-8'
    }
    exporter = AutoExporter(config)
    test_content = "这是一段测试内容，用于验证自动导出功能。\n第二行内容。"
    metadata = {'title': '测试章节', 'chapter_index': 1}
    
    result_path = exporter.export(test_content, metadata)
    if result_path:
        # 检查文件是否存在并读取内容
        assert os.path.exists(result_path), "导出文件不存在"
        with open(result_path, 'r', encoding='utf-8') as f:
            read_content = f.read()
            assert read_content == test_content, "内容不匹配"
        print(f"自测通过，文件保存在: {result_path}")
        # 清理
        os.remove(result_path)
        os.rmdir(test_dir)
    else:
        print("自测失败：没有生成文件")