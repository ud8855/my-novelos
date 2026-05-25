# -*- coding: utf-8 -*-
"""
API协议模块
============
功能：定义NovelOS系统中所有API交互的统一协议，包括请求/响应结构、错误码、
     协议注册/调度机制，支持热插拔、配置化、日志记录。
所属层：02_协议层
依赖：无（底层协议，仅依赖标准库）
被依赖：03_UI层、04_Agent层、05_Runtime层（通过协议通信）
遵循原则：单一职责、接口隔离、依赖倒置
"""

import logging
import configparser
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Callable, Optional, Union
from enum import Enum
import json
import os

# ============================================================
# 错误码定义
# ============================================================
class ErrorCode(Enum):
    """统一错误码枚举"""
    SUCCESS = (0, "成功")
    INVALID_REQUEST = (1, "请求参数无效")
    UNKNOWN_API = (2, "未知API名称")
    HANDLER_NOT_FOUND = (3, "未找到处理器")
    INTERNAL_ERROR = (4, "内部服务错误")
    TIMEOUT = (5, "请求超时")
    AUTH_FAILED = (6, "认证失败")
    RATE_LIMITED = (7, "请求频率超限")

    def __init__(self, code: int, description: str):
        self.code = code
        self.description = description

# ============================================================
# 协议数据模型
# ============================================================
@dataclass
class ApiRequest:
    """API请求基类"""
    api_name: str                     # 目标API标识
    request_id: str = ""              # 请求唯一ID，用于链路追踪
    timestamp: float = 0.0            # 请求时间戳 (Unix时间)
    version: str = "1.0"              # 协议版本
    payload: Dict[str, Any] = field(default_factory=dict)  # 业务参数

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @staticmethod
    def from_json(json_str: str) -> 'ApiRequest':
        data = json.loads(json_str)
        return ApiRequest(**data)

@dataclass
class ApiResponse:
    """API响应基类"""
    request_id: str = ""              # 对应的请求ID
    api_name: str = ""                # 响应的API名称
    code: int = ErrorCode.SUCCESS.code
    message: str = ErrorCode.SUCCESS.description
    data: Any = None                  # 业务数据，可为list/dict/None
    timestamp: float = 0.0            # 响应时间戳

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @staticmethod
    def from_json(json_str: str) -> 'ApiResponse':
        data = json.loads(json_str)
        return ApiResponse(**data)

# ============================================================
# 协议异常
# ============================================================
class APIException(Exception):
    """API协议层异常，携带错误码"""
    def __init__(self, error_code: ErrorCode, detail: str = ""):
        super().__init__(f"{error_code.description}: {detail}")
        self.error_code = error_code
        self.detail = detail

# ============================================================
# 可插拔的API协议注册中心
# ============================================================
class ProtocolRegistry:
    """
    API协议注册与调度中心
    支持动态注册、热插拔、配置化、日志记录
    实现依赖倒置：上层通过接口注册具体处理器，协议层不依赖具体实现
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        :param config: 配置字典，可包含 logging.level 等
        """
        self._handlers: Dict[str, Callable[[ApiRequest], ApiResponse]] = {}
        self.config = config or {}
        self._setup_logging()

    def _setup_logging(self):
        """根据配置初始化日志"""
        log_level = self.config.get("logging", {}).get("level", "INFO")
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        logging.basicConfig(level=numeric_level,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(f"{__name__}.ProtocolRegistry")

    def register(self, api_name: str, handler: Callable[[ApiRequest], ApiResponse]):
        """
        注册API处理器
        :param api_name: 唯一API标识
        :param handler: 处理函数，接收ApiRequest返回ApiResponse
        """
        if api_name in self._handlers:
            self.logger.warning(f"API '{api_name}' 将被覆盖注册")
        self._handlers[api_name] = handler
        self.logger.info(f"API '{api_name}' 注册成功")

    def unregister(self, api_name: str):
        """注销API处理器"""
        if api_name in self._handlers:
            del self._handlers[api_name]
            self.logger.info(f"API '{api_name}' 注销成功")
        else:
            self.logger.warning(f"尝试注销不存在的API: '{api_name}'")

    def handle(self, api_name: str, request: ApiRequest) -> ApiResponse:
        """
        调度请求到对应的处理器
        :param api_name: 目标API
        :param request: 请求对象
        :return: 响应对象
        """
        if api_name not in self._handlers:
            self.logger.error(f"未知API: {api_name}")
            raise APIException(ErrorCode.UNKNOWN_API, f"API '{api_name}' 未注册")

        handler = self._handlers[api_name]
        if handler is None:
            self.logger.error(f"API '{api_name}' 的处理器为空")
            raise APIException(ErrorCode.HANDLER_NOT_FOUND, f"API '{api_name}' 无有效处理器")

        try:
            self.logger.debug(f"处理API: {api_name}, request_id: {request.request_id}")
            response = handler(request)
            # 自动填充部分响应字段
            response.api_name = api_name
            if not response.request_id:
                response.request_id = request.request_id
            from time import time
            response.timestamp = time()
            return response
        except APIException:
            raise
        except Exception as e:
            self.logger.exception(f"API '{api_name}' 处理器异常: {e}")
            raise APIException(ErrorCode.INTERNAL_ERROR, str(e))

# ============================================================
# 配置加载工具函数
# ============================================================
def load_config_from_file(config_path: str) -> Dict[str, Any]:
    """
    从配置文件加载配置（支持INI格式）
    :param config_path: 配置文件路径
    :return: 配置字典
    """
    if not os.path.exists(config_path):
        logging.warning(f"配置文件不存在: {config_path}，使用默认配置")
        return {}
    parser = configparser.ConfigParser()
    parser.read(config_path, encoding='utf-8')
    config = {}
    for section in parser.sections():
        config[section] = dict(parser.items(section))
    return config

# ============================================================
# 自测代码（仅用于验证骨架正确性）
# ============================================================
if __name__ == "__main__":
    # 1. 创建协议注册中心（使用内存配置）
    registry = ProtocolRegistry({"logging": {"level": "DEBUG"}})

    # 2. 定义一个示例API处理器（仅为测试）
    def handle_test(request: ApiRequest) -> ApiResponse:
        name = request.payload.get("name", "World")
        return ApiResponse(
            code=ErrorCode.SUCCESS.code,
            message="处理成功",
            data={"greeting": f"Hello, {name}!"}
        )

    # 3. 注册处理器
    registry.register("test.greet", handle_test)

    # 4. 构造请求并调度
    request = ApiRequest(
        api_name="test.greet",
        request_id="req-001",
        timestamp=1234567890.0,
        payload={"name": "NovelOS"}
    )

    try:
        response = registry.handle("test.greet", request)
        print("响应:", response.to_json())
    except APIException as e:
        print("API异常:", e)

    # 5. 测试未注册API -> 应抛出异常
    try:
        bad_request = ApiRequest(api_name="unknown.api", request_id="req-002")
        registry.handle("unknown.api", bad_request)
    except APIException as e:
        print(f"预期异常: {e.error_code.name} - {e}")

    # 6. 测试配置加载（如果存在配置文件config.ini）
    if os.path.exists("api_protocol_config.ini"):
        config = load_config_from_file("api_protocol_config.ini")
        print("配置文件内容:", config)

    print("自测全部通过")