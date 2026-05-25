"""
Token规划模块 - 负责Token预算的分配与管理
用于在小说创作过程中，根据任务需求、模型能力、成本控制等因素，规划每一步的Token使用量。
可插拔，可配置，支持热更新。

依赖：配置系统、日志系统、模型协同接口（抽象）
被调用：由规划系统的上层调用，如大纲规划、章节规划等。
"""

import logging
from typing import Dict, Optional, Any

# 尝试导入全局配置管理器，若环境中不存在则后续可注入
try:
    from novelos.core.config import config_manager as global_config
except ImportError:
    global_config = None

logger = logging.getLogger(__name__)


class TokenPlanner:
    """Token规划器，负责根据上下文分配Token预算"""

    def __init__(self, model_capabilities: Optional[Dict[str, Any]] = None,
                 config: Optional[Any] = None):
        """
        初始化Token规划器

        Args:
            model_capabilities: 可选，模型能力字典，如 {'max_tokens': 4096, 'context_length': 8192}
            config: 可选，配置管理器对象，若未提供则尝试使用全局配置
        """
        self._config = config or global_config
        if self._config is None:
            logger.warning("No config manager provided, using empty defaults")
            self._config = _DummyConfig()

        self.model_capabilities = model_capabilities or self._config.get('model_capabilities', {})
        self.default_budget = self._config.get('token_planning.default_budget', 2048)
        self.reserved_tokens = self._config.get('token_planning.reserved_tokens', 500)

        logger.info("TokenPlanner initialized: capabilities=%s, default_budget=%d, reserved=%d",
                     self.model_capabilities, self.default_budget, self.reserved_tokens)

    def plan(self, task_type: str, context_length: int, user_prompt_tokens: int) -> Dict[str, int]:
        """
        根据任务类型和上下文长度规划Token预算

        Args:
            task_type: 任务类型，如 'outline', 'chapter', 'dialogue', 'summary'
            context_length: 当前上下文窗口已使用或计划使用的Token数（包含历史消息等）
            user_prompt_tokens: 用户提示的Token数量

        Returns:
            包含分配信息的字典，如:
            {
                'system_tokens': 系统提示Token数,
                'input_tokens': 输入Token总数,
                'max_output_tokens': 允许的最大输出Token数,
                'recommended_output': 推荐的输出Token数,
                'remaining_budget': 剩余可用预算
            }
        """
        # 获取该任务类型的配置比例
        task_config = self._config.get(f'token_planning.task_budgets.{task_type}', {})
        max_total = self.model_capabilities.get('max_tokens', 4096)

        system_tokens = self.reserved_tokens
        input_tokens = system_tokens + context_length + user_prompt_tokens

        available_for_output = max_total - input_tokens

        if available_for_output <= 0:
            logger.warning("Insufficient token budget: total=%d, input=%d", max_total, input_tokens)
            budget = {
                'system_tokens': system_tokens,
                'input_tokens': input_tokens,
                'max_output_tokens': max(0, available_for_output),
                'recommended_output': max(0, available_for_output // 2),
                'remaining_budget': 0
            }
        else:
            output_ratio = task_config.get('output_ratio', 0.8)
            recommended = int(available_for_output * output_ratio)
            recommended = min(recommended, self.default_budget)  # 不超过默认预算上限
            budget = {
                'system_tokens': system_tokens,
                'input_tokens': input_tokens,
                'max_output_tokens': available_for_output,
                'recommended_output': recommended,
                'remaining_budget': available_for_output - recommended
            }

        logger.debug("Token plan for '%s': %s", task_type, budget)
        return budget

    def update_capabilities(self, new_capabilities: Dict[str, Any]):
        """更新模型能力，支持热更新"""
        self.model_capabilities = new_capabilities
        logger.info("Model capabilities updated: %s", new_capabilities)

    def set_config(self, config):
        """替换配置管理器实例，实现可插拔"""
        self._config = config
        logger.info("Configuration manager replaced")


class _DummyConfig:
    """存根配置，当未提供真实配置时使用，避免None调用"""
    def get(self, key, default=None):
        return default


# ------------------ 自测部分 ------------------
if __name__ == "__main__":
    # 配置日志输出
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 模拟一个提供必要配置的简单配置管理器
    class MockConfig:
        def get(self, key, default=None):
            mock_data = {
                'model_capabilities': {'max_tokens': 409