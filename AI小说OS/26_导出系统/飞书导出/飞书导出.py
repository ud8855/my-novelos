"""
飞书导出模块 - LarkExporter
层级：导出系统层 (26_导出系统)
依赖：可能通过 21_API模型/ 调用飞书API，通过配置获取凭证
被调用：由外部调度器或用户界面触发导出任务
职责：将小说内容、分析结果等数据导出到飞书（文档、表格、消息等）
特性：可插拔、配置化、日志化、支持多种导出目标
"""

import logging
import json
import os
from typing import Any, Dict, Optional

# 第三方库预留（实际使用时取消注释）
# import requests
# from lark_oapi import Client

# 日志配置（可通过配置文件覆盖）
LOG = logging.getLogger("LarkExporter")
LOG.setLevel(logging.INFO)
if not LOG.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(asctime)s] %(name)s %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    LOG.addHandler(handler)

class LarkExporter:
    """
    飞书导出核心类
    支持导出到飞书云文档、多维表格、消息群组等
    配置驱动，默认从 config/lark_export.json 加载
    """

    DEFAULT_CONFIG_PATH = "config/lark_export.json"

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化导出器
        :param config_path: 配置文件路径，若为None则使用默认路径
        """
        self.config = self._load_config(config_path or self.DEFAULT_CONFIG_PATH)
        self.app_id = self.config.get("app_id", "")
        self.app_secret = self.config.get("app_secret", "")
        self.base_url = self.config.get("base_url", "https://open.feishu.cn/open-apis")
        self.logger = LOG
        self.logger.info("飞书导出器初始化完成，app_id: %s", self.app_id[:4] + "****" if self.app_id else "未设置")
        # 可扩展：在此初始化API客户端（如果库存在）
        # self.client = Client(app_id=self.app_id, app_secret=self.app_secret)

    def _load_config(self, path: str) -> Dict[str, Any]:
        """加载配置文件，若失败则返回默认空配置"""
        if not os.path.exists(path):
            self.logger.warning("配置文件 %s 不存在，使用默认配置", path)
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                config = json.load(f)
            self.logger.debug("成功加载配置文件: %s", path)
            return config
        except Exception as e:
            self.logger.error("加载配置文件失败: %s, 错误: %s", path, e)
            return {}

    def export_to_doc(self, content: str, doc_token: Optional[str] = None, title: str = "NovelOS 导出") -> bool:
        """
        导出内容到飞书文档
        :param content: 要导出的文本内容（支持Markdown）
        :param doc_token: 目标文档Token，若为None则创建新文档
        :param title: 文档标题（仅当创建新文档时有效）
        :return: 成功返回True，否则False
        """
        # TODO: 实际API调用骨架
        self.logger.info("开始导出到飞书文档，标题: %s", title)
        try:
            # 获取 tenant_access_token
            # token = self._get_tenant_token()
            # 调用创建文档或更新文档API
            # 模拟成功
            self.logger.debug("文档导出模拟: 内容长度 %d 字符", len(content))
            # 正常情况下返回响应，检查是否成功
            self.logger.info("飞书文档导出成功（模拟）")
            return True
        except Exception as e:
            self.logger.exception("飞书文档导出失败: %s", e)
            return False

    def export_to_sheet(self, data: list, sheet_token: Optional[str] = None, sheet_title: str = "NovelOS Data") -> bool:
        """
        导出数据到飞书多维表格
        :param data: 二维列表，每一行是一条记录
        :param sheet_token: 目标多维表格Token，若为None则创建新的
        :param sheet_title: 表格标题（仅在新建时有效）
        :return: 成功返回True，否则False
        """
        self.logger.info("开始导出到飞书多维表格，标题: %s", sheet_title)
        try:
            # token = self._get_tenant_token()
            # 调用创建或追加数据API
            self.logger.debug("表格导出模拟: 行数 %d, 列数 %d", len(data), len(data[0]) if data else 0)
            self.logger.info("飞书多维表格导出成功（模拟）")
            return True
        except Exception as e:
            self.logger.exception("飞书多维表格导出失败: %s", e)
            return False

    def send_message(self, chat_id: str, msg_type: str = "text", content: Any = None) -> bool:
        """
        发送消息到飞书群组或个人
        :param chat_id: 目标会话ID
        :param msg_type: 消息类型 (text, post, image, interactive等)
        :param content: 消息内容，根据类型提供相应结构
        :return: 成功返回True，否则False
        """
        self.logger.info("开始发送飞书消息到 %s, 类型: %s", chat_id, msg_type)
        try:
            # token = self._get_tenant_token()
            # 调用消息API
            self.logger.debug("消息发送模拟: 内容 %s", str(content)[:100])
            self.logger.info("飞书消息发送成功（模拟）")
            return True
        except Exception as e:
            self.logger.exception("飞书消息发送失败: %s", e)
            return False

    def _get_tenant_token(self) -> str:
        """
        获取 tenant_access_token（内部使用，需要实现）
        :return: token字符串
        """
        # 实际应调用飞书认证接口
        raise NotImplementedError("tenant_access_token 获取需实现认证逻辑")

    def reload_config(self, config_path: Optional[str] = None):
        """重新加载配置文件，支持热更新"""
        path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = self._load_config(path)
        self.app_id = self.config.get("app_id", self.app_id)
        self.app_secret = self.config.get("app_secret", self.app_secret)
        self.base_url = self.config.get("base_url", self.base_url)
        self.logger.info("配置已重新加载")

# 自测与演示
if __name__ == "__main__":
    # 创建导出器实例（若无配置文件则使用默认空配置）
    exporter = LarkExporter()

    # 模拟导出内容
    test_content = "# 第一章\n夜色深沉，万籁俱寂。"
    test_data = [
        ["章节", "字数", "情绪值"],
        ["第一章", 1234, "悬疑"],
        ["第二章", 2345, "温馨"]
    ]

    # 测试导出到文档
    print("=== 测试导出到飞书文档 ===")
    exporter.export_to_doc(test_content, title="测试小说章节")

    # 测试导出到多维表格
    print("=== 测试导出到飞书多维表格 ===")
    exporter.export_to_sheet(test_data, sheet_title="章节统计")

    # 测试发送消息
    print("=== 测试发送飞书消息 ===")
    exporter.send_message(chat_id="oc_xxx", msg_type="text", content={"text": "导出完成"})

    # 测试重新加载配置（即使配置文件不存在，也不会崩溃）
    exporter.reload_config()