import logging
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

# 配置模块（假设存在全局配置管理）
try:
    from novelos.config import get_config
except ImportError:
    # 自测时降级
    def get_config(key: str, default=None):
        return default

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MythologyGenerator")


class MythologyGenerator:
    """
    神话生成器：负责根据用户指定的主题、风格、要素等，生成小说世界观中的创世神话。
    
    可插拔特性：支持通过配置切换不同的生成策略（模板填充、AI调用、混合等）。
    所有模型调用通过 20_模型协同 或 21_API模型 的统一接口进行，不在本模块内直接实例化模型。
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化神话生成器。

        :param config: 可选的配置字典，若未提供则从全局配置中读取 'myth_generator' 部分。
        """
        self.config = config if config is not None else get_config("myth_generator", {})
        self.strategy = self.config.get("strategy", "template")  # 默认使用模板策略
        self.template_dir = Path(self.config.get("template_dir", "./templates/myths"))
        self.model_config = self.config.get("model_config", {})  # 用于传递给统一模型接口的参数
        logger.info(f"MythologyGenerator 初始化，策略={self.strategy}，模板目录={self.template_dir}")

    def generate_myth(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成神话故事。根据当前策略调用相应的生成逻辑。

        :param parameters: 生成参数，例如：
            - theme: 主题（如'光明与黑暗'）
            - style: 风格（如'史诗'）
            - entities: 包含的神话实体列表
            - length: 期望长度
        :return: 生成结果字典，包含 'myth_text' 字段及可能的元数据。
        """
        logger.info(f"生成神话，参数: {parameters}")
        if self.strategy == "template":
            return self._generate_by_template(parameters)
        elif self.strategy == "ai":
            return self._generate_by_ai(parameters)
        elif self.strategy == "hybrid":
            return self._generate_hybrid(parameters)
        else:
            error_msg = f"未知的生成策略: {self.strategy}"
            logger.error(error_msg)
            return {"error": error_msg}

    def _generate_by_template(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于模板的生成方法：使用预定义的叙事模板和插槽填充。
        
        :param parameters: 生成参数
        :return: 结果字典
        """
        logger.debug("使用模板策略生成神话")
        # 1. 加载合适的模板（根据 theme 或 style）
        template = self._load_template(parameters.get("theme", "default"))
        # 2. 填充模板中的占位符
        myth_text = self._fill_template(template, parameters)
        # 3. 后处理（如格式调整）
        myth_text = self._postprocess(myth_text)
        return {"myth_text": myth_text, "strategy": "template", "parameters": parameters}

    def _generate_by_ai(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        基于AI模型的生成方法：通过统一模型接口调用大语言模型生成神话。
        
        :param parameters: 生成参数
        :return: 结果字典
        """
        logger.debug("使用AI策略生成神话")
        # 构建Prompt，调用统一接口
        prompt = self._build_prompt(parameters)
        try:
            from novelos.modules.model_coordination import call_model
            response = call_model(prompt, config=self.model_config)
            myth_text = response.get("text", "")
        except ImportError:
            # 自测时模拟
            myth_text = f"[模拟AI生成] 根据{parameters}生成的创世神话..."
        myth_text = self._postprocess(myth_text)
        return {"myth_text": myth_text, "strategy": "ai", "prompt": prompt}

    def _generate_hybrid(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        混合生成：先用模板生成草稿，再调用AI进行润色或扩展。
        
        :param parameters: 生成参数
        :return: 结果字典
        """
        logger.debug("使用混合策略生成神话")
        # 首先生成模板底稿
        draft_result = self._generate_by_template(parameters)
        draft_text = draft_result.get("myth_text", "")
        # 再调用AI润色
        refined_parameters = {**parameters, "draft_text": draft_text}
        ai_result = self._generate_by_ai(refined_parameters)
        final_text = ai_result.get("myth_text", draft_text)
        return {"myth_text": final_text, "strategy": "hybrid", "draft": draft_text}

    def _load_template(self, theme: str) -> str:
        """
        从模板目录加载指定主题的模板文件。
        
        :param theme: 主题标识
        :return: 模板字符串
        """
        template_file = self.template_dir / f"{theme}.txt"
        if not template_file.exists():
            logger.warning(f"模板文件不存在: {template_file}，使用默认模板")
            template_file = self.template_dir / "default.txt"
        try:
            with open(template_file, "r", encoding="utf-8") as f:
                template = f.read()
            logger.debug(f"加载模板: {template_file}")
            return template
        except Exception as e:
            logger.error(f"加载模板失败: {e}")
            return "在远古，{entity}创造了世界。"

    def _fill_template(self, template: str, parameters: Dict[str, Any]) -> str:
        """
        使用参数替换模板中的占位符（格式：{key}）。
        
        :param template: 模板字符串
        :param parameters: 参数字典
        :return: 填充后的文本
        """
        # 安全的格式化，避免缺失参数导致KeyError
        from string import Formatter
        result = template
        # 只替换提供的键，缺失的保留原样
        for key, value in parameters.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    def _postprocess(self, text: str) -> str:
        """
        后处理文本：去除多余空白、统一标点等。
        
        :param text: 原始文本
        :return: 清理后的文本
        """
        # 简单处理，实际可扩展
        cleaned = text.strip()
        return cleaned

    def _build_prompt(self, parameters: Dict[str, Any]) -> str:
        """
        根据参数构建发送给AI模型的Prompt。
        
        :param parameters: 生成参数
        :return: Prompt字符串
        """
        # TODO: 使用模板化的Prompt管理，此处简化为直接拼接
        prompt_template = (
            "请创作一段创世神话。主题：{theme}。风格：{style}。包含以下元素：{entities}。"
            "长度要求：{length}字左右。"
        )
        prompt = prompt_template.format(
            theme=parameters.get("theme", "万物起源"),
            style=parameters.get("style", "史诗"),
            entities="、".join(parameters.get("entities", ["混沌", "光明"])),
            length=parameters.get("length", 300)
        )
        return prompt

    def switch_strategy(self, strategy: str):
        """
        运行时切换生成策略（支持热插拔）。
        
        :param strategy: 新策略名称 (template, ai, hybrid)
        """
        if strategy not in ("template", "ai", "hybrid"):
            logger.error(f"无效的策略名称: {strategy}")
            return
        self.strategy = strategy
        logger.info(f"策略已切换为: {strategy}")

    def reload_config(self):
        """重新加载配置，实现运行时配置热更新。"""
        self.config = get_config("myth_generator", {})
        self.strategy = self.config.get("strategy", self.strategy)
        self.template_dir = Path(self.config.get("template_dir", self.template_dir))
        self.model_config = self.config.get("model_config", self.model_config)
        logger.info("神话生成器配置已重新加载")


def self_test():
    """
    自测函数：演示神话生成模块的基本功能。
    """
    print("=== 神话生成模块自测 ===")
    gen = MythologyGenerator({"strategy": "template", "template_dir": "./test_templates"})
    # 创建测试模板目录
    test_dir = Path("./test_templates")
    test_dir.mkdir(exist_ok=True)
    with open(test_dir / "default.txt", "w", encoding="utf-8") as f:
        f.write("在{entity}的指引下，{antagonist}与{protagonist}展开了永恒的战争。")
    
    parameters = {
        "theme": "光明与黑暗",
        "entity": "创世神",
        "antagonist": "暗影领主",
        "protagonist": "圣光之子"
    }
    result = gen.generate_myth(parameters)
    print("生成结果:", json.dumps(result, ensure_ascii=False, indent=2))
    
    # 切换策略测试
    gen.switch_strategy("ai")
    # 模拟AI生成（由于模块环境可能无统一接口，会用模拟数据）
    result2 = gen.generate_myth(parameters)
    print("AI策略结果:", json.dumps(result2, ensure_ascii=False, indent=2))
    
    # 清理测试目录
    import shutil
    shutil.rmtree(test_dir, ignore_errors=True)
    print("=== 自测完成 ===")


if __name__ == "__main__":
    self_test()