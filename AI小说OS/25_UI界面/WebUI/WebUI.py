"""
Module: 25_UI界面/WebUI/WebUI.py
Layer: UI层 (表现层)
Dependencies: 系统配置模块, 日志模块
Called by: 主程序启动, 作为用户交互界面
Solves: 提供可插拔的Web服务框架, 允许动态注册路由/蓝图, 支持配置化与日志记录
"""

import logging
import importlib
from flask import Flask

# 尝试导入系统配置与日志模块 (如果存在)
try:
    from system_config import config_manager   # 实际路径可能为 00_系统配置
    from system_log import log_manager         # 实际路径可能为 01_日志系统
except ImportError:
    config_manager = None
    log_manager = None


class WebUI:
    """可插拔的WebUI服务框架"""

    def __init__(self, config_path=None):
        self.config = self._load_config(config_path)
        self.logger = self._setup_logger()
        self.app = Flask(__name__)
        self.app.config.update(self.config.get('flask', {}))
        self._register_builtin_routes()
        self.logger.info("WebUI initialized")

    def _load_config(self, config_path):
        """从系统配置模块加载配置, 失败则使用默认配置"""
        if config_manager:
            return config_manager.get_module_config('webui')
        # 默认配置
        return {
            'host': '0.0.0.0',
            'port': 5000,
            'debug': False,
            'flask': {
                'SECRET_KEY': 'dev-secret'
            }
        }

    def _setup_logger(self):
        """从日志系统获取logger, 否则使用标准logging"""
        if log_manager:
            return log_manager.get_logger('WebUI')
        logger = logging.getLogger('WebUI')
        logger.setLevel(logging.DEBUG)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    def _register_builtin_routes(self):
        """注册内置路由 (健康检查等)"""
        @self.app.route('/health')
        def health():
            return {'status': 'ok'}

    def register_blueprint(self, blueprint, url_prefix=None):
        """注册Flask蓝图 (可插拔扩展点)"""
        self.app.register_blueprint(blueprint, url_prefix=url_prefix)
        self.logger.info(
            f"Registered blueprint: {blueprint.name} at {url_prefix}"
        )

    def register_module(self, module_path, url_prefix=None):
        """
        动态加载模块并注册其蓝图 (插件式)
        module_path: Python模块路径, 如 'modules.dashboard.bp'
        """
        try:
            mod = importlib.import_module(module_path)
            bp = getattr(mod, 'blueprint', None) or getattr(mod, 'bp', None)
            if bp:
                self.register_blueprint(bp, url_prefix=url_prefix)
            else:
                self.logger.warning(f"No blueprint found in {module_path}")
        except Exception as e:
            self.logger.error(f"Failed to register module {module_path}: {e}")

    def run(self):
        """启动Web服务 (可用于自测)"""
        self.logger.info("Starting WebUI...")
        self.app.run(
            host=self.config.get('host', '127.0.0.1'),
            port=self.config.get('port', 5000),
            debug=self.config.get('debug', False)
        )


# 自测入口
if __name__ == '__main__':
    webui = WebUI()
    # 示例: 可以在这里动态注册测试蓝图
    # from test_blueprint import bp as test_bp
    # webui.register_blueprint(test_bp)
    webui.run()