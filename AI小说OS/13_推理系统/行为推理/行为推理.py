from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Protocol

# ----------------------------------------------------------------
# 层归属：13_推理系统
# 职责：负责根据角色状态、上下文与长期设定，推理出角色的下一步行为
# 依赖：20_模型协同（通过注入的模型调用接口）
# 被调用者：剧情推进、交互响应等上层模块
# ----------------------------------------------------------------

# 可插拔接口定义（允许未来替换不同的行为推理算法）
class BehaviorReasoningInterface(Protocol):
    """行为推理协议，所有行为推理器必须实现此接口"""
    def reason(self, context: Dict[str, Any], character_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Args:
            context: 当前场景上下文，包含环境信息、时间线、对话历史等
            character_state: 角色状态，包含性格、情绪、目标、记忆等
        Returns:
            行为决策结果字典，例如：{'action': 'move_to', 'target': 'kitchen', 'reasoning': '...'}
        """
        ...


class LLMBehaviorReasoner:
    """基于大模型的行为推理器（默认实现）"""
    
    def __init__(self, 
                 model_call: Callable[[str], str],
                 config: Optional[Dict[str, Any]] = None):
        """
        Args:
            model_call: 对20_模型协同/21_API模型的抽象调用入口，签名(prompt) -> completion_text
            config: 可选的配置字典，用于覆盖默认参数
        """
        self.model_call = model_call
        self.logger = logging.getLogger(self.__class__.__name__)
        self._apply_config(config or {})
    
    def _apply_config(self, config: Dict[str, Any]) -> None:
        """应用配置，所有行为参数均可热更新"""
        self.behavior_temperature = config.get('behavior_temperature', 0.7)
        self.max_reasoning_tokens = config.get('max_reasoning_tokens', 256)
        self.persona_focus_weight = config.get('persona_focus_weight', 0.5)
        self.logger.info("BehaviorReasoner配置已加载: %s", config)
    
    def _build_prompt(self, context: Dict[str, Any], character_state: Dict[str, Any]) -> str:
        """构造发送给模型的行为推理提示模板（模板化，方便替换）"""
        # 未来可替换为从文件加载的Jinja2模板
        prompt = f"""
你是一个角色行为推理引擎。请根据以下信息决定角色的下一步行为。

当前场景上下文：
{context}

角色当前状态：
{character_state}

请返回一个JSON格式的行为决策，必须包含：
- action: 动作名称
- target: 动作目标（可选）
- emotion: 执行该动作时的情绪
- reasoning: 推理过程简述

只返回JSON，不要其他内容。
"""
        return prompt.strip()
    
    def _parse_response(self, raw_response: str) -> Dict[str, Any]:
        """解析模型返回的原始文本为结构化决策（基础实现，可被覆盖）"""
        import json
        try:
            decision = json.loads(raw_response)
            return decision
        except json.JSONDecodeError:
            self.logger.warning("行为推理结果解析失败，使用默认动作。原始输出: %s", raw_response)
            return {"action": "idle", "reasoning": "解析失败，默认待机"}
    
    def reason(self, context: Dict[str, Any], character_state: Dict[str, Any]) -> Dict[str, Any]:
        """执行行为推理（主入口）"""
        self.logger.debug("开始行为推理，context_keys=%s, character_state_keys=%s", 
                          list(context.keys()), list(character_state.keys()))
        
        # 1. 构建提示
        prompt = self._build_prompt(context, character_state)
        
        # 2. 调用模型（通过注入的接口，不直接依赖具体API）
        try:
            raw_output = self.model_call(prompt)
        except Exception as e:
            self.logger.error("模型调用失败: %s", e)
            # 异常恢复：返回默认安全行为
            return {"action": "idle", "reasoning": f"模型调用异常: {e}"}
        
        # 3. 解析结果
        decision = self._parse_response(raw_output)
        
        # 4. 附加元数据（便于追踪）
        decision['_meta'] = {
            'reasoner': self.__class__.__name__,
            'temperature': self.behavior_temperature,
            'context_len': len(context),
        }
        self.logger.info("行为推理完成: %s", decision.get('action'))
        return decision
    
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """热更新配置，无需重启"""
        self._apply_config(new_config)
        self.logger.info("行为推理器配置热更新成功")


# 自测模块（仅在直接执行时运行）
if __name__ == "__main__":
    import sys
    # 配置日志
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    
    # 模拟一个模型调用函数（占位）
    def mock_model_call(prompt: str) -> str:
        print(f"[MockModel] 收到prompt，长度{len(prompt)}")
        # 返回一个示例JSON
        return '{"action": "greet", "target": "player", "emotion": "friendly", "reasoning": "看到玩家，表示欢迎"}'
    
    # 实例化推理器
    reasoner = LLMBehaviorReasoner(model_call=mock_model_call)
    
    # 构造测试数据
    test_context = {
        "location": "tavern",
        "time": "evening",
        "nearby_entities": ["innkeeper", "player"],
        "recent_events": ["player entered the tavern"]
    }
    test_character = {
        "name": "Innkeeper",
        "personality": "warm and hospitable",
        "current_emotion": "neutral",
        "goal": "serve customers"
    }
    
    # 执行推理
    decision = reasoner.reason(test_context, test_character)
    print("\n行为决策结果:", decision)
    
    # 测试热更新
    reasoner.update_config({"behavior_temperature": 0.9})
    decision2 = reasoner.reason(test_context, test_character)
    print("\n更新配置后决策:", decision2)