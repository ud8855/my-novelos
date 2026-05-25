"""
Agent监控 UI模块
属于: 25_UI界面/Agent监控
依赖: 核心监控服务接口 (通过依赖注入)
被调用: 系统启动器或用户界面管理器
解决: 展示Agent运行状态、性能指标、异常信息等
"""

import logging
import configparser
import time
import sys
from typing import Optional, Dict, Any, List

# 假设的监控数据接口规范，实际应由 20_模型协同/ 或专门的监控服务提供
# UI层不直接依赖底层实现，仅依赖抽象接口


class AgentMonitorDataSource:
    """监控数据源抽象接口，供依赖注入使用"""

    def get_all_agent_status(self) -> List[Dict[str, Any]]:
        """获取所有Agent的状态摘要"""
        raise NotImplementedError

    def get_agent_detail(self, agent_id: str) -> Dict[str, Any]:
        """获取指定Agent的详细信息"""
        raise NotImplementedError

    def get_system_health(self) -> Dict[str, Any]:
        """获取整体系统健康状态"""
        raise NotImplementedError


class AgentMonitorUI:
    """Agent监控UI，可插拔设计，通过注入的数据源获取监控信息"""

    def __init__(self,
                 monitor_data_source: Optional[AgentMonitorDataSource] = None,
                 config_path: str = "config/agent_monitor_ui.ini"):
        """
        :param monitor_data_source: 监控数据源接口实现，可插拔，默认为None(需要在启动时注入)
        :param config_path: 配置文件路径
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self._load_config(config_path)
        self._data_source = monitor_data_source
        self._refresh_interval = self._config.getfloat('ui', 'refresh_interval_sec', fallback=5.0)
        self._is_running = False
        self._logger.info("AgentMonitorUI initialized, refresh interval=%.2fs", self._refresh_interval)

    def _load_config(self, config_path: str):
        """加载UI配置文件"""
        self._config = configparser.ConfigParser()
        try:
            self._config.read(config_path)
            self._logger.debug("Config loaded from %s", config_path)
        except Exception as e:
            self._logger.warning("Failed to load config, using defaults. Error: %s", e)
            # 确保有默认值
            self._config = configparser.ConfigParser()
            self._config.add_section('ui')
            self._config.set('ui', 'refresh_interval_sec', '5.0')

    def set_data_source(self, data_source: AgentMonitorDataSource):
        """设置/更换数据源，实现热插拔"""
        self._data_source = data_source
        self._logger.info("Monitor data source set/updated.")

    def run(self):
        """启动监控UI主循环（控制台输出示例）"""
        if self._data_source is None:
            self._logger.error("No data source provided. Cannot start monitoring.")
            print("错误：未提供监控数据源，请先调用 set_data_source()")
            return

        self._is_running = True
        self._logger.info("Agent monitor UI started.")
        try:
            while self._is_running:
                self._display_status()
                time.sleep(self._refresh_interval)
        except KeyboardInterrupt:
            self._logger.info("Monitor UI interrupted by user.")
            self.stop()

    def _display_status(self):
        """刷新并显示当前状态（简单控制台输出）"""
        try:
            agents = self._data_source.get_all_agent_status()
            health = self._data_source.get_system_health()
            self._render(agents, health)
        except Exception as e:
            self._logger.error("Failed to retrieve or render status: %s", e, exc_info=True)
            print(f"[ERROR] 监控数据获取/渲染失败: {e}")

    def _render(self, agents: List[Dict[str, Any]], health: Dict[str, Any]):
        """渲染监控信息到控制台"""
        # 清屏 (简单方式)
        print("\033c", end="")  # ANSI清屏
        print("=" * 60)
        print("Agent监控面板")
        print(f"系统健康状态: {health.get('status', 'unknown')}")
        print("-" * 60)
        if agents:
            for agent in agents:
                aid = agent.get('id', '?')
                status = agent.get('status', '?')
                task = agent.get('current_task', 'idle')
                print(f"Agent [{aid}] 状态: {status}  当前任务: {task}")
        else:
            print("当前无活跃Agent")
        print("=" * 60)
        print(f"自动刷新间隔: {self._refresh_interval}秒  (按Ctrl+C退出)")

    def stop(self):
        """停止监控UI"""
        self._is_running = False
        self._logger.info("Agent monitor UI stopped.")


# ------------ 自测模块 ------------
class MockMonitorDataSource(AgentMonitorDataSource):
    """模拟数据源，用于自测"""

    def get_all_agent_status(self) -> List[Dict[str, Any]]:
        return [
            {"id": "agent_01", "status": "working", "current_task": "plot_design"},
            {"id": "agent_02", "status": "idle", "current_task": "None"},
            {"id": "agent_03", "status": "error", "current_task": "style_review",
             "error_msg": "Token limit exceeded"},
        ]

    def get_agent_detail(self, agent_id: str) -> Dict[str, Any]:
        return {"id": agent_id, "memory_usage": "1.2G", "api_calls": 245}

    def get_system_health(self) -> Dict[str, Any]:
        return {"status": "healthy", "uptime": "1h 23m", "overall_load": 0.74}


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        handlers=[logging.StreamHandler(sys.stdout)])

    # 创建UI实例，使用模拟数据源
    mock_source = MockMonitorDataSource()
    ui = AgentMonitorUI(config_path="config/agent_monitor_ui.ini")
    ui.set_data_source(mock_source)

    # 运行监控UI（测试用，设较短刷新间隔）
    ui._refresh_interval = 2.0  # 测试快速刷新
    ui.run()
    # 注意：run() 是阻塞主循环，若要退出可按Ctrl+C