#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块路径：24_创世系统/规则创世/规则创世.py
所属层级：创世系统（世界构建层）
依赖：无（或可配置依赖其他规则模板库）
被调用：创世系统主控、世界编辑器、运行时系统
解决问题：根据配置和模板生成叙事世界的规则体系（物理法则、社会结构、魔法系统等），
         提供可插拔、可配置、可热更新的规则生成器骨架。
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------- 配置管理 ----------------------------
DEFAULT_CONFIG = {
    "rule_templates_dir": "templates/rules",          # 规则模板目录
    "output_dir": "output/rules",                     # 生成规则输出目录
    "log_level": "INFO",                              # 日志级别
    "log_format": "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
    "default_rule_categories": ["physics", "society", "magic"],  # 默认规则类别
    "enable_validation": True,                        # 是否启用规则验证
    "max_rules_per_category": 10,                     # 每类规则最大生成数量
}

class Config:
    """
    配置类，负责加载和提供配置。
    可插拔：未来可替换为从远程配置中心加载。
    """
    def __init__(self, config_path: Optional[str] = None):
        self._config = DEFAULT_CONFIG.copy()
        if config_path and os.path.exists(config_path):
            self.load_from_file(config_path)

    def load_from_file(self, path: str):
        """从JSON文件加载配置并合并"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                file_config = json.load(f)
            self._config.update(file_config)
        except Exception as e:
            logging.getLogger(__name__).warning(f"加载配置失败，使用默认配置: {e}")

    def get(self, key: str, default=None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        self._config[key] = value

# ---------------------------- 日志配置 ----------------------------
def setup_logging(config: Config):
    """根据配置设置全局日志"""
    level_name = config.get("log_level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    log_format = config.get("log_format", DEFAULT_CONFIG["log_format"])
    logging.basicConfig(level=level, format=log_format, stream=sys.stdout)

# ---------------------------- 核心生成器 ----------------------------
class RuleCreator:
    """
    规则创世引擎。
    支持热插拔：可动态替换规则生成算法（通过策略模式或插件机制）。
    单例模式（或工厂创建），确保全局唯一（可根据需要调整）。
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Optional[Config] = None, rebuild: bool = False):
        if hasattr(self, '_initialized') and not rebuild:
            return
        self._initialized = True

        self.config = config or Config()
        if not config:
            # 若未传入配置，使用默认并尝试加载环境变量中的配置文件
            if "RULE_CREATOR_CONFIG" in os.environ:
                self.config.load_from_file(os.environ["RULE_CREATOR_CONFIG"])

        setup_logging(self.config)
        self.logger = logging.getLogger(self.__class__.__name__)

        # 规则模板仓库（可扩展）
        self.rule_templates: Dict[str, Any] = {}
        self.generated_rules: Dict[str, List[Dict]] = {}  # 按类别存储已生成规则
        self._load_templates()

    def _load_templates(self):
        """加载规则生成模板（可热更新）"""
        tmpl_dir = self.config.get("rule_templates_dir")
        if not tmpl_dir or not os.path.isdir(tmpl_dir):
            self.logger.info("未配置规则模板目录，使用内置空模板")
            return
        try:
            for file in Path(tmpl_dir).glob("*.json"):
                with open(file, 'r', encoding='utf-8') as f:
                    category = file.stem
                    self.rule_templates[category] = json.load(f)
                    self.logger.debug(f"加载模板: {category}")
            self.logger.info(f"已加载 {len(self.rule_templates)} 个规则模板")
        except Exception as e:
            self.logger.error(f"加载模板失败: {e}")

    def reload_templates(self):
        """热更新：重新加载模板库"""
        self.rule_templates.clear()
        self._load_templates()

    def generate_rules(self, categories: Optional[List[str]] = None, custom_params: Optional[Dict] = None) -> Dict[str, List[Dict]]:
        """
        根据模板生成规则。
        参数:
            categories: 需要生成的类别列表，默认使用配置中的default_rule_categories
            custom_params: 自定义参数，用于覆盖模板中的占位符
        返回:
            按类别组织的规则字典
        """
        if categories is None:
            categories = self.config.get("default_rule_categories", [])
        params = custom_params or {}
        result = {}
        for cat in categories:
            template = self.rule_templates.get(cat)
            if not template:
                self.logger.warning(f"未找到类别 '{cat}' 的模板，跳过生成")
                continue
            # 这里是一个抽象的生成流程，实际可根据模板填充参数
            rules = self._generate_rules_for_category(cat, template, params)
            if rules:
                result[cat] = rules
                self.generated_rules[cat] = rules
        self.logger.info(f"生成规则完成，共 {sum(len(v) for v in result.values())} 条规则")
        return result

    def _generate_rules_for_category(self, category: str, template: Dict, params: Dict) -> List[Dict]:
        """
        内部生成逻辑：解析模板，替换变量，产生规则条目。
        这里提供一个简单的示例实现，实际应更复杂。
        """
        max_count = self.config.get("max_rules_per_category", 10)
        rules = []
        # 假设模板包含一个 "rules" 列表，每个元素有 "pattern" 和 "defaults"
        for i, rule_template in enumerate(template.get("rules", [])):
            if i >= max_count:
                break
            # 简单替换，未来可引入 jinja2 等模板引擎
            rule_dict = {"id": f"{category}_{i+1}", "category": category}
            for key, value in rule_template.get("defaults", {}).items():
                # 如果params中有对应键，则替换
                rule_dict[key] = params.get(key, value)
            rules.append(rule_dict)
        return rules

    def validate_rules(self, rules: Optional[Dict[str, List[Dict]]] = None) -> bool:
        """
        验证生成的规则是否完整、合法。
        可插拔：可接入外部验证器。
        """
        if not self.config.get("enable_validation", True):
            self.logger.info("规则验证已禁用")
            return True
        target = rules if rules is not None else self.generated_rules
        if not target:
            self.logger.warning("无可验证的规则")
            return False
        # 简化验证：检查是否有ID重复等
        all_ids = []
        for cat, rule_list in target.items():
            for rule in rule_list:
                rid = rule.get("id")
                if rid in all_ids:
                    self.logger.error(f"规则ID重复: {rid}")
                    return False
                all_ids.append(rid)
        self.logger.info(f"规则验证通过，共 {len(all_ids)} 条")
        return True

    def export_rules(self, output_format: str = "json", output_path: Optional[str] = None) -> str:
        """
        导出规则到文件，支持热插拔格式。
        """
        base_dir = self.config.get("output_dir", DEFAULT_CONFIG["output_dir"])
        out_path = output_path or os.path.join(base_dir, f"rules.{output_format}")
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        if output_format == "json":
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(self.generated_rules, f, ensure_ascii=False, indent=2)
        else:
            raise ValueError(f"不支持的输出格式: {output_format}")
        self.logger.info(f"规则已导出至: {out_path}")
        return out_path

    def reset(self):
        """重置生成状态，清空已生成规则"""
        self.generated_rules.clear()
        self.logger.info("规则生成器已重置")

# ---------------------------- 自测 ----------------------------
def self_test():
    """模块自测，验证基本功能"""
    print("==== 规则创世自测开始 ====")
    # 使用默认配置（不指定文件）
    config = Config()
    creator = RuleCreator(config=config)

    # 可选：生成几个简单规则
    # 因为没有真实模板，这里会生成空或少量
    print("当前模板:", creator.rule_templates)
    results = creator.generate_rules(categories=["physics", "society"])
    print("生成结果:", json.dumps(results, indent=2, ensure_ascii=False))

    # 验证
    if creator.validate_rules(results):
        print("规则验证通过")
    else:
        print("规则验证失败")

    # 导出（测试用临时目录）
    import tempfile
    tmpdir = tempfile.mkdtemp()
    config.set("output_dir", tmpdir)
    exported = creator.export_rules(output_format="json")
    print(f"规则已导出到: {exported}")

    # 重置
    creator.reset()
    print(f"重置后规则数量: {len(creator.generated_rules)}")
    print("==== 自测结束 ====")

if __name__ == "__main__":
    self_test()