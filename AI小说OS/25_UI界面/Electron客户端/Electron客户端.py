"""  
NovelOS - Electron客户端骨架  
层级：25_UI界面  
依赖：无（抽象接口，不直接依赖数据库、模型等）  
被调用：由UI层发起，通过Runtime与系统其他模块交互  
职责：定义Electron客户端的统一接口，负责与Electron前端的生命周期管理、双向通信。  
可插拔：通过继承实现不同的Electron集成方式（如Eel、Flask-SocketIO、本地WebSocket等）  
支持热更新：预留重载前端页面的接口  
异常恢复：内建自动重启机制  
日志与配置化：使用标准logging，配置从UI配置模块读取  
"""  

import abc  
import logging  
import threading  
import time  
import sys  
from typing import Any, Callable, Dict, Optional  

# 配置化：假定UI层有自己的配置模块  
try:  
    from .config import ElectronConfig  
except ImportError:  
    # 简单后备配置  
    class ElectronConfig:  
        HOST = "127.0.0.1"  
        PORT = 8000  
        WINDOW_TITLE = "NovelOS"  
        WINDOW_WIDTH = 1024  
        WINDOW_HEIGHT = 768  
        AUTO_START = True  
        RESTART_ON_ERROR = True  
        RESTART_DELAY = 3  # 秒  

# 日志配置  
logger = logging.getLogger(__name__)  
logging.basicConfig(  
    level=logging.INFO,  
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",  
    handlers=[logging.StreamHandler(sys.stdout)]  
)  

class ElectronClientBase(abc.ABC):  
    """  
    Electron客户端抽象接口  
    定义了与Electron前端交互所需的核心方法  
    """  

    def __init__(self, config: Optional[ElectronConfig] = None):  
        self.config = config or ElectronConfig()  
        self._server_thread = None  
        self._running = False  
        self._event_handlers: Dict[str, Callable] = {}  

    def start(self) -> None:  
        """启动Electron客户端（含本地服务器及Electron进程）"""  
        if self._running:  
            logger.warning("Electron client is already running.")  
            return  
        logger.info("Starting Electron client...")  
        try:  
            self._start_impl()  
            self._running = True  
            logger.info("Electron client started successfully.")  
        except Exception as e:  
            logger.error(f"Failed to start Electron client: {e}", exc_info=True)  
            if self.config.RESTART_ON_ERROR:  
                self._schedule_restart()  
            raise  

    @abc.abstractmethod  
    def _start_impl(self) -> None:  
        """具体启动实现，由子类完成"""  
        pass  

    def stop(self) -> None:  
        """停止Electron客户端"""  
        if not self._running:  
            return  
        logger.info("Stopping Electron client...")  
        try:  
            self._stop_impl()  
        except Exception as e:  
            logger.error(f"Error stopping Electron client: {e}")  
        finally:  
            self._running = False  
            logger.info("Electron client stopped.")  

    @abc.abstractmethod  
    def _stop_impl(self) -> None:  
        """具体停止实现，由子类完成"""  
        pass  

    def send_to_renderer(self, channel: str, data: Any) -> None:  
        """向Electron渲染进程发送消息"""  
        if not self._running:  
            logger.warning("Cannot send message: client not running.")  
            return  
        logger.debug(f"Sending message to renderer on channel '{channel}': {data}")  
        try:  
            self._send_to_renderer_impl(channel, data)  
        except Exception as e:  
            logger.error(f"Error sending message: {e}")  
            if self.config.RESTART_ON_ERROR:  
                self._schedule_restart()  

    @abc.abstractmethod  
    def _send_to_renderer_impl(self, channel: str, data: Any) -> None:  
        """具体发送实现"""  
        pass  

    def on_message_from_renderer(self, channel: str, callback: Callable) -> None:  
        """注册渲染进程发来消息的回调"""  
        self._event_handlers[channel] = callback  
        logger.info(f"Registered callback for channel '{channel}'.")  

    def _handle_message(self, channel: str, data: Any) -> None:  
        """内部处理消息，分发到注册的回调"""  
        if channel in self._event_handlers:  
            try:  
                self._event_handlers[channel](data)  
            except Exception as e:  
                logger.error(f"Error in callback for channel '{channel}': {e}")  
        else:  
            logger.warning(f"No handler for channel '{channel}'.")  

    def reload(self) -> None:  
        """热更新前端页面（如果支持）"""  
        logger.info("Reloading frontend...")  
        try:  
            self._reload_impl()  
        except Exception as e:  
            logger.error(f"Reload failed: {e}")  

    @abc.abstractmethod  
    def _reload_impl(self) -> None:  
        """具体重载实现"""  
        pass  

    def _schedule_restart(self) -> None:  
        """异常恢复：延迟重启"""  
        logger.info(f"Scheduling restart in {self.config.RESTART_DELAY} seconds...")  
        def restart():  
            time.sleep(self.config.RESTART_DELAY)  
            try:  
                self.stop()  
                self.start()  
            except Exception as e:  
                logger.critical(f"Restart attempt failed: {e}")  
        threading.Thread(target=restart, daemon=True).start()  

    @property  
    def is_running(self) -> bool:  
        return self._running  


class ElectronClient(ElectronClientBase):  
    """  
    Electron客户端的默认实现（骨架）  
    目前使用占位实现，需要根据实际选用的集成方案进行填充  
    """  

    def _start_impl(self) -> None:  
        # TODO: 启动后端服务（如Flask-SocketIO）并启动Electron子进程  
        raise NotImplementedError("ElectronClient._start_impl must be implemented.")  

    def _stop_impl(self) -> None:  
        # TODO: 关闭Electron进程及后端服务  
        raise NotImplementedError("ElectronClient._stop_impl must be implemented.")  

    def _send_to_renderer_impl(self, channel: str, data: Any) -> None:  
        # TODO: 通过IPC发送消息  
        raise NotImplementedError("ElectronClient._send_to_renderer_impl must be implemented.")  

    def _reload_impl(self) -> None:  
        # TODO: 通知前端重新加载  
        raise NotImplementedError("ElectronClient._reload_impl must be implemented.")  


# 自测部分  
if __name__ == "__main__":  
    print("=== Electron客户端骨架自测 ===")  
    # 创建实例  
    client = ElectronClient()  
    print(f"配置: 窗口标题={client.config.WINDOW_TITLE}, 端口={client.config.PORT}")  
    print(f"客户端运行状态: {client.is_running}")  

    # 注册一个测试回调  
    def test_callback(data):  
        print(f"收到消息: {data}")  
    client.on_message_from_renderer("test_channel", test_callback)  

    # 尝试启动（会抛出NotImplementedError，因为未实现具体后端）  
    try:  
        client.start()  
    except NotImplementedError as e:  
        print(f"预期异常 (作为骨架): {e}")  

    print("自测完成，骨架正常工作。")