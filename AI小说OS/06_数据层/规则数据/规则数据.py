# 文件名: rule_data.py
# 模块路径: 06_数据层/规则数据/规则数据.py
# 说明: 规则数据管理层，提供规则数据的增删改查、持久化、缓存等基础能力。当前为骨架代码，实现可插拔接口。

import json
import logging
import os
from typing import Any, Dict, List, Optional
from pathlib import Path

# 配置和日志初始化，遵循配置化与可插拔原则
logger = logging.getLogger(__name__)

class RuleDataManager:
    """
    规则数据管理器
    负责规则数据的存取、缓存、持久化。支持多种后端（默认JSON文件），可插拔扩展。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化管理器
        :param config: 配置字典，包含存储路径、缓存策略等
        """
        self._config = config or self._default_config()
        self._rules_cache: Dict[str, Dict[str, Any]] = {}
        self._load_rules()
        logger.info("RuleDataManager 初始化完成")

    def _default_config(self) -> Dict[str, Any]:
        """
        默认配置
        """
        return {
            "storage_type": "json",       # 存储类型: json / database / memory
            "storage_path": str(Path(__file__).parent / "rules_store.json"),
            "enable_cache": True,
            "auto_save": True,
            "encoding": "utf-8"
        }

    def _load_rules(self) -> None:
        """
        从持久化存储加载规则数据到缓存
        """
        if self._config["storage_type"] == "json":
            file_path = self._config["storage_path"]
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding=self._config.get("encoding", "utf-8")) as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        self._rules_cache = data
                    else:
                        logger.warning("规则文件格式错误，使用空缓存")
                        self._rules_cache = {}
                    logger.info(f"规则数据已加载，共 {len(self._rules_cache)} 条")
                except (json.JSONDecodeError, IOError) as e:
                    logger.error(f"加载规则文件失败: {e}，使用空缓存")
                    self._rules_cache = {}
            else:
                logger.info("规则文件不存在，初始化空缓存")
                self._rules_cache = {}
        else:
            # 扩展点：数据库等后端
            logger.info("使用非文件存储类型，暂不支持自动预加载")
            self._rules_cache = {}

    def _save_rules(self) -> None:
        """
        将缓存中的规则数据持久化存储
        """
        if self._config["storage_type"] == "json":
            file_path = self._config["storage_path"]
            try:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, 'w', encoding=self._config.get("encoding", "utf-8")) as f:
                    json.dump(self._rules_cache, f, ensure_ascii=False, indent=2)
                logger.debug("规则数据已保存")
            except IOError as e:
                logger.error(f"保存规则文件失败: {e}")
        else:
            # 扩展点
            logger.debug("非文件后端，不执行自动保存")

    def get_rule(self, rule_id: str) -> Optional[Dict[str, Any]]:
        """
        根据规则ID获取规则内容
        :param rule_id: 规则唯一标识
        :return: 规则字典或None
        """
        rule = self._rules_cache.get(rule_id)
        logger.debug(f"获取规则 {rule_id}: {'命中' if rule else '缺失'}")
        return rule

    def set_rule(self, rule_id: str, rule_data: Dict[str, Any]) -> None:
        """
        添加或更新规则
        :param rule_id: 规则标识
        :param rule_data: 规则内容字典
        """
        self._rules_cache[rule_id] = rule_data
        logger.info(f"规则 {rule_id} 已更新")
        if self._config.get("auto_save", True):
            self._save_rules()

    def delete_rule(self, rule_id: str) -> bool:
        """
        删除指定规则
        :param rule_id: 规则标识
        :return: 是否成功删除
        """
        if rule_id in self._rules_cache:
            del self._rules_cache[rule_id]
            logger.info(f"规则 {rule_id} 已删除")
            if self._config.get("auto_save", True):
                self._save_rules()
            return True
        else:
            logger.warning(f"规则 {rule_id} 不存在，删除失败")
            return False

    def list_rules(self) -> List[str]:
        """
        列出所有规则ID
        :return: 规则ID列表
        """
        return list(self._rules_cache.keys())

    def query_rules(self, filter_func) -> Dict[str, Dict[str, Any]]:
        """
        根据自定义过滤函数查询规则
        :param filter_func: 接收(rule_id, rule_data)返回bool的函数
        :return: 符合条件的规则字典
        """
        result = {rid: rdata for rid, rdata in self._rules_cache.items() if filter_func(rid, rdata)}
        logger.debug(f"条件查询得到 {len(result)} 条规则")
        return result

    def reload(self) -> None:
        """
        重新从持久化存储加载规则，覆盖缓存（热更新支持）
        """
        logger.info("执行规则热重载")
        self._load_rules()

    def flush(self) -> None:
        """
        强制将缓存写回存储
        """
        logger.info("强制刷写规则到存储")
        self._save_rules()

    def register_backend(self, backend_type: str, backend_instance):
        """
        注册新的存储后端（可插拔扩展点）
        :param backend_type: 后端类型标识
        :param backend_instance: 后端实例
        """
        logger.info(f"注册存储后端: {backend_type}")
        # 此处保留接口，具体实现可后续扩展
        pass


# ---------- 自测部分 (仅在直接运行本模块时执行) ----------
def _self_test():
    """
    简单的自测逻辑，验证基础功能
    """
    print("执行自测...")
    # 使用临时配置，避免污染实际数据
    test_config = {
        "storage_type": "memory",  # 内存模式，不落盘
        "enable_cache": True,
        "auto_save": False
    }
    manager = RuleDataManager(test_config)

    # 增
    manager.set_rule("test_001", {"name": "禁止暴力描写", "severity": "high"})
    manager.set_rule("test_002", {"name": "章节结构模板", "template": "起承转合"})

    # 查
    rule1 = manager.get_rule("test_001")
    assert rule1 is not None and rule1["name"] == "禁止暴力描写", "get_rule 失败"

    # 列表
    ids = manager.list_rules()
    assert len(ids) == 2, "list_rules 数量错误"

    # 删
    manager.delete_rule("test_002")
    assert manager.get_rule("test_002") is None, "删除失败"

    # 热重载 (内存模式无实际作用，但不报错)
    manager.reload()

    print("自测全部通过！")

if __name__ == "__main__":
    # 配置日志输出
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _self_test()