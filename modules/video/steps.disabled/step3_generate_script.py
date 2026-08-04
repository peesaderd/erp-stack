"""Pipeline Step3 Generate Script — extracted from pipeline_affiliate.py."""
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


def generate_script(
    product_name: str,
    product_profile: dict,
    recipe: dict,
    ugc_style: str = "holding",
) -> str:
    """
    Step 3: Generate script via Gemini

    Args:
        product_name: ชื่อสินค้า
        product_profile: ผลจาก analyze_product()
        recipe: ผลจาก load_recipe()
        ugc_style: สไตล์ UGC (holding, review, product_demo, ...)

    Returns:
        str: full_script
    """
    logger.info(f"Step 3/9: Generate script (Gemini, style={ugc_style})")

    try:
        sys.path.insert(0, str(Path(__file__).parent))
        from script_gen import generate_tiktok_review_script

        # product_demo style → use natural Thai narration template
        # other styles → use review template (Hook/Value/CTA)
        style = "product_demo" if ugc_style == "product_demo" else "review"

        result = generate_tiktok_review_script(
            product_name=product_name,
            customer_problem=product_profile.get("customer_problem", ""),
            main_benefit=product_profile.get("main_benefit", ""),
            target_audience=product_profile.get("target_audience", ""),
            tone="เป็นกันเอง พูดเร็ว",
            duration=f"{recipe.get('total_duration', 8)}s",
            features=product_profile.get("features", ""),
            product_appearance=product_profile.get("product_appearance", ""),
            style=style,
            gender=product_profile.get("target_gender", "female"),
            target_age=product_profile.get("target_age", ""),
        )

        script = result.get("script", "")
        logger.info(f"  Script: {script[:100]}... (uses_llm={result.get('uses_llm')})")
        return script

    except Exception as e:
        logger.error(f"Script generation failed: {e}")
        # Fallback: natural Thai narration for product_demo
        if ugc_style == "product_demo":
            feat = product_profile.get("features", "")
            appear = product_profile.get("product_appearance", "")
            if feat:
                return f"{product_name} ตัวนี้ {feat} ใช้งานง่ายมาก"
            elif appear:
                return f"{product_name} ตัวนี้{appear[:100]} ใช้งานดี"
            return f"{product_name} ตัวนี้ใช้งานดีมาก"
        # Default: template review script
        base = f"{product_profile.get('customer_problem', 'ปัญหาที่เจอบ่อย')} ใช่ไหมคะ? วันนี้เรามี {product_name}"
        feat = product_profile.get("features", "")
        if feat:
            base += f" มี {feat}"
        base += f" {product_profile.get('main_benefit', 'คุณภาพดี')} ค่ะ กดตะกร้าเลย!"
        return base


# ═══════════════════════════════════════════════════════════════════════════
