# -*- coding: utf-8 -*-
"""
模块路径: 25_UI界面/状态面板/状态面板.py
所属层级: UI界面层
依赖: 无（可后续注入状态提供者）
被调用: 主界面(主控台)、任务管理器、Agent监控等需要展示系统状态的组件
解决问题: 提供统一、可插拔的系统状态可视化面板，展示Agent运行状态、进度、资源占用等信息。
        支持热插拔状态项，所有数据通过回调获取，不直接访问数据库或API。
        遵循配置化、日志记录、异常恢复原则。
"""

import logging
import json
import os
from typing import Callable, Dict, Any, Optional, List
from datetime import datetime

# 默认配置路径
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "state_panel_config.json")

class StatePanel:
    """
    系统状态面板组件。
    特性：
        - 可插拔：通过注册机制动态添加/移除状态显示项
        - 配置化：所有显示项参数可通过配置文件定义
        - 日志：完整记录面板初始化和状态更新事件
        - 异常恢复：每个状态项独立更新，一个失败不影响其他
        - 热更新：注册项可在运行时增删，无需重启
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化状态面板。
        :param config_path: 配置文件路径，若为None则使用默认路径
        """
        self._config: Dict[str, Any] = {}
        self._state_items: Dict[str, Dict[str, Any]] = {}  # key -> {'func': Callable, 'refresh_interval': float, ...}
        self._logger = logging.getLogger(self.__class__.__name__)
        self._setup_logging()

        # 加载配置
        self._config_path = config_path or DEFAULT_CONFIG_PATH
        self._load_config()

        self._last_update = datetime.now()
        self._logger.info("StatePanel initialized successfully.")

    def _setup_logging(self):
        """配置日志记录器"""
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(name)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def _load_config(self):
        """
        加载配置文件。
        配置格式示例：
        {
            "auto_refresh": true,
            "refresh_interval": 1.0,
            "default_display_order": ["agent_status", "system_resource", "progress"]
        }
        若文件不存在则使用默认配置。
        """
        default_config = {
            "auto_refresh": True,
            "refresh_interval": 1.0,
            "default_display_order": []
        }
        try:
            if os.path.exists(self._config_path):
                with open(self._config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                self._config = {**default_config, **user_config}
                self._logger.info(f"Configuration loaded from {self._config_path}")
            else:
                self._config = default_config
                self._logger.warning(f"Config file {self._config_path} not found, using defaults.")
        except Exception as e:
            self._logger.error(f"Failed to load config: {e}, using defaults.")
            self._config = default_config

    def register_state_item(self, key: str, update_func: Callable[[], Any],
                            refresh_interval: Optional[float] = None,
                            display_name: Optional[str] = None) -> bool:
        """
        注册一个状态显示项。
        :param key: 唯一标识符
        :param update_func: 获取状态数据的回调函数，返回任意可显示内容
        :param refresh_interval: 更新间隔（秒），为None时使用全局配置
        :param display_name: 显示名称，用于UI标签
        :return: 注册成功返回True，重复key返回False
        """
        if key in self._state_items:
            self._logger.warning(f"State item '{key}' already registered.")
            return False

        interval = refresh_interval if refresh_interval is not None else self._config.get("refresh_interval", 1.0)
        self._state_items[key] = {
            'func': update_func,
            'refresh_interval': interval,
            'display_name': display_name or key,
            'last_result': None,
            'error_count': 0
        }
        self._logger.info(f"State item registered: key='{key}', display='{display_name or key}', interval={interval}s")
        return True

    def unregister_state_item(self, key: str) -> bool:
        """
        移除一个状态显示项。
        :param key: 注册时的唯一标识
        :return: 存在并移除返回True，否则False
        """
        if key in self._state_items:
            del self._state_items[key]
            self._logger.info(f"State item unregistered: '{key}'")
            return True
        self._logger.warning(f"Attempt to unregister unknown state item: '{key}'")
        return False

    def update_display(self) -> Dict[str, Any]:
        """
        刷新所有注册状态项的数据，并记录更新日志。
        每个状态项独立调用，单个失败不会中断整体流程。
        :return: 更新后的状态数据字典，key为状态项标识，value为最新数据
        """
        updated_data = {}
        self._last_update = datetime.now()
        for key, item in list(self._state_items.items()):
            try:
                data = item['func']()
                item['last_result'] = data
                item['error_count'] = 0  # 重置错误计数
                updated_data[key] = data
                self._logger.debug(f"Updated state item '{key}': {data}")
            except Exception as e:
                item['error_count'] += 1
                self._logger.exception(f"Error updating state item '{key}' (errors: {item['error_count']}): {e}")
                updated_data[key] = f"ERROR: {str(e)}"
        return updated_data

    def render(self) -> str:
        """
        渲染状态面板为字符串（或其他形式，需子类实现具体UI）。
        当前骨架返回一个格式化的文本表示，用于控制台测试。
        :return: 面板的文本显示
        """
        data = self.update_display()
        output_lines = ["===== System State Panel ====="]
        output_lines.append(f"Last update: {self._last_update.strftime('%Y-%m-%d %H:%M:%S')}")
        if not data:
            output_lines.append("No state items registered.")
        else:
            # 使用配置中的显示顺序，若没有则按自然顺序
            order = self._config.get("default_display_order", list(data.keys()))
            # 确保所有已注册的key都被包含（可能有新增项未在配置中）
            all_keys = list(data.keys())
            for key in order:
                if key in data:
                    all_keys.remove(key)
            # 最终的顺序：先按配置顺序，然后剩余key按字母排序
            final_order = order + sorted(all_keys)
            for key in final_order:
                if key in data:
                    item_info = self._state_items.get(key, {})
                    display_name = item_info.get('display_name', key)
                    value = data[key]
                    # 简短的值显示
                    str_value = str(value)
                    if len(str_value) > 80:
                        str_value = str_value[:77] + "..."
                    output_lines.append(f"  {display_name}: {str_value}")
        return "\n".join(output_lines)

    def auto_refresh_loop(self, stop_event=None):
        """
        自动刷新循环，按全局刷新间隔不断更新并渲染。
        可用于独立线程。
        :param stop_event: threading.Event对象，用于停止循环
        """
        import time
        import threading
        self._logger.info("Auto refresh loop started.")
        while not (stop_event and stop_event.is_set()):
            try:
                rendered = self.render()
                # 这里可以调用上层UI的刷新方法（通过回调注入）
                print(rendered)  # 临时输出到控制台
                time.sleep(self._config.get("refresh_interval", 1.0))
            except Exception as e:
                self._logger.exception(f"Auto refresh loop error: {e}")
                time.sleep(5)  # 异常后延长冷却
        self._logger.info("Auto refresh loop stopped.")


# ----------------- 自测代码 -----------------
def _self_test():
    """模块自测：演示注册状态项、手动更新和自动刷新。"""
    import random
    import time
    import threading

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    panel = StatePanel()  # 使用默认配置

    # 模拟的函数提供状态数据
    def agent_status_func():
        agents = ["Agent_NovelOutline", "Agent_ChapterWrite", "Agent_Review"]
        return {name: random.choice(["running", "idle", "error"]) for name in agents}

    def resource_func():
        import psutil  # 这里仅演示，实际可能没有psutil，使用伪数据
        try:
            cpu = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory().percent
            return f"CPU: {cpu}% | MEM: {mem}%"
        except ImportError:
            return "CPU: 45% (simulated) | MEM: 62% (simulated)"

    def progress_func():
        return f"Chapter 3/5: 60%"

    # 注册状态项
    panel.register_state_item("agent_status", agent_status_func, refresh_interval=2.0, display_name="Agent运行状态")
    panel.register_state_item("system_resource", resource_func, refresh_interval=1.0, display_name="系统资源")
    panel.register_state_item("progress", progress_func, refresh_interval=5.0, display_name="创作进度")

    print("=" * 50)
    print("Manual test: single render")
    print(panel.render())
    print("=" * 50)

    # 测试自动刷新循环（运行5秒）
    stop_event = threading.Event()
    refresh_thread = threading.Thread(target=panel.auto_refresh_loop, args=(stop_event,), daemon=True)
    refresh_thread.start()
    time.sleep(6)
    stop_event.set()
    refresh_thread.join(timeout=2)
    print("Auto-refresh test completed.")

    # 测试卸载一个项