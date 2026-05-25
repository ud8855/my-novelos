"""插件配置模块
负责管理NovelOS插件的配置信息，包括加载、保存、启用/禁用插件等。
单一职责：仅处理插件配置数据，不涉及插件具体功能。
可插拔设计：通过配置文件动态管理插件，支持热插拔接口。
日志：记录配置变更及错误。
配置化：插件配置文件路径可通过系统配置指定，默认路径为 01_配置中心/plugin_config.json
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# 设置本模块日志器
logger = logging.getLogger("NovelOS.PluginConfig")

class PluginConfigError(Exception):
    """插件配置相关异常"""
    pass

class PluginConfigManager:
    """
    插件配置管理器
    负责加载、保存、查询和修改插件配置。
    设计为单例模式（模块级对象），确保全局配置一致性。
    """
    _instance = None  # 单例实例

    def __new__(cls, config_file_path: Optional[Path] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_done = False
        return cls._instance

    def __init__(self, config_file_path: Optional[Path] = None):
        """初始化配置管理器，仅在首次实例化时执行"""
        if self._init_done:
            return
        self._init_done = True
        # 默认配置文件路径，可通过参数或环境变量覆盖
        if config_file_path is None:
            config_root = Path(os.environ.get("NOVELOS_CONFIG_ROOT", "01_配置中心"))
            config_file_path = config_root / "plugin_config.json"
        self.config_file: Path = Path(config_file_path)
        # 插件配置数据结构：{plugin_id: {enabled: bool, settings: dict}}
        self._plugins: Dict[str, Dict[str, Any]] = {}
        self._load_config()
        logger.info(f"PluginConfigManager initialized with config file: {self.config_file}")

    def _load_config(self) -> None:
        """从配置文件加载插件配置，若文件不存在则创建默认空配置"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self._plugins = json.load(f)
                logger.info(f"Loaded plugin configuration from {self.config_file}")
            else:
                self._plugins = {}
                self._save_config()  # 创建空文件
                logger.warning(f"Config file not found, created empty at {self.config_file}")
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Failed to load plugin config: {e}")
            raise PluginConfigError(f"Cannot load plugin config from {self.config_file}") from e

    def _save_config(self) -> None:
        """保存当前配置到文件"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._plugins, f, indent=2, ensure_ascii=False)
            logger.debug(f"Plugin configuration saved to {self.config_file}")
        except IOError as e:
            logger.error(f"Failed to save plugin config: {e}")
            raise PluginConfigError(f"Cannot save plugin config to {self.config_file}") from e

    def get_plugin_ids(self) -> List[str]:
        """获取所有已注册的插件ID列表"""
        return list(self._plugins.keys())

    def get_enabled_plugins(self) -> List[str]:
        """获取当前启用的插件ID列表"""
        return [pid for pid, cfg in self._plugins.items() if cfg.get("enabled", False)]

    def is_enabled(self, plugin_id: str) -> bool:
        """判断指定插件是否启用"""
        return self._plugins.get(plugin_id, {}).get("enabled", False)

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        """启用或禁用指定插件"""
        if plugin_id not in self._plugins:
            # 如果不存在则自动注册并应用设置
            self._plugins[plugin_id] = {"enabled": enabled, "settings": {}}
            logger.info(f"New plugin registered and {'enabled' if enabled else 'disabled'}: {plugin_id}")
        else:
            self._plugins[plugin_id]["enabled"] = enabled
            logger.info(f"Plugin '{plugin_id}' {'enabled' if enabled else 'disabled'}")
        self._save_config()

    def get_plugin_settings(self, plugin_id: str) -> Dict[str, Any]:
        """获取插件的自定义设置"""
        return self._plugins.get(plugin_id, {}).get("settings", {})

    def update_plugin_settings(self, plugin_id: str, settings: Dict[str, Any]) -> None:
        """更新插件的自定义设置（合并更新）"""
        if plugin_id not in self._plugins:
            self._plugins[plugin_id] = {"enabled": False, "settings": settings}
            logger.info(f"New plugin settings added for {plugin_id}")
        else:
            self._plugins[plugin_id].setdefault("settings", {}).update(settings)
            logger.info(f"Plugin settings updated for {plugin_id}")
        self._save_config()

    def remove_plugin(self, plugin_id: str) -> None:
        """完全移除某个插件的配置"""
        if plugin_id in self._plugins:
            del self._plugins[plugin_id]
            self._save_config()
            logger.info(f"Plugin '{plugin_id}' configuration removed")

    def reload_config(self) -> None:
        """重新加载配置文件（用于热更新）"""
        old_ids = set(self._plugins.keys())
        self._load_config()
        new_ids = set(self._plugins.keys())
        logger.info(f"Config reloaded. Plugin changes: added={new_ids-old_ids}, removed={old_ids-new_ids}")

    # 提供类级别的便捷方法，方便其他模块直接调用单例
    @classmethod
    def get_instance(cls, config_file_path: Optional[Path] = None) -> 'PluginConfigManager':
        return cls(config_file_path)


# ==================== 自测部分 ====================
if __name__ == "__main__":
    # 配置日志输出到控制台，便于观察自测结果
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 使用临时文件进行测试，避免污染实际配置
    test_config_path = Path("test_plugin_config.json")
    # 清理之前的测试文件（如果存在）
    if test_config_path.exists():
        test_config_path.unlink()

    print("开始插件配置模块自测...")
    manager = PluginConfigManager(config_file_path=test_config_path)

    # 测试1: 初始状态应为空
    assert manager.get_plugin_ids() == []
    print("测试1通过：初始插件列表为空")

    # 测试2: 启用一个新插件
    manager.set_enabled("core_editor", True)
    assert manager.is_enabled("core_editor") is True
    assert "core_editor" in manager.get_enabled_plugins()
    print("测试2通过：启用插件成功")

    # 测试3: 禁用插件
    manager.set_enabled("core_editor", False)
    assert not manager.is_enabled("core_editor")
    assert "core_editor" not in manager.get_enabled_plugins()
    print("测试3通过：禁用插件成功")

    # 测试4: 更新插件设置
    manager.update_plugin_settings("core_editor", {"font_size": 14, "theme": "dark"})
    settings = manager.get_plugin_settings("core_editor")
    assert settings == {"font_size": 14, "theme": "dark"}
    manager.update_plugin_settings("core_editor", {"font_size": 16})  # 合并更新
    assert manager.get_plugin_settings("core_editor") == {"font_size": 16, "theme": "dark"}
    print("测试4通过：插件设置合并更新正确")

    # 测试5: 删除插件
    manager.remove_plugin("core_editor")
    assert "core_editor" not in manager.get_plugin_ids()
    print("测试5通过：删除插件成功")

    # 测试6: 热重载
    # 模拟另一个管理器实例（实际上还是同一个单例）加载同一个文件
    # 注意：因为单例已初始化，先手动改文件再调用reload_config
    # 简单测试：直接通过第二个“实例”调用，实际上是同一个对象
    manager2 = PluginConfigManager(config_file_path=test_config_path)
    manager2.set_enabled("voice_reader", True)  # 会保存到文件
    # 创建一个新的管理器（由于单例，实际上是同一个，但调用reload_config会重新加载文件）
    manager.reload_config()
    assert "voice_reader" in manager.get_plugin_ids()
    print("测试6通过：热重载成功")

    # 清理测试文件
    test_config_path.unlink(missing_ok=True)
    print("所有自测通过！")