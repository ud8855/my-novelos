"""
25_UI界面/控制台.py
Layer: 用户界面层 (UI)
依赖: 配置管理模块, 日志模块, 可能的调度器/事件总线
被调用: 由主程序启动，负责控制台交互界面，接收用户输入并委派给下层模块
解决问题: 提供命令行交互式操作界面，作为用户与NovelOS进行交互的主要入口之一
"""

import logging
import sys
from typing import Optional, Dict, Any

# 假定项目内配置和日志模块，实际路径根据项目调整
try:
    from utils.config_loader import ConfigLoader
    from utils.logger import setup_logger
except ImportError:
    # 简化模拟，确保自测可运行
    class ConfigLoader:
        def __init__(self, config_path: str = ""):
            self.config: Dict[str, Any] = {}
        def load(self):
            self.config = {"console_ui": {"prompt": "NovelOS> "}}
            return self
        def get(self, key: str, default=None):
            return self.config.get(key, default)

    def setup_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
        logger = logging.getLogger(name)
        if not logger.handlers:
            ch = logging.StreamHandler(sys.stdout)
            ch.setLevel(level)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)
            logger.setLevel(level)
        return logger


class ConsoleUI:
    """
    NovelOS 控制台交互界面
    负责启动交互循环，接收用户指令并分发到下层处理器。
    设计为可插拔组件，通过配置决定行为，所有操作记录日志。
    """
    
    def __init__(self, config: Optional[ConfigLoader] = None, logger: Optional[logging.Logger] = None):
        """
        初始化控制台UI
        :param config: 配置加载器实例，如果不提供则使用默认配置
        :param logger: 日志记录器，如果不提供则创建新logger
        """
        # 配置
        self.config = config if config is not None else ConfigLoader().load()
        # 从配置读取控制台相关设置，如提示符、历史记录等
        self.console_config = self.config.get("console_ui", {})
        self.prompt = self.console_config.get("prompt", "NovelOS> ")
        
        # 日志
        self.logger = logger or setup_logger(self.__class__.__name__)
        self.logger.info("ConsoleUI instance created.")
        
        # 状态
        self.running = False
        
        # 命令处理器注册表（可插拔式扩展）
        self.command_handlers: Dict[str, callable] = {}
        
        # 预留接口：与调度器或事件总线的连接对象
        self.event_bus = None  # 稍后注入，避免跨层依赖
        
    def register_handler(self, command: str, handler: callable):
        """
        注册命令处理器，实现功能热插拔
        :param command: 命令字符串（如 "write", "edit", "quit"）
        :param handler: 处理函数，接收参数列表
        """
        self.command_handlers[command] = handler
        self.logger.debug(f"Registered handler for command: {command}")
        
    def unregister_handler(self, command: str):
        """
        移除命令处理器
        :param command: 命令字符串
        """
        if command in self.command_handlers:
            del self.command_handlers[command]
            self.logger.debug(f"Unregistered handler for command: {command}")
    
    def inject_event_bus(self, event_bus):
        """
        注入事件总线，用于与下层模块通信（不直接访问数据库或Agent）
        :param event_bus: 事件总线实例
        """
        self.event_bus = event_bus
        self.logger.info("Event bus injected into ConsoleUI.")
        
    def start(self):
        """
        启动控制台交互循环
        """
        self.running = True
        self.logger.info("ConsoleUI started. Type 'help' for commands, 'quit' to exit.")
        try:
            while self.running:
                try:
                    user_input = input(self.prompt).strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nExiting...")
                    self.stop()
                    break
                if not user_input:
                    continue
                # 简单解析：第一个词为命令，其余为参数
                parts = user_input.split()
                command = parts[0].lower()
                args = parts[1:]
                
                # 内置命令
                if command in ("quit", "exit"):
                    self.stop()
                elif command == "help":
                    self._show_help()
                else:
                    # 分发到注册的处理器
                    handler = self.command_handlers.get(command)
                    if handler:
                        try:
                            handler(args)
                        except Exception as e:
                            self.logger.error(f"Error executing command '{command}': {e}", exc_info=True)
                            print(f"命令执行错误: {e}")
                    else:
                        print(f"未知命令: {command}，输入 'help' 查看可用命令。")
        except Exception as e:
            self.logger.critical(f"ConsoleUI fatal error: {e}", exc_info=True)
            self.stop()
            raise

    def stop(self):
        """
        停止控制台，关闭循环
        """
        self.running = False
        self.logger.info("ConsoleUI stopped.")
        # 预留清理工作
        if self.event_bus:
            # 解绑等
            pass

    def _show_help(self):
        """显示帮助信息（内置命令 + 注册的命令）"""
        help_text = [
            "NovelOS 控制台命令:",
            "  help                 - 显示此帮助",
            "  quit / exit          - 退出程序",
        ]
        if self.command_handlers:
            help_text.append("已注册功能命令:")
            for cmd in self.command_handlers:
                help_text.append(f"  {cmd}")
        print("\n".join(help_text))


# 自测代码
if __name__ == "__main__":
    # 基础配置
    test_config = ConfigLoader()
    test_config.config.update({
        "console_ui": {
            "prompt": "NovelOS(test)> "
        }
    })
    logger = setup_logger("ConsoleUI_Test", logging.DEBUG)
    
    ui = ConsoleUI(config=test_config, logger=logger)
    
    # 示例命令：一个简单的echo功能，演示可插拔
    def echo_handler(args):
        message = " ".join(args)
        print(f"Echo: {message}")
    
    ui.register_handler("echo", echo_handler)
    ui.register_handler("hello", lambda args: print("Hello, NovelOS!"))
    
    print("=== NovelOS 控制台自测模式 ===")
    print("可用命令: help, quit, echo, hello")
    ui.start()