#!/usr/bin/env python3
"""
Prompt Builder — Unified Pipeline
====================================
Uses Mistral for:
  - Product analysis (category, gender, age, problem, benefit)
  - UGC prompt generation (image_prompt, video_prompt, negative_prompt)

Single import for all prompt-related work.
"""

import os
import sys
import json
import logging
import re
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger("prompt-builder-service")

# ─── Paths ───────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent  # prompt-builder-service/
PROMPTS_DIR = BASE_DIR
UGC_DIR = BASE_DIR / "UGC_prompts"

# ─── Mistral Config ──────────────────────────────────────────────────
from shared_config import MISTRAL_API_KEY as _MISTRAL_API_KEY_LAZY

# ─── Style / Category Maps (fallback when Mistral fails) ─────────────

STYLE_MAP = {
    "holding": {
        "model_action": "holding the product in both hands, product packaging facing camera, smiling naturally",
        "camera": "mid shot, waist up, product visible at chest level",
        "vibe": "friendly, approachable, product-focused",
        "keywords": "both hands holding product, product clearly visible and in focus",
        "video_motion": "model holding product, gentle hand movement showing product tube, natural breathing motion, slight head tilt",
    },
    "usage": {
        "model_action": "actively using the product in a natural daily setting, candid moment, product in use",
        "camera": "medium shot showing product usage context, slightly zoomed for action",
        "vibe": "authentic, lifestyle, in-the-moment",
        "keywords": "product in use, daily routine, natural hands-on moment",
        "video_motion": "model applying/using product naturally, gentle hand movements, routine motion",
    },
    "review": {
        "model_action": "holding product up showing packaging to camera, excited expression, like unboxing reaction",
        "camera": "close up to mid shot, product front and center, model slightly off-center",
        "vibe": "enthusiastic, honest, review energy",
        "keywords": "product held up, packaging visible, model reacting to product",
        "video_motion": "model showing product to camera, gentle presenter motion, slight zoom effect",
    },
    "talking": {
        "model_action": "talking while casually holding product, relaxed hand gesture, product naturally present",
        "camera": "close up, talking head style, product in lower frame",
        "vibe": "conversational, vlog-style, personal",
        "keywords": "talking head, casually holding, natural conversation pose",
        "video_motion": "model talking naturally, subtle head and hand gestures, casual vlog motion",
    },
}

PRODUCT_CATEGORY_MAP = {
    "ลิปสติก":    {"category": "beauty",  "gender": "female", "age": "25", "setting": "vanity room หรือ outdoor เช่น ร้านกาแฟ"},
    "ลิป":        {"category": "beauty",  "gender": "female", "age": "25", "setting": "vanity room หรือ outdoor เช่น ร้านกาแฟ"},
    "คอนซีลเลอร์": {"category": "beauty",  "gender": "female", "age": "25", "setting": "vanity room with mirror, good lighting"},
    "บลัช":       {"category": "beauty",  "gender": "female", "age": "25", "setting": "vanity or bedroom, soft natural lighting"},
    "มาส์ก":      {"category": "beauty",  "gender": "female", "age": "25", "setting": "bathroom or bedroom, clean modern background"},
    "สบู่":        {"category": "beauty",  "gender": "unisex", "age": "25", "setting": "bathroom, clean tiled wall, modern"},
    "ครีม":       {"category": "beauty",  "gender": "female", "age": "25", "setting": "bathroom หรือ bedroom vanity"},
    "เซรั่ม":     {"category": "beauty",  "gender": "female", "age": "25", "setting": "bathroom vanity, clean white background"},
    "กันแดด":     {"category": "beauty",  "gender": "unisex", "age": "25", "setting": "outdoor หรือ near window, natural light"},
    "สกินแคร์":    {"category": "beauty",  "gender": "female", "age": "25", "setting": "bedroom vanity, soft natural lighting"},
    "หูฟัง":      {"category": "electronics", "gender": "unisex", "age": "25", "setting": "modern room, desk with tech accessories"},
    "ลำโพง":     {"category": "electronics", "gender": "unisex", "age": "25", "setting": "living room หรือ desk, modern decor"},
    "ขนม":        {"category": "food",    "gender": "unisex", "age": "25", "setting": "kitchen table หรือ cafe, natural lighting"},
    "เครื่องดื่ม": {"category": "food",    "gender": "unisex", "age": "25", "setting": "cafe corner หรือ modern kitchen"},
    "เสื้อผ้า":    {"category": "fashion", "gender": "unisex", "age": "25", "setting": "modern wardrobe, clean background"},
    "รองเท้า":    {"category": "fashion", "gender": "unisex", "age": "25", "setting": "streetwear style, urban background"},
    "ไขควง":      {"category": "tools",   "gender": "male",   "age": "25", "setting": "workshop หรือ garage, tool bench background"},
    "เครื่องมือ":  {"category": "tools",   "gender": "male",   "age": "25", "setting": "workshop background with tool rack"},
    "ของใช้ในบ้าน": {"category": "home",  "gender": "unisex", "age": "25", "setting": "bright living room หรือ kitchen"},
    "เฟอร์นิเจอร์": {"category": "home",  "gender": "unisex", "age": "25", "setting": "bright modern room display"},
}

LIGHTING_MAP = {
    "beauty":     {"lighting": "soft diffused natural window lighting, warm and gentle", "composition": "model centered or slightly off-center, eye-level angle", "background": "clean minimal background, soft pastel tones or white", "color_palette": "warm pastels, pink tones, natural skin tones", "atmosphere": "warm, inviting, feminine, premium"},
    "tools":      {"lighting": "bright functional lighting, cool to neutral white balance", "composition": "model holding tool in working posture, slightly low angle for strength", "background": "workshop wall with tool rack or pegboard", "color_palette": "neutral grays, blue tones, wood workshop tones", "atmosphere": "practical, sturdy, professional"},
    "electronics": {"lighting": "clean bright studio lighting with soft shadows", "composition": "model holding device at chest level, tech-focused framing", "background": "modern minimalist room, blurred ambient background", "color_palette": "cool whites, blue-grays, tech blue accent", "atmosphere": "modern, sleek, innovative"},
    "food":       {"lighting": "warm golden hour lighting, natural and appetizing", "composition": "close up of product and model's hands, upper body shot", "background": "cafe, kitchen counter, blurred warm background", "color_palette": "warm amber, creamy beige, natural green accents", "atmosphere": "cozy, appetizing, lifestyle"},
    "fashion":    {"lighting": "bright studio lighting, fashion editorial style", "composition": "full body or 3/4 shot, dynamic pose", "background": "modern clean background, studio or urban setting", "color_palette": "neutral fashion tones, monochrome or bold accent", "atmosphere": "stylish, trendy, confident"},
    "home":       {"lighting": "bright natural daylight, clean and fresh", "composition": "medium shot showing product in home context", "background": "bright clean living space, lifestyle setting", "color_palette": "clean whites, wood tones, natural greens", "atmosphere": "clean, organized, practical"},
    "other":      {"lighting": "soft natural lighting, clean and professional", "composition": "upper body shot, product visible and in focus", "background": "clean minimal background, lifestyle appropriate", "color_palette": "natural tones, neutral background", "atmosphere": "authentic, professional, relatable"},
}


# ═══════════════════════════════════════════════════════════════════════
# ─── Core: Load UGC Prompt Templates ─────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

UGC_STYLE_FOLDER = {
    "holding": "Holding_Product",
    "review": "UGC_Review",
    "usage": "Product_Usage",
    "talking": "UGC_Review",
}


def load_ugc_templates(style: str) -> dict:
    """Load UGC_prompts/{style}/ template files into a dict.

    Returns: { 'system': str, 'master': str, 'user.template': str, 'negative': str }
    """
    folder_name = UGC_STYLE_FOLDER.get(style, "UGC_Review")
    base = UGC_DIR / folder_name
    result = {}
    for name in ["system", "master", "user.template", "negative"]:
        f = base / f"{name}.prompt"
        if f.exists():
            result[name] = f.read_text(encoding="utf-8")
        else:
            result[name] = ""
    return result


def fill_template(template: str, data: dict) -> str:
    """Replace {key} or {{key}} placeholders with data[key]."""
    def replacer(m):
        key = m.group(1).strip()
        v = data.get(key)
        return str(v) if v is not None else ""
    text = re.sub(r'\{\{(\w+)\}\}', replacer, template)
    text = re.sub(r'\{(\w+)\}', replacer, text)
    return text


def _match_category(product_name: str, description: str = "") -> dict:
    """Match product name keywords to category map (fallback)."""
    combined = (product_name + " " + description).lower()
    best_match = {"category": "other", "gender": "unisex", "age": "20-35", "setting": "clean modern lifestyle setting"}
    for keyword, info in PRODUCT_CATEGORY_MAP.items():
        if keyword.lower() in combined:
            return info
    return best_match


def _get_lighting(category: str) -> dict:
    return LIGHTING_MAP.get(category, LIGHTING_MAP["other"])


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from Mistral response."""
    if not text:
        return None
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            return None
    return None


# ═══════════════════════════════════════════════════════════════════════
# ─── Mistral API Calls ────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

MISTRAL_TEXT_MODEL = "mistral-large-latest"
MISTRAL_VISION_MODEL = "pixtral-large-latest"
MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"


def _get_mistral_key() -> str:
    # Get key directly from os.environ (most reliable)
    key = os.environ.get("MISTRAL_API_KEY", "")
    if key:
        return key
    # Fallback to shared_config
    try:
        key = _MISTRAL_API_KEY_LAZY() if callable(_MISTRAL_API_KEY_LAZY) else _MISTRAL_API_KEY_LAZY
        if key:
            return key
    except Exception:
        pass
    return ""


def _call_mistral_vision(system_prompt: str, user_text: str, image_url: str, temperature: float = 0.3) -> Optional[str]:
    """Call Mistral API with image input (vision via Pixtral)."""
    api_key = _get_mistral_key()
    if not api_key:
        logger.warning("No MISTRAL_API_KEY set in environment")
        return None
    if not image_url:
        return None
    try:
        payload = {
            "model": MISTRAL_VISION_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": image_url}
                ]},
            ],
            "temperature": temperature,
            "max_tokens": 2048,
        }
        resp = requests.post(
            MISTRAL_API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        else:
            logger.error(f"Mistral Vision API error ({resp.status_code}): {resp.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Mistral Vision call failed: {e}")
        return None


def _call_mistral_text(system_prompt: str, user_text: str, temperature: float = 0.3) -> Optional[str]:
    """Call Mistral API with system instruction."""
    api_key = _get_mistral_key()
    if not api_key:
        logger.warning("No MISTRAL_API_KEY set in environment")
        return None
    try:
        payload = {
            "model": MISTRAL_TEXT_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            "temperature": temperature,
            "max_tokens": 2048,
        }
        resp = requests.post(
            MISTRAL_API_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        else:
            logger.error(f"Mistral API error ({resp.status_code}): {resp.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Mistral call failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════
# ─── Product Analysis ─────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

PRODUCT_ANALYSIS_SYSTEM = """คุณคือนักวิเคราะห์สินค้าสำหรับ TikTok Shop
วิเคราะห์สินค้าที่ได้รับ และตอบกลับเป็น JSON ONLY (ไม่มีข้อความอื่น)

กฎสำคัญ:
- target_gender ต้องเลือกเพียง 1 เพศเท่านั้น: "male" หรือ "female" ห้ามใช้ "unisex"
- customer_problem: ระบุปัญหาเฉพาะที่เจาะจง ไม่กว้างเกินไป
- image_description: ภาษาอังกฤษล้วน 100% ห้ามมีภาษาไทยเด็ดขาด

JSON ที่ต้องตอบ:
{
  "category": "beauty/fashion/electronics/food/home/tools/health/other",
  "target_gender": "male/female",
  "target_age": "25",
  "target_audience": "กลุ่มเป้าหมายหลัก เช่น สาววัยทำงานที่มีปัญหาริมฝีปากแห้ง",
  "setting": "สถานที่ถ่ายวิดีโอ เช่น vanity room หรือ bathroom",
  "customer_problem": "ปัญหาที่สินค้านี้แก้ (เจาะจง) เช่น ริมฝีปากแห้งแตก ไม่ฉ่ำ ใต้ตาคล้ำจากนอนดึก",
  "main_benefit": "คุณประโยชน์หลักของสินค้า เช่น ให้ริมฝีปากชุ่มชื้น ฉ่ำวาว ตลอดวัน",
  "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"],
  "image_description": "ENGLISH ONLY — absolutely NO Thai language. Describe the scene for AI image generation. Include: model appearance (Thai woman/man, age 25, glowing skin), pose (holding product naturally / applying on skin), expression (confident smile / happy), setting (vanity room, cafe), lighting (soft natural window light), mood (warm, inviting). Focus on product texture and usage — e.g. for lip products mention 'showing glossy texture on lips' or 'applying on lips showing melted texture'. Do NOT mention product brand name. Example: 'A beautiful Thai woman, 25 years old, glowing skin, happy smile, applying lip product in vanity room, soft natural window lighting, glossy lip texture visible, warm and inviting atmosphere'"
}"""


PRODUCT_VISION_SYSTEM = """You are a product image analyst for TikTok Shop.
Analyze the product image and return JSON ONLY (no other text).

CRITICAL RULES:
- target_gender MUST be "male" or "female" — NEVER "unisex"
- image_description must be 100% English with NO Thai language

JSON format:
{
  "category": "beauty/fashion/electronics/food/home/tools/health/other",
  "product_type": "lipstick/cream/headphones/etc.",
  "target_gender": "male/female",
  "target_age": "25",
  "target_audience": "primary target audience (specific, in Thai for script)",
  "setting": "suggested video setting (English, e.g. vanity room, bathroom, cafe)",
  "colors": ["dominant color 1", "dominant color 2", "dominant color 3"],
  "packaging_style": "luxury/minimal/colorful/modern",
  "estimated_product_size": "small/medium/large",
  "customer_problem": "specific problem this product solves (in Thai for script)",
  "main_benefit": "specific main benefit (in Thai for script)",
  "image_description": "ENGLISH ONLY — absolutely NO Thai. Describe the ideal scene for AI image gen. Include: model appearance (Thai woman/man, age 25, glowing skin), pose (how they hold/use product, e.g. applying on lips showing glossy texture), expression, setting, lighting, mood. Focus on product texture/usage. Example: 'A beautiful Thai woman, 25 years old, glowing skin, happy smile, applying product on lips, vanity room, soft natural window lighting, glossy texture visible, warm atmosphere'
}"""


def analyze_product_image(product_image: str, product_name: str, description: str = "") -> Optional[dict]:
    """Analyze product image via Mistral Pixtral Vision API."""
    if not product_image:
        return None
    user_text = f"Analyze this product image. Product name: {product_name}. Description: {description if description else 'N/A'}"
    raw = _call_mistral_vision(PRODUCT_VISION_SYSTEM, user_text, product_image, temperature=0.3)
    if raw:
        result = _extract_json(raw)
        if result:
            logger.info(f"Vision analysis result: {result.get('category', 'unknown')} / {result.get('product_type', 'unknown')}")
            return result
    return None


def analyze_product(product_name: str, description: str = "", keywords: Optional[List[str]] = None) -> dict:
    """Analyze product via Mistral and return profile dict.
    
    Falls back to category map if Mistral fails.
    """
    keywords = keywords or []
    kw_str = ", ".join(keywords[:5]) if keywords else "ไม่มี"
    
    user_text = f"""ชื่อสินค้า: {product_name}
คำอธิบาย: {description if description else 'ไม่มี'}
Keywords: {kw_str}"""

    raw = _call_mistral_text(PRODUCT_ANALYSIS_SYSTEM, user_text, temperature=0.3)
    mistral_profile = _extract_json(raw) if raw else None

    if not mistral_profile:
        logger.warning("Mistral analysis failed — using category map fallback")
        cinfo = _match_category(product_name, description)
        # Never use "unisex" — pick one specific gender per execution
        raw_gender = cinfo.get("gender", "female")
        if raw_gender == "unisex":
            import random as _rng
            raw_gender = _rng.choice(["female", "male"])
        gender_en = {"female": "woman", "male": "man"}.get(raw_gender, "woman")
        gender_label = {"female": "หญิง", "male": "ชาย"}.get(raw_gender, "หญิง")
        mistral_profile = {
            "category": cinfo["category"],
            "target_gender": raw_gender,
            "target_age": cinfo["age"],
            "target_audience": f"ผู้{gender_label}วัย {cinfo['age']} ปี ที่มีปัญหาเกี่ยวกับ{product_name[:20]}",
            "setting": cinfo["setting"],
            "customer_problem": f"ปัญหาที่{product_name[:30]}นี้ช่วยแก้",
            "main_benefit": f"คุณประโยชน์ของ{product_name[:20]}",
            "hashtags": keywords[:5] if len(keywords) >= 5 else [product_name[:20]],
            "image_description": f"A beautiful Thai {gender_en}, {cinfo['age']} years old, glowing skin, confident smile, in {cinfo['setting']}",
        }
        if isinstance(mistral_profile.get("hashtags"), str):
            mistral_profile["hashtags"] = [h.strip().replace("#", "") for h in mistral_profile["hashtags"].split(",")][:5]
        elif not isinstance(mistral_profile.get("hashtags"), list):
            mistral_profile["hashtags"] = [product_name.replace(" ", "")[:20]]

    # Normalize
    h = mistral_profile.get("hashtags", [])
    if isinstance(h, list):
        h = [x.strip().replace("#", "") for x in h if x.strip()]
        while len(h) < 5:
            h.append(product_name.replace(" ", "").replace("\n", "")[:20])
        mistral_profile["hashtags"] = h[:5]
    else:
        mistral_profile["hashtags"] = [product_name.replace(" ", "")[:20]] * 5

    return mistral_profile


# ═══════════════════════════════════════════════════════════════════════
# ─── Image & Video Prompt Generation ──────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

def build_image_prompt(profile: dict, product_name: str, ugc_style: str = "holding") -> str:
    """Generate image prompt using Mistral's image_description + UGC templates.
    
    The image_description from Mistral Vision analysis describes the ideal scene
    (model appearance, expression, pose, setting, lighting). We combine it with
    UGC style templates that handle composition/camera/quality instructions.
    
    Product name is NOT injected into the prompt — Nano Banana sees the product
    via the reference image (img2img), so text descriptions of the product name
    only cause text rendering artifacts.
    """
    templates = load_ugc_templates(ugc_style)
    style_info = STYLE_MAP.get(ugc_style, STYLE_MAP["holding"])
    category = profile.get("category", "other")
    model_gender = profile.get("target_gender", "unisex")
    model_age = profile.get("target_age", "20-35")
    lighting = _get_lighting(category)
    image_description = profile.get("image_description", "")
    # Support both "female/male/unisex" and "woman/man/person" formats
    gender_en = {
        "female": "woman", "woman": "woman",
        "male": "man", "man": "man",
        "unisex": "person", "person": "person"
    }.get(model_gender, "woman")  # default to woman for beauty products

    # Build scene description from Mistral's image_description (preferred)
    # or fallback to generated description
    if image_description:
        scene_desc = image_description
    else:
        scene_desc = f"Thai {gender_en}, {model_age} years old, pretty face, professional model quality"

    data = {
        "scene_description": scene_desc,
        "model_gender": gender_en,
        "model_age": model_age,  # Use from profile (Mistral suggests "25")
        "style": ugc_style,
        "tone": "casual",
        "composition": lighting["composition"],
        "lighting": lighting["lighting"],
        "atmosphere": lighting["atmosphere"],
        "color_palette": lighting["color_palette"],
        "background": lighting.get("background", "clean minimal background"),
        "model_action": "",  # Removed - use scene_description only
        "camera": style_info["camera"],
        "vibe": style_info["vibe"],
        "keywords": style_info.get("keywords", ""),
        "hashtags": ", ".join(profile.get("hashtags", [])),
    }

    # Build image prompt: use master template only (no user.template to avoid duplication)
    if templates.get("master"):
        image_prompt = fill_template(templates["master"], data)
        negative = templates.get("negative", "")
    else:
        # Fallback hardcode - UGC style
        image_prompt = (
            f"{scene_desc}. "
            f"{style_info['model_action']}. "
            f"{style_info['camera']}, {style_info['vibe']}. "
            f"{lighting['composition']}, {lighting['atmosphere']}, {lighting['color_palette']}. "
            f"The product is clearly in frame. "
            f"{lighting['lighting']}. "
            f"Wearing casual everyday outfit. Authentic UGC style. "
            f"--ar 9:16"
        )
        negative = templates.get("negative", "")
    
    # Clean up section markers if present (for documentation only, not for AI)
    image_prompt = re.sub(r'\[Style & Mood\]\s*', '', image_prompt)
    image_prompt = re.sub(r'\[Subject & Scene\]\s*', '', image_prompt)
    image_prompt = re.sub(r'\[Product Rules\]\s*', '', image_prompt)
    # Clean up double dots and extra spaces
    image_prompt = re.sub(r'\.\.+', '.', image_prompt)
    image_prompt = re.sub(r',\s*,', ',', image_prompt)
    image_prompt = re.sub(r'\s+', ' ', image_prompt)
    image_prompt = image_prompt.strip()

    return image_prompt, negative


def build_video_prompt(profile: dict, product_name: str, ugc_style: str = "holding") -> str:
    """Generate video prompt for Wan 2.7 img2vid."""
    style_info = STYLE_MAP.get(ugc_style, STYLE_MAP["holding"])
    category = profile.get("category", "other")
    model_gender = profile.get("target_gender", "unisex")
    model_setting = profile.get("setting", "clean modern lifestyle setting")
    lighting = _get_lighting(category)
    gender_en = {"female": "woman", "male": "man", "unisex": "person", "woman": "woman", "man": "man"}.get(model_gender, "person")

    video_prompt = (
        f"Thai {gender_en} 25, {style_info['video_motion']}. "
        f"The product is visible in frame. "
        f"Setting: {model_setting}. "
        f"{lighting['lighting']}. {lighting['atmosphere']}. "
        f"9:16 portrait, smooth natural motion"
    )
    return video_prompt


def build_negative_prompt(profile: dict, ugc_style: str = "holding") -> str:
    """Build negative prompt — merge template + defaults."""
    templates = load_ugc_templates(ugc_style)
    default = (
        "no text, no watermark, no logo, no UI overlay, "
        "no blurred face, no distorted hands, no extra fingers, "
        "no manga, no cartoon, no illustration, no 3D render, "
        "no low resolution, no pixelation, no artifacts, "
        "no cluttered background, no messy room"
    )
    tpl_neg = templates.get("negative", "")
    if tpl_neg:
        return f"{tpl_neg}, {default}"
    return default


# ═══════════════════════════════════════════════════════════════════════
# ─── Main Public API (combine everything) ─────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

async def analyze_and_build_prompts(
    product_name: str,
    description: str = "",
    keywords: Optional[List[str]] = None,
    ugc_style: str = "holding",
    product_id: str = "",
    price: float = 0.0,
    product_image: str = "",
    category: str = "",
    product_category: str = "",
) -> dict:
    """
    Full pipeline:
      1. Analyze product via Mistral → product profile
      2. Optionally analyze product image via Mistral Pixtral Vision for enrichment
      3. Build image prompt, video prompt, negative prompt (from UGC_prompts)
      4. Return everything in one dict
    """
    # Step 1: Analyze
    profile = analyze_product(product_name, description, keywords)

    # Step 1b: If product_image provided, run vision analysis to enrich profile
    vision_profile = None
    if product_image:
        try:
            vision_profile = analyze_product_image(product_image, product_name, description)
        except Exception as e:
            logger.warning(f"Vision analysis failed (non-fatal): {e}")

    if vision_profile:
        for key in ["category", "target_gender", "target_age", "target_audience", "setting",
                     "customer_problem", "main_benefit", "image_description"]:
            if key in vision_profile and vision_profile[key]:
                profile[key] = vision_profile[key]
        if "product_type" in vision_profile and vision_profile["product_type"]:
            profile["product_type"] = vision_profile["product_type"]
        if "colors" in vision_profile and vision_profile["colors"]:
            profile["colors"] = vision_profile["colors"]
        if "packaging_style" in vision_profile and vision_profile["packaging_style"]:
            profile["packaging_style"] = vision_profile["packaging_style"]

    # Override with explicit params if provided
    if category:
        profile["category"] = category
    if product_category:
        profile["product_category"] = product_category
    
    # Step 2: Build prompts
    image_prompt, negative_prompt = build_image_prompt(profile, product_name, ugc_style)
    video_prompt = build_video_prompt(profile, product_name, ugc_style)
    if not negative_prompt:
        negative_prompt = build_negative_prompt(profile, ugc_style)
    
    result = {
        "product_id": product_id,
        "analysis": {
            "category": profile.get("category", "other"),
            "target_gender": profile.get("target_gender", "unisex"),
            "target_age": profile.get("target_age", "20-35"),
            "target_audience": profile.get("target_audience", ""),
            "setting": profile.get("setting", ""),
            "customer_problem": profile.get("customer_problem", ""),
            "main_benefit": profile.get("main_benefit", ""),
            "hashtags": profile.get("hashtags", []),
            "image_description": profile.get("image_description", ""),
        },
        "image_prompt": image_prompt,
        "video_prompt": video_prompt,
        "negative_prompt": negative_prompt,
        "metadata": {
            "ugc_style": ugc_style,
            "used_mistral": True,
            "image_analyzed": bool(vision_profile),
        },
        "vision_enrichment": {
            "product_type": profile.get("product_type", ""),
            "colors": profile.get("colors", []),
            "packaging_style": profile.get("packaging_style", ""),
        } if vision_profile else None,
    }
    
    logger.info(f"Prompt built for [{product_name[:30]}]: img={len(image_prompt)}ch, vid={len(video_prompt)}ch")
    return result


# ─── Backward Compat APIs ────────────────────────────────────────────

async def build_prompt(
    product_name: str,
    description: str = "",
    ugc_style: str = "holding",
    gemini_analysis: Optional[dict] = None
) -> dict:
    """Legacy API — calls analyze_and_build_prompts."""
    return await analyze_and_build_prompts(
        product_name=product_name,
        description=description,
        ugc_style=ugc_style,
    )


async def process_image_prompt_request(
    product_name: str,
    description: str = "",
    ugc_style: str = "holding",
) -> dict:
    """Legacy API wrapper."""
    return await analyze_and_build_prompts(
        product_name=product_name,
        description=description,
        ugc_style=ugc_style,
    )
