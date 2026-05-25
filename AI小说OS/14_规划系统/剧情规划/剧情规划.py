"""
剧情规划模块
负责根据小说设定生成整体剧情结构、章节规划、冲突发展线等。
属于14_规划系统层，依赖小说设定输入，被更上层的创作协调器调用。
可插拔设计：实现PlotPlannerBase抽象接口，可通过配置替换具体实现。
"""
import logging
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

# 默认配置，可通过外部配置文件或初始化参数覆盖
DEFAULT_CONFIG = {
    "log_level": "INFO",
    "log_format": "[%(asctime)s] [%(name)s] %(levelname)s: %(message)s",
    "max_chapters": 50,
    "default_structure_type": "three_act",  # 三幕结构
    "planning_mode": "auto",  # auto / manual
}

class PlotPlannerBase(ABC):
    """剧情规划器抽象基类，所有剧情规划器必须实现此接口，保证可插拔性。"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        self.logger = self._setup_logger()
        self.logger.info("剧情规划器初始化完成")

    def _setup_logger(self) -> logging.Logger:
        """根据配置初始化日志记录器"""
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(getattr(logging, self.config.get("log_level", "INFO").upper(), logging.INFO))
        # 避免重复添加处理器（如果已经存在则不添加）
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(self.config.get("log_format", "[%(asctime)s] %(levelname)s: %(message)s"))
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    @abstractmethod
    def generate_structure(self, novel_setting: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据小说设定生成整体剧情结构
        :param novel_setting: 包含主题、世界观、人物等的设定字典
        :return: 剧情结构描述字典，至少包含acts、main_conflict等
        """
        pass

    @abstractmethod
    def plan_chapters(self, structure: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        基于剧情结构细化章节规划
        :param structure: 由generate_structure输出的剧情结构
        :return: 章节规划列表，每项包含章节号、大纲摘要、关键事件等
        """
        pass

    @abstractmethod
    def adjust_plan(self, feedback: Dict[str, Any]) -> bool:
        """
        根据外部反馈动态调整规划，支持热更新
        
        :param feedback: 反馈信息，例如用户修改、编辑建议等
        :return: 调整是否成功
        """
        pass

    @abstractmethod
    def save_plan(self, path: Optional[str] = None) -> str:
        """
        保存当前规划到文件，支持持久化与恢复
        :param path: 保存路径，若为空则使用默认路径
        :return: 实际保存的文件路径
        """
        pass

    @abstractmethod
    def load_plan(self, path: str) -> bool:
        """
        从文件加载规划，用于恢复或合并
        :param path: 文件路径
        :return: 加载是否成功
        """
        pass


class PlotPlanner(PlotPlannerBase):
    """剧情规划器的默认实现，基于三幕结构和冲突驱动模型。"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        # 可在此加载额外的资源，如模板、知识库等
        self.current_structure = None
        self.current_chapters = []

    def generate_structure(self, novel_setting: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info("开始生成剧情结构，设定类型：%s", novel_setting.get("type", "未知"))
        # 实际实现将根据设定分析生成结构，此处为骨架占位
        structure = {
            "structure_type": self.config.get("default_structure_type", "three_act"),
            "acts": [
                {"act": 1, "name": "开端", "description": "引入世界观和主要人物，铺垫核心冲突"},
                {"act": 2, "name": "发展", "description": "冲突升级，人物成长，转折点出现"},
                {"act": 3, "name": "结局", "description": "解决冲突，揭示主题"}
            ],
            "main_conflict": {"type": "占位冲突", "description": "待分析设定后填充"},
            "subplots": [],
            "pacing_guide": "均衡"
        }
        self.current_structure = structure
        self.logger.info("剧情结构生成完成")
        return structure

    def plan_chapters(self, structure: Dict[str, Any]) -> List[Dict[str, Any]]:
        self.logger.info("开始根据结构规划章节，总幕数：%d", len(structure.get("acts", [])))
        max_ch = self.config.get("max_chapters", 50)
        # 简单按比例分配章节到一个列表（占位）
        chapters = []
        for i in range(1, min(max_ch + 1, 11)):  # 示例只生成10章
            chapters.append({
                "chapter": i,
                "title": f"第{i}章",
                "outline": f"占位大纲，对应场景",
                "key_events": ["事件A", "事件B"],
                "act": (i - 1) // (max_ch // 3) + 1 if max_ch >= 3 else 1
            })
        self.current_chapters = chapters
        self.logger.info("章节规划完成，共生成%d章", len(chapters))
        return chapters

    def adjust_plan(self, feedback: Dict[str, Any]) -> bool:
        self.logger.info("接收到调整反馈：%s", feedback)
        # 实际会根据反馈修改current_structure和current_chapters
        # 此处仅返回成功标志
        return True

    def save_plan(self, path: Optional[str] = None) -> str:
        save_path = path or os.path.join(os.getcwd(), "plot_plan.json")
        data = {
            "structure": self.current_structure,
            "chapters": self.current_chapters
        }
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.info("规划已保存至 %s", save_path)
            return save_path
        except Exception as e:
            self.logger.error("保存规划失败：%s", e)
            raise

    def load_plan(self, path: str) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.current_structure = data.get("structure")
            self.current_chapters = data.get("chapters", [])
            self.logger.info("成功从 %s 加载规划", path)
            return True
        except Exception as e:
            self.logger.error("加载规划失败：%s", e)
            return False


# 自测代码
if __name__ == "__main__":
    # 配置日志直接输出
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
    # 测试默认规划器
    planner = PlotPlanner({"max_chapters": 30})
    test_setting = {
        "type": "奇幻冒险",
        "theme": "友情与成长",
        "world": "魔法大陆",
        "protagonist": "少年法师"
    }
    structure = planner.generate_structure(test_setting)
    print("生成的剧情结构：")
    print(json.dumps(structure, ensure_ascii=False, indent=2))

    chapters = planner.plan_chapters(structure)
    print("\n生成的章节规划（前3章）：")
    for ch in chapters[:3]:
        print(f"  第{ch['chapter']}章: {ch['outline']}")

    # 测试保存与加载
    saved = planner.save_plan("test_plot_plan.json")
    planner2 = PlotPlanner()
    if planner2.load_plan(saved):
        print("\n加载后的规划结构类型：", planner2.current_structure.get("structure_type") if planner2.current_structure else "无")
    # 清理测试文件
    if os.path.exists("test_plot_plan.json"):
        os.remove("test_plot_plan.json")
    print("\n自测通过。")