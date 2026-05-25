from __future__ import annotations

import os
import sys
import signal
import json
import logging
import traceback
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, Callable

# -------- 可插拔Agent基类｜抽象协议 --------
class BaseAgent(ABC):
    """所有Agent必须实现的接口，确保热插拔和统一调度"""
    
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config
        self._running = False
        self._init_logger()

    def _init_logger(self):
        """配置独立的日志系统，支持文件与终端双输出"""
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(self.config.get("log_level", logging.INFO))
        formatter = logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
        )
        # 终端输出
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
        # 文件输出（可配置）
        log_file = self.config.get("log_file")
        if log_file:
            fh = logging.FileHandler(log_file, encoding="utf-8")
            fh.setFormatter(formatter)
            self.logger.addHandler(fh)

    @abstractmethod
    def start(self) -> None:
        """启动Agent，加载资源，注册回调等"""
        pass

    @abstractmethod
    def stop(self) -> None:
        """优雅停止，释放资源"""
        pass

    @abstractmethod
    def process(self, task: dict) -> dict:
        """处理任务的核心接口，必须幂等且可重入"""
        pass

    def is_running(self) -> bool:
        return self._running

    def health_check(self) -> bool:
        """供调度器检查健康状态"""
        return self.is_running()


# -------- 世界Agent｜骨架实现 --------
class WorldAgent(BaseAgent):
    """
    世界观管理Agent
    职责：
      1. 维护世界观一致性（地点、历史、规则、力量体系等）
      2. 根据创作任务扩展/查询世界设定
      3. 与其他Agent（如角色、情节）交互保持设定不冲突
    热插拔：通过注册回调实现对外通知，可动态挂载新规则模块
    """

    def __init__(self, config_path: Optional[str] = None):
        # 加载配置
        default_config = {
            "name": "WorldAgent",
            "log_level": logging.INFO,
            "log_file": "logs/world_agent.log",
            "world_data_path": "data/world_settings.json",
            "backup_interval": 300,  # 自动保存间隔（秒）
            "max_retries": 3,
            "hot_reload_signal": "SIGUSR1"
        }
        self.config = default_config
        if config_path and os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                file_config = json.load(f)
            self.config.update(file_config)
        super().__init__(self.config.get("name", "WorldAgent"), self.config)

        # 内部状态
        self.world_data: Dict[str, Any] = {}
        self.callbacks: Dict[str, Callable] = {}  # 热插拔通知钩子

    # -------- 核心接口实现 --------
    def start(self) -> None:
        """启动世界Agent：加载数据、启动自动保存、注册信号"""
        try:
            self._running = True
            self._load_world_data()
            self._register_hot_reload()
            self.logger.info("世界Agent已启动。")
        except Exception as e:
            self.logger.error(f"启动失败: {e}")
            raise

    def stop(self) -> None:
        """停止世界Agent：保存当前数据、清理回调"""
        self._running = False
        self._save_world_data()
        self.callbacks.clear()
        self.logger.info("世界Agent已停止。")

    def process(self, task: dict) -> dict:
        """
        处理世界观相关任务。
        task格式: {
            "action": "query" | "update" | "expand",
            "params": {...}
        }
        返回: {"status": "ok"|"error", "data": ..., "message": ""}
        """
        if not self._running:
            return {"status": "error", "message": "Agent未启动"}

        action = task.get("action", "query")
        params = task.get("params", {})
        retries = self.config["max_retries"]

        for attempt in range(1, retries + 1):
            try:
                result = self._execute_action(action, params)
                self._notify_callbacks(action, params, result)
                return {"status": "ok", "data": result}
            except Exception as e:
                self.logger.error(f"第{attempt}次尝试处理失败: {e}\n{traceback.format_exc()}")
                if attempt == retries:
                    # 异常恢复：尽可能保存状态，返回安全默认
                    self._save_world_data()
                    return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "未知错误"}

    # -------- 内部动作执行 --------
    def _execute_action(self, action: str, params: dict) -> dict:
        """根据动作分发处理（可扩展)"""
        if action == "query":
            return self._query_world(params)
        elif action == "update":
            return self._update_world(params)
        elif action == "expand":
            return self._expand_world(params)
        else:
            raise ValueError(f"不支持的动作: {action}")

    def _query_world(self, params: dict) -> dict:
        key = params.get("key")
        if not key:
            return self.world_data
        return {key: self.world_data.get(key, "未知设定")}

    def _update_world(self, params: dict) -> dict:
        key = params["key"]
        value = params["value"]
        old = self.world_data.get(key)
        self.world_data[key] = value
        self.logger.info(f"更新世界设定: {key} {old} -> {value}")
        return {"updated": key}

    def _expand_world(self, params: dict) -> dict:
        """占位：未来接入AI模型扩展世界观"""
        prompt = params.get("prompt", "")
        self.logger.info(f"扩展世界观请求: {prompt}")
        # 模拟返回
        return {"new_content": "【占位】世界观扩展结果"}

    # -------- 数据管理 --------
    def _load_world_data(self):
        path = self.config["world_data_path"]
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.world_data = json.load(f)
            self.logger.info(f"已加载世界数据: {path}")
        except FileNotFoundError:
            self.world_data = {}
            self.logger.warning("世界数据文件未找到，使用空设定。")

    def _save_world_data(self):
        path = self.config["world_data_path"]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.world_data, f, ensure_ascii=False, indent=2)
        self.logger.debug("世界数据已自动保存。")

    # -------- 热插拔与信号 --------
    def _register_hot_reload(self):
        """注册热更新信号（Unix环境）"""
        if sys.platform != "win32":
            signal.signal(signal.SIGUSR1, self._handle_hot_reload)

    def _handle_hot_reload(self, signum, frame):
        """收到热更新信号：重新加载配置和数据，但保持运行"""
        self.logger.info("收到热更新信号，尝试热加载...")
        try:
            self._load_world_data()
            self.logger.info("热加载完成。")
        except Exception as e:
            self.logger.error(f"热加载失败: {e}")

    def register_callback(self, event: str, func: Callable):
        """动态注册回调，实现可插拔联动"""
        self.callbacks[event] = func
        self.logger.debug(f"已注册回调: {event} -> {func.__name__}")

    def unregister_callback(self, event: str):
        self.callbacks.pop(event, None)

    def _notify_callbacks(self, event: str, *args, **kwargs):
        """通知所有关注该事件的回调"""
        for ev, func in self.callbacks.items():
            if ev == event or ev == "*":
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    self.logger.error(f"回调 {func.__name__} 执行异常: {e}")


# -------- 自测与演示 --------
if __name__ == "__main__":
    # 快速自测，不依赖外部文件
    test_config = {
        "log_level": logging.DEBUG,
        "log_file": None,  # 只输出到终端
        "world_data_path": "tests/test_world.json",
        "max_retries": 2
    }
    agent = WorldAgent()
    # 覆盖配置
    agent.config.update(test_config)
    # 重新初始化日志（同步配置）
    agent.logger.handlers.clear()
    agent._init_logger()

    print("--- 自测开始 ---")
    agent.start()

    # 测试更新与查询
    res = agent.process({"action": "update", "params": {"key": "时代", "value": "赛博唐朝"}})
    print("更新结果:", res)
    res = agent.process({"action": "query", "params": {"key": "时代"}})
    print("查询结果:", res)

    # 测试扩展
    res = agent.process({"action": "expand", "params": {"prompt": "增加一种新能源"}})
    print("扩展结果:", res)

    # 异常恢复测试：非法动作
    res = agent.process({"action": "invalid"})
    print("异常处理结果:", res)

    agent.stop()
    print("--- 自测结束 ---")