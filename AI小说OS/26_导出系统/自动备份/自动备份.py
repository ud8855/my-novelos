# -*- coding: utf-8 -*-
"""
自动备份模块 - AutoBackup
所属层：26_导出系统
职责：根据配置定期或事件触发，自动备份 NovelOS 项目数据。
特性：可插拔、配置化、日志记录、支持多存储后端。
依赖：需实现具体存储适配器（本地文件、云存储等），本模块仅定义接口和调度。
被调用者：导出系统调度器、系统守护进程或定时任务。
"""

import os
import sys
import json
import logging
import shutil
import datetime
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

# ---------- 默认配置 ----------
DEFAULT_CONFIG = {
    "enabled": True,
    "backup_interval_minutes": 60,
    "max_backups": 5,
    "sources": [
        {"path": "./projects", "description": "小说工程文件夹"}
    ],
    "storage": {
        "type": "local",
        "local_path": "./backups"
    },
    "compression": "zip",
    "retention_policy": "by_count",
    "logging": {
        "level": "INFO",
        "file": "logs/auto_backup.log"
    }
}

class StorageBackend(ABC):
    """存储后端抽象基类，实现具体存储逻辑"""
    @abstractmethod
    def save(self, source_path: str, destination: str, metadata: Dict[str, Any]) -> bool:
        """保存备份数据到目标存储"""
        pass

    @abstractmethod
    def list_backups(self) -> List[Dict[str, Any]]:
        """列出当前存储中的所有备份"""
        pass

    @abstractmethod
    def delete(self, backup_id: str) -> bool:
        """删除指定备份"""
        pass

class LocalStorageBackend(StorageBackend):
    """本地文件系统存储后端"""
    def __init__(self, base_path: str, logger: logging.Logger):
        self.base_path = base_path
        self.logger = logger
        os.makedirs(base_path, exist_ok=True)

    def save(self, source_path: str, destination: str, metadata: Dict[str, Any]) -> bool:
        try:
            dest_path = os.path.join(self.base_path, destination)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            # 简单拷贝，实际可扩展为压缩、差异备份等
            if os.path.isdir(source_path):
                shutil.copytree(source_path, dest_path)
            elif os.path.isfile(source_path):
                shutil.copy2(source_path, dest_path)
            else:
                self.logger.error(f"无法备份：源路径无效 {source_path}")
                return False
            self.logger.info(f"备份成功：{source_path} -> {dest_path}")
            return True
        except Exception as e:
            self.logger.exception(f"备份失败: {e}")
            return False

    def list_backups(self) -> List[Dict[str, Any]]:
        backups = []
        for f in os.listdir(self.base_path):
            backups.append({"id": f, "path": os.path.join(self.base_path, f)})
        return backups

    def delete(self, backup_id: str) -> bool:
        path = os.path.join(self.base_path, backup_id)
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            elif os.path.isfile(path):
                os.remove(path)
            else:
                self.logger.warning(f"要删除的备份不存在: {backup_id}")
                return False
            self.logger.info(f"已删除备份: {backup_id}")
            return True
        except Exception as e:
            self.logger.exception(f"删除备份失败: {e}")
            return False

class AutoBackup:
    """
    自动备份核心类
    职责：加载配置、初始化存储后端、执行备份、应用保留策略。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化自动备份模块
        :param config: 配置字典，若为None则加载默认配置
        """
        self.config = config or DEFAULT_CONFIG
        self.logger = self._setup_logging()
        self.storage = None
        if self.config["enabled"]:
            self.storage = self._init_storage()

    def _setup_logging(self) -> logging.Logger:
        """根据配置初始化日志"""
        log_cfg = self.config.get("logging", {})
        logger = logging.getLogger("AutoBackup")
        logger.setLevel(getattr(logging, log_cfg.get("level", "INFO"), logging.INFO))
        # 避免重复添加handler
        if not logger.handlers:
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            # 文件handler
            log_file = log_cfg.get("file")
            if log_file:
                os.makedirs(os.path.dirname(log_file), exist_ok=True)
                fh = logging.FileHandler(log_file, encoding='utf-8')
                fh.setFormatter(formatter)
                logger.addHandler(fh)
            # 控制台handler
            ch = logging.StreamHandler(sys.stdout)
            ch.setFormatter(formatter)
            logger.addHandler(ch)
        return logger

    def _init_storage(self) -> Optional[StorageBackend]:
        """根据配置初始化存储后端"""
        storage_cfg = self.config.get("storage", {})
        stype = storage_cfg.get("type", "local")
        if stype == "local":
            path = storage_cfg.get("local_path", "./backups")
            return LocalStorageBackend(base_path=path, logger=self.logger)
        else:
            self.logger.error(f"不支持的存储类型: {stype}")
            return None

    def is_enabled(self) -> bool:
        """检查模块是否启用"""
        return self.config.get("enabled", False)

    def run_backup(self) -> bool:
        """
        执行一次备份操作
        :return: 成功返回True，否则False
        """
        if not self.is_enabled() or not self.storage:
            self.logger.warning("自动备份未启用或存储后端未初始化")
            return False
        sources = self.config.get("sources", [])
        if not sources:
            self.logger.warning("未定义备份源")
            return False
        success = True
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        for src in sources:
            src_path = src.get("path")
            if not src_path or not os.path.exists(src_path):
                self.logger.error(f"备份源不存在: {src_path}")
                success = False
                continue
            dest_name = f"{os.path.basename(src_path)}_{timestamp}"
            metadata = {
                "source": src_path,
                "timestamp": timestamp,
                "description": src.get("description", "")
            }
            if not self.storage.save(src_path, dest_name, metadata):
                success = False

        # 应用保留策略
        self._apply_retention()
        return success

    def _apply_retention(self):
        """根据配置清理过期备份"""
        if not self.storage:
            return
        policy = self.config.get("retention_policy", "by_count")
        max_backups = self.config.get("max_backups", 5)
        if policy == "by_count":
            backups = self.storage.list_backups()
            # 按名称排序（假设时间戳在名称中），删除超出数量的旧备份
            if len(backups) > max_backups:
                backups.sort(key=lambda x: x["id"])  # 简易排序
                to_delete = backups[:-max_backups]
                for b in to_delete:
                    self.storage.delete(b["id"])
        # 可扩展其他策略

    def reload_config(self, new_config: Dict[str, Any]):
        """热更新配置，重新初始化存储和日志"""
        self.config = new_config
        # 重置日志
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            handler.close()
        self.logger = self._setup_logging()
        self.storage = self._init_storage()
        self.logger.info("配置已重载")

    def shutdown(self):
        """安全关闭模块，清理资源（如关闭文件句柄）"""
        for handler in self.logger.handlers:
            handler.close()
            self.logger.removeHandler(handler)

# ---------- 自测单元 ----------
if __name__ == "__main__":
    print("=== 自动备份模块自测 ===")
    # 创建临时测试目录和文件
    test_source = "./test_source"
    os.makedirs(test_source, exist_ok=True)
    with open(os.path.join(test_source, "test.txt"), "w") as f:
        f.write("Hello NovelOS")

    # 构建测试配置
    test_config = {
        "enabled": True,
        "backup_interval_minutes": 1,
        "max_backups": 2,
        "sources": [
            {"path": test_source, "description": "测试源"}
        ],
        "storage": {
            "type": "local",
            "local_path": "./test_backups"
        },
        "compression": "none",
        "retention_policy": "by_count",
        "logging": {
            "level": "DEBUG",
            "file": None  # 仅控制台输出
        }
    }

    # 初始化并运行
    backup = AutoBackup(config=test_config)
    if backup.is_enabled():
        result = backup.run_backup()
        print(f"备份执行结果: {result}")
        # 再次运行以测试保留策略
        backup.run_backup()
        backup.run_backup()
        backup.run_backup()
        # 列出剩余备份
        if backup.storage:
            for b in backup.storage.list_backups():
                print(f"备份存在: {b['id']}")
    else:
        print("备份未启用")

    # 清理测试文件
    backup.shutdown()
    import shutil as _shutil
    _shutil.rmtree(test_source, ignore_errors=True)
    _shutil.rmtree("./test_backups", ignore_errors=True)
    print("自测完成")