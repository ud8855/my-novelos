"""
微瑕疵注入模块
用于在AI生成的文本中引入可控的微小瑕疵，以降低AI检测率。
可插拔设计：瑕疵类型通过插件方式注册，主注入器根据配置和概率执行。
配置化：所有参数从配置模块读取，支持运行时动态修改。
日志：所有操作记录日志，便于追踪和调试。
"""

import random
import logging
from typing import Callable, Dict, List, Optional
import importlib

logger = logging.getLogger(__name__)


class FlawInjector:
    """瑕疵注入器抽象接口，所有具体瑕疵类型需实现此接口"""
    def inject(self, text: str) -> str:
        """对输入文本应用瑕疵，返回修改后的文本"""
        raise NotImplementedError


class TypoInjector(FlawInjector):
    """模拟拼写错误：随机交换两个相邻字符"""
    def inject(self, text: str) -> str:
        if len(text) < 2:
            return text
        pos = random.randint(0, len(text) - 2)
        # 简单交换相邻字符
        return text[:pos] + text[pos+1] + text[pos] + text[pos+2:]


class PunctuationErrorInjector(FlawInjector):
    """标点错误：偶尔用逗号代替句号，或删除标点"""
    def inject(self, text: str) -> str:
        # 简化实现：随机替换最后一个句号为逗号
        if text.endswith('。'):
            return text[:-1] + '，'
        elif text.endswith('？'):
            return text[:-1] + '，'
        return text


class RepetitionInjector(FlawInjector):
    """不必要的重复：随机重复一个词"""
    def inject(self, text: str) -> str:
        words = text.split()
        if len(words) < 2:
            return text
        pos = random.randint(0, len(words) - 1)
        words.insert(pos, words[pos])
        return ' '.join(words)


class MicroFlawGenerator:
    """
    微瑕疵生成主类
    职责：根据配置加载瑕疵注入器，按概率对文本施加瑕疵。
    可插拔：内置注入器通过类注册，外部插件通过配置文件中的模块路径动态加载。
    配置化：所有行为参数均可通过config字典统一管理，可从统一配置模块导入。
    """
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化生成器
        :param config: 可选的配置字典，用于覆盖默认配置或从统一配置模块读取。
        """
        self.config = self._load_config(config)
        self.flaw_injectors: Dict[str, FlawInjector] = {}
        self._register_builtin_injectors()
        self._load_plugin_injectors()

    def _load_config(self, config: Optional[Dict]) -> Dict:
        """加载配置，优先使用传入的config，否则从默认值和统一配置模块读取"""
        default = {
            'flaw_probability': 0.05,           # 整体瑕疵触发概率
            'enabled_flaws': ['typo', 'punctuation_error'],  # 当前启用的瑕疵类型列表
            'flaw_plugins': []                  # 外部插件模块路径列表
        }
        if config:
            default.update(config)
        # 此处可集成NovelOS统一配置模块，例如:
        # try:
        #     from novelos.config import get_config
        #     unified = get_config().get('micro_flaw', {})
        #     default.update(unified)
        # except ImportError:
        #     pass
        return default

    def _register_builtin_injectors(self):
        """注册内置的瑕疵注入器"""
        self.register_injector('typo', TypoInjector())
        self.register_injector('punctuation_error', PunctuationErrorInjector())
        self.register_injector('repetition', RepetitionInjector())

    def _load_plugin_injectors(self):
        """从配置的插件列表中动态加载外部瑕疵注入器"""
        plugins = self.config.get('flaw_plugins', [])
        for module_path in plugins:
            try:
                module = importlib.import_module(module_path)
                # 约定插件模块实现register_plugin方法，接收本实例以便注册自定义注入器
                if hasattr(module, 'register_plugin'):
                    module.register_plugin(self)
                    logger.info(f"成功加载插件: {module_path}")
                else:
                    logger.warning(f"插件 {module_path} 未实现 register_plugin 接口，已跳过")
            except Exception as e:
                logger.error(f"加载瑕疵插件失败: {module_path}, 错误: {e}")

    def register_injector(self, name: str, injector: FlawInjector):
        """注册一个瑕疵注入器，供内部或插件调用"""
        if not isinstance(injector, FlawInjector):
            raise TypeError(f"注入器必须继承自 FlawInjector，但接收到 {type(injector)}")
        self.flaw_injectors[name] = injector
        logger.info(f"注册瑕疵注入器: {name}")

    def inject_flaws(self, text: str) -> str:
        """对外接口：对文本注入一次随机瑕疵，概率由flaw_probability控制"""
        if not text:
            return text

        probability = self.config.get('flaw_probability', 0)
        if random.random() > probability:
            return text  # 未触发

        enabled = self.config.get('enabled_flaws', [])
        # 可用且已注册的注入器
        available = [name for name in enabled if name in self.flaw_injectors]
        if not available:
            logger.debug("没有可用的瑕疵注入器")
            return text

        flaw_name = random.choice(