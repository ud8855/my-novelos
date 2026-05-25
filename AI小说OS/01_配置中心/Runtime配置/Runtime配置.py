import logging
from typing import Any, Callable, Dict, Optional

class RuntimeConfig:
    """
    运行时配置管理器（单例模式）
    职责：统一管理运行时可变的配置项，支持热更新、配置源替换，保证异常恢复与日志记录。
    可插拔：通过 set_config_source 替换配置来源，实现不同环境的配置加载策略。
    """
    _instance: Optional['RuntimeConfig'] = None
    _config: Dict[str, Any] = {}
    _config_source: Optional[Callable[[], Dict[str, Any]]] = None

    def __new__(cls, config_source: Optional[Callable[[], Dict[str, Any]]] = None):
        if cls._instance is None:
            instance = super().__new__(cls)
            cls._instance = instance
            instance._initialized = False
        return cls._instance

    def __init__(self, config_source: Optional[Callable[[], Dict[str, Any]]] = None):
        if self._initialized:
            return
        self._initialized = True
        self.logger = logging.getLogger(self.__class__.__name__)
        self._config_source = config_source or self._default_source
        self._config = {}
        self.load()

    @staticmethod
    def _default_source() -> Dict[str, Any]:
        """
        默认配置源：可以从环境变量或固定位置文件加载，此处返回空字典作为占位。
        实际部署时可替换为从 YAML / JSON / 远程中心加载。
        """
        # TODO: 集成真实配置源，如环境变量、配置文件等
        return {}

    def load(self) -> None:
        """
        加载配置核心逻辑，包含异常恢复：若加载失败，保留原有配置不变。
        """
        try:
            self.logger.info("正在加载运行时配置...")
            source = self._config_source
            if not callable(source):
                raise TypeError("配置源必须是可调用对象，返回配置字典。")
            new_config = source()
            if not isinstance(new_config, dict):
                raise TypeError("配置源必须返回 dict 类型。")
            self._config = new_config.copy()
            self.logger.info("运行时配置加载成功。")
        except Exception as e:
            self.logger.error(f"加载运行时配置失败: {e}", exc_info=True)
            # 异常恢复：保持原有配置，不抛异常（根据需求也可选择抛出）
            # raise

    def reload(self) -> None:
        """
        热更新：重新执行 load，实现配置不重启更新。
        """
        self.logger.info("触发运行时配置热更新。")
        self.load()

    def get(self, key: str, default: Any = None) -> Any:
        """获取单个配置值"""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """运行时动态设置某一个配置（用于临时覆盖）"""
        self._config[key] = value
        self.logger.debug(f"配置已更新: {key} = {value}")

    def all(self) -> Dict[str, Any]:
        """返回当前全部配置的浅拷贝，防止外部直接修改内部字典"""
        return self._config.copy()

    def set_config_source(self, source: Callable[[], Dict[str, Any]]) -> None:
        """
        替换配置源，实现可插拔。
        传入一个无参数的可调用对象，返回配置字典。
        """
        self.logger.info("运行时配置源已切换。")
        self._config_source = source
        self.reload()


# ---------- 自测与示例 ----------
if __name__ == "__main__":
    # 设置日志格式与级别
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 1. 获取单例，使用默认空源
    config = RuntimeConfig()
    print("默认配置:", config.all())
    assert config.get('nonexistent', 'fallback') == 'fallback'

    # 2. 测试可插拔：替换为一个自定义源
    def custom_source() -> Dict[str, Any]:
        return {"app_name": "NovelOS", "debug": True}

    config.set_config_source(custom_source)
    assert config.get('app_name') == 'NovelOS'
    assert config.get('debug') is True
    print("自定义配置:", config.all())

    # 3. 测试热更新：修改源返回值，调用 reload
    def updated_source() -> Dict[str, Any]:
        return {"app_name": "NovelOS", "debug": False, "version": "0.1.0"}

    config.set_config_source(updated_source)  # 自动触发 reload
    assert config.get('debug') is False
    assert config.get('version') == '0.1.0'
    print("热更新配置:", config.all())

    # 4. 动态设置
    config.set("temp_key", 123)
    assert config.get("temp_key") == 123
    print("动态设置后配置:", config.all())

    print("自测全部通过。")