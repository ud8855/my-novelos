"""
指令总线（InstructionBus）
层级：05_核心总线
职责：
    1. 接收来自UI、Agent等的指令，并路由到对应的执行模块。
    2. 支持指令的注册/注销（可插拔），动态扩展指令集。
    3. 提供统一的指令调用接口（同步/异步）。
    4. 记录所有指令的流转日志。
    5. 通过配置文件定义指令映射。
依赖：基础配置、日志模块
被谁调用：UI层、Agent协调器、自动化调度器
演化方向：支持指令优先级、指令队列、指令事务
"""

import json
import logging
import asyncio
from typing import Dict, Callable, Any, Optional, Union
from pathlib import Path

# 配置化示例路径（实际使用时从统一配置中心读取）
DEFAULT_CONFIG_PATH = Path(__file__).parent / "instruction_config.json"

class InstructionBus:
    """
    指令总线核心类，实现指令的注册、查找、执行与日志。
    """

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        """
        初始化指令总线，加载配置并设置日志。
        :param config_path: 指令映射配置文件路径，若为None则使用默认路径
        """
        self._handlers: Dict[str, Callable] = {}  # 指令 -> 处理函数映射
        self._async_handlers: Dict[str, Callable] = {}  # 异步指令处理映射
        self._config = {}
        self.logger = logging.getLogger("InstructionBus")
        self._load_config(config_path)
        self.logger.info("指令总线初始化完成")

    def _load_config(self, config_path: Optional[Union[str, Path]]):
        """加载指令路由配置"""
        path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        try:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    self._config = json.load(f)
                self.logger.info(f"已加载指令配置：{path}")
            else:
                self.logger.warning(f"指令配置文件不存在：{path}，使用空配置")
                self._config = {}
        except Exception as e:
            self.logger.error(f"加载指令配置失败：{e}")
            self._config = {}

    def register_handler(self, instruction: str, handler: Callable, is_async: bool = False):
        """
        注册指令处理函数（可插拔）
        :param instruction: 指令字符串
        :param handler: 处理函数，同步或异步
        :param is_async: True表示异步处理函数
        """
        if is_async:
            if not asyncio.iscoroutinefunction(handler):
                raise TypeError("异步处理器必须是协程函数")
            self._async_handlers[instruction] = handler
        else:
            if asyncio.iscoroutinefunction(handler):
                raise TypeError("同步处理函数不能是协程，请设置is_async=True")
            self._handlers[instruction] = handler
        self.logger.info(f"注册指令处理：{instruction} (异步={is_async})")

    def unregister_handler(self, instruction: str):
        """注销指令"""
        if instruction in self._handlers:
            del self._handlers[instruction]
            self.logger.info(f"注销同步指令处理：{instruction}")
        elif instruction in self._async_handlers:
            del self._async_handlers[instruction]
            self.logger.info(f"注销异步指令处理：{instruction}")
        else:
            self.logger.warning(f"尝试注销未注册的指令：{instruction}")

    def execute(self, instruction: str, *args, **kwargs) -> Any:
        """
        同步执行指令，会优先查找配置中的路由，然后再查找已注册的handler。
        """
        # 从配置中查找路由（可支持别名映射）
        route = self._config.get("route", {}).get(instruction, instruction)
        self.logger.debug(f"指令执行请求：{instruction} 路由至 {route}")

        # 先尝试同步handler
        handler = self._handlers.get(route)
        if handler:
            try:
                result = handler(*args, **kwargs)
                self.logger.debug(f"指令 {instruction} 执行成功")
                return result
            except Exception as e:
                self.logger.exception(f"指令 {instruction} 执行异常：{e}")
                raise
        # 再检查异步handler（但不推荐同步调用异步handler，这里抛出异常）
        if route in self._async_handlers:
            raise RuntimeError(f"指令 {instruction} 对应异步处理器，请使用 execute_async")

        self.logger.error(f"未找到指令处理函数：{instruction}")
        raise KeyError(f"未注册的指令：{instruction}")

    async def execute_async(self, instruction: str, *args, **kwargs) -> Any:
        """异步执行指令"""
        route = self._config.get("route", {}).get(instruction, instruction)
        self.logger.debug(f"异步指令请求：{instruction} 路由至 {route}")

        handler = self._async_handlers.get(route)
        if handler:
            try:
                result = await handler(*args, **kwargs)
                self.logger.debug(f"异步指令 {instruction} 执行成功")
                return result
            except Exception as e:
                self.logger.exception(f"异步指令 {instruction} 执行异常：{e}")
                raise
        # 降级到同步handler（需在异步环境中安全执行，这里简单实现为直接调用）
        sync_handler = self._handlers.get(route)
        if sync_handler:
            self.logger.warning(f"异步调用同步指令 {instruction}，不推荐。将同步执行")
            try:
                return sync_handler(*args, **kwargs)
            except Exception as e:
                self.logger.exception(f"指令 {instruction} 同步执行异常：{e}")
                raise

        self.logger.error(f"未找到异步指令处理函数：{instruction}")
        raise KeyError(f"未注册的异步指令：{instruction}")

    def list_instructions(self) -> Dict[str, str]:
        """列出所有已注册指令及其类型"""
        listing = {}
        for ins in self._handlers:
            listing[ins] = "sync"
        for ins in self._async_handlers:
            listing[ins] = "async"
        return listing


# ---------- 自测部分 ----------
if __name__ == "__main__":
    # 设置基本日志
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("InstructionBusTest")

    bus = InstructionBus()

    # 注册一个同步handler
    def handle_greet(name):
        return f"Hello, {name}!"

    bus.register_handler("greet", handle_greet)

    # 注册一个异步handler
    async def handle_fetch_data(url):
        await asyncio.sleep(0.1)  # 模拟异步操作
        return f"Data from {url}"

    bus.register_handler("fetch", handle_fetch_data, is_async=True)

    # 测试同步调用
    print("同步测试：", bus.execute("greet", "World"))

    # 测试异步调用
    async def test_async():
        result = await bus.execute_async("fetch", "http://example.com")
        print("异步测试：", result)

    asyncio.run(test_async())

    # 测试未注册指令
    try:
        bus.execute("unknown")
    except KeyError as e:
        print("预期错误：", e)

    # 列出指令
    print("已注册指令：", bus.list_instructions())