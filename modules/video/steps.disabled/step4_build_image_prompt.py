"""Pipeline Step4 Build Image Prompt — extracted from pipeline_affiliate.py."""
import os, sys, json, time, uuid, logging, subprocess, shutil, re
from pathlib import Path
from typing import Optional, List, Dict, Any
import requests

# Add parent paths
_erp_stack = Path(__file__).parent.parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))

from shared_config import PRODIA_TOKEN, GEMINI_API_KEY
_ugc_client_dir = os.path.join(str(_erp_stack), "prompt-builder-service")
if _ugc_client_dir not in sys.path:
    sys.path.insert(0, _ugc_client_dir)
from ugc_schema_client import get_default_style, get_style_config, validate_ugc_style, is_valid_style

from .common import (
    logger, STORAGE_DIR, TMP_DIR, IMAGE_GEN_URL, PROMPT_BUILDER_URL,
    download_file, concat_videos, get_bgm_path,
)


def build_image_prompt(
    product_name: str,
    product_profile: dict,
    recipe: dict,
) -> str:
    """
    Step 4: Build image prompt via Mistral

    Args:
        product_name: ชื่อสินค้า
        product_profile: ผลจาก analyze_product()
        recipe: ผลจาก load_recipe()

    Returns:
        str: image_prompt
    """
    logger.info(f"Step 4/9: Build image prompt (Mistral)")

    # ใช้ image_prompt ที่ได้จาก analyze_product() (Step 1)
    image_prompt = product_profile.get("_image_prompt", "")

    if image_prompt:
        logger.info(f"  Image prompt: {image_prompt[:60]}...")
        return image_prompt

    # Fallback: basic prompt
    logger.warning("  No image prompt from analyze, using fallback")
    return f"{product_name}, product showcase, clean background, professional photography"


