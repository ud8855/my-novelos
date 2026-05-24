"""
模块依赖规则检查器
所属层: 32_架构治理
职责: 验证模块间的依赖关系是否符合架构规则（如层间依赖约束、循环依赖检测）
依赖: 无强制外部依赖，可集成 22_日志系统 和 23_配置管理
被调用者: CI流水线、代码审查工具、架构守护脚本
"""
import json
import logging
import os
from typing import List, Dict, Any, Callable, Optional

# 默认日志器，允许外部替换
logger = logging.getLogger("ModuleDependencyChecker")


def set_logger(custom_logger: logging.Logger) -> None:
    """可插拔：替换全局日志器"""
    global logger
    logger = custom_logger


class DependencyViolation:
    """依赖违规记录"""
    def __init__(self, module_name: str, dependency: str, rule: str, detail: str = ""):
        self.module_name = module_name
        self.dependency = dependency
        self.rule = rule
        self.detail = detail

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module": self.module_name,
            "dependency": self.dependency,
            "rule": self.rule,
            "detail": self.detail
        }

    def __repr__(self):
        return f"<Violation: {self.module_name} -> {self.dependency} ({self.rule})>"


# 默认层依赖规则：定义“允许的下层依赖”，key为当前层，value为允许依赖的层集合
# 层名称需与项目一级目录匹配
DEFAULT_LAYER_RULES = {
    "10_核心基础设施": {"10_核心基础设施"},                     # 核心只依赖自己
    "20_模型协同": {"10_核心基础设施", "20_模型协同"},         # 可依赖核心和自身
    "21_API模型": {"10_核心基础设施", "20_模型协同", "21_API模型"},
    "22_日志系统": {"10_核心基础设施"},
    "23_配置管理": {"10_核心基础设施"},
    "30_多Agent协同": {"10_核心基础设施", "20_模型协同", "30_多Agent协同"},
    "31_场景引擎": {"10_核心基础设施", "30_多Agent协同", "31_场景引擎"},
    "32_架构治理": {"10_核心基础设施"}                        # 架构治理应独立，可访问核心
    # 其他层按需添加
}


class ModuleDependencyChecker:
    """
    模块依赖规则检查器
    支持从配置文件加载规则、注册自定义规则，实现热插拔检查逻辑
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, config_file: Optional[str] = None):
        """
        初始化检查器
        :param config: 直接传入配置字典（优先级高于文件）
        :param config_file: 配置文件路径（JSON格式）
        """
        self.config = {}
        self.layer_rules: Dict[str, set] = {}
        self.custom_rules: List[Callable] = []
        self._load_config(config, config_file)
        # 应用默认层规则，可被配置覆盖
        self.layer_rules = DEFAULT_LAYER_RULES.copy()
        if self.config.get("layer_rules"):
            # 配置中的规则覆盖或合并
            for layer, allowed in self.config["layer_rules"].items():
                self.layer_rules[layer] = set(allowed)

        logger.info(f"模块依赖检查器初始化完成，已加载 {len(self.layer_rules)} 层级规则")

    def _load_config(self, config: Optional[Dict[str, Any]], config_file: Optional[str]) -> None:
        """加载配置，优先使用传入的config字典"""
        if config:
            self.config = config
        elif config_file and os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.debug(f"从文件加载配置: {config_file}")
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
        else:
            logger.debug("使用空配置")

    def add_rule(self, rule_func: Callable[..., List[DependencyViolation]]) -> None:
        """
        注册自定义依赖检查规则
        :param rule_func: 可调用对象，接收参数 (module_name, dependencies_list, context) -> List[DependencyViolation]
        """
        self.custom_rules.append(rule_func)
        logger.debug(f"注册自定义规则: {rule_func.__name__}")

    def remove_rule(self, rule_func: Callable) -> None:
        """移除自定义规则"""
        if rule_func in self.custom_rules:
            self.custom_rules.remove(rule_func)
            logger.debug(f"移除规则: {rule_func.__name__}")

    def check_module(self, module: Dict[str, Any], all_modules: List[Dict[str, Any]] = None) -> List[DependencyViolation]:
        """
        检查单个模块的依赖
        :param module: 模块信息字典，至少需包含 'name', 'layer', 'dependencies'（依赖模块名列表）
        :param all_modules: 所有模块列表，用于上下文敏感规则（如循环依赖检测）
        :return: 违规列表
        """
        violations = []
        module_name = module.get("name", "unknown")
        module_layer = module.get("layer", "")
        dependencies = module.get("dependencies", [])
        if not isinstance(dependencies, list):
            logger.warning(f"模块 {module_name} 的依赖数据格式错误，已忽略")
            return violations

        # 1. 执行默认层级规则检查
        if module_layer and dependencies:
            allowed_layers = self.layer_rules.get(module_layer)
            if allowed_layers is not None:
                for dep in dependencies:
                    # 获取被依赖模块的层，如果在all_modules中能找到
                    dep_layer = self._find_module_layer(dep, all_modules) if all_modules else None
                    if dep_layer and dep_layer not in allowed_layers:
                        violations.append(DependencyViolation(
                            module_name, dep, "layer_rule",
                            f"模块 {module_name} (层: {module_layer}) 不能依赖 {dep} (层: {dep_layer})"
                        ))
                        logger.warning(f"层级违规: {module_name} -> {dep}")
            else:
                logger.debug(f"层 {module_layer} 未在规则中定义，跳过层级检查")

        # 2. 执行全局规则：循环依赖检测（需要全量模块信息）
        if all_modules:
            cyclic_violations = self._check_cyclic_dependency(module_name, dependencies, all_modules)
            violations.extend(cyclic_violations)

        # 3. 执行所有注册的自定义规则
        for rule_func in self.custom_rules:
            try:
                result = rule_func(module_name, dependencies, module, all_modules)
                if isinstance(result, list):
                    violations.extend(result)
            except Exception as e:
                logger.exception(f"自定义规则 {rule_func.__name__} 执行出错: {e}")

        return violations

    def check_all(self, modules: List[Dict[str, Any]]) -> List[DependencyViolation]:
        """检查所有模块
        :param modules: 模块信息列表，每个模块应包含 'name', 'layer', 'dependencies'
        :return: 所有违规记录
        """
        all_violations = []
        # 先构建模块名到层的快速查找，便于检查
        module_map = {m['name']: m for m in modules}
        for module in modules:
            violations = self.check_module(module, modules)
            all_violations.extend(violations)
        return all_violations

    def _find_module_layer(self, module_name: str, all_modules: List[Dict[str, Any]]) -> Optional[str]:
        """从模块列表中查找模块所属层"""
        if not all_modules:
            return None
        for m in all_modules:
            if m.get("name") == module_name:
                return m.get("layer")
        return None

    def _check_cyclic_dependency(self, module_name: str, dependencies: List[str], all_modules: List[Dict]) -> List[DependencyViolation]:
        """简单的循环依赖检测：检查依赖链中是否出现当前模块（直接或间接）"""
        # 这里仅实现直接或间接检测的简化版本，实际项目可采用图算法
        violations = []
        # 检查直接循环
        if module_name in dependencies:
            violations.append(DependencyViolation(
                module_name, module_name, "cyclic_dependency",
                f"模块 {module_name} 直接依赖自身"
            ))
            return violations

        # 简单间接循环检测：依赖的模块如果也依赖当前模块
        for dep in dependencies:
            dep_mod = self._find_module_by_name(dep, all_modules)
            if dep_mod and module_name in dep_mod.get("dependencies", []):
                violations.append(DependencyViolation(
                    module_name, dep, "cyclic_dependency",
                    f"模块 {module_name} 与 {dep} 形成直接循环"
                ))
        return violations

    def _find_module_by_name(self, name: str, all_modules: List[Dict]) -> Optional[Dict]:
        """根据名称查找模块字典"""
        for m in all_modules:
            if m.get("name") == name:
                return m
        return None


# ------------------------- 自测部分 -------------------------
def run_self_test():
    """模块依赖规则自测"""
    # 配置日志输出到控制台
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    test_logger = logging.getLogger("ModuleDependencyChecker")
    set_logger(test_logger)

    # 模拟项目模块数据
    sample_modules = [
        {"name": "core.utils", "layer": "10_核心基础设施", "dependencies": []},
        {"name": "core.logging", "layer": "10_核心基础设施", "dependencies": ["core.utils"]},  # 合法
        {"name": "api.client", "layer": "21_API模型", "dependencies": ["core.utils", "coordination.agent"]},  # 依赖20层，非法
        {"name": "coordination.agent", "layer": "20_模型协同", "dependencies": ["core.logging"]},  # 合法
        {"name": "coordination.registry", "layer": "20_模型协同", "dependencies": ["coordination.agent"]},  # 合法
        {"name": "gov.checker", "layer": "32_架构治理", "