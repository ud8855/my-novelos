"""
羁绊系统骨架模块
所属层：角色引擎 (11_角色引擎)
依赖：配置管理器(10_配置管理)，日志模块(99_工具/日志)
被调用：由角色引擎核心调用，用于管理角色之间的羁绊关系及对剧情的影响
功能：提供可插拔的羁绊管理，支持配置化羁绊类型、等级、效果脚本，确保热更新与异常恢复
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path

# 日志配置
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())  # 避免无处理器时的警告，实际由框架注入

class FettersSystem:
    """
    羁绊系统核心类
    可插拔：通过设置不同的 effect_handler 或提供扩展点实现定制
    配置化：依赖外部配置文件定义羁绊类型、等级、效果
    日志化：所有关键操作均记录日志
    """
    
    def __init__(self, config_path: Optional[str] = None, **kwargs):
        """
        初始化羁绊系统
        :param config_path: 配置文件路径(JSON)，若为None则使用默认空配置
        :param kwargs: 其他扩展参数
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        # 羁绊存储结构：{角色对标识: {type: str, level: int, metadata: dict}}
        self.fetters: Dict[str, Dict[str, Any]] = {}
        # 可插拔效果处理器，外部可注入
        self.effect_handler: Optional[Callable] = kwargs.get('effect_handler', None)
        self._load_config()
        logger.info("羁绊系统初始化完成，配置路径: %s", config_path or "无")

    def _load_config(self):
        """加载或应用默认配置"""
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.debug("羁绊配置加载成功: %s", self.config_path)
            except Exception as e:
                logger.error("加载羁绊配置失败: %s, 使用默认空配置", e)
                self.config = {}
        else:
            logger.warning("未提供有效配置文件，使用默认空配置")
            self.config = {}

    def get_fetter_pair_key(self, char_id_a: str, char_id_b: str) -> str:
        """生成稳定的角色对键（避免AB与BA不一致）"""
        # 简单排序拼接，保证唯一
        ids = sorted([char_id_a, char_id_b])
        return f"{ids[0]}_{ids[1]}"

    def add_fetter(self, char_id_a: str, char_id_b: str, fetter_type: str, level: int = 1, metadata: Optional[Dict] = None) -> bool:
        """
        添加或更新两个角色间的羁绊
        :param char_id_a: 角色A标识
        :param char_id_b: 角色B标识
        :param fetter_type: 羁绊类型（需在配置中定义）
        :param level: 羁绊等级
        :param metadata: 附加信息
        :return: 成功返回True，失败返回False
        """
        if not char_id_a or not char_id_b or not fetter_type:
            logger.error("添加羁绊失败: 参数不完整")
            return False
        # 检查类型是否在配置允许范围内（如果配置了类型白名单）
        allowed_types = self.config.get("allowed_types", None)
        if allowed_types and fetter_type not in allowed_types:
            logger.error("不允许的羁绊类型: %s", fetter_type)
            return False
        pair_key = self.get_fetter_pair_key(char_id_a, char_id_b)
        old_fetter = self.fetters.get(pair_key)
        self.fetters[pair_key] = {
            "type": fetter_type,
            "level": level,
            "metadata": metadata or {}
        }
        logger.info("羁绊已设置: %s <-> %s, 类型: %s, 等级: %d",
                     char_id_a, char_id_b, fetter_type, level)
        # 触发羁绊添加效果（可插拔）
        self._trigger_effect("on_fetter_add", char_id_a, char_id_b, fetter_type, level)
        return True

    def remove_fetter(self, char_id_a: str, char_id_b: str) -> bool:
        """
        移除两个角色间的羁绊
        """
        pair_key = self.get_fetter_pair_key(char_id_a, char_id_b)
        if pair_key in self.fetters:
            removed = self.fetters.pop(pair_key)
            logger.info("羁绊已移除: %s <-> %s, 类型: %s", char_id_a, char_id_b, removed.get("type"))
            self._trigger_effect("on_fetter_remove", char_id_a, char_id_b, removed.get("type"), removed.get("level"))
            return True
        else:
            logger.warning("未找到羁绊，无法移除: %s <-> %s", char_id_a, char_id_b)
            return False

    def get_fetter(self, char_id_a: str, char_id_b: str) -> Optional[Dict]:
        """查询特定角色对间的羁绊信息"""
        return self.fetters.get(self.get_fetter_pair_key(char_id_a, char_id_b))

    def list_all_fetters(self) -> Dict[str, Dict]:
        """获取所有羁绊（用于快照/调试）"""
        return self.fetters.copy()

    def update_level(self, char_id_a: str, char_id_b: str, delta: int) -> bool:
        """
        改变羁绊等级
        :return: 是否更新成功
        """
        entry = self.get_fetter(char_id_a, char_id_b)
        if not entry:
            logger.warning("更新等级失败: 羁绊不存在")
            return False
        new_level = entry["level"] + delta
        if new_level < 0:
            logger.warning("羁绊等级不能为负，当前等级: %d，delta: %d", entry["level"], delta)
            return False
        entry["level"] = new_level
        logger.info("羁绊等级变化: %s <-> %s, 当前等级 %d (变化 %+d)", char_id_a, char_id_b, new_level, delta)
        self._trigger_effect("on_level_change", char_id_a, char_id_b, entry["type"], new_level, delta)
        return True

    def check_threshold(self, char_id_a: str, char_id_b: str, threshold: int) -> bool:
        """检查羁绊等级是否达到阈值"""
        entry = self.get_fetter(char_id_a, char_id_b)
        if entry:
            return entry["level"] >= threshold
        return False

    def inject_effect_handler(self, handler: Callable):
        """注入外部效果处理器，实现可插拔"""
        self.effect_handler = handler
        logger.info("羁绊效果处理器已注入")

    def _trigger_effect(self, event: str, *args):
        """内部触发效果（可插拔核心）"""
        if callable(self.effect_handler):
            try:
                self.effect_handler(event, *args)
            except Exception as e:
                logger.error("执行羁绊效果处理器时异常: %s", e)
        else:
            # 无处理器时仅记录调试日志
            logger.debug("无效果处理器，触发事件: %s, 参数: %s", event, args)

    def reset(self):
        """重置所有羁绊数据（用于测试或重新加载）"""
        self.fetters.clear()
        logger.info("羁绊系统已重置")

    def to_dict(self) -> Dict:
        """导出当前状态为字典（用于持久化或接口返回）"""
        return {
            "config_path": self.config_path,
            "fetters": self.fetters
        }

    def from_dict(self, state: Dict):
        """从字典恢复状态（热更新/恢复）"""
        self.fetters = state.get("fetters", {})
        logger.info("羁绊系统状态已从字典恢复")


if __name__ == "__main__":
    # 自测代码：骨架功能演示
    print("========== 羁绊系统骨架自测 ==========")
    # 默认空配置
    fs = FettersSystem()
    # 测试添加羁绊
    assert fs.add_fetter("主角", "女祭司", "友情", 1) == True
    assert fs.add_fetter("主角", "女祭司", "友情", 1) == True  # 覆盖添加
    assert fs.add_fetter("主角", "魔王", "敌对", 2) == True
    # 查询
    fetter1 = fs.get_fetter("主角", "女祭司")
    assert fetter1 is not None and fetter1["type"] == "友情"
    print("查询主角-女祭司羁绊:", fetter1)
    # 等级更改
    fs.update_level("主角", "女祭司", 2)
    assert fs.get_fetter("主角", "女祭司")["level"] == 3
    # 阈值检查
    assert fs.check_threshold("主角", "女祭司", 3) == True
    assert fs.check_threshold("主角", "魔王", 3) == False
    # 移除
    fs.remove_fetter("主角", "魔王")
    assert fs.get_fetter("主角", "魔王") is None
    # 列出所有
    all_f = fs.list_all_fetters()
    print("当前所有羁绊:", all_f)
    # 测试注入效果处理器
    def sample_handler(event, *args):
        print(f"事件触发: {event}, 参数: {args}")
    fs.inject_effect_handler(sample_handler)
    fs.update_level("主角", "女祭司", -1)  # 应触发处理器
    # 重置
    fs.reset()
    assert len(fs.list_all_fetters()) == 0
    print("重置后羁绊数量:", len(fs.list_all_fetters()))
    print("========== 自测通过 ==========")