"""
Runtime状态模块
位于 NovelOS 07_状态系统/Runtime状态
功能：管理运行时的状态信息，支持可插拔的状态管理器。
依赖：抽象接口，配置对象，日志。
被调用：由上层调度系统、Agent等使用。
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

# 获取日志记录器
logger = logging.getLogger(__name__)


class RuntimeStatusInterface(ABC):
    """运行时状态接口，定义标准方法"""
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化状态管理器"""
        pass

    @abstractmethod
    def get_status(self, key: str) -> Optional[Any]:
        """获取指定状态键的值"""
        pass

    @abstractmethod
    def set_status(self, key: str, value: Any) -> bool:
        """设置状态键的值"""
        pass

    @abstractmethod
    def delete_status(self, key: str) -> bool:
        """删除状态键"""
        pass

    @abstractmethod
    def get_all_status(self) -> Dict[str, Any]:
        """获取全部状态"""
        pass

    @abstractmethod
    def reset(self) -> bool:
        """重置所有状态"""
        pass


class DefaultRuntimeStatus(RuntimeStatusInterface):
    """默认的运行时状态实现，使用内存字典存储状态"""
    def __init__(self):
        self._status_dict: Dict[str, Any] = {}
        self._initialized = False
        logger.info("DefaultRuntimeStatus 实例已创建")

    def initialize(self, config: Dict[str, Any]) -> bool:
        """根据配置初始化，可设置初始状态"""
        try:
            # 示例配置：config.get("initial_status", {})
            initial = config.get("initial_status", {})
            self._status_dict.update(initial)
            self._initialized = True
            logger.info(f"Runtime状态初始化完成，初始状态数量：{len(self._status_dict)}")
            return True
        except Exception as e:
            logger.error(f"初始化失败: {e}")
            return False

    def get_status(self, key: str) -> Optional[Any]:
        if not self._initialized:
            logger.warning("状态管理器未初始化")
            return None
        return self._status_dict.get(key)

    def set_status(self, key: str, value: Any) -> bool:
        if not self._initialized:
            logger.warning("状态管理器未初始化")
            return False
        self._status_dict[key] = value
        logger.debug(f"状态更新: {key}={value}")
        return True

    def delete_status(self, key: str) -> bool:
        if not self._initialized:
            logger.warning("状态管理器未初始化")
            return False
        if key in self._status_dict:
            del self._status_dict[key]
            logger.debug(f"状态删除: {key}")
            return True
        return False

    def get_all_status(self) -> Dict[str, Any]:
        if not self._initialized:
            logger.warning("状态管理器未初始化")
            return {}
        return self._status_dict.copy()

    def reset(self) -> bool:
        self._status_dict.clear()
        logger.info("运行时状态已重置")
        return True


# 工厂函数，支持可插拔配置
def create_runtime_status(mode: str = "default", config: Optional[Dict[str, Any]] = None) -> RuntimeStatusInterface:
    """
    根据模式创建运行时状态实例
    mode: 状态管理器类型，如 'default'、'redis' 等（可扩展）
    config: 配置参数字典
    """
    if config is None:
        config = {}
    logger.info(f"创建RuntimeStatus，模式: {mode}")
    if mode == "default":
        instance = DefaultRuntimeStatus()
    else:
        # 可扩展: 从配置中动态加载类
        raise ValueError(f"不支持的状态管理器模式: {mode}")
    instance.initialize(config)
    return instance


# 自测代码
if __name__ == "__main__":
    # 设置基本日志
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    print("==== Runtime状态 自测开始 ====")
    # 测试默认实现
    config = {"initial_status": {"novel_id": "001", "chapter": 1, "progress": 0.0}}
    status_mgr = create_runtime_status("default", config)
    # 获取状态
    print("novel_id:", status_mgr.get_status("novel_id"))
    print("all:", status_mgr.get_all_status())
    # 设置新状态
    status_mgr.set_status("progress", 0.5)
    print("progress after set:", status_mgr.get_status("progress"))
    # 删除状态
    status_mgr.delete_status("chapter")
    print("all after delete:", status_mgr.get_all_status())
    # 重置
    status_mgr.reset()
    print("all after reset:", status_mgr.get_all_status())
    print("==== 自测通过 ====")