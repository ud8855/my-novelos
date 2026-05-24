"""
NovelOS - 接口协议管理模块
所属层: 32_架构治理
依赖: 日志模块, 配置模块
被调用: 各级模块注册并查询接口协议版本
解决问题: 统一管理模块间接口协议，支持版本兼容性检查，防止接口破坏性变更
"""

import logging
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pathlib import Path

# 默认配置路径 (可覆盖)
DEFAULT_PROTOCOL_CONFIG_PATH = Path("02_配置/接口协议配置.json")

class Protocol(ABC):
    """接口协议抽象基类，定义必须实现的协议描述和检查方法"""
    
    def __init__(self, module_name: str, version: str):
        self.module_name = module_name
        self.version = version
        
    @abstractmethod
    def describe(self) -> Dict[str, Any]:
        """返回协议描述，包含接口方法签名、参数、返回值等"""
        pass
    
    @abstractmethod
    def check_compatibility(self, other_version: str) -> bool:
        """检查与另一版本的兼容性"""
        pass
    
    def __repr__(self):
        return f"<Protocol {self.module_name} v{self.version}>"

class ProtocolManager:
    """协议管理器：注册、查询、兼容性验证"""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or DEFAULT_PROTOCOL_CONFIG_PATH
        self.logger = logging.getLogger(self.__class__.__name__)
        self._protocols: Dict[str, List[Protocol]] = {}  # module_name -> list of protocols
        self._load_config()
        
    def _load_config(self):
        """从配置文件加载初始协议注册信息（可选）"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.logger.info(f"加载接口协议配置: {self.config_path}")
                # 这里可以预先注册一些已知协议，但不强制
            except Exception as e:
                self.logger.error(f"加载协议配置失败: {e}")
        else:
            self.logger.info("未找到接口协议配置文件，使用空注册表")
            
    def register(self, protocol: Protocol):
        """注册一个接口协议"""
        module = protocol.module_name
        if module not in self._protocols:
            self._protocols[module] = []
        # 避免重复注册相同版本
        for p in self._protocols[module]:
            if p.version == protocol.version:
                self.logger.warning(f"协议 {module} v{protocol.version} 已存在，忽略注册")
                return
        self._protocols[module].append(protocol)
        self.logger.info(f"注册协议: {protocol}")
        
    def unregister(self, module_name: str, version: str):
        """注销指定版本的协议"""
        if module_name in self._protocols:
            before_count = len(self._protocols[module_name])
            self._protocols[module_name] = [
                p for p in self._protocols[module_name]
                if p.version != version
            ]
            after_count = len(self._protocols[module_name])
            if after_count < before_count:
                self.logger.info(f"注销协议: {module_name} v{version}")
            else:
                self.logger.warning(f"未找到协议 {module_name} v{version}，无法注销")
                
    def get_protocol(self, module_name: str, version: str) -> Optional[Protocol]:
        """获取指定模块和版本的协议对象"""
        for p in self._protocols.get(module_name, []):
            if p.version == version:
                return p
        return None
    
    def list_protocols(self, module_name: Optional[str] = None) -> Dict[str, List[str]]:
        """列出已注册协议，可按模块过滤"""
        if module_name:
            return {module_name: [p.version for p in self._protocols.get(module_name, [])]}
        return {mod: [p.version for p in protos] for mod, protos in self._protocols.items()}
    
    def check_compatibility(self, module_name: str, version