# Configuration for DeepSeek API

import os
from typing import Dict, Optional

# DeepSeek API Configuration
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODELS = {
    "deepseek-v4-flash": {
        "description": "Fast and efficient model for quick responses",
        "max_tokens": 1024
    },
    "deepseek-v4-pro": {
        "description": "High-quality model for detailed responses",
        "max_tokens": 2048
    }
}


def validate_deepseek_key() -> bool:
    """Check if DeepSeek API key is set."""
    return DEEPSEEK_API_KEY is not None and DEEPSEEK_API_KEY.strip() != ""


def get_deepseek_model_config(model_name: str) -> Optional[Dict]:
    """Get configuration for a specific DeepSeek model."""
    return DEEPSEEK_MODELS.get(model_name)