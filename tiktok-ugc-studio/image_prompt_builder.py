#!/usr/bin/env python3
"""
Prompt Builder — HTTP Shim
=============================
Delegates all prompt work to a remote Prompt Builder Service via HTTP.
"""

import os
import logging
from typing import Optional, List

import httpx

logger = logging.getLogger("prompt_builder")

PROMPT_BUILDER_URL = os.environ.get(
    "PROMPT_BUILDER_URL",
    "http://localhost:8117",
)


async def analyze_and_build_prompts(
    product_name: str,
    description: str = "",
    keywords: Optional[List[str]] = None,
    ugc_style: str = "holding",
    product_id: str = "",
    price: float = 0.0,
) -> dict:
    """Full pipeline: analyze product + build prompts via remote service."""
    payload = {
        "product_name": product_name,
        "description": description,
        "keywords": keywords or [],
        "ugc_style": ugc_style,
        "product_id": product_id,
        "price": price,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{PROMPT_BUILDER_URL}/api/v1/build",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()


async def build_prompt(
    product_name: str,
    description: str = "",
    ugc_style: str = "holding",
    gemini_analysis: Optional[dict] = None,
) -> dict:
    """Legacy API — delegates to analyze-and-build."""
    return await analyze_and_build_prompts(
        product_name=product_name,
        description=description,
        ugc_style=ugc_style,
    )


async def process_image_prompt_request(
    product_name: str,
    description: str = "",
    ugc_style: str = "holding",
    use_mistral: bool = True,
) -> dict:
    """Legacy API wrapper — delegates to analyze-and-build."""
    return await analyze_and_build_prompts(
        product_name=product_name,
        description=description,
        ugc_style=ugc_style,
    )
