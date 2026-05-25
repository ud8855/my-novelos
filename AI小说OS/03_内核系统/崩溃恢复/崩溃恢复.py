from __future__ import annotations
import json
import logging
import os
import signal
import sys
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type, Union


# ---------- 默认配置 ----------
DEFAULT_CONFIG = {
    "checkpoint_dir": "./checkpoints",
    "max_checkpoints": 5,
    "auto_recovery": True,
    "watchdog_interval": 10,  # 秒
    "strategy": "simple"      # simple, incremental, differential
}


# ---------- 崩溃恢复异常 ----------
class CrashRecoveryError(Exception):
    """崩溃恢复模块基础异常"""
    pass

class CheckpointSaveError(CrashRecoveryError):
    """检查点保存失败"""
    pass

class CheckpointLoadError(CrashRecoveryError):
    """检查点加载失败"""
    pass

class RecoveryFailedError(CrashRecoveryError):
    """恢复流程失败"""
    pass


# ---------- 检查点数据容器 ----------
@dataclass
class Checkpoint:
    """检查点数据容器"""
    id: str
    timestamp: float
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------- 检查点存储策略基类 ----------
class CheckpointStorage(ABC):
    """检查点存储策略抽象基类，实现可插拔的存储后端"""

    @abstractmethod
    def save(self, checkpoint: Checkpoint) -> None:
        """保存检查点"""
        ...

    @abstractmethod
    def load(self, checkpoint_id: str) -> Checkpoint:
        """加载指定检查点"""
        ...

    @abstractmethod
    def list_checkpoints(self) -> List[str]:
        """列出所有可用的检查点ID"""
        ...

    @abstractmethod
    def delete(self, checkpoint_id: str) -> None:
        """删除指定检查点"""
        ...


class FileSystemCheckpointStorage(CheckpointStorage):
    """基于文件系统的检查点存储实现"""

    def __init__(self, base_dir: str, logger: Optional[logging.Logger] = None):
        self.base_dir = base_dir
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        os.makedirs(self.base_dir, exist_ok=True)

    def _get_path(self, checkpoint_id: str) -> str:
        return os.path.join(self.base_dir, f"{checkpoint_id}.json")

    def save(self, checkpoint: Checkpoint) -> None:
        path = self._get_path(checkpoint.id)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({
                    "id": checkpoint.id,
                    "timestamp": checkpoint.timestamp,
                    "data": checkpoint.data,
                    "metadata": checkpoint.metadata
                }, f, ensure_ascii=False, indent=2)
            self.logger.info(f"检查点已保存: {checkpoint.id} -> {path}")
        except Exception as e:
            self.logger.error(f"检查点保存失败: {checkpoint.id}")
            raise CheckpointSaveError(f"检查点保存失败: {e}") from e

    def load(self, checkpoint_id: str) -> Checkpoint:
        path = self._get_path(checkpoint_id)
        if not os.path.exists(path):
            raise CheckpointLoadError(f"检查点不存在: {checkpoint_id}")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                obj = json.load(f)
            return Checkpoint(
                id=obj["id"],
                timestamp=obj["timestamp"],
                data=obj["data"],
                metadata=obj.get("metadata", {})
            )
        except Exception as e:
            self.logger.error(f"检查点加载失败: {checkpoint_id}")
            raise CheckpointLoadError(f"检查点加载失败: {e}") from e

    def list_checkpoints(self) -> List[str]:
        files = [f for f in os.listdir(self.base_dir) if f.endswith(".json")]
        # 返回不带扩展名的ID
        return [os.path.splitext(f)[0] for f in files]

    def delete(self, checkpoint_id: str) -> None:
        path = self._get_path(checkpoint_id)
        if os.path.exists(path):
            os.remove(path)
            self.logger.info(f"检查点已删除: {checkpoint_id}")
        else:
            self.logger.warning(f"尝试删除不存在的检查点: {checkpoint_id}")


# ---------- 核心崩溃恢复管理器 ----------
class CrashRecovery:
    """
    崩溃恢复管理器
    负责检查点保存、加载、自动恢复、看门狗监控
    遵循单一职责：只处理崩溃恢复逻辑，不涉及业务状态
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        logger: Optional[logging.Logger] = None,
        storage: Optional[CheckpointStorage] = None
    ):
        """
        :param config: 配置字典，默认使用DEFAULT_CONFIG
        :param logger: 可注入的日志器，若不提供则使用默认
        :param storage: 可注入的存储后端，若不提供则基于配置创建文件存储
        """
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.logger = logger or logging.getLogger("CrashRecovery")
        self.logger.info("崩溃恢复模块初始化开始")

        # 初始化存储后端
        if storage is not None:
            self.storage = storage
        else:
            checkpoint_dir = self.config.get("checkpoint_dir", "./checkpoints")
            self.storage = FileSystemCheckpointStorage(checkpoint_dir, self.logger)
        self.logger.info(f"使用存储后端: {type(self.storage).__name__}")

        # 内部状态
        self._lock = threading.RLock()
        self._running = False
        self._last_checkpoint_id: Optional[str] = None
        self._watchdog_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # 看门狗回调
        self._on_health_check: Optional[Callable[[], bool]] = None
        self._on_recovery: Optional[Callable[[], Any]] = None

        # 注册信号处理（仅主线程）
        if threading.current_thread() is threading.main_thread():
            try:
                signal.signal(signal.SIGTERM, self._signal_handler)
                signal.signal(signal.SIGINT, self._signal_handler)
            except ValueError:
                # 非主线程无法设置信号，忽略
                pass

        self.logger.info("崩溃恢复模块初始化完成")

    # ---------- 公共接口 ----------
    def set_health_check_handler(self, handler: Callable[[], bool]) -> None:
        """设置健康检查回调函数，返回True表示健康，False表示异常"""
        with self._lock:
            self._on_health_check = handler
        self.logger.debug("健康检查回调已注册")

    def set_recovery_handler(self, handler: Callable[[], Any]) -> None:
        """
        设置恢复回调函数，当检测到崩溃自动恢复时调用。
        该回调应执行状态恢复，例如重新加载上下文。
        """
        with self._lock:
            self._on_recovery = handler
        self.logger.debug("恢复回调已注册")

    def start(self) -> None:
        """启动崩溃恢复服务，包括看门狗监控（如果启用）"""
        with self._lock:
            if self._running:
                self.logger.warning("崩溃恢复服务已在运行")
                return
            self._running = True
            if self.config.get("auto_recovery", True):
                self._stop_event.clear()
                self._watchdog_thread = threading.Thread(
                    target=self._watchdog_loop,
                    name="CrashRecoveryWatchdog",
                    daemon=True
                )
                self._watchdog_thread.start()
                self.logger.info("看门狗线程已启动")
            self.logger.info("崩溃恢复服务已启动")

    def stop(self) -> None:
        """停止崩溃恢复服务"""
        with self._lock:
            if not self._running:
                return
            self._running = False
            if self._watchdog_thread and self._watchdog_thread.is_alive():
                self._stop_event.set()
                self._watchdog_thread.join(timeout=2.0)
                self.logger.info("看门狗线程已停止")
            self.logger.info("崩溃恢复服务已停止")

    def save_checkpoint(self, data: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        手动保存一个检查点
        :param data: 需要持久化的状态数据
        :param metadata: 附加元数据
        :return: 生成的检查点ID
        """
        with self._lock:
            checkpoint_id = self._generate_checkpoint_id()
            checkpoint = Checkpoint(
                id=checkpoint_id,
                timestamp=time.time(),
                data=data,
                metadata=metadata or {}
            )
            self.storage.save(checkpoint)
            self._last_checkpoint_id = checkpoint_id
            self._rotate_checkpoints()
            self.logger.info(f"手动保存检查点: {checkpoint_id}")
            return checkpoint_id

    def load_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        加载最新的检查点数据
        :return: 检查点的data字段，如果没有检查点则返回None
        """
        with self._lock:
            checkpoints = self.storage.list_checkpoints()
            if not checkpoints:
                self.logger.warning("没有可用的检查点")
                return None
            # 按时间戳排序（文件名包含时间信息，但这里简单取最后创建）
            # 更健壮的方式是从元数据获取，但为了骨架简单使用文件名排序
            latest_id = sorted(checkpoints)[-1]
            checkpoint = self.storage.load(latest_id)
            self._last_checkpoint_id = latest_id
            self.logger.info(f"已加载最新检查点: {latest_id}")
            return checkpoint.data

    def recover(self, checkpoint_id: Optional[str] = None) -> bool:
        """
        触发恢复流程（手动调用）
        :param checkpoint_id: 指定检查点ID，若不指定则使用最新
        :return: 是否恢复成功
        """
        with self._lock:
            if checkpoint_id is None:
                checkpoints = self.storage.list_checkpoints()
                if not checkpoints:
                    self.logger.error("恢复失败：没有可用的检查点")
                    raise RecoveryFailedError("没有可用的检查点")
                checkpoint_id = sorted(checkpoints)[-1]
            try:
                checkpoint = self.storage.load(checkpoint_id)
                self.logger.info(f"正在从检查点 {checkpoint_id} 恢复...")
                # 调用外部恢复回调
                if self._on_recovery:
                    # 注意：回调可能依赖外部状态，这里简单传递data，或由回调自行读取
                    # 为保持通用性，可将checkpoint.data传入
                    self._on_recovery()
                else:
                    self.logger.warning("未注册恢复回调，只能恢复检查点数据，但未应用")
                self._last_checkpoint_id = checkpoint_id
                self.logger.info("恢复流程完成")
                return True
            except Exception as e:
                self.logger.error(f"恢复失败: {e}")
                raise RecoveryFailedError(f"恢复失败: {e}") from e

    # ---------- 内部方法 ----------
    def _generate_checkpoint_id(self) -> str:
        """生成唯一的检查点ID"""
        return f"ckpt_{int(time.time() * 1000)}_{os.getpid()}"

    def _rotate_checkpoints(self) -> None:
        """按照配置保留最大检查点数量，删除旧的"""
        max_checkpoints = self.config.get