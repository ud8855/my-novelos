""" 
Module: style_perturbation.py
Layer: 23_去AI化 (De-AIfication Layer) 
Purpose: Provide style perturbation to reduce AI-like writing style.
Dependencies: 20_模型协同/ (model coordination), 21_API模型/ (API model), config, logging.
Called by: upper coordination module (e.g., 小说生成流程)
Solves: Modifying generated text to mimic human writing quirks.
"""

import logging
import json
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
import random

# ---- Logger Setup ----
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

# ---- Default Configuration ----
DEFAULT_CONFIG = {
    "perturbation_strength": 0.3,          # 0.0 (none) to 1.0 (aggressive)
    "enable_typo_injection": False,        # inject occasional typos
    "typo_probability": 0.02,              # per character
    "enable_sentence_fragments": True,     # use incomplete sentences
    "fragment_probability": 0.1,           # per sentence
    "enable_human_vocab_shift": True,      # replace overly perfect words
    "vocab_shift_map": {
        # example: AI word -> more colloquial alternative
        "utilize": "use",
        "commence": "start",
        "therefore": "so",
        "nevertheless": "but still"
    },
    "enable_punctuation_quirk": True,      # add ... or -- occasionally
    "quirk_probability": 0.05,
    "max_perturbation_rounds": 1,
    "random_seed": None,
    "log_level": "DEBUG"
}

# Load config from a JSON file if exists; otherwise use default.
def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    if config_path is None:
        config_path = Path(__file__).parent / "style_perturbation_config.json"
    else:
        config_path = Path(config_path)
    
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                config.update(user_config)
                logger.info(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}, using defaults.")
    else:
        logger.info("No config file found, using default configuration.")
    
    # Set random seed if provided
    if config.get("random_seed") is not None:
        random.seed(config["random_seed"])
    return config


class StylePerturbator:
    """
    Pluggable style perturbator to reduce AI detection.
    Implements configurable techniques.
    Can be hot-replaced or updated.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            config = load_config()
        self.config = config
        self._validate_config()
        logger.info(f"StylePerturbator initialized with strength={self.config['perturbation_strength']}")
    
    def _validate_config(self):
        required_keys = ["perturbation_strength", "enable_typo_injection", "enable_sentence_fragments",
                         "enable_human_vocab_shift", "enable_punctuation_quirk"]
        for key in required_keys:
            if key not in self.config:
                raise KeyError(f"Missing config key: {key}")
        # Clamp strength
        self.config["perturbation_strength"] = max(0.0, min(1.0, self.config["perturbation_strength"]))
    
    def reload_config(self, config_path: Optional[str] = None):
        """Hot reload configuration from file or dict."""
        new_config = load_config(config_path)
        self.config = new_config
        self._validate_config()
        logger.info("Configuration hot-reloaded.")
    
    def set_config_param(self, key: str, value: Any):
        """Update a single config parameter at runtime."""
        if key in self.config:
            self.config[key] = value
            logger.info(f"Config param '{key}' set to {value}.")
            if key == "perturbation_strength":
                self._validate_config()
        else:
            logger.warning(f"Config param '{key}' not recognized; adding it.")
            self.config[key] = value
    
    def perturb(self, text: str) -> str:
        """Main entry point: apply all enabled perturbations to text."""
        if not text:
            return text
        
        strength = self.config["perturbation_strength"]
        if strength <= 0:
            return text
        
        logger.debug(f"Original text length: {len(text)}")
        # Apply perturbations sequentially. Order may matter.
        perturbed = text
        # Sentence fragmentation
        if self.config["enable_sentence_fragments"] and strength > 0:
            perturbed = self._apply_sentence_fragments(perturbed)
        
        # Human vocabulary shift
        if self.config["enable_human_vocab_shift"] and strength > 0:
            perturbed = self._apply_vocab_shift(perturbed)
        
        # Punctuation quirks
        if self.config["enable_punctuation_quirk"] and strength > 0:
            perturbed = self._apply_punctuation_quirk(perturbed)
        
        # Typo injection (applied last because typos might break structures)
        if self.config["enable_typo_injection"] and strength > 0:
            perturbed = self._apply_typo_injection(perturbed)
        
        logger.info(f"Perturbation applied. Final length: {len(perturbed)}")
        return perturbed
    
    def _apply_sentence_fragments(self, text: str) -> str:
        """Randomly truncate sentences to create fragments."""
        if not text:
            return text
        prob = self.config["fragment_probability"] * self.config["perturbation_strength"]
        sentences = text.split('.')
        new_sentences = []
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                new_sentences.append(sent)
                continue
            if random.random() < prob:
                # Cut sentence at a random word boundary, add ellipsis maybe
                words = sent.split()
                if len(words) > 3:
                    cut_point = random.randint(2, len(words)-1)
                    frag = ' '.join(words[:cut_point]) + '...'
                    new_sentences.append(frag)
                else:
                    new_sentences.append(sent)
            else:
                new_sentences.append(sent)
        return '. '.join(new_sentences) + ('.' if text.endswith('.') else '')
    
    def _apply_vocab_shift(self, text: str) -> str:
        """Replace AI-sounding words with more colloquial alternatives."""
        vocab_map = self.config.get("vocab_shift_map", {})
        if not vocab_map:
            return text
        import re
        # Simple case-insensitive replacement for whole words
        for ai_word, human_word in vocab_map.items():
            # Only replace if randomness threshold met based on strength
            if random.random() > self.config["perturbation_strength"]:
                continue
            pattern = re.compile(r'\b' + re.escape(ai_word) + r'\b', re.IGNORECASE)
            text = pattern.sub(human_word, text)
        return text
    
    def _apply_punctuation_quirk(self, text: str) -> str:
        """Insert extra punctuation marks like '--' or '...' in random places."""
        if not text:
            return text
        prob = self.config["quirk_probability"] * self.config["perturbation_strength"]
        result = []
        # Insert quirk between words or after punctuation occasionally
        for char in text:
            result.append(char)
            if char in (' ', ',', '.', ';', ':') and random.random() < prob:
                quirk = random.choice(['...', '--'])
                result.append(quirk)
        return ''.join(result)
    
    def _apply_typo_injection(self, text: str) -> str:
        """Invert letters, drop letters, or swap with common typo."""
        prob = self.config["typo_probability"] * self.config["perturbation_strength"]
        if prob <= 0:
            return text
        chars = list(text)
        for i in range(len(chars)):
            if random.random() < prob and chars[i].isalpha():
                # Simple typo: replace with adjacent keyboard letter (simplified)
                typo_map = {'a': 's', 's': 'a', 'd': 'f', 'f': 'd', 'g': 'h', 'h': 'g',
                            'e': 'r', 'r': 'e', 't': 'y', 'y': 't', 'u': 'i', 'i': 'o'}
                char_lower = chars[i].lower()
                if char_lower in typo_map:
                    replacement = typo_map[char_lower]
                    if chars[i].isupper():
                        replacement = replacement.upper()
                    chars[i] = replacement
                else:
                    # Randomly delete with low prob
                    if random.random() < 0.5:
                        chars[i] = ''   # will be removed later
        text = ''.join(chars)
        # Clean up any double spaces from deletions
        import re
        text = re.sub(r' +', ' ', text)
        return text
    
    def __repr__(self):
        return f"StylePerturbator(strength={self.config['perturbation_strength']})"

# ---- Pluggable API ----
# This module should expose a factory and be hot-swappable.
def create_perturbator(config_path: Optional[str] = None) -> StylePerturbator:
    """Factory function to create a perturbator instance."""
    return StylePerturbator(load_config(config_path))

# ---- Self-Test Routine ----
if __name__ == "__main__":
    # Simple built-in test when run directly
    logging.basicConfig(level=logging.DEBUG)
    test_text = "Therefore, the protagonist commenced his journey. It was a beautiful morning. Nevertheless, challenges awaited."
    print("Original:", test_text)
    p = StylePerturbator()
    print("Perturbed:", p.perturb(test_text))
    
    # Test hot-reload
    p.set_config_param("enable_typo_injection", True)
    p.set_config_param("typo_probability", 0.1)
    print("After config change:", p.perturb(test_text))
    
    # Test fragment heavy
    p.set_config_param("perturbation_strength", 0.9)
    p.set_config_param("fragment_probability", 0.5)
    print("Heavy perturbation:", p.perturb(test_text))