"""
32_架构治理/命名规范
职责：提供项目命名规范的检查、验证与建议服务。
依赖：logging、json、os（自测可能用到）
被调用：架构治理服务、代码生成器、CI检查流程
解决：确保所有命名符合NovelOS长期演化的命名约定，提高一致性
"""

import logging
import json
import os
from typing import Dict, Any, Optional, List, Tuple

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


class NamingConventions:
    """
    命名规范检查器
    可插拔设计：通过配置文件定义规则，支持热更新与扩展
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化命名规范检查器
        
        Args:
            config_path: 配置文件路径，默认使用同目录下的 naming_rules.json
        """
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "naming_rules.json")
        self.rules: Dict[str, Any] = self._load_config()
        logger.info("命名规范检查器初始化完成，配置路径：%s", self.config_path)

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件，若不存在则返回默认规则"""
        default_rules = {
            "directory": {"pattern": "^[0-9]+_[a-z0-9_]+$", "description": "目录名：数字前缀_小写字母数字下划线"},
            "file": {"pattern": "^[a-z][a-zA-Z0-9_]*\\.py$", "description": "文件名：小写开头，可含字母数字下划线，扩展名.py"},
            "class": {"pattern": "^[A-Z][a-zA-Z0-9]+$", "description": "类名：大写开头驼峰"},
            "function": {"pattern": "^[a-z][a-z0-9_]*$", "description": "函数名：小写加下划线"},
            "variable": {"pattern": "^[a-z][a-z0-9_]*$", "description": "变量名：小写加下划线，不以下划线开头"},
        }
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                rules = json.load(f)
                logger.info("已加载命名规则配置")
                return rules
        except FileNotFoundError:
            logger.warning("配置文件 %s 未找到，使用默认规则", self.config_path)
            return default_rules
        except json.JSONDecodeError as e:
            logger.error("配置文件解析错误: %s，使用默认规则", e)
            return default_rules

    def reload_config(self) -> None:
        """重新加载配置，支持热更新"""
        self.rules = self._load_config()
        logger.info("配置已热更新")

    def validate_name(self, name_type: str, name: str) -> Tuple[bool, str]:
        """
        通用命名验证
        
        Args:
            name_type: 命名类型 (directory, file, class, function, variable)
            name: 待验证的名称
        
        Returns:
            (是否合法, 错误信息)
        """
        rule = self.rules.get(name_type)
        if not rule:
            return False, f"未找到命名类型 '{name_type}' 的规则"
        import re
        pattern = rule.get("pattern", "")
        if not pattern:
            return False, "规则中缺少 pattern"
        if re.match(pattern, name):
            return True, ""
        else:
            desc = rule.get("description", name_type)
            return False, f"命名 '{name}' 不符合规则：{desc} (正则: {pattern})"

    def check_directory_name(self, dir_name: str) -> Tuple[bool, str]:
        """检查目录名"""
        return self.validate_name("directory", dir_name)

    def check_file_name(self, file_name: str) -> Tuple[bool, str]:
        """检查文件名（含扩展名）"""
        return self.validate_name("file", file_name)

    def check_class_name(self, class_name: str) -> Tuple[bool, str]:
        """检查类名"""
        return self.validate_name("class", class_name)

    def check_function_name(self, func_name: str) -> Tuple[bool, str]:
        """检查函数名"""
        return self.validate_name("function", func_name)

    def check_variable_name(self, var_name: str) -> Tuple[bool, str]:
        """检查变量名"""
        return self.validate_name("variable", var_name)

    def get_all_rules(self) -> Dict[str, Any]:
        """返回所有规则，供外部展示或文档生成"""
        return self.rules


# --------------------------------------------------------------------------
# 自测代码
# --------------------------------------------------------------------------
if __name__ == "__main__":
    # 实例化检查器
    checker = NamingConventions()
    print("=== 命名规范自测 ===")
    # 测试目录名
    test_dirs = ["01_utils", "utils", "01_Utils", "01_utils_v2"]
    for d in test_dirs:
        ok, msg = checker.check_directory_name(d)
        print(f"目录名 '{d}': {'PASS' if ok else 'FAIL'} - {msg if not ok else '合法'}")

    # 测试文件名
    test_files = ["naming_conventions.py", "NamingConventions.py", "naming-conventions.py", "naming_conventions.txt"]
    for f in test_files:
        ok, msg = checker.check_file_name(f)
        print(f"文件名 '{f}': {'PASS' if ok else 'FAIL'} - {msg if not ok else '合法'}")

    # 测试类名
    test_classes = ["NamingConventions", "namingConventions", "Naming_Conventions", "naming_conventions"]
    for c in test_classes:
        ok, msg = checker.check_class_name(c)
        print(f"类名 '{c}': {'PASS' if ok else 'FAIL'} - {msg if not ok else '合法'}")

    # 测试函数名
    test_funcs = ["check_name", "CheckName", "checkName", "check_name1"]
    for fu in test_funcs:
        ok, msg = checker.check_function_name(fu)
        print(f"函数名 '{fu}': {'PASS' if ok else 'FAIL'} - {msg if not ok else '合法'}")

    # 测试变量名
    test_vars = ["my_var", "_my_var", "myVar", "my_var123"]
    for v in test_vars:
        ok, msg = checker.check_variable_name(v)
        print(f"变量名 '{v}': {'PASS' if ok else 'FAIL'} - {msg if not ok else '合法'}")

    # 热更新模拟
    print("\n=== 模拟配置热更新 ===")
    checker.reload_config()
    print("所有规则:\n", json.dumps(checker.get_all_rules(), indent=2, ensure_ascii=False))