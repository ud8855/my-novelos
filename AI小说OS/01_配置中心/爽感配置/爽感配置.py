"""
模块：爽感配置
层级：01_配置中心
依赖：标准库 logging, json, os, copy, typing
被调用：被 Runtime/故事引擎、Agent/情节规划 等通过接口调用
功能：定义和管理小说爽感的类型、强度、触发条件等配置项，支持热加载和自定义扩展
设计原则：可插拔（通过注册爽感类型），配置化（JSON文件），日志记录，异常恢复
"""

import logging
import json
import os
import copy
from typing import Dict, Any, List, Optional, Callable

# 配置日志
logger = logging.getLogger(__name__)

class PleasureConfig:
    """
    爽感配置管理器
    负责加载、存储、查询和更新爽感配置，支持自定义爽感类型注册
    """

    # 默认配置，确保系统在没有外部文件时也能运行
    DEFAULT_CONFIG = {
        "pleasure_types": {
            "beat_face": {
                "name": "打脸",
                "description": "主角逆袭，让轻视者难堪",
                "base_intensity": 3,
                "trigger_conditions": [
                    "对手公然挑衅",
                    "宴会场合冲突",
                    "比武/比赛获胜"
                ],
                "enhancements": {
                    "audience_reaction": 1,
                    "public_place": 2
                }
            },
            "upgrade": {
                "name": "突破升级",
                "description": "主角实力或地位大幅提升",
                "base_intensity": 4,
                "trigger_conditions": [
                    "获得奇遇",
                    "修炼突破",
                    "吸收宝物"
                ],
                "enhancements": {
                    "突破大境界": 2,
                    "众人目睹": 1
                }
            },
            "gain_treasure": {
                "name": "获得宝物",
                "description": "主角获得稀有宝物",
                "base_intensity": 3,
                "trigger_conditions": [
                    "探索秘境",
                    "拍卖会",
                    "战斗掉落"
                ],
                "enhancements": {
                    "宝物等级高": 2,
                    "引发争夺": 1
                }
            },
            "revenge": {
                "name": "复仇成功",
                "description": "主角成功报复仇人",
                "base_intensity": 5,
                "trigger_conditions": [
                    "找到仇人",
                    "实力足够",
                    "公平对决"
                ],
                "enhancements": {
                    "长期压抑": 2,
                    "公开处决": 1
                }
            }
        },
        "global_settings": {
            "default_intensity": 3,
            "max_intensity": 10,
            "min_intensity": 1,
            "pleasure_cooldown": 10,  # 至少间隔多少字数触发同一爽点
            "auto_detect": True  # 是否启用NPC协作自动检测爽点
        }
    }

    def __init__(self, config_file: Optional[str] = None):
        """
        初始化配置管理器
        :param config_file: 配置文件路径（JSON），可选，若为None则使用默认配置
        """
        self.config_file = config_file
        self._config = copy.deepcopy(self.DEFAULT_CONFIG)
        self._custom_type_validators: Dict[str, Callable] = {}  # 可插拔的自定义爽点验证器
        if self.config_file and os.path.exists(self.config_file):
            self.load_config()
        else:
            logger.info("未指定配置文件或文件不存在，使用默认爽感配置")

    def load_config(self):
        """从JSON文件加载爽感配置，并合并到默认配置上，保证必需字段完整"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            # 深度合并，保留默认值中的缺失键
            self._config = self._deep_merge(self._config, user_config)
            logger.info(f"爽感配置已从 {self.config_file} 加载成功")
        except Exception as e:
            logger.error(f"加载爽感配置失败: {e}，将继续使用当前配置")

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """递归合并字典，override中的值会覆盖base中的对应值"""
        result = copy.deepcopy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def save_config(self, file_path: Optional[str] = None):
        """保存当前配置到JSON文件"""
        target = file_path if file_path else self.config_file
        if not target:
            logger.warning("未指定保存路径，无法保存配置")
            return
        try:
            with open(target, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info(f"爽感配置已保存至 {target}")
        except Exception as e:
            logger.error(f"保存配置失败: {e}")

    def get_config(self) -> Dict[str, Any]:
        """获取当前完整配置（深拷贝，防止外部无意修改）"""
        return copy.deepcopy(self._config)

    def update_config(self, updates: Dict[str, Any]):
        """更新配置项，支持部分更新"""
        try:
            self._config = self._deep_merge(self._config, updates)
            logger.info("爽感配置已部分更新")
            # 可选：自动保存
            # self.save_config()
        except Exception as e:
            logger.error(f"更新配置失败: {e}")
            raise

    def get_pleasure_type(self, type_key: str) -> Optional[Dict]:
        """获取指定爽感类型的定义"""
        types = self._config.get("pleasure_types", {})
        return types.get(type_key)

    def register_pleasure_type(self, type_key: str, config: Dict,
                               validator: Optional[Callable] = None):
        """
        注册新的爽感类型（可插拔接口）
        :param type_key: 类型标识符，如 "rescue_beauty"
        :param config: 类型配置字典，需包含 name, base_intensity, trigger_conditions 等
        :param validator: 可选的自定义验证函数，用于检查触发器是否满足
        """
        if type_key in self._config["pleasure_types"]:
            logger.warning(f"爽感类型 {type_key} 已存在，将被覆盖")
        self._config["pleasure_types"][type_key] = config
        if validator:
            self._custom_type_validators[type_key] = validator
        logger.info(f"注册新爽感类型: {type_key}")

    def unregister_pleasure_type(self, type_key: str):
        """移除爽感类型"""
        if type_key in self._config["pleasure_types"]:
            del self._config["pleasure_types"][type_key]
            self._custom_type_validators.pop(type_key, None)
            logger.info(f"已移除爽感类型: {type_key}")

    def validate_trigger(self, type_key: str, context: Dict) -> bool:
        """
        使用验证器（如果有）检查触发条件
        :param type_key: 爽感类型
        :param context: 上下文信息
        :return: 是否满足条件
        """
        validator = self._custom_type_validators.get(type_key)
        if validator:
            try:
                return validator(self.get_pleasure_type(type_key), context)
            except Exception as e:
                logger.error(f"验证器执行异常: {e}")
                return False
        # 默认始终认为满足（由插件决定）
        return True

    def reload(self):
        """热重载配置文件"""
        if self.config_file:
            self.load_config()
        else:
            logger.warning("无配置文件路径，未能重载")

    def __repr__(self):
        return f"<PleasureConfig config_file={self.config_file}>"


# ---------- 自测代码 ----------
if __name__ == "__main__":
    # 设置测试日志输出到控制台
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 测试1：默认配置实例
    pc = PleasureConfig()
    print("=== 默认爽感类型列表 ===")
    for k, v in pc.get_config()["pleasure_types"].items():
        print(f"  {k}: {v['name']} (基础强度: {v['base_intensity']})")

    # 测试2：注册自定义爽感类型
    pc.register_pleasure_type("save_cat", {
        "name": "救下小猫",
        "description": "主角从危险中救出可爱小猫",
        "base_intensity": 2,
        "trigger_conditions": ["发现受困小猫", "提供帮助"],
        "enhancements": {"众人围观": 1}
    })
    print("\n=== 注册新类型后 ===")
    print(pc.get_pleasure_type("save_cat"))

    # 测试3：部分更新配置
    pc.update_config({
        "global_settings": {"max_intensity": 12}
    })
    print("\n=== 更新后全局设置 ===")
    print(pc.get_config()["global_settings"])

    # 测试4：默认验证器（无自定义验证器时默认True）
    print("\n=== 验证器测试 ===")
    print("beat_face 触发验证:", pc.validate_trigger("beat_face", {"reason": "test"}))

    # 测试5：保存到临时文件并重新加载
    temp_file = "test_pleasure_config.json"
    pc.save_config(temp_file)
    pc2 = PleasureConfig(temp_file)
    print("\n=== 从文件加载的配置类型数量 ===")
    print(len(pc2.get_config()["pleasure_types"]))
    # 清理测试文件
    try:
        os.remove(temp_file)
    except:
        pass

    print("\n=== 自测完成 ===")