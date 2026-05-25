class FaceSlapAlgorithmBase:
    """打脸算法抽象基类，定义统一接口，确保算法可插拔、可扩展。"""
    
    def __init__(self, config: dict = None):
        """
        初始化算法实例，支持配置化。
        :param config: 字典形式的高级配置，如阈值、权重等。若未提供则使用默认值。
        """
        self.config = config or self.default_config()
        self.logger = self._init_logger()
    
    @staticmethod
    def default_config() -> dict:
        """返回默认配置字典，子类可覆盖以提供自身默认值。"""
        return {
            "min_face_slap_score": 0.5,          # 最小打脸有效分值
            "emotion_weight": 0.3,               # 情绪权重
            "reversal_weight": 0.4,              # 反转冲击力权重
            "reader_expectation_weight": 0.3,    # 读者预期破坏权重
        }
    
    def _init_logger(self):
        """初始化日志记录器，支持热更新配置。"""
        import logging
        logger = logging.getLogger(self.__class__.__name__)
        logger.setLevel(logging.DEBUG if self.config.get("debug", False) else logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger
    
    def analyze_face_slap(self, context: dict) -> dict:
        """
        分析给定情境下的打脸效果。子类必须实现。
        :param context: 上下文数据，包含人物关系、前期铺垫、反转事件等。
        :return: 字典结果，至少包含 'score' (float), 'intensity' (str), 'suggestions' (list)
        """
        raise NotImplementedError("Subclasses must implement analyze_face_slap method.")
    
    def heat_calculate(self, raw_score: float) -> float:
        """根据原始得分计算最终热度值，允许子类自定义映射。"""
        # 默认线性映射，可重写
        return min(max(raw_score, 0.0), 1.0)
    
    def generate_suggestion(self, intensity: str, target_reader: str = "average") -> list:
        """根据打脸强度生成优化建议，可扩展。"""
        # 占位实现，返回空列表，子类可覆盖
        return []
    
    def update_config(self, new_config: dict):
        """动态更新配置，支持热插拔。"""
        self.config.update(new_config)
        self.logger.info(f"Configuration updated: {new_config}")
    
    def __repr__(self):
        return f"{self.__class__.__name__}(config={self.config})"


# ------------------ 自测部分 ------------------
if __name__ == "__main__":
    # 简单自测：创建实例，检查基本功能
    try:
        algo = FaceSlapAlgorithmBase()
        print("FaceSlapAlgorithmBase instance created.")
        print("Default config:", algo.default_config())
        
        # 尝试调用未实现的抽象方法，应引发 NotImplementedError
        try:
            algo.analyze_face_slap({})
        except NotImplementedError as e:
            print("NotImplementedError caught as expected:", e)
        
        # 测试配置更新
        algo.update_config({"min_face_slap_score": 0.7})
        print("Updated config:", algo.config)
        
        # 测试热度计算
        score = algo.heat_calculate(0.8)
        print(f"Heat calculated: {score}")
        
        print("Self-test passed.")
    except Exception as e:
        print(f"Self-test failed: {e}")