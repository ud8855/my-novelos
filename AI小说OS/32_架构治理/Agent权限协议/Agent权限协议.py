"""Agent权限协议 - 定义与管理多Agent协同中的权限规则

本模块属于“32_架构治理”层，为Agent协同提供统一的权限验证接口。
依赖：无（底层协议），被调用方：Agent调度、任务分发器、模型协同等模块。
解决：确保Agent在授权范围内执行操作，防止越权。
设计原则：可插拔（通过抽象基类）、配置化（从配置文件加载规则）、日志记录、单一职责。
"""

import abc
import logging
import configparser
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

# ---------------------------- 日志配置 ----------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# 默认简单控制台输出，实际部署时可替换为文件或外部日志系统
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(asctime)s][%(name)s][%(levelname)s] %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# ---------------------------- 配置加载器 ----------------------------
class PermissionConfig:
    """权限配置文件加载器，默认从config/agent_permissions.ini读取"""
    DEFAULT_CONFIG_PATH = "config/agent_permissions.ini"
    
    def __init__(self, config_path: Optional[str] = None):
        self.config = configparser.ConfigParser()
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path(self.DEFAULT_CONFIG_PATH)
        self._load()
    
    def _load(self):
        if self.config_path.exists():
            self.config.read(self.config_path, encoding='utf-8')
            logger.info(f"权限配置文件已加载: {self.config_path}")
        else:
            logger.warning(f"权限配置文件不存在: {self.config_path}, 将使用内置默认空规则")
    
    def get_permission_rules(self) -> Dict[str, Set[str]]:
        """返回所有权限规则: {agent_role: {allowed_action, ...}}"""
        rules = {}
        for section in self.config.sections():
            allowed = self.config.get(section, 'allowed_actions', fallback='')
            actions = {action.strip() for action in allowed.split(',') if action.strip()}
            rules[section] = actions
        return rules
    
    def get_agent_roles(self) -> Set[str]:
        return set(self.config.sections())

# ---------------------------- 权限协议抽象基类 ----------------------------
class AgentPermissionProtocol(abc.ABC):
    """Agent权限协议抽象接口
    
    所有具体权限实现必须继承此类，实现check_permission方法。
    支持热插拔：通过配置指定具体实现类。
    """
    
    @abc.abstractmethod
    def check_permission(self, agent_id: str, action: str, resource: str = "*",
                         context: Optional[Dict[str, Any]] = None) -> bool:
        """检查某个Agent是否具有执行指定操作在指定资源上的权限
        
        Args:
            agent_id: 唯一标识代理ID
            action: 操作名称（如 'read', 'write', 'execute'）
            resource: 资源标识（如 'novel_chapter', 'global_config'，默认'*'表示任意）
            context: 可选的上下文信息，用于更精细的权限判断
        
        Returns:
            bool: True表示允许，False表示拒绝
        """
        pass
    
    @abc.abstractmethod
    def get_allowed_actions(self, agent_id: str) -> Set[str]:
        """获取某个Agent被允许的全部操作集合（辅助方法）"""
        pass

# ---------------------------- 默认权限协议实现 ----------------------------
class DefaultAgentPermissionProtocol(AgentPermissionProtocol):
    """基于配置文件的默认权限协议实现
    
    权限控制逻辑：
    - 将agent_id映射到角色（默认映射规则：agent_id包含角色名，如 'writer_01' 映射到 'writer' 角色）
    - 从配置中读取该角色的允许操作列表
    - 检查请求的action是否在允许列表中
    - resource 参数保留用于未来扩展
    """
    
    def __init__(self, config: Optional[PermissionConfig] = None):
        self.config = config or PermissionConfig()
        self.role_rules = self.config.get_permission_rules()
        logger.info("DefaultAgentPermissionProtocol 初始化完成")
        logger.debug(f"已加载角色权限规则: {self.role_rules}")
    
    def _agent_id_to_role(self, agent_id: str) -> str:
        """简单的角色映射：将agent_id下划线前面的部分作为角色"""
        if not agent_id:
            return "unknown"
        # 例如 "writer_01" -> "writer"
        return agent_id.split('_')[0] if '_' in agent_id else agent_id
    
    def check_permission(self, agent_id: str, action: str, resource: str = "*",
                         context: Optional[Dict[str, Any]] = None) -> bool:
        role = self._agent_id_to_role(agent_id)
        allowed = self.role_rules.get(role, set())
        # 特殊角色 'admin' 或 '*' 表示通配授权
        if '*' in allowed or 'all' in allowed:
            logger.debug(f"Agent[{agent_id}](角色:{role}) 对操作 '{action}' 拥有通配授权")
            return True
        # 检查操作是否在允许列表中
        result = action in allowed
        if result:
            logger.debug(f"Agent[{agent_id}](角色:{role}) 允许操作 '{action}'")
        else:
            logger.warning(f"Agent[{agent_id}](角色:{role}) 拒绝操作 '{action}'，允许的操作: {allowed}")
        return result
    
    def get_allowed_actions(self, agent_id: str) -> Set[str]:
        role = self._agent_id_to_role(agent_id)
        allowed = self.role_rules.get(role, set())
        if '*' in allowed or 'all' in allowed:
            return {'*'}
        return allowed

# ---------------------------- 权限协议工厂（可插拔） ----------------------------
class PermissionProtocolFactory:
    """权限协议工厂，根据配置或类名动态创建权限协议实例
    
    支持在运行时切换不同的权限实现，满足可插拔要求。
    """
    _registry: Dict[str, type] = {}
    
    @classmethod
    def register(cls, name: str, protocol_class: type):
        """注册一个新的权限协议实现类"""
        if not issubclass(protocol_class, AgentPermissionProtocol):
            raise TypeError(f"{protocol_class} 必须继承自 AgentPermissionProtocol")
        cls._registry[name] = protocol_class
        logger.info(f"权限协议注册: {name} -> {protocol_class.__name__}")
    
    @classmethod
    def create(cls, protocol_name: str = "default", **kwargs) -> AgentPermissionProtocol:
        """创建权限协议实例
        
        Args:
            protocol_name: 注册名或完全限定类名
            kwargs: 传递给具体实现的初始化参数
        """
        if protocol_name in cls._registry:
            return cls._registry[protocol_name](**kwargs)
        else:
            # 尝试按类名动态加载（如果已安装为插件）
            try:
                parts = protocol_name.rsplit('.', 1)
                if len(parts) == 2:
                    module_name, class_name = parts
                    module = __import__(module_name, fromlist=[class_name])
                    protocol_class = getattr(module, class_name)
                    if issubclass(protocol_class, AgentPermissionProtocol):
                        return protocol_class(**kwargs)
            except (ImportError, AttributeError, TypeError):
                pass
            raise ValueError(f"未知的权限协议: {protocol_name}")

# 默认注册内置实现
PermissionProtocolFactory.register("default", DefaultAgentPermissionProtocol)

# ---------------------------- 自测 ----------------------------
if __name__ == "__main__":
    # 创建一个简单的配置文件用于测试（不写实际文件，使用内存配置）
    test_config = configparser.ConfigParser()
    test_config['writer'] = {'allowed_actions': 'write_chapter, read_outline, request_review'}
    test_config['reviewer'] = {'allowed_actions': 'read_chapter, provide_feedback, approve'}
    test_config['admin'] = {'allowed_actions': '*'}
    
    class TestPermissionConfig(PermissionConfig):
        def __init__(self):
            self.config = test_config
            self.role_rules = {role: set(actions.split(',')) for role, actions in 
                               [(s, self.config[s]['allowed_actions']) for s in self.config.sections()]}
        def get_permission_rules(self):
            return self.role_rules
    
    # 测试实例
    protocol = DefaultAgentPermissionProtocol(config=TestPermissionConfig())
    
    # 测试用例
    test_cases = [
        ("writer_01", "write_chapter", True),
        ("writer_01", "read_outline", True),
        ("writer_01", "approve", False),       # writer没有审批权限
        ("reviewer_02", "provide_feedback", True),
        ("reviewer_02", "write_chapter", False), # reviewer不能写章节
        ("admin_42", "anything", True),          # admin通配
        ("unknown_99", "read", False),           # 未知角色无权限
    ]
    
    print("=== Agent权限协议自测 ===")
    for agent, action, expected in test_cases:
        result = protocol.check_permission(agent, action)
        status = "PASS" if result == expected else "FAIL"
        print(f"[{status}] Agent={agent}, Action={action}, Result={result}, Expected={expected}")
    
    # 测试获取全部允许操作
    print("\n允许操作查询测试:")
    print(f"writer_01: {protocol.get_allowed_actions('writer_01')}")
    print(f"admin_42: {protocol.get_allowed_actions('admin_42')}")
    
    # 测试工厂
    protocol2 = PermissionProtocolFactory.create("default", config=TestPermissionConfig())
    print("\n工厂创建测试: ", protocol2.check_permission("writer_03", "write_chapter"))
    
    logger.info("自测完成，所有权限协议功能正常工作。")