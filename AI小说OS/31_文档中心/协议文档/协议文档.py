"""31_文档中心/协议文档.py

协议文档模块：负责根据系统内各模块的协议定义(如接口描述、数据格式、调用规范等)，
生成标准化、可阅读的协议文档（如Markdown、HTML、PDF等）。

本模块设计为可插拔架构，支持多种文档输出格式和模板。
通过配置文件指定输出目录、格式、模板路径等。
实现了完整的日志记录与自测功能。

依赖：无直接跨层依赖，仅读取标准化协议配置文件。
被调用：文档中心主控模块、CI/CD工作流、开发者手动生成。
"""

import logging
import importlib
import os
import sys
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type

# 配置与日志默认值
DEFAULT_CONFIG = {
    "output_dir": "./output/protocol_docs",
    "default_format": "markdown",
    "template_dir": "./templates/protocol",
    "log_level": "INFO",
    "source_protocol_dirs": [
        "./10_接口定义与协议/协议文件",
        "./20_模型协同/接口协议",
        "./21_API模型/接口协议",
        "./30_业务逻辑层/各模块协议",
    ],
}


class ProtocolDocumentGenerator(ABC):
    """
    协议文档生成器抽象基类，所有具体格式生成器需继承此类。
    实现了可插拔：新增格式只需实现此类并注册即可。
    """

    @abstractmethod
    def generate(self, protocol_data: Dict[str, Any], output_path: str) -> None:
        """
        根据协议数据生成文档文件。
        :param protocol_data: 结构化的协议数据字典
        :param output_path: 输出文件路径（不含扩展名，生成器自行添加）
        """
        pass


class MarkdownProtocolGenerator(ProtocolDocumentGenerator):
    """
    Markdown 格式协议文档生成器示例。
    """

    def generate(self, protocol_data: Dict[str, Any], output_path: str) -> None:
        # 这里实现Markdown文档生成逻辑
        logging.info(f"[MarkdownGenerator] 生成文档: {output_path}.md")
        # 示例：写入文件
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(f"{output_path}.md", "w", encoding="utf-8") as f:
            f.write(f"# 协议文档\n\n")
            for module_name, interfaces in protocol_data.items():
                f.write(f"## 模块: {module_name}\n\n")
                for iface_name, iface_spec in interfaces.items():
                    f.write(f"### {iface_name}\n\n")
                    f.write(f"```json\n{iface_spec}\n```\n\n")


class HTMLProtocolGenerator(ProtocolDocumentGenerator):
    """HTML 格式生成器骨架"""

    def generate(self, protocol_data: Dict[str, Any], output_path: str) -> None:
        logging.info(f"[HTMLGenerator] 生成文档: {output_path}.html")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(f"{output_path}.html", "w", encoding="utf-8") as f:
            f.write("<html><body><h1>协议文档</h1></body></html>")


class ProtocolDocManager:
    """
    协议文档管理核心类。
    负责加载配置、收集协议数据、调度生成器输出文档。
    支持热插拔：通过字符串指定生成器类路径进行动态加载。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        :param config: 自定义配置字典，若未提供则使用默认配置
        """
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self._configure_logging()
        self.generators: Dict[str, Type[ProtocolDocumentGenerator]] = {
            "markdown": MarkdownProtocolGenerator,
            "html": HTMLProtocolGenerator,
        }
        self._loaded_modules: Dict[str, Any] = {}  # 当前加载的协议数据

    def _configure_logging(self):
        """配置日志输出"""
        log_level = getattr(logging, self.config.get("log_level", "INFO").upper(), logging.INFO)
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        self.logger = logging.getLogger("ProtocolDocManager")
        self.logger.info("协议文档管理器初始化完成")

    def register_generator(self, format_name: str, generator_cls: Type[ProtocolDocumentGenerator]):
        """
        注册新的文档生成器，实现热插拔扩展。
        :param format_name: 格式标识（如 'pdf'）
        :param generator_cls: 生成器类（需继承 ProtocolDocumentGenerator）
        """
        if not issubclass(generator_cls, ProtocolDocumentGenerator):
            raise TypeError("生成器必须继承 ProtocolDocumentGenerator")
        self.generators[format_name] = generator_cls
        self.logger.info(f"已注册新生成器: {format_name} -> {generator_cls.__name__}")

    def load_protocol_data(self) -> Dict[str, Any]:
        """
        从配置的源协议目录中扫描并加载协议定义文件。
        协议文件应为 JSON 或 YAML 格式，包含模块接口描述。
        返回统一的结构化数据。
        """
        all_data = {}
        # 此处为示例，实际需遍历 source_protocol_dirs 并解析文件
        # 为避免跨层污染，本模块仅读取配置文件，不直接操作数据库或API。
        for dir_path in self.config["source_protocol_dirs"]:
            if not os.path.exists(dir_path):
                self.logger.warning(f"协议源目录不存在: {dir_path}")
                continue
            # 模拟加载：假设每个目录下有一个 protocol_definition.py 提供 get_protocol() 函数
            # 真实环境应安全导入并执行。
            self.logger.debug(f"扫描协议目录: {dir_path}")
            # 这里保持骨架，返回空数据
        self._protocol_data = all_data
        return all_data

    def generate_docs(self, format_name: Optional[str] = None, output_dir: Optional[str] = None):
        """
        生成所有已加载协议的文档。
        :param format_name: 指定输出格式，若未指定则使用配置中的默认格式
        :param output_dir: 输出目录，覆盖配置
        """
        fmt = format_name or self.config["default_format"]
        out_dir = output_dir or self.config["output_dir"]
        generator_cls = self.generators.get(fmt)
        if not generator_cls:
            self.logger.error(f"未找到格式生成器: {fmt}")
            raise ValueError(f"Unsupported format: {fmt}")

        protocol_data = self._protocol_data if self._protocol_data else self.load_protocol_data()
        if not protocol_data:
            self.logger.warning("没有可用的协议数据，文档生成跳过")
            return

        generator = generator_cls()
        # 为每个模块生成一个文档，或整体生成，此处设计为整体输出
        output_file = os.path.join(out_dir, "protocols")
        generator.generate(protocol_data, output_file)
        self.logger.info(f"协议文档生成完成: {output_file}.{fmt}")

    def reload_config(self, new_config: Dict[str, Any]):
        """热更新配置，重新初始化日志等"""
        self.config.update(new_config)
        self._configure_logging()
        self.logger.info("配置已热更新")


# ================= 自测部分 =================
if __name__ == "__main__":
    """
    模块自测：验证基本功能，不依赖外部真实数据。
    可以通过修改此处的模拟协议数据进行测试。
    """
    print("开始协议文档模块自测...")

    # 测试默认初始化
    manager = ProtocolDocManager()
    print(f"默认配置: {manager.config}")

    # 测试注册自定义生成器
    class PlainTextGenerator(ProtocolDocumentGenerator):
        def generate(self, protocol_data, output_path):
            logging.info(f"[PlainTextGenerator] 生成文档: {output_path}.txt")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(f"{output_path}.txt", "w", encoding="utf-8") as f:
                f.write("Protocol Documentation\n")
                f.write(str(protocol_data))

    manager.register_generator("text", PlainTextGenerator)

    # 模拟协议数据
    mock_protocol_data = {
        "UserModule": {
            "create_user": {"method": "POST", "path": "/users", "request": "UserCreateRequest", "response": "UserResponse"},
            "get_user": {"method": "GET", "path": "/users/{id}", "response": "UserResponse"},
        },
        "ModelCoordination": {
            "query_model": {"type": "GRPC", "service": "ModelService", "method": "Query", "input": "QueryRequest", "output": "QueryResponse"}
        }
    }
    manager._protocol_data = mock_protocol_data  # 直接注入，避免文件扫描

    # 测试生成多种格式
    for fmt in ["markdown", "html", "text"]:
        print(f"正在生成 {fmt} 格式文档...")
        manager.generate_docs(format_name=fmt)
    
    print("自测完成，请检查输出目录: " + manager.config["output_dir"])