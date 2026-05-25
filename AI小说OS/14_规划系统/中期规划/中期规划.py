# -*- coding: utf-8 -*-
"""
NovelOS - 14_规划系统/中期规划/中期规划.py
层级: 14_规划系统
依赖: 15_上下文系统, 20_模型协同/21_API模型 (通过抽象接口, 不直接调用)
被调用: 由13_故事主线或上层调度器触发, 为写作Agent提供中期创作指导
功能: 将故事主线分解为可执行的中期章节规划, 管理角色弧、剧情转折、节奏控制
"""

import logging
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# --------------------- 接口定义 (可插拔) ---------------------
class IMidTermPlanner(ABC):
    """中期规划器抽象接口, 确保可插拔性"""
    @abstractmethod
    def generate_plan(self, context: Dict[str, Any]) -> "MidTermPlan":
        """基于上下文生成中期规划"""
        ...

    @abstractmethod
    def adjust_plan(self, plan: "MidTermPlan", feedback: Dict[str, Any]) -> "MidTermPlan":
        """根据反馈动态调整规划"""
        ...

    @abstractmethod
    def get_next_action(self, plan: "MidTermPlan", current_state: Dict[str, Any]) -> Dict[str, Any]:
        """获取下一步创作指令"""
        ...

# --------------------- 数据容器 ---------------------
@dataclass
class ChapterBlueprint:
    """章节蓝图数据"""
    chapter_id: str
    title_hint: str
    key_events: List[str] = field(default_factory=list)
    character_focus: List[str] = field(default_factory=list)
    plot_goals: List[str] = field(default_factory=list)
    emotional_tone: str = "neutral"
    estimated_words: int = 2000

@dataclass
class MidTermPlan:
    """中期规划数据容器"""
    story_id: str
    chapters: List[ChapterBlueprint] = field(default_factory=list)
    overall_tone: str = "neutral"
    pacing_strategy: str = "steady"
    main_characters_arc: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

# --------------------- 中期规划器实现 ---------------------
class MidTermPlanner(IMidTermPlanner):
    """中期规划器主类, 实现可插拔接口, 配置驱动, 日志完善"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化规划器
        :param config_path: 配置文件路径, 默认从环境变量或内置配置加载
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = self._load_config(config_path)
        self._setup_logging()
        self.logger.info("中期规划器初始化完成")
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """加载配置, 支持外部JSON文件"""
        default_config = {
            "max_chapters": 50,
            "chapter_min_words": 1000,
            "pacing_modes": ["fast", "steady", "slow"],
            "default_pacing": "steady",
            "enable_auto_adjust": True,
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": None
            }
        }
        
        # 尝试从指定路径或环境变量加载
        env_path = os.getenv("MIDTERM_PLANNER_CONFIG")
        path = config_path or env_path
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                # 合并配置
                merged = {**default_config, **user_config}
                self.logger.info(f"成功加载外部配置: {path}")
                return merged
            except Exception as e:
                self.logger.warning(f"加载配置失败: {e}, 使用默认配置")
                return default_config
        return default_config
    
    def _setup_logging(self):
        """根据配置设置日志"""
        log_config = self.config.get("logging", {})
        level = getattr(logging, log_config.get("level", "INFO").upper(), logging.INFO)
        fmt = log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        logging.basicConfig(level=level, format=fmt)
        if log_config.get("file"):
            fh = logging.FileHandler(log_config["file"], encoding='utf-8')
            fh.setLevel(level)
            fh.setFormatter(logging.Formatter(fmt))
            logging.getLogger().addHandler(fh)
    
    def generate_plan(self, context: Dict[str, Any]) -> MidTermPlan:
        """
        根据上下文生成中期规划
        实际逻辑需接入模型协同层, 当前返回骨架结构
        """
        self.logger.debug(f"开始生成中期规划, 上下文摘要: {str(list(context.keys()))}")
        
        # 示例: 从上下文提取story_id等
        story_id = context.get("story_id", "default_story")
        
        # TODO: 接入模型协同模块, 进行实际规划逻辑
        plan = MidTermPlan(
            story_id=story_id,
            overall_tone=context.get("tone", "neutral"),
            pacing_strategy=self.config.get("default_pacing", "steady")
        )
        
        # 生成占位章节蓝图
        chapter_count = min(context.get("target_chapters", 10), self.config.get("max_chapters", 50))
        for i in range(chapter_count):
            chap = ChapterBlueprint(
                chapter_id=f"ch_{i+1:03d}",
                title_hint=f"第{i+1}章",
                key_events=[f"事件_{i+1}_A", f"事件_{i+1}_B"],
                character_focus=context.get("main_characters", ["主角"])[:2],
                plot_goals=[f"目标_{i+1}"],
                emotional_tone=plan.overall_tone,
                estimated_words=max(self.config.get("chapter_min_words", 1000), 2000)
            )
            plan.chapters.append(chap)
        
        self.logger.info(f"中期规划生成完成, 共{len(plan.chapters)}章")
        return plan
    
    def adjust_plan(self, plan: MidTermPlan, feedback: Dict[str, Any]) -> MidTermPlan:
        """根据写作反馈动态调整规划, 支持热更新"""
        self.logger.debug(f"接收调整反馈: {feedback}")
        if not self.config.get("enable_auto_adjust", True):
            self.logger.info("自动调整已关闭, 返回原规划")
            return plan
        
        # TODO: 基于反馈修改章节蓝图, 调整节奏等
        plan.metadata["last_adjust_feedback"] = feedback
        self.logger.info("中期规划已根据反馈调整")
        return plan
    
    def get_next_action(self, plan: MidTermPlan, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """根据当前进度获取下一个创作指令"""
        current_chapter = current_state.get("current_chapter_id", "ch_001")
        try:
            idx = next(i for i, ch in enumerate(plan.chapters) if ch.chapter_id == current_chapter)
            next_chapter = plan.chapters[idx+1] if idx+1 < len(plan.chapters) else None
        except StopIteration:
            next_chapter = None
        
        action = {
            "action": "write_chapter",
            "target_chapter": next_chapter.chapter_id if next_chapter else None,
            "blueprint": next_chapter,
            "message": "继续下一章" if next_chapter else "已到达规划终点"
        }
        self.logger.debug(f"返回下一步动作: {action}")
        return action

# --------------------- 自测 ---------------------
if __name__ == "__main__":
    # 设置基础日志, 便于观察
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")
    
    print("="*50)
    print("中期规划模块自测开始")
    
    # 模拟上下文
    sample_context = {
        "story_id": "test_novel_001",
        "target_chapters": 5,
        "main_characters": ["李逍遥", "赵灵儿"],
        "tone": "adventure"
    }
    
    planner = MidTermPlanner()
    
    # 测试生成规划
    plan = planner.generate_plan(sample_context)
    print(f"生成规划: 故事ID={plan.story_id}, 章节数={len(plan.chapters)}")
    for ch in plan.chapters:
        print(f"  - {ch.chapter_id}: {ch.title_hint}, 情绪={ch.emotional_tone}")
    
    # 测试调整
    feedback = {"chapter_id": "ch_001", "reader_emotion": "engaged", "adjust_pacing": "fast"}
    adjusted_plan = planner.adjust_plan(plan, feedback)
    print(f"调整后元数据: {adjusted_plan.metadata}")
    
    # 测试获取下一步动作
    current_state = {"current_chapter_id": "ch_001"}
    action = planner.get_next_action(adjusted_plan, current_state)
    print(f"下一步动作: {action['message']}")
    
    print("自测完成")
    print("="*50)