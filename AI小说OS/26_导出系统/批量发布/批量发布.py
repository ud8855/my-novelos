# -*- coding: utf-8 -*-
"""
批量发布模块
职责：根据配置，调度多个导出任务批量发布到多个平台。
依赖：导出系统基类/发布器接口（可插拔）
被调用：由用户触发或定时任务调度
"""

import logging
import importlib
from typing import List, Dict, Any, Optional

# 配置日志
logger = logging.getLogger(__name__)

class BatchPublisher:
    """
    批量发布器
    负责加载发布器插件，对多个导出内容进行批量发布。
    可插拔：通过配置文件指定发布器类路径。
    配置化：支持并发数、重试策略、发布平台等配置。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.publishers = {}  # 平台名称 -> 发布器实例
        self._load_publishers()

    @staticmethod
    def _default_config() -> Dict[str, Any]:
        """默认配置"""
        return {
            "publishers": {
                "novel_website": None,  # 插件路径，如 "export.publishers.novel_website"
                "pdf": None
            },
            "max_workers": 4,
            "retry_times": 3,
            "target_format": "markdown"  # 默认导出格式
        }

    def _load_publishers(self):
        """根据配置动态加载发布器插件"""
        for platform, plugin_path in self.config.get("publishers", {}).items():
            if plugin_path:
                try:
                    module = importlib.import_module(plugin_path)
                    publisher_cls = getattr(module, "Publisher", None)
                    if publisher_cls:
                        self.publishers[platform] = publisher_cls()
                        logger.info(f"已加载发布器: {platform} -> {plugin_path}")
                    else:
                        logger.warning(f"发布器模块 {plugin_path} 未找到 Publisher 类")
                except Exception as e:
                    logger.error(f"加载发布器 {platform} 失败: {e}")
                    continue

    def publish_batch(self, export_results: List[Dict[str, Any]], platforms: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        批量发布导出的内容到指定平台
        :param export_results: 导出结果列表，每项包含内容、元数据等
        :param platforms: 目标平台列表，不指定则发布所有已加载的发布器
        :return: 发布结果汇总
        """
        if platforms is None:
            platforms = list(self.publishers.keys())
        summary = {}
        for platform in platforms:
            if platform in self.publishers:
                # TODO: 实际发布逻辑，处理并发等
                summary[platform] = {"status": "pending", "details": "尚未实现"}
                logger.info(f"准备发布到 {platform}")
            else:
                summary[platform] = {"status": "error", "details": f"未加载发布器 {platform}"}
                logger.error(f"发布器 {platform} 未加载")
        return summary

    def add_publisher(self, platform: str, publisher):
        """手动注册发布器"""
        self.publishers[platform] = publisher
        logger.info(f"手动注册发布器: {platform}")

    def remove_publisher(self, platform: str):
        """移除发布器"""
        if platform in self.publishers:
            del self.publishers[platform]
            logger.info(f"已移除发布器: {platform}")

# 自测
if __name__ == "__main__":
    # 设置基本日志
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    print("=== 批量发布模块自测 ===")
    # 使用默认配置创建
    bp = BatchPublisher()
    # 模拟导出结果
    dummy_export = [{"file": "chapter1.txt", "content": "...", "meta": {}}]
    result = bp.publish_batch(dummy_export, platforms=["pdf"])
    print("发布结果:", result)
    print("自测完成，无致命错误。")