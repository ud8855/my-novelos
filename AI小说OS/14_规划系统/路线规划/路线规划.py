#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
路线规划模块
负责根据初始设定生成多级小说路线（大纲/分卷/章节），
支持后续触发式调整，所有操作记录日志，参数可配置。

设计原则：
- 可插拔：独立封装，可通过配置切换不同的规划策略
- 日志化：关键步骤输出到统一日志系统
- 配置化：规划参数（如最大层级、章节上限等）从外部配置载入
- 单一职责：只负责路线规划，不涉及具体内容生成或UI展示
"""

import os
import yaml
import json
import logging
from typing import Dict, Any, Optional, List, Union
from pathlib import Path

# 假设系统已有统一的配置和日志加载器，此处仅给出接口模拟
# 实际应替换为项目中的具体实现，例如：
# from config_loader import load_config
# from logger import get_logger

class RoutePlanner:
    """路线规划器，负责小说大纲、分卷、章节结构的生成与调整"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化路线规划器
        
        Args:
            config_path: 配置文件路径，默认自动寻找内部默认配置
        """
        # 加载配置
        self.config = self._load_config(config_path)
        
        # 设置日志记录器（可插拔：可根据配置选择日志通道）
        self.logger = self._setup_logger()
        
        # 规划策略注册表，用于后续插拔不同算法（目前仅占位）
        self.strategies = {}
        
        self.logger.info("RoutePlanner 初始化完成")
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """
        加载配置，优先使用传入路径，否则使用模块内置默认配置
        
        Args:
            config_path: 配置文件路径
        
        Returns:
            配置字典
        """
        default_config = {
            "planning": {
                "max_volumes": 10,           # 最大卷数
                "max_chapters_per_volume": 50,  # 每卷最大章节数
                "default_structure": "sequential", # 路线结构类型
                "enable_depth_3": False,     # 是否启用章下分节
                "min_chapter_count": 3       # 每个卷至少包含的章节数
            },
            "logging": {
                "level": "INFO",
                "format": "[%(asctime)s] [%(name)s] %(levelname)s: %(message)s"
            }
        }
        
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                if config_path.endswith('.yaml') or config_path.endswith('.yml'):
                    user_config = yaml.safe_load(f)
                elif config_path.endswith('.json'):
                    user_config = json.load(f)
                else:
                    self.logger.warning(f"未知配置文件格式，使用默认配置")
                    return default_config
            # 合并配置（用户覆盖默认）
            merged = {**default_config, **user_config}
            return merged
        else:
            # 无外部配置，使用默认
            return default_config
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器，支持控制台和文件输出（可配置）"""
        logger = logging.getLogger("RoutePlanner")
        logger.setLevel(self.config.get("logging", {}).get("level", "INFO"))
        
        # 避免重复添加handler
        if not logger.handlers:
            formatter = logging.Formatter(
                self.config.get("logging", {}).get("format",
                    "[%(asctime)s] [%(name)s] %(levelname)s: %(message)s")
            )
            # 控制台handler
            ch = logging.StreamHandler()
            ch.setFormatter(formatter)
            logger.addHandler(ch)
            
            # 可选文件handler
            log_file = self.config.get("logging", {}).get("file")
            if log_file:
                fh = logging.FileHandler(log_file, encoding='utf-8')
                fh.setFormatter(formatter)
                logger.addHandler(fh)
        return logger
    
    def plan(self, novel_id: str, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        核心路由规划接口，根据小说设定生成完整路线（大纲结构）
        
        Args:
            novel_id: 小说唯一标识
            settings: 额外设定，如主题、梗概、类型等，优先级高于配置
        
        Returns:
            路线计划字典，结构如：
            {
                "novel_id": ...,
                "structure": "volumes",
                "volumes": [
                    {
                        "volume_index": 1,
                        "title": "卷名",
                        "summary": "卷概要",
                        "chapters": [
                            {"chapter_index": 1, "title": "章名", "outline": "大纲"},
                            ...
                        ]
                    }
                ]
            }
        """
        self.logger.info(f"开始为小说 {novel_id} 生成路线计划，附加设定：{settings}")
        
        # TODO: 实际规划逻辑，这里返回占位示例
        plan = {
            "novel_id": novel_id,
            "structure": self.config["planning"]["default_structure"],
            "volumes": []
        }
        
        # 简单示例：创建一个卷，包含3章
        if self.config["planning"]["max_volumes"] > 0:
            vol = {
                "volume_index": 1,
                "title": "示例卷",
                "summary": "这是自动生成的示例卷",
                "chapters": []
            }
            for i in range(3):
                vol["chapters"].append({
                    "chapter_index": i+1,
                    "title": f"章节 {i+1}",
                    "outline": "待填充的大纲"
                })
            plan["volumes"].append(vol)
        
        self.logger.info(f"路线计划生成完成，包含 {len(plan['volumes'])} 卷")
        return plan
    
    def adjust(self, novel_id: str, trigger_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据触发条件调整现有路线
        
        Args:
            novel_id: 小说标识
            trigger_info: 触发信息，例如 {'type': 'user_feedback', 'content': ...}
        
        Returns:
            调整后的路线计划
        """
        self.logger.info(f"收到调整请求，小说 {novel_id}，触发信息: {trigger_info}")
        
        # TODO: 加载已有路线，根据触发信息进行修改
        # 占位返回
        return {"status": "not_implemented", "message": "adjustment logic placeholder"}
    
    def validate(self, plan: Dict[str, Any]) -> bool:
        """
        验证路线计划的完整性与合理性
        
        Args:
            plan: 待验证的计划
        
        Returns:
            是否通过验证
        """
        self.logger.debug("开始验证路线计划")
        if not plan:
            self.logger.warning("计划为空")
            return False
        
        # 简单规则：至少有一个卷，每个卷至少有一个章节
        volumes = plan.get("volumes", [])
        if not volumes:
            self.logger.error("路线计划缺少卷定义")
            return False
        
        for vol in volumes:
            chapters = vol.get("chapters", [])
            if len(chapters) < self.config["planning"]["min_chapter_count"]:
                self.logger.error(f"卷 {vol.get('title', '未命名')} 章节数不足最低要求")
                return False
        
        self.logger.info("路线计划验证通过")
        return True
    
    def save_route(self, plan: Dict[str, Any], output_path: str):
        """
        将路线计划保存到文件
        
        Args:
            plan: 路线计划
            output_path: 保存路径（支持 .yaml / .json）
        """
        self.logger.info(f"保存路线计划至 {output_path}")
        dir_name = os.path.dirname(output_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            if output_path.endswith('.yaml') or output_path.endswith('.yml'):
                yaml.dump(plan, f, allow_unicode=True, default_flow_style=False)
            else:
                json.dump(plan, f, ensure_ascii=False, indent=2)
    
    def load_route(self, input_path: str) -> Dict[str, Any]:
        """
        从文件加载路线计划
        
        Args:
            input_path: 文件路径
        
        Returns:
            路线计划字典
        """
        self.logger.info(f"从 {input_path} 加载路线计划")
        with open(input_path, 'r', encoding='utf-8') as f:
            if input_path.endswith('.yaml') or input_path.endswith('.yml'):
                return yaml.safe_load(f)
            elif input_path.endswith('.json'):
                return json.load(f)
            else:
                raise ValueError("不支持的文件格式，仅支持 yaml/json")
    
    # 可插拔策略注册（示例）
    def register_strategy(self, name: str, strategy_func):
        """注册自定义规划策略"""
        self.strategies[name] = strategy_func
        self.logger.info(f"策略 '{name}' 已注册")


# ------------------- 自测模块 -------------------
def self_test():
    """简单的自测：创建实例，生成路线并打印"""
    planner = RoutePlanner()
    test_plan = planner.plan(novel_id="novel_001")
    planner.validate(test_plan)
    planner.save_route(test_plan, "test_route.json")
    loaded = planner.load_route("test_route.json")
    print(json.dumps(loaded, ensure_ascii=False, indent=2))
    # 清除测试文件（可选）
    os.remove("test_route.json")
    print("自测通过")

if __name__ == "__main__":
    self_test()