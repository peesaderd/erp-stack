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
    PRODUCT_ANALYSIS_SYSTEM, _generate_media_prompts,
)
from persona_engine import (
    PERSONA_TEMPLATES, _select_persona, _apply_persona_to_profile,
)
from router_agent import router_decide

logger = logging.getLogger("prompt-builder-service")

# ─── Clothing/Accessories Category Detection ──────────────────────
# Single source of truth for clothing/fashion display (image + video).
# Keep in sync with Gemini's rule: clothing/fashion → model WEARS, never holds.
WEARABLE_IMAGE_ACTION = "modeling and displaying the clothing elegantly on body, garment clearly visible, smiling naturally"

CLOTHING_CATEGORIES = {
    "fashion", "clothing", "apparel",  # broad
    "accessories", "jewelry", "shoes", "bags", "watch", "watches",
    # specific garment types
    "shirt", "tops", "t-shirt", "polo", "blouse", "sweater", "hoodie",
    "jacket", "coat", "blazer", "vest",
    "pants", "jeans", "trousers", "shorts", "skirt", "leggings", "joggers",
    "dress", "suit", "uniform", "swimwear", "swimsuit", "bikini",
    "underwear", "lingerie", "loungewear", "sleepwear", "activewear",
    "socks", "scarf", "hat", "gloves", "belt", "tie", "cap",
    "garment", "outfit", "wearable",
    # Thai categories
    "แฟชั่น", "เสื้อ", "เสื้อผ้า", "เสื้อเชิ้ต", "เชิ้ต",
    "กางเกง", "ยีนส์", "เดรส", "กระโปรง", "สูท", "แจ็คเก็ต",
    "ชุด", "เครื่องแต่งกาย", "เครื่องนุ่งห่ม", "ผ้า",
}

def _is_wearable_category(category: str) -> bool:
    cat_lower = (category or "").lower().strip()
    return any(w in cat_lower for w in CLOTHING_CATEGORIES) or cat_lower in CLOTHING_CATEGORIES


def _normalize_age(raw_age) -> int:
    """Normalize age from profile to 18-25 range for UGC models."""
    import random
    try:
        if isinstance(raw_age, (int, float)):
            age = int(raw_age)
        else:
            parts = str(raw_age).replace(" ", "").split("-")
            nums = [int(p) for p in parts if p.isdigit()]
            age = nums[0] if nums else 22
    except (ValueError, TypeError):
        age = 22
    return max(18, min(25, age + random.randint(-1, 1)))


# ─── Country → Ethnicity descriptor ──────────────────────────────
# Single source of truth for the model's ethnicity/appearance based on
# the selected country. Used by image/video prompt builders and the
# media-generation (Gemini) prompts so the model always matches the
# user's chosen country instead of a hardcoded "Ethnic Thai".
COUNTRY_ETHNICITY = {
    "thai": ("ethnic Thai", "Southeast Asian ethnic Thai features"),
    "vietnamese": ("ethnic Vietnamese", "Southeast Asian Vietnamese features"),
    "korean": ("ethnic Korean", "East Asian Korean features"),
    "japanese": ("ethnic Japanese", "East Asian Japanese features"),
    "chinese": ("ethnic Chinese", "East Asian Chinese features"),
    "indian": ("ethnic Indian", "South Asian Indian features"),
    "western": ("Caucasian", "Western European features"),
}

def _country_ethnicity(country: str) -> tuple:
    """Return (ethnicity_label, features_desc) for a country code."""
    return COUNTRY_ETHNICITY.get((country or "").lower().strip(), COUNTRY_ETHNICITY["thai"])


def _normalize_gender_in_description(text: str, gender_en: str) -> str:
    """Force gender words inside a Gemini-generated image_description
    to match the resolved target gender.

    Gemini frequently hardcodes 'Ethnic Thai woman' even when the product
    targets men (or vice versa). The resolved gender (from user input /
    keyword auto-detect) is authoritative, so rewrite any ethnic-Thai
    person phrase to the correct gender before the prompt is used.
    """
    if not text:
        return text
    # Map of every known woman-phrase -> equivalent man-phrase and vice versa.
    # Order matters: check 'Ethnic Thai woman/man' and 'Thai woman/man' first.
    if gender_en == "man":
        repl = [
            (r"ethnic\s+thai\s+wom[ae]n?\b", "ethnic Thai man"),
            (r"thai\s+wom[ae]n?\b", "Thai man"),
            (r"ethnic\s+thai\s+girls?\b", "ethnic Thai man"),
            (r"thai\s+girls?\b", "Thai man"),
            (r"young\s+thai\s+wom[ae]n?\b", "young Thai man"),
            (r"\bwom[ae]n\b", "man"),
            (r"\bshe\b", "he"),
            (r"\bher\b", "his"),
            (r"\bhers\b", "his"),
            (r"\bherself\b", "himself"),
        ]
    elif gender_en == "woman":
        repl = [
            (r"ethnic\s+thai\s+wom[ae]n?\b", "ethnic Thai woman"),
            (r"thai\s+wom[ae]n?\b", "Thai woman"),
            (r"ethnic\s+thai\s+m[ae]n\b", "ethnic Thai woman"),
            (r"thai\s+m[ae]n\b", "Thai woman"),
            (r"young\s+thai\s+m[ae]n\b", "young Thai woman"),
            (r"\bm[ae]n\b", "woman"),
            (r"\bhe\b", "she"),
            (r"\bhim\b", "her"),
            (r"\bhis\b", "her"),
            (r"\bhimself\b", "herself"),
        ]
    else:  # unknown gender — never invent/strip; leave text untouched
        repl = []
    out = text
    for pat, replacement in repl:
        out = re.sub(pat, replacement, out, flags=re.IGNORECASE)
    return out

def analyze_product(product_name: str, description: str = "", keywords: Optional[List[str]] = None, target_duration: int = 15, features: str = "", target_age: str = "", ugc_style: str = "", category: str = "", target_gender: str = "", product_id: str = "", price: float = 0.0, product_category: str = "", country: str = "") -> dict:
    """Analyze product via Gemini and return profile dict.
    
    Uses Router Agent for strategic context (recipe, style, persona),
    and Gemini for visual/profile details.
    Falls back to simple default if Gemini fails.
    """
    keywords = keywords or []
    kw_str = ", ".join(keywords) if keywords else "ไม่มี"
    
    # Get Router Agent config (strategy decision)
    router_config = router_decide(
        product_name=product_name,
        description=description,
        keywords=keywords,
        target_duration=target_duration,
    )
    
    # Get product profile from Gemini analysis
    # UNIFIED FEED: every known field is ALWAYS sent — never conditionally omitted.
    user_text = f"""ชื่อสินค้า: {product_name}
คำอธิบาย: {description if description else 'ไม่มี'}
Keywords: {kw_str}
คุณสมบัติเด่น (Features): {features if features else 'ไม่มี'}
UGC Style ที่ต้องการ: {ugc_style if ugc_style else 'ไม่ได้ระบุ'}
หมวดหมู่สินค้า: {category if category else 'ไม่ระบุ'}
หมวดหมู่รอง (Product Category): {product_category if product_category else 'ไม่ระบุ'}
อายุกลุ่มเป้าหมาย: {target_age if target_age else 'ไม่ได้ระบุ'}
เพศกลุ่มเป้าหมาย: {target_gender if target_gender else 'ไม่ได้ระบุ (ให้วิเคราะห์จากชื่อสินค้า/คำอธิบายเอง)'}
ประเทศ/เชื้อชาติของโมเดล: {country if country else 'thai'}
ราคา: {price if price else 'ไม่ระบุ'}
Product ID: {product_id if product_id else 'ไม่ระบุ'}"""

    raw = _call_gemini(PRODUCT_ANALYSIS_SYSTEM, user_text, temperature=0.3)
    gemini_profile = _extract_json(raw) if raw else None

    if not gemini_profile:
        logger.warning("Gemini analysis failed — using default profile with Router context")
        gender_en = ""
        profile = {
            "category": "other",
            "country": country or "thai",
            "target_gender": "",
            "target_age": "",
            "target_audience": f"คนที่กำลังมองหา{_thai_safe_truncate(product_name, 20)}",
            "setting": "clean modern lifestyle setting",
            "customer_problem": f"ปัญหาที่{_thai_safe_truncate(product_name, 30)}นี้ช่วยแก้",
            "main_benefit": f"คุณประโยชน์ของ{_thai_safe_truncate(product_name, 20)}",
            "packaging_action": "generic_hold",
            "action_desc": "ถือสินค้าและใช้งานทั่วไป",
            "hashtags": keywords[:5] if len(keywords) >= 5 else [_thai_safe_truncate(product_name.replace(" ", ""), 20)] * 5,
            "image_description": "",
            # Extract basic features from description when Gemini fails
            "features": _extract_features_from_description(description) if description else "",
            "product_appearance": _extract_appearance_from_description(description) if description else "",
        }
    else:
        profile = gemini_profile
        profile["country"] = country or "thai"
        # Normalize hashtags
        h = profile.get("hashtags", [])
        if isinstance(h, str):
            h = [x.strip().replace("#", "") for x in h.split(",")]
        elif isinstance(h, list):
            h = [x.strip().replace("#", "") for x in h if x.strip()]
        while len(h) < 5:
            h.append(_thai_safe_truncate(product_name.replace(" ", "").replace("\n", ""), 20))
        profile["hashtags"] = h[:5]

    if features:
        profile["features"] = features

    # ── usage_action fallback ─────────────────────────────────────────
    # Gemini sometimes omits usage_action. For fashion/wearable products the
    # model must WEAR the garment (never hold it). Provide a sensible default
    # so the Gemini media-generation path (build_image_prompt/build_video_prompt)
    # is always used for fashion.
    if not profile.get("usage_action", ""):
        _cat = (profile.get("category") or category or "").lower()
        if _is_wearable_category(_cat):
            profile["usage_action"] = (
                "already wearing the garment, she smooths the pleats and turns "
                "slowly to showcase the silhouette and the fabric quality"
            )
        else:
            profile["usage_action"] = (
                "holding the product and showing it to camera, then using it naturally"
            )

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
    return _thai_safe_truncate(desc, 80)

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
            return _thai_safe_truncate(desc, 100)
    return _thai_safe_truncate(desc, 60)


def build_image_prompt(profile: dict, product_name: str, ugc_style: str = "holding") -> str:
    """Generate image prompt — style-driven, category-modulated.
    
    PRINCIPLE:
    - ugc_style controls what the person DOES in the scene (holding, reviewing, using)
    - category controls WHERE/context (home, beauty environment modifiers)
    - Person is ALWAYS in the scene
    - Each style produces distinctly different output
    """
    templates = load_ugc_templates(ugc_style)
    # For wearable/fashion products, force the fashion_lookbook style so the model
    # WEARS the garment (never holds it). The product IS the outfit on the body.
    if _is_wearable_category(profile.get("category", "other")):
        style_info = STYLE_MAP.get("fashion_lookbook", STYLE_MAP["holding"])
    else:
        style_info = STYLE_MAP.get(ugc_style, STYLE_MAP["holding"])
    model_gender = profile.get("target_gender")
    model_age = profile.get("_normalized_age") or _normalize_age(profile.get("target_age", "")) or ""
    category = profile.get("category", "other")

    # ── Category-aware display action (clothing → wearing, others → holding) ──

    gender_en = {"female": "woman", "male": "man"}.get(model_gender, "")
    
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
        pa_clean = re.sub(r'^the\s+', '', pa_clean, flags=re.IGNORECASE).strip()
        article = "an" if pa_clean[:1].lower() in "aeiou" else "a"
    
    env_str = _thai_safe_truncate(env_context or "a modern lifestyle setting", 120)
    age_seg = f" {model_age} years old" if model_age else ""
    _eth_label, _eth_features = _country_ethnicity(profile.get("country", ""))
    thai_base = f"An {_eth_label} {gender_en}{age_seg}, {_eth_features}, small nose bridge"
    
    _used_media_img = False  # True when Gemini media generation produced the image_prompt


    # ── Priority 1: Direct Gemini Vision Scene Description (Exact Product Visual Match) ──
    if False and image_description and len(image_description) > 20:  # disabled: vision describes product-only photo, not the model
        if _is_wearable_category(category):
            image_description = image_description.replace("holding", "wearing").replace("hold", "wear")
        # Gemini hardcodes a gender even when user selected opposite —
        # force it to match the RESOLVED target gender (user input authoritative).
        image_description = _normalize_gender_in_description(image_description, gender_en)
        if age_seg and age_seg not in image_description:
            # Gemini Vision only sees the photo — it cannot know the target age.
            # Inject the age so image + video prompts stay consistent.
            _eth_label, _eth_features = _country_ethnicity(profile.get("country", ""))
            m = re.search(rf'(ethnic\s+\w+\s+(?:woman|man|person))', image_description, re.IGNORECASE)
            if m:
                image_description = image_description[:m.end()] + age_seg + image_description[m.end():]
            else:
                tail = image_description[0].lower() + image_description[1:] if image_description else ""
                image_description = f"{thai_base}, {tail}".strip()
        scene_desc = image_description
    # ── Priority 2: Style-driven scene fallback ─────────────────
    # Step 2: usage_action-driven media generation (Gemini 2-step architecture)
    # When the vision analysis produced a usage_action, use the MEDIA_GENERATION_SYSTEM
    # image_prompt (constructed scene-first, product integrated naturally).
    elif profile.get("usage_action", "") and ugc_style not in ("product_demo", "tabletop", "tabletop_demo"):
        _media_img, _media_vid = _get_media_prompts_cached(
            product_name=product_name,
            product_appearance=pa_clean or product_name,
            usage_action=profile.get("usage_action", ""),
            ugc_style=ugc_style,
            category=category,
            model_gender=gender_en,
            model_age=str(model_age) if model_age else "",
            env_context=env_context,
            features=profile.get("features", ""),
            country=profile.get("country", ""),
        )
        if _media_img:
            scene_desc = _media_img
            _used_media_img = True
        else:
            raise RuntimeError(
                f"Gemini media generation returned empty image_prompt for product "
                f"'{product_name}' (usage_action='{profile.get('usage_action', '')}'). "
                f"No fallback — fix the Gemini call."
            )
    elif ugc_style == "product_demo":
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
            f"Product placed on {env_str}. {_thai_safe_truncate(prod_desc, 200)} — "
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
            clothing=profile.get("persona_clothing", ""),
            hair=profile.get("persona_hair", ""),
            ugc_style=ugc_style,
        )
        if gemini_image:
            scene_desc = gemini_image
        elif pa_clean:
            prod_str = f"{article} {_thai_safe_truncate(pa_clean, 200)}"
            scene_desc = (
                f"{env_str}. {thai_base}{clothing_str}{hair_str} beside {prod_str or product_name} — "
                f"about to use the product. "
                f"Product and person in frame, casual lifestyle moment."
            )
        else:
            scene_desc = (
                f"{thai_base}{clothing_str}{hair_str} beside {product_name} — "
                f"about to use the product. "
                f"{env_str}."
            )
        
    elif ugc_style == "review":
        # Person holding product + looking at camera, review-style
        if pa_clean:
            prod_str = f"{article} {_thai_safe_truncate(pa_clean, 200)}"
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
            prod_str = f"{article} {_thai_safe_truncate(pa_clean, 200)}"
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
            prod_str = f"{article} {_thai_safe_truncate(pa_clean, 200)}"
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
            prod_str = f"{article} {_thai_safe_truncate(pa_clean, 200)}"
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
    
    # ── Wearing guard (source of truth: clothing must be WORN, never held) ──
    if (_is_wearable_category(category) or ugc_style in ("fashion_lookbook", "lookbook", "outfit", "fashion")) and "holds" in scene_desc:
        head = scene_desc.rsplit("holds", 1)[0].rstrip(", ")
        scene_desc = (
            f"{head} wearing the garment naturally, full body visible, "
            f"garment clearly in frame and fitting naturally. "
            f"Warm natural window lighting."
        )

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
        "model_action": WEARABLE_IMAGE_ACTION if _is_wearable_category(category) else style_info.get("model_action", "",),
        "camera": style_info.get("camera", ""),
        "vibe": style_info.get("vibe", ""),
        "keywords": style_info.get("keywords", ""),
        "hashtags": ", ".join(profile.get("hashtags", [])),
    }
    if templates.get("master"):
        image_prompt = fill_template(templates["master"], data)
        negative = templates.get("negative", "")
    elif _used_media_img:
        # Gemini media generation already produced a complete, non-conflicting
        # image_prompt (action + single setting + lighting). Do NOT append the
        # STYLE_MAP model_action/camera/vibe — that would duplicate/conflict.
        image_prompt = (
            f"{scene_desc}. "
            f"natural composition, warm inviting atmosphere. "
            f"The product is clearly in frame. "
            f"soft natural lighting. "
            f"--ar 9:16"
        )
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
    # model_action templates may embed a hardcoded 'Ethnic Thai woman' —
    # force every gender word to match the resolved target gender.
    image_prompt = _normalize_gender_in_description(image_prompt, gender_en)
    # Strip any hardcoded ethnicity from the engine action — the ethnicity
    # is injected via the country field (single source of truth).
    image_prompt = re.sub(r'Model\s+with\s+[^,]+features', '', image_prompt, flags=re.IGNORECASE).strip()
    image_prompt = re.sub(r'^,\s*', '', image_prompt).strip()

    # ── Ethnicity + age guard (safety net) ─────────────────────────────
    # Gemini sometimes omits the ethnicity/age even when instructed. The model
    # must always look like a Southeast Asian Thai person at the target age,
    # never a white/foreign model. If the ethnicity is missing, prepend it.
    if gender_en and not re.search(r'ethnic\s+\w+', image_prompt, re.IGNORECASE):
        age_guard = f", {model_age} years old" if model_age else ""
        _eth_label, _eth_features = _country_ethnicity(profile.get("country", ""))
        image_prompt = f"An {_eth_label} {gender_en}{age_guard}, {_eth_features}. {image_prompt}"

    # ── Age consistency guard ─────────────────────────────────────────
    # Gemini sometimes writes a different age than the resolved target age.
    # Force every "N years old" in the prompt to match _normalized_age so
    # image + video prompts stay consistent.
    if model_age:
        image_prompt = re.sub(
            r'\b\d{1,2}\s+years?\s+old\b',
            f'{model_age} years old',
            image_prompt,
            flags=re.IGNORECASE,
        )

    return image_prompt, negative


def img_desc_sentences(text: str) -> list:
    """Split image_description into sentences."""
    return [s.strip() for s in text.split(".") if s.strip()]


def build_video_prompt(profile: dict, product_name: str, ugc_style: str = "holding") -> str:
    """Generate video prompt for Wan 2.7 img2vid.

    Uses Gemini (via _get_media_prompts_cached) to produce a cinematic,
    narrative video prompt with clear scene, movement, and direction.
    Falls back to the STYLE_MAP-driven template if Gemini fails.
    """
    # Wearable/fashion products → fashion_lookbook (model WEARS the garment, never holds)
    if _is_wearable_category(profile.get("category", "other")):
        style_info = STYLE_MAP.get("fashion_lookbook", STYLE_MAP["holding"])
    else:
        style_info = STYLE_MAP.get(ugc_style, STYLE_MAP["holding"])
    model_gender = profile.get("target_gender")
    env_context = profile.get("env_context", "a modern space")
    category = profile.get("category", "other")

    gender_en = {"female": "woman", "male": "man"}.get(model_gender, "")
    model_age = profile.get("_normalized_age") or _normalize_age(profile.get("target_age", "")) or ""

    # ── Product description (common) ──
    product_appearance = profile.get("product_appearance", "")
    pa_clean = product_appearance
    if pa_clean:
        pa_clean = re.sub(r'^(The\s+)?product\s+(is\s+)?', '', pa_clean, flags=re.IGNORECASE).strip()
        pa_clean = pa_clean[0].lower() + pa_clean[1:] if pa_clean else ""
        pa_clean = re.sub(r'^(a|an)\s+', '', pa_clean, flags=re.IGNORECASE).strip()
        pa_clean = re.sub(r'^the\s+', '', pa_clean, flags=re.IGNORECASE).strip()
        article = "an" if pa_clean[:1].lower() in "aeiou" else "a"
        prod_desc_vid = f"{article} {_thai_safe_truncate(pa_clean, 200)}"
    else:
        prod_desc_vid = product_name

    # ── Try Gemini first (cinematic narrative video prompt) ──
    try:
        _media_img, _media_vid = _get_media_prompts_cached(
            product_name=product_name,
            product_appearance=pa_clean or product_name,
            usage_action=profile.get("usage_action", ""),
            ugc_style=ugc_style,
            category=category,
            model_gender=gender_en,
            model_age=str(model_age) if model_age else "",
            env_context=env_context,
            features=profile.get("features", ""),
            country=profile.get("country", ""),
        )
        if _media_vid and len(_media_vid) > 20:
            # Gemini produced a complete narrative video prompt — use it.
            video_prompt = _media_vid
            video_prompt = re.sub(r'\s+', ' ', video_prompt).strip()
            video_prompt = _normalize_gender_in_description(video_prompt, gender_en)
            # ── Age consistency guard ─────────────────────────────────
            # Gemini sometimes writes a different age than the resolved target
            # age. Force every "N years old" to match _normalized_age so the
            # image + video prompts stay consistent.
            if model_age:
                video_prompt = re.sub(
                    r'\b\d{1,2}\s+years?\s+old\b',
                    f'{model_age} years old',
                    video_prompt,
                    flags=re.IGNORECASE,
                )
            return video_prompt
    except Exception as e:
        logger.warning(f"Gemini video prompt generation failed, falling back to template: {e}")

    # ── Fallback: STYLE_MAP-driven template ──
    age_seg = f" {model_age} years old" if model_age else ""
    _eth_label, _eth_features = _country_ethnicity(profile.get("country", ""))
    model_intro = f"{_eth_label} {gender_en}{age_seg}"

    _style_action = style_info.get("model_action", "").strip()
    _style_motion = style_info.get("video_motion", "").strip()
    _style_action = re.sub(r'Model\s+with\s+[^,]+features', '', _style_action, flags=re.IGNORECASE).strip()
    _style_action = re.sub(r'^,\s*', '', _style_action).strip()
    if _style_action:
        action = f"{model_intro} {_style_action}, product: {prod_desc_vid or product_name}"
        if _style_motion and _style_motion.lower() not in action.lower():
            action += f", {_style_motion}"
    else:
        action = f"{model_intro} gently holding {prod_desc_vid or product_name} in both hands, showing product to camera with slight slow rotation"

    video_prompt = f"{env_context.rstrip('.')}. {action} soft natural lighting, warm atmosphere. 9:16 portrait, smooth natural motion"
    video_prompt = re.sub(r'\s+', ' ', video_prompt).strip()
    video_prompt = _normalize_gender_in_description(video_prompt, gender_en)
    return video_prompt

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
    features: str = "",
    keywords: Optional[List[str]] = None,
    ugc_style: str = "holding",
    product_id: str = "",
    price: float = 0.0,
    product_image: str = "",
    target_gender: str = "",
    category: str = "",
    product_category: str = "",
    target_duration: int = 15,
    target_age: str = "",
    country: str = "",
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
    profile = analyze_product(
        product_name, description, keywords,
        target_duration=target_duration,
        features=features,
        target_age=target_age,
        ugc_style=ugc_style,
        category=category,
        target_gender=target_gender,
        product_id=product_id,
        price=price,
        product_category=product_category,
        country=country,
    )

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
                     "image_description", "features", "usage_action"]:
            if key in vision_profile and vision_profile[key]:
                profile[key] = vision_profile[key]
        # product_type from vision overwrites text analysis
        if "product_type" in vision_profile and vision_profile["product_type"]:
            profile["product_type"] = vision_profile["product_type"]
        if "colors" in vision_profile and vision_profile["colors"]:
            profile["colors"] = vision_profile["colors"]

    # Ensure target_gender is explicitly resolved
    if profile.get("target_gender", "") in ("", None):
        profile["target_gender"] = ""

    # Override with explicit params if provided
    # Override with explicit target_gender if provided
    if not target_gender:
        # Auto-detect gender from product name/description — LLM may guess wrong
        # (e.g. "เบลเซอร์ผู้ชาย" → female) so the product text is authoritative.
        # "สตรีท" (street) contains substring "สตรี" → normalize first so
        # streetwear is NOT misclassified as female.
        combined = (f"{product_name} {description}").lower().replace("สตรีท", "street")
        if any(w in combined for w in ("ผู้ชาย", "ชาย", "gentleman", "for men", "mens")):
            target_gender = "male"
        elif any(w in combined for w in ("ผู้หญิง", "หญิง", "lady", "ladies", "sukhon", "สุภาพสตรี", "for women", "womens", "สตรี")):
            target_gender = "female"
        elif not target_gender:
            # No gender signal in product data → keep empty, never invent
            target_gender = ""
    if target_gender:
        profile["target_gender"] = target_gender
    if target_age:
        profile["target_age"] = target_age

    if category:
        profile["category"] = category
    if product_category:
        profile["product_category"] = product_category
    
    # Step 3: Inject persona for diversity
    persona = _select_persona(profile.get("category", "other"), product_name, profile.get("target_gender"))
    profile = _apply_persona_to_profile(profile, persona)
    logger.info(f"Persona: {persona.get('vibe', '')} | Env: {persona.get('environment', '')}")

    # Sync age — normalize once so image + video prompt ages match
    profile["_normalized_age"] = _normalize_age(profile.get("target_age", ""))

    # Step 4: Clear Gemini cache for fresh prompts, then build
    _gemini_prompt_cache.clear()
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
        "price": price,
        "product_category": product_category,
        "router_config": router_config,
        "analysis": {
            "category": profile.get("category", "other"),
            "target_gender": profile.get("target_gender", ""),
            "target_age": profile.get("target_age", ""),
            "price": profile.get("price") or price,
            "product_id": profile.get("product_id") or product_id,
            "product_category": profile.get("product_category") or product_category,
            "target_audience": profile.get("target_audience", ""),
            "setting": profile.get("setting", ""),
            "customer_problem": profile.get("customer_problem", ""),
            "main_benefit": profile.get("main_benefit", ""),
            "hashtags": profile.get("hashtags", []),
            "image_description": profile.get("image_description", ""),
            "env_context": profile.get("env_context", ""),
            "product_appearance": profile.get("product_appearance", ""),
            "features": profile.get("features", ""),
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
            "total_duration": timing_validation.get("total_duration", 15),
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
    
    logger.info(f"Prompt built for [{_thai_safe_truncate(product_name, 30)}]: img={len(image_prompt)}ch, vid={len(video_prompt)}ch")
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

_THAI_DANGLING_CHARS = set("\u0e40\u0e41\u0e42\u0e43\u0e44\u0e34\u0e35\u0e36\u0e37\u0e38\u0e39\u0e3a\u0e48\u0e49\u0e4a\u0e4b\u0e4c\u0e4d\u0e4e")
_THAI_CONSONANTS = set(chr(c) for c in range(0x0E01, 0x0E2F))  # ก..ฮ

def _thai_safe_truncate(text: str, max_chars: int, extra_buffer: int = 5) -> str:
    """Truncate text to max_chars without cutting a Thai word in half.

    Strategy:
      1. If the cut point splits a Thai word, extend to the next word boundary
         (whitespace / punctuation / end of word) so the word stays whole.
      2. Never leave a dangling Thai leading vowel / tone mark / vowel mark
         as the final character.
      3. For mixed Latin text, prefer a whitespace boundary.
    """
    if not text or len(text) <= max_chars:
        return text

    cut = max_chars
    if 0 < cut < len(text):
        prev_char = text[cut - 1]
        next_char = text[cut]
        # Mid-word cut: a Thai consonant/vowel-mark sits right before the cut
        # and more Thai (consonant or vowel mark) follows after it.
        if (
            prev_char in _THAI_CONSONANTS
            and (next_char in _THAI_CONSONANTS or next_char in _THAI_DANGLING_CHARS)
        ) or (
            prev_char in _THAI_DANGLING_CHARS and next_char in _THAI_CONSONANTS
        ):
            # Extend to the next word boundary (whitespace / punctuation / end)
            # so the Thai word is never split mid-word. Cap at a generous limit
            # to avoid runaway growth on very long unbroken strings.
            limit = min(len(text), max_chars + max(extra_buffer, 40))
            while cut < limit and text[cut] not in " \n\t.,;:!?()":
                cut += 1

    # Never leave a dangling Thai vowel / tone mark at the end.
    while cut > 0 and text[cut - 1] in _THAI_DANGLING_CHARS:
        cut -= 1

    # Prefer a whitespace boundary for mixed Latin text.
    min_cut = max_chars * 0.6
    if cut > min_cut:
        last_space = text.rfind(" ", 0, cut)
        if last_space > min_cut:
            cut = last_space
    return text[:cut]
def _trim_to_word(text: str, max_chars: int) -> str:
    """Trim text to max_chars without cutting mid-word or breaking Thai chars."""
    if not text or len(text) <= max_chars:
        return text
    # Prefer a whitespace boundary so Thai words are never split mid-word.
    # Fall back to _thai_safe_truncate (which extends up to extra_buffer chars)
    # only when no whitespace exists within a reasonable window.
    last_space = text.rfind(" ", 0, max_chars)
    if last_space > max_chars * 0.5:
        return text[:last_space]
    return _thai_safe_truncate(text, max_chars, extra_buffer=12)


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
        candidate = ' '.join(kept) if kept else _thai_safe_truncate(product_name, 30)
        product_short = candidate if len(candidate) <= 35 else ' '.join(kept[:3]) if len(kept) >= 3 else _thai_safe_truncate(product_name, 30)
    
    if len(product_short) < 5:
        product_short = _thai_safe_truncate(product_name, 30)
    
    # Gender-aware Thai register
    target_gender = (profile or {}).get("target_gender", "")
    is_female = target_gender in ("female", "woman")
    reg_hook = "คะ" if is_female else "ครับ"
    reg_val = "ค่ะ" if is_female else "ครับ"
    
    # Use customer_problem + main_benefit from Gemini analysis when available
    customer_problem = profile.get("customer_problem", "") if profile else ""
    main_benefit = profile.get("main_benefit", "") if profile else ""
    
    if customer_problem and main_benefit and len(customer_problem) > 5:
        # Shorten problem and benefit for natural spoken Thai
        hook_text = _trim_to_word(customer_problem, 40)
        # Value segment: do NOT repeat the product name (it was already said in
        # the hook). Strip the product name (and its reordered tokens) from
        # main_benefit so the script doesn't sound repetitive.
        benefit = _trim_to_word(main_benefit, 45)
        # Collect distinctive product-name tokens (len>=3) to strip from benefit.
        name_tokens = []
        for name in (product_short, product_name):
            for tok in name.split():
                tok = tok.strip("(),.!")
                if len(tok) >= 3 and tok not in name_tokens:
                    name_tokens.append(tok)
        for tok in sorted(name_tokens, key=len, reverse=True):
            benefit = benefit.replace(tok, "")
        benefit = re.sub(r'\s+', ' ', benefit).strip(" ,")
        value_text = f"{product_short} {benefit}" if benefit else product_short
    elif category in ("home", "electronics", "tools"):
        hook_text = f"เจอปัญหานี้อยู่ใช่ไหม{reg_hook}"
        value_text = f"{product_short} ตัวนี้ช่วยได้เยอะเลย{reg_val}"
    elif "blush" in category.lower() or "cheek" in category.lower():
        hook_text = f"อยากหน้าสดใส ดูมีมิติใช่ไหม{reg_hook}"
        value_text = f"{product_short} เติมแก้มสวยเป็นธรรมชาติ{reg_val}"
    elif "lip" in category.lower():
        hook_text = f"อยากปากฉ่ำวาว สวยทนนานไหม{reg_hook}"
        value_text = f"{product_short} ทาแล้วปากชุ่มชื้น สวยปัง{reg_val}"
    elif "mask" in category.lower() or "facial" in category.lower():
        hook_text = f"ผิวแห้ง หมองคล้ำ ต้องลองตัวนี้{reg_hook}"
        value_text = f"{product_short} ช่วยบำรุงผิวชุ่มชื้นฉ่ำน้ำ{reg_val}"
    elif "serum" in category.lower() or "moisturizer" in category.lower():
        hook_text = f"อยากผิวใส ชุ่มชื้น แนะนำเลย{reg_hook}"
        value_text = f"{product_short} ซึมไว ไม่เหนอะหนะ{reg_val}"
    elif "concealer" in category.lower() or "corrector" in category.lower():
        hook_text = f"กลบรอยใต้ตา เนียนกริบ{reg_hook}"
        value_text = f"{product_short} ปกปิดเนียนสวย ไม่ตกร่อง{reg_val}"
    else:
        hook_text = f"ของดีต้องบอกต่อ{reg_hook}"
        value_text = f"{product_short} ใช้งานง่าย คุ้มค่ามาก{reg_val}"
    cta_text = f"สนใจพิกัดในตะกร้าซ้ายล่างได้เลย{reg_val}"
    
    target_dur_sec = 12
    if profile and profile.get("target_duration"):
        try:
            target_dur_sec = int(str(profile.get("target_duration")).replace("s", ""))
        except ValueError:
            target_dur_sec = 15

    # Scale segment timing proportionally based on target duration
    # Hook (~25%), Value (~50%), CTA (~25%)
    hook_dur = max(2, int(target_dur_sec * 0.25))
    cta_dur = max(2, int(target_dur_sec * 0.25))
    value_dur = target_dur_sec - hook_dur - cta_dur

    segments = [
        {"key": "hook", "text": hook_text, "duration_sec": hook_dur, "timing": f"0-{hook_dur}"},
        {"key": "value", "text": value_text, "duration_sec": value_dur, "timing": f"{hook_dur}-{hook_dur+value_dur}"},
        {"key": "cta", "text": cta_text, "duration_sec": cta_dur, "timing": f"{hook_dur+value_dur}-{target_dur_sec}"},
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
        "total_duration": target_dur_sec,
    }

# ─── Gemini Prompt Generation (for product_usage style) ──────────
# Cache: same product+age within same request returns cached result
_gemini_prompt_cache = {}

# Cache for Step-2 media generation (usage_action-driven). Keyed by
# (product_name, usage_action) so build_image_prompt and build_video_prompt
# share ONE Gemini call per product instead of two.
_media_prompt_cache = {}


def _get_media_prompts_cached(
    product_name: str,
    product_appearance: str,
    usage_action: str,
    ugc_style: str,
    category: str,
    model_gender: str,
    model_age: str = "",
    env_context: str = "",
    features: str = "",
    country: str = "",
) -> tuple:
    """Cached wrapper around _generate_media_prompts (Step 2).

    build_image_prompt and build_video_prompt both call this; the cache
    ensures only ONE Gemini call happens per (product, usage_action).
    Returns (image_prompt, video_prompt).
    """
    _cache_key = (product_name, usage_action, ugc_style)
    if _cache_key in _media_prompt_cache:
        return _media_prompt_cache[_cache_key]
    result = _generate_media_prompts(
        product_name=product_name,
        product_appearance=product_appearance,
        usage_action=usage_action,
        ugc_style=ugc_style,
        category=category,
        model_gender=model_gender,
        model_age=model_age,
        env_context=env_context,
        features=features,
        country=country,
    )
    _media_prompt_cache[_cache_key] = result
    return result

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
    gender_en = {"female": "woman", "male": "man"}.get(model_gender, "")
    
    # Cache by product name + age — avoid duplicate calls within same request
    _cache_key = (product_name, model_age)
    cached = _gemini_prompt_cache.get(_cache_key)
    if cached is not None:
        return cached
    
    # Clean appearance
    pa = product_appearance or ""
    if pa:
        pa = re.sub(r'^(The\s+)?product\s+(is\s+)?', '', pa, flags=re.IGNORECASE).strip()
        pa = re.sub(r'^(a|an)\s+', '', pa, flags=re.IGNORECASE).strip()
    
    feat_str = ""
    if isinstance(features, list):
        feat_str = "; ".join(f.strip() for f in features if f.strip())
    elif isinstance(features, str) and features:
        feat_str = _thai_safe_truncate(features, 200)
    
    # Wan 2.7 is a diffusion model — it ONLY understands literal visual descriptions
    system_prompt = (
        "You write prompts for Wan 2.7, a DIFFUSION video model.\n"
        "Wan 2.7 CANNOT understand abstract concepts, product mechanics, or cause/effect.\n"
        "Describe ONLY what is VISUALLY seen — no concepts like 'sensor detects' or 'automatically'.\n\n"
        "CRITICAL RULES:\n"
        "1. Describe ONLY concrete visual actions (moves, stops, places, lifts, presses, turns).\n"
        "2. Be EXTREMELY specific about hand/body POSITION relative to product:\n"
        "   - Use BELOW the nozzle, ABOVE the button, BESIDE the product, IN FRONT OF the camera.\n"
        "3. Product is FIXED/MOUNTED on wall or table — DO NOT have person hold the product unless it's a handheld product (phone, bottle, tool). For FASHION/APPAREL, the product is ALREADY WORN.\n"
        "4. FORBIDDEN WORDS: detects, automatically, intelligently, senses, recognizes, responds, or catalog jargon like \"feature\".\n"
        "5. FIRST-FRAME CONSTRAINT (CRITICAL): This video uses Wan 2.7 img2vid which sees a SINGLE still image of the model already holding/positioned with the product. The video motion MUST start from THAT pose and move forward naturally. \n"
        "6. FOR HARD GOODS/BEAUTY: Describe NATURAL USE moving forward (uncap, squeeze, press). Show DIRECT APPLICATION (e.g., 'hand brings lipstick to lips').\n"
        "7. FOR FASHION/APPAREL (CRITICAL AVOIDANCE): NEVER instruct hands to touch, pull, adjust, or smooth the clothing (this causes severe hand/body mutations). Use MACRO-MOVEMENTS ONLY (e.g., 'model stands still and turns gracefully', 'the fabric sways and drapes naturally in the breeze'). \n"
        "8. IMAGE_PROMPT: include FULL look details (southeast asian thai face, porcelain skin, monolid eyes, clothing, hair) since the model is generated from scratch.\n"
        "9. VIDEO_PROMPT: do NOT re-describe the face/skin/outfit in detail — the first frame shows the person; keep only 'Thai " + "woman/man" + " + age' there.\n"
        f"   Age: {model_age or 'unspecified'}; gender: {gender_en or 'unspecified'}; clothing: {clothing}; hair: {hair}\n\n"
        "IMAGE_PROMPT (under 80 words): Still scene. Product is visible, woman is positioned near it (or wearing it).\n"
        "VIDEO_PROMPT (under 130 words): Step-by-step visual actions. Use BELOW/ABOVE/BESIDE for hard goods.\n"
        "Do NOT add negative instructions or aspect ratios.\n"
        "Output format:\n"
        "IMAGE_PROMPT: ...\n"
        "VIDEO_PROMPT: ..."
    )
    
    # Build the product description block — emphasize physical placement
    mount_hint = ""
    # Check for wall/table mount indicators
    pa_lower = (pa + " " + product_name + " " + feat_str).lower() if pa else product_name.lower()
    if any(w in pa_lower for w in ["wall", "mount", "sensor", "dispenser", "mounted"]):
        mount_hint = "\nIMPORTANT: This product is FIXED on wall or table. Person does NOT hold it. Describe it in place."
    elif any(w in pa_lower for w in ["bottle", "jar", "tube", "dropper"]):
        mount_hint = "\nThis product is HANDHELD and ALREADY in the person's hand in the first frame. Describe NATURAL USE: the product is ready for immediate use — uncapping/squeezing/pumping are fine when the design requires. Hand moves the product toward the target and applies."
    
    product_block = f"Product: {product_name}\nAppearance: {_thai_safe_truncate(pa, 350)}\n"
    if feat_str:
        product_block += f"Features: {_thai_safe_truncate(feat_str, 200)}\n"
    product_block += f"Setting: {_thai_safe_truncate(env_context, 120)}\n"
    product_block += mount_hint
    model_seg = f"{model_age}yo " if model_age else ""
    product_block += f"\nModel: {model_seg}{gender_en}, {clothing}, {hair}\n"
    
    user_text = f"{product_block}\nGenerate prompts for Wan 2.7:"
    
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
        
        # Cache result
        _gemini_prompt_cache[_cache_key] = (image_prompt, video_prompt)
        return (image_prompt, video_prompt)
    except Exception as e:
        logger.error(f"Gemini prompt generation failed: {e}")
        _gemini_prompt_cache[_cache_key] = ("", "")
        return ("", "")
