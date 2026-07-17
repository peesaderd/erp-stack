# ─── Prompt Builder — Main Orchestrator ──────────────────────────
# Thin layer that imports from sub-modules and orchestrates the pipeline
# ═══════════════════════════════════════════════════════════════════════

import os
import json
import logging
import random
import re
from typing import Optional, List, Dict, Any
from pathlib import Path
from copy import deepcopy

import requests

from prompt_templates import (
    STYLE_MAP, PRODUCT_CATEGORY_MAP, UGC_STYLE_FOLDER,
    load_ugc_templates, fill_template, _match_category,
    _get_lighting, _extract_json, BASE_DIR,
)
from gemini_client import (
    _call_gemini, _call_gemini_vision, _get_gemini_key, analyze_product_image,
    PRODUCT_ANALYSIS_SYSTEM,
)
from persona_engine import (
    PERSONA_TEMPLATES, _select_persona, _apply_persona_to_profile,
)

logger = logging.getLogger("prompt-builder-service")

def analyze_product(product_name: str, description: str = "", keywords: Optional[List[str]] = None) -> dict:
    """Analyze product via Mistral and return profile dict.
    
    Falls back to category map if Mistral fails.
    """
    keywords = keywords or []
    kw_str = ", ".join(keywords[:5]) if keywords else "ไม่มี"
    
    user_text = f"""ชื่อสินค้า: {product_name}
คำอธิบาย: {description if description else 'ไม่มี'}
Keywords: {kw_str}"""

    raw = _call_gemini(PRODUCT_ANALYSIS_SYSTEM, user_text, temperature=0.3)
    mistral_profile = _extract_json(raw) if raw else None

    if not mistral_profile:
        logger.warning("Gemini analysis failed — using category map fallback")
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
            "packaging_action": "generic_hold",
            "action_desc": "ถือสินค้าและใช้งานทั่วไป",
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


# ─── Audio Timing & Script Length Validation ──────────────────────────



def build_video_prompt(profile: dict, product_name: str, ugc_style: str = "holding") -> str:
    """Generate video prompt for Wan 2.7 img2vid.
    
    Uses product packaging action from Mistral analysis to create specific,
    product-appropriate video motions instead of generic ones.
    """
    style_info = STYLE_MAP.get(ugc_style, STYLE_MAP["holding"])
    category = profile.get("category", "other")
    model_gender = profile.get("target_gender", "unisex")
    model_setting = profile.get("setting", "clean modern lifestyle setting")
    # Detect packaging action from product name if Mistral didn't return it or returned generic
    packaging_action = profile.get("packaging_action", "")
    name_lower = product_name.lower()
    # Check if Mistral returned a genuine specific action or just generic_hold
    mistral_was_generic = packaging_action in ("", "generic_hold")
    # Run fallback if Mistral was generic AND we detect a specific keyword in product name
    if mistral_was_generic:
        # Check if name has specific keywords that suggest a non-generic action
        if any(w in name_lower for w in ["click", "คลิก", "กดกิ๊ก"]):
            packaging_action = "click_to_release"
        elif any(w in name_lower for w in ["pump", "ปั๊ม"]):
            packaging_action = "pump"
        elif any(w in name_lower for w in ["spray", "สเปรย์", "ฉีด"]):
            packaging_action = "spray"
        elif any(w in name_lower for w in ["roll", "โรล"]):
            packaging_action = "roll"
        elif any(w in name_lower for w in ["glossy", "ฉ่ำ", "วาว", "ชุ่มชื้น"]):
            packaging_action = "glossy_shine"
        elif any(w in name_lower for w in ["blush", "บลัช", "บลัชออน"]):
            packaging_action = "blush_swirl"
        elif any(w in name_lower for w in ["cushion", "คุชชั่น"]):
            packaging_action = "dab_press"
        elif any(w in name_lower for w in ["pen", "ปากกา"]):
            packaging_action = "click_pen"
        elif any(w in name_lower for w in ["cream", "ครีม"]):
            packaging_action = "blend"
        elif any(w in name_lower for w in ["matte", "แมทท์"]):
            packaging_action = "smooth_application"
        else:
            packaging_action = "generic_hold"
    lighting = _get_lighting(category)
    gender_en = {"female": "woman", "male": "man", "unisex": "person", "woman": "woman", "man": "man"}.get(model_gender, "person")

    # Build packaging-specific video motions
    PACKAGING_VIDEO_MOTIONS = {
        "click_to_release": "CLICKING the pen mechanism at bottom to release product, holding product up to show the mechanism working, then applying product on lips",
        "click_pen": "CLICKING the pen to extend product, showing the twisting/clicking mechanism, then applying",
        "pump": "PUMPING the bottle top, showing product dispensing, then applying on skin",
        "spray": "SPRAYING the product onto skin/face, fine mist visible, gentle patting motion after",
        "roll": "ROLLING the ball applicator on skin, circular motion, product gliding smoothly",
        "smooth_application": "applying product with smooth even strokes, blending motion, showing matte finish",
        "glossy_shine": "applying product on lips, pressing lips together to show glossy shine, tilting lips to catch light and reveal wet-looking gloss texture",
        "blend": "pumping/squeezing product onto fingers, blending into skin with circular motion, product absorbing",
        "dab_press": "dabbing cushion puff on face with gentle pressing motion, even coverage",
        "blush_swirl": "swirling brush in blush compact, then gently dusting on cheeks in circular motion, building up color naturally, looking in mirror to check",
        "generic_hold": style_info['video_motion'],
    }
    
    video_motion = PACKAGING_VIDEO_MOTIONS.get(packaging_action, style_info['video_motion'])
    
    video_prompt = (
        f"Thai {gender_en} 25, {video_motion}. "
        f"The product is visible in frame throughout. "
        f"Setting: {model_setting}. "
        f"{lighting['lighting']}. {lighting['atmosphere']}. "
        f"9:16 portrait, smooth natural motion, no text, no watermark"
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
      1. Analyze product via Gemini → product profile
      2. Optionally analyze product image via Gemini Vision for enrichment
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
    
    # Step 2b: Inject random persona for diversity
    persona = _select_persona(profile.get("category", category or "other"), product_name)
    profile = _apply_persona_to_profile(profile, persona)
    logger.info(f"Persona: {persona.get('vibe', '')} | Env: {persona.get('environment', '')}")

    # Step 3: Build prompts (with persona-injected profile)
    image_prompt, negative_prompt = build_image_prompt(profile, product_name, ugc_style)
    video_prompt = build_video_prompt(profile, product_name, ugc_style)
    if not negative_prompt:
        negative_prompt = build_negative_prompt(profile, ugc_style)
    
    # Step 4: Validate script timing
    category_key = profile.get("category", category or "beauty")
    timing_validation = _build_timing_validated_script(product_name, category_key)
    
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
        "timing_validation": {
            "segments": {
                "hook": timing_validation["hook"],
                "value": timing_validation["value"],
                "cta": timing_validation["cta"],
            },
            "tts_speed": timing_validation["tts_speed"],
            "product_short_for_tts": timing_validation["product_short_for_tts"],
            "all_segments_fit": timing_validation["all_segments_fit"],
            "total_duration": 8,
        },
        "scripts": {
            "full_script": timing_validation["full_script"],
            "tts_script": timing_validation["tts_script"],
            "breakdown": {
                "hook": timing_validation["hook"]["text"],
                "value": timing_validation["value"]["text"],
                "cta": timing_validation["cta"]["text"],
            }
        },
        "image_prompt": image_prompt,
        "video_prompt": video_prompt,
        "negative_prompt": negative_prompt,
        "metadata": {
            "ugc_style": ugc_style,
            "used_gemini": True,
            "image_analyzed": bool(vision_profile),
            "persona": {
                "vibe": profile.get("persona_vibe", persona.get("vibe", "")),
                "environment": profile.get("setting", persona.get("environment", "")),
                "lighting": profile.get("persona_lighting", persona.get("lighting_variation", "")),
                "motion_speed": profile.get("persona_motion", persona.get("motion_speed", "")),
            }
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


def _estimate_speech_duration(text: str) -> float:
    """
    Estimate speaking duration for Thai + mixed Thai/English text.
    
    Thai: ~15 chars/sec at normal conversational pace
    English: ~8 chars/sec in Thai context (shorter words, brand names)
    Mixed: weighted average
    
    These are calibrated for Google TTS Thai female voice at 1.0x speed.
    """
    if not text or not text.strip():
        return 0
    text_clean = text.replace(' ', '')
    if not text_clean:
        return 0
    # Separate Thai and non-Thai characters
    thai_chars = sum(1 for c in text if '\u0E00' <= c <= '\u0E7F')
    non_thai_chars = len(text_clean) - thai_chars
    if non_thai_chars < 0:
        non_thai_chars = 0
    
    # Thai at natural conversational pace
    thai_sec = thai_chars / 18.0  # ~18 chars/sec (native Thai speakers are fast)
    non_thai_sec = non_thai_chars / 9.0  # ~9 chars/sec for English brand names in Thai context
    
    # Add a small buffer for pauses/gaps between language switches
    switches = 0
    if thai_chars > 0 and non_thai_chars > 0:
        switches = 1  # one natural pause between language change
    
    return thai_sec + non_thai_sec + (switches * 0.1)




def _build_timing_validated_script(product_name: str, category: str = "beauty") -> dict:
    """
    Build script segments with timing validation.
    Auto-abbreviates product name if it would cause TTS to rush.
    
    Returns {
        "hook": {"text": ..., "timing": "0-2", "duration_sec": 2, "ok": bool},
        "value": {"text": ..., "timing": "2-6", "duration_sec": 4, "ok": bool},
        "cta": {"text": ..., "timing": "6-8", "duration_sec": 2, "ok": bool},
        "tts_speed": 1.0,  # suggested speed multiplier
        "full_script": ...,
        "tts_script": ...,  # abbreviated version for TTS
    }
    """
    # Full product name — check if it fits
    product_short = product_name
    full_name_chars = len(product_name)
    
    # If product name is long, create abbreviated version for TTS
    # Strategy: keep brand name + key category word, drop descriptive adjectives
    if full_name_chars > 25:
        parts = product_name.split()
        # Words that are brand/essential keywords worth keeping
        keep_keywords = {"la", "glace", "lip", "click", "pen", "pump", "spray", "cream", "mask", "serum"}
        # Words that are fluff/description — drop for TTS brevity
        drop_keywords = {"melted", "sundae", "matte", "glossy", "shine", "moisture", "hydra", "glow", 
                       "smooth", "natural", "fresh", "clear", "bright", "perfect", "daily", "extra",
                       "ultra", "pro", "max", "new", "premium", "luxury", "blink", "blush"}
        kept = []
        for p in parts:
            p_lower = p.lower().strip("(),.!")
            if p_lower in keep_keywords:
                kept.append(p)
            elif p_lower not in drop_keywords and len(p) > 3:
                # Keep unknown words that are short brand-like (e.g. SADOER, OUKEYA)
                if p.isupper() and len(p) <= 8:
                    kept.append(p)
                elif not p.isupper():
                    kept.append(p)  # Keep Thai text
        candidate = ' '.join(kept) if kept else product_name[:30]
        if len(candidate) <= 35:
            product_short = candidate
        else:
            # If still too long, just take first 3 relevant parts
            product_short = ' '.join(kept[:3]) if len(kept) >= 3 else product_name[:30]
    
    # Ensure we never use empty or too-short name
    if len(product_short) < 5:
        product_short = product_name[:30]
    
    # Build script segments — category-aware
    if "blush" in category.lower() or "cheek" in category.lower():
        hook_text = f"หน้าแบน ไม่มีมิติ แต่งหน้ายังไงก็ไม่ปัง?"
        value_text = f"{product_short} บลัชออน 2 เฉดในเดียว เพิ่มความสดใส วิ้งเบาๆ เป็นธรรมชาติ"
    elif "lip" in category.lower() or "lipstick" in category.lower() or "lip gloss" in category.lower():
        hook_text = f"ใครปากแห้ง ปากหมองคล้ำบ้าง?"
        value_text = f"{product_short} ให้ปากฉ่ำวาว ไม่เหนอะ ติดทนตลอดวัน"
    elif "mask" in category.lower() or "facial" in category.lower():
        hook_text = f"ผิวแห้ง หมองคล้ำ ไม่สดใส ต้องลอง!"
        value_text = f"{product_short} บำรุงล้ำลึก ให้ผิวชุ่มชื้น กระจ่างใส"
    elif "serum" in category.lower() or "moisturizer" in category.lower():
        hook_text = f"ผิวพังจากมลภาวะ อายุที่เพิ่มขึ้น หมดกังวล!"
        value_text = f"{product_short} บำรุงเข้มข้น ซึมไว ไม่เหนอะหนะ"
    elif "concealer" in category.lower() or "corrector" in category.lower():
        hook_text = f"ใต้ตาดำคล้ำ นอนดึกทุกวัน หมดปัญหา!"
        value_text = f"{product_short} ปกปิดเนียนกริบ ไม่ตกร่อง ไม่เป็นคราบ"
    else:
        hook_text = f"ต้องลอง! สินค้าดีบอกต่อ"
        value_text = f"{product_short} คุณภาพเยี่ยม ใช้งานง่าย เห็นผลจริง"
    cta_text = f"กดลิงก์หน้าโปรไฟล์เลย รับส่วนลดทันที"
    
    segments = [
        {"key": "hook", "text": hook_text, "duration_sec": 2, "timing": "0-2"},
        {"key": "value", "text": value_text, "duration_sec": 4, "timing": "2-6"},
        {"key": "cta", "text": cta_text, "duration_sec": 2, "timing": "6-8"},
    ]
    
    total_ok = True
    max_speed_needed = 1.0
    for seg in segments:
        estimated = _estimate_speech_duration(seg["text"])
        seg["estimated_sec"] = round(estimated, 1)
        seg["ok"] = estimated <= seg["duration_sec"]
        if not seg["ok"]:
            total_ok = False
            # Calculate needed speedup
            needed = estimated / seg["duration_sec"]
            if needed > max_speed_needed:
                max_speed_needed = needed
    
    tts_speed = min(max_speed_needed, 1.3)  # Max 1.3x speed
    if tts_speed < 1.0:
        tts_speed = 1.0
    
    full = " ".join(s["text"] for s in segments)
    
    return {
        "hook": segments[0],
        "value": segments[1],
        "cta": segments[2],
        "tts_speed": tts_speed,
        "full_script": full,
        "tts_script": full,
        "product_short_for_tts": product_short,
        "all_segments_fit": total_ok,
    }




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
      1. Analyze product via Gemini → product profile
      2. Optionally analyze product image via Gemini Vision for enrichment
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
    
    # Step 2b: Inject random persona for diversity
    persona = _select_persona(profile.get("category", category or "other"), product_name)
    profile = _apply_persona_to_profile(profile, persona)
    logger.info(f"Persona: {persona.get('vibe', '')} | Env: {persona.get('environment', '')}")

    # Step 3: Build prompts (with persona-injected profile)
    image_prompt, negative_prompt = build_image_prompt(profile, product_name, ugc_style)
    video_prompt = build_video_prompt(profile, product_name, ugc_style)
    if not negative_prompt:
        negative_prompt = build_negative_prompt(profile, ugc_style)
    
    # Step 4: Validate script timing
    category_key = profile.get("category", category or "beauty")
    timing_validation = _build_timing_validated_script(product_name, category_key)
    
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
        "timing_validation": {
            "segments": {
                "hook": timing_validation["hook"],
                "value": timing_validation["value"],
                "cta": timing_validation["cta"],
            },
            "tts_speed": timing_validation["tts_speed"],
            "product_short_for_tts": timing_validation["product_short_for_tts"],
            "all_segments_fit": timing_validation["all_segments_fit"],
            "total_duration": 8,
        },
        "scripts": {
            "full_script": timing_validation["full_script"],
            "tts_script": timing_validation["tts_script"],
            "breakdown": {
                "hook": timing_validation["hook"]["text"],
                "value": timing_validation["value"]["text"],
                "cta": timing_validation["cta"]["text"],
            }
        },
        "image_prompt": image_prompt,
        "video_prompt": video_prompt,
        "negative_prompt": negative_prompt,
        "metadata": {
            "ugc_style": ugc_style,
            "used_gemini": True,
            "image_analyzed": bool(vision_profile),
            "persona": {
                "vibe": profile.get("persona_vibe", persona.get("vibe", "")),
                "environment": profile.get("setting", persona.get("environment", "")),
                "lighting": profile.get("persona_lighting", persona.get("lighting_variation", "")),
                "motion_speed": profile.get("persona_motion", persona.get("motion_speed", "")),
            }
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


