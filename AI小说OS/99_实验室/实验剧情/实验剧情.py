"""实验剧情.py - 实验性剧情生成与管理模块

   位置：99_实验室/实验剧情/
   层级：实验性模块（实验室）
   依赖：标准库 logging、configparser、json（读取配置）、os（路径处理）、sys
   被调用者：主剧情调度器（未来）或直接用于实验原型验证
   功能：提供实验性剧情元素生成、组合、验证的框架，支持配置化、日志记录、热插拔。

   设计原则：
        - 单一职责：仅处理实验剧情逻辑，不涉及存储、UI或外部API。
        - 可插拔：通过标准接口与主系统交互，易于替换。
        - 配置化：所有可调参数从配置文件加载。
        - 日志记录：关键操作与异常均记录。
        - 自测：模块可独立运行进行功能验证。
"""

import os
import sys
import logging
import configparser
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# 设置模块根路径，确保无论从何处调用 config 路径都正确
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(MODULE_DIR, "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 日志格式
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DEFAULT_CONFIG_PATH = os.path.join(MODULE_DIR, "实验剧情_config.ini")

# ---------------------------------------------------------------------------- #
# 配置数据类，保证类型安全（可选，用dataclass使代码整洁）
@dataclass
class ExperimentalPlotConfig:
    """实验剧情模块配置"""
    max_plot_length: int = 2000          # 单次生成剧情最大字数
    generation_retries: int = 3          # 生成失败重试次数
    temperature: float = 0.8             # 创意程度 (0.0 ~ 1.0)
    enable_log: bool = True              # 是否启用日志
    log_level: str = "INFO"              # 日志级别
    log_file: Optional[str] = "实验剧情.log"   # 日志文件（None则只输出控制台）

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "ExperimentalPlotConfig":
        """从字典构建配置，忽略未知键"""
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in config_dict.items() if k in valid_keys}
        return cls(**filtered)

# ---------------------------------------------------------------------------- #
# 剧情记录结构
@dataclass
class PlotSegment:
    """剧情片段"""
    content: str                        # 文本内容
    meta: Dict[str, Any] = None         # 元数据（如标签、风格等）

# ---------------------------------------------------------------------------- #
class ExperimentalPlot:
    """
    实验剧情生成器

    提供实验性的剧情生成接口，可用于快速原型测试不同生成策略。
    本身不绑定任何模型或API，通过回调或策略模式注入生成逻辑。
    """

    def __init__(self, config_path: str = None):
        """
        初始化实验剧情模块

        Args:
            config_path: 配置文件路径，默认使用同目录下的 实验剧情_config.ini
        """
        self.logger = None
        self.config = None
        self._plot_history: List[PlotSegment] = []
        self._init_config(config_path)
        self._init_logging()
        self.logger.info("实验剧情模块初始化完成")

    def _init_config(self, config_path: Optional[str]):
        """加载配置文件"""
        if config_path is None:
            config_path = DEFAULT_CONFIG_PATH
        
        # 默认配置
        default_config = ExperimentalPlotConfig()
        config_data = {}
        
        if os.path.exists(config_path):
            parser = configparser.ConfigParser()
            parser.read(config_path, encoding='utf-8')
            if parser.has_section("ExperimentalPlot"):
                items = dict(parser.items("ExperimentalPlot"))
                # 类型转换：数值类型需手动转换
                for key, value in items.items():
                    try:
                        # 尝试转为 int/float/bool
                        if value.lower() in ("true", "false"):
                            config_data[key] = value.lower() == "true"
                        elif "." in value:
                            config_data[key] = float(value)
                        else:
                            config_data[key] = int(value)
                    except ValueError:
                        config_data[key] = value  # 保留字符串
        
        # 合并配置：配置文件覆盖默认值
        try:
            self.config = ExperimentalPlotConfig.from_dict(config_data)
        except Exception as e:
            # 配置错误时使用默认配置并记录
            self.config = default_config
            if self.logger:
                self.logger.warning(f"配置解析失败，使用默认配置: {e}")
            else:
                print(f"配置解析失败: {e}")

    def _init_logging(self):
        """设置日志"""
        self.logger = logging.getLogger(f"ExperimentalPlot.{id(self)}")
        self.logger.handlers.clear()
        self.logger.setLevel(getattr(logging, self.config.log_level.upper(), logging.INFO))
        
        formatter = logging.Formatter(LOG_FORMAT)
        
        # 文件日志
        if self.config.enable_log and self.config.log_file:
            log_file_path = os.path.join(MODULE_DIR, self.config.log_file)
            fh = logging.FileHandler(log_file_path, encoding='utf-8')
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
        
        # 控制台日志（可选，开发调试用）
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
        
        # 避免日志传播到根logger
        self.logger.propagate = False

    def generate(self, prompt: str, **kwargs) -> Optional[str]:
        """
        生成实验剧情（占位实现）

        实际项目中，此方法将调用注入的生成器 (如模型接口) 来生成文本。
        目前返回一个模拟结果以验证流程。

        Args:
            prompt: 剧情提示词
            **kwargs: 额外参数（如温度覆盖等）

        Returns:
            生成的剧情文本，失败返回None
        """
        self.logger.debug(f"收到生成请求，提示词: {prompt[:50]}...")
        retry_count = self.config.generation_retries
        for attempt in range(1, retry_count + 1):
            try:
                # TODO: 替换为实际模型调用
                result = self._mock_generate(prompt)
                # 简单后处理
                if result and len(result) <= self.config.max_plot_length:
                    segment = PlotSegment(content=result, meta={"attempt": attempt})
                    self._plot_history.append(segment)
                    self.logger.info(f"生成成功 (尝试 {attempt})，长度 {len(result)}")
                    return result
                else:
                    self.logger.warning(f"生成内容异常 (尝试 {attempt})，长度超限或为空")
                    continue
            except Exception as e:
                self.logger.error(f"生成异常 (尝试 {attempt}): {e}")
                if attempt == retry_count:
                    return None
        return None

    def _mock_generate(self, prompt: str) -> str:
        """模拟生成剧情（临时），返回简单的字符串。实际使用时会被替换"""
        return f"[实验剧情生成] 基于提示 \"{prompt}\" 的模拟内容。这里将会是AI生成的小说段落。\n系统配置最大字数: {self.config.max_plot_length}。"

    def set_generator(self, generator_callable):
        """
        插件化生成器：
        可以注入一个可调用对象，定义生成逻辑。从而实现热插拔。
        
        Args:
            generator_callable: 可调用对象，签名为 callable(prompt: str, **kwargs) -> str
        """
        self._generator = generator_callable
        self.logger.info("已注入自定义生成器")

    def clear_history(self):
        """清除历史剧情记录"""
        self._plot_history.clear()
        self.logger.info("已清除历史剧情记录")

    @property
    def plot_history(self) -> List[PlotSegment]:
        """返回不可变的历史记录（可按需扩展返回副本）"""
        return self._plot_history.copy()

# -------------------------------- 自测 ---------------------------------------- #
if __name__ == "__main__":
    # 简单自测
    print("=== 实验剧情模块自测 ===")
    ep = ExperimentalPlot()
    print("配置加载完成")
    print(f"  max_plot_length: {ep.config.max_plot_length}")
    print(f"  temperature: {ep.config.temperature}")
    print(f"  log_level: {ep.config.log_level}")
    
    # 测试生成
    test_prompt = "在深夜的图书馆里，主角发现了一本神秘的书。"
    result = ep.generate(test_prompt)
    if result:
        print(f"生成结果: \n{result}")
        print(f"历史记录数: {len(ep.plot_history)}")
    else:
        print("生成失败")
    
    # 测试清除历史
    ep.clear_history()
    print(f"清除后历史记录数: {len(ep.plot_history)}")
    
    # 测试自定义生成器
    def custom_generator(prompt: str, **kwargs) -> str:
        return f"CUSTOM: {prompt}"
    
    ep.set_generator(custom_generator)
    # 但当前的 generate 方法还未使用 self._generator，需要扩展。
    # 这里仅演示插件接口，实际使用时 generate 内部将调用 self._generator。
    print("自定义生成器已注入（当前占位逻辑未使用，需修改generate以调用）")
    
    print("自测完成。")