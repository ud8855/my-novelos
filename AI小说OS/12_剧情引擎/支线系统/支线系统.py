"""支线系统模块 (Subplot System)
所属层：12_剧情引擎
依赖：核心模型（人物、事件），配置管理，日志
被调用：剧情引擎主控、故事进行中触发支线
解决：管理小说创作中的支线剧情，根据条件触发、推进、结束支线，不影响主线
"""

import logging
import json
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path

# 配置日志
logger = logging.getLogger("SubplotSystem")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class SubplotConfig:
    """支线系统配置类，从文件或默认配置加载"""
    def __init__(self, config_path: Optional[str] = None):
        self.enabled = True
        self.max_active_subplots = 5
        self.trigger_check_interval = 1  # 每次事件后检查触发
        self.subplot_definitions_file = "subplot_definitions.json"
        
        if config_path:
            self.load_config(config_path)
        else:
            self.load_default_config()

    def load_default_config(self):
        """加载默认配置"""
        logger.info("使用默认支线系统配置")
        # 可以在这里定义更多默认参数

    def load_config(self, path: str):
        """从文件加载配置"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            self.enabled = config_data.get("enabled", self.enabled)
            self.max_active_subplots = config_data.get("max_active_subplots", self.max_active_subplots)
            self.trigger_check_interval = config_data.get("trigger_check_interval", self.trigger_check_interval)
            self.subplot_definitions_file = config_data.get("subplot_definitions_file", self.subplot_definitions_file)
            logger.info(f"支线配置从 {path} 加载成功")
        except Exception as e:
            logger.error(f"加载支线配置失败: {e}，使用默认配置")

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "enabled": self.enabled,
            "max_active_subplots": self.max_active_subplots,
            "trigger_check_interval": self.trigger_check_interval,
            "subplot_definitions_file": self.subplot_definitions_file,
        }

class Subplot:
    """单个支线实例，保存状态与数据"""
    def __init__(self, subplot_id: str, definition: Dict[str, Any]):
        self.id = subplot_id
        self.name = definition.get("name", "未命名支线")
        self.description = definition.get("description", "")
        self.status = "inactive"  # inactive, active, completed, failed
        self.current_stage = 0
        self.stages = definition.get("stages", [])
        self.start_conditions = definition.get("start_conditions", {})
        self.fail_conditions = definition.get("fail_conditions", {})
        self.completion_conditions = definition.get("completion_conditions", {})
        self.attached_characters = definition.get("characters", [])
        self.data = {}  # 支线内部变量

    def activate(self, context: Dict[str, Any]) -> bool:
        """激活支线，检查当前上下文是否符合启动条件"""
        if not self._check_conditions(self.start_conditions, context):
            logger.debug(f"支线 {self.id} 启动条件不满足")
            return False
        self.status = "active"
        self.current_stage = 0
        logger.info(f"支线 {self.id} ({self.name}) 已激活")
        return True

    def progress(self, context: Dict[str, Any]) -> Optional[str]:
        """推进支线到下一阶段，返回当前阶段描述或None"""
        if self.status != "active":
            return None
        # 检查是否已完成或失败
        if self._check_conditions(self.completion_conditions, context):
            self.complete()
            return f"支线 {self.name} 已完成"
        if self._check_conditions(self.fail_conditions, context):
            self.fail()
            return f"支线 {self.name} 已失败"

        if self.current_stage < len(self.stages):
            stage_desc = self.stages[self.current_stage]
            self.current_stage += 1
            logger.debug(f"支线 {self.id} 推进到阶段 {self.current_stage}: {stage_desc}")
            return stage_desc
        else:
            # 所有阶段结束，标记完成
            self.complete()
            return f"支线 {self.name} 所有阶段结束，自动完成"

    def complete(self):
        """标记支线完成"""
        self.status = "completed"
        logger.info(f"支线 {self.id} ({self.name}) 已完成")

    def fail(self):
        """标记支线失败"""
        self.status = "failed"
        logger.info(f"支线 {self.id} ({self.name}) 已失败")

    def _check_conditions(self, conditions: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """检查条件是否满足，简单实现：检查上下文字段是否存在及匹配"""
        if not conditions:
            return True  # 无条件，默认通过
        for key, value in conditions.items():
            if key not in context or context[key] != value:
                return False
        return True

    def get_status(self) -> str:
        return self.status

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典，方便存储或传输"""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "current_stage": self.current_stage,
            "data": self.data,
        }

class SubplotSystem:
    """支线系统主类，管理所有支线定义和实例"""
    def __init__(self, config: Optional[SubplotConfig] = None, event_bus: Optional[Callable] = None):
        self.config = config if config else SubplotConfig()
        self.event_bus = event_bus  # 可选的事件总线，用于通知其他模块
        self.subplot_definitions: Dict[str, Dict] = {}  # id -> 定义
        self.active_subplots: Dict[str, Subplot] = {}  # 活跃的支线实例
        self.completed_subplots: List[str] = []  # 完成的支线ID列表
        self.load_definitions()

    def load_definitions(self):
        """从配置指定的文件加载支线定义"""
        def_file = self.config.subplot_definitions_file
        try:
            with open(def_file, 'r', encoding='utf-8') as f:
                definitions = json.load(f)
            if isinstance(definitions, list):
                for item in definitions:
                    if "id" in item:
                        self.subplot_definitions[item["id"]] = item
            elif isinstance(definitions, dict):
                self.subplot_definitions = definitions
            logger.info(f"已加载 {len(self.subplot_definitions)} 个支线定义")
        except FileNotFoundError:
            logger.warning(f"支线定义文件 {def_file} 不存在，将使用空定义")
        except Exception as e:
            logger.error(f"加载支线定义失败: {e}")

    def check_and_trigger(self, context: Dict[str, Any]) -> List[str]:
        """根据当前上下文检查并触发符合条件的支线，返回激活的支线ID列表"""
        triggered = []
        if not self.config.enabled:
            return triggered
        
        # 检查是否可激活新支线
        available_slots = self.config.max_active_subplots - len(self.active_subplots)
        if available_slots <= 0:
            return triggered

        # 遍历所有定义，尝试激活未激活的支线
        for sub_id, definition in self.subplot_definitions.items():
            if sub_id in self.active_subplots or sub_id in self.completed_subplots:
                continue  # 已经激活或已完成
            subplot = Subplot(sub_id, definition)
            if subplot.activate(context):
                self.active_subplots[sub_id] = subplot
                triggered.append(sub_id)
                available_slots -= 1
                if available_slots <= 0:
                    break
        if triggered:
            logger.info(f"触发了支线: {triggered}")
            if self.event_bus:
                self.event_bus("subplot_triggered", {"subplot_ids": triggered})
        return triggered

    def update_active_subplots(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """推进所有活跃支线，返回每个支线的更新结果"""
        results = []
        for sub_id, subplot in list(self.active_subplots.items()):
            result = subplot.progress(context)
            status = subplot.get_status()
            if status in ("completed", "failed"):
                # 移除已结束的支线
                self.completed_subplots.append(sub_id)
                del self.active_subplots[sub_id]
            results.append({
                "subplot_id": sub_id,
                "status": status,
                "result": result,
            })
        return results

    def get_subplot_status(self, subplot_id: str) -> Optional[Dict[str, Any]]:
        """获取指定支线的状态"""
        if subplot_id in self.active_subplots:
            return self.active_subplots[subplot_id].to_dict()
        # 也可查询已完成列表
        return None

    def get_all_active_summary(self) -> List[Dict[str, Any]]:
        """获取所有活跃支线的摘要"""
        return [sp.to_dict() for sp in self.active_subplots.values()]

    def reset(self):
        """重置支线系统状态（可用于测试或重新开始）"""
        self.active_subplots.clear()
        self.completed_subplots.clear()
        logger.info("支线系统已重置")

    def shutdown(self):
        """优雅关闭，保存必要状态等"""
        # 可以在这里持久化支线状态
        logger.info("支线系统关闭")


# 自测代码
if __name__ == "__main__":
    print("支线系统自测开始...")
    # 创建测试配置
    test_config = SubplotConfig()
    # 创建支线系统实例
    subplot_system = SubplotSystem(config=test_config)
    # 手动加载测试支线定义（模拟）
    subplot_system.subplot_definitions = {
        "sub_test_1": {
            "name": "测试支线1",
            "description": "一个测试用的支线",
            "stages": ["遇到神秘人物", "获取关键物品", "返回主城"],
            "start_conditions": {"location": "forest"},
            "completion_conditions": {"has_item": "magic_sword"},
            "fail_conditions": {"player_health": 0},
            "characters": ["npc_guide", "npc_enemy"]
        }
    }
    # 模拟游戏上下文
    context = {"location": "forest", "player_health": 100}
    # 触发支线
    triggered = subplot_system.check_and_trigger(context)
    print(f"已触发支线: {triggered}")
    # 推进支线
    updates = subplot_system.update_active_subplots(context)
    print("支线更新结果:")
    for u in updates:
        print(f"  {u}")
    # 再次推进
    context["has_item"] = "magic_sword"
    updates2 = subplot_system.update_active_subplots(context)
    print("再次推进后:")
    for u in updates2:
        print(f"  {u}")
    # 查看状态
    print("活跃支线摘要:", subplot_system.get_all_active_summary())
    # 完成
    subplot_system.shutdown()
    print("支线系统自测结束")