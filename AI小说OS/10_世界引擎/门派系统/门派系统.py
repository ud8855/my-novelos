# -*- coding: utf-8 -*-
"""
门派系统 (FactionSystem)
负责管理小说世界中的门派、势力、组织及其关系。
属于世界引擎层，为剧情生成提供背景和约束。
"""
import logging
import json
import os
from typing import Dict, List, Optional, Any

class FactionSystem:
    """门派系统主类，可插拔，支持热插拔"""
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._factions: Dict[str, Dict] = {}  # 门派数据存储
        self._relations: Dict[str, Dict] = {} # 关系矩阵，faction_a->faction_b: relation
        self._initialized = False

    def initialize(self):
        """初始化系统，加载配置和数据"""
        self.logger.info("门派系统初始化开始")
        # 从配置文件加载预设门派等
        self._initialized = True
        self.logger.info("门派系统初始化完成")

    def shutdown(self):
        """关闭系统，保存状态"""
        self.logger.info("门派系统关闭，保存数据")
        self._factions.clear()
        self._relations.clear()
        self._initialized = False

    def create_faction(self, faction_id: str, data: Dict[str, Any]) -> bool:
        """创建门派
        
        Args:
            faction_id: 门派唯一标识
            data: 门派属性数据（名称、类型、等级等）
        
        Returns:
            是否成功
        """
        if not self._initialized:
            self.logger.error("门派系统未初始化，无法创建门派")
            return False
        if faction_id in self._factions:
            self.logger.warning(f"门派已存在: {faction_id}")
            return False
        self._factions[faction_id] = data.copy()
        self.logger.info(f"创建门派: {faction_id}, 数据: {data}")
        return True

    def get_faction(self, faction_id: str) -> Optional[Dict]:
        """获取门派信息"""
        return self._factions.get(faction_id)

    def delete_faction(self, faction_id: str) -> bool:
        """删除门派"""
        if faction_id in self._factions:
            del self._factions[faction_id]
            # 同时清理与该门派相关的所有关系
            self._relations.pop(faction_id, None)
            for other in self._relations:
                self._relations[other].pop(faction_id, None)
            self.logger.info(f"删除门派: {faction_id}")
            return True
        return False

    def update_faction(self, faction_id: str, data: Dict[str, Any]) -> bool:
        """更新门派数据"""
        if faction_id not in self._factions:
            self.logger.warning(f"门派不存在: {faction_id}")
            return False
        self._factions[faction_id].update(data)
        self.logger.info(f"更新门派: {faction_id}")
        return True

    def set_relation(self, faction_a: str, faction_b: str, relation: str,
                     bidirectional: bool = False) -> bool:
        """设置两个门派间的关系
        
        Args:
            faction_a: 源门派ID
            faction_b: 目标门派ID
            relation: 关系描述（如 'ally', 'enemy', 'neutral'）
            bidirectional: 是否同时设置逆向关系
        """
        if faction_a not in self._factions or faction_b not in self._factions:
            self.logger.error("门派不存在，无法设置关系")
            return False
        self._relations.setdefault(faction_a, {})[faction_b] = relation
        if bidirectional:
            self._relations.setdefault(faction_b, {})[faction_a] = relation
        self.logger.info(f"设置关系: {faction_a} -> {faction_b} = {relation} (双向: {bidirectional})")
        return True

    def get_relation(self, faction_a: str, faction_b: str) -> Optional[str]:
        """查询两个门派间的关系"""
        if faction_a not in self._relations:
            return None
        return self._relations[faction_a].get(faction_b)

    def list_factions(self, filter_func=None) -> List[str]:
        """列出所有门派ID，可过滤
        
        Args:
            filter_func: 过滤函数，接收门派数据，返回布尔值
        """
        if filter_func:
            return [fid for fid, data in self._factions.items() if filter_func(data)]
        return list(self._factions.keys())

    def export_data(self) -> Dict:
        """导出当前门派和关系数据，用于持久化"""
        return {
            "factions": self._factions,
            "relations": self._relations,
        }

    def import_data(self, data: Dict):
        """导入数据，覆盖当前状态"""
        self._factions = data.get("factions", {})
        self._relations = data.get("relations", {})
        self.logger.info("导入门派数据完成")

# 自测代码
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    
    # 配置示例
    config = {
        "default_faction_type": "cultivation",
        "auto_save": True
    }
    
    fs = FactionSystem(config)
    fs.initialize()
    
    # 创建门派
    assert fs.create_faction("shaolin", {"name": "少林派", "type": "Buddhist", "level": 5})
    assert fs.create_faction("wudang", {"name": "武当派", "type": "Taoist", "level": 5})
    assert not fs.create_faction("shaolin", {})  # 重复创建应失败
    
    # 查询
    shaolin = fs.get_faction("shaolin")
    assert shaolin["name"] == "少林派"
    
    # 更新
    assert fs.update_faction("shaolin", {"level": 6})
    assert fs.get_faction("shaolin")["level"] == 6
    
    # 关系设置
    assert fs.set_relation("shaolin", "wudang", "neutral")
    assert fs.get_relation("shaolin", "wudang") == "neutral"
    assert fs.get_relation("wudang", "shaolin") is None  # 默认单向
    assert fs.set_relation("shaolin", "wudang", "ally", bidirectional=True)
    assert fs.get_relation("wudang", "shaolin") == "ally"
    
    # 列表
    all_factions = fs.list_factions()
    assert len(all_factions) == 2
    strong = fs.list_factions(lambda d: d["level"] >= 6)
    assert "shaolin" in strong
    
    # 删除
    assert fs.delete_faction("shaolin")
    assert fs.get_faction("shaolin") is None
    assert fs.get_relation("shaolin", "wudang") is None
    assert fs.get_relation("wudang", "shaolin") is None  # 相关关系也被清理
    
    # 数据导出导入
    exported = fs.export_data()
    fs.sh