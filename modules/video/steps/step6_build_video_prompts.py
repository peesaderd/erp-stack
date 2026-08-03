"""Pipeline Step6 Build Video Prompts — extracted from pipeline_affiliate.py."""
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


def build_video_prompts(
    product_profile: dict,
    recipe: dict,
    image_path: str,
    ugc_style: str = "holding",
) -> list:
    """
    Step 6: Build video prompts from recipe + image context

    Args:
        product_profile: ผลจาก analyze_product()
        recipe: ผลจาก load_recipe()
        image_path: path ของ image ที่สร้างแล้ว (Step 5)
        ugc_style: UGC style — ใช้ product_type/category กำหนด action ที่เหมาะสม

    Returns:
        list: video_prompts (1 prompt per scene)
    """
    logger.info(f"Step 6/9: Build video prompts (ugc_style={ugc_style})")

    scenes = recipe.get("scenes", [])
    video_prompts = []

    setting = product_profile.get("setting", "clean modern lifestyle")
    category = product_profile.get("category", "other")
    product_type = product_profile.get("product_type", "").lower()
    product_name = product_profile.get("product_name", "") or product_profile.get("_product_name", "")

    # Lighting map (simple version)
    lighting_map = {
        "beauty": "soft diffused natural window lighting",
        "tools": "bright functional lighting",
        "electronics": "clean bright studio lighting",
        "food": "warm golden hour lighting",
        "fashion": "bright studio lighting",
        "home": "bright natural daylight",
        "other": "soft natural lighting",
    }
    lighting = lighting_map.get(category, "soft natural lighting")
    
    # Use target_age from analysis only — no fallback, no jitter
    try:
        target_age = int(product_profile.get("target_age", ""))
    except (ValueError, TypeError):
        target_age = None
    model_age = target_age if target_age is not None else ""

    # ── Scene descriptions ตาม product_type/category ──
    # แทนที่จะใช้ "hold only, cap CLOSED" เดียวกันทุก product
    # ใช้ product_type กำหนด action ที่เหมาะสมต่อ scene
    scene_descriptions = _scene_descriptions_for_category(category, product_type, product_name)

    # ── Model look (จาก profile, ไม่ hardcode) ──
    model_gender = product_profile.get("target_gender", "female")
    gender_en = {"female": "woman", "male": "man"}.get(model_gender, "woman")
    
    # ── Build per-scene prompts ──
    for i, scene in enumerate(scenes):
        scene_name = scene.get("name", f"Scene{i+1}")
        scene_dur = scene.get("duration", 2)
        
        # Get scene-specific description or default
        scene_action = scene_descriptions.get(scene_name, "product visible in frame, natural setting")
        
        # Build the full positive prompt (keep clean and focused on action and character)
        age_seg = f" {model_age} years old" if model_age else ""
        enhanced = (
            f"Ethnic Thai {gender_en}{age_seg}, porcelain white glowing skin, "
            f"monolid eyes, Southeast Asian ethnic Thai features. "
            f"{scene_action} "
            f"Setting: {setting}. {lighting}. "
            f"9:16 portrait, smooth natural motion"
        )
        
        # For beauty products: keep "not opening" restriction
        # For electronics/home/tools: allow natural product interaction
        if category in ("beauty", "health") and ugc_style == "holding":
            enhanced += (
                " CRITICAL: Product cap is CLOSED and sealed. "
                "Model is NOT opening or applying the product. "
                "Just holding and showing to camera."
            )
        
        video_prompts.append(enhanced)

    logger.info(f"  Generated {len(video_prompts)} video prompts for category={category}")
    return video_prompts


def _scene_descriptions_for_category(category: str, product_type: str, product_name: str) -> dict:
    """Generate scene descriptions based on product category/type.
    
    Returns dict {scene_name: action_description} ใช้ใน build_video_prompts()
    """
    pn = product_name or "product"
    
    # ── Electronics ──
    if category == "electronics":
        return {
            "Hook": f"Model walking toward {pn} installed on wall/counter, product clearly visible in the setting",
            "Problem": f"Close-up of {pn} in off/inactive state, showing need for activation",
            "Discovery": f"Hand reaching for {pn}, finger pressing button or switch, product activating with subtle indicator glow",
            "Features": f"{pn} in active use, feature demonstration, product functionality visible and working",
            "Transformation": f"Wide shot showing {pn} improving the space or solving the problem, room/area visibly better",
            "CTA": f"Model with satisfied expression, {pn} in focus in the background, final product showcase",
        }
    
    # ── Home / Tools ──
    elif category in ("home", "tools"):
        return {
            "Hook": f"Model entering frame holding {pn}, product clearly visible and recognizable",
            "Problem": f"Close-up showing problem or need before using {pn}, relatable struggle",
            "Discovery": f"Model beginning to use {pn}, natural action, product solving the immediate issue",
            "Features": f"Product detail close-up, key features of {pn} visible, texture and build quality shown",
            "Transformation": f"Result visible after using {pn}, improved situation, problem solved",
            "CTA": f"Model satisfied, {pn} in focus, final encouraging shot",
        }
    
    # ── Food ──
    elif category == "food":
        return {
            "Hook": f"{pn} packaging visible, appetizing presentation on table or counter",
            "Problem": f"Opening or preparing {pn}, anticipation visible",
            "Discovery": f"{pn} being revealed, poured, or displayed, texture and color visible",
            "Features": f"Close-up of {pn} texture, ingredients or details visible, mouth-watering shot",
            "Transformation": f"Final prepared state of {pn}, ready to enjoy, appetizing result",
            "CTA": f"Final shot of {pn}, encouraging viewer to try it",
        }
    
    # ── Fashion ──
    elif category == "fashion":
        return {
            "Hook": f"Model wearing {pn}, fashion-forward entrance, garment clearly visible on body",
            "Problem": f"Showing outfit without {pn}, neutral expression, missing piece visible",
            "Discovery": f"{pn} being worn and styled, model adjusting garment naturally on body",
            "Features": f"Texture and fabric detail close-up of {pn} on body, drape and fit visible",
            "Transformation": f"Complete look with {pn} worn confidently, full outfit visible on model",
            "CTA": f"Final confident look, {pn} worn and featured prominently on body",
        }
    
    # ── Beauty — keep original holding restriction ──
    elif category == "beauty":
        return {
            "Hook": f"Model holding {pn} in both hands, product packaging facing camera, smiling naturally, just showing",
            "Problem": f"Model still holding {pn}, gentle expression, product clearly visible",
            "Discovery": f"Model examining {pn}, slight head movement, product still in hands",
            "Features": f"Close-up of {pn}, product texture and packaging detail visible",
            "Transformation": f"Model presenting {pn} proudly, product in focus",
            "CTA": f"Final product showcase, {pn} in frame, model smiling warmly",
        }
    
    # ── Default: generic ──
    else:
        return {
            "Hook": f"Model holding {pn}, product clearly visible, natural opening",
            "Problem": f"{pn} shown in context, viewer attention drawn to product",
            "Discovery": f"Model interacting with {pn}, natural movement",
            "Features": f"Close-up details of {pn}, texture and build visible",
            "Transformation": f"Result or benefit of {pn} shown, improvement visible",
            "CTA": f"Final showcase, {pn} in focus, encouraging shot",
        }


