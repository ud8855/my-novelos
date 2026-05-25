import logging
import json
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

class TokenControllerBase(ABC):
    """
    Abstract base for token management within the context system.
    Ensures pluggability and a common interface.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def count_tokens(self, text: str, model_name: Optional[str] = None) -> int:
        """Count tokens in the given text, optionally for a specific model."""
        pass

    @abstractmethod
    def budget_check(self, current_tokens: int, additional_tokens: int, max_tokens: Optional[int] = None) -> bool:
        """Check whether adding tokens stays within budget."""
        pass

    @abstractmethod
    def truncate_text(self, text: str, max_tokens: int, model_name: Optional[str] = None) -> str:
        """Truncate text to fit within max_tokens, preserving as much relevant content as possible."""
        pass

class TokenController(TokenControllerBase):
    """
    Concrete token controller that supports configurable tokenizer backends,
    usage logging, and budget enforcement.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.default_model = config.get("default_model", "gpt-3.5-turbo")
        self.tokenizer_backend = config.get("tokenizer_backend", "tiktoken")  # placeholder
        self.log_token_usage = config.get("log_token_usage", True)
        self.max_budget = config.get("max_budget", 4096)
        self._init_tokenizer()

    def _init_tokenizer(self):
        """Load or initialize the tokenizer backend based on configuration."""
        self.logger.info(f"Initializing tokenizer backend: {self.tokenizer_backend}")
        # Placeholder for actual backend loading (e.g., tiktoken, transformers)
        pass

    def count_tokens(self, text: str, model_name: Optional[str] = None) -> int:
        model = model_name or self.default_model
        self.logger.debug(f"Counting tokens for model {model}")
        # Placeholder: implement actual tokenization
        # For now, use a rough approximation (4 chars = 1 token)
        token_count = len(text) // 4
        if self.log_token_usage:
            self.logger.info(f"Token count: {token_count} tokens (text length={len(text)})")
        return token_count

    def budget_check(self, current_tokens: int, additional_tokens: int, max_tokens: Optional[int] = None) -> bool:
        limit = max_tokens if max_tokens is not None else self.max_budget
        allowed = (current_tokens + additional_tokens) <= limit
        self.logger.debug(f"Budget check: {current_tokens} + {additional_tokens} <= {limit} -> {allowed}")
        return allowed

    def truncate_text(self, text: str, max_tokens: int, model_name: Optional[str] = None) -> str:
        # Naive truncation: cut off at approximate character boundary
        approximate_chars = max_tokens * 4
        if len(text) <= approximate_chars:
            return text
        self.logger.info(f"Truncating text from {len(text)} chars to ~{approximate_chars} chars for {max_tokens} tokens")
        return text[:approximate_chars] + "..."

    @staticmethod
    def load_config(config_path: str) -> Dict[str, Any]:
        """Load configuration from JSON/YAML file."""
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file {config_path} not found.")
        with open(config_path, "r") as f:
            if config_path.endswith(".yaml") or config_path.endswith(".yml"):
                # Placeholder for YAML loading; for now assume JSON
                raise NotImplementedError("YAML support not yet implemented.")
            return json.load(f)

# Self-test block
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    sample_config = {
        "default_model": "gpt-4",
        "tokenizer_backend": "tiktoken",
        "log_token_usage": True,
        "max_budget": 8192
    }
    controller = TokenController(sample_config)
    test_text = "This is a sample text that will be used to demonstrate token control functionality. " * 50
    tokens = controller.count_tokens(test_text)
    print(f"Token count: {tokens}")
    print(f"Budget check (5000 + 3000): {controller.budget_check(5000, 3000)}")
    truncated = controller.truncate_text(test_text, 100)
    print(f"Truncated length: {len(truncated)}")