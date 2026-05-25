# 角色状态.py
# 模块位置: 07_状态系统/角色状态
# 功能: 管理单个角色的状态(生命、魔力、情绪、位置等)，支持可插拔事件回调、配置化、日志记录
# 依赖: 标准库 logging, json, os; 外部配置加载(可选，此处提供内置默认配置)
# 被调用: 由场景管理、AI决策、叙事引擎等模块调用

import copy
import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Union


class RoleState:
    """
    角色状态管理器
    维护角色基础属性，提供状态变更、事件监听、序列化等功能。
    所有属性变更均通过 update_state 方法，以确保日志记录与回调触发。
    """

    # 默认配置(当未提供外部配置时使用)
    DEFAULT_CONFIG = {
        "attributes": {
            "hp": {"default": 100, "min": 0, "max": 100},
            "mp": {"default": 50, "min": 0, "max": 100},
            "mood": {"default": 75, "min": 0, "max": 100},  # 情绪值 0-100
            "location": {"default": "未知", "type": "str"}    # 当前位置
        },
        "log_level": "INFO",
        "validate_restrictions": True,   # 是否对值进行限制检查
    }

    def __init__(self, character_id: str, config: Optional[Dict[str, Any]] = None):
        """
        初始化角色状态
        :param character_id: 角色唯一标识(如角色名或ID)
        :param config: 可选配置字典，若提供则与默认配置合并；也可提供配置文件路径字符串
        """
        self.character_id = character_id
        self.logger = logging.getLogger(f"RoleState.{character_id}")

        # 加载配置：优先使用传入的dict，若为字符串则尝试作为路径加载
        if isinstance(config, str):
            self.config = self._load_config_from_file(config)
        elif isinstance(config, dict):
            self.config = self._merge_config(config)
        else:
            self.config = copy.deepcopy(self.DEFAULT_CONFIG)

        # 设置日志级别
        log_level = getattr(logging, self.config.get("log_level", "INFO"), logging.INFO)
        self.logger.setLevel(log_level)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        # 初始化属性值
        self.attributes: Dict[str, Any] = {}
        self._init_attributes()

        # 事件回调注册表： key为事件名(如"state_changed"、"hp_changed")，value为callback列表
        self.callbacks: Dict[str, List[Callable]] = {
            "state_changed": [],
            "state_loaded": [],
            "before_state_change": []
        }

        self.logger.info(f"角色状态初始化完成: {character_id}")

    def _load_config_from_file(self, path: str) -> Dict[str, Any]:
        """从JSON文件加载配置并与默认配置合并"""
        if not os.path.exists(path):
            self.logger.warning(f"配置文件{path}不存在，使用默认配置")
            return copy.deepcopy(self.DEFAULT_CONFIG)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                external = json.load(f)
            return self._merge_config(external)
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}，使用默认配置")
            return copy.deepcopy(self.DEFAULT_CONFIG)

    def _merge_config(self, external: Dict[str, Any]) -> Dict[str, Any]:
        """将外部配置与默认配置合并，外部配置覆盖默认值"""
        merged = copy.deepcopy(self.DEFAULT_CONFIG)
        if "attributes" in external:
            for attr, settings in external["attributes"].items():
                if attr in merged["attributes"]:
                    merged["attributes"][attr].update(settings)
                else:
                    merged["attributes"][attr] = settings
        # 其他顶层配置直接覆盖
        for key in external:
            if key != "attributes":
                merged[key] = external[key]
        return merged

    def _init_attributes(self):
        """根据配置初始化所有属性为默认值"""
        for attr_name, settings in self.config["attributes"].items():
            default_val = settings.get("default", 0)
            self.attributes[attr_name] = default_val

    def get(self, attribute: str) -> Optional[Any]:
        """获取指定属性值，若不存在返回None"""
        return self.attributes.get(attribute)

    def set(self, attribute: str, value: Any, force: bool = False) -> bool:
        """
        直接设置属性值(绕过部分检查和回调？实际上应该用update_state，但为方便保留)
        推荐使用 update_state 方法。
        """
        return self.update_state(attribute, value, force)

    def update_state(self, attribute: str, value: Any, force: bool = False) -> bool:
        """
        更新指定属性，执行验证、限制检查、触发回调
        :param attribute: 属性名
        :param value: 新值
        :param force: 是否强制更新(忽略限制和回调？false时完全流程)
        :return: 是否成功
        """
        if attribute not in self.attributes:
            self.logger.error(f"未知属性: {attribute}")
            return False

        old_value = self.attributes[attribute]
        if not force:
            # 触发 'before_state_change' 回调，允许外部干预
            if not self._fire_before_change_callbacks(attribute, old_value, value):
                self.logger.info(f"属性变更被拦截: {attribute} {old_value} -> {value}")
                return False

        # 执行值有效性验证
        validated_value = self._validate_and_restrict(attribute, value)
        if validated_value is None and not force:
            return False

        # 应用新值
        self.attributes[attribute] = validated_value
        self.logger.debug(f"属性变更: {attribute}: {old_value} -> {validated_value}")
        # 触发变更后回调
        self._fire_state_changed_callbacks(attribute, old_value, validated_value)
        return True

    def _validate_and_restrict(self, attribute: str, value: Any) -> Optional[Any]:
        """根据配置的 min/max/type 限制对值进行验证与修正，返回修正后的值，若严重不符返回None"""
        if not self.config.get("validate_restrictions", False):
            return value  # 不做限制
        attr_config = self.config["attributes"].get(attribute)
        if not attr_config:
            return value

        # 类型校验
        expected_type = attr_config.get("type")
        if expected_type:
            try:
                if expected_type == "int":
                    value = int(value)
                elif expected_type == "float":
                    value = float(value)
                elif expected_type == "str":
                    value = str(value)
                # 可扩展其他类型
            except (ValueError, TypeError):
                self.logger.error(f"属性{attribute}类型转换失败，期望{expected_type}，得到{type(value)}")
                return None

        # 范围限制(仅数值类型)
        if isinstance(value, (int, float)):
            min_val = attr_config.get("min")
            max_val = attr_config.get("max")
            if min_val is not None and value < min_val:
                value = min_val
                self.logger.debug(f"属性{attribute}值被限制到最小值{min_val}")
            if max_val is not None and value > max_val:
                value = max_val
                self.logger.debug(f"属性{attribute}值被限制到最大值{max_val}")
        return value

    def register_callback(self, event: str, callback: Callable):
        """
        注册事件回调(可插拔)
        :param event: 事件名（state_changed, before_state_change, state_loaded）
        :param callback: 回调函数，签名应匹配对应事件
        """
        if event in self.callbacks:
            self.callbacks[event].append(callback)
            self.logger.debug(f"回调注册成功: 事件={event}, 函数={callback.__name__}")
        else:
            self.logger.warning(f"未知事件类型: {event}")

    def unregister_callback(self, event: str, callback: Callable):
        """移除回调"""
        if event in self.callbacks and callback in self.callbacks[event]:
            self.callbacks[event].remove(callback)

    def _fire_before_change_callbacks(self, attribute: str, old_value: Any, new_value: Any) -> bool:
        """
        触发 before_state_change 回调，若任一回调返回False则阻止更新
        """
        for cb in self.callbacks.get("before_state_change", []):
            try:
                result = cb(self.character_id, attribute, old_value, new_value)
                if result is False:
                    return False
            except Exception as e:
                self.logger.error(f"before_state_change回调执行异常: {e}")
        return True

    def _fire_state_changed_callbacks(self, attribute: str, old_value: Any, new_value: Any):
        """触发 state_changed 回调"""
        for cb in self.callbacks.get("state_changed", []):
            try:
                cb(self.character_id, attribute, old_value, new_value)
            except Exception as e:
                self.logger.error(f"state_changed回调执行异常: {e}")

    def save_state(self, filepath: str = None) -> Optional[Dict[str, Any]]:
        """
        保存当前状态到文件，若未提供路径则返回字典
        :return: 保存的状态字典，或None（如果保存失败）
        """
        state_dict = {
            "character_id": self.character_id,
            "attributes": copy.deepcopy(self.attributes),
            "config": self.config  # 可保存配置以便还原
        }
        if filepath:
            try:
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(state_dict, f, ensure_ascii=False, indent=2)
                self.logger.info(f"状态已保存至: {filepath}")
            except Exception as e:
                self.logger.error(f"保存状态失败: {e}")
                return None
        return state_dict

    def load_state(self, source: Union[str, Dict[str, Any]]) -> bool:
        """
        从文件或字典加载状态
        :param source: 文件路径或状态字典
        """
        if isinstance(source, str):
            try:
                with open(source, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                self.logger.error(f"加载状态文件失败: {e}")
                return False
        elif isinstance(source, dict):
            data = source
        else:
            self.logger.error("load_state 参数类型错误，需要str或dict")
            return False

        # 验证结构
        if "attributes" not in data:
            self.logger.error("状态数据缺少attributes字段")
            return False
        # 可选择性合并配置
        if "config" in data:
            self.config = self._merge_config(data["config"])
        self.attributes = copy.deepcopy(data["attributes"])
        # 确保所有配置中的属性存在(防止加载后缺属性)
        self._ensure_all_attributes_exist()