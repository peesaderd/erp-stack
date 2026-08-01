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
from model_casting import select_model_cast
from router_agent import router_decide

logger = logging.getLogger("prompt-builder-service")
def _override_style_for_clothing(style_info: dict, category: str) -> dict:
    if not _is_wearable_category(category):
        return style_info
    info = dict(style_info)
    if info.get("model_action"):
        info["model_action"] = info["model_action"].replace(
            "holding the product in both hands", "modeling the garment draped on body"
        ).replace(
            "casually holding product", "casually modeling the garment"
        ).replace(
            "holding product up showing packaging", "modeling the garment, turning to show fit"
        ).replace(
            "holding product", "modeling garment"
        ).replace(
            "both hands holding product", "garment draped beautifully on body"
        ).replace(
            "just holding and showing", "showing how garment fits naturally"
        )
    if info.get("video_motion"):
        info["video_motion"] = info["video_motion"].replace(
            "holding product gently in both hands", "modeling garment naturally, slight turn to show fit"
        ).replace(
            "holding product", "modeling garment"
        )
    if info.get("keywords"):
        info["keywords"] = info["keywords"].replace(
            "both hands holding product", "garment draped on body"
        ).replace(
            "holding product", "wearing garment"
        )
    return info

# ─── Clothing/Accessories Category Detection ──────────────────────
CLOTHING_CATEGORIES = {
    "fashion", "clothing", "apparel", # broad
    "accessories", "jewelry", "shoes", "bags", "watch", "watches",
    # specific garment types
    "shirt", "tops", "t-shirt", "polo", "blouse", "sweater", "hoodie",
    "jacket", "coat", "blazer", "vest",
    "pants", "jeans", "trousers", "shorts", "skirt", "leggings", "joggers",
    "dress", "suit", "uniform", "swimwear", "swimsuit", "bikini",
    "underwear", "lingerie", "loungewear", "sleepwear", "activewear",
    "socks", "scarf", "hat", "gloves", "belt", "tie", "cap",
    "garment", "outfit", "wearable"
}

def _is_wearable_category(category: str) -> bool:
    cat_lower = (category or "").lower().strip()
    return any(w in cat_lower for w in CLOTHING_CATEGORIES) or cat_lower in CLOTHING_CATEGORIES

def _get_category_display_action(category: str) -> dict:
    if _is_wearable_category(category):
        return {
            "holds": "wears and shows off",
            "hold_replace": "wears",
            "pose_phrase": "the garment draped beautifully on the body, clearly visible and in focus",
            "model_action_tail": "modeling and displaying the clothing elegantly on body, garment clearly visible, smiling naturally",
            "default_vid_motion": "gently modeling and displaying the garment on body",
        }
    else:
        return {
            "holds": "holds",
            "hold_replace": "holds",
            "pose_phrase": "product held at chest level, product clearly visible and in focus",
            "model_action_tail": "holding the product in both hands, product packaging facing camera, smiling naturally, NOT applying or using product, NOT opening product, just holding and showing",
            "default_vid_motion": "gently holding product in both hands at chest level",
        }



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
            "image_description": f"A 25-35 year old ethnic Thai {gender_en}, porcelain white glowing skin, monolid eyes, Southeast Asian features, wearing a neutral outfit, product visible in frame, clean modern setting",
            # Extract basic features from description when Gemini fails
            "features": _extract_features_from_description(description) if description else "",
            "product_appearance": _extract_appearance_from_description(description) if description else "",
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


def _extract_features_from_description(description: str) -> str:
    """Extract key product features from plaintext description when Gemini fails.
    Returns full phrases instead of isolated keywords.
    """
    desc = description.strip()
    if not desc:
        return ""
    # Try to extract meaningful feature phrases from the description
    # Look for number+unit combos, key tech specs
    spec_patterns = []
    # Find capacity/volume specs
    import re
    ml_match = re.search(r'\d+\s*ml', desc, re.IGNORECASE)
    if ml_match:
        spec_patterns.append(ml_match.group())
    # Find battery/power specs
    for kw in ['ไร้สาย', 'ชาร์จ USB', 'USB-C', 'แบตในตัว', 'rechargeable', 'wireless']:
        if kw.lower() in desc.lower():
            spec_patterns.append(kw)
    # Find tech features
    for kw in ['เซนเซอร์', 'sensor', 'อัตโนมัติ', 'automatic', 'LED', 'digital', 'smart', 'Bluetooth']:
        if kw.lower() in desc.lower() and kw not in spec_patterns:
            spec_patterns.append(kw)
    if spec_patterns:
        return ", ".join(spec_patterns[:6])
    # Last resort: first sentence
    return desc[:80]

def _extract_appearance_from_description(description: str) -> str:
    """Extract physical appearance from plaintext description."""
    desc = description.strip()
    if not desc:
        return ""
    # Try full sentences about appearance
    for kw in ['ดีไซน์', 'design', 'สี', 'รูปทรง', 'ลักษณะ', 'material', 'plastic', 'glass', 'metal',
               'white', 'black', 'pink', 'bottle', 'spray', 'nozzle', 'ขนาด', 'น้ำหนัก']:
        if kw.lower() in desc.lower():
            # Return first 100 chars that contain appearance context
            return desc[:100]
    return desc[:60]


def _strip_clothing_hair_from_desc(desc: str) -> str:
    """Remove clothing/hair from image_description so persona_clothing/hair takes priority."""
    if not desc:
        return desc
    # Remove ", wearing ..." clauses (any position in sentence)
    desc = re.sub(r',?\s*wearing\s+[^,]+', '', desc, flags=re.IGNORECASE)
    # Remove ", hair ..." or "straight dark hair worn sleek" style clauses
    desc = re.sub(r',?\s*hair\s+(in\s+)?[^,]+', '', desc, flags=re.IGNORECASE)
    desc = re.sub(r',?\s*straight\s+dark\s+hair\s+worn\s+\w+', '', desc, flags=re.IGNORECASE)
    # Remove ", sleek middle part down" etc
    desc = re.sub(r',?\s*sleek\s+middle\s+part\s+down', '', desc, flags=re.IGNORECASE)
    # Remove trailing camera/shot descriptors (can appear alongside clothing)
    desc = re.sub(r',?\s*(full|half|three.quarter|head.and.shoulders)\s+(body\s+)?shot', '', desc, flags=re.IGNORECASE)
    # Clean up
    desc = re.sub(r',\s*,', ',', desc)
    desc = re.sub(r'\s{2,}', ' ', desc).strip()
    desc = re.sub(r',$', '', desc).strip()
    return desc

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

    # ── Category-aware display action (clothing → wearing, others → holding) ──
    _cat_action = _get_category_display_action(category)
    _cat_hold = _cat_action["holds"]  # "wears and shows off" or "holds"
    _cat_pose = _cat_action["pose_phrase"]
    _cat_hold_replace = _cat_action["hold_replace"]  # "wears" or "holds"
    style_info = _override_style_for_clothing(style_info, category)

    gender_en = {
        "female": "woman", "woman": "woman",
        "male": "man", "man": "man",
        "unisex": "person", "person": "person"
    }.get(model_gender, "woman")
    
    persona_clothing = profile.get("persona_clothing", "")
    persona_hair = profile.get("persona_hair", "")
    env_context = profile.get("persona_environment", profile.get("setting", "")) or profile.get("env_context", "")
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
    if image_description:
        thai_base = image_description
        # Gender correction — Gemini bias safety net
        if gender_en == "man":
            thai_base = thai_base.replace("woman", "man").replace("Woman", "Man").replace("girl", "man").replace("Girl", "Man").replace("lady", "man").replace("Lady", "Man")
        elif gender_en == "woman":
            thai_base = thai_base.replace("man", "woman").replace("Man", "Woman").replace("guy", "woman").replace("Guy", "Woman").replace("boy", "woman").replace("Boy", "Woman")
        # Strip clothing/hair from image_description if persona provides them
        if persona_clothing or persona_hair:
            thai_base = _strip_clothing_hair_from_desc(thai_base)
    else:
        thai_base = f"An ethnic Thai {gender_en}, {model_age} years old, porcelain white glowing skin, monolid eyes, Southeast Asian ethnic Thai features, small nose bridge"


    # ── Style-driven scene (ugc_style is PRIMARY) ─────────────────
    if ugc_style == "product_demo":
        prod_desc = product_appearance or product_name
        try:
            from ugc_config import auto_select_preset
            cat = profile.get("category", "other")
            selection = auto_select_preset(cat)
            preset_mood = selection["preset"].get("mood", "clean, informative")
            preset_light = selection["preset"].get("lighting", "clean studio light")
        except ImportError:
            preset_mood = "clean, informative"
            preset_light = "clean studio light"
        scene_desc = (
            f"Product placed on {env_str}. {prod_desc[:200]} — "
            f"clean surface, product centered in frame. "
            f"Product features clearly visible. No people in frame. "
            f"Lighting: {preset_light}. Mood: {preset_mood}."
        )
    elif ugc_style in ("usage", "product_usage"):
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
                f"{env_str}. {thai_base}{clothing_str}{hair_str} {_cat_hold} {prod_str or product_name} in hand, "
                f"looking directly at camera with a friendly reviewing expression. "
                f"Product clearly visible and in focus. Lifestyle setting, natural window light."
            )
        else:
            scene_desc = (
                f"{thai_base}{clothing_str}{hair_str} {_cat_hold} {product_name}, "
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
                f"{env_str}. {thai_base}{clothing_str}{hair_str} {_cat_hold} {prod_str or product_name} in both hands, "
                f"showing product clearly to camera. Warm natural window lighting. "
                f"Product centered in frame at chest level."
            )
        else:
            scene_desc = (
                f"{thai_base}{clothing_str}{hair_str} {_cat_hold} {product_name} in hands, "
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
        "model_action": _cat_action["model_action_tail"] if _is_wearable_category(category) else style_info.get("model_action", ""),
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
            f"{_cat_action['model_action_tail'] if _is_wearable_category(category) else style_info.get('model_action', '')}. "
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

    # ── Final gender sweep ── template model_action hardcodes "Thai woman"
    if gender_en == "man":
        image_prompt = image_prompt.replace("woman", "man").replace("Woman", "Man").replace("girl", "man").replace("Girl", "Man").replace("lady", "man").replace("Lady", "Man")
    elif gender_en == "woman":
        image_prompt = image_prompt.replace("man", "woman").replace("Man", "Woman").replace("guy", "woman").replace("Guy", "Woman").replace("boy", "woman").replace("Boy", "Woman")

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

    category = profile.get("category", "other")

    # ── Category-aware display action (clothing → wearing, others → holding) ──
    _cat_action = _get_category_display_action(category)
    _cat_hold = _cat_action["holds"]  # "wears and shows off" or "holds"
    _cat_pose = _cat_action["pose_phrase"]
    _cat_hold_replace = _cat_action["hold_replace"]  # "wears" or "holds"
    style_info = _override_style_for_clothing(style_info, category)

    gender_en = {"female": "woman", "male": "man", "unisex": "person"}.get(model_gender, "person")
    model_age = profile.get("_normalized_age") or _normalize_age(profile.get("target_age", "20-35"))
    
    # ── Product description (common) ──
    env_context = profile.get("persona_environment", profile.get("setting", "")) or profile.get("env_context", "a modern space")
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
    
    # Minimal subject reference — appearance is from reference image
    # Video prompt describes ONLY motion, camera, and environment
    subject = f"A Thai {gender_en}"
    
    # ── Style-driven video_motion (ugc_style is PRIMARY) ──────────
    if ugc_style == "product_demo":
        # Import preset config for mood/lighting
        try:
            from ugc_config import auto_select_preset, build_shot_prompts
            cat = profile.get("category", "other")
            selection = auto_select_preset(cat)
            preset = selection["preset"]
            p_lighting = preset.get("lighting", "clean studio light")
            p_mood = preset.get("mood", "clean, informative")
            p_bgm = preset.get("bgm_style", "informative_jazz")
        except ImportError:
            p_lighting = "clean studio light, evenly diffused"
            p_mood = "clean, informative"
            p_bgm = "informative_jazz"
        
        # Build 3-shot prompt for product demo
        prod = prod_desc_vid or product_name
        if _is_wearable_category(category):
            shot1 = f"Shot1/0-5s: Full-body shot of {subject} STANDING, modeling {prod}. Garment fits naturally, clearly visible. Camera slow push in to mid-body. {p_lighting}."
            shot2 = f"Shot2/5-10s: Model turns slightly, showing {prod} from different angle — fabric texture, stitching, and fit details visible. Cinematic slow motion. Static camera."
            shot3 = f"Shot3/10-15s: Wide shot of {subject} STANDING fully visible, modeling {prod} complete outfit. Natural ambient setting. Camera slow pan right to reveal full scene."
            extra = "No sitting. No floor. 9:16 portrait, smooth natural motion."
        else:
            shot1 = f"Shot1/0-5s: Establishing wide shot of {prod} on {env_context}. Product centered, clean surface, minimal composition. Camera slow push in. {p_lighting}."
            shot2 = f"Shot2/5-10s: Close-up of {prod}. A hand enters frame, reaches toward product. Fine mist spray bursts from nozzle. Backlit highlighting particles drifting in air. Cinematic slow motion. Static camera."
            shot3 = f"Shot3/10-15s: Wide lifestyle shot of {prod} placed on {env_context} with natural ambient setting. Product in use context — warm atmosphere, depth of field. Camera slow pan right to reveal full scene."
            extra = "No people except hand in shot2."

        action = f"{shot1} {shot2} {shot3} {extra} Mood: {p_mood}. BGM: {p_bgm}."
    elif ugc_style in ("usage", "product_usage"):
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
            # Fallback: simple generic prompt — motion + camera only
            if _is_wearable_category(category):
                action = (
                    f"{subject} naturally modeling {prod_desc_vid or product_name}, "
                    f"gentle turn to show how the garment fits and drapes on body. "
                    f"Natural confident movement, garment details clearly visible. "
                    f"Camera follows with slow pan. "
                    f"{env_context}, soft natural light"
                )
            else:
                action = (
                    f"{subject} naturally demonstrates {prod_desc_vid or product_name} — "
                    f"the key product function shown in use. "
                    f"Natural hand movements, interacting with product. "
                    f"Camera follows the action with slow pan. "
                    f"{env_context}, soft natural light"
                )
    elif ugc_style == "review":
        # Review-style product showcase
        if _is_wearable_category(category):
            action = (
                f"{subject} naturally modeling {prod_desc_vid or product_name}, "
                f"turning slightly to show how the garment fits and drapes. "
                f"Looking at camera with confident, casual expression. "
                f"Garment details clearly visible. Camera static with subtle pull-back. "
                f"Lifestyle setting, soft natural light"
            )
        else:
            action = (
                f"{subject} {_cat_hold} {prod_desc_vid or product_name} in hand, "
                f"looking directly at camera with slight head tilt, casual reviewing pose. "
                f"Slow gentle rotation showing product from slightly different angles. "
                f"Subtle hand movement, natural breathing. Camera static with subtle zoom in. "
                f"Lifestyle setting, soft natural light"
            )
    elif ugc_style in ("tabletop", "tabletop_demo"):
        if _is_wearable_category(category):
            action = (
                f"{subject} modeling {prod_desc_vid or product_name}, "
                f"turning slowly to show garment from multiple angles. "
                f"Camera pans slowly around, full outfit visible. "
                f"Clean studio lighting, garment-centered presentation"
            )
        else:
            action = (
                f"{prod_desc_vid or product_name} is draped flat on surface, fully visible. " if _is_wearable_category(category) else f"{prod_desc_vid or product_name} sits on table. "
                f"{subject} nearby points at it and gestures with hands. "
                f"Camera pans slowly across tabletop, hands visible in frame gesturing toward product. "
                f"Product-centered demonstration, clean studio lighting"
            )
    elif ugc_style in ("talking", "talking_head"):
        # Head/shoulders, talking about product
        if _is_wearable_category(category):
            talking_tail = (
                f"{subject} in medium close-up, facing camera, "
                f"naturally modeling {prod_desc_vid or product_name}, slight turn to show how it fits. "
                f"Gentle head movements, natural facial expressions, conversational tone. "
                f"{prod_desc_vid or product_name} draped beautifully on body. "
                f"Camera static with subtle handheld feel. Natural daylight"
            )
            action = talking_tail
        else:
            action = (
                f"{subject} in medium close-up, facing camera, "
                f"speaking naturally about {prod_desc_vid or product_name}. "
                f"Gentle head movements, natural facial expressions, conversational tone. "
                f"Product resting nearby slightly blurred in foreground. "
                f"Camera static with subtle handheld feel. Natural daylight"
            )
    elif ugc_style == "unbox":
        if _is_wearable_category(category):
            action = (
                f"{subject} first reveal wearing {prod_desc_vid or product_name}, "
                f"stepping into frame confidently, showing off the full outfit. "
                f"Garment details fully visible as model poses naturally. "
                f"Camera slow push-in as outfit is revealed. "
                f"Clean bright setting, natural light"
            )
        else:
            action = (
                f"{subject} unboxing {prod_desc_vid or product_name}, "
                f"hands opening packaging, lifting product out with slight excitement. "
                f"Product emerging from packaging — unboxing reveal motion. "
                f"Camera slow push-in as product is revealed. "
                f"Clean bright setting, natural light"
            )
    else:
        # Default: holding — show product, gentle rotation
        action = (
            f"{subject} " + _cat_action.get("default_vid_motion", "gently holding product in both hands at chest level") + ", "
            f"showing product to camera with slight slow rotation. "
            f"Subtle smile, natural breathing motion, gentle hand movement. "
            f"Camera slow push-in. Warm natural light"
        )
    
    # ── Category-specific restrictions (SECONDARY) ──
    video_prompt = action
    # No more hardcoded beauty restrictions — Gemini handles appropriateness
    
    # Lighting + format tail (environment already in action)
    video_prompt += (
        f" 9:16 portrait, smooth natural motion"
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
    Full pipeline — now powered by PromptPipeline with 10 explicit steps.
    See GET /api/v1/pipeline/steps for agent-readable step list.
    """
    from pipeline import Pipeline
    from steps import ALL_STEPS

    pipeline = Pipeline("prompt-builder", ALL_STEPS)

    ctx = await pipeline.run({
        "product_name": product_name,
        "description": description,
        "keywords": keywords,
        "ugc_style": ugc_style,
        "product_id": product_id,
        "product_image": product_image,
        "category": category,
        "product_category": product_category,
    })

    # Build same response format as before (backward-compatible)
    c = ctx.ctx
    router_config = c.get("router_config", {})

    return {
        "product_id": product_id,
        "router_config": router_config,
        "pipeline": ctx.snapshot(),
        "analysis": {
            "category": c.get("category", "other"),
            "target_gender": c.get("target_gender", "female"),
            "target_age": c.get("target_age", "20-35"),
            "target_audience": c.get("target_audience", ""),
            "setting": c.get("setting", c.get("persona_environment", "")),
            "customer_problem": c.get("customer_problem", ""),
            "main_benefit": c.get("main_benefit", ""),
            "hashtags": c.get("hashtags", []),
            "image_description": c.get("image_description", ""),
            "env_context": c.get("env_context", ""),
            "product_appearance": c.get("product_appearance", ""),
            "features": c.get("features", ""),
        },
            "timing_validation": {
            "segments": {
                "hook": c.get("timing_validation", {}).get("hook", {}),
                "value": c.get("timing_validation", {}).get("value", {}),
                "cta": c.get("timing_validation", {}).get("cta", {}),
            },
            "tts_speed": c.get("timing_validation", {}).get("tts_speed", 1.0),
            "product_short_for_tts": c.get("timing_validation", {}).get("product_short_for_tts", product_name),
            "all_segments_fit": c.get("timing_validation", {}).get("all_segments_fit", True),
            "total_duration": 8,
        },
        "scripts": {
            "full_script": c.get("full_script", ""),
            "tts_script": c.get("tts_script", ""),
            "breakdown": c.get("scripts_breakdown", {"hook": "", "value": "", "cta": ""}),
        },
        "image_prompt": c.get("image_prompt", ""),
        "video_prompt": c.get("video_prompt", ""),
        "negative_prompt": c.get("negative_prompt", ""),
        "metadata": {
            "ugc_style": ugc_style,
            "used_gemini": True,
            "image_analyzed": bool(product_image),
            "model_id": c.get("model_id", ""),
            "route_reason": router_config.get("reason", ""),
            "persona": {
                "vibe": c.get("persona_vibe", ""),
                "environment": c.get("persona_environment", c.get("setting", "")),
                "lighting": c.get("persona_lighting", ""),
                "motion_speed": c.get("persona_motion", ""),
                "clothing": c.get("persona_clothing", ""),
                "hair": c.get("persona_hair", ""),
            }
        }
    }

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
# Cache: same product+age within same request returns cached result
_gemini_prompt_cache = {}

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
    
    # Cache by product name + age — avoid duplicate calls within same request
    _cache_key = (product_name, model_age, "image")
    # Check both image and video cache — if either missing, regenerate both
    cached_img = _gemini_prompt_cache.get((product_name, model_age, "image"))
    cached_vid = _gemini_prompt_cache.get((product_name, model_age, "video"))
    if cached_img is not None and cached_vid is not None:
        return (cached_img[0], cached_vid[1])
    
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
    
    # Wan 2.7 is a diffusion model — it ONLY understands literal visual descriptions
    system_prompt_image = (
        "You write a SINGLE image prompt for an AI image generator.\n"
        "CRITICAL RULES:\n"
        "1. Describe ONLY what is VISUALLY seen — no abstract concepts or product mechanics.\n"
        "2. Model appearance: Age {model_age}, Thai {gender_en}, porcelain white glowing skin, "
        "monolid eyes, Southeast Asian Thai features, small nose bridge.\n"
        "3. Use EXACTLY the clothing and hair from the Model line below. Do NOT invent or modify them.\n"
        "4. The model's clothing and hair must appear exactly ONCE in the prompt.\n"
        "5. Describe the product and setting clearly.\n"
        "6. Keep under 80 words. No negative instructions, no aspect ratios.\n"
        "Output ONLY the prompt text, no label or prefix."
        .format(model_age=model_age, gender_en=gender_en)
    )

    system_prompt_video = (
        "You write a SINGLE video prompt for Wan 2.7, a DIFFUSION video model.\n"
        "Wan 2.7 CANNOT understand abstract concepts or product mechanics.\n"
        "Describe ONLY concrete, PHYSICAL, VISUAL movements step by step.\n\n"
        "CRITICAL RULES:\n"
        "1. Describe ONLY concrete visible actions (moves, stops, places, lifts, presses).\n"
        "2. Be EXTREMELY specific about hand/body POSITION relative to product:\n"
        "   - Use BELOW the nozzle, ABOVE the button, BESIDE the product, IN FRONT OF camera.\n"
        "3. NO: detects, automatically, intelligently, senses, recognizes, responds.\n"
        "4. YES: clear liquid appears on palm, button moves down, mist appears below nozzle.\n"
        "5. The person\\'s appearance, face, skin, body, clothing, and hair are "
        "ALREADY DEFINED in the reference image. Do NOT describe or modify them.\n"
        "6. Product is FIXED/MOUNTED on wall or table — DO NOT have person hold the product "
        "unless it is a handheld product (phone, bottle, tool).\n"
        "7. Do NOT describe camera shots (no 'head-and-shoulders shot', 'three-quarter body shot', etc).\n"
        "8. Do NOT copy the image prompt. This is a DIFFERENT, action-focused description.\n"
        "9. Keep under 130 words. No negative instructions, no aspect ratios.\n"
        "Output ONLY the prompt text, no label or prefix."
        .format(model_age=model_age, gender_en=gender_en)
    )
    
    # Build the product description block — emphasize physical placement
    mount_hint = ""
    # Check for wall/table mount indicators
    pa_lower = (pa + " " + product_name + " " + feat_str).lower() if pa else product_name.lower()
    if any(w in pa_lower for w in ["wall", "mount", "sensor", "dispenser", "mounted"]):
        mount_hint = "\nIMPORTANT: This product is FIXED on wall or table. Person does NOT hold it. Describe it in place."
    elif any(w in pa_lower for w in ["bottle", "jar", "tube", "dropper"]):
        mount_hint = "\nThis product is HANDHELD. Person picks it up from a surface to use it."
    
    product_block = f"Product: {product_name}\nAppearance: {pa[:350]}\n"
    if feat_str:
        product_block += f"Features: {feat_str[:200]}\n"
    product_block += f"Setting: {env_context[:120]}\n"
    product_block += mount_hint
    # Model appearance is from reference image — video prompt does NOT need it
    
    try:
        # Two separate Gemini calls: image + video (different system prompts, no cross-contamination)
        image_prompt = ""
        video_prompt = ""

        user_text_image = f"{product_block}\nGenerate ONLY the image prompt:"
        result_image = _call_gemini(system_prompt_image, user_text_image, temperature=0.4)
        if result_image:
            image_prompt = result_image.strip().split("\n")[0].strip()
            # Clean prefixes like "IMAGE_PROMPT:" if model hallucinates them
            image_prompt = re.sub(r'^(IMAGE_PROMPT|image_prompt|Image Prompt)[:]\s*', '', image_prompt, flags=re.IGNORECASE).strip()

        user_text_video = f"{product_block}\nGenerate ONLY the video prompt describing concrete physical actions step by step:"
        result_video = _call_gemini(system_prompt_video, user_text_video, temperature=0.5)
        if result_video:
            video_prompt = result_video.strip().split("\n")[0].strip()
            video_prompt = re.sub(r'^(VIDEO_PROMPT|video_prompt|Video Prompt)[:]\s*', '', video_prompt, flags=re.IGNORECASE).strip()

        # Cache with separate keys for image/video
        _gemini_prompt_cache[(_cache_key[0], _cache_key[1], "image")] = (image_prompt, video_prompt)
        _gemini_prompt_cache[(_cache_key[0], _cache_key[1], "video")] = (image_prompt, video_prompt)
        return (image_prompt, video_prompt)
    except Exception as e:
        logger.error(f"Gemini prompt generation failed: {e}")
        _gemini_prompt_cache[(_cache_key[0], _cache_key[1], "image")] = ("", "")
        _gemini_prompt_cache[(_cache_key[0], _cache_key[1], "video")] = ("", "")
        return ("", "")
