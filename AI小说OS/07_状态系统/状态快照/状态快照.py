"""状态快照.py - NovelOS 状态快照模块
所属层级：07_状态系统
依赖模块：日志系统、配置系统
被调用者：状态管理器、回滚系统、调试工具
解决的问题：对系统运行状态进行快照保存与恢复，支持热插拔、版本管理和异常恢复
"""

import logging
import json
import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List

# 配置默认值（可被外部配置文件覆盖）
DEFAULT_SNAPSHOT_DIR = "snapshots"
DEFAULT_MAX_SNAPSHOTS = 50
DEFAULT_COMPRESS = False
DEFAULT_FORMAT = "json"

class SnapshotError(Exception):
    """快照操作异常类"""
    pass

class BaseSnapshot(ABC):
    """快照抽象基类，定义必须实现的接口，保证可插拔性"""
    
    def __init__(self, snapshot_id: str, metadata: Dict[str, Any] = None):
        self.snapshot_id = snapshot_id
        self.timestamp = time.time()
        self.metadata = metadata or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def save(self, state: Dict[str, Any]) -> None:
        """保存状态快照"""
        pass

    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """恢复状态快照"""
        pass

    @abstractmethod
    def delete(self) -> None:
        """删除快照"""
        pass

    def get_info(self) -> Dict[str, Any]:
        """获取快照基本信息"""
        return {
            "id": self.snapshot_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }

class FileSnapshot(BaseSnapshot):
    """基于文件的快照实现，默认使用JSON格式"""
    
    def __init__(self, snapshot_id: str, directory: str, metadata: Dict[str, Any] = None):
        super().__init__(snapshot_id, metadata)
        self.directory = directory
        self.filepath = os.path.join(directory, f"{snapshot_id}.json")
        os.makedirs(directory, exist_ok=True)
        self.logger.info(f"初始化文件快照: {snapshot_id} -> {self.filepath}")

    def save(self, state: Dict[str, Any]) -> None:
        """将状态序列化保存到文件"""
        try:
            data = {
                "snapshot_id": self.snapshot_id,
                "timestamp": self.timestamp,
                "metadata": self.metadata,
                "state": state
            }
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"快照已保存: {self.snapshot_id}")
        except Exception as e:
            self.logger.error(f"保存快照失败 {self.snapshot_id}: {e}")
            raise SnapshotError(f"保存快照失败: {e}")

    def load(self) -> Dict[str, Any]:
        """从文件加载快照数据"""
        if not os.path.exists(self.filepath):
            raise SnapshotError(f"快照文件不存在: {self.filepath}")
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.logger.info(f"快照已加载: {self.snapshot_id}")
            return data.get("state", {})
        except Exception as e:
            self.logger.error(f"加载快照失败 {self.snapshot_id}: {e}")
            raise SnapshotError(f"加载快照失败: {e}")

    def delete(self) -> None:
        """删除快照文件"""
        if os.path.exists(self.filepath):
            try:
                os.remove(self.filepath)
                self.logger.info(f"快照已删除: {self.snapshot_id}")
            except Exception as e:
                self.logger.error(f"删除快照失败 {self.snapshot_id}: {e}")
                raise SnapshotError(f"删除快照失败: {e}")
        else:
            self.logger.warning(f"尝试删除不存在的快照: {self.snapshot_id}")

class SnapshotManager:
    """快照管理器，负责创建、恢复、列表和维护快照（可配置化）"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.snapshot_dir = self.config.get("snapshot_dir", DEFAULT_SNAPSHOT_DIR)
        self.max_snapshots = self.config.get("max_snapshots", DEFAULT_MAX_SNAPSHOTS)
        self.compress = self.config.get("compress", DEFAULT_COMPRESS)
        self.format = self.config.get("format", DEFAULT_FORMAT)
        self.logger = logging.getLogger(f"{__name__}.SnapshotManager")
        self.logger.info(f"快照管理器初始化，目录: {self.snapshot_dir}, 最大数量: {self.max_snapshots}")
        os.makedirs(self.snapshot_dir, exist_ok=True)

    def create_snapshot(self, state: Dict[str, Any], metadata: Dict[str, Any] = None) -> FileSnapshot:
        """创建新快照"""
        snapshot_id = self._generate_id()
        snapshot = FileSnapshot(snapshot_id, self.snapshot_dir, metadata)
        snapshot.save(state)
        self._enforce_limit()
        return snapshot

    def load_snapshot(self, snapshot_id: str) -> Dict[str, Any]:
        """按ID加载快照"""
        snapshot = FileSnapshot(snapshot_id, self.snapshot_dir)
        return snapshot.load()

    def delete_snapshot(self, snapshot_id: str) -> None:
        """按ID删除快照"""
        snapshot = FileSnapshot(snapshot_id, self.snapshot_dir)
        snapshot.delete()

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """列出所有已保存的快照元信息"""
        snapshots = []
        if not os.path.exists(self.snapshot_dir):
            return snapshots
        for filename in os.listdir(self.snapshot_dir):
            if filename.endswith(f".{self.format}"):
                snapshot_id = filename[:-len(f".{self.format}")]
                filepath = os.path.join(self.snapshot_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    snap_info = {
                        "id": data.get("snapshot_id"),
                        "timestamp": data.get("timestamp"),
                        "metadata": data.get("metadata", {})
                    }
                    snapshots.append(snap_info)
                except Exception as e:
                    self.logger.warning(f"读取快照文件失败 {filename}: {e}")
        # 按时间戳降序排列（最新的在前）
        snapshots.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return snapshots

    def _generate_id(self) -> str:
        """生成唯一的快照ID"""
        return f"snap_{int(time.time() * 1000)}_{os.urandom(4).hex()}"

    def _enforce_limit(self) -> None:
        """执行快照数量限制，超出则删除最旧的快照"""
        snapshots = self.list_snapshots()
        if len(snapshots) > self.max_snapshots:
            # 保留最新的 max_snapshots 个，删除其余
            to_delete = snapshots[self.max_snapshots:]
            for snap in to_delete:
                self.delete_snapshot(snap["id"])
                self.logger.info(f"自动清理旧快照: {snap['id']}")

# 自测代码
if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    # 测试快照管理器
    config = {"snapshot_dir": "test_snapshots", "max_snapshots": 3}
    manager = SnapshotManager(config)

    # 创建测试状态
    state1 = {"chapter": 1, "draft": "这是一段小说内容。", "tokens": 100}
    state2 = {"chapter": 2, "draft": "第二章开始。", "tokens": 200}
    state3 = {"chapter": 3, "draft": "第三章推进。", "tokens": 300}

    # 保存多个快照
    snap1 = manager.create_snapshot(state1, {"author": "AI", "version": "1.0"})
    snap2 = manager.create_snapshot(state2, {"author": "AI", "version": "1.1"})
    snap3 = manager.create_snapshot(state3, {"author": "AI", "version": "1.2"})

    # 列出快照
    snapshots = manager.list_snapshots()
    logger.info(f"当前快照数量: {len(snapshots)}")
    for sn in snapshots:
        logger.info(f"  - {sn['id']}")

    # 加载最新快照
    if snapshots:
        new_state = manager.load_snapshot(snapshots[0]["id"])
        logger.info(f"恢复的状态: {new_state}")

    # 测试超出数量限制，应该自动删除最早的一个
    state4 = {"chapter": 4, "draft": "第四章。", "tokens": 400}
    manager.create_snapshot(state4, {"author": "AI", "version": "1.3"})
    logger.info(f"创建第四个快照后，现有快照数: {len(manager.list_snapshots())}")

    # 清理测试目录
    import shutil
    shutil.rmtree("test_snapshots", ignore_errors=True)
    logger.info("自测完成，测试目录已清理。")