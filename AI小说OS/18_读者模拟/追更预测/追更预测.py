# -*- coding: utf-8 -*-
"""
追更预测模块 (Chase Prediction Module)
所属层级: 18_读者模拟/追更预测
依赖层: 20_模型协同/模型调度器 (ModelCoordinator) 或 21_API模型/外部API
被调用者: 读者模拟引擎、剧情影响分析等上层模块
功能: 根据小说当前进度、读者画像和历史行为，预测读者是否继续追更。
设计原则: 单一职责、可插拔、配置化、日志完整、支持热插拔。
"""

import logging
import json
import os
from typing import Dict, Any, Optional, Tuple

# 配置默认路径，可通过外部注入覆盖
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "chase_prediction_config.json")

class ChasePredictor:
    """
    追更预测器
    提供核心预测能力，所有预测逻辑必须通过统一的 predict 接口调用。
    该预测器可通过替换内部模型适配器实现插拔。
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化预测器，加载配置、设置日志。
        
        Args:
            config_path: 配置文件的绝对路径，若为None则使用默认路径。
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config = self._load_config()
        self._setup_logging()
        self.logger = logging.getLogger("ChasePredictor")
        self.logger.info("追更预测器初始化开始")
        
        # 模型适配器，实际调用底层模型，可插拔
        self.model_adapter = None
        # 可在此处根据配置动态加载模型适配器（如ModelCoordinator或API调用器）
        # 示例：self.model_adapter = ModelCoordinator(self.config.get("model", {}))
        self.logger.info("追更预测器初始化完成")
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载JSON配置文件，若文件不存在则返回默认配置。
        
        Returns:
            配置字典
        """
        if not os.path.exists(self.config_path):
            default_config = {
                "model": {
                    "type": "mock",
                    "parameters": {}
                },
                "threshold": 0.6,
                "features": ["recent_chapters", "reader_retention", "sentiment_score"]
            }
            logging.warning(f"配置文件未找到: {self.config_path}，使用默认配置")
            return default_config
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logging.info(f"配置文件加载成功: {self.config_path}")
                return config
        except Exception as e:
            logging.error(f"配置文件加载失败: {e}")
            raise
    
    def _setup_logging(self):
        """配置日志输出，采用标准格式，支持配置文件控制级别。"""
        log_config = self.config.get("logging", {})
        log_level = log_config.get("level", "INFO")
        log_format = log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        log_file = log_config.get("file", None)
        
        handlers = []
        if log_file:
            handlers.append(logging.FileHandler(log_file, encoding='utf-8'))
        else:
            # 默认标准输出
            handlers.append(logging.StreamHandler())
        
        logging.basicConfig(
            level=getattr(logging, log_level.upper(), logging.INFO),
            format=log_format,
            handlers=handlers
        )
    
    def predict(self, context: Dict[str, Any], reader_profile: Dict[str, Any]) -> Tuple[bool, float, Dict[str, Any]]:
        """
        预测读者是否追更。
        
        Args:
            context: 小说上下文信息，如最近章节内容、更新频率、章节质量评分等。
            reader_profile: 读者画像，包括历史阅读行为、偏好、活跃度等。
        
        Returns:
            (will_chase, confidence, details)
            will_chase: 布尔值，是否追更
            confidence: 置信度0-1之间
            details: 详细解释或中间结果，便于调试和分析
        """
        self.logger.info("开始执行追更预测")
        try:
            # 特征提取（可扩展）
            features = self._extract_features(context, reader_profile)
            self.logger.debug(f"提取特征: {features}")
            
            # 调用模型进行预测
            raw_prediction = self._invoke_model(features)
            self.logger.debug(f"模型原始输出: {raw_prediction}")
            
            # 决策与后处理
            will_chase, confidence, details = self._post_process(raw_prediction)
            self.logger.info(f"预测完成: will_chase={will_chase}, confidence={confidence:.2f}")
            return will_chase, confidence, details
            
        except Exception as e:
            self.logger.error(f"预测过程异常: {e}", exc_info=True)
            # 异常情况下返回保守预测（不追更），日志记录后可触发自动恢复机制
            return False, 0.0, {"error": str(e)}
    
    def _extract_features(self, context: Dict[str, Any], reader_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        从原始输入中提取用于预测的特征向量。
        具体特征根据配置文件中的 features 列表选取。
        此方法可被子类重写以实现自定义特征工程。
        
        Args:
            context: 上下文
            reader_profile: 读者画像
        
        Returns:
            特征字典
        """
        feature_names = self.config.get("features", [])
        features = {}
        # 基于配置提取特征，避免硬编码
        for fname in feature_names:
            # 简单示例：直接从输入字典查找，实际可做更复杂处理
            features[fname] = (context.get(fname) or reader_profile.get(fname))
        return features
    
    def _invoke_model(self, features: Dict[str, Any]) -> Any:
        """
        调用底层模型适配器获取预测结果。
        当前使用模拟适配器，正式实现时替换为ModelCoordinator或API调用。
        
        Args:
            features: 特征字典
        
        Returns:
            模型输出，格式由适配器定义
        """
        # TODO: 替换为真实模型调用，通过依赖注入的 model_adapter
        if self.model_adapter is not None:
            return self.model_adapter.predict(features)
        else:
            # 模拟返回
            self.logger.warning("使用模拟模型适配器，返回默认结果")
            return {"prediction": 0.7, "explanation": "mock_output"}
    
    def _post_process(self, raw_prediction: Any) -> Tuple[bool, float, Dict[str, Any]]:
        """
        对模型原始输出进行后处理，得到最终的追更决策和置信度。
        可根据配置中的阈值进行调整。
        
        Args:
            raw_prediction: 模型原始输出
        
        Returns:
            (追更决策, 置信度, 详细信息)
        """
        # 假设模型输出是一个字典，包含 score 字段
        if isinstance(raw_prediction, dict) and "prediction" in raw_prediction:
            score = raw_prediction["prediction"]
            confidence = score
        else:
            score = 0.5
            confidence = 0.5
        
        threshold = self.config.get("threshold", 0.5)
        will_chase = score >= threshold
        
        details = {
            "raw_score": score,
            "threshold": threshold,
            "explanation": raw_prediction.get("explanation", "") if isinstance(raw_prediction, dict) else ""
        }
        return will_chase, confidence, details
    
    def update_config(self, new_config: Dict[str, Any]):
        """
        动态更新配置，无需重启服务，支持热更新。
        
        Args:
            new_config: 新的配置字典
        """
        self.config.update(new_config)
        self.logger.info("配置热更新成功")
    
    def reload_config(self):
        """重新从文件加载配置，实现配置热重载。"""
        try:
            self.config = self._load_config()
            self.logger.info("配置文件重载成功")
        except Exception as e:
            self.logger.error(f"配置文件重载失败: {e}")


# 模块自测部分
if __name__ == "__main__":
    # 设置一个简单的测试
    print("=== 追更预测模块自测 ===")
    
    # 测试配置加载
    predictor = ChasePredictor()
    
    # 构造测试数据
    test_context = {
        "recent_chapters": 10,
        "update_frequency": 2,   # 每周更新次数
        "average_quality": 4.2
    }
    test_profile = {
        "reader_retention": 0.8,
        "sentiment_score": 0.7,
        "active_days": 30
    }
    
    # 执行预测
    will_chase, conf, details = predictor.predict(test_context, test_profile)
    print(f"预测结果: 追更={will_chase}, 置信度={conf:.2f}")
    print(f"详细信息: {details}")
    
    # 测试配置热更新
    predictor.update_config({"threshold": 0.8})
    will_chase2, conf2, _ = predictor.predict(test_context, test_profile)
    print(f"阈值调整为0.8后: 追更={will_chase2}, 置信度={conf2:.2f}")
    
    print("=== 自测完成 ===")