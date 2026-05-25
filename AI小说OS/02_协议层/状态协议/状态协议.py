# 状态协议.py - NovelOS 状态协议骨架
# 位置: 02_协议层/状态协议
# 依赖: 无外部协议层依赖，使用标准库
# 被调用: 其他模块通过此协议交换状态信息
# 功能: 定义状态数据的打包/解包接口，支持可插拔序列化器

import json
import logging
from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass, field

# 配置：可以从外部配置文件读取，这里提供默认值
DEFAULT_CONFIG = {
    "serializer": "json",         # 序列化方式: json, msgpack 等
    "use_compression": False,     # 是否压缩
    "compression_level": 6,       # 压缩等级
    "version": "1.0.0"            # 协议版本
}

class StateProtocol:
    """状态协议核心类，负责状态消息的序列化与反序列化。
    
    支持可插拔的序列化器，通过配置或方法注入。
    """
    
    def __init__(self, config: Optional[Dict] = None, serializer: Optional[Callable] = None, deserializer: Optional[Callable] = None):
        """
        初始化协议实例。
        
        Args:
            config: 配置字典，若不提供则使用默认配置。
            serializer: 自定义序列化函数，用于 encode 步骤。
            deserializer: 自定义反序列化函数，用于 decode 步骤。
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        
        # 设置序列化器 (可插拔)
        if serializer:
            self.encode_func = serializer
        else:
            self.encode_func = self._default_encode
            
        if deserializer:
            self.decode_func = deserializer
        else:
            self.decode_func = self._default_decode
        
        self.logger.info(f"状态协议初始化，版本: {self.config['version']}，序列化方式: {self.config['serializer']}")
    
    def _default_encode(self, data: Dict) -> bytes:
        """默认JSON编码器"""
        return json.dumps(data, ensure_ascii=False).encode('utf-8')
    
    def _default_decode(self, raw: bytes) -> Dict:
        """默认JSON解码器"""
        return json.loads(raw.decode('utf-8'))
    
    def encode(self, data: Dict) -> bytes:
        """将状态字典打包为字节流（可扩展压缩）"""
        try:
            packed = self.encode_func(data)
            if self.config.get("use_compression"):
                # 压缩逻辑占位，可后续插入
                # packed = compress(packed, level=self.config["compression_level"])
                self.logger.debug("压缩功能待实现")
            return packed
        except Exception as e:
            self.logger.error(f"编码失败: {e}")
            raise
    
    def decode(self, raw: bytes) -> Dict:
        """将字节流解包为状态字典"""
        try:
            if self.config.get("use_compression"):
                # 解压逻辑占位
                # raw = decompress(raw)
                self.logger.debug("解压功能待实现")
            data = self.decode_func(raw)
            return data
        except Exception as e:
            self.logger.error(f"解码失败: {e}")
            raise
    
    def create_message(self, event_type: str, payload: Dict, **kwargs) -> Dict:
        """创建标准化状态消息结构
        
        Args:
            event_type: 事件类型字符串，如 'character_update', 'plot_progress'。
            payload: 消息负载，具体内容。
            **kwargs: 额外元数据，如 source_module, timestamp 等。
        
        Returns:
            准备好的消息字典，可立即编码。
        """
        import time
        message = {
            "protocol": "state_protocol",
            "version": self.config["version"],
            "event_type": event_type,
            "timestamp": kwargs.get("timestamp", time.time()),
            "source": kwargs.get("source", "unknown"),
            "payload": payload,
            "extra": kwargs.get("extra", {})
        }
        return message

# 自测部分
if __name__ == "__main__":
    # 配置日志输出到控制台便于测试
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # 测试1：默认配置
    print("=== 测试默认JSON协议 ===")
    proto = StateProtocol()
    msg = proto.create_message(
        event_type="test_event",
        payload={"novel_id": "42", "status": "drafting"},
        source="test_module"
    )
    print("原始消息:", msg)
    
    encoded = proto.encode(msg)
    print("编码后 (bytes):", encoded[:50], "...")
    
    decoded = proto.decode(encoded)
    print("解码后:", decoded)
    assert msg == decoded, "编解码结果不一致"
    print("测试1通过\n")
    
    # 测试2：自定义序列化器（可插拔演示）
    print("=== 测试自定义序列化器 ===")
    import pickle
    
    def pickle_encode(data):
        return pickle.dumps(data)
    
    def pickle_decode(raw):
        return pickle.loads(raw)
    
    proto_custom = StateProtocol(serializer=pickle_encode, deserializer=pickle_decode)
    msg2 = proto_custom.create_message(event_type="character_update", payload={"name": "主角", "age": 25})
    enc2 = proto_custom.encode(msg2)
    dec2 = proto_custom.decode(enc2)
    assert msg2 == dec2, "自定义序列化测试失败"
    print("自定义序列化测试通过\n")
    
    # 测试3：配置压缩（占位未实现，确保不报错）
    print("=== 测试压缩配置（占位） ===")
    proto_comp = StateProtocol(config={"use_compression": True, "compression_level": 9})
    msg3 = proto_comp.create_message("compress_test", {"data": "some large content"})
    enc3 = proto_comp.encode(msg3)  # 占位，不影响
    dec3 = proto_comp.decode(enc3)
    assert dec3["event_type"] == "compress_test"
    print("压缩占位测试通过\n")
    
    print("所有自测通过。")