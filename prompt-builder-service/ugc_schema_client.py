"""
UGC Style Schema Client

Central source of truth for UGC styles.
Reads from Schema Engine (port 8100) with local fallback.
"""

import json
import logging
import os
import requests
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SCHEMA_ENGINE_URL = os.getenv("SCHEMA_ENGINE_URL", "http://localhost:8100")

# DeepSeek API Configuration
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


def call_deepseek_api(prompt: str, model: str = "deepseek-v4-flash") -> Optional[str]:
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024
    }
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data)
        response.raise_for_status()
        return response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling DeepSeek API: {e}")
        return None

# ── Local fallback (used when Schema Engine is unreachable) ─────────
_FALLBACK_STYLES: Dict[str, Dict[str, Any]] = {
    "warehouse_vlog": {
        "model_action": "Ethnic Thai presenter standing inside an authentic warehouse/stockroom surrounded by shelves stacked with inventory boxes, holding the product and pointing to warehouse stock",
        "camera": "medium shot, warehouse aisle framing, shelves with stock boxes in background",
        "vibe": "high-trust"
    }
}