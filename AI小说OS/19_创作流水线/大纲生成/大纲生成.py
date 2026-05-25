"""
大纲生成模块 - NovelOS创作流水线
生成小说大纲，支持可插拔策略，配置化参数，热更新。
"""
import logging
import json
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

# 配置日志
logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_CONFIG = {
    "max_chapters": 30,
    "min_chapters": 10,
    "outline_format": "detailed",  # detailed / simple
    "use_ai": True,
    "model_name": "default",
    "temperature": 0.7,
}


class OutlineGeneratorBase(ABC):
    """大纲生成器抽象基类，实现可插拔"""

    @abstractmethod
    def generate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """根据参数生成大纲，返回大纲字典"""
        pass


class BasicOutlineGenerator(OutlineGeneratorBase):
    """基础大纲生成器实现，基于规则或简单AI调用（骨架）"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        logger.info(f"Initialized BasicOutlineGenerator with config: {self.config}")

    def generate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成大纲
        params需包含:
            - premise: 故事前提
            - genre: 类型
            - style: 风格
            - characters: 角色信息 (optional)
        返回大纲结构:
            {
                "title": str,
                "chapters": [
                    {"number": int, "title": str, "summary": str, "key_events": []}
                ]
            }
        """
        logger.debug(f"Generating outline with params: {params}")
        # 骨架逻辑：返回一个模拟大纲，未来接入AI模型
        outline = self._mock_generate(params)
        logger.info(f"Generated outline with {len(outline.get('chapters', []))} chapters")
        return outline

    def _mock_generate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """模拟生成，实际开发中替换为模型调用"""
        num_chapters = min(self.config.get("max_chapters", 20), self.config.get("min_chapters", 5))
        title = params.get("premise", "Untitled Story")[:50]
        chapters = []
        for i in range(num_chapters):
            chapters.append({
                "number": i + 1,
                "title": f"Chapter {i+1}",
                "summary": f"Summary of chapter {i+1} based on premise: {title}",
                "key_events": [f"Event {i+1}-1", f"Event {i+1}-2"]
            })
        return {"title": title, "chapters": chapters}


# 对外暴露的默认生成器
default_generator = BasicOutlineGenerator()


def generate_outline(params: Dict[str, Any], generator: Optional[OutlineGeneratorBase] = None) -> Dict[str, Any]:
    """便捷接口函数"""
    gen = generator or default_generator
    return gen.generate(params)


if __name__ == "__main__":
    # 自测
    logging.basicConfig(level=logging.DEBUG)
    params = {
        "premise": "A young wizard discovers a hidden world.",
        "genre": "fantasy",
        "style": "descriptive",
        "characters": ["Harry", "Hermione"]
    }
    outline = generate_outline(params)
    print(json.dumps(outline, ensure_ascii=False, indent=2))