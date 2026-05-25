# -*- coding: utf-8 -*-
"""
模块：角色规划
所属层级：14_规划系统（业务规划层）
依赖：
    - 标准库：logging, os, json
    - 外部库：无（配置化可后续扩展yaml等）
被谁调用：
    - 20_模型协同/故事引擎（通过标准化角色规划协议接口调用）
    - 16_调度系统（通过任务调度方式触发长线角色规划）
解决问题：
    - 接收高层角色设定要求，生成详细的角色轮廓、成长弧线、关系网络规划
    - 将规划结果转化为标准化数据结构，供下游生成模块和叙事模块使用
协议：
    - 输入：角色规划请求（dict）包含角色类型、故事背景、期望弧光等
    - 输出：角色规划方案（dict）包含角色档案、阶段变化、关键冲突、关系图谱等
可插拔、配置化、日志记录、支持热更新与异常恢复（通过配置和日志体系）
"""
import logging
import os
import json
from typing import Dict, Any, Optional

# 默认配置路径，可外部注入
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "character_plan_config.json")

class CharacterPlanner:
    """
    角色规划器（可插拔组件）
    
    职责：
        - 基于故事世界和创作目标，生成详尽的角色规划
        - 支持多模板、多策略的规划流水线
        - 提供规划结果的校验与结构化输出
    """
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化角色规划器
        
        参数:
            config_path: 配置文件路径，若为None则使用默认配置
        """
        self.config = self._load_config(config_path or DEFAULT_CONFIG_PATH)
        self.logger = self._setup_logger()
        self.logger.info("CharacterPlanner 实例化完成")
        # 组件状态标记
        self._ready = True
        
    def _load_config(self, path: str) -> Dict[str, Any]:
        """加载JSON配置文件，缺失时使用默认配置"""
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except Exception as e:
                # 容错：配置损坏时使用内嵌默认配置
                config = self._default_config()
                # 临时日志输出，正式日志器还未建立时使用print或后续补充
        else:
            config = self._default_config()
        return config
    
    def _default_config(self) -> Dict[str, Any]:
        """内置默认角色规划配置"""
        return {
            "plan_depth": "standard",            # 规划深度：basic / standard / detailed
            "template_library": "default",       # 模板库标识
            "max_relations": 20,                 # 角色关系图谱最大节点数
            "enable_growth_arc": True,           # 是否生成成长弧线
            "enable_cross_novel_consistency": False  # 跨部一致性检查（暂关闭）
        }
    
    def _setup_logger(self) -> logging.Logger:
        """创建并配置模块日志器"""
        logger = logging.getLogger("CharacterPlanner")
        logger.setLevel(logging.DEBUG if self.config.get("debug", False) else logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def plan_character(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        核心角色规划接口
        
        参数:
            request: 规划请求字典，需包含:
                - character_brief (必选): 角色简介描述
                - world_context (可选): 故事世界背景
                - constraints (可选): 规划约束条件
                - previous_plans (可选): 已有的关联规划
        
        返回:
            dict: 规划结果，结构参见协议定义。当前骨架返回空规划模板。
        """
        if not self._ready:
            self.logger.error("规划器未就绪，无法执行规划")
            return {"status": "error", "message": "Planner not ready"}
        
        self.logger.info(f"收到角色规划请求: {request.get('character_brief', '未知')[:30]}...")
        
        # 骨架阶段：只进行参数校验与占位返回，不实现具体规划逻辑
        if "character_brief" not in request:
            self.logger.warning("缺少 character_brief 字段")
            return {"status": "error", "message": "Missing character_brief"}
        
        # 模拟规划流程（后续由模型协同层填充）
        plan = self._create_empty_plan(request)
        self.logger.debug(f"返回占位规划: {json.dumps(plan, ensure_ascii=False)}")
        return {"status": "success", "data": plan}
    
    def _create_empty_plan(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成一个符合协议的空角色规划模板，用于骨架测试。
        """
        return {
            "character_id": None,                         # 角色唯一标识（待分配）
            "basic_profile": {
                "name": request.get("character_brief", ""),
                "role": "",
                "archetype": "",
                "core_conflict": ""
            },
            "growth_arc": {
                "stages": [],                              # 成长阶段列表
                "turning_points": [],                      # 转折点
                "final_state": ""
            },
            "relationship_map": {
                "nodes": [],                               # 关系节点
                "edges": []                                # 关系连线
            },
            "behavioral_patterns": [],                     # 行为模式
            "cross_novel_consistency": None,               # 跨部一致性数据，暂为空
            "metadata": {
                "plan_depth": self.config["plan_depth"],
                "generated_by": "CharacterPlanner_skeleton",
                "version": "0.1.0"
            }
        }
    
    def configure(self, new_config: Dict[str, Any]) -> None:
        """
        热更新配置（可插拔能力）
        
        参数:
            new_config: 要合并的配置字典
        """
        self.config.update(new_config)
        self.logger.info("配置已更新")
        # 根据需要调整日志级别
        if "debug" in new_config:
            self.logger.setLevel(logging.DEBUG if new_config["debug"] else logging.INFO)
    
    def reset(self) -> None:
        """重置规划器内部状态（用于故障恢复）"""
        self._ready = True
        self.logger.info("规划器状态已重置")
    
    def self_test(self) -> bool:
        """
        自测方法：验证模块基本可用性
        运行基础请求，检查返回结构，记录日志。
        """
        self.logger.info("执行自测...")
        test_request = {
            "character_brief": "测试角色",
            "world_context": "测试世界",
            "constraints": {}
        }
        result = self.plan_character(test_request)
        if result.get("status") == "success" and "data" in result:
            self.logger.info("自测通过")
            return True
        else:
            self.logger.error("自测失败: %s", result.get("message", ""))
            return False

# 模块自测入口（可直接运行本文件进行基础验证）
if __name__ == "__main__":
    print("运行角色规划模块自测...")
    planner = CharacterPlanner()
    success = planner.self_test()
    if success:
        print("自测成功")
    else:
        print("自测失败")