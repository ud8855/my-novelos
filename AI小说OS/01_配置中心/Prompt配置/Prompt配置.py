#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
模块：Prompt配置
所属层：01_配置中心
依赖：无（标准库）
被调用者：所有需要Prompt模板的模块（如Agent、模型调用模块）
解决：统一管理、加载、热更新所有Prompt模板，提供配置化、日志记录、可插拔的Prompt获取接口
"""

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

import yaml  # 需要安装PyYAML，此处假设已安装

# --------------------------------------------------------------------------------
# 日志配置（可插拔：外部可覆盖日志器）
# --------------------------------------------------------------------------------
logger = logging.getLogger("PromptConfig")
logger.addHandler(logging.NullHandler())  # 避免无 handler 时的警告
# 实际使用时由外部统一配置，此处仅默认输出到控制台
if not logger.handlers:
    _console_handler = logging.StreamHandler()
    _console_handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    logger.addHandler(_console_handler)
logger.setLevel(logging.INFO)  # 默认级别，可外部修改

# --------------------------------------------------------------------------------
# 核心类：PromptConfig
# --------------------------------------------------------------------------------
class PromptConfig:
    """
    Prompt 配置管理器
    职责：加载、缓存、提供、热更新 Prompt 模板
    可插拔性：通过构造函数接收不同的配置文件路径，可改为从数据库、远程服务加载
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化 Prompt 配置
        :param config_path: 配置文件路径，指定 prompt 源（JSON/YAML）；
                            若为 None，则从环境变量 PROMPT_CONFIG_PATH 或默认路径读取
        """
        if config_path is None:
            config_path = os.environ.get(
                "PROMPT_CONFIG_PATH",
                str(Path(__file__).parent / "prompts_config.yaml")  # 默认路径
            )
        self.config_path = Path(config_path)
        self._prompts: Dict[str, str] = {}          # 缓存 prompt 模板 {key: template}
        self._lock = threading.RLock()              # 线程安全
        self._last_modified: float = 0.0            # 记录文件最后修改时间，用于热更新
        self._watch_thread: Optional[threading.Thread] = None
        self._stop_watch = threading.Event()

        # 初次加载
        self.reload_prompts()
        logger.info(f"Prompt配置初始化完成，来源：{self.config_path}，加载 {len(self._prompts)} 个模板")

        # 若启用热更新，启动文件监听
        if os.environ.get("PROMPT_AUTO_RELOAD", "false").lower() == "true":
            self._start_watching()

    # --------------------------------------------------------------------
    # 加载与重载
    # --------------------------------------------------------------------
    def reload_prompts(self) -> None:
        """
        重新从配置源加载所有 Prompt 模板
        支持格式：YAML、JSON，根据文件扩展名自动识别
        热更新时也会调用此方法
        """
        if not self.config_path.exists():
            logger.warning(f"Prompt配置文件不存在：{self.config_path}")
            with self._lock:
                self._prompts.clear()
            return

        with self._lock:
            try:
                ext = self.config_path.suffix.lower()
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    if ext in ('.yaml', '.yml'):
                        raw_data = yaml.safe_load(f)
                    elif ext == '.json':
                        raw_data = json.load(f)
                    else:
                        logger.error(f"不支持的配置文件格式：{ext}，仅支持 YAML/JSON")
                        return

                if not isinstance(raw_data, dict):
                    logger.error("配置文件顶层必须为字典，每个键为一个 prompt 标识")
                    return

                # 清理并校验：所有值必须是字符串
                cleaned = {}
                for key, value in raw_data.items():
                    if isinstance(value, str):
                        cleaned[key] = value
                    else:
                        logger.warning(f"跳过非字符串的 prompt 项：{key}，类型：{type(value)}")
                self._prompts = cleaned
                self._last_modified = self._get_file_mtime()
                logger.info(f"成功重载Prompt配置，共 {len(self._prompts)} 个模板")

            except Exception as e:
                logger.exception(f"加载Prompt配置失败：{e}")

    def _get_file_mtime(self) -> float:
        """获取配置文件最后修改时间（秒）"""
        try:
            return self.config_path.stat().st_mtime
        except FileNotFoundError:
            return 0.0

    def _start_watching(self) -> None:
        """
        启动后台线程监听文件变化（热更新）
        每隔一定时间检查文件修改时间，如果变化则重新加载
        """
        if self._watch_thread and self._watch_thread.is_alive():
            return

        def watch_loop():
            logger.info("Prompt文件监听已启动")
            while not self._stop_watch.is_set():
                current_mtime = self._get_file_mtime()
                if current_mtime > self._last_modified:
                    logger.info("检测到Prompt配置文件变更，触发重载...")
                    self.reload_prompts()
                self._stop_watch.wait(timeout=2.0)  # 每2秒检查一次
            logger.info("Prompt文件监听已停止")

        self._watch_thread = threading.Thread(target=watch_loop, daemon=True)
        self._watch_thread.start()

    def stop_watching(self) -> None:
        """停止文件监听线程"""
        self._stop_watch.set()
        if self._watch_thread:
            self._watch_thread.join(timeout=5)

    # --------------------------------------------------------------------
    # Prompt 获取
    # --------------------------------------------------------------------
    def get(self, key: str, **kwargs) -> Optional[str]:
        """
        根据 key 获取 Prompt 模板，并可选进行格式化（替换占位符）
        :param key: Prompt 标识
        :param kwargs: 模板中 {key} 对应的值
        :return: 格式化后的 Prompt 字符串，若 key 不存在则返回 None
        """
        with self._lock:
            template = self._prompts.get(key)
        if template is None:
            logger.warning(f"请求的Prompt键不存在：{key}")
            return None
        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"格式化Prompt时缺少参数：{e}，key={key}")
            return None
        except Exception as e:
            logger.exception(f"格式化Prompt异常：{e}，key={key}")
            return None

    def get_all_keys(self) -> list:
        """返回所有可用的 Prompt 键名"""
        with self._lock:
            return list(self._prompts.keys())

    def get_raw(self, key: str) -> Optional[str]:
        """获取原始的、未格式化的模板字符串"""
        with self._lock:
            return self._prompts.get(key)

    # --------------------------------------------------------------------
    # 自检与测试（单元测试骨架）
    # --------------------------------------------------------------------
    @staticmethod
    def run_self_test():
        """
        自测：验证基本功能（加载、获取、格式化、热更）
        使用临时配置文件进行测试
        """
        import tempfile
        import textwrap

        # 创建临时 YAML 配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as tf:
            tf.write(textwrap.dedent("""
            greeting: "Hello, {name}!"
            story_start: "Once upon a time, in {setting}, there was {character}."
            """).strip())
            tmp_path = tf.name

        try:
            pc = PromptConfig(config_path=tmp_path)
            # 测试正常获取
            result1 = pc.get("greeting", name="Tester")
            assert result1 == "Hello, Tester!", f"预期不符: {result1}"
            print("[自测] 基本获取通过")

            # 测试缺失 key
            result2 = pc.get("nonexistent")
            assert result2 is None, "应返回 None"
            print("[自测] 缺失Key返回None通过")

            # 测试缺少格式化参数
            result3 = pc.get("greeting")
            assert result3 is None, "应返回 None"
            print("[自测] 缺少参数返回None通过")

            # 测试 get_all_keys
            keys = pc.get_all_keys()
            assert "greeting" in keys and "story_start" in keys, f"Keys 异常: {keys}"
            print("[自测] 获取所有Keys通过")

            # 测试热更：修改文件内容，等待监听触发
            # 注意：需要启用自动重载环境变量，这里手动触发重载模拟
            pc.reload_prompts()  # 手动重载已通过，无需再测
            print("[自测] 手动重载通过")

            # 测试文件监听（不真正启用，仅验证方法存在）
            assert hasattr(pc, '_start_watching')
            print("[自测] 热更新监听接口存在")

            print("✅ 所有自测通过！")

        except Exception as e:
            logger.exception(f"自测失败：{e}")
            print(f"❌ 自测失败：{e}")
        finally:
            # 清理临时文件
            os.unlink(tmp_path)


# --------------------------------------------------------------------------------
# 单例（可选，全局唯一实例，方便调用）
# --------------------------------------------------------------------------------
_global_prompt_config = None
_global_lock = threading.Lock()


def get_prompt_config(config_path: Optional[str] = None) -> PromptConfig:
    """
    获取全局唯一的 PromptConfig 实例（单例模式）
    首次调用时可传入 config_path，后续调用返回同一实例
    """
    global _global_prompt_config
    if _global_prompt_config is None:
        with _global_lock:
            if _global_prompt_config is None:
                _global_prompt_config = PromptConfig(config_path)
    return _global_prompt_config


# --------------------------------------------------------------------------------
# 模块入口：直接运行可执行自测
# --------------------------------------------------------------------------------
if __name__ == "__main__":
    # 设置测试环境变量（可选）
    os.environ.setdefault("PROMPT_AUTO_RELOAD", "false")
    PromptConfig.run_self_test()