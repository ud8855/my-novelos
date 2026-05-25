"""25_UI界面/Token监控/Token监控.py - Token监控UI组件骨架
符合NovelOS架构：可插拔、日志、配置化、单一职责、依赖注入
依赖：TokenDataProvider接口（由20_模型协同或21_API模型实现）
被调用：UI主框架或令牌监控管理器
"""

import logging
import configparser
import os
import time
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

# 默认配置文件路径
DEFAULT_CONFIG_PATH = os.path.join("config", "token_monitor.conf")
SECTION_NAME = "TokenMonitor"

logger = logging.getLogger(__name__)


class TokenDataProvider(ABC):
    """Token数据提供者抽象接口,由底层模型协同模块实现"""
    
    @abstractmethod
    def get_current_token_usage(self) -> Dict[str, Any]:
        """
        获取当前Token使用统计
        
        Returns:
            字典包含:
                total_tokens (int): 累计消耗Token总数
                prompt_tokens (int): 提示词Token数
                completion_tokens (int): 补全Token数
                estimated_cost (float): 预估费用(美元)
                timestamp (float): 数据时间戳
        """
        pass


class TokenMonitor:
    """
    Token监控UI组件
    
    职责:
    - 定期查询Token使用数据
    - 将数据传递到界面展示
    - 可配置启用/禁用与刷新间隔
    
    可插拔特性: 通过配置文件TokenMonitor.enable字段控制启用状态,
               通过依赖注入切换实际数据源,不影响UI层其他部分
    """
    
    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH,
                 data_provider: Optional[TokenDataProvider] = None):
        self._config_path = config_path
        self.config = configparser.ConfigParser()
        self.config.read(config_path, encoding='utf-8')
        
        # 配置化参数
        self.enabled = self.config.getboolean(SECTION_NAME, 'enable', fallback=False)
        self.refresh_interval = self.config.getfloat(SECTION_NAME, 'refresh_interval', fallback=5.0)
        
        self.data_provider = data_provider
        self._running = False
        self._thread = None
        
        logger.info(f"TokenMonitor initialized: enabled={self.enabled}, interval={self.refresh_interval}s")
    
    def set_data_provider(self, provider: TokenDataProvider):
        """设置数据提供者(热插拔)"""
        self.data_provider = provider
        logger.info("Token data provider updated")
    
    def start(self):
        """启动监控任务"""
        if not self.enabled:
            logger.info("TokenMonitor disabled by config")
            return
            
        if self.data_provider is None:
            logger.error("Cannot start: data_provider not set")
            raise RuntimeError("Token data provider missing")
        
        if self._running:
            logger.warning("TokenMonitor already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("TokenMonitor started")
    
    def stop(self):
        """停止监控任务"""
        if not self._running:
            return
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("TokenMonitor stopped")
    
    def update_display(self, data: Dict[str, Any]):
        """
        更新UI显示(供外部或内部循环调用)
        
        Args:
            data: Token使用数据字典, 格式同TokenDataProvider返回
        """
        # 骨架: 仅记录日志,真实实现会通知UI组件刷新
        logger.debug(f"Display update: total={data.get('total_tokens')}, cost={data.get('estimated_cost')}")
    
    def _monitor_loop(self):
        """后台监控循环"""
        while self._running:
            try:
                if self.data_provider:
                    data = self.data_provider.get_current_token_usage()
                    self.update_display(data)
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
            time.sleep(self.refresh_interval)


# ================== 自测部分 ==================
if __name__ == "__main__":
    # 配置测试日志
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
    
    # 确保配置文件存在
    os.makedirs("config", exist_ok=True)
    if not os.path.exists(DEFAULT_CONFIG_PATH):
        with open(DEFAULT_CONFIG_PATH, 'w', encoding='utf-8') as f:
            f.write(f"[{SECTION_NAME}]\n")
            f.write("enable = True\n")
            f.write("refresh_interval = 2.0\n")
    
    # 模拟数据提供者(自测用)
    class MockTokenProvider(TokenDataProvider):
        def get_current_token_usage(self) -> Dict[str