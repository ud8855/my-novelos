"""插件权限.py - 插件权限管理模块

提供插件对系统资源的访问控制。支持基于配置文件的权限定义，
可动态加载与热更新，确保只有授权插件执行允许的操作。

所属层级：28_插件系统（系统基础服务）
依赖：无（仅标准库）
被调用：插件加载器、Hook系统、插件运行时
解决：防止未授权插件访问敏感资源或执行危险操作
"""

import json
import logging
import os
from threading import Lock
from typing import Any, Dict, List, Optional, Set, Tuple

# 配置日志
logger = logging.getLogger(__name__)


class PluginPermissionManager:
    """插件权限管理器

    负责加载、缓存权限规则，并提供统一的权限检查接口。
    遵循单一职责，仅处理权限逻辑，不关心业务含义。
    """

    def __init__(self, config_path: Optional[str] = None):
        """初始化管理器

        Args:
            config_path: 权限配置文件路径（JSON格式），若为None则使用默认路径
        """
        self._lock = Lock()
        self._config_path: Optional[str] = None
        # 缓存权限规则：plugin_name -> { allowed_resources: Set[str], denied_resources: Set[str], actions: Set[str] }
        self._rules: Dict[str, Dict[str, Set[str]]] = {}
        if config_path:
            self.load_config(config_path)
        else:
            logger.info("未指定权限配置文件，所有插件默认获得全部权限（开放模式）")

    def load_config(self, config_path: str) -> bool:
        """从指定路径加载权限配置

        Args:
            config_path: JSON配置文件路径

        Returns:
            bool: 加载成功返回True
        """
        if not os.path.isfile(config_path):
            logger.error(f"权限配置文件不存在: {config_path}")
            return False

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"读取权限配置文件失败: {e}")
            return False

        with self._lock:
            self._parse_config(config)
            self._config_path = config_path
        logger.info(f"成功加载插件权限配置，共{len(self._rules)}个插件规则")
        return True

    def reload(self) -> bool:
        """重新加载当前配置文件，支持热更新"""
        if not self._config_path:
            logger.warning("尚未指定配置文件路径，无法重载")
            return False
        return self.load_config(self._config_path)

    def _parse_config(self, config: Dict[str, Any]) -> None:
        """解析配置字典为内部规则结构（内部方法）"""
        raw_plugins = config.get("plugins", {})
        new_rules: Dict[str, Dict[str, Set[str]]] = {}
        for plugin_name, rule in raw_plugins.items():
            allowed = set(rule.get("allowed_resources", []))
            denied = set(rule.get("denied_resources", []))
            actions = set(rule.get("actions", []))
            new_rules[plugin_name] = {
                "allowed_resources": allowed,
                "denied_resources": denied,
                "actions": actions
            }
        self._rules = new_rules

    def check_permission(self, plugin_name: str, resource: str, action: str = "read",
                         context: Optional[Dict[str, Any]] = None) -> bool:
        """检查插件是否具有对指定资源的操作权限

        Args:
            plugin_name: 插件标识
            resource: 资源标识（如文件路径、数据库表等）
            action: 操作类型（如 read, write, execute）
            context: 额外的上下文信息（未来扩展用）

        Returns:
            bool: 允许返回True，否则False
        """
        with self._lock:
            rules = self._rules
        if not rules:
            # 未加载任何规则，默认开放（或根据策略决定）
            logger.debug(f"无规则，默认允许：插件={plugin_name}, 资源={resource}, 操作={action}")
            return True

        plugin_rule = rules.get(plugin_name)
        if plugin_rule is None:
            # 没有为插件定义规则，默认拒绝（安全优先）或可配置
            logger.warning(f"插件 {plugin_name} 未定义权限规则，默认拒绝访问 {resource} {action}")
            return False

        # 检查操作类型
        allowed_actions = plugin_rule.get("actions", set())
        if action not in allowed_actions:
            logger.info(f"插件 {plugin_name} 不支持操作 {action}，已拒绝")
            return False

        # 检查资源黑名单（优先）
        denied = plugin_rule.get("denied_resources", set())
        if "*" in denied or resource in denied:
            logger.info(f"插件 {plugin_name} 资源 {resource} 在黑名单中，已拒绝")
            return False

        # 检查资源白名单
        allowed = plugin_rule.get("allowed_resources", set())
        if "*" in allowed or resource in allowed:
            logger.debug(f"插件 {plugin_name} 允许访问 {resource} {action}")
            return True

        # 既不在白名单也不在黑名单，默认拒绝
        logger.info(f"插件 {plugin_name} 资源 {resource} 未在白名单中，默认拒绝")
        return False

    def add_plugin_rule(self, plugin_name: str, allowed_resources: Optional[List[str]] = None,
                        denied_resources: Optional[List[str]] = None, actions: Optional[List[str]] = None) -> None:
        """动态添加或更新插件权限规则（用于运行时管理）

        Args:
            plugin_name: 插件名
            allowed_resources: 允许资源列表
            denied_resources: 拒绝资源列表
            actions: 允许操作列表，默认["read"]
        """
        with self._lock:
            self._rules[plugin_name] = {
                "allowed_resources": set(allowed_resources) if allowed_resources else set(),
                "denied_resources": set(denied_resources) if denied_resources else set(),
                "actions": set(actions) if actions else {"read"}
            }
        logger.info(f"动态添加/更新插件规则: {plugin_name}")

    def remove_plugin_rule(self, plugin_name: str) -> None:
        """移除指定插件的权限规则"""
        with self._lock:
            if plugin_name in self._rules:
                del self._rules[plugin_name]
                logger.info(f"已移除插件 {plugin_name} 的权限规则")
            else:
                logger.warning(f"尝试移除不存在的插件规则: {plugin_name}")


# ---------- 自测代码 ----------
if __name__ == "__main__":
    import tempfile
    import sys

    # 配置测试日志
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    # 创建临时配置文件
    test_config = {
        "plugins": {
            "writer_plugin": {
                "allowed_resources": ["file1.txt", "file2.txt"],
                "denied_resources": ["secret.txt"],
                "actions": ["read", "write"]
            },
            "reader_plugin": {
                "allowed_resources": ["*"],
                "denied_resources": ["secret.txt"],
                "actions": ["read"]
            },
            "admin_plugin": {
                "allowed_resources": ["*"],
                "actions": ["*"]
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as tmp:
        json.dump(test_config, tmp)
        config_file = tmp.name

    try:
        # 测试1：加载配置
        manager = PluginPermissionManager()
        success = manager.load_config(config_file)
        assert success, "加载配置失败"

        # 测试2：权限检查 - 允许
        assert manager.check_permission("writer_plugin", "file1.txt", "write") is True
        assert manager.check_permission("reader_plugin", "anyfile.txt", "read") is True

        # 测试3：权限检查 - 拒绝（黑名单）
        assert manager.check_permission("reader_plugin", "secret.txt", "read") is False
        assert manager.check_permission("writer_plugin", "secret.txt", "write") is False

        # 测试4：未知插件
        assert manager.check_permission("unknown_plugin", "somefile", "read") is False

        # 测试5：不支持的action
        assert manager.check_permission("writer_plugin", "file1.txt", "execute") is False

        # 测试6：动态添加规则
        manager.add_plugin_rule("new_plugin", ["public/*"], actions=["read"])
        assert manager.check_permission("new_plugin", "public/data", "read") is True
        assert manager.check_permission("new_plugin", "public/data", "write") is False

        # 测试7：移除规则
        manager.remove_plugin_rule("new_plugin")
        assert manager.check_permission("new_plugin", "public/data", "read") is False

        # 测试8：热更新
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump({"plugins": {"writer_plugin": {"allowed_resources": ["*"], "actions": ["read"]}}}, f)
        manager.reload()
        # writer_plugin 现在只有read权限
        assert manager.check_permission("writer_plugin", "any", "read") is True
        assert manager.check_permission("writer_plugin", "any", "write") is False

        print("所有自测通过！")

    finally:
        os.unlink(config_file)
        sys.exit(0)