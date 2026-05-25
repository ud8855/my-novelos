"""Web入口 - NovelOS Web服务启动入口
层级：00_启动入口
依赖：配置模块(config)，日志模块(logging)，插件管理器(PluginManager - 待实现)
被谁调用：直接作为主程序运行
解决：初始化并启动Web服务器，挂载所有可插拔的功能模块
"""

import logging
import sys
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ==================== 配置加载（可插拔的配置源） ====================
try:
    # 尝试从外部配置模块导入，若不存在则使用默认配置
    from config import WEB_CONFIG, LOG_CONFIG
except ImportError:
    # 默认配置，方便自测与快速启动
    WEB_CONFIG = {
        "host": "0.0.0.0",
        "port": 8000,
        "reload": False,        # 生产环境关闭自动重载
        "debug": False,
        "workers": 1
    }
    LOG_CONFIG = {
        "level": logging.INFO,
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S"
    }

# ==================== 日志系统初始化 ====================
def setup_logging(config: dict = None):
    """配置全局日志（支持运行时重配）"""
    if config is None:
        config = LOG_CONFIG
    logging.basicConfig(
        level=config.get("level", logging.INFO),
        format=config.get("format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s"),
        datefmt=config.get("datefmt", "%Y-%m-%d %H:%M:%S"),
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    # 降低第三方库的日志级别，避免干扰
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ==================== 插件管理器骨架（可插拔核心） ====================
class PluginManager:
    """
    插件管理器（空骨架）
    职责：发现、加载、卸载、启停所有业务插件
    待实现：扫描指定目录，动态导入模块，注册路由，管理生命周期
    """
    def __init__(self, app: FastAPI):
        self.app = app
        self.plugins = {}
        logger.info("PluginManager initialized (empty skeleton)")

    def discover(self, plugin_dir: str = "plugins"):
        """发现插件目录下的模块（待实现）"""
        logger.info(f"Discovering plugins in {plugin_dir} (not implemented)")
        # 未来将扫描目录，动态导入

    def load(self, plugin_name: str):
        """加载单个插件（待实现）"""
        logger.info(f"Loading plugin: {plugin_name} (not implemented)")

    def unload(self, plugin_name: str):
        """卸载插件（待实现）"""
        logger.info(f"Unloading plugin: {plugin_name} (not implemented)")

    def reload(self, plugin_name: str):
        """热更新单个插件（待实现）"""
        logger.info(f"Reloading plugin: {plugin_name} (not implemented)")

    def start_all(self):
        """启动所有插件（待实现）"""
        logger.info("Starting all plugins (no plugins registered yet)")

    def stop_all(self):
        """停止所有插件（待实现）"""
        logger.info("Stopping all plugins (no plugins registered yet)")


# ==================== 应用工厂 ====================
def create_app() -> FastAPI:
    """创建并配置FastAPI应用实例"""
    _app = FastAPI(
        title="NovelOS Web Service",
        description="AI小说创作操作系统 - Web接口层",
        version="0.1.0",
        docs_url="/docs" if WEB_CONFIG.get("debug") else None,  # 生产可关闭文档
        redoc_url=None,
    )

    # CORS 配置（允许前端开发跨域，生产应从配置读取）
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=WEB_CONFIG.get("cors_origins", ["*"]),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 内置健康检查端点（基础版，可后续由插件增强）
    @_app.get("/health", tags=["system"])
    async def health_check():
        return {"status": "ok", "service": "NovelOS Web Entry"}

    # 挂载插件管理器（空壳）
    plugin_manager = PluginManager(_app)
    _app.state.plugin_manager = plugin_manager

    # 启动时预扫描/加载插件（当前无操作）
    plugin_manager.discover()
    plugin_manager.start_all()

    logger.info("Application created successfully")
    return _app


# ==================== 启动入口 ====================
def main():
    """主启动函数，包含异常恢复和优雅退出"""
    try:
        setup_logging()
        logger.info("=== NovelOS Web Entry Starting ===")
        app = create_app()

        # 从配置读取运行参数
        host = WEB_CONFIG.get("host", "0.0.0.0")
        port = WEB_CONFIG.get("port", 8000)
        reload = WEB_CONFIG.get("reload", False)
        workers = WEB_CONFIG.get("workers", 1)

        logger.info(f"Uvicorn running on {host}:{port} (reload={reload}, workers={workers})")
        uvicorn.run(
            "Web入口:app",          # 字符串路径，以便reload时正确重载
            host=host,
            port=port,
            reload=reload,
            workers=workers,
            log_config=None,        # 使用我们自己的日志配置
            log_level=LOG_CONFIG.get("level", logging.INFO).lower()
        )
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.exception(f"Fatal error during startup: {e}")
        sys.exit(1)
    finally:
        # 关闭插件（扩展点）
        if 'app' in locals() and hasattr(app.state, 'plugin_manager'):
            app.state.plugin_manager.stop_all()
        logger.info("=== NovelOS Web Entry Stopped ===")


# ==================== 自测：直接运行 ====================
if __name__ == "__main__":
    # 方便直接使用 `python Web入口.py` 启动
    # 为了更好地支持 reload，也可以用 app 实例
    import uvicorn
    setup_logging()
    app = create_app()
    uvicorn.run(
        app,
        host=WEB_CONFIG.get("host", "0.0.0.0"),
        port=WEB_CONFIG.get("port", 8000),
        log_config=None,
        log_level=LOG_CONFIG.get("level", "info").lower()
    )