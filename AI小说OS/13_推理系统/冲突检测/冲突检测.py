"""冲突检测模块 - 推理系统的一部分
负责检测小说创作过程中的逻辑冲突、设定冲突、情节矛盾等。
遵循可插拔、配置化、日志化原则。
"""
import logging
import json
from typing import Dict, List, Optional, Any

# 配置路径（后续统一到配置中心）
DEFAULT_CONFIG = {
    "enabled": True,
    "log_level": "INFO",
    "conflict_types": ["情节冲突", "人物设定冲突", "时间线矛盾", "世界观冲突"],
    "severity_levels": ["信息", "警告", "错误", "阻塞"],
    "detection_methods": [],  # 动态加载检测器
    "plugins": [],  # 冲突检测插件列表
}

class ConflictDetector:
    """冲突检测基类，所有具体检测器需继承此类"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or DEFAULT_CONFIG
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(self.config.get("log_level", "INFO"))
        self._plugin_instances = []

    def initialize(self) -> None:
        """初始化检测器，加载插件和配置依赖"""
        self.logger.info("冲突检测器初始化")
        # 未来在此加载插件、检测规则等

    def detect(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        主检测入口，接收上下文，返回冲突列表
        context: 包含待检测的文本、设定、时间线等所有必要信息
        返回: 冲突字典列表，每个冲突包含类型、严重程度、描述、位置等
        """
        self.logger.debug("开始冲突检测")
        conflicts = []
        if not self.config.get("enabled"):
            return conflicts
        # 调用插件化检测方法
        for plugin in self._plugin_instances:
            try:
                result = plugin.detect(context)
                if result:
                    conflicts.extend(result)
            except Exception as e:
                self.logger.error(f"插件 {plugin.__class__.__name__} 检测异常: {e}", exc_info=True)
        # 未来可以添加内置检测逻辑
        return conflicts

    def add_plugin(self, plugin: Any) -> None:
        """注册冲突检测插件，实现可插拔"""
        if hasattr(plugin, 'detect'):
            self._plugin_instances.append(plugin)
            self.logger.info(f"已注册冲突检测插件: {plugin.__class__.__name__}")
        else:
            self.logger.warning("插件缺少 detect 方法，无法注册")

    def remove_plugin(self, plugin_name: str) -> bool:
        """移除插件"""
        for plugin in self._plugin_instances:
            if plugin.__class__.__name__ == plugin_name:
                self._plugin_instances.remove(plugin)
                self.logger.info(f"已移除冲突检测插件: {plugin_name}")
                return True
        return False

    def reload_config(self, config: Dict[str, Any]) -> None:
        """热更新配置"""
        self.config = config
        self.logger.setLevel(config.get("log_level", "INFO"))
        self.logger.info("冲突检测器配置已热更新")

    def shutdown(self) -> None:
        """清理资源"""
        self.logger.info("冲突检测器关闭")
        self._plugin_instances.clear()


# 以下为简单的自测代码，在实际系统中不会运行，仅用于模块独立验证
if __name__ == "__main__":
    # 配置日志以便观察
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    detector = ConflictDetector()
    detector.initialize()
    # 模拟一个假的插件
    class MockPlugin:
        def detect(self, context):
            return [{"type": "测试冲突", "severity": "信息", "desc": "这是个示例冲突"}]
    detector.add_plugin(MockPlugin())
    # 执行检测
    test_context = {"chapter": "第一章", "content": "主角在房间内，但之前说他出去了"}
    result = detector.detect(test_context)
    print("检测结果:", json.dumps(result, ensure_ascii=False, indent=2))
    detector.shutdown()