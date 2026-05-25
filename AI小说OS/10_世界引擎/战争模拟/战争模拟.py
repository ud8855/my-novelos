"""
10_世界引擎/战争模拟/战争模拟.py
战争模拟引擎骨架模块

所属层级：世界引擎层（10_世界引擎）
依赖：无外部依赖，仅依赖标准库和 NovelOS 基础插件接口（假设存在 BasePlugin）
被谁调用：被世界引擎的主控模块或剧情生成模块调用，用于模拟战争进程
解决问题：为小说中的战争场景提供可配置、可插拔的模拟计算，生成军队损失、战局变化等结果
原则：
- 单一职责：仅负责战争模拟的核心抽象，不处理 UI、数据库等
- 可插拔：通过继承/实现预定义接口，支持替换不同模拟算法
- 配置化：所有参数从外部配置文件加载，支持热更新
- 日志：记录模拟关键步骤和异常
- 异常恢复：模拟过程出现错误时返回安全默认值，不影响主流程
- 热更新：运行时可通过 reload_config 重新加载配置
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

# 假设 NovelOS 提供基础插件接口，如果不存在，则使用简单基类
try:
    from novelos.core.plugin_base import BasePlugin
except ImportError:
    class BasePlugin(ABC):
        """模拟基础插件接口，实际项目应从 core 导入"""
        @abstractmethod
        def initialize(self, config: Dict[str, Any]) -> bool:
            """初始化插件"""
            pass

        @abstractmethod
        def shutdown(self) -> None:
            """关闭插件"""
            pass


class WarSimulationEngine(BasePlugin):
    """
    战争模拟引擎基类
    所有具体战争模拟器都必须继承此类，并实现 simulate 方法。
    提供配置加载、日志、热更新等通用能力。
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化战争模拟引擎

        :param config_path: 配置文件路径（JSON 格式），若为 None 则使用默认配置
        """
        super().__init__()
        self.config = {}  # 当前配置
        self.default_config = {
            "simulation_mode": "basic",  # 模拟模式：basic, advanced
            "enable_logging": True,
            "log_level": "INFO",
            "max_turns": 10,
            "default_casualty_rate": 0.1,
            "default_morale_decay": 0.05,
            # 更多默认参数...
        }
        self.logger = None
        self.config_path = config_path

        # 生成唯一的 logger 名称
        logger_name = f"WarSimulationEngine.{id(self)}"
        self.logger = logging.getLogger(logger_name)

        # 先加载配置，其中可能包含日志级别设定
        self._load_config()

        # 根据配置设置日志级别
        if self.config.get("enable_logging", True):
            log_level = self.config.get("log_level", "INFO").upper()
            self.logger.setLevel(getattr(logging, log_level, logging.INFO))
            # 如果根 logger 没有处理器，添加一个简单的控制台处理器
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter(
                    '[%(asctime)s] [%(name)s] %(levelname)s: %(message)s'
                )
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
        else:
            # 如果禁用日志，则设置一个 NullHandler
            self.logger.addHandler(logging.NullHandler())

        self.logger.info("战争模拟引擎已初始化")

    def _load_config(self):
        """
        从配置文件加载配置，若未指定路径或加载失败则使用默认配置。
        支持异常恢复。
        """
        self.config = self.default_config.copy()
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                self.config.update(loaded)
                self.logger.info(f"配置已从 {self.config_path} 加载")
            except Exception as e:
                self.logger.error(f"加载配置文件失败: {e}，使用默认配置")
        else:
            self.logger.info("未指定配置文件或文件不存在，使用默认配置")

    def reload_config(self, config_path: Optional[str] = None) -> bool:
        """
        热更新配置：重新从相同或新路径加载配置，并应用到当前实例。

        :param config_path: 新的配置文件路径，若为 None 则使用之前路径
        :return: 是否重新加载成功
        """
        old_path = self.config_path
        if config_path is not None:
            self.config_path = config_path
        self.logger.info(f"开始热更新配置，路径: {self.config_path}")
        try:
            self._load_config()
            # 如果日志相关配置变更，需要更新日志级别
            if self.config.get("enable_logging", True):
                log_level = self.config.get("log_level", "INFO").upper()
                self.logger.setLevel(getattr(logging, log_level, logging.INFO))
            else:
                # 禁用日志时，移除所有处理器避免输出
                for handler in self.logger.handlers[:]:
                    self.logger.removeHandler(handler)
                self.logger.addHandler(logging.NullHandler())
            self.logger.info("配置热更新成功")
            return True
        except Exception as e:
            self.logger.error(f"配置热更新失败: {e}")
            # 恢复原路径，防止破坏性变更导致后续无法恢复
            self.config_path = old_path
            return False

    @abstractmethod
    def simulate(self, world_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行战争模拟。子类必须实现具体算法。

        :param world_state: 当前世界状态，包含参战方兵力、地形、气候等。
        :return: 模拟结果，包含伤亡、领土变化、新状态等。
        """
        pass

    def safe_simulate(self, world_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        带异常保护的模拟调用，任何错误都会记录日志并返回空结果。
        这是对外部调用的安全接口。

        :param world_state: 当前世界状态
        :return: 模拟结果或错误时的默认结果
        """
        try:
            self.logger.info("开始安全战争模拟")
            result = self.simulate(world_state)
            self.logger.info("战争模拟完成")
            return result
        except Exception as e:
            self.logger.exception(f"战争模拟发生异常: {e}")
            # 返回一个无影响的默认结果，避免阻断流程
            return {
                "error": str(e),
                "casualties": {},
                "territory_changes": [],
                "new_world_state": world_state  # 原样返回
            }

    def initialize(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        实现 BasePlugin 接口，用于插件系统初始化。
        可以传递额外的配置字典，覆盖文件配置。

        :param config: 附加配置字典
        :return: 是否初始化成功
        """
        if config:
            self.config.update(config)
        self.logger.info("战争模拟引擎 initialize 完成")
        return True

    def shutdown(self) -> None:
        """
        关闭引擎，清理资源（当前为空实现）。
        """
        self.logger.info("战争模拟引擎已关闭")
        # 可以在这里加入资源释放逻辑


# ------------------- 简单的默认实现（用于测试） -------------------
class BasicWarSimulation(WarSimulationEngine):
    """
    基础战争模拟器，用于演示和测试。
    仅根据配置中的默认伤亡率和士气衰减进行简单计算。
    """

    def simulate(self, world_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        一个极小化的模拟示例，实际项目应替换为复杂逻辑。

        :param world_state: 包含 "armies" 列表，每个军队有 "strength", "morale"
        :return: 模拟后的状态
        """
        rate = self.config.get("default_casualty_rate", 0.1)
        morale_decay = self.config.get("default_morale_decay", 0.05)
        armies = world_state.get("armies", [])
        new_armies = []
        for army in armies:
            strength = army.get("strength", 100)
            morale = army.get("morale", 100)
            # 简单计算损失
            loss = int(strength * rate)
            new_strength = max(0, strength - loss)
            new_morale = max(0, morale - (morale * morale_decay))
            new_armies.append({
                "name": army.get("name", "未知"),
                "strength": new_strength,
                "morale": new_morale
            })
        self.logger.debug(f"基础模拟完成，处理军队数量: {len(armies)}")
        return {
            "armies": new_armies,
            "summary": f"基础模拟：默认伤亡率 {rate}，士气衰减 {morale_decay}"
        }


# ------------------- 自测代码 -------------------
if __name__ == "__main__":
    # 创建一个临时配置文件用于测试
    test_config_path = "test_war_config.json"
    with open(test_config_path, 'w', encoding='utf-8') as f:
        json.dump({
            "simulation_mode": "basic",
            "enable_logging": True,
            "log_level": "DEBUG",
            "default_casualty_rate": 0.2,
            "default_morale_decay": 0.1
        }, f, indent=2)

    # 使用配置文件初始化引擎
    engine = BasicWarSimulation(config_path=test_config_path)

    # 准备初始世界状态
    world = {
        "armies": [
            {"name": "北方军团", "strength": 1000, "morale": 80},
            {"name": "南方叛军", "strength": 800, "morale": 60}
        ],
        "terrain": "平原"
    }

    # 执行安全模拟
    result = engine.safe_simulate