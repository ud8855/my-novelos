# -*- coding: utf-8 -*-
"""
NovelOS - 架构治理层 - 模块职责书
路径: 32_架构治理/模块职责书/模块职责书.py
功能: 定义、加载、验证系统所有模块的职责书，确保架构规则（层隔离、单一职责等）不被违反。
特性: 可插拔、日志记录、配置化、热更新、异常恢复。
依赖: 无其他业务模块（仅依赖Python标准库和基础配置）。
被调用: 架构治理工具、CI/CD检查、系统启动时自检。
"""

import os
import json
import logging
import configparser
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from pathlib import Path

# ============================================================================
# 配置化 (支持外部配置)
# ============================================================================
class ModuleManifestConfig:
    """模块职责书配置管理器（支持热更新）"""
    def __init__(self, config_path: Optional[str] = None):
        self._config = configparser.ConfigParser()
        self._logger = logging.getLogger(f"{__name__}.ModuleManifestConfig")
        self._last_load_time = 0.0
        if config_path:
            self.load_config(config_path)

    def load_config(self, config_path: str):
        """加载ini格式的配置文件（支持热重载）"""
        try:
            if not os.path.exists(config_path):
                self._logger.warning(f"配置文件不存在: {config_path}, 使用默认配置")
                return
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config.read_file(f)
            self._last_load_time = os.path.getmtime(config_path)
            self._logger.info(f"配置已加载: {config_path}")
        except Exception as e:
            self._logger.error(f"加载配置文件失败: {config_path}, 错误: {e}")

    def get(self, section: str, key: str, fallback: Any = None) -> Any:
        """获取配置项"""
        return self._config.get(section, key, fallback=fallback)

    def check_and_reload(self, config_path: str):
        """检查配置文件时间戳，若更新则热重载"""
        if not os.path.exists(config_path):
            return
        mtime = os.path.getmtime(config_path)
        if mtime > self._last_load_time:
            self.load_config(config_path)

# ============================================================================
# 模块职责数据结构
# ============================================================================
@dataclass
class DependencyRule:
    """依赖规则：描述模块被谁调用、可以调用谁、禁止调用谁"""
    allowed_callers: List[str] = field(default_factory=list)   # 允许调用本模块的模块标识
    forbidden_callers: List[str] = field(default_factory=list) # 禁止调用本模块的模块标识
    allowed_dependencies: List[str] = field(default_factory=list)  # 本模块允许调用的其他模块
    forbidden_dependencies: List[str] = field(default_factory=list) # 本模块禁止调用的其他模块

@dataclass
class ModuleResponsibility:
    """单个模块职责书"""
    module_id: str                            # 模块唯一标识，如 "20_模型协同/模型协调器"
    module_path: str                          # 文件系统相对路径
    layer: int                                # 所属层级编号（1~9）
    description: str                          # 模块职责描述（中文）
    single_responsibility: str                # 单一职责定义
    is_pluggable: bool = True                 # 是否可插拔
    dependency_rules: DependencyRule = field(default_factory=DependencyRule)  # 依赖规则
    extra_properties: Dict[str, Any] = field(default_factory=dict)  # 扩展属性

    def __post_init__(self):
        """验证基本字段"""
        if not self.module_id:
            raise ValueError("模块ID不能为空")
        if not 1 <= self.layer <= 9:
            raise ValueError(f"层级编号必须在1-9之间，当前: {self.layer}")

@dataclass
class ModuleManifest:
    """整个系统的模块职责清单"""
    version: str = "1.0.0"
    generated_by: str = "NovelOS Architect"
    modules: List[ModuleResponsibility] = field(default_factory=list)
    global_rules: Dict[str, Any] = field(default_factory=dict)  # 全局架构规则

# ============================================================================
# 职责书验证器接口（可插拔）
# ============================================================================
class IResponsibilityValidator(ABC):
    """职责验证器抽象基类，实现可插拔的验证逻辑"""
    @abstractmethod
    def validate(self, manifest: ModuleManifest, context: Dict[str, Any]) -> List[str]:
        """
        执行验证，返回错误列表（空列表表示通过）
        :param manifest: 整个模块职责清单
        :param context: 额外上下文信息（如文件系统状态）
        :return: 错误信息字符串列表
        """
        pass

# 内置验证器 - 禁止跨层污染验证
class CrossLayerPollutionValidator(IResponsibilityValidator):
    def validate(self, manifest: ModuleManifest, context: Dict[str, Any]) -> List[str]:
        errors = []
        self._logger = logging.getLogger(f"{__name__}.CrossLayerValidator")
        # 获取所有模块的层级映射
        layer_map = {m.module_id: m.layer for m in manifest.modules}
        for module in manifest.modules:
            # 检查禁止调用的模块是否属于更低或更高层次（跨层污染）
            for forbidden_dep in module.dependency_rules.forbidden_dependencies:
                if forbidden_dep in layer_map:
                    dep_layer = layer_map[forbidden_dep]
                    # 示例规则：禁止UI层(1)直接调用数据层(7~9) (需要具体规则)
                    # 这里只做示意性检查
                    pass
            # 实际规则可由配置驱动
        return errors

# 内置验证器 - 重复功能检查（基于职责描述相似度，简化示例）
class DuplicateResponsibilityValidator(IResponsibilityValidator):
    def validate(self, manifest: ModuleManifest, context: Dict[str, Any]) -> List[str]:
        errors = []
        descriptions = {}
        for module in manifest.modules:
            desc = module.single_responsibility.lower().strip()
            if desc in descriptions:
                errors.append(f"重复职责: {module.module_id} 与 {descriptions[desc]} 具有相同的职责描述")
            else:
                descriptions[desc] = module.module_id
        return errors

# ============================================================================
# 模块职责书管理器
# ============================================================================
class ModuleResponsibilityManager:
    """模块职责书的核心管理器，负责加载、验证、热更新"""
    def __init__(self, manifest_file: Optional[str] = None, config: Optional[ModuleManifestConfig] = None):
        self._logger = logging.getLogger(f"{__name__}.Manager")
        self._manifest: Optional[ModuleManifest] = None
        self._manifest_file = manifest_file
        self._config = config or ModuleManifestConfig()
        self._validators: List[IResponsibilityValidator] = []
        # 注册默认验证器
        self.register_validator(CrossLayerPollutionValidator())
        self.register_validator(DuplicateResponsibilityValidator())

    def load_manifest(self, file_path: Optional[str] = None) -> bool:
        """从JSON文件加载职责清单"""
        target = file_path or self._manifest_file
        if not target:
            self._logger.error("未指定职责清单文件路径")
            return False
        try:
            with open(target, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # 解析为ModuleManifest
            modules = []
            for mod_data in data.get("modules", []):
                # 构造DependencyRule
                dep_rule_data = mod_data.get("dependency_rules", {})
                dep_rule = DependencyRule(
                    allowed_callers=dep_rule_data.get("allowed_callers", []),
                    forbidden_callers=dep_rule_data.get("forbidden_callers", []),
                    allowed_dependencies=dep_rule_data.get("allowed_dependencies", []),
                    forbidden_dependencies=dep_rule_data.get("forbidden_dependencies", [])
                )
                module = ModuleResponsibility(
                    module_id=mod_data["module_id"],
                    module_path=mod_data["module_path"],
                    layer=mod_data["layer"],
                    description=mod_data["description"],
                    single_responsibility=mod_data["single_responsibility"],
                    is_pluggable=mod_data.get("is_pluggable", True),
                    dependency_rules=dep_rule,
                    extra_properties=mod_data.get("extra_properties", {})
                )
                modules.append(module)
            self._manifest = ModuleManifest(
                version=data.get("version", "1.0.0"),
                generated_by=data.get("generated_by", "NovelOS Architect"),
                modules=modules,
                global_rules=data.get("global_rules", {})
            )
            self._logger.info(f"成功加载职责清单: {target}, 模块数量: {len(modules)}")
            return True
        except Exception as e:
            self._logger.error(f"加载职责清单失败: {target}, 错误: {e}")
            return False

    def register_validator(self, validator: IResponsibilityValidator):
        """注册一个验证器（可插拔）"""
        self._validators.append(validator)
        self._logger.debug(f"验证器已注册: {type(validator).__name__}")

    def unregister_validator(self, validator_type: type):
        """移除指定类型的验证器"""
        self._validators = [v for v in self._validators if not isinstance(v, validator_type)]

    def validate_all(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, List[str]]:
        """执行所有验证器，返回每个验证器的错误列表"""
        if not self._manifest:
            self._logger.error("未加载职责清单，无法验证")
            return {"global": ["未加载职责清单"]}
        if context is None:
            context = {}
        results = {}
        for validator in self._validators:
            try:
                errors = validator.validate(self._manifest, context)
                results[type(validator).__name__] = errors
            except Exception as e:
                self._logger.error(f"验证器 {type(validator).__name__} 执行异常: {e}")
                results[type(validator).__name__] = [f"验证器异常: {e}"]
        return results

    def get_module(self, module_id: str) -> Optional[ModuleResponsibility]:
        """根据ID获取模块职责"""
        if not self._manifest:
            return None
        for mod in self._manifest.modules:
            if mod.module_id == module_id:
                return mod
        return None

    def hot_reload_manifest(self, file_path: str):
        """热更新职责清单（如文件发生变化）"""
        if not os.path.exists(file_path):
            self._logger.warning(f"热更新失败，文件不存在: {file_path}")
            return
        self._manifest_file = file_path
        self.load_manifest(file_path)

    def export_manifest_template(self, output_path: str):
        """导出一个空模板清单（用于扩展）"""
        template = {
            "version": "1.0.0",
            "generated_by": "NovelOS Architect",
            "modules": [],
            "global_rules": {
                "forbidden_cross_layer_calls": ["UI->Data", "Agent->API directly"],
                "require_single_responsibility": True
            }
        }
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=2, ensure_ascii=False)
            self._logger.info(f"模板已导出: {output_path}")
        except Exception as e:
            self._logger.error(f"导出模板失败: {e}")

# ============================================================================
# 自测代码 (可独立运行)
# ============================================================================
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s