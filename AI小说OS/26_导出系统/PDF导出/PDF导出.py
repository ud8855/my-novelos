from pathlib import Path
import logging
import json
import sys
from typing import Optional, Any, Dict

# 导入配置管理（假设系统有统一的配置加载器，这里先简单自己实现）
try:
    from core.config_manager import load_config  # 假设系统全局配置
except ImportError:
    load_config = None

# 日志设置（可插拔：允许外部传入logger）
logger = logging.getLogger("PDFExporter")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    h = logging.StreamHandler()
    h.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    h.setFormatter(formatter)
    logger.addHandler(h)

class PDFExporter:
    """
    PDF导出器 - 负责将小说内容转换为PDF文件。
    属于26_导出系统层，依赖配置系统和日志系统，
    被导出调度器调用，解决PDF格式导出问题。
    
    特性：
    - 可插拔：实现统一的导出接口，可被导出管理器动态加载和替换。
    - 配置化：所有页面参数、字体、边距等通过配置文件加载。
    - 异常恢复：失败时记录日志并可回滚输出文件（待实现）。
    - 热更新：支持从配置中心动态更新参数（通过属性监听，待完善）。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, config_path: Optional[str] = None):
        """
        初始化PDF导出器。
        
        Args:
            config: 直接传入配置字典（优先级最高）。
            config_path: 配置文件路径，若未提供config则从文件加载。
        """
        self.config = config or {}
        if not self.config and config_path:
            self.config = self._load_config_from_file(config_path)
        elif not self.config:
            # 使用默认配置
            self.config = self._default_config()
        
        # 解析并设置关键参数
        self.page_size = self.config.get("page_size", "A4")
        self.margin_top = self.config.get("margin_top", 20)
        self.margin_bottom = self.config.get("margin_bottom", 20)
        self.margin_left = self.config.get("margin_left", 25)
        self.margin_right = self.config.get("margin_right", 25)
        self.font_name = self.config.get("font_name", "SimSun")
        self.font_size = self.config.get("font_size", 12)
        self.line_height = self.config.get("line_height", 1.5)
        self.output_dir = self.config.get("output_dir", "./output")
        
        logger.info(f"PDFExporter initialized with page_size={self.page_size}, font={self.font_name}")
    
    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """返回默认配置，避免依赖外部文件。"""
        return {
            "page_size": "A4",
            "margin_top": 20,
            "margin_bottom": 20,
            "margin_left": 25,
            "margin_right": 25,
            "font_name": "SimSun",
            "font_size": 12,
            "line_height": 1.5,
            "output_dir": "./output",
            "cover_page": True,
            "header_text": "",
            "footer_text": "",
            "watermark": None,
        }
    
    @staticmethod
    def _load_config_from_file(path: str) -> Dict[str, Any]:
        """从JSON或YAML文件加载配置（当前仅支持JSON）。"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                if path.endswith('.json'):
                    return json.load(f)
                elif path.endswith('.yaml') or path.endswith('.yml'):
                    try:
                        import yaml
                        return yaml.safe_load(f)
                    except ImportError:
                        logger.error("YAML support requires PyYAML. Falling back to default config.")
                        return PDFExporter._default_config()
                else:
                    logger.warning(f"Unsupported config format: {path}. Using default.")
                    return PDFExporter._default_config()
        except Exception as e:
            logger.error(f"Failed to load config from {path}: {e}. Using default.")
            return PDFExporter._default_config()
    
    def reload_config(self, new_config: Dict[str, Any]):
        """热更新配置（可被外部调用）。"""
        self.__init__(config=new_config)
        logger.info("PDFExporter configuration reloaded.")
    
    def export(self, novel_data: Any, output_path: Optional[str] = None) -> Optional[str]:
        """
        执行PDF导出。
        
        Args:
            novel_data: 小说结构化数据，可以是字典、对象等，具体格式待定义。
            output_path: 输出文件路径，若为None则自动生成。
            
        Returns:
            成功时返回输出文件路径，失败返回None。
        """
        if not novel_data:
            logger.error("No novel data provided for export.")
            return None
        
        # 生成输出路径
        if output_path is None:
            import time
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"novel_{timestamp}.pdf"
            output_path = str(Path(self.output_dir) / filename)
        
        logger.info(f"Starting PDF export to: {output_path}")
        
        try:
            # 确保输出目录存在
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            # 实际PDF生成逻辑（骨架阶段使用占位，后续集成reportlab或类似库）
            self._generate_pdf(novel_data, output_path)
            
            logger.info(f"PDF export succeeded: {output_path}")
            return output_path
        except Exception as e:
            logger.exception(f"PDF export failed: {e}")
            # 异常恢复：删除可能损坏的输出文件
            if output_path and Path(output_path).exists():
                try:
                    Path(output_path).unlink()
                    logger.info(f"Removed incomplete file: {output_path}")
                except Exception as clean_e:
                    logger.warning(f"Could not clean up incomplete file: {clean_e}")
            return None
    
    def _generate_pdf(self, novel_data: Any, output_path: str):
        """
        核心PDF生成方法。当前为占位实现，实际使用时需集成PDF库。
        
        Args:
            novel_data: 小说数据
            output_path: 输出路径
        """
        # TODO: 实现真实的PDF生成逻辑，例如使用reportlab或fpdf
        # 示例伪代码:
        # from reportlab.pdfgen import canvas
        # c = canvas.Canvas(output_path, pagesize=getattr(reportlab.lib.pagesizes, self.page_size))
        # c.setFont(self.font_name, self.font_size)
        # ...
        # c.save()
        
        logger.warning("PDF generation is currently a stub. Please install a PDF library (e.g., reportlab) and implement _generate_pdf.")
        
        # 简单创建一个测试文件表示骨架运行正常（可选）
        # 这里我们写入一个简单的占位PDF内容（非有效PDF，仅为了测试路径）
        # 在生产代码中应当移除。
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("STUB PDF CONTENT. Replace with actual PDF generation.\n")
        logger.info(f"Stub PDF created at {output_path} for testing purposes.")


# ================= 自测代码 =================
if __name__ == "__main__":
    # 简单自测：使用默认配置导出模拟数据
    print("Running PDFExporter self-test...")
    exporter = PDFExporter()
    
    # 模拟小说数据结构（字典）
    mock_novel = {
        "title": "测试小说",
        "author": "AI作家",
        "chapters": [
            {"title": "第一章", "content": "这是第一章的内容。"},
            {"title": "第二章", "content": "这是第二章的内容。"}
        ]
    }
    
    result = exporter.export(mock_novel, output_path="./test_output/novel_test.pdf")
    if result:
        print(f"Test export succeeded: {result}")
    else:
        print("Test export failed.")
    
    # 测试配置热更新
    exporter.reload_config({"page_size": "Letter", "font_size": 14})
    print(f"After reload: page_size={exporter.page_size}, font_size={exporter.font_size}")
    
    # 测试加载配置文件
    config_path = "./configs/pdf_export_config.json"
    exporter2 = PDFExporter(config_path=config_path)
    print(f"Exporter2 page_size: {exporter2.page_size}")  # 使用配置文件或默认
    
    # 测试异常情况（空数据）
    result2 = exporter.export(None)
    assert result2 is None, "Should return None for empty data"
    print("All self-tests passed.")