"""
Prodia v2 Async API — Video Module Wrapper
============================================
Re-exports from shared prodia_client.py at erp-stack root.
Adds video-specific convenience functions.
"""

import os
import sys
from pathlib import Path
from typing import Optional

# Import shared client
_erp_stack = Path(__file__).parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))

from prodia_client import (
    ProdiaV2Client,
    ProdiaV2Error,
    ProdiaJobFailedError,
    ProdiaTimeoutError,
    ProdiaValidationError,
    ProdiaRateLimitError,
    get_default_client,
)

# Re-export everything
__all__ = [
    "ProdiaV2Client",
    "ProdiaV2Error",
    "ProdiaJobFailedError",
    "ProdiaTimeoutError",
    "ProdiaValidationError",
    "ProdiaRateLimitError",
    "get_default_client",
    "generate_video_async",
    "generate_image_async",
]


def generate_video_async(
    prompt: str,
    input_image: Optional[bytes] = None,
    duration: int = 8,
    resolution: str = "720P",
    ratio: str = "9:16",
    **kwargs,
) -> dict:
    """
    One-shot video generation via Prodia v2 Async API.
    
    Returns dict with: job_id, output_url, price, metrics, result_raw
    """
    client = get_default_client()
    return client.generate_video(
        prompt=prompt,
        input_image=input_image,
        duration=duration,
        resolution=resolution,
        ratio=ratio,
        **kwargs,
    )


def generate_image_async(
    prompt: str,
    input_image: Optional[bytes] = None,
    **kwargs,
) -> dict:
    """
    One-shot image generation via Prodia v2 Async API.
    """
    client = get_default_client()
    return client.generate_image(
        prompt=prompt,
        input_image=input_image,
        **kwargs,
    )
