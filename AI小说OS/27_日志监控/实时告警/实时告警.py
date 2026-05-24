import logging
import time
import threading
from typing import Dict, List, Callable, Any, Optional
import json
import os

# 默认配置，所有可配置项均提供合理初始值
DEFAULT_CONFIG = {
    "alerter_name": "default",
    "alert_rules": {},                     # {rule_name: { "condition": callable, "template": str, "channels": [str] }}
    "notifier_plugins": {},                # {channel_name: callable(alert_message) }
    "throttle_interval_seconds": 60,       # 同一规则最小告警间隔(秒)
    "max_alerts_per_interval": 10,         # 全局速率限制(每个时间窗口最多告警数)
    "log_level": "INFO"
}

class RealtimeAlerter:
    """
    实时告警器
    职责：检查告警规则，通过可插拔的通知通道发送告警。
    特性：配置化、可插拔规则与通知通道、速率限制、线程安全、完整日志。
    """

    def __init__(self, config: Optional[Dict] = None, config_path: Optional[str] = None):
        self.config = self._load_config(config, config_path)
        # 建立专属日志记录器
        self.logger = logging.getLogger(f"RealtimeAlerter.{self.config.get('alerter_name', 'default')}")
        self._setup_logging()
        # 规则与通知通道注册表
        self.rules: Dict[str, dict] = self.config.get("alert_rules", {})
        self.notifiers: Dict[str, Callable] = self.config.get("notifier_plugins", {})
        # 限流相关状态
        self.throttle_timestamps: Dict[str, float] = {}   # 记录每条规则最近一次触发时间
        self.global_alert_count = 0
        self.global_interval_start = time.time()
        self.lock = threading.Lock()                      # 保证多线程下的规则操作安全

    def _load_config(self, config_dict=None, config_path=None):
        """加载配置，优先级：传入字典 > 配置文件 > 默认配置"""
        if config_dict:
            return {**DEFAULT_CONFIG, **config_dict}
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
            return {**DEFAULT_CONFIG, **user_config}
        return DEFAULT_CONFIG.copy()

    def _setup_logging(self):
        """根据配置设置日志级别"""
        level = getattr(logging, self.config.get("log_level", "INFO").upper(), logging.INFO)
        logging.basicConfig(level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # ---------- 插件式管理 ----------
    def register_rule(self, rule_name: str, condition_check: Callable[[], bool], alert_template: str, channels: List[str]):
        """注册一条告警规则，当 condition_check 返回 True 时向指定通道发送消息"""
        self.rules[rule_name] = {
            "condition": condition_check,
            "template": alert_template,
            "channels": channels
        }
        self.logger.info(f"Registered alert rule: {rule_name} with channels {channels}")

    def register_notifier(self, channel_name: str, notifier_func: Callable[[str], None]):
        """注册一个通知通道插件，notifier_func 接收告警消息字符串"""
        self.notifiers[channel_name] = notifier_func
        self.logger.info(f"Registered notifier: {channel_name}")

    def remove_rule(self, rule_name: str):
        """移除一条规则"""
        if rule_name in self.rules:
            del self.rules[rule_name]
            self.logger.info(f"Removed alert rule: {rule_name}")

    def remove_notifier(self, channel_name: str):
        """移除一个通知通道"""
        if channel_name in self.notifiers:
            del self.notifiers[channel_name]
            self.logger.info