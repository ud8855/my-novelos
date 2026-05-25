# -*- coding: utf-8 -*-
"""
上下文拼接模块
层：09_上下文系统
依赖：配置管理器（通过传入config dict），日志系统
被调用：上层 Agent、任务系统或其他需要组装上下文的模块
解决：将分散的上下文资源（对话、大纲、角色等信息）按可配置模板拼接成一个完整上下文字符串，支持截断与优先级管理
可插拔性：通过模板配置与截断策略注入实现灵活拼接
"""
import logging
from typing import Dict, Any, Optional, Callable, List

class ContextAssembler:
    """上下文拼接器，负责根据模板将上下文各部分拼接成最终输入模型的上下文文本"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化拼接器
        :param config: 配置字典，必须包含 'template' (str) 和可选 'max_length', 'truncation_strategy' 等
        """
        self.config = config
        self.template: str = config.get("template", "{context}")
        self.max_length: int = config.get("max_length", 4000)
        # 截断策略，默认为从尾部保留，可注入自定义函数
        self.truncation_strategy: Callable[[str, int], str] = config.get(
            "truncation_strategy", self._default_truncation
        )
        # 日志记录器
        self.logger = logging.getLogger(self.__class__.__name__)

    def assemble(self, context_parts: Dict[str, str]) -> str:
        """
        根据模板将上下文字典拼接为最终字符串
        :param context_parts: 键值对，键对应模板中的占位符，值为对应的文本片段
        :return: 拼接后的完整上下文，可能会被截断
        """
        try:
            # 使用模板填充
            filled = self.template.format(**context_parts)
        except KeyError as e:
            self.logger.error(f"上下文拼接缺少必要键: {e}")
            # 缺少键时尝试只填充存在的部分，用空字符串替代缺失的键
            filled = self.template
            for key in context_parts:
                filled = filled.replace(f"{{{key}}}", context_parts[key])
            # 清除未填充的占位符
            filled = self._clean_unfilled(filled)
        except Exception as e:
            self.logger.error(f"上下文拼接模板填充异常: {e}", exc_info=True)
            return ""

        # 长度控制
        if len(filled) > self.max_length:
            self.logger.debug(f"上下文长度 {len(filled)} 超过最大 {self.max_length}，执行截断")
            filled = self.truncation_strategy(filled, self.max_length)
        return filled

    def _clean_unfilled(self, template: str) -> str:
        """移除模板中尚未填充的占位符"""
        import re
        return re.sub(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}", "", template)

    def _default_truncation(self, text: str, max_len: int) -> str:
        """
        默认截断策略：保留尾部 max_len 个字符，前面添加省略提示
        """
        if len(text) <= max_len:
            return text
        self.logger.info("使用默认截断策略：保留尾部文本")
        truncated = text[-max_len:]
        return f"...(前文已省略)\n{truncated}"

    def set_truncation_strategy(self, strategy: Callable[[str, int], str]) -> None:
        """运行时更换截断策略，支持热插拔"""
        self.truncation_strategy = strategy
        self.logger.info("截断策略已更新")

    @staticmethod
    def default_config() -> Dict[str, Any]:
        """
        返回一个示例配置，便于快速测试
        """
        return {
            "template": (
                "【故事背景】\n{world_setting}\n\n"
                "【角色信息】\n{character_info}\n\n"
                "【大纲概要】\n{outline}\n\n"
                "【对话历史】\n{dialogue_history}\n\n"
                "【当前场景】\n{current_scene}"
            ),
            "max_length": 3000,
            "truncation_strategy": None  # 使用默认
        }

# 自测部分
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 准备配置
    config = ContextAssembler.default_config()

    # 创建拼接器
    assembler = ContextAssembler(config)

    # 模拟上下文字典
    test_parts = {
        "world_setting": "这是一个魔法与科技并存的世界，人类与精灵共享大陆。",
        "character_info": "主角：雷恩，20岁，冒险者，性格勇敢但有些冲动。",
        "outline": "雷恩将出发寻找失落的水晶，途中遇到神秘的旅伴。",
        "dialogue_history": "雷恩：我准备好了。\n精灵艾莉：小心森林中的陷阱。",
        "current_scene": "雷恩站在森林入口，夕阳染红了天空。"
    }

    # 执行拼接
    context = assembler.assemble(test_parts)
    print("=== 拼接结果 ===")
    print(context)
    print(f"=== 长度: {len(context)} ===")

    # 测试超长截断
    long_parts = {
        "world_setting": "很长" * 500,  # 1000字符
        "character_info": "角色" * 500,
        "outline": "大纲" * 500,
        "dialogue_history": "对话" * 500,
        "current_scene": "场景" * 500
    }
    context_long = assembler.assemble(long_parts)
    print("\n=== 超长上下文测试 ===")
    print(f"截断后长度: {len(context_long)}")
    print(context_long[:200] + "...")

    # 测试自定义截断策略（保留头部）
    def head_truncation(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len] + "\n...(后文已省略)"
    assembler.set_truncation_strategy(head_truncation)
    context_head = assembler.assemble(long_parts)
    print("\n=== 更换截断策略（保留头部） ===")
    print(f"截断后长度: {len(context_head)}")
    print(context_head[-200:] + "...")