"""
插件协议模块

定义NovelOS插件系统的核心协议，包括插件接口、配置、日志集成。
所有插件必须实现此协议，以实现可插拔、可配置、可监控的架构。
"""

import logging
import abc
from typing import Any, Dict, Optional
from dataclasses import dataclass, field


# =============================================================================
# 插件配置基类
# =============================================================================
@dataclass
class PluginConfig:
    """
    插件通用配置基类。
    每个插件可以继承此类，添加自己的配置项。
    """
    # 插件唯一标识符
    plugin_id: str = ""
    # 插件显示名称
    display_name: str = "Unnamed Plugin"
    # 插件版本
    version: str = "0.1.0"
    # 插件作者
    author: str = ""
    # 插件描述
    description: str = ""
    # 是否启用
    enabled: bool = True
    # 其他自定义配置字典
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典，便于序列化"""
        return {
            "plugin_id": self.plugin_id,
            "display_name": self.display_name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "enabled": self.enabled,
            **self.extra
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginConfig":
        """从字典构建配置实例，支持子类扩展"""
        return cls(
            plugin_id=data.get("plugin_id", ""),
            display_name=data.get("display_name", "Unnamed Plugin"),
            version=data.get("version", "0.1.0"),
            author=data.get("author", ""),
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
            extra={k: v for k, v in data.items() if k not in ["plugin_id", "display_name", "version", "author", "description", "enabled"]}
        )


# =============================================================================
# 插件上下文
# =============================================================================
class PluginContext:
    """
    插件执行上下文，为插件提供必要的基础设施（日志、配置、共享数据等）。
    插件通过此对象获得系统服务，避免直接依赖全局变量。
    """
    def __init__(self, plugin_id: str, config: PluginConfig, logger: Optional[logging.Logger] = None):
        self.plugin_id = plugin_id
        self.config = config
        # 若未提供日志记录器，则使用默认设置
        if logger is None:
            self.logger = logging.getLogger(f"plugin.{plugin_id}")
            self.logger.addHandler(logging.NullHandler())
        else:
            self.logger = logger

        # 共享数据存储，用于插件间通信（慎用）
        self.shared_data: Dict[str, Any] = {}

    def log(self, level: int, message: str, *args, **kwargs):
        """统一的日志记录方法，便于后续扩展（如自定义格式化）"""
        self.logger.log(level, f"[{self.plugin_id}] {message}", *args, **kwargs)


# =============================================================================
# 插件协议（抽象基类）
# =============================================================================
class PluginProtocol(abc.ABC):
    """
    插件抽象基类，所有插件必须继承并实现其抽象方法。
    定义了插件生命周期和核心功能接口。
    """

    def __init__(self, config: Optional[PluginConfig] = None):
        """
        初始化插件实例。
        注意：真正的初始化应在 on_load 中进行，构造函数中避免执行重型操作。
        """
        self.config = config or PluginConfig()
        self.context: Optional[PluginContext] = None
        self._logger: Optional[logging.Logger] = None

    @abc.abstractmethod
    def get_metadata(self) -> PluginConfig:
        """
        返回插件元数据（配置）。
        子类可覆盖此方法以提供动态配置或自定义配置类型。
        """
        pass

    @abc.abstractmethod
    def on_load(self, context: PluginContext) -> bool:
        """
        插件加载时调用。
        参数:
            context: 插件上下文，包含日志、配置等。
        返回:
            bool: 加载成功返回 True，否则返回 False。
        此方法中完成资源初始化、注册监听器等。
        """
        pass

    @abc.abstractmethod
    def on_unload(self) -> bool:
        """
        插件卸载时调用。
        返回:
            bool: 卸载成功返回 True，否则返回 False。
        此方法中释放资源、注销监听器等。
        """
        pass

    def on_enable(self) -> bool:
        """
        插件被启用时调用（可选覆盖）。
        默认为空操作，子类可根据需要实现。
        """
        if self.context:
            self.context.log(logging.INFO, "插件已启用")
        return True

    def on_disable(self) -> bool:
        """
        插件被禁用时调用（可选覆盖）。
        默认为空操作，子类可根据需要实现。
        """
        if self.context:
            self.context.log(logging.INFO, "插件已禁用")
        return True

    def get_status(self) -> Dict[str, Any]:
        """
        获取当前插件状态（可选覆盖）。
        返回一个字典，包含运行状态信息。
        """
        return {
            "plugin_id": self.config.plugin_id,
            "loaded": self.context is not None,
            "enabled": self.config.enabled,
        }

    @property
    def logger(self) -> logging.Logger:
        """获取插件的日志记录器。必须在 on_load 之后才可用。"""
        if self.context and self.context.logger:
            return self.context.logger
        raise RuntimeError("Logger is not available before plugin is loaded.")


# =============================================================================
# 简单测试（自测）
# =============================================================================
if __name__ == "__main__":
    # 配置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    test_logger = logging.getLogger("test")

    # 创建一个具体插件用于测试
    class DemoPlugin(PluginProtocol):
        def get_metadata(self) -> PluginConfig:
            config = PluginConfig(
                plugin_id="demo_plugin",
                display_name="演示插件",
                description="一个用于测试协议实现的插件"
            )
            return config

        def on_load(self, context: PluginContext) -> bool:
            self.context = context
            context.log(logging.INFO, "演示插件正在加载...")
            # 模拟初始化工作
            context.shared_data["demo_key"] = "demo_value"
            context.log(logging.DEBUG, "演示插件加载完成")
            return True

        def on_unload(self) -> bool:
            if self.context:
                self.context.log(logging.INFO, "演示插件正在卸载...")
                self.context.shared_data.pop("demo_key", None)
                self.context.log(logging.DEBUG, "演示插件卸载完成")
            return True

    # 实例化插件
    plugin = DemoPlugin()
    meta = plugin.get_metadata()
    print("元数据:", meta.to_dict())

    # 模拟上下文
    ctx = PluginContext(meta.plugin_id, meta, logger=test_logger)

    # 加载插件
    load_ok = plugin.on_load(ctx)
    print("加载结果:", load_ok)
    print("插件状态:", plugin.get_status())
    print("共享数据:", ctx.shared_data)

    # 启用/禁用测试
    plugin.on_enable()
    plugin.on_disable()

    # 卸载插件
    unload_ok = plugin.on_unload()
    print("卸载结果:", unload_ok)
    print("最终状态:", plugin.get_status())