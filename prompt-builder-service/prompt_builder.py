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
    """Generate image prompt using profile + UGC templates.
    
    Strategy:
    - Category-aware: home/electronics/tools → scene in environment, not person holding
    - Beauty/fashion → model holding product (current behavior)
    - Product details from product_appearance (Mistral Vision) or image_description (Gemini text)
    """
    templates = load_ugc_templates(ugc_style)
    style_info = STYLE_MAP.get(ugc_style, STYLE_MAP["holding"])
    model_gender = profile.get("target_gender", "female")
    model_age = _normalize_age(profile.get("target_age", "20-35"))
    category = profile.get("category", "other")

    gender_en = {
        "female": "woman", "woman": "woman",
        "male": "man", "man": "man",
        "unisex": "person", "person": "person"
    }.get(model_gender, "woman")

    thai_features = "porcelain white glowing skin, monolid eyes, Southeast Asian ethnic Thai features, small nose bridge"
    thai_model = f"An ethnic Thai {gender_en}, {model_age} years old, {thai_features}"

    persona_clothing = profile.get("persona_clothing", "")
    persona_hair = profile.get("persona_hair", "")
    env_context = profile.get("env_context", "")
    product_appearance = profile.get("product_appearance", "")
    image_description = profile.get("image_description", "")

    # ── Category-specific scene description ──────────────────────────
    # For home/electronics/tools: product IN ENVIRONMENT, not held
    if category in ("home", "electronics", "tools"):
        if product_appearance:
            scene_desc = f"{env_context or 'A clean modern space'}. Fixed to the wall/surface is a {product_appearance[:250]}."
        elif image_description:
            scene_desc = image_description[:250]
        else:
            scene_desc = f"{env_context or 'A modern living space with soft evening lighting'}. The product is installed and visible."
        # Person naturally in scene
        if persona_clothing:
            scene_desc += f" A {gender_en} aged {model_age} wearing {persona_clothing} walks past naturally."
        else:
            scene_desc += f" A {gender_en} aged {model_age} walks past naturally, casual pose."
        if persona_clothing:
            scene_desc += f" Wearing {persona_clothing}."
        if persona_hair:
            scene_desc += f" {persona_hair}."
    else:
        # Beauty/fashion/food: model holding/using product
        scene_desc = image_description or f"{thai_model}, pretty face, professional model quality"
        if "Thai" in scene_desc and "ethnic" not in scene_desc.lower() and "Southeast" not in scene_desc:
            scene_desc = scene_desc.replace("Thai", f"Ethnic Thai with {thai_features}", 1)
            scene_desc = scene_desc.replace("glowing skin", "porcelain white glowing skin")
        # Add clothing/hair from persona
        if persona_clothing:
            scene_desc += f" Wearing {persona_clothing}."
        if persona_hair:
            scene_desc += f" {persona_hair}."
        # Extract product_pkg from image_description for beauty
        if image_description:
            for sentence in img_desc_sentences(image_description):
                # Append if it's about packaging
                s = sentence.strip().lower()
                if any(w in s for w in ["bottle", "tube", "jar", "container", "tube", "packaging", "cap"]):
                    if "thai woman" not in s[:40] and "thai man" not in s[:40]:
                        scene_desc += f" {sentence.strip()}."
                        break

    # ── Use template or build directly ──
    if category in ("home", "electronics", "tools"):
        # Don't use beauty-biased "Holding Product" template for non-beauty
        image_prompt = (
            f"{scene_desc} "
            f"Natural ambient {style_info.get('lighting', 'soft natural lighting')}, warm atmosphere. "
            f"Cinematic natural composition, eye-level angle. "
            f"The product is visible and in focus. "
            f"9:16 portrait, high quality photography"
        )
        negative = templates.get("negative", "text, watermark, logo, ui, caption")
    else:
        # Use standard template for beauty/fashion/etc
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
            "model_action": style_info.get("model_action", "holding product"),
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
    
    # ── Beauty-specific restrictions ──
    if category in ("beauty", "health"):
        image_prompt += " CRITICAL: The cap is CLOSED and sealed. Both hands hold the closed product only. Not opening, not using."
        image_prompt = re.sub(r"her\s+(own\s+)?lips?\b", "the product", image_prompt, flags=re.IGNORECASE)
        image_prompt = re.sub(r"his\s+(own\s+)?lips?\b", "the product", image_prompt, flags=re.IGNORECASE)
        image_prompt = re.sub(r"\bon (their|her|his) (lips?|skin|face)\b", " ", image_prompt, flags=re.IGNORECASE)

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
    Category-aware: home/electronics/tools → use case in environment
    Beauty/fashion → packaging action + holding product
    """
    style_info = STYLE_MAP.get(ugc_style, STYLE_MAP["holding"])
    model_gender = profile.get("target_gender", "female")
    model_setting = profile.get("setting", "clean modern lifestyle setting")
    category = profile.get("category", "other")

    gender_en = {"female": "woman", "male": "man", "unisex": "person"}.get(model_gender, "person")

    # ── Thai ethnic face + clothing/hair variety ───────────────────
    persona_clothing = profile.get("persona_clothing", "")
    persona_hair = profile.get("persona_hair", "")
    clothing_str = f", wearing {persona_clothing}" if persona_clothing else ""
    hair_str = f", {persona_hair}" if persona_hair else ""
    thai_face = "porcelain white glowing skin, monolid eyes, Southeast Asian ethnic Thai features"

    model_age = _normalize_age(profile.get("target_age", "20-35"))

    # ── Category-aware video_motion ────────────────────────────────
    if category in ("home", "electronics", "tools"):
        # Use case: product installed, person interacting naturally
        env_context = profile.get("env_context", "a hallway")
        features = profile.get("features", [])
        if isinstance(features, str):
            features = [features]
        feature_str = ", ".join(features[:3]) if features else "automatic operation"
        
        video_motion = (
            f"walking naturally in {env_context}, product visible and installed. "
            f"Person passes by naturally — product activates automatically: {feature_str}. "
            f"No staring at camera, no artificial posing, natural everyday movement"
        )
    elif ugc_style == "holding":
        # Holding style: just show product (for beauty primarily)
        video_motion = style_info.get('video_motion', 
            "gently holding product in both hands, slight slow rotation, showing to camera")
    else:
        # Non-holding styles: packaging action inference
        packaging_action = profile.get("packaging_action", "")
        name_lower = product_name.lower()
        mistral_was_generic = packaging_action in ("", "generic_hold")

        if mistral_was_generic:
            if any(w in name_lower for w in ["click", "คลิก", "กดกิ๊ก"]):
                packaging_action = "click_to_release"
            elif any(w in name_lower for w in ["pump", "ปั๊ม"]):
                packaging_action = "pump"
            elif any(w in name_lower for w in ["spray", "สเปรย์", "ฉีด"]):
                packaging_action = "spray"
            elif any(w in name_lower for w in ["roll", "โรล"]):
                packaging_action = "roll"
            elif any(w in name_lower for w in ["cushion", "คุชชั่น"]):
                packaging_action = "dab_press"
            elif any(w in name_lower for w in ["pen", "ปากกา"]):
                packaging_action = "click_pen"
            elif any(w in name_lower for w in ["cream", "ครีม"]):
                packaging_action = "blend"
            elif any(w in name_lower for w in ["matte", "แมทท์"]):
                packaging_action = "smooth_application"
            elif any(w in name_lower for w in ["glossy", "ฉ่ำ", "วาว"]):
                packaging_action = "glossy_shine"
            elif any(w in name_lower for w in ["blush", "บลัช", "บลัชออน"]):
                packaging_action = "blush_swirl"
            else:
                packaging_action = "generic_hold"

        PACKAGING_VIDEO_MOTIONS = {
            "click_to_release": "CLICKING the pen mechanism, holding product up, then applying on lips",
            "click_pen": "CLICKING the pen to extend product, then applying",
            "pump": "PUMPING the bottle top, showing product dispensing",
            "spray": "SPRAYING the product onto skin, fine mist visible",
            "roll": "ROLLING the ball applicator on skin, circular motion",
            "smooth_application": "applying product with smooth even strokes, blending motion",
            "glossy_shine": "applying product on lips, pressing lips together to show glossy shine",
            "blend": "blending product into skin with circular motion",
            "dab_press": "dabbing cushion puff on face with gentle pressing motion",
            "blush_swirl": "swirling brush in blush compact, dusting on cheeks",
            "generic_hold": style_info.get('video_motion', 'holding product gently at chest level'),
        }
        video_motion = PACKAGING_VIDEO_MOTIONS.get(packaging_action, style_info.get('video_motion', ''))

    category = profile.get("category", "other")

    # ── Build product description ──────────────────────────────────
    # For home/electronics/tools: use product_appearance from Mistral Vision
    # For beauty/fashion: extract packaging from image_description
    if category in ("home", "electronics", "tools"):
        env_context = profile.get("env_context", "a hallway")
        product_appearance = profile.get("product_appearance", "the product")
        product_desc = f"installed in {env_context}. Product: {product_appearance[:200]}"
        model_intro = f"Ethnic Thai {gender_en} {model_age} years old, {thai_face}{clothing_str}{hair_str}"
        video_prompt = (
            f"{model_intro}, {video_motion}. "
            f"The product is {product_desc}. "
        )
    else:
        # Beauty/fashion: extract packaging details from image_description
        image_desc = profile.get("image_description", "")
        product_pkg = ""
        if image_desc:
            for sentence in image_desc.split("."):
                s = sentence.strip().lower()
                first_part = s[:40]
                if any(w in first_part for w in ["thai woman", "thai man", "model", "ethnic thai"]):
                    continue
                container_words = ["bottle", "tube", "jar", "container", "packaging", "cap", "label",
                                 "twist", "pump", "spray", "flip-top", "click", 
                                 "carton", "box", "wrapper", "applicator"]
                is_about_packaging = s.startswith("the product ") or s.startswith("the packaging ")
                is_about_packaging = is_about_packaging or any(w in s for w in container_words)
                if is_about_packaging:
                    product_pkg = sentence.strip()
                    break
            if not product_pkg and len(image_desc) > 40:
                product_pkg = image_desc[:120]

        model_intro = f"Ethnic Thai {gender_en} {model_age} years old, {thai_face}{clothing_str}{hair_str}"
        if product_pkg:
            pkg_clean = re.sub(r'^(The\s+)?product\s+(is\s+)?', '', product_pkg, flags=re.IGNORECASE).strip()
            pkg_clean = re.sub(r'^(The\s+)?packaging\s+(is\s+)?', '', pkg_clean, flags=re.IGNORECASE).strip()
            video_prompt = f"{model_intro}, {video_motion}. The packaging: {pkg_clean}. "
        else:
            video_prompt = f"{model_intro}, {video_motion}. "

    # ── Beauty-specific restrictions ──
    if category in ("beauty", "health"):
        video_prompt += " CRITICAL: Do NOT open or apply the product. Cap is CLOSED and sealed. No squeezing, no pumping, no spraying."

    video_prompt += (
        f" Setting: {model_setting}. "
        f"soft natural lighting, warm atmosphere. "
        f"9:16 portrait, smooth natural motion, no text, no watermark"
    )
    
    # Clean up
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
                     "customer_problem", "main_benefit", "env_context", "product_appearance"]:
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

    # Step 4: Build prompts
    image_prompt, negative_prompt = build_image_prompt(profile, product_name, ugc_style)
    video_prompt = build_video_prompt(profile, product_name, ugc_style)
    if not negative_prompt:
        negative_prompt = build_negative_prompt(profile, ugc_style)
    
    # Step 5: Validate script timing
    timing_validation = _build_timing_validated_script(product_name, profile.get("category", "other"))
    
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


def _build_timing_validated_script(product_name: str, category: str = "beauty") -> dict:
    """Build script segments with timing validation."""
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
    
    # Script segments
    if "blush" in category.lower() or "cheek" in category.lower():
        hook_text = f"หน้าแบน ไม่มีมิติ แต่งหน้ายังไงก็ไม่ปัง?"
        value_text = f"{product_short} บลัชออน เพิ่มความสดใส วิ้งเบาๆ เป็นธรรมชาติ"
    elif "lip" in category.lower():
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
