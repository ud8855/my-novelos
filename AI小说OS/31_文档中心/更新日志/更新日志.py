"""31_文档中心/更新日志/更新日志.py

层级：文档中心层
职责：
    - 提供系统更新日志的记录、查询、导出功能。
    - 遵循可插拔：通过配置选择存储后端（JSON文件、数据库等）。
    - 所有操作记录日志，支持异常恢复。
    - 配置化：日志级别、存储路径等均可通过配置调整。
依赖：
    - 配置管理模块（通过注入）
    - 日志模块（通过注入）
被调用者：
    - 后端API（如 /api/changelog）
    - 命令行工具
    - 其他需要查询更新日志的模块

设计原则：单一职责、开闭原则、依赖倒置。
"""

import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

# 假设有一个基础配置和日志注入方式，这里用占位符表示实际项目中从框架获取
# 在实际系统中会通过依赖注入传递，这里为了自测简单实现


class ChangelogConfig:
    """更新日志配置（可插拔，默认使用JSON文件存储）"""
    DEFAULT_STORAGE_BACKEND = "json_file"
    DEFAULT_STORAGE_PATH = "data/changelog.json"
    DEFAULT_LOG_LEVEL = "INFO"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        cfg = config or {}
        self.storage_backend = cfg.get("storage_backend", self.DEFAULT_STORAGE_BACKEND)
        self.storage_path = cfg.get("storage_path", self.DEFAULT_STORAGE_PATH)
        self.log_level = cfg.get("log_level", self.DEFAULT_LOG_LEVEL)


class ChangelogStorageBackend(ABC):
    """存储后端抽象接口（可插拔）"""

    @abstractmethod
    def read_all(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def append(self, entry: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def clear(self) -> None:
        pass


class JsonFileStorage(ChangelogStorageBackend):
    """JSON文件存储后端实现"""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        # 确保目录存在
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.file_path.exists():
            self._write_json([])

    def _read_json(self) -> Any:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write_json(self, data: Any) -> None:
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def read_all(self) -> List[Dict[str, Any]]:
        return self._read_json()

    def append(self, entry: Dict[str, Any]) -> None:
        data = self._read_json()
        data.append(entry)
        self._write_json(data)

    def clear(self) -> None:
        self._write_json([])


class ChangelogManager:
    """
    更新日志管理器
    遵循依赖倒置：依赖存储后端接口，不依赖具体实现
    提供更新日志的CRUD及查询功能
    """

    def __init__(self, config: ChangelogConfig, storage: ChangelogStorageBackend, logger=None):
        self.config = config
        self.storage = storage
        self.logger = logger or self._default_logger()

    @staticmethod
    def _default_logger():
        import logging
        logger = logging.getLogger("Changelog")
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            ch = logging.StreamHandler()
            ch.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)
        return logger

    def _create_entry(self, version: str, description: str, author: str = "system", details: Optional[Dict] = None) -> Dict[str, Any]:
        """构造一条更新日志条目（内部格式）"""
        entry = {
            "version": version,
            "description": description,
            "author": author,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "details": details or {}
        }
        return entry

    def add_changelog(self, version: str, description: str, author: str = "system", details: Optional[Dict] = None) -> None:
        """添加一条更新日志"""
        try:
            entry = self._create_entry(version, description, author, details)
            self.storage.append(entry)
            self.logger.info(f"添加更新日志: {version} - {description[:50]}...")
        except Exception as e:
            self.logger.error(f"添加更新日志失败: {e}")
            raise

    def get_all_changelogs(self, reverse: bool = False) -> List[Dict[str, Any]]:
        """获取所有更新日志，可选择倒序"""
        try:
            logs = self.storage.read_all()
            if reverse:
                logs = list(reversed(logs))
            return logs
        except Exception as e:
            self.logger.error(f"获取更新日志失败: {e}")
            return []

    def get_latest_version(self) -> Optional[Dict[str, Any]]:
        """获取最新一条更新日志"""
        logs = self.get_all_changelogs(reverse=True)
        return logs[0] if logs else None

    def search_by_version(self, version: str) -> List[Dict[str, Any]]:
        """按版本号查询（简单字符串匹配）"""
        logs = self.storage.read_all()
        return [log for log in logs if version.lower() in log.get("version", "").lower()]

    def export_to_markdown(self, output_path: Optional[str] = None) -> str:
        """将更新日志导出为Markdown格式字符串，可选写入文件"""
        logs = self.get_all_changelogs(reverse=True)
        md_lines = ["# NovelOS 更新日志"]
        for log in logs:
            md_lines.append(f"## {log['version']} - {log['timestamp']}")
            md_lines.append(f"**作者**: {log['author']}")
            md_lines.append(f"\n{log['description']}\n")
            if log.get("details"):
                md_lines.append("### 详细变更")
                for key, value in log["details"].items():
                    md_lines.append(f"- **{key}**: {value}")
                md_lines.append("")
            md_lines.append("---")
        markdown_content = "\n".join(md_lines)
        if output_path:
            try:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(markdown_content)
                self.logger.info(f"更新日志已导出至: {output_path}")
            except Exception as e:
                self.logger.error(f"导出更新日志失败: {e}")
                raise
        return markdown_content

    def clear_logs(self) -> None:
        """清空所有日志（谨慎操作）"""
        try:
            self.storage.clear()
            self.logger.warning("所有更新日志已被清空")
        except Exception as e:
            self.logger.error(f"清空日志失败: {e}")
            raise


# 可选：工厂函数，便于组装
def create_changelog_manager_from_config(config: Optional[Dict] = None, logger=None) -> ChangelogManager:
    cfg = ChangelogConfig(config)
    if cfg.storage_backend == "json_file":
        storage = JsonFileStorage(cfg.storage_path)
    else:
        raise ValueError(f"不支持的存储后端: {cfg.storage_backend}")
    return ChangelogManager(cfg, storage, logger)


# ========== 自测部分（仅用于直接运行此文件时验证） ==========
if __name__ == "__main__":
    import tempfile

    # 使用临时文件进行测试
    with tempfile.TemporaryDirectory() as tmpdir:
        test_config = {
            "storage_backend": "json_file",
            "storage_path": os.path.join(tmpdir, "test_changelog.json")
        }
        manager = create_changelog_manager_from_config(test_config)

        # 添加日志
        manager.add_changelog("1.0.0", "初始版本发布", author="DevTeam", details={"新增": "核心功能"})
        manager.add_changelog("1.0.1", "修复若干bug", author="QA", details={"修复": "登录异常"})

        # 获取全部
        all_logs = manager.get_all_changelogs()
        assert len(all_logs) == 2
        print("所有日志:", all_logs)

        # 获取最新
        latest = manager.get_latest_version()
        print("最新:", latest)
        assert latest["version"] == "1.0.1"

        # 搜索
        found = manager.search_by_version("1.0.0")
        assert len(found) == 1

        # 导出markdown
        md = manager.export_to_markdown()
        print("Markdown导出:\n", md)

        # 清除
        manager.clear_logs()
        assert len(manager.get_all_changelogs()) == 0

        print("自测通过！")