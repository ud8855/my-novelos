# -*- coding: utf-8 -*-
"""
权限管理模块 - 可插拔权限控制
依赖：logging，配置化
被调用：各Agent或服务进行权限校验
"""

import logging
from typing import Dict, List, Set, Optional

class PermissionError(Exception):
    """权限异常基类"""
    pass

class UserNotFoundError(PermissionError):
    """用户不存在"""
    pass

class RoleNotFoundError(PermissionError):
    """角色不存在"""
    pass

class PermissionManager:
    """
    可插拔的权限管理器
    支持基于角色的访问控制(RBAC)
    """
    def __init__(self, config: Optional[Dict] = None, logger: Optional[logging.Logger] = None):
        """
        初始化权限管理器
        :param config: 配置字典，包含 'users' 和 'roles' 映射。
                       例如:
                       {
                           'users': {'user_id': 'role_name', ...},
                           'roles': {'role_name': ['permission1', 'permission2', ...], ...}
                       }
        :param logger: 日志记录器
        """
        self.logger = logger or logging.getLogger(__name__)
        self.config = config or {}
        self.users: Dict[str, str] = self.config.get('users', {})
        self.roles: Dict[str, Set[str]] = {
            role: set(perms)
            for role, perms in self.config.get('roles', {}).items()
        }
        self.permission_cache: Dict[str, Set[str]] = {}  # 用户权限缓存，加速检查
        self.logger.info("PermissionManager 初始化完成")

    def set_config(self, config: Dict):
        """热更新配置"""
        self.config = config
        self.users = config.get('users', {})
        self.roles = {
            role: set(perms)
            for role, perms in config.get('roles', {}).items()
        }
        self.permission_cache.clear()
        self.logger.info("PermissionManager 配置已热更新")

    def get_user_role(self, user_id: str) -> str:
        """获取用户角色"""
        if user_id not in self.users:
            raise UserNotFoundError(f"用户 '{user_id}' 不存在")
        return self.users[user_id]

    def get_role_permissions(self, role_name: str) -> Set[str]:
        """获取角色权限集合"""
        if role_name not in self.roles:
            raise RoleNotFoundError(f"角色 '{role_name}' 不存在")
        return self.roles[role_name]

    def get_user_permissions(self, user_id: str) -> Set[str]:
        """获取用户权限集合（带缓存）"""
        if user_id in self.permission_cache:
            return self.permission_cache[user_id]
        try:
            role = self.get_user_role(user_id)
            perms = self.get_role_permissions(role)
            self.permission_cache[user_id] = perms
            return perms
        except PermissionError:
            self.logger.warning(f"无法获取用户 '{user_id}' 的权限")
            return set()

    def check_permission(self, user_id: str, resource: str, action: str) -> bool:
        """
        权限检查
        :param user_id: 用户标识
        :param resource: 资源名（保留扩展，