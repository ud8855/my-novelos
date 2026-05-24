"""
Module: API日志
Path: 27_日志监控/API日志/API日志.py
Layer: 日志监控层 (Layer 27)
Dependency: 标准库 logging, 配置管理模块 (例如 08_用户配置/配置中心.py, 但此处通过依赖注入避免硬依赖)
Called by: 21_API模型/API调用器.py (任何需要记录API交互的模块)
Solution: 提供统一、可插拔、配置化的 API 调用日志记录器，支持热插拔处理器和过滤器，隔离日志实现细节。
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional, Union

# 默认配置，可由外部配置覆盖
DEFAULT_CONFIG = {
    'logger_name': 'NovelOS_API',
    'level': logging.INFO,
    'format_str': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'handlers': [
        {
            'type': 'console',  # console, file, rotating_file
            'level': logging.DEBUG,
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            # 如果是 file 或 rotating_file 则需额外参数
        }
    ],
    'propagate': False,
}


class APILogger:
    """
    API日志记录器
    负责记录所有API请求、响应、错误、延迟等信息。
    支持插拔处理器和过滤器，通过配置初始化，保持高度可扩展。
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化日志记录器。
        :param config: 配置字典，可选。若不提供则使用 DEFAULT_CONFIG。
        """
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.logger = logging.getLogger(self.config['logger_name'])
        self.logger.setLevel(self.config.get('level', logging.INFO))
        self.logger.propagate = self.config.get('propagate', False)

        # 清除已有处理器，避免重复（支持热更新）
        if self.logger.hasHandlers():
            self.logger.handlers.clear()

        # 根据配置添加处理器
        for handler_conf in self.config.get('handlers', []):
            handler = self._build_handler(handler_conf)
            if handler:
                self.logger.addHandler(handler)

        # 钩子列表：用于可插拔的额外处理[回调函数]
        self.request_hooks: List[Callable] = []
        self.response_hooks: List[Callable] = []
        self.error_hooks: List[Callable] = []

    def _build_handler(self, handler_conf: Dict) -> Optional[logging.Handler]:
        """
        根据配置构建日志处理器（Handler）。
        :param handler_conf: 处理器配置
        :return: Handler实例
        """
        h_type = handler_conf.get('type', 'console')
        level = handler_conf.get('level', logging.DEBUG)
        fmt = handler_conf.get('format', self.config.get('format_str'))

        formatter = logging.Formatter(fmt)

        if h_type == 'console':
            handler = logging.StreamHandler()
        elif h_type == 'file':
            filename = handler_conf.get('filename', 'api.log')
            handler = logging.FileHandler(filename, encoding='utf-8')
        elif h_type == 'rotating_file':
            from logging.handlers import RotatingFileHandler
            filename = handler_conf.get('filename', 'api.log')
            max_bytes = handler_conf.get('max_bytes', 10 * 1024 * 1024)
            backup_count = handler_conf.get('backup_count', 5)
            handler = RotatingFileHandler(filename, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')
        else:
            return None

        handler.setLevel(level)
        handler.setFormatter(formatter)
        return handler

    def add_handler(self, handler: logging.Handler):
        """
        热插拔：动态添加一个日志处理器。
        :param handler: Handler对象
        """
        self.logger.addHandler(handler)

    def remove_handler(self, handler: logging.Handler):
        """
        移除指定处理器。
        """
        self.logger.removeHandler(handler)

    def add_filter(self, log_filter: logging.Filter):
        """
        添加过滤器。
        """
        self.logger.addFilter(log_filter)

    def register_request_hook(self, hook: Callable[[Dict], None]):
        """注册请求钩子（可插拔处理请求日志）"""
        self.request_hooks.append(hook)

    def register_response_hook(self, hook: Callable[[Dict], None]):
        """注册响应钩子"""
        self.response_hooks.append(hook)

    def register_error_hook(self, hook: Callable[[Dict], None]):
        """注册错误钩子"""
        self.error_hooks.append(hook)

    def log_request(self, method: str, url: str, headers: Optional[Dict] = None,
                    body: Any = None, timestamp: Optional[float] = None, **extra):
        """
        记录API请求。
        :param method: HTTP方法
        :param url: 请求URL
        :param headers: 请求头
        :param body: 请求体
        :param timestamp: 请求时间戳，默认为当前时间
        :param extra: 额外自定义字段
        """
        req_info = {
            'type': 'request',
            'method': method,
            'url': url,
            'headers': headers,
            'body': body,
            'timestamp': timestamp or time.time(),
            **extra
        }
        msg = f"API Request: {method} {url} | Headers: {headers} | Body: {body}"
        self.logger.info(msg)
        # 执行所有请求钩子
        for hook in self.request_hooks:
            try:
                hook(req_info)
            except Exception as e:
                self.logger.error(f"Request hook error: {e}")

    def log_response(self, status_code: int, response_body: Any = None,
                     latency: Optional[float] = None, **extra):
        """
        记录API响应。
        :param status_code: HTTP状态码
        :param response_body: 响应体
        :param latency: 延迟时间(秒)
        """
        resp_info = {
            'type': 'response',
            'status_code': status_code,
            'response_body': response_body,
            'latency': latency,
            **extra
        }
        msg = f"API Response: Status {status_code} | Latency: {latency:.4f}s | Body: {response_body}"
        if status_code >= 400:
            self.logger.warning(msg)
        else:
            self.logger.info(msg)
        for hook in self.response_hooks:
            try:
                hook(resp_info)
            except Exception as e:
                self.logger.error(f"Response hook error: {e}")

    def log_error(self, error_message: str, exception: Optional[Exception] = None, **extra):
        """
        记录API调用过程中的错误。
        """
        err_info = {
            'type': 'error',
            'error_message': error_message,
            'exception': str(exception) if exception else None,
            **extra
        }
        self.logger.error(f"API Error: {error_message} | Exception: {exception}")
        for hook in self.error_hooks:
            try:
                hook(err_info)
            except Exception as e:
                self.logger.error(f"Error hook error: {e}")

    def set_level(self, level: Union[int, str]):
        """动态修改日志级别"""
        self.logger.setLevel(level)

    def shutdown(self):
        """安全关闭所有处理器"""
        logging.shutdown()


# ----- 自测部分 -----
if __name__ == '__main__':
    # 示例配置：只输出到控制台
    test_config = {
        'logger_name': 'Test_API_Logger',
        'level': logging.DEBUG,
        'handlers': [
            {'type': 'console', 'level': logging.DEBUG}
        ]
    }
    api_logger = APILogger(config=test_config)

    # 模拟记录请求
    api_logger.log_request(method='GET', url='https://api.example.com/v1/resource',
                           headers={'Authorization': 'Bearer token'}, body=None)

    # 模拟记录成功响应
    api_logger.log_response(status_code=200, response_body={'data': 'test'}, latency=0.1234)

    # 模拟记录错误响应
    api_logger.log_response(status_code=404, response_body={'error': 'not found'}, latency=0.05)

    # 模拟记录异常
    try:
        1 / 0
    except Exception as e:
        api_logger.log_error('Division by zero', e)

    # 测试插拔钩子
    def custom_request_hook(info):
        print(f"[CustomHook] Request logged with extra: {info.get('extra_field', 'none')}")

    api_logger.register_request_hook(custom_request_hook)
    api_logger.log_request('POST', 'https://api.example.com/v1/test', extra_field='my_extra')

    # 热插拔：添加文件处理器
    file_handler = logging.FileHandler('test_api.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    api_logger.add_handler(file_handler)
    api_logger.logger.info('Added file handler dynamically.')

    api_logger.shutdown()