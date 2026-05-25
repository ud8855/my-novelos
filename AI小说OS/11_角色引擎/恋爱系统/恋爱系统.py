import os
import json
import logging
from typing import Dict, Any, Optional

# ------------------------------------------------------------
# 配置管理
# ------------------------------------------------------------
class LoveSystemConfig:
    """
    恋爱系统配置
    可插拔：通过配置文件加载，也允许运行时动态注入
    """
    DEFAULT_CONFIG = {
        "affection_growth_rate": 1.0,    # 好感度增长速度
        "max_affection": 100,            # 最大好感度
        "min_affection": -100,           # 最小好感度
        "event_probability": 0.1,        # 随机事件触发概率
        "log_level": "INFO",             # 日志级别
    }

    def __init__(self, config_path: Optional[str] = None):
        self._config = self.DEFAULT_CONFIG.copy()
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                self._config.update(user_config)

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def set(self, key: str, value):
        self._config[key] = value

    def __repr__(self):
        return f"LoveSystemConfig({self._config})"


# ------------------------------------------------------------
# 恋爱系统核心逻辑（骨架）
# ------------------------------------------------------------
class LoveSystem:
    """
    NovelOS 恋爱系统
    所属层级：11_角色引擎/恋爱系统
    依赖：无（依赖外部注入角色数据、事件触发接口）
    被调用：由角色引擎调度，向其他子系统提供好感度查询、事件触发等服务
    解决：管理角色间恋爱关系、好感度计算、特殊事件触发
    可插拔：通过配置类与接口解耦，允许替换实现
    """

    def __init__(self, config: Optional[LoveSystemConfig] = None):
        """
        初始化恋爱系统
        :param config: 恋爱系统配置实例，若未提供则使用默认配置
        """
        self.config = config or LoveSystemConfig()
        self.logger = self._setup_logger()
        self.logger.info("恋爱系统初始化完成")

    def _setup_logger(self) -> logging.Logger:
        """配置日志记录器"""
        logger = logging.getLogger("NovelOS.LoveSystem")
        log_level = self.config.get("log_level", "INFO")
        logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

        # 避免重复添加 handler（确保热插拔时无重复日志）
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(name)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    # ---------- 核心接口（骨架） ----------
    def calculate_affection(self, character_id_a: str, character_id_b: str, event_data: Dict[str, Any]) -> float:
        """
        计算两个角色之间因某个事件产生的好感度变化
        :param character_id_a: 角色A标识
        :param character_id_b: 角色B标识
        :param event_data: 事件数据，包含事件类型、上下文等
        :return: 本次变化的好感度差值
        """
        self.logger.debug(f"计算好感度变化: A={character_id_a}, B={character_id_b}, event={event_data}")
        # 骨架实现：返回固定值，未来由模型协同层注入算法
        return 0.0

    def get_relationship_status(self, character_id_a: str, character_id_b: str) -> Dict[str, Any]:
        """
        获取两个角色之间的当前恋爱关系状态
        :param character_id_a: 角色A
        :param character_id_b: 角色B
        :return: 状态字典，包含好感度、关系阶段、特殊标记等
        """
        self.logger.debug(f"查询关系状态: {character_id_a} <-> {character_id_b}")
        # 骨架返回空模板
        return {
            "affection": 0.0,
            "stage": "stranger",
            "flags": [],
        }

    def trigger_event(self, event_type: str, participants: list, context: Dict[str, Any]):
        """
        触发恋爱相关事件（如约会、告白、争吵等）
        :param event_type: 事件类型标识
        :param participants: 参与角色ID列表
        :param context: 事件上下文
        """
        self.logger.info(f"触发恋爱事件: type={event_type}, participants={participants}")
        # 骨架：仅记录日志，具体事件处理由外部事件系统编排
        return

    def inject_external_processor(self, event_type: str, processor_callable):
        """
        注入外部处理器（用于插拔式扩展）
        :param event_type: 事件类型
        :param processor_callable: 可调用对象，接收 (self, participants, context)
        """
        self.logger.info(f"注册外部处理器: {event_type} -> {processor_callable}")
        # 骨架：存储到内部字典，完整实现可根据需要
        if not hasattr(self, '_external_processors'):
            self._external_processors = {}
        self._external_processors[event_type] = processor_callable

    def reset(self):
        """
        重置恋爱系统状态（用于热更新或场景切换）
        """
        self.logger.warning("恋爱系统执行重置")
        # 清理内存数据等
        if hasattr(self, '_external_processors'):
            self._external_processors.clear()
        self.logger.info("恋爱系统重置完成")


# ------------------------------------------------------------
# 自测代码（仅用于开发阶段验证骨架）
# ------------------------------------------------------------
if __name__ == "__main__":
    print("=== 恋爱系统骨架自测 ===")

    # 1. 默认配置测试
    config = LoveSystemConfig()
    print(f"默认配置: {config}")

    # 2. 实例化系统
    love_sys = LoveSystem(config)
    print("恋爱系统实例创建成功")

    # 3. 基础接口调用测试
    diff = love_sys.calculate_affection("char01", "char02", {"type": "chat", "sentiment": 0.8})
    print(f"好感度变化: {diff}")

    status = love_sys.get_relationship_status("char01", "char02")
    print(f"关系状态: {status}")

    love_sys.trigger_event("confession", ["char01", "char02"], {"location": "garden"})

    # 4. 外部处理器注入测试
    def custom_handler(sys_inst, participants, ctx):
        print(f"自定义处理器被调用: participants={participants}, ctx={ctx}")

    love_sys.inject_external_processor("custom_event", custom_handler)

    # 5. 重置测试
    love_sys.reset()

    print("=== 自测完成 ===")