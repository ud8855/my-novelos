"""
审核规则引擎模块 - NovelOS 规则引擎层
负责定义、加载和执行内容审核规则
可插拔设计：规则通过配置文件注册，支持热加载和扩展
依赖：20_模型协同/ 或 21_API模型/（在规则需要模型时调用，但此处通过规则接口抽象）
被调用者：16_规则引擎/规则调度器 或 内容流处理管线
"""
import logging
import importlib
import traceback
from typing import Dict, Any, List, Optional, Set, Type

from pathlib import Path
from configparser import ConfigParser
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class ReviewRule(ABC):
    """
    审核规则抽象基类
    所有具体审核规则必须继承此类并实现 apply 方法
    """
    def __init__(self, config: Dict[str, Any]):
        """
        初始化规则，传入配置参数字典
        """
        self.config = config
        self.name = self.__class__.__name__
        logger.info(f"规则 {self.name} 初始化，配置：{config}")

    @abstractmethod
    def apply(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        对内容执行审核，返回审核结果
        输入: content 字典，至少包含 'text' 字段
        输出: {
            'passed': bool,
            'violations': List[str],  # 违规项描述
            'score': float,           # 可选，风险评分
            'details': Dict           # 可选，详细违规信息
        }
        """
        pass

    def __repr__(self):
        return f"<ReviewRule:{self.name}>"


class RuleEngineConfig:
    """
    规则引擎配置管理
    负责加载和解析规则配置文件
    """
    def __init__(self, config_path: str = None):
        self.config_path = config_path or str(Path(__file__).parent / "rules_config.ini")
        self.rules_registry: Dict[str, Type[ReviewRule]] = {}  # 规则类注册表
        self.active_rules: List[ReviewRule] = []  # 当前激活的规则实例列表
        self._load_configuration()

    def _load_configuration(self):
        """
        解析配置文件，构建规则注册表和激活规则列表
        配置文件格式示例：
        [Rules]
        active_rules = SensitiveContentRule, AdvertisementRule
        [RuleParameters]
        SensitiveContentRule.keywords = 暴力,色情
        AdvertisementRule.max_links = 3
        """
        parser = ConfigParser()
        if not Path(self.config_path).exists():
            logger.warning(f"规则配置文件 {self.config_path} 不存在，使用空配置")
            return

        parser.read(self.config_path, encoding='utf-8')

        # 获取激活规则名称列表
        if parser.has_option('Rules', 'active_rules'):
            active_names = [name.strip() for name in parser.get('Rules', 'active_rules').split(',') if name.strip()]
        else:
            active_names = []

        # 动态导入规则模块（假设规则类文件位于 rules/ 目录下）
        # 此处提供一种基于配置名的自动导入机制，但实际使用时可根据项目结构调整
        rule_classes = self._discover_rule_classes()

        # 根据激活列表实例化规则
        for class_name in active_names:
            cls = rule_classes.get(class_name)
            if not cls:
                logger.error(f"规则类 {class_name} 未找到，已跳过")
                continue

            # 获取该规则的参数（如果存在）
            params = {}
            if parser.has_section('RuleParameters'):
                for key, value in parser.items('RuleParameters'):
                    # 键格式: RuleClassName.param_name
                    if key.startswith(f"{class_name}."):
                        param_name = key[len(class_name)+1:]
                        params[param_name] = value

            try:
                instance = cls(params)
                self.active_rules.append(instance)
                logger.info(f"规则 {class_name} 已激活")
            except Exception as e:
                logger.error(f"实例化规则 {class_name} 失败: {e}")

    def _discover_rule_classes(self) -> Dict[str, Type[ReviewRule]]:
        """
        发现并返回所有可用的 ReviewRule 子类
        此实现从当前模块中搜索，但也可以扩展为扫描 plugins 目录
        """
        rule_classes = {}
        # 简单实现：从当前文件所在模块开始扫描已导入的规则类
        # 更完善的实现可通过 __subclasses__() 递归查找
        def find_subclasses(base_cls):
            sub = {}
            for cls in base_cls.__subclasses__():
                sub[cls.__name__] = cls
                sub.update(find_subclasses(cls))
            return sub

        # 获取所有 ReviewRule 子类
        classes = find_subclasses(ReviewRule)
        # 更新注册表（考虑多模块的情况）
        self.rules_registry.update(classes)
        return classes

    def reload(self):
        """
        重新加载配置并重置激活规则列表
        支持热更新
        """
        logger.info("重新加载规则引擎配置")
        self.active_rules = []
        self._load_configuration()

    def get_active_rules(self) -> List[ReviewRule]:
        return self.active_rules

    def register_rule(self, rule_class: Type[ReviewRule], params: Dict = None):
        """
        手动注册并激活一个规则
        """
        if params is None:
            params = {}
        try:
            instance = rule_class(params)
            self.active_rules.append(instance)
            self.rules_registry[rule_class.__name__] = rule_class
            logger.info(f"手动激活规则：{rule_class.__name__}")
        except Exception as e:
            logger.error(f"手动激活规则失败: {e}")


class ReviewPipeline:
    """
    审核管线：串联所有激活的规则，对内容逐一审核
    支持短路、聚合分数等策略
    """
    def __init__(self, engine_config: RuleEngineConfig):
        self.engine_config = engine_config
        self.rules = engine_config.get_active_rules()
        logger.info(f"审核管线已创建，激活规则数: {len(self.rules)}")

    def run(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行审核管线
        返回最终结果，包含是否通过和所有违规信息汇总
        """
        if not self.rules:
            logger.warning("审核管线无激活规则，默认放行")
            return {"passed": True, "violations": [], "details": []}

        all_violations = []
        all_details = []
        total_score = 0.0
        passed = True

        for rule in self.rules:
            try:
                result = rule.apply(content)
                if not isinstance(result, dict):
                    logger.error(f"规则 {rule.name} 返回了非字典结果：{result}")
                    continue
                # 提取违规信息
                if not result.get('passed', True):
                    passed = False
                    violations = result.get('violations', [])
                    if violations:
                        all_violations.extend(violations)
                # 记录详细信息
                details = result.get('details', {})
                if details:
                    all_details.append({"rule": rule.name, "details": details})
                # 累计评分（如果规则提供） 
                score = result.get('score', 0.0)
                total_score += score
            except Exception as e:
                logger.error(f"规则 {rule.name} 执行失败: {e}\n{traceback.format_exc()}")
                # 根据策略可选择是否因异常而拒绝内容；这里默认不阻断，但记录异常
                # 可配置化异常处理策略
                continue

        response = {
            "passed": passed,
            "violations": all_violations,
            "details": all_details,
            "score": total_score,
        }
        logger.info(f"审核管线完成，结果: passed={passed}, violations={len(all_violations)}")
        return response

    def update_rules(self):
        """
        更新规则列表以反映配置变更（热更新）
        """
        self.rules = self.engine_config.get_active_rules()
        logger.info("管线规则列表已更新")

    def add_rule(self, rule: ReviewRule):
        """
        动态添加一条规则到当前管线
        """
        self.rules.append(rule)
        logger.info(f"动态添加规则: {rule.name}")

    def remove_rule(self, rule_name: str):
        """
        动态移除规则
        """
        self.rules = [r for r in self.rules if r.name != rule_name]
        logger.info(f"动态移除规则: {rule_name}")


# ================== 以下部分为骨架自测代码 ==================

class DummyRule(ReviewRule):
    """测试用假规则：拦截包含敏感词的文本"""
    def apply(self, content: Dict[str, Any]) -> Dict[str, Any]:
        text = content.get('text', '')
        keywords = self.config.get('keywords', '').split(',')
        violations = [kw for kw in keywords if kw in text]
        passed = len(violations) == 0
        return {
            'passed': passed,
            'violations': [f'包含敏感词: {v}' for v in violations],
            'score': len(violations) * 0.5,
            'details': {'matched_keywords': violations}
        }


class MaxLengthRule(ReviewRule):
    """测试规则：限制最大长度"""
    def apply(self, content: Dict[str, Any]) -> Dict[str, Any]:
        text = content.get('text', '')
        max_len = int(self.config.get('max_length', 500))
        if len(text) > max_len:
            return {
                'passed': False,
                'violations': [f'文本长度超过限制 ({len(text)} > {max_len})'],
                'score': 1.0,
                'details': {'text_length': len(text)}
            }
        return {'passed': True, 'violations': [], 'score': 0.0, 'details': {}}


def create_test_config_file(path: str):
    """创建测试用配置文件"""
    config_content = """[Rules]
active_rules = DummyRule, MaxLengthRule

[RuleParameters]
DummyRule.keywords = 暴力,色情
MaxLengthRule.max_length = 100
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(config_content)


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 生成测试配置文件
    test_config_path = str(Path(__file__).parent / "test_rules_config.ini")
    create_test_config_file(test_config_path)

    print("=== 规则引擎自测开始 ===")

    # 1. 初始化配置引擎
    engine_config = RuleEngineConfig(test_config_path)
    print(f"激活规则: {[r.name for r in engine_config.get_active_rules()]}")

    # 2. 创建审核管线并运行测试用例
    pipeline = ReviewPipeline(engine_config)

    test_contents = [
        {"text": "这是一段正常文本，没有违规内容。", "metadata": {}},
        {"text": "杀戮和破坏，充满暴力", "metadata": {}},
        {"text": "这是一段包含色情描述的文本", "metadata": {}},
        {"text": "短文本", "metadata": {}},
        {"text": "很长" * 30, "metadata": {}},  # 长度超过100
    ]

    for idx, content in enumerate(test_contents):
        result = pipeline.run(content)
        print(f"\n测试 {idx+1}: 文本='{content['text'][:30]}...'")
        print(f"  通过: {result['passed']}, 违规: {result['violations']}, 评分: {result['score']:.2f}")

    # 3. 测试动态添加规则
    print("\n=== 测试动态添加规则 ===")
    custom_rule = DummyRule({"keywords": "广告"})
    pipeline.add_rule(custom_rule)
    result = pipeline.run({"text": "这是一条广告推广"})
    print(f"添加自定义规则后: 通过={result['passed']}, 违规={result['violations']}")

    # 4. 测试热重载配置
    print("\n=== 测试配置热重载 ===")
    # 修改配置文件，只保留 MaxLengthRule
    with open(test_config_path, 'w', encoding='utf-8') as f:
        f.write("""[Rules]
active_rules = MaxLengthRule

[RuleParameters]
MaxLengthRule.max_length = 50
""")
    engine_config.reload()
    pipeline.update_rules()
    result =