import logging
import json
import os
from typing import Optional, Dict, Any, Callable

class BlackeningSystem:
    """
    角色黑化系统：负责管理角色黑化状态、触发条件、程度评估与演变。
    支持热插拔、配置化、日志、可扩展。
    """

    # 默认配置
    DEFAULT_CONFIG = {
        "enabled": True,
        "log_level": "INFO",
        "log_file": None,  # None 表示输出到控制台
        "blackening_threshold": 0.5,   # 黑化阈值，超过该值视为黑化
        "decay_rate": 0.01,            # 每自然衰减率（每时间单位）
        "trigger_multipliers": {       # 不同触发类型的乘数
            "betrayal": 2.0,
            "injustice": 1.5,
            "loss": 1.8,
            "temptation": 1.2
        },
        "max_blackening": 1.0,
        "min_blackening": 0.0,
        "update_interval": 1.0         # 自动衰减间隔（秒），0 表示不自动衰减
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化黑化系统
        
        Args:
            config: 可选配置字典，与默认配置合并；也可以传入配置文件路径字符串
        """
        self._config = self.DEFAULT_CONFIG.copy()
        self._logger = None
        self._is_running = False
        self._character_blackening = {}  # 存储角色当前黑化值，键：角色ID，值：float

        # 合并配置
        if config:
            if isinstance(config, str):
                self.load_config_from_file(config)
            else:
                self.update_config(config)

        # 初始化日志
        self.setup_logger()

        # 自动衰减定时器相关（简化：这里仅通过process方法手动触发衰减，不设定时器）
        # 实际使用时可通过外部调度或在此处集成异步循环

    def setup_logger(self):
        """根据配置设置日志系统"""
        log_level = getattr(logging, self._config.get("log_level", "INFO").upper(), logging.INFO)
        self._logger = logging.getLogger("BlackeningSystem")
        self._logger.setLevel(log_level)

        # 避免重复添加handler
        if not self._logger.handlers:
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            if self._config.get("log_file"):
                file_handler = logging.FileHandler(self._config["log_file"], encoding='utf-8')
                file_handler.setFormatter(formatter)
                self._logger.addHandler(file_handler)
            else:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(formatter)
                self._logger.addHandler(console_handler)

        self._logger.info("黑化系统日志初始化完成")

    def load_config_from_file(self, file_path: str):
        """从JSON配置文件加载配置
        
        Args:
            file_path: 配置文件路径
        """
        if not os.path.exists(file_path):
            self._logger.warning(f"配置文件 {file_path} 不存在，使用默认配置")
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self.update_config(config)
            self._logger.info(f"已从文件加载配置: {file_path}")
        except Exception as e:
            self._logger.error(f"加载配置文件失败: {e}")

    def update_config(self, new_config: Dict[str, Any]):
        """更新部分配置，保留未更新项
        
        Args:
            new_config: 要合并的配置字典
        """
        if not isinstance(new_config, dict):
            self._logger.error("配置更新失败：参数必须是字典")
            return
        self._config.update(new_config)
        self._logger.debug("配置已更新")

    def start(self):
        """启动黑化系统（启用黑化计算）"""
        if self._is_running:
            self._logger.warning("黑化系统已在运行中")
            return
        if not self._config.get("enabled"):
            self._logger.info("黑化系统未启用，跳过启动")
            return
        self._is_running = True
        self._logger.info("黑化系统已启动")

    def stop(self):
        """停止黑化系统"""
        if not self._is_running:
            self._logger.warning("黑化系统已停止")
            return
        self._is_running = False
        self._logger.info("黑化系统已停止")

    def process_character(self, character_id: str, trigger_type: Optional[str] = None, 
                          intensity: float = 1.0, decay: bool = True) -> float:
        """处理角色的黑化事件。
        
        Args:
            character_id: 角色唯一标识
            trigger_type: 触发类型（如 betrayal, injustice, loss, temptation），为None表示仅衰减
            intensity: 触发强度，缩放因子
            decay: 是否在处理前执行自然衰减
        
        Returns:
            当前角色的黑化值（0-1）
        """
        if not self._is_running:
            self._logger.debug("黑化系统未运行，忽略处理")
            return self.get_blackening(character_id)

        # 初始化角色黑化值
        if character_id not in self._character_blackening:
            self._character_blackening[character_id] = self._config["min_blackening"]

        # 自然衰减
        if decay:
            self._apply_decay(character_id)

        # 触发事件处理
        if trigger_type:
            multiplier = self._config.get("trigger_multipliers", {}).get(trigger_type, 1.0)
            delta = multiplier * intensity
            old_value = self._character_blackening[character_id]
            new_value = old_value + delta
            new_value = max(self._config["min_blackening"], 
                            min(self._config["max_blackening"], new_value))
            self._character_blackening[character_id] = new_value
            self._logger.info(f"角色 {character_id} 触发 '{trigger_type}'，黑化值: {old_value:.3f} -> {new_value:.3f} (delta: {delta:.3f})")
        else:
            self._logger.debug(f"角色 {character_id} 仅衰减，当前黑化值: {self._character_blackening[character_id]:.3f}")

        return self._character_blackening[character_id]

    def _apply_decay(self, character_id: str):
        """应用自然衰减"""
        current = self._character_blackening.get(character_id, 0.0)
        decay_rate = self._config.get("decay_rate", 0.0)
        if decay_rate > 0:
            new_value = max(self._config["min_blackening"], current - decay_rate)
            self._character_blackening[character_id] = new_value
            # 仅记录微小衰减
            if abs(new_value - current) > 0.001:
                self._logger.debug(f"角色 {character_id} 自然衰减: {current:.3f} -> {new_value:.3f}")

    def get_blackening(self, character_id: str) -> float:
        """获取指定角色的当前黑化值"""
        return self._character_blackening.get(character_id, self._config["min_blackening"])

    def is_blackened(self, character_id: str) -> bool:
        """判断角色是否已黑化"""
        return self.get_blackening(character_id) >= self._config["blackening_threshold"]

    def reset_character(self, character_id: str):
        """重置角色的黑化值到最小值"""
        self._character_blackening[character_id] = self._config["min_blackening"]
        self._logger.info(f"角色 {character_id} 黑化值已重置")

    def set_blackening(self, character_id: str, value: float):
        """直接设置角色黑化值（用于调试或特殊场景）"""
        clamped = max(self._config["min_blackening"], 
                      min(self._config["max_blackening"], value))
        self._character_blackening[character_id] = clamped
        self._logger.info(f"角色 {character_id} 黑化值被设置为: {clamped:.3f}")

    def get_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        return {
            "is_running": self._is_running,
            "enabled": self._config.get("enabled"),
            "blackened_count": sum(1 for v in self._character_blackening.values() if v >= self._config["blackening_threshold"]),
            "total_characters": len(self._character_blackening),
            "threshold": self._config["blackening_threshold"]
        }


# 自测代码
if __name__ == "__main__":
    # 测试配置
    test_config = {
        "enabled": True,
        "log_level": "DEBUG",
        "blackening_threshold": 0.5,
        "decay_rate": 0.05,
        "trigger_multipliers": {
            "betrayal": 2.0,
            "injustice": 1.5
        }
    }

    # 实例化并启动
    system = BlackeningSystem(test_config)
    system.start()

    # 测试角色处理
    char_id = "hero_001"
    print(f"初始黑化值: {system.get_blackening(char_id)} (黑化: {system.is_blackened(char_id)})")

    # 触发背叛事件
    system.process_character(char_id, trigger_type="betrayal", intensity=0.3)
    print(f"背叛后: {system.get_blackening(char_id):.3f}")

    # 再触发一个不公事件
    system.process_character(char_id, trigger_type="injustice", intensity=0.2)
    print(f"不公后: {system.get_blackening(char_id):.3f}")

    # 检查是否黑化
    if system.is_blackened(char_id):
        print(f"角色 {char_id} 已黑化！")
    else:
        print(f"角色 {char_id} 未黑化。")

    # 模拟衰减多次
    for i in range(5):
        system.process_character(char_id, decay=True)
        print(f"衰减第{i+1}次: {system.get_blackening(char_id):.3f}")

    # 显示统计
    print("系统统计:", system.get_stats())

    # 停止系统
    system.stop()

    # 停止后再处理应无效
    system.process_character(char_id, trigger_type="betrayal", intensity=0.5)
    print(f"停止后处理，黑化值不变: {system.get_blackening(char_id):.3f}")