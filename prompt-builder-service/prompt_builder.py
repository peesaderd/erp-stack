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
    STYLE_MAP, UGC_STYLE_FOLDER,
    load_ugc_templates, fill_template, _extract_json, BASE_DIR,
)
from gemini_client import (
    _call_gemini, _call_gemini_vision, _get_gemini_key, analyze_product_image,
    PRODUCT_ANALYSIS_SYSTEM,
)
from persona_engine import (
    PERSONA_TEMPLATES, _select_persona, _apply_persona_to_profile,
)
from router_agent import router_decide

logger = logging.getLogger("prompt-builder-service")


def analyze_product(product_name: str, description: str = "", keywords: Optional[List[str]] = None) -> dict:
    """Analyze product via Gemini and return profile dict.
    
    Uses Router Agent for strategic context (recipe, style, persona),
    and Gemini for visual/profile details.
    Falls back to simple default if Gemini fails.
    """
    keywords = keywords or []
    kw_str = ", ".join(keywords[:5]) if keywords else "ไม่มี"
    
    # Get Router Agent config (strategy decision)
    router_config = router_decide(
        product_name=product_name,
        description=description,
        keywords=keywords,
    )
    
    # Get product profile from Gemini analysis
    user_text = f"""ชื่อสินค้า: {product_name}
คำอธิบาย: {description if description else 'ไม่มี'}
Keywords: {kw_str}"""

    raw = _call_gemini(PRODUCT_ANALYSIS_SYSTEM, user_text, temperature=0.3)
    gemini_profile = _extract_json(raw) if raw else None

    if not gemini_profile:
        logger.warning("Gemini analysis failed — using default profile with Router context")
        gender_en = "woman"
        profile = {
            "category": "other",
            "target_gender": "female",
            "target_age": "25-35",
            "target_audience": f"คนที่กำลังมองหา{product_name[:20]}",
            "setting": "clean modern lifestyle setting",
            "customer_problem": f"ปัญหาที่{product_name[:30]}นี้ช่วยแก้",
            "main_benefit": f"คุณประโยชน์ของ{product_name[:20]}",
            "packaging_action": "generic_hold",
            "action_desc": "ถือสินค้าและใช้งานทั่วไป",
            "hashtags": keywords[:5] if len(keywords) >= 5 else [product_name.replace(" ", "")[:20]] * 5,
            "image_description": f"An ethnic Thai {gender_en}, 25-35 years old, porcelain white glowing skin, monolid eyes, Southeast Asian features, holding a product at chest level, in a clean modern setting",
        }
    else:
        profile = gemini_profile
        # Normalize hashtags
        h = profile.get("hashtags", [])
        if isinstance(h, str):
            h = [x.strip().replace("#", "") for x in h.split(",")]
        elif isinstance(h, list):
            h = [x.strip().replace("#", "") for x in h if x.strip()]
        while len(h) < 5:
            h.append(product_name.replace(" ", "").replace("\n", "")[:20])
        profile["hashtags"] = h[:5]

    # Merge Router Agent insights into profile
    profile["router_config"] = {
        "recipe_type": router_config.get("recipe_type", "pas"),
        "duration": router_config.get("duration", "8s"),
        "visual_style": router_config.get("visual_style", "usage"),
        "persona": router_config.get("persona", "gen_z_trendy"),
        "reason": router_config.get("reason", ""),
    }
    profile["scenes"] = router_config.get("scenes", [])

    return profile


# ═══════════════════════════════════════════════════════════════════════
# ─── Image & Video Prompt Generation ──────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════


def build_image_prompt(profile: dict, product_name: str, ugc_style: str = "holding") -> str:
    """Generate image prompt — style-driven, category-modulated.
    
    PRINCIPLE:
    - ugc_style controls what the person DOES in the scene (holding, reviewing, using)
    - category controls WHERE/context (home, beauty environment modifiers)
    - Person is ALWAYS in the scene
    - Each style produces distinctly different output
    """
    templates = load_ugc_templates(ugc_style)
    style_info = STYLE_MAP.get(ugc_style, STYLE_MAP["holding"])
    model_gender = profile.get("target_gender", "female")
    model_age = profile.get("_normalized_age") or _normalize_age(profile.get("target_age", "20-35"))
    category = profile.get("category", "other")

    gender_en = {
        "female": "woman", "woman": "woman",
        "male": "man", "man": "man",
        "unisex": "person", "person": "person"
    }.get(model_gender, "woman")
    
    persona_clothing = profile.get("persona_clothing", "")
    persona_hair = profile.get("persona_hair", "")
    env_context = profile.get("env_context", "")
    product_appearance = profile.get("product_appearance", "")
    image_description = profile.get("image_description", "")
    
    clothing_str = f", wearing {persona_clothing}" if persona_clothing else ""
    hair_str = f", {persona_hair}" if persona_hair else ""
    
    # ── Clean product_appearance ──
    pa_clean = product_appearance
    if pa_clean:
        pa_clean = re.sub(r'^(The\s+)?product\s+(is\s+)?', '', pa_clean, flags=re.IGNORECASE).strip()
        pa_clean = pa_clean[0].lower() + pa_clean[1:] if pa_clean else ""
        pa_clean = re.sub(r'^(a|an)\s+', '', pa_clean, flags=re.IGNORECASE).strip()
        article = "an" if pa_clean[:1].lower() in "aeiou" else "a"
    
    env_str = (env_context or "a modern lifestyle setting")[:120]
    thai_base = f"An ethnic Thai {gender_en}, {model_age} years old, porcelain white glowing skin, monolid eyes, Southeast Asian ethnic Thai features, small nose bridge"
    
    # ── Style-driven scene (ugc_style is PRIMARY) ─────────────────
    if ugc_style in ("usage", "product_usage"):
        # Try Gemini for natural product usage scene
        gemini_image, _ = _gemini_generate_prompts(
            product_name=product_name,
            product_appearance=pa_clean or product_name,
            features=profile.get("features", ""),
            env_context=env_context,
            category=category,
            model_age=model_age,
            model_gender=gender_en,
            clothing=clothing_str.lstrip(", wearing "),
            hair=hair_str.lstrip(", "),
            ugc_style=ugc_style,
        )
        if gemini_image:
            scene_desc = gemini_image
        elif pa_clean:
            prod_str = f"{article} {pa_clean[:200]}"
            scene_desc = (
                f"{env_str}. {thai_base}{clothing_str}{hair_str} beside {prod_str or product_name} — "
                f"ingredients nearby on counter, about to use the product. "
                f"Ready to blend, product and person in frame, casual preparation moment."
            )
        else:
            scene_desc = (
                f"{thai_base}{clothing_str}{hair_str} beside {product_name} — "
                f"ingredients and product on counter, about to use it. "
                f"{env_str}."
            )
        
    elif ugc_style == "review":
        # Person holding product + looking at camera, review-style
        if pa_clean:
            prod_str = f"{article} {pa_clean[:200]}"
            scene_desc = (
                f"{env_str}. {thai_base}{clothing_str}{hair_str} holds {prod_str or product_name} in hand, "
                f"looking directly at camera with a friendly reviewing expression. "
                f"Product clearly visible and in focus. Lifestyle setting, natural window light."
            )
        else:
            scene_desc = (
                f"{thai_base}{clothing_str}{hair_str} holds {product_name}, "
                f"looking at camera with a reviewing expression. "
                f"Product visible in hand, natural lighting, {env_str}."
            )
        
    elif ugc_style in ("tabletop", "tabletop_demo"):
        # Product on table, person's hands demonstrating
        if pa_clean:
            prod_str = f"{article} {pa_clean[:200]}"
            scene_desc = (
                f"{env_str}. On a table sits {prod_str}. "
                f"{thai_base}{clothing_str}{hair_str} gestures toward it, "
                f"hands visible demonstrating features. Product centered on tabletop, person nearby."
            )
        else:
            scene_desc = (
                f"{thai_base}{clothing_str}{hair_str} standing by a table with {product_name}. "
                f"Hands gesturing toward product, tabletop demo style, {env_str}."
            )
        
    elif ugc_style in ("talking", "talking_head"):
        # Head/shoulders framing, talking about product
        if pa_clean:
            prod_str = f"{article} {pa_clean[:200]}"
        else:
            prod_str = product_name
        scene_desc = (
            f"{thai_base}{clothing_str}{hair_str} facing camera, head and shoulders framing, "
            f"speaking conversationally about the product. "
            f"{prod_str} visible resting nearby in frame. "
            f"{env_str}. Soft natural lighting, shallow depth of field."
        )
        
    elif ugc_style == "unbox":
        # Opening package
        scene_desc = (
            f"{thai_base}{clothing_str}{hair_str} unboxing/unpacking {product_name} — "
            f"hands removing product from packaging, opening the box. "
            f"Excited expression, product partially visible. {env_str}."
        )
        
    else:
        # Default: holding — person holds product, shows to camera
        if pa_clean:
            prod_str = f"{article} {pa_clean[:200]}"
            scene_desc = (
                f"{env_str}. {thai_base}{clothing_str}{hair_str} holds {prod_str or product_name} in both hands, "
                f"showing product clearly to camera. Warm natural window lighting. "
                f"Product centered in frame at chest level."
            )
        else:
            scene_desc = (
                f"{thai_base}{clothing_str}{hair_str} holds {product_name} in hands, "
                f"showing the product to camera. Natural lighting, {env_str}."
            )
    
    # ── Category modifiers (SECONDARY) ───────────────────────────────
    # No hardcoded beauty restrictions — Gemini handles appropriateness
    
    # ── Build final prompt ──
    data = {
        "scene_description": scene_desc,
        "model_gender": gender_en,
        "model_age": model_age,
        "style": ugc_style,
        "tone": "casual",
        "composition": "natural composition, eye-level angle",
        "lighting": "soft natural lighting",
        "atmosphere": "warm, inviting, authentic",
        "color_palette": "natural tones, neutral background",
        "background": "clean minimal background",
        "model_action": style_info.get("model_action", "",),
        "camera": style_info.get("camera", ""),
        "vibe": style_info.get("vibe", ""),
        "keywords": style_info.get("keywords", ""),
        "hashtags": ", ".join(profile.get("hashtags", [])),
    }
    if templates.get("master"):
        image_prompt = fill_template(templates["master"], data)
        negative = templates.get("negative", "")
    else:
        image_prompt = (
            f"{scene_desc}. "
            f"{style_info.get('model_action', '')}. "
            f"{style_info.get('camera', '')}, {style_info.get('vibe', '')}. "
            f"natural composition, warm inviting atmosphere. "
            f"The product is clearly in frame. "
            f"soft natural lighting. "
            f"--ar 9:16"
        )
        negative = templates.get("negative", "")
    
    # Clean up
    image_prompt = re.sub(r'\[.*?\]\s*', '', image_prompt)
    image_prompt = re.sub(r'\.\.+', '.', image_prompt)
    image_prompt = re.sub(r',\s*,', ',', image_prompt)
    image_prompt = re.sub(r'\s+', ' ', image_prompt)
    image_prompt = image_prompt.strip()

    return image_prompt, negative


def img_desc_sentences(text: str) -> list:
    """Split image_description into sentences."""
    return [s.strip() for s in text.split(".") if s.strip()]


def build_video_prompt(profile: dict, product_name: str, ugc_style: str = "holding") -> str:
    """Generate video prompt for Wan 2.7 img2vid.
    Style-driven, category-modulated.
    
    PRINCIPLE:
    - ugc_style controls person action (holding, reviewing, using)
    - category controls environment/context detail only
    - Person is ALWAYS in the scene
    """
    style_info = STYLE_MAP.get(ugc_style, STYLE_MAP["holding"])
    model_gender = profile.get("target_gender", "female")
    model_setting = profile.get("setting", "clean modern lifestyle setting")
    category = profile.get("category", "other")

    gender_en = {"female": "woman", "male": "man", "unisex": "person"}.get(model_gender, "person")
    persona_clothing = profile.get("persona_clothing", "")
    persona_hair = profile.get("persona_hair", "")
    clothing_str = f", wearing {persona_clothing}" if persona_clothing else ""
    hair_str = f", {persona_hair}" if persona_hair else ""
    model_age = profile.get("_normalized_age") or _normalize_age(profile.get("target_age", "20-35"))
    
    # ── Product description (common) ──
    env_context = profile.get("env_context", "a modern space")
    product_appearance = profile.get("product_appearance", "")
    pa_clean = product_appearance
    if pa_clean:
        pa_clean = re.sub(r'^(The\s+)?product\s+(is\s+)?', '', pa_clean, flags=re.IGNORECASE).strip()
        pa_clean = pa_clean[0].lower() + pa_clean[1:] if pa_clean else ""
        pa_clean = re.sub(r'^(a|an)\s+', '', pa_clean, flags=re.IGNORECASE).strip()
        article = "an" if pa_clean[:1].lower() in "aeiou" else "a"
        prod_desc_vid = f"{article} {pa_clean[:200]}"
    else:
        prod_desc_vid = product_name
    
    model_intro = f"Ethnic Thai {gender_en} {model_age} years old, porcelain white glowing skin, monolid eyes, Southeast Asian ethnic Thai features{clothing_str}{hair_str}"
    
    # ── Style-driven video_motion (ugc_style is PRIMARY) ──────────
    if ugc_style in ("usage", "product_usage"):
        # Try Gemini for natural product usage description
        gemini_image, gemini_video = _gemini_generate_prompts(
            product_name=product_name,
            product_appearance=pa_clean or product_name,
            features=profile.get("features", ""),
            env_context=env_context,
            category=category,
            model_age=model_age,
            model_gender=gender_en,
            clothing=clothing_str.lstrip(", wearing "),
            hair=hair_str.lstrip(", "),
            ugc_style=ugc_style,
        )
        if gemini_video:
            action = gemini_video
        else:
            # Fallback: simple generic prompt — no is_* branches
            action = (
                f"{model_intro} in {env_context} with {prod_desc_vid or product_name}. "
                f"She naturally demonstrates how to use the product — "
                f"the key function is shown. "
                f"Product features are visible as she uses it. "
                f"Natural product usage demonstration"
            )
    elif ugc_style == "review":
        # Person holding product + looking at camera, review-style
        action = (
            f"{model_intro} holds {prod_desc_vid or product_name} in hand, "
            f"looking directly at camera with slight head tilt, casual reviewing pose. "
            f"Slow gentle movement, showing product from slightly different angles. "
            f"Lifestyle setting, product visible. "
            f"Person speaking casually, product in hand"
        )
    elif ugc_style in ("tabletop", "tabletop_demo"):
        # Product on table, person's hands visible
        action = (
            f"{prod_desc_vid or product_name} sits on table. "
            f"{model_intro} nearby points at it and gestures with hands. "
            f"Camera pans slowly showing product on tabletop, hands visible in frame. "
            f"Product-centered demonstration, person gesturing"
        )
    elif ugc_style in ("talking", "talking_head"):
        # Head/shoulders, talking about product
        action = (
            f"{model_intro} in medium close-up, facing camera, "
            f"speaking naturally about {prod_desc_vid or product_name}. "
            f"Gentle head movements, conversational tone. "
            f"Product resting nearby, slightly blurred in foreground. "
            f"Smooth natural motion, person talking to camera"
        )
    elif ugc_style == "unbox":
        action = (
            f"{model_intro} unboxing {prod_desc_vid or product_name}, "
            f"hands opening packaging, lifting product out. "
            f"Slight excitement in movement. "
            f"Product emerging from packaging, unboxing reveal motion"
        )
    else:
        # Default: holding — show product, gentle rotation
        action = (
            f"{model_intro} gently holding {prod_desc_vid or product_name} in both hands, "
            f"showing product to camera with slight slow rotation. "
            f"Warm natural motion, product centered. "
            f"Person holding product gently at chest level"
        )
    
    # ── Category-specific restrictions (SECONDARY) ──
    video_prompt = action
    # No more hardcoded beauty restrictions — Gemini handles appropriateness
    
    video_prompt += (
        f" Setting: {model_setting}. "
        f"{env_context}. "
        f"soft natural lighting, warm atmosphere. "
        f"9:16 portrait, smooth natural motion"
    )
    
    video_prompt = re.sub(r'\s+', ' ', video_prompt).strip()
    return video_prompt


def _normalize_age(raw_age) -> int:
    """Normalize age from profile to 18-25 range with real randomness."""
    import random
    try:
        if isinstance(raw_age, (int, float)):
            age = int(raw_age)
        else:
            # Handle "25-35" or "20-35" range strings
            parts = str(raw_age).replace(" ", "").split("-")
            nums = [int(p) for p in parts if p.isdigit()]
            age = nums[0] if nums else 22
    except (ValueError, TypeError):
        age = 22
    upper = min(25, age)
    lower = max(18, upper - 3)
    if lower > upper:
        return 18
    return random.randint(lower, upper)


def build_negative_prompt(profile: dict, ugc_style: str = "holding") -> str:
    """Build negative prompt — just the defaults (text/watermark/hands/distortion).
    Caller merges with template negatives."""
    return (
        "no text, no watermark, no logo, no UI overlay, "
        "no blurred face, no distorted hands, no extra fingers, "
        "no manga, no cartoon, no illustration, no 3D render, "
        "no low resolution, no pixelation, no artifacts, "
        "no cluttered background, no messy room"
    )


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
      2. Run Router Agent to decide recipe/style/duration/persona
      3. Optionally analyze product image via Gemini Vision for enrichment
      4. Build image prompt, video prompt, negative prompt
      5. Return everything in one dict
    """
    # Step 1: Analyze (includes Router Agent call)
    profile = analyze_product(product_name, description, keywords)

    # Router Agent insights are purely advisory — NEVER override user's ugc_style choice
    # The user's ugc_style selection is always authoritative
    router_config = profile.get("router_config", {})

    # Step 2: If product_image provided, run vision analysis to enrich profile
    vision_profile = None
    if product_image:
        try:
            vision_profile = analyze_product_image(product_image, product_name, description)
        except Exception as e:
            logger.warning(f"Vision analysis failed (non-fatal): {e}")

    if vision_profile:
        for key in ["category", "target_gender", "target_age", "target_audience", "setting",
                     "customer_problem", "main_benefit", "env_context", "product_appearance",
                     "features"]:
            if key in vision_profile and vision_profile[key]:
                profile[key] = vision_profile[key]
        # product_type from vision overwrites text analysis
        if "product_type" in vision_profile and vision_profile["product_type"]:
            profile["product_type"] = vision_profile["product_type"]
        if "colors" in vision_profile and vision_profile["colors"]:
            profile["colors"] = vision_profile["colors"]

    # Fallback: ensure target_gender is specific for image gen
    if profile.get("target_gender", "") in ("unisex", "", None):
        profile["target_gender"] = "female"

    # Override with explicit params if provided
    if category:
        profile["category"] = category
    if product_category:
        profile["product_category"] = product_category
    
    # Step 3: Inject persona for diversity
    persona = _select_persona(profile.get("category", "other"), product_name)
    profile = _apply_persona_to_profile(profile, persona)
    logger.info(f"Persona: {persona.get('vibe', '')} | Env: {persona.get('environment', '')}")

    # Sync age — normalize once so image + video prompt ages match
    profile["_normalized_age"] = _normalize_age(profile.get("target_age", "20-35"))

    # Step 4: Build prompts
    image_prompt, neg_from_template = build_image_prompt(profile, product_name, ugc_style)
    video_prompt = build_video_prompt(profile, product_name, ugc_style)
    # Merge: template neg (text/watermark) + default neg (fingers/hands/distortion)
    default_neg = build_negative_prompt(profile, ugc_style)
    if neg_from_template:
        negative_prompt = f"{neg_from_template}, {default_neg}"
    else:
        negative_prompt = default_neg
    
    # Step 5: Validate script timing
    timing_validation = _build_timing_validated_script(product_name, profile.get("category", "other"), profile)
    
    result = {
        "product_id": product_id,
        "router_config": router_config,
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
            "env_context": profile.get("env_context", ""),
            "product_appearance": profile.get("product_appearance", ""),
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
            "route_reason": router_config.get("reason", ""),
            "persona": {
                "vibe": profile.get("persona_vibe", persona.get("vibe", "")),
                "environment": profile.get("setting", persona.get("environment", "")),
                "lighting": profile.get("persona_lighting", persona.get("lighting_variation", "")),
                "motion_speed": profile.get("persona_motion", persona.get("motion_speed", "")),
                "clothing": persona.get("clothing", ""),
                "hair": persona.get("hair_style", ""),
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
    """Estimate speaking duration for Thai + mixed text."""
    if not text or not text.strip():
        return 0
    text_clean = text.replace(' ', '')
    if not text_clean:
        return 0
    thai_chars = sum(1 for c in text if '\u0E00' <= c <= '\u0E7F')
    non_thai_chars = len(text_clean) - thai_chars
    if non_thai_chars < 0:
        non_thai_chars = 0
    thai_sec = thai_chars / 18.0
    non_thai_sec = non_thai_chars / 9.0
    switches = 1 if (thai_chars > 0 and non_thai_chars > 0) else 0
    return thai_sec + non_thai_sec + (switches * 0.1)


def _build_timing_validated_script(product_name: str, category: str = "beauty", profile: dict = None) -> dict:
    """Build script segments with timing validation.
    Uses customer_problem + main_benefit from Gemini analysis when available.
    Gender-aware: female register (คะ/ค่ะ) for female target_gender.
    """
    product_short = product_name
    full_name_chars = len(product_name)
    
    if full_name_chars > 25:
        parts = product_name.split()
        keep_keywords = {"la", "glace", "lip", "click", "pen", "pump", "spray", "cream", "mask", "serum"}
        drop_keywords = {"melted", "sundae", "matte", "glossy", "shine", "moisture", "hydra", "glow",
                       "smooth", "natural", "fresh", "clear", "bright", "perfect", "daily", "extra",
                       "ultra", "pro", "max", "new", "premium", "luxury", "blink", "blush"}
        kept = []
        for p in parts:
            p_lower = p.lower().strip("(),.!")
            if p_lower in keep_keywords:
                kept.append(p)
            elif p_lower not in drop_keywords and len(p) > 3:
                if p.isupper() and len(p) <= 8:
                    kept.append(p)
                elif not p.isupper():
                    kept.append(p)
        candidate = ' '.join(kept) if kept else product_name[:30]
        product_short = candidate if len(candidate) <= 35 else ' '.join(kept[:3]) if len(kept) >= 3 else product_name[:30]
    
    if len(product_short) < 5:
        product_short = product_name[:30]
    
    # Gender-aware Thai register
    target_gender = profile.get("target_gender", "female") if profile else "female"
    is_female = target_gender in ("female", "woman")
    reg_hook = "คะ" if is_female else "ครับ"
    reg_val = "ค่ะ" if is_female else "ครับ"
    
    # Use customer_problem + main_benefit from Gemini analysis when available
    customer_problem = profile.get("customer_problem", "") if profile else ""
    main_benefit = profile.get("main_benefit", "") if profile else ""
    
    if customer_problem and main_benefit and len(customer_problem) > 5:
        # Use Gemini-generated problem/benefit (already includes register)
        hook_text = customer_problem
        value_text = f"{product_short} {main_benefit}"
    elif category in ("home", "electronics", "tools"):
        hook_text = f"ต้องเดินคลำทางในที่มืดใช่ไหม{reg_hook}"
        value_text = f"{product_short} ให้แสงสว่างทันที ช่วยเพิ่มความสะดวกและปลอดภัย{reg_val}"
    elif "blush" in category.lower() or "cheek" in category.lower():
        hook_text = f"หน้าแบน ไม่มีมิติ แต่งหน้ายังไงก็ไม่ปัง{reg_hook}"
        value_text = f"{product_short} บลัชออน เพิ่มความสดใส วิ้งเบาๆ เป็นธรรมชาติ{reg_val}"
    elif "lip" in category.lower():
        hook_text = f"ใครปากแห้ง ปากหมองคล้ำบ้าง{reg_hook}"
        value_text = f"{product_short} ให้ปากฉ่ำวาว ไม่เหนอะ ติดทนตลอดวัน{reg_val}"
    elif "mask" in category.lower() or "facial" in category.lower():
        hook_text = f"ผิวแห้ง หมองคล้ำ ไม่สดใส ต้องลอง{reg_hook}"
        value_text = f"{product_short} บำรุงล้ำลึก ให้ผิวชุ่มชื้น กระจ่างใส{reg_val}"
    elif "serum" in category.lower() or "moisturizer" in category.lower():
        hook_text = f"ผิวพังจากมลภาวะ อายุที่เพิ่มขึ้น หมดกังวล{reg_hook}"
        value_text = f"{product_short} บำรุงเข้มข้น ซึมไว ไม่เหนอะหนะ{reg_val}"
    elif "concealer" in category.lower() or "corrector" in category.lower():
        hook_text = f"ใต้ตาดำคล้ำ นอนดึกทุกวัน หมดปัญหา{reg_hook}"
        value_text = f"{product_short} ปกปิดเนียนกริบ ไม่ตกร่อง ไม่เป็นคราบ{reg_val}"
    else:
        hook_text = f"ต้องลอง! สินค้าดีบอกต่อ{reg_hook}"
        value_text = f"{product_short} คุณภาพเยี่ยม ใช้งานง่าย เห็นผลจริง{reg_val}"
    cta_text = f"กดดูในตะกร้าเลย{reg_val}"
    
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
            needed = estimated / seg["duration_sec"]
            if needed > max_speed_needed:
                max_speed_needed = needed
    
    tts_speed = min(max(max_speed_needed, 1.0), 1.3)
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

# ─── Gemini Prompt Generation (for product_usage style) ──────────
def _gemini_generate_prompts(
    product_name: str,
    product_appearance: str,
    features: str,
    env_context: str,
    category: str,
    model_age: int,
    model_gender: str,
    clothing: str,
    hair: str,
    ugc_style: str = "product_usage",
) -> tuple:
    """Generate image + video prompts via Gemini for product_usage style.
    
    Returns (image_prompt, video_prompt) — falls back to ("", "") on error.
    """
    # Build a concise product info block
    gender_en = {"female": "woman", "woman": "woman", "male": "man", "man": "man"}.get(model_gender, "woman")
    
    # Clean appearance
    pa = product_appearance or ""
    if pa:
        pa = re.sub(r'^(The\s+)?product\s+(is\s+)?', '', pa, flags=re.IGNORECASE).strip()
        pa = re.sub(r'^(a|an)\s+', '', pa, flags=re.IGNORECASE).strip()
    
    feat_str = ""
    if isinstance(features, list):
        feat_str = "; ".join(f.strip() for f in features if f.strip())
    elif isinstance(features, str) and features:
        feat_str = features[:200]
    
    system_prompt = (
        "Generate IMAGE_PROMPT and VIDEO_PROMPT for AI video generation.\n"
        "ALWAYS include model details naturally in the first sentence:\n"
        f"  Age {model_age}, Thai {gender_en}, porcelain white glowing skin, "
        "monolid eyes, Southeast Asian Thai features, small nose bridge.\n"
        "Also include clothing and hair style.\n\n"
        "IMAGE_PROMPT (under 80 words): Still scene. The woman is with the product.\n"
        "VIDEO_PROMPT (under 120 words): Natural product usage action. "
        "Weave product features into what she does — don't list them separately.\n"
        "For beauty/health: show application naturally.\n"
        "For electronics/home: show automatic/sensor/plug-in features naturally.\n"
        "Do NOT add negative instructions (no 'no text, no watermark, no logo').\n"
        "Do NOT add aspect ratios or tech specs like 9:16, 720P.\n"
        "Output format:\n"
        "IMAGE_PROMPT: ...\n"
        "VIDEO_PROMPT: ..."
    )
    
    # Build the product description block
    product_block = f"Product: {product_name}\nAppearance: {pa[:300]}\n"
    if feat_str:
        product_block += f"Features: {feat_str[:200]}\n"
    product_block += f"Setting: {env_context[:100]}\n"
    product_block += f"Style: {ugc_style} — show the person using this product with natural hands-on demonstration.\n"
    product_block += (f"Model: {model_age}yo {gender_en}, {clothing}, {hair}\n")
    
    user_text = f"{product_block}\nGenerate IMAGE_PROMPT and VIDEO_PROMPT:"
    
    try:
        result = _call_gemini(system_prompt, user_text, temperature=0.4)
        if not result:
            return ("", "")
        
        image_prompt = ""
        video_prompt = ""
        
        for line in result.strip().split("\n"):
            line_lower = line.lower().strip()
            if line_lower.startswith("image_prompt:") or line_lower.startswith("**image_prompt:**"):
                image_prompt = line.split(":", 1)[1].strip().lstrip("*").strip()
            elif line_lower.startswith("video_prompt:") or line_lower.startswith("**video_prompt:**"):
                video_prompt = line.split(":", 1)[1].strip().lstrip("*").strip()
        
        return (image_prompt, video_prompt)
    except Exception as e:
        logger.error(f"Gemini prompt generation failed: {e}")
        return ("", "")
