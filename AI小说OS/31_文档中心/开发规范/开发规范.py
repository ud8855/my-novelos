# 31_文档中心/开发规范/开发规范.py
# 所属层：文档中心层
# 依赖：无外部模块，仅依赖Python标准库 logging, json, os
# 被调用：项目开发阶段，可由CI/CD、代码审查工具、IDE插件调用，用于检查代码是否符合NovelOS开发规范
# 解决问题：提供可配置、可扩展的开发规范检查能力，确保代码质量与架构一致性

import logging
import json
import os
from typing import Any, Dict, List, Optional


class DevelopmentSpecification:
    """开发规范检查器骨架 —— 可插拔、配置化、带日志 —— 当前阶段仅实现接口与占位逻辑"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化开发规范检查器
        :param config: 自定义配置字典；若为None，则从默认配置文件或环境变量加载
        """
        # 配置加载
        self.config: Dict[str, Any] = config or self._load_default_config()
        # 日志初始化
        self._setup_logging()
        self.logger.info("开发规范检查器已初始化")
        # 规范化规则（未来可动态加载规则模块）
        self.rules: List[Dict[str, Any]] = []

    def _load_default_config(self) -> Dict[str, Any]:
        """从默认配置文件或环境变量加载配置"""
        default_config = {
            "log_level": "INFO",          # 日志级别
            "log_file": None,             # 日志文件路径，None表示仅控制台输出
            "rules_config_path": None,    # 规则配置文件路径，None使用内置规则
        }
        # 尝试从环境变量覆盖
        for key in default_config:
            env_val = os.environ.get(f"NOVELOS_DEVSPEC_{key.upper()}")
            if env_val is not None:
                default_config[key] = env_val
        # 若存在规则配置文件则加载
        if default_config["rules_config_path"] and os.path.exists(default_config["rules_config_path"]):
            with open(default_config["rules_config_path"], 'r', encoding='utf-8') as f:
                rules_data = json.load(f)
                default_config["rules"] = rules_data.get("rules", [])
        else:
            default_config["rules"] = []  # 后期可内置默认规则集
        return default_config

    def _setup_logging(self):
        """配置日志系统"""
        self.logger = logging.getLogger("NovelOS.DevSpec")
        level = getattr(logging, self.config.get("log_level", "INFO").upper(), logging.INFO)
        self.logger.setLevel(level)
        formatter = logging.Formatter(
            '[%(asctime)s][%(name)s][%(levelname)s] %(message)s'
        )
        # 如果配置了日志文件，添加文件处理器
        log_file = self.config.get("log_file")
        if log_file:
            fh = logging.FileHandler(log_file, encoding='utf-8')
            fh.setLevel(level)
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)
        # 添加控制台处理器
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def load_rules(self) -> None:
        """加载规则定义（从配置文件或内置规则集）"""
        config_rules = self.config.get("rules", [])
        if config_rules:
            self.rules = config_rules
        else:
            # 占位：将来加载内置的基础规则集
            self.rules = [
                {"id": "NO_DUPLICATE", "level": "ERROR", "description": "禁止重复功能"},
                {"id": "NO_CROSS_LAYER", "level": "ERROR", "description": "禁止跨层污染"},
                # 更多规则...
            ]
        self.logger.info(f"已加载 {len(self.rules)} 条开发规范规则")

    def check_file(self, file_path: str) -> List[Dict[str, Any]]:
        """
        对单个文件执行规范检查（骨架，暂返回空列表）
        :param file_path: 待检查的源代码文件路径
        :return: 违反规范列表，每个元素包含 rule_id, message, line 等
        """
        self.logger.debug(f"检查文件: {file_path}")
        # 实际检查逻辑将在后续阶段实现
        violations = []
        # 示例：检查文件名是否规范
        # 此处仅占位返回
        return violations

    def check_project(self, project_root: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        对整个项目执行规范检查
        :param project_root: 项目根目录
        :return: 以文件路径为键，违规列表为值的字典
        """
        self.logger.info(f"开始项目级规范检查: {project_root}")
        results = {}
        # 遍历文件（占位：仅遍历.py文件）
        for root, dirs, files in os.walk(project_root):
            for file in files:
                if file.endswith('.py'):
                    full_path = os.path.join(root, file)
                    violations = self.check_file(full_path)
                    if violations:
                        results[full_path] = violations
        self.logger.info(f"检查完成，发现 {len(results)} 个文件存在违规")
        return results

    def report(self, violations: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        生成违规报告（占位实现简单文本）
        :param violations: check_project 返回的结果
        :return: 格式化的报告字符串
        """
        if not violations:
            return "未发现任何违反开发规范的问题。"
        lines = ["开发规范检查报告:"]
        for file, vlist in violations.items():
            lines.append(f"文件: {file}")
            for v in vlist:
                lines.append(f"  [{v.get('rule_id', 'UNKNOWN')}] {v.get('message', '无描述')} (行: {v.get('line', '?')})")
        return '\n'.join(lines)


# 自测模块
if __name__ == "__main__":
    # 创建默认配置的检查器实例
    checker = DevelopmentSpecification()
    checker.load_rules()

    # 模拟检查当前目录（不包含子目录，仅是示例）
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建一个非法示例文件（空文件，检查可能无违规）
        test_file = os.path.join(tmpdir, "test.py")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("# 测试文件\nprint('hello')\n")
        # 执行检查
        result = checker.check_project(tmpdir)
        # 输出报告
        print(checker.report(result))

    print("自测完成：开发规范骨架模块运行正常。")