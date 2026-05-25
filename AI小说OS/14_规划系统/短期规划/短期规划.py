from __future__ import annotations
import logging
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

# 配置日志（可插拔：允许外部覆盖handler）
logger = logging.getLogger("NovelOS.Planning.ShortTerm")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

class ShortTermPlannerConfig:
    """短期规划器配置（配置化：从字典/配置文件/环境变量加载）"""
    def __init__(self, config_dict: Optional[Dict[str, Any]] = None):
        # 默认配置
        self.max_steps: int = 5                # 单次规划最大步骤数
        self.context_window: int = 2048        # 上下文窗口大小（token）
        self.temperature: float = 0.8          # 模型温度
        self.model_name: str = "gpt-4"         # 默认模型名称
        self.fallback_model: str = "gpt-3.5-turbo"  # 降级模型
        self.enable_reflection: bool = True    # 是否启用自我反思
        self.reflection_depth: int = 2         # 反思深度

        if config_dict:
            self.update(config_dict)

    def update(self, config_dict: Dict[str, Any]) -> None:
        """更新配置（支持热更新）"""
        for key, value in config_dict.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.debug(f"配置更新: {key} = {value}")
            else:
                logger.warning(f"未知配置项: {key}")

    @classmethod
    def from_file(cls, filepath: str) -> "ShortTermPlannerConfig":
        """从JSON文件加载配置"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                config_dict = json.load(f)
            return cls(config_dict)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}，使用默认配置")
            return cls()

class BasePlanner(ABC):
    """所有规划器的抽象基类（保证可插拔）"""
    @abstractmethod
    def plan(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成规划步骤
        
        Args:
            context: 包含当前状态、目标、约束等信息的上下文字典
        
        Returns:
            规划步骤列表，每个步骤为一个字典
        """
        pass

    @abstractmethod
    def can_handle(self, context: Dict[str, Any]) -> bool:
        """判断当前规划器是否可以处理该场景（用于动态选择）"""
        pass

class ShortTermPlanner(BasePlanner):
    """短期规划器：将中期目标分解为可立即执行的微观步骤（单一职责）"""
    
    def __init__(self, config: Optional[ShortTermPlannerConfig] = None):
        self.config = config or ShortTermPlannerConfig()
        self._model_interface = None  # 模型调用接口，由外部注入（遵守跨层污染规则）
        self._fallback_planner = None # 备用规划器（热插拔）
        logger.info("短期规划器初始化完成，配置: %s", self.config.__dict__)
    
    def set_model_interface(self, model_interface: Any) -> None:
        """注入模型调用接口（通过20_模型协同/21_API模型获得）"""
        self._model_interface = model_interface
        logger.debug("模型接口已注入")
    
    def set_fallback_planner(self, planner: BasePlanner) -> None:
        """设置备用规划器（热插拔支持）"""
        self._fallback_planner = planner
        logger.debug("备用规划器已设置")
    
    def plan(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """短期规划主入口
        
        职责: 接收当前写作上下文（如角色状态、剧情位置、伏笔信息），
              生成不超过max_steps个可执行写作步骤。
              严格调用模型协同层，不直接访问API或数据库。
        
        Args:
            context: {
                "current_chapter": int,
                "scene_summary": str,
                "character_states": dict,
                "pending_foreshadowings": list,
                "medium_term_goal": str,
                ...
            }
        Returns:
            steps: [
                {
                    "step_id": "step_001",
                    "action": "write_dialogue",
                    "description": "描写主角与配角的对话，引出伏笔A",
                    "expected_length": 500,
                    "dependencies": [],
                    "model_prompt": "..."  # 内部使用，不暴露给UI
                },
                ...
            ]
        """
        logger.info("开始短期规划，上下文摘要: %s", context.get("scene_summary", "无"))
        
        # 检查模型接口是否可用
        if self._model_interface is None:
            logger.error("模型接口未注入，无法规划")
            raise RuntimeError("ShortTermPlanner需要模型接口，请调用set_model_interface()")
        
        steps = []
        try:
            # 1. 构建规划提示词（通过模板化Prompt，此处仅为示例结构）
            plan_prompt = self._build_planning_prompt(context)
            
            # 2. 调用模型生成规划（假设 model_interface.generate 返回结构化数据）
            response = self._model_interface.generate(
                prompt=plan_prompt,
                model_name=self.config.model_name,
                temperature=self.config.temperature,
                max_tokens=1024
            )
            # 3. 解析响应为步骤列表（解析逻辑待实现）
            raw_steps = self._parse_response(response)
            
            # 4. 验证和修正步骤数量
            if len(raw_steps) > self.config.max_steps:
                logger.warning("规划步骤超过上限%d，截断至%d", self.config.max_steps, self.config.max_steps)
                raw_steps = raw_steps[:self.config.max_steps]
            
            # 5. 为每个步骤添加唯一ID和依赖处理
            for i, step_data in enumerate(raw_steps):
                step_id = f"step_{i+1:03d}"
                step = {
                    "step_id": step_id,
                    "action": step_data.get("action", "write"),
                    "description": step_data.get("description", ""),
                    "expected_length": step_data.get("expected_length", 200),
                    "dependencies": step_data.get("dependencies", []),
                    "model_prompt": step_data.get("prompt", "")
                }
                steps.append(step)
            
            # 可选：自我反思修正（如果启用）
            if self.config.enable_reflection:
                steps = self._reflect_and_refine(steps, context)
            
            logger.info("短期规划生成完成，共计%d个步骤", len(steps))
            
        except Exception as e:
            logger.error("短期规划失败: %s", e, exc_info=True)
            # 尝试使用备用规划器（如果有）
            if self._fallback_planner and self._fallback_planner.can_handle(context):
                logger.info("尝试备用规划器")
                steps = self._fallback_planner.plan(context)
            else:
                # 返回空列表，由上层处理
                steps = []
        
        return steps
    
    def can_handle(self, context: Dict[str, Any]) -> bool:
        """判断上下文是否适合短期规划（简单检查是否存在scene_summary）"""
        return "scene_summary" in context and context["scene_summary"] is not None
    
    def _build_planning_prompt(self, context: Dict[str, Any]) -> str:
        """构建规划提示词（模板化，后续应从Prompt库获取）"""
        # 这里仅返回骨架结构，真实实现需通过Prompt模板管理器
        template = (
            "你是一个小说创作助理。根据以下上下文，生成接下来的写作步骤，"
            "每个步骤应具体、可执行，并注明预期长度。上下文：{context}"
        )
        return template.format(context=json.dumps(context, ensure_ascii=False))
    
    def _parse_response(self, response: Any) -> List[Dict[str, Any]]:
        """解析模型响应（需实现具体解析逻辑，暂时返回示例数据）"""
        logger.debug("解析模型响应: %s", str(response)[:200])
        # TODO: 实现解析，当前返回空列表
        return []
    
    def _reflect_and_refine(self, steps: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """自我反思修正（可插拔反思策略）"""
        logger.info("执行反思修正，当前步骤数: %d", len(steps))
        # 反思逻辑待实现，可能去重、检查依赖完整性等
        return steps

# 插件注册机制（保证可插拔）
registry = {}

def register_planner(name: str, planner_class: type) -> None:
    """将规划器注册到系统中，支持动态发现"""
    if name in registry:
        logger.warning("规划器 '%s' 已存在，将被覆盖", name)
    registry[name] = planner_class
    logger.info("规划器 '%s' 注册成功", name)

def get_planner(name: str, config: Optional[Dict[str, Any]] = None) -> BasePlanner:
    """根据名称获取规划器实例（工厂模式）"""
    if name not in registry:
        raise ValueError(f"未找到规划器: {name}，可用: {list(registry.keys())}")
    planner_cls = registry[name]
    if config:
        planner_config = ShortTermPlannerConfig(config)
        return planner_cls(config=planner_config)
    return planner_cls()

# 默认注册
register_planner("short_term", ShortTermPlanner)

# ---------- 自测部分 ----------
if __name__ == "__main__":
    print("运行短期规划器自测...")
    # 1. 测试配置加载
    test_config = ShortTermPlannerConfig({"max_steps": 3})
    planner = ShortTermPlanner(test_config)
    
    # 2. 模拟模型接口（简单mock）
    class MockModelInterface:
        def generate(self, prompt, model_name, temperature, max_tokens):
            return "模拟响应"
    
    planner.set_model_interface(MockModelInterface())
    
    # 3. 创建测试上下文
    test_context = {
        "current_chapter": 1,
        "scene_summary": "主角进入神秘房间",
        "character_states": {"protagonist": "curious"},
        "medium_term_goal": "发现隐藏的线索"