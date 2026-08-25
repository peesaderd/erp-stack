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

# ─── JSON Prompt Sources (Data-Driven) ───────────────────────────
import json as _json
import random as _random
import hashlib as _hashlib
from pathlib import Path as _Path
_PROMPT_SOURCES = None
_UGC_STYLES = None

# ─── SSOT: UGC styles & combos (ugc_styles.json) ─────────────────
# Single source of truth for style prompt_anchor / has_person / shots.
# Moved out of ugc_config.py (Python dict) into ugc_styles.json so edits
# to the schema auto-reflect in the Prodia video/image anchors. This is the
# ONLY entry point — do NOT add a second UGC_STYLES copy elsewhere.
def _load_ugc_styles():
    """Load UGC_STYLES + UGC_COMBOS from ugc_styles.json (SSOT).
    
    Cache after first read. Raises if the file is missing/malformed so we
    break loudly rather than silently generate with an empty anchor map.
    """
    global _UGC_STYLES
    if _UGC_STYLES is None:
        src_path = _Path(__file__).parent / "ugc_styles.json"
        with open(src_path) as f:
            _UGC_STYLES = _json.load(f)
        # Validate the keys prompt_builder depends on.
        if "UGC_STYLES" not in _UGC_STYLES:
            raise ValueError("ugc_styles.json: missing 'UGC_STYLES' — add it")
    return _UGC_STYLES


def _is_no_human_style(ugc_style: str) -> bool:
    """True when the style's has_person flag (SSOT ugc_styles.json) is False.

    Used to route no-human styles (currently product_demo + pov) to the
    product-only single 9:16 + no-human video branch instead of the holding/
    talking template that would inject a person into the frame. Reads the SSOT
    flag so we never hardcode a second style list here (single source of truth).
    Falls back to False (assume has a person) if the style is unknown, so we
    never accidentally drop the person from a style that needs one.
    """
    style = (ugc_style or "").strip().lower()
    try:
        _styles = _load_ugc_styles().get("UGC_STYLES", {})
        entry = _styles.get(style, {}) or {}
        return entry.get("has_person") is False
    except Exception:
        return False


def _load_prompt_sources():
    global _PROMPT_SOURCES
    if _PROMPT_SOURCES is None:
        src_path = _Path(__file__).parent / "prompt_sources.json"
        with open(src_path) as f:
            _PROMPT_SOURCES = _json.load(f)
    return _PROMPT_SOURCES


def _ai_select(category: str, subcategory: str, gender: str, product_name: str, loop_count: int = 0) -> dict:
    """AI-select variables from category_mapping. Deterministic with seed+loop_count.
    
    Fallback chain: subcategory → category → "other"
    Returns: {scene, action, camera, lighting, mood, persona}
    """
    sources = _load_prompt_sources()
    cat_map = sources.get("category_mapping", {})
    
    # Fallback chain: subcategory → category → "other"
    sub = cat_map.get(category, {}).get(subcategory, None)
    cat_default = cat_map.get(category, {}).get("default", {})
    other = cat_map.get("other", {}).get("default", {})
    
    mapping = sub or cat_default or other
    
    # Deterministic seed: hash(product_name) + loop_count for variation
    base_seed = int(_hashlib.md5(product_name.encode()).hexdigest(), 16) % 1000000
    seed = (base_seed + loop_count) % 1000000
    rng = _random.Random(seed)

    # Strict JSON-driven: every required field must exist in prompt_sources.json.
    # No hardcoded fallback values — if a category is missing a key we raise a
    # clear error pointing at the JSON (single source of truth).
    required = ("scene", "action", "camera", "lighting", "mood")
    missing = [k for k in required if not mapping.get(k)]
    if missing:
        raise ValueError(
            f"prompt_sources.json category_mapping['{category}'] missing required "
            f"keys {missing} (sub={subcategory!r}) — add them"
        )
    scene = rng.choice(mapping["scene"])
    action = mapping["action"]
    camera = mapping["camera"]
    lighting = mapping["lighting"]
    mood = mapping["mood"]
    
    # Select persona matching demographic
    persona = _select_persona_fit(category, subcategory, gender, rng)
    
    return {
        "scene": scene,
        "action": action,
        "camera": camera,
        "lighting": lighting,
        "mood": mood,
        "persona": persona,
    }


def _select_persona_fit(category: str, subcategory: str, gender: str, rng) -> dict:
    """Select persona that fits the product demographic. Uses category_mapping first."""
    sources = _load_prompt_sources()
    personas = sources.get("personas", {})
    gender_key = "female" if gender.lower() in ("female", "woman", "หญิง") else "male"
    pool = personas.get(gender_key, personas.get("unisex", []))
    
    if not pool:
        return {"gender": "woman", "age": 25}
    
    p = rng.choice(pool)
    age = rng.randint(p["age_range"][0], p["age_range"][1])
    gender_word = "woman" if gender_key == "female" else "man"
    
    return {
        "ethnicity": p.get("ethnicity", "Thai"),
        "gender": gender_word,
        "age": age,
        "skin_tone": p.get("skin_tone", "medium"),
    }


def _pick_end_scene(category="other", subcategory=None, profile=None):
    """Pick a result-specific end scene from the SSOT Prompt Library (prompt_sources.json).

    Resolution chain (single source of truth, data-driven):
      1. subcategory (result-specific key, e.g. underarm_cream) → most precise end scene
      2. category → generic per-category pool
      3. "other" → final fallback

    The scene is further filtered by profile['body_part'] (when present) so the
    end scene FOCUSES on the same body area the payload declared — it must NOT
    drift to a different part (e.g. a whole-body / hand cream must never end on
    belly/waist/thighs). Falls back to whole pool pick when no body_part set.

    Returns a full blueprint dict: {scene, camera, outfit, result_focus,
    expression, product_placement}. Legacy pools (category) only have
    {scene, camera} — the missing keys are filled with sane defaults so
    callers can rely on the full shape.
    """
    sources = _load_prompt_sources()
    end_scenes = sources.get("end_scenes", {})

    # Resolve pool: subcategory (result library) → category → other
    pool = None
    if subcategory and subcategory in end_scenes:
        pool = end_scenes.get(subcategory)
    if not pool and category in end_scenes:
        pool = end_scenes.get(category)
    if not pool:
        pool = end_scenes.get("other", [])

    if not pool:
        return {
            "scene": "product prominently displayed",
            "camera": "medium shot",
            "outfit": "",
            "result_focus": "",
            "expression": "",
            "product_placement": "",
        }

    # ── Body-part-first resolution (owner 2026-08-24): when the payload carries
    # body_part (or the audience is pregnancy), the end scene FOLLOWS that part
    # DIRECTLY — deterministic, no bucket lottery, no filter-then-fallback.
    # ALL scene wording lives in prompt_sources.json
    # ssot_extras.body_part_end_scenes (SSOT) — this file holds only alias /
    # decision logic, zero hardcoded scene text. Only products WITHOUT a known
    # part fall through to the legacy subcategory → category → other pick.
    bp = ""
    st = ""
    if isinstance(profile, dict):
        bp = (profile.get("body_part") or "").strip().lower()
        st = (profile.get("special_target") or "").strip().lower()

    chosen = None
    if bp or st in ("pregnant", "pregnancy", "maternity"):
        bp_scenes = _load_ssot_extras()["body_part_end_scenes"]
        bp_norm = bp.replace(" ", "-").replace("_", "-")
        bp_key = {"hands": "hand", "whole-body": "hand", "body": "hand"}.get(bp_norm, bp_norm)
        if bp_key in bp_scenes:
            chosen = bp_scenes[bp_key]
        elif st in ("pregnant", "pregnancy", "maternity"):
            chosen = bp_scenes["belly"]

    if chosen is not None:
        return {
            "scene": chosen.get("scene", "product prominently displayed"),
            "camera": chosen.get("camera", "medium shot"),
            "outfit": chosen.get("outfit", ""),
            "result_focus": chosen.get("result_focus", ""),
            "expression": chosen.get("expression", "satisfied smile"),
            "product_placement": chosen.get("product_placement", "product placed visibly in frame"),
        }

    chosen = _random.choice(pool)
    # Normalize to the full blueprint shape (legacy category entries lack the
    # result-specific keys — fill defaults so callers never KeyError).
    return {
        "scene": chosen.get("scene", "product prominently displayed"),
        "camera": chosen.get("camera", "medium shot"),
        "outfit": chosen.get("outfit", ""),
        "result_focus": chosen.get("result_focus", ""),
        "expression": chosen.get("expression", "satisfied smile"),
        "product_placement": chosen.get("product_placement", "product placed visibly in frame"),
    }


def _pick_transition():
    sources = _load_prompt_sources()
    transitions = sources.get("transitions")
    if not isinstance(transitions, list) or not transitions:
        raise ValueError("prompt_sources.json: missing or empty 'transitions' list — add it")
    return _random.choice(transitions)


def _clean_product_name_for_video(product_name: str) -> str:
    """Return generic 'product' for video prompts.
    
    Wan 2.7 may interpret product names as instructions.
    The reference image already shows the actual product.
    """
    return "product"


def _generate_default_hashtags(product_name: str, description: str = "") -> list:
    """Generate diverse default hashtags from product name and description."""
    hashtags = []
    clean_name = product_name.replace(" ", "").replace("【", "").replace("】", "").replace("[", "").replace("]", "")
    if clean_name:
        hashtags.append(clean_name[:20])
    
    desc_lower = (description or "").lower()
    category_hashtags = {
        "beauty": ["skincare", "beauty", "glowing", "whitening"],
        "skin": ["skincare", "skin", "glowing", "moisturizer"],
        "food": ["food", "yummy", "delicious", "tasty"],
        "fashion": ["fashion", "style", "outfit", "ootd"],
        "tech": ["tech", "gadget", "smart", "innovative"],
        "health": ["health", "wellness", "fitness", "healthy"],
        "home": ["home", "decor", "interior", "cozy"],
    }
    
    for category, tags in category_hashtags.items():
        if category in desc_lower:
            hashtags.extend(tags[:3])
            break
    
    general_tags = ["trending", "viral", "fyp", "foryou"]
    while len(hashtags) < 5:
        for tag in general_tags:
            if tag not in hashtags and len(hashtags) < 5:
                hashtags.append(tag)
        break
    
    return hashtags[:5]
    sources = _load_prompt_sources()

def _clean_product_name_for_video(product_name: str) -> str:
    """Return generic 'product' for video prompts.
    
    Wan 2.7 may interpret product names as instructions.
    The reference image already shows the actual product.
    """
    return "product"


def _generate_default_hashtags(product_name: str, description: str = "") -> list:
    """Generate diverse default hashtags from product name and description."""
    hashtags = []
    
    # Clean product name for hashtag
    clean_name = product_name.replace(" ", "").replace("【", "").replace("】", "").replace("[", "").replace("]", "")
    if clean_name:
        hashtags.append(clean_name[:20])
    
    # Extract category-related hashtags from description
    desc_lower = (description or "").lower()
    category_hashtags = {
        "beauty": ["skincare", "beauty", "glowing", "whitening"],
        "skin": ["skincare", "skin", "glowing", "moisturizer"],
        "food": ["food", "yummy", "delicious", "tasty"],
        "fashion": ["fashion", "style", "outfit", "ootd"],
        "tech": ["tech", "gadget", "smart", "innovative"],
        "health": ["health", "wellness", "fitness", "healthy"],
        "home": ["home", "decor", "interior", "cozy"],
    }
    
    for category, tags in category_hashtags.items():
        if category in desc_lower:
            hashtags.extend(tags[:3])
            break
    
    # Add general hashtags if not enough
    general_tags = ["trending", "viral", "fyp", "foryou"]
    while len(hashtags) < 5:
        for tag in general_tags:
            if tag not in hashtags and len(hashtags) < 5:
                hashtags.append(tag)
        break
    
    return hashtags[:5]


def analyze_product(product_name: str, description: str = "", keywords: Optional[List[str]] = None, target_duration: int = 15, features: str = "") -> dict:
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
        target_duration=target_duration,
    )
    
    # Get product profile from Gemini analysis
    feat_text = f"\nคุณสมบัติเด่น (Features): {features}" if features else ""
    user_text = f"""ชื่อสินค้า: {product_name}{feat_text}
คำอธิบาย: {description if description else 'ไม่มี'}
Keywords: {kw_str}"""

    raw = _call_gemini(PRODUCT_ANALYSIS_SYSTEM, user_text, temperature=0.3, max_output_tokens=1500, response_mime_type="application/json")
    gemini_profile = _extract_json(raw) if raw else None

    if not gemini_profile:
        logger.warning("Gemini analysis failed — using default profile with Router context")
        gender_en = "woman"
        profile = {
            "category": "other",
            "subcategory": "",
            "target_gender": "female",
            "target_age": "25-35",
            "target_audience": f"คนที่กำลังมองหา{product_name[:20]}",
            "setting": "clean modern lifestyle setting",
            "customer_problem": f"ปัญหาที่{product_name[:30]}นี้ช่วยแก้",
            "main_benefit": f"คุณประโยชน์ของ{product_name[:20]}",
            "packaging_action": "generic_hold",
            "action_desc": "ถือสินค้าและใช้งานทั่วไป",
            "hashtags": keywords[:5] if len(keywords) >= 5 else _generate_default_hashtags(product_name, description),
            # Extract basic features from description when Gemini fails
            "features": _extract_features_from_description(description) if description else "",
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
            default_tag = product_name.replace(" ", "").replace("\n", "").replace("【", "").replace("】", "").replace("[", "").replace("]", "")[:20]
            if default_tag not in h:
                h.append(default_tag)
            else:
                # Add a category-specific tag instead of duplicate
                category = profile.get("category", "other")
                fallback_tags = {
                    "beauty": ["skincare", "beauty", "glowing"],
                    "food": ["food", "yummy"],
                    "fashion": ["fashion", "style"],
                    "tech": ["tech", "gadget"],
                    "health": ["health", "wellness"],
                    "home": ["home", "decor"],
                }
                for tag in fallback_tags.get(category, ["trending", "viral"]):
                    if tag not in h and len(h) < 5:
                        h.append(tag)
                        break
                else:
                    h.append("trending")
        profile["hashtags"] = h[:5]

    if features:
        profile["features"] = features

    # Merge Router Agent insights into profile
    profile["router_config"] = {
        "recipe_type": router_config.get("recipe_type", "pas"),
        "duration": router_config.get("duration", "8s"),
        "visual_style": router_config.get("visual_style", "usage"),
        "persona": router_config.get("persona", "gen_z_trendy"),
        "reason": router_config.get("reason", ""),
    }
    _router_scenes = router_config.get("scenes", [])
    profile["scenes"] = _router_scenes
    # <KEY>: put scenes INSIDE router_config too so P1/P2/P4 readers
    # (which read router_config.scenes) activate on the real pipeline.
    if isinstance(_router_scenes, list) and len(_router_scenes) >= 2:
        profile["router_config"]["scenes"] = _router_scenes

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


def _image_prompt_readable(image_prompt: str) -> str:
    """Return a line-broken version of the single 9:16 image prompt for
    readability (display only). Wan/image API still uses the single-line
    `image_prompt`. Breaks at 'Main scene', 'End scene', 'Featured', and
    'Product:' boundaries without emitting any panel wording."""
    if not image_prompt:
        return image_prompt
    rebuilt = (
        image_prompt
        .replace("Main scene: ", "\nMain scene: ")
        .replace("End scene: ", "\nEnd scene: ")
        .replace("Featured: ", "\nFeatured: ")
        .replace("Product: ", "\nProduct: ")
    )
    rebuilt = re.sub(r"\n{2,}", "\n", rebuilt)
    return rebuilt.strip()


def _clean_brand_name(product_name: str) -> str:
    """Extract a short latin brand token from the product name for cover logo text.
    Returns e.g. 'Dr.PONG' from '(Best Seller) Dr.PONG เซตคู่ Triple C + Gluta 250'.
    Falls back to '' if nothing usable (pure Thai / too short)."""
    import re
    # Drop Thai chars + bracketed promo prefixes, then split into individual words.
    cleaned = re.sub(r"[\u0e00-\u0e7f\[\]()（）【】]+", " ", product_name or "")
    words = cleaned.split()
    # Skip generic / promo / quantity words (case-insensitive).
    skip = {"set", "kit", "pack", "bottle", "bottles", "vitamin", "vitamins",
            "supplement", "supplements", "gluta", "triple", "plus", "the", "and",
            "dr", "official", "store", "best", "seller", "bestseller", "1000", "250",
            "care", "skin", "health", "smart", "c", "cc", "vc"}
    # 1) Prefer a token with an uppercase letter + a digit or dot (brand code e.g. Dr.PONG).
    for w in words:
        core = w.strip('.,:;+-&()').strip()
        if not core or core.lower() in skip:
            continue
        if any(ch.isupper() for ch in core) and (any(ch.isdigit() for ch in core) or '.' in core):
            return core
    # 2) Fallback: first token with an uppercase letter that isn't a generic word.
    for w in words:
        core = w.strip('.,:;+-&()').strip()
        if not core or core.lower() in skip:
            continue
        if any(ch.isupper() for ch in core) and len(core) >= 3:
            return core
    return ""


def _cover_product_desc(profile: dict, product_name: str) -> str:
    """Build a cover-page product description for the single 9:16 frame.

    The image opens as a clean commercial cover — NOT a raw "exactly as shown in
    reference" (that made the model cram the product photo in whole and clip the
    label text). Tell the model to design a clean commercial cover using the
    brand from the reference, with the product(s) placed on it as a styled shot.
    """
    appearance = (profile or {}).get("product_appearance", "") or ""
    brand = _clean_brand_name(product_name)
    # Owner: NO 'OFFICIAL STORE' watermark — the model keeps painting that text
    # onto product/background areas and it looks cluttered/unwanted. Keep only a
    # subtle brand logo; instruct the model NOT to add any invented text/captions.
    logo = f"a subtle '{brand}' logo in the upper corner" if brand else "no extra text or logos"
    # Design a cover, don't copy the reference wholesale. Reference defines the
    # product/brand only; the model composes the layout so text stays legible.
    # Use the cleaned brand so the cover label matches the actual product.
    # NO invented text: brand text only from the real product label, never add
    # words like OFFICIAL STORE, BEST, 100%, etc. (owner: those leak onto the image).
    pair_desc = (
        "designed as a clean studio product cover featuring the product(s) from "
        "the reference image, crisp unclipped labels; render every item, label "
        "and variant that appears, laid out neatly side by side; do not add any "
        "invented text or captions beyond what is on the real product label"
    )
    return (
        f"clean professional commercial product cover page: "
        f"{pair_desc}; {logo}"
    )


def build_image_prompt(profile: dict, product_name: str, ugc_style: str = "holding", loop_count: int = 0) -> tuple:
    """Generate a single vertical 9:16 image prompt.

    Owner direction (2026-08-24): ALWAYS one portrait 9:16 frame. Cover +
    model/product + result composition are folded into ONE continuous frame
    so the first-frame (Nano Banana) quality stays high and matches the video.
    Uses _ai_select() for scene/action/camera/lighting from category_mapping,
    plus product_appearance / colors from Mistral analysis (P3).
    """
    model_gender = profile.get("target_gender", "female")
    category = profile.get("category", "other")
    subcategory = profile.get("subcategory", "")

    # AI select from category_mapping
    selected = _ai_select(category, subcategory, model_gender, product_name, loop_count)

    scene = selected["scene"]
    action = selected["action"]
    lighting = selected["lighting"]

    # ── Model identity: Thai + age + room from profile (fallback to ai_select) ──
    gender_en = {"female": "woman", "male": "man", "unisex": "person"}.get(model_gender, "woman")
    age = profile.get("target_age", "") or ""
    # User rule: use the YOUNGEST age from the range (e.g. "25-50" -> "25") so the
    # demo model looks as young/appealing as the target allows.
    age_young = _youngest_age(age)
    age_desc = f", {age_young} years old" if age_young else ""
    model_desc = f"Thai {gender_en}{age_desc}"
    # Target-audience visibility (owner 2026-08-24): a pregnancy product must
    # show a visibly PREGNANT model — wording from ssot_extras.model_hints
    # (SSOT, no hardcoded text here).
    if ((profile.get("special_target") or "").strip().lower()
            in ("pregnant", "pregnancy", "maternity")):
        _pg_hint = _load_ssot_extras()["model_hints"].get("pregnant") or ""
        if _pg_hint and _pg_hint.lower() not in model_desc.lower():
            model_desc = f"{model_desc}, {_pg_hint}"
    # Room/setting: prefer profile['setting'] (user set), else ai_select scene
    room = (profile.get("setting") or "").strip() or scene
    room_desc = room

    # ── Single 9:16 frame (owner direction 2026-08-24) ──
    # Always output ONE vertical 9:16 image prompt. Composition is folded into
    # a single portrait frame (cover + model/product + end-scene together) so
    # first-frame quality stays high. Do NOT switch to 16:9 / 3-panel.
    router_config = profile.get("router_config", {}) if isinstance(profile, dict) else {}
    scenes = router_config.get("scenes") if isinstance(router_config, dict) else None

    # Build the composition once (shared by all single-frame branches).
    _cover = _cover_product_desc(profile, product_name)
    _app_hint = _apply_hint(subcategory, category, profile)
    if profile.get("special_target", "").strip():
        mid_hint = (
            f"{model_desc} applying the product from the reference image, "
            f"{_app_hint}, {room_desc}, "
            f"medium close-up framing, the product held prominently toward the camera, "
            f"product large in frame and clearly readable"
        )
    else:
        mid_hint = (
            f"{model_desc} holding the product(s) from the reference image, "
            f"bottles facing the camera, {room_desc}, "
            f"medium close-up framing, product held prominently toward the camera, "
            f"product large in frame and clearly readable"
        )
    # Pick the product-specific end scene (SSOT Prompt Library) and bind it to
    # profile so build_video_prompt() reuses the SAME blueprint -> image & video
    # end scenes stay consistent (they no longer drift apart).
    es = _pick_end_scene(category, subcategory=subcategory, profile=profile)
    profile["_end_scene"] = es
    _outfit = f"; outfit: {es['outfit']}" if es.get("outfit") else ""
    _result = es.get("result_focus") or "a happy result"
    _expr = es.get("expression") or "smiling"
    _placement = es.get("product_placement") or "product still in hand"
    result_hint = (
        f"the same {model_desc} from the first part of the frame, wearing the same "
        f"outfit, {_expr}, showing {_result}; {_placement}{_outfit}"
    )
    # Address recipe beats (solve/us/value) from scenes onto the single frame.
    if isinstance(scenes, list):
        for sc in scenes:
            bid = (sc.get("id") or "").lower()
            if bid in ("solve", "us", "value"):
                vis = (sc.get("visual") or "").strip()
                if vis:
                    vis = (vis
                           .replace("{gender_en}", gender_en)
                           .replace("{vp_product}", product_name or "the product")
                           .replace("{apply_hint}", "")
                           .replace("{result_focus}", _result or "a happy result"))
                    mid_hint = f"{model_desc}, {vis}"
                else:
                    mid_hint = _beat_panel_hint(profile, product_name, model_desc, action, room_desc, "middle")

    colors = profile.get("colors", "") or ""
    parts_colors = f"color palette: {', '.join(colors)}. " if colors else ""

    # ── No-human styles (product_demo, pov): single frame with NO person ──
    # Styles whose SSOT has_person flag is False must NOT show a person in frame.
    if _is_no_human_style(ugc_style):
        style_l = (ugc_style or "").strip().lower()
        if style_l == "product_demo":
            feat_hint = (
                f"{product_name} close-up product shot showing label and packaging "
                f"details, product centered on clean background, {room_desc}"
            )
            no_human_clause = (
                "NO humans, NO people, NO hands in frame; pure product photography."
            )
        else:  # pov — first-person, hands visible, no face
            feat_hint = mid_hint  # first-person hands holding the product
            no_human_clause = (
                "First-person POV throughout; no face of the person in frame, "
                "only hands and product visible."
            )
        image_prompt = (
            f"Single vertical 9:16 frame: {_cover}. "
            f"Featured: {feat_hint}. "
            f"Product: show exactly the item(s) from the reference product image — "
            f"render every variant/color that appears in it. "
            f"{parts_colors}{lighting}. "
            f"{no_human_clause} "
            f"NO text, letters, words, labels, logos or watermark. "
            f"Cohesive consistent style, high quality product photography. --ar 9:16"
        )
        logger.info(f"  Image prompt (no-human single 9:16 {style_l}, {len(image_prompt)} chars)")
        image_prompt = _apply_prompt_anchor(ugc_style, image_prompt, product_name)
        negative = "blurry hands, extra fingers, deformed hands, wrong hand position, unrealistic proportions, wrong number of fingers, unclear product details, low quality, low resolution, distorted faces, bad anatomy, incorrect product placement, unrealistic lighting, unrealistic shadows, unrealistic body parts, unrealistic body gestures, unrealistic body movements"
        logger.info(f"  Image prompt (single 9:16 {len(image_prompt)} chars): {image_prompt[:100]}...")
        return image_prompt, negative

    # ── Human styles (holding/usage/review/talking_head/comparison/unboxing) ──
    # Owner 2026-08-24: ONE continuous image. NO "cover / Main scene / End scene"
    # split wording (Nano Banana rendered 3 horizontal panels from that). Build a
    # single coherent scene from payload fields only (model, product, setting,
    # lighting) so the model draws one unbroken 9:16 frame.
    image_prompt = (
        f"Single vertical 9:16 frame, one continuous scene, single camera shot, "
        f"seamless edge to edge, no panels, no split: {mid_hint}; "
        f"{product_name} facing the camera, {parts_colors}{lighting}. "
        f"Show exactly the item(s) from the reference product image — render every "
        f"variant/color that appears in it. NO text, letters, words, labels, logos "
        f"or watermark. Cohesive consistent style, high quality product "
        f"photography. --ar 9:16"
    )
    logger.info(f"  Image prompt (single continuous 9:16 {len(image_prompt)} chars): {image_prompt[:100]}...")
    image_prompt = _apply_prompt_anchor(ugc_style, image_prompt, product_name)
    negative = "blurry hands, extra fingers, deformed hands, wrong hand position, unrealistic proportions, wrong number of fingers, unclear product details, low quality, low resolution, distorted faces, bad anatomy, incorrect product placement, unrealistic lighting, unrealistic shadows, unrealistic body parts, unrealistic body gestures, unrealistic body movements"
    return image_prompt, negative


def _youngest_age(age_str: str) -> str:
    """Return the youngest age from a range string.

    '25-50' -> '25', '25+' -> '25', '30' -> '30', '' -> ''.
    The demo model should look as young as the target audience allows.
    """
    if not age_str:
        return ""
    s = str(age_str).strip().lower()
    # Take the first number found (youngest end of any range).
    m = __import__("re").search(r"\d+", s)
    return m.group(0) if m else ""


def _beat_panel_hint(profile, product_name, model_desc, action, scene, panel_role: str) -> str:
    """Derive a clean English visual hint for the single 9:16 image frame.

    Builds a compact visual instruction Nano Banana understands. Uses the
    product's appearance (Mistral) to add detail. Keeps hints visual (English)
    rather than raw Thai script text.
    model_desc = e.g. 'Thai woman, 25-35 years old' (already age/demographic).
    """
    appearance = (profile or {}).get("product_appearance", "") or ""
    appearance = appearance[:80] if appearance else ""
    # NOTE: no hardcoded item count / tagline here — the reference image is the
    # ground truth for how many variants and which labels/colors to show.
    if panel_role == "cover":
        base = _cover_product_desc(profile, product_name)
    elif panel_role == "middle":
        # Reference-driven (USER TEMPLATE vid_b43d89ab). Compact wording
        # (owner: too wordy) — one clean line, no hardcoded item count.
        # NEW: apply action ONLY for special_target (e.g. pregnancy cream → face/belly);
        # all other products (incl. body_part=whole-body) stay a plain HOLD — "ถือสินค้า
        # พูด" is the fallback when no apply-specific audience is known.
        _app_hint = _apply_hint((profile or {}).get("subcategory"), (profile or {}).get("category"), profile)
        if (profile.get("special_target") or "").strip():
            base = (
                f"{model_desc} applying the product from the reference image, "
                f"{_app_hint}, {scene}, medium close-up framing, product large in frame"
            )
        else:
            base = (
                f"{model_desc} holding the product(s) from the reference image, "
                f"bottles facing the camera, {scene}"
            )
    else:  # result
        base = (
            f"the same {model_desc} from the first part of the frame, wearing the "
            f"same outfit, smiling showing a happy result, product(s) still in hand"
        )
    return base


def img_desc_sentences(text: str) -> list:
    """Split image_description into sentences."""
    return [s.strip() for s in text.split(".") if s.strip()]


def _load_ssot_extras():
    """Load owner-SSOT blocks (2026-08-24) from prompt_sources.json:
    ssot_extras.apply_hints / body_part_end_scenes / model_hints.
    ALL prompt wording lives there (single source of truth) — this file carries
    decision logic ONLY. Strict: a missing/incomplete block raises immediately
    instead of silently falling back to stale behavior."""
    sources = _load_prompt_sources()
    extras = sources.get("ssot_extras") or {}
    required = {
        "apply_hints": [
            "template", "hold_template", "by_body_part", "by_subcategory",
            "by_category", "default_area", "pregnant_unknown_bp_area",
        ],
        "body_part_end_scenes": ["face", "hand", "belly"],
        "model_hints": ["pregnant"],
    }
    missing = []
    for blk, keys in required.items():
        block = extras.get(blk)
        if not isinstance(block, dict):
            missing.append(blk)
            continue
        missing += [f"{blk}.{k}" for k in keys if k not in block]
    if missing:
        raise ValueError(
            f"prompt_sources.json 'ssot_extras' missing keys: {', '.join(missing)}"
        )
    return extras


def _apply_hint(subcategory=None, category=None, profile=None):
    """BEAT 2 'apply' action - concise, no squeeze/cap/scoop (Wan 2.7 warps).

    Decision order (logic ONLY — every English phrase comes from
    prompt_sources.json ssot_extras.apply_hints):
      1. special_target=pregnant → FOLLOW body_part (face→face, hand-ish→hand;
         unknown part → pregnant_unknown_bp_area=belly, modest)
      2. body_part from payload (whole-body/body→hand, owner rule)
      3. subcategory map → category map → default area
    """
    hints = _load_ssot_extras()["apply_hints"]
    tmpl = hints["template"]
    bp = ""
    st = ""
    if isinstance(profile, dict):
        bp = (profile.get("body_part") or "").strip().lower()
        st = (profile.get("special_target") or "").strip().lower()
    bp_norm = bp.replace(" ", "-").replace("_", "-")
    hand_like = ("hand", "hands", "whole-body", "body")

    if st in ("pregnant", "pregnancy", "maternity"):
        if bp_norm == "face":
            return tmpl.format(area=hints["by_body_part"]["face"])
        if bp_norm in hand_like:
            return tmpl.format(area=hints["by_body_part"]["hand"])
        return tmpl.format(area=hints["pregnant_unknown_bp_area"])

    area = (
        hints["by_body_part"].get(bp_norm)
        or hints["by_subcategory"].get((subcategory or "").lower())
        or hints["by_category"].get((category or "").lower())
        or hints["default_area"]
    )
    return tmpl.format(area=area)


def _apply_prompt_anchor(
    ugc_style: str, video_prompt: str, vp_product: str = ""
) -> str:
    """Append the per-style prompt_anchor (from UGC_STYLES config) to the video
    prompt so Wan knows the shot/composition anchor it must follow. The anchor
    substitutes {product} / [product] placeholders with the (cleaned) product
    name. Falls back to the original prompt if the style has no anchor.
    """
    style = (ugc_style or "").strip().lower()
    # review is a TALKING style (mouth_control.talking_styles) — treat it as
    # talking_head so it uses the stable / fixed-framing anchor + talking path.
    if style in ("talking", "talking_head", "review"):
        style = "talking_head"
    anchor = None
    try:
        _styles = _load_ugc_styles().get("UGC_STYLES", {})
        anchor = (_styles.get(style, {}) or {}).get("prompt_anchor")
    except Exception:
        anchor = None
    if not anchor:
        return video_prompt
    # Resolve placeholders with the cleaned product name.
    prod = vp_product.strip() or "the product"
    anchor = anchor.replace("[product]", prod).replace("{product}", prod)
    return video_prompt.rstrip() + f" Composition: {anchor.strip()}".rstrip()


def build_video_prompt(profile: dict, product_name: str, ugc_style: str = "holding", loop_count: int = 0, script: str = "") -> str:
    """Generate SHORT video prompt — ~50 chars.

    Uses action from category_mapping. Wan 2.7 handles motion details.
    """
    model_gender = profile.get("target_gender", "female")
    category = profile.get("category", "other")
    subcategory = profile.get("subcategory", "")

    # AI select from category_mapping
    selected = _ai_select(category, subcategory, model_gender, product_name, loop_count)

    action = selected["action"]
    scene = selected["scene"]

    gender_en = {"female": "Woman", "male": "Man", "unisex": "Person"}.get(model_gender, "Woman")

    # ── NEW (P4): 4-beat natural video prompt ──
    # Owner-defined template (2026-08-20). Wan 2.7 = FL2V only (first/last frame),
    # no mid-sequence image reference. So we keep a tight 4-beat arc with minimal
    # expression words — specifically NO agitate/concerned/downside drama, and NO
    # squeeze-bottle/open-cap/scoop actions (Wan warps those). Each beat shifts
    # camera/action slightly so Wan doesn't repeat the same motion. The result
    # reveal lives in the beat + end scene, while the "problem/agitation" is told
    # through the AUDIO script, not the visuals.
    router_config = profile.get("router_config", {}) if isinstance(profile, dict) else {}
    scenes = router_config.get("scenes") if isinstance(router_config, dict) else None
    if (
        isinstance(scenes, list) and len(scenes) >= 2
        and product_name and ugc_style not in ("talking", "talking_head", "review")
        and not _is_no_human_style(ugc_style)
    ):
        vp_product = _clean_product_name_for_video(product_name)
        gender_en = {"female": "Woman", "male": "Man", "unisex": "Person"}.get(model_gender, "Woman")

        # SSOT end scene (same one the image frame uses) → beat 3 result + closing.
        es = profile.get("_end_scene") or _pick_end_scene(category, subcategory=subcategory, profile=profile)
        profile["_end_scene"] = es
        _result = es.get("result_focus") or "the result"
        _outfit = ", wearing " + es["outfit"] if es.get("outfit") else ""

        # apply-lotion hint: keep it "a little" so Wan doesn't smear too much;
        # no bottle-squeeze / cap / scoop (Wan warps those).
        # NEW: "ถือสินค้าพูด" is the DEFAULT. Only force an APPLY action when
        # special_target is set (e.g. pregnancy cream that must be applied to
        # face/belly). For every normal product (body_card/body_part alone) we
        # replace the apply hint with a neutral HOLD so an unbox/holding video
        # never turns into a smear-on-arm demo (owner bug report).
        _is_special = bool((profile.get("special_target") or "").strip())
        apply_hint = _apply_hint(subcategory, category, profile) if _is_special else (
            _load_ssot_extras()["apply_hints"]["hold_template"].format(product=vp_product)
        )

        # ── NEW (A): 4-beat driven by recipe scene visuals (scenes[].visual) ──
        # Each recipe schema (pas/comparison/secret_hook) defines a per-scene
        # English "visual" beat hint + optional "visual_pre" (camera move). We map
        # those onto numbered beats so the video prompt actually follows the recipe
        # (pas = open/apply/solve/cta, comparison = hook/them/us/cta, secret_hook =
        # hook/reveal/value/cta) instead of a hardcoded hold→apply→reveal→hold.
        # Rules kept from owner: no squeeze/cap/scoop, no agitate drama in the
        # visual (the pain lives in the AUDIO script), “a little” apply, every beat
        # shifts camera/action. The end scene (result) is bound to the same instance
        # build_image_prompt used, so image & video stay consistent.
        visual_scenes = [s for s in scenes if (s.get("visual") or "").strip()]
        if visual_scenes:
            preview = []
            for i, s in enumerate(visual_scenes, start=1):
                vid = (s.get("id") or "").lower()
                vis = s.get("visual") or ""
                pre = (s.get("visual_pre") or "").strip()
                # Resolve placeholders from the recipe scene visual:
                vis = vis.replace("{gender_en}", gender_en)
                vis = vis.replace("{vp_product}", vp_product)
                vis = vis.replace("{apply_hint}", apply_hint)
                vis = vis.replace("{result_focus}", _result)
                # A scene whose job is the "problem/agitate" shouldn't paint drama:
                # its meaning already rides on the audio script; keep the image beat neutral.
                if vid in ("agitate",):
                    vis = (
                        f"she pauses briefly with a slight thoughtful look, "
                        f"{gender_en} still holding {vp_product} toward the camera"
                    )
                if pre:
                    vis = f"{pre}; {vis}"
                preview.append(f"Scene {i}: {vis.strip()}")
            beats = preview
        else:
            # Fallback: owner template (same hold arc) if scene visuals missing.
            # Product must stay SHARP and STILL — Wan warps the label when the
            # prompt asks for scene transitions / flowing camera motion in 10s.
            # (owner bug report 2026-08-23: zoom in/out made product blur/morph)
            beats = [
                f"Scene 1: {gender_en} holds {vp_product} steady toward the camera in a medium close-up, product large in frame, stays sharp and centered",
                f"Scene 2: keep holding {vp_product} steady, only a gentle slight hand motion, product stays sharp",
                f"Scene 3: still holding {vp_product}, same framing, product remains sharp and readable",
                f"Scene 4: {gender_en} holds {vp_product} toward the camera, smiling, same framing, product sharp",
            ]

        video_prompt = (
            "A Thai woman naturally speaks the following Thai lines aloud to camera "
            "while staying in the same steady framing throughout:\n\n"
            + "\n".join(beats)
            + "\n\nKeep the same woman and product in every scene, staying in one steady framing "
            "throughout, the product stays sharp and clearly readable, "
            "speak the Thai lines naturally and continuously throughout."
        )
        logger.info(f"  Video prompt (4-beat, {len(video_prompt)} chars):")
        video_prompt = re.sub(r'[ \t]+', ' ', video_prompt).strip()
        logger.info(f"  Video prompt (4-beat, {len(video_prompt)} chars multi-line):")
        for l in video_prompt.split('\n'):
            logger.info(f"    {l}")
        return _apply_prompt_anchor(ugc_style, video_prompt, vp_product)

    # Build short video prompt with end scene (start + transition + end)
    # Wan 2.7 generates 1 continuous clip from a single image ref.
    # Integrating the end scene into the SAME prompt lets the model
    # animate a natural open → close arc in one pass (no separate clips).
    # If build_image_prompt() already bound an end scene (same profile), reuse it so
    # image & video end scenes stay EXACTLY consistent; otherwise pick fresh here.
    end = profile.get("_end_scene") or _pick_end_scene(category, subcategory=subcategory, profile=profile)
    transition = _pick_transition()

    # ── No-human styles: NO-human product video prompt ──
    # Wan 2.7 animates the product rotating / revealing itself (product_demo) or a
    # first-person POV using the product (pov), without showing a person's face.
    # The first/only frame comes from the matching no-human single 9:16 (image) so
    # video + image stay consistent. (We deliberately exclude no-human styles from
    # the 4-beat path above and give them their own branch here rather than falling
    # through to the legacy `else` which would inject a person.)
    if _is_no_human_style(ugc_style):
        style_l = (ugc_style or "").strip().lower()
        _vp_product = _clean_product_name_for_video(product_name)
        _result = end.get("result_focus") or "the product detailing"
        _end_cam = end.get("camera", "medium shot")
        if style_l == "pov":
            # First-person POV: only hands + product visible, no face. The user
            # picks up & uses the product in a natural daily scene.
            video_prompt = (
                f"First-person POV footage, the user's hands holding the {_vp_product} "
                f"and using it naturally in a daily setting, only hands and product in "
                f"frame, no face visible, natural hand movement, smooth stable motion, "
                f"then {_result} at {_end_cam}, 9:16"
            )
        else:  # product_demo
            video_prompt = (
                f"Pure product shot of the {_vp_product}, clean studio background, "
                f"the product slowly rotates 360 degrees showing its label and packaging, "
                f"smooth continuous rotation, no human, no hands in frame, crisp focus, "
                f"then settles centered showing {_result} at {_end_cam}, 9:16, smooth motion"
            )
        video_prompt = _apply_prompt_anchor(ugc_style, video_prompt, _vp_product)
        video_prompt = apply_mouth_steer(video_prompt, ugc_style)
        logger.info(f"  Video prompt (no-human {style_l}, {len(video_prompt)} chars): {video_prompt[:80]}...")
        return video_prompt

    if ugc_style in ("talking", "talking_head", "review"):
        # Talking-head: presenter faces camera, upper body, clean background.
        # Docs-exact pattern (VALIDATED 2026-08-15, job abf8a2b2):
        #   - ห้ามใส่ script ไทยใน prompt — script ทำให้ Wan พูดของมันเอง ปากไม่ตรงเสียง
        #   - prompt สั้น ภาษาบวก ไม่มี do/not/never
        #   - เสียงขับปากมาจาก audio param (TTS 16k) ที่ pipeline ส่งให้ Wan
        # USER TEMPLATE (vid_b43d89ab): "speaking naturally, subtle head movement,
        # holding the product toward the camera, ... then finishes speaking, holds
        # the product toward the camera, smiling" + micro-expressions for clean
        # restrained lip-sync (small natural mouth movement, minimal jaw, soft spoken).
        talking_scene = (
            "presenting from a clean bright background, upper body, "
            "facing directly to the camera"
        )
        _vp_product = _clean_product_name_for_video(product_name)
        start_part = (
            f"{gender_en} speaking naturally, subtle head movement, "
            f"holding the {_vp_product} toward the camera, {talking_scene}"
        )
        # Talking end: STOP talking and show the product.
        end_part = (
            "Face kept clear, then finishes speaking, "
            "holds the product toward the camera, smiling"
        )
        transition = ""
        # Mouth/head-only motion: keep face forward, avoid warping the frame.
        # Audio (not script) drives the mouth — audio param ส่งแยกที่ create_job.
        # Micro-expression steer comes once from apply_mouth_steer() below
        # (mouth_control.steer_talking_prompt from prompt_sources.json) — do NOT
        # duplicate it here or it appends twice.
        lipsync_part = (
            " subtle head movement, face kept clear and forward, "
            f"the {_vp_product} held still in front of the presenter"
        )
    else:
        start_part = f"{gender_en} {action}. {scene}."
        end_part = f"{end.get('camera', 'medium shot')}, {end.get('scene', 'product shown to camera')}."
        lipsync_part = (
            " lips moving subtly, smooth natural motion, "
            "product held still and sharp"
        )

    # Compose: opening action → gentle transition → end scene
    # Keep it natural-language so Wan's motion model flows smoothly.
    # Talking-head end_part is self-contained (start + finish + stop + show product),
    # so don't inject "transition, then" which would produce a broken " , then Face".
    if ugc_style in ("talking", "talking_head", "review"):
        video_prompt = f"{start_part} {end_part} 9:16.{lipsync_part}"
    else:
        video_prompt = f"{start_part} {transition}, then {end_part} 9:16.{lipsync_part}"

    # Clean up
    video_prompt = re.sub(r'\s+', ' ', video_prompt).strip()

    # Mouth steer (POSITIVE prompt side): for talking styles, append the
    # steer keywords so Wan keeps lip movement small/natural/restrained.
    # Goes on the positive prompt, never on the negative (see apply_mouth_steer).
    video_prompt = apply_mouth_steer(video_prompt, ugc_style)

    logger.info(f"  Video prompt ({len(video_prompt)} chars): {video_prompt[:80]}...")
    return _apply_prompt_anchor(ugc_style, video_prompt, _clean_product_name_for_video(product_name))
def _normalize_age(raw_age) -> int:
    """Extract the minimum age from target_age range (e.g., '25-35' -> 25).
    Falls back to a default age if parsing fails.
    """
    import re
    if not raw_age:
        return 25
    try:
        if isinstance(raw_age, (int, float)):
            return int(raw_age)
        # Find all numbers in the string
        nums = [int(n) for n in re.findall(r'\d+', str(raw_age))]
        if nums:
            # Take the minimum/lowest number in the range (e.g., 25 from '25-35')
            return min(nums)
    except Exception:
        pass
    return 25


def _load_mouth_control() -> dict:
    """Load the mouth_control block from prompt_sources.json (single source of truth).
    No hardcoded copy / no silent fallback: if the block is missing or malformed
    we raise so the JSON (the one place to fix) is always the authority. This keeps
    code from drifting away from the data and makes failures obvious & fixable."""
    sources = _load_prompt_sources()
    mc = sources.get("mouth_control")
    if not isinstance(mc, dict):
        raise ValueError("prompt_sources.json: missing or invalid 'mouth_control' block — add it")
    required = ("talking_styles", "non_talking_styles", "negative_base",
                "negative_talking", "negative_non_talking", "steer_talking_prompt")
    missing = [k for k in required if k not in mc]
    if missing:
        raise ValueError(f"prompt_sources.json 'mouth_control' missing keys: {missing}")
    return mc


def _is_talking_style(ugc_style: str, mc: dict) -> bool:
    """True if the ugc_style is in the talking list.
    Unknown styles default to talk (soft) so we never risk locking a mouth
    that actually needs to speak — harmless for non-talking (mouth just moves
    slightly, no melt)."""
    s = (ugc_style or "").strip().lower()
    talking = [x.strip().lower() for x in mc["talking_styles"]]
    non_talking = [x.strip().lower() for x in mc["non_talking_styles"]]
    if s in talking:
        return True
    if s in non_talking:
        return False
    # Unknown style → default to talking (soft) for safety.
    return True


def build_negative_prompt(profile: dict, ugc_style: str = "holding") -> str:
    """Build negative prompt — defaults (text/watermark/hands/distortion)
    + Wan identity-stability terms (anti-morph / anti-melt).
    Caller no longer needs to merge — this is the complete negative.

    Mouth-control is style-aware (data-driven from prompt_sources.json):
      - Talking styles  → base (anti-melt only) + SOFT mouth terms.
        NEVER "no open mouth" — that kills speech entirely.
      - Non-talking styles → base + HARD mouth terms (lock jaw fully).
      - Unknown style   → treated as talking (soft) for safety.
    """
    mc = _load_mouth_control()
    base = mc["negative_base"]
    style_l = (ugc_style or "").strip().lower()
    # No-human styles (product_demo, pov) have no person/hands in frame, so the
    # "stays closed and in hand" anti_open term would contradict the composition.
    # Drop it for those styles and rely on the base + mouth terms.
    is_no_human_style = _is_no_human_style(ugc_style)
    # Product-handling negative: Wan img2vid starts from a still where the product is
    # ALREADY in hand — forbid it from opening/unpacking/squeezing the product (was in
    # the video prompt's opening before; moved here so the video prompt stays positive).
    anti_open = "" if is_no_human_style else (
        "no opening the product, no uncapping, no squeezing, no pumping, no unpacking, "
        "no taking the product out of its box, product stays closed and in hand"
    )
    if _is_talking_style(ugc_style, mc):
        mouth_terms = ", ".join(x.strip() for x in mc["negative_talking"])
    else:
        mouth_terms = ", ".join(x.strip() for x in mc["negative_non_talking"])
    parts = [p for p in (base, anti_open, mouth_terms) if p]
    negative = ", ".join(parts)
    # Wan 2.7 hard-caps the negative prompt at ~500 chars — trim from the tail
    # (mouth terms last) if we ever exceed it, so the job doesn't error.
    if len(negative) > 500:
        neg = negative[:500]
        # never cut mid-word
        cut = neg.rfind(", ")
        if cut > 0:
            neg = neg[:cut]
        negative = neg
    return negative


def apply_mouth_steer(video_prompt: str, ugc_style: str = "holding") -> str:
    """Append positive steer keywords to a video prompt for talking styles.
    These go in the POSITIVE prompt (not the negative) so Wan moves the mouth
    in small, natural, restrained ways instead of wide/jaw-heavy gesticulation.
    Non-talking / unknown styles get no steer (they shouldn't be talking)."""
    mc = _load_mouth_control()
    if not _is_talking_style(ugc_style, mc):
        return video_prompt
    steer = [x.strip() for x in mc["steer_talking_prompt"]]
    if not steer:
        return video_prompt
    steer_text = ", ".join(steer)
    return video_prompt.rstrip() + f" {steer_text}."


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
    category: str = "",
    loop_count: int = 0,
    product_category: str = "",
    target_duration: int = 15,
    target_age: Any = "",
    target_gender: str = "",
    country: str = "",
    script: str = "",
    body_part: str = "",
    special_target: str = "",
    usage_howto: str = "",
    ingredient_highlight: str = "",
    **kwargs,
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
    profile = analyze_product(product_name, description, keywords, target_duration=target_duration, features=features)

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
        for key in ["category", "target_gender", "target_age", "target_audience",
                     "customer_problem", "main_benefit", "features"]:
            if key in vision_profile and vision_profile[key]:
                profile[key] = vision_profile[key]
        # product_type from vision overwrites text analysis
        if "subcategory" in vision_profile and vision_profile["subcategory"]:
            profile["subcategory"] = vision_profile["subcategory"]
        if "target_skin_tone" in vision_profile and vision_profile["target_skin_tone"]:
            profile["target_skin_tone"] = vision_profile["target_skin_tone"]
        if "product_type" in vision_profile and vision_profile["product_type"]:
            profile["product_type"] = vision_profile["product_type"]
        if "colors" in vision_profile and vision_profile["colors"]:
            profile["colors"] = vision_profile["colors"]

    # Ensure target_gender is explicitly resolved
    if profile.get("target_gender", "") in ("", None):
        profile["target_gender"] = "person"

    # Override with explicit params if provided
    if category:
        profile["category"] = category
    if product_category:
        profile["product_category"] = product_category
    # Explicit target_gender / target_age must be authoritative (user choice),
    # otherwise Gemini's auto-analysis of the product often defaults to female.
    if target_gender and target_gender.strip():
        profile["target_gender"] = target_gender.strip()
    if target_age not in ("", None):
        profile["target_age"] = str(target_age)

    # NEW: inject deep-analysis fields (body_part/special_target/usage/ingredient)
    # into the product profile so both build_image_prompt() and build_video_prompt()
    # can tune the visual composition (e.g. pregnant→belly/face, whole-body→hand).
    if body_part:
        profile["body_part"] = body_part.strip()
    if special_target:
        profile["special_target"] = special_target.strip()
    if usage_howto:
        profile["usage_howto"] = usage_howto.strip()
    if ingredient_highlight:
        profile["ingredient_highlight"] = ingredient_highlight.strip()
    
    # Step 3: Inject persona for diversity
    persona = _select_persona(profile.get("category", "other"), product_name, profile.get("target_gender"))
    profile = _apply_persona_to_profile(profile, persona)
    logger.info(f"Persona: {persona.get('vibe', '')} | Env: {persona.get('environment', '')}")

    # Sync age — normalize once so image + video prompt ages match
    profile["_normalized_age"] = _normalize_age(profile.get("target_age", "20-35"))

    # Step 4: Build script timing FIRST so the video prompt can embed the
    # spoken Thai script (Option A: drop lip-sync audio, let Wan read/feel the
    # script text directly so it moves lips in sync with the TTS voiceover).
    # If the caller supplied an external `script` (the exact TTS script from the
    # pipeline), use THAT so the video prompt matches the voiceover 1:1.
    timing_validation = _build_timing_validated_script(product_name, profile.get("category", "other"), profile)
    tv = timing_validation if isinstance(timing_validation, dict) else {}
    if script and script.strip():
        # Prefer the caller-provided TTS script verbatim (must match voiceover).
        tv["full_script"] = script.strip()
        tv["tts_script"] = script.strip()
    _spoken_script = tv.get("full_script", "") if isinstance(tv, dict) else ""

    # Step 5: Build prompts (video prompt receives the spoken script for talking style)
    image_prompt, neg_from_template = build_image_prompt(profile, product_name, ugc_style, loop_count)
    video_prompt = build_video_prompt(profile, product_name, ugc_style, loop_count, script=_spoken_script)
    # FIX (negative duplication): build_image_prompt() ALREADY returns the full
    # default negative via build_negative_prompt(). Concatenating it again with
    # default_neg duplicated every term ~2x (wasted Prodia word budget and
    # confused Wan). Use neg_from_template alone — it already includes the
    # identity-stability terms.
    negative_prompt = neg_from_template  
    
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
            # image_description removed — using JSON template
            # env_context and product_appearance removed — using JSON sources
            "features": profile.get("features", ""),
        },
        "timing_validation": {
            "segments": {
                "hook": _tv_seg_text(tv, "hook"),
                "value": _tv_seg_text(tv, "value"),
                "cta": _tv_seg_text(tv, "cta"),
            },
            "tts_speed": tv.get("tts_speed", 1.0),
            "product_short_for_tts": tv.get("product_short_for_tts", ""),
            "all_segments_fit": tv.get("all_segments_fit", True),
            "total_duration": tv.get("total_duration", 15),
            "beats": tv.get("beats", []),
            "recipe": tv.get("recipe", ""),
        },
        "scripts": {
            "full_script": tv.get("full_script", ""),
            "tts_script": tv.get("tts_script", ""),
            "breakdown": {
                "hook": _tv_seg_text(tv, "hook"),
                "value": _tv_seg_text(tv, "value"),
                "cta": _tv_seg_text(tv, "cta"),
            }
        },
        "hashtags": profile.get("hashtags", []),
        "image_prompt": image_prompt,
        "image_prompt_readable": _image_prompt_readable(image_prompt),
        "video_prompt": video_prompt.replace("\n", " ") if video_prompt else video_prompt,
        "video_prompt_readable": video_prompt,
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
    # FIX (thai speaking-rate calibration): old rate 18 chars/sec over-estimated
    # how fast Thai is spoken, so duration came out too short and the resulting
    # tts_speed came out too low (voice not sped up enough). Measured (Gemini TTS,
    # No Edge TTS — Edge ถูกถอดออก 2026-08-15):
    #   125 Thai chars -> 8.5s  (~14.7 c/s)
    #   172 Thai chars -> 11.0s (~15.5 c/s)
    # Average ~15. Use 14.5 c/s (slightly conservative) so estimated duration is a
    # bit longer -> tts_speed can ramp up a touch. Non-Thai stays 9 c/s.
    thai_sec = thai_chars / 14.5
    non_thai_sec = non_thai_chars / 9.0
    switches = 1 if (thai_chars > 0 and non_thai_chars > 0) else 0
    return thai_sec + non_thai_sec + (switches * 0.1)


def _normalize_thai_gender_register(text: str, is_female: bool) -> str:
    """Normalize Thai polite particles to match target model gender (ครับ -> ค่ะ/คะ for female)."""
    if not text:
        return ""
    if is_female:
        text = re.sub(r'ครับ', 'ค่ะ', text)
        text = re.sub(r'นะคะ\s*นะคะ', 'นะคะ', text)
    else:
        text = re.sub(r'ค่ะ|คะ', 'ครับ', text)
    return text


# ─── Owner script rules (ported from modules/video/script_gen.py, commit 9e7e226f) ───
# Owner directive (2026-08-23 vid_6baa888a + 2026-08-24): the product name is spoken
# at most ONCE per script — later mentions are DROPPED entirely, never substituted
# with 'ตัวนี้/เจ้านี้'. Spoken name prefers Thai tokens over Latin (Wan reads Latin
# brand names badly).

def _brand_tokens(product_name: str):
    """Split product name into normalized tokens so Thai & English variants of the
    SAME brand fold to one identity (e.g. ครีมสกินชี ↔ Skinshe). Returns [(word, norm)]."""
    import unicodedata
    toks = []
    for raw in re.split(r"[\s\[\]()\\,.:;|\-]+", product_name or ""):
        w = raw.strip()
        if not w:
            continue
        if re.fullmatch(r"(เซต|ชิ้น|มี|แถม|ขนาด|ใหม่|เจน|รุ่น|สี|แพ็ค|แพ็ก|set|pack|box|ml|g|gift|cream|ครีม)", w, re.I):
            continue
        if w.isdigit():
            continue
        latin = bool(re.search(r"[A-Za-z]", w))
        if latin:
            norm = unicodedata.normalize("NFKD", w.lower())
            norm = re.sub(r"[^a-z0-9]", "", norm)
        else:
            norm = re.sub(r"[^\u0E00-\u0E7F0-9]", "", w)
        if norm:
            toks.append((w, norm))
    return toks


def _tts_product_name(product_name: str) -> str:
    """Thai-dominant short name for SPOKEN script + BRAND kept (owner 2026-08-25:
    "มันไม่มีคำว่า Zeblanc อ่ะ" — brand must be spoken too).
    Keeps Thai descriptor tokens, then appends the FIRST Latin (brand) token if
    it fits. Pure-Latin products keep Latin only. Whole tokens only, no chopping."""
    name = (product_name or "").strip()
    if not name:
        return name
    toks = _brand_tokens(name)
    thai = [w for w, _ in toks if re.search(r"[\u0E00-\u0E7F]", w)]
    latin = [w for w, _ in toks if not re.search(r"[\u0E00-\u0E7F]", w)]

    def _join(words):
        out = ""
        for w in words:
            cand = (out + " " + w).strip()
            if cand and len(cand) > 35 and out:
                break  # keep whole tokens only — never chop mid-word
            out = cand
        return out.strip()

    if thai:
        out = _join(thai)
        if latin and len(f"{out} {latin[0]}") <= 40:
            out = f"{out} {latin[0]}".strip()
        return out or name
    return _join(latin[:2]) or name


def _name_variants(*names) -> List[str]:
    seen, out = set(), []
    for n in names:
        n = (n or "").strip()
        if len(n) >= 3 and n.lower() not in seen:
            seen.add(n.lower())
            out.append(n)
    return out


def _owner_script_variants(*bases) -> List[str]:
    """Name variants for the drop-rule: full names + individual brand tokens
    (>=4 chars) so TRUNCATED mentions (beat trimmer cuts mid-name) still match."""
    import re as _re
    out = _name_variants(*bases)
    for b in bases:
        for w, _n in _brand_tokens(b):
            if len(w) >= 4:
                wl = w.lower()
                if wl not in {o.lower() for o in out}:
                    out.append(w)
    return out


def _title_claims(name: str) -> str:
    """Owner rule (2026-08-25): selling points come from the product NAME itself,
    not AI image analysis. Pregnancy-safe products MUST speak their 'free of X'
    claims (e.g. ปราศจากน้ำหอมและพาราเบน). Extracts Thai claim tokens:
    ไม่X / ปราศจากX / ไร้X / ...ชุ่มชื้น / กันน้ำ / กันแดด style phrases."""
    if not name:
        return ""
    claims = []
    for t in re.split(r"\s+", name):
        if not re.search(r"[\u0E00-\u0E7F]", t):
            continue  # Thai-only tokens
        if t.startswith(("ไม่", "ปราศจาก", "ไร้", "ไม่มี", "ต่ำกว่า")) or \
           ("ชุ่มชื้น" in t and t.startswith("ให้")) or t == "ชุ่มชื้น":
            claims.append(t)
    return " ".join(claims)


def _scrub_placeholder_words(segments: list) -> None:
    """Owner rule: spoken lines NEVER use name-substitute words.
    Strip standalone 'ตัวนี้/เจ้านี้/อันนี้' from every segment text
    (schema templates may still carry them; they are always substitutive here).
    Keeps different words like ปัญหานี้/วันนี้/จุดนี้ untouched."""
    pat = re.compile(r"\s*(?:ตัวนี้|เจ้านี้|อันนี้)(?:เลย|ดิ|สิ)?\s*")
    for seg in segments:
        t = seg.get("text", "") or ""
        if not t:
            continue
        if pat.search(t):
            t2 = pat.sub(" ", t)
            t2 = re.sub(r"\s{2,}", " ", t2).strip()
            t2 = re.sub(r"^(และ|หรือ|กับ|ของ)\s+", "", t2)
            seg["text"] = t2


def _drop_later_name_mentions(segments: list, variants: List[str]) -> int:
    """Keep the FIRST segment containing any name variant; strip the name from all
    LATER segments (and any 'ตัวนี้/เจ้านี้/อันนี้' right there) instead of ever
    substituting a placeholder. Mutates segment dicts' 'text'. Returns drops count."""
    alts = sorted({re.escape(v) for v in variants}, key=len, reverse=True)
    if not alts:
        return 0
    pat = re.compile(r"\s*(?:" + "|".join(alts) + r")\s*", re.I)
    seen = False
    drops = 0
    for seg in segments:
        t = seg.get("text", "") or ""
        if not t:
            continue
        if not seen and pat.search(t):
            seen = True
            continue
        if seen and pat.search(t):
            t2 = pat.sub(" ", t)
            # owner: no 'ตัวนี้/เจ้านี้' placeholder where the name used to repeat
            t2 = re.sub(r"(ตัวนี้|เจ้านี้|อันนี้)(เลย|ดิ|สิ)?\s*", " ", t2)
            t2 = re.sub(r"\s{2,}", " ", t2).strip()
            t2 = re.sub(r"^(และ|หรือ|กับ|ของ)\s+", "", t2)
            t2 = re.sub(r"\s+(และ|หรือ|กับ)$", "", t2)
            seg["text"] = t2
            drops += 1
    return drops

# Thai vowel/tone marks that must never dangle at a slice boundary.
_THAI_VOWEL_ABOVE = set('ีืัุู')
_THAI_MARK = 'เแโใไะาำิีึืุู็่้๊๋์ํ'  # Thai vowel/tone marks
# Thai leading consonants (start of a syllable).
_THAI_LEAD = set('กขฃคฅฆงจฉชซฌญฎฏฐฑฒณดตถทธนบปผฝพฟภมยรลวศษสหฬอฮ')


def _drop_dangling_thai(s: str) -> str:
    """Trim a trailing INCOMPLETE Thai word from `s`.

    Gemini sometimes returns a benefit already sliced mid-word (e.g.
    "เรียบเนียนภายใน 1 ส" where "ส" starts "สัปดาห์"). We only drop a trailing
    BARE consonant fragment when it is clearly a clipped word start: a single
    leading consonant that follows a SPACE (so "ภายใน 1 ส" -> "ภายใน 1", but a
    complete word like "เรียบเนียน" or "ดำ" is left whole because its final
    consonant is glued to its own vowel/word, not after a space).
    """
    if not s:
        return s
    t = s.rstrip(' ')
    if not t:
        return s
    # Only when the very last token (after a space) is a single bare consonant
    # do we treat it as a clipped lookahead word and remove it.
    sp_idx = t.rfind(' ')
    if sp_idx >= 0:
        tail = t[sp_idx + 1:]
        if len(tail) == 1 and tail[0] in _THAI_LEAD:
            return t[:sp_idx]
    return t


def _safe_thai_truncate(text: str, limit: int) -> str:
    """Truncate to <= limit chars WITHOUT splitting a Thai word.

    Rules (never produce broken Thai speech):
      - Prefer the last SPACE boundary within the limit when it is a "real"
        word break reasonably near the limit (not a bare separator at the start).
      - Otherwise back off from the limit so we never END on a Thai vowel/tone
        mark and never START the tail with a vowel mark (mid-syllable).
      - Then drop a trailing bare-consonant fragment (Gemini-truncated word).
    """
    if not text:
        return text
    if len(text) > limit:
        head = text[:limit]
        sp = head.rfind(' ')
        # use the space break only when it leaves a substantial, clean chunk
        if sp > limit * 0.5:
            head = head[:sp]
        else:
            # No good space boundary (contiguous Thai / no word break):
            # correct Thai word-splitting needs a dictionary we do not have, so
            # the SAFE choice is to keep the text (slightly longer script is far
            # better than chopped Thai speech).
            return _drop_dangling_thai(text)
        text = head
    return _drop_dangling_thai(text)


def _fit_beat_text(text: str, dur_sec: float, thai_cps: float = 14.5, non_thai_cps: float = 9.0) -> str:
    """Trim a beat's spoken text so it fits its scene duration WITHOUT speeding
    the voice up aggressively.

    Budget = how many chars fit in `dur_sec` at the calibrated speech rates
    (Thai 14.5 c/s, non-Thai 9 c/s — see _estimate_speech_duration). We walk
    backward from the end, dropping whole words/phrases (space / Thai-dash
    separators) until the estimate <= dur_sec. Never breaks mid-word: if no
    separator is found we fall back to the raw text (better long than chopped
    Thai speech) and let tts_speed handle it.
    """
    if not text or not dur_sec or dur_sec <= 0:
        return text or ""
    # Fast path: already fits
    if _estimate_speech_duration(text) <= dur_sec:
        return text
    # Walk backward over the whole text, truncating at natural breaks
    tokens = re.split(r"(\s+)", text)
    # tokens: [word0, sep0, word1, sep1, ...] — rebuild from the front
    running = ""
    for i in range(0, len(tokens) - 1, 2):
        word = tokens[i]
        sep = tokens[i + 1] if i + 1 < len(tokens) else ""
        candidate = running + word + sep
        if _estimate_speech_duration(candidate.rstrip()) > dur_sec:
            # This word would overflow — stop; keep whatever fit so far.
            break
        running = candidate
    trimmed = running.rstrip()
    # Drop a dangling dash/separator left at the tail (e.g. '... —' with nothing after)
    trimmed = re.sub(r"[\s\u2014\u2013\-]+$", "", trimmed)
    if not trimmed:
        # even the first word overflows — return first word (best effort)
        return tokens[0] if tokens else text
    return trimmed or text


def _tv_seg_text(tv, key):
    """Safely extract segment text from a timing_validation dict (handles beats)."""
    if not isinstance(tv, dict):
        return ""
    seg = tv.get(key)
    if isinstance(seg, dict):
        return seg.get("text", "")
    # 4-beat path: fall back to matching beat by id
    for b in tv.get("beats", []) or []:
        if isinstance(b, dict) and b.get("key") == key:
            return b.get("text", "")
    return str(seg) if seg else ""


def _resolve_scene_text(scene, product_short, customer_problem, main_benefit, target_audience, profile_feature=""):
    """Fill a 4-beat scene prompt_template with real values.

    Scene dict comes from router_config.scenes (built by router_agent._build_scenes),
    with keys: id / duration / purpose / prompt_template.
    Placeholders come from the product profile (Mistral/Gemini analysis).
    Falls back to purpose text if template is empty/invalid.
    """
    tpl = scene.get("prompt_template") or scene.get("purpose") or ""
    # Keep only {placeholder} tokens we can actually fill (drop unknown ones)
    def _fill(m):
        key = m.group(1).strip()
        vals = {
            "problem": customer_problem or "",
            "product": product_short or "",
            "benefit": main_benefit or "",
            "target_audience": target_audience or "",
            "feature": (profile_feature or ""),
        }
        return vals.get(key, "")
    return re.sub(r"\{(\w[^}]*)\}\??", _fill, tpl).strip()


def _build_timing_validated_script(product_name: str, category: str = "beauty", profile: dict = None) -> dict:
    """Build script segments with timing validation.

    Prefers the Router Agent's 4-beat scenes (router_config.scenes) so the script
    matches the chosen recipe (pas/comparison/secret_hook). Falls back to the old
    3-segment hook/value/cta structure when no scenes are present.
    Uses customer_problem + main_benefit from Gemini/Mistral analysis when available.
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
    # Owner rule 2026-08-25: claims from the product NAME win over AI analysis
    _tb = _title_claims(product_name or "")
    if _tb:
        main_benefit = _tb
    
    if customer_problem and main_benefit and len(customer_problem) > 5:
        # Shorten problem and benefit for natural spoken Thai and normalize polite particle by gender
        hook_text = _normalize_thai_gender_register(_safe_thai_truncate(customer_problem, 40), is_female)
        value_text = _normalize_thai_gender_register(f"{product_short} {_safe_thai_truncate(main_benefit, 45)}", is_female)
    elif category in ("home", "electronics", "tools"):
        hook_text = f"เจอปัญหานี้อยู่ใช่ไหม{reg_hook}"
        value_text = f"{product_short} ช่วยได้เยอะเลย{reg_val}"
    elif "blush" in category.lower() or "cheek" in category.lower():
        hook_text = f"อยากหน้าสดใส ดูมีมิติใช่ไหม{reg_hook}"
        value_text = f"{product_short} เติมแก้มสวยเป็นธรรมชาติ{reg_val}"
    elif "lip" in category.lower():
        hook_text = f"อยากปากฉ่ำวาว สวยทนนานไหม{reg_hook}"
        value_text = f"{product_short} ทาแล้วปากชุ่มชื้น สวยปัง{reg_val}"
    elif "mask" in category.lower() or "facial" in category.lower():
        hook_text = f"ผิวแห้ง หมองคล้ำ ต้องลองสักครั้ง{reg_hook}"
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

    target_dur_sec = 15
    if profile and profile.get("target_duration"):
        try:
            target_dur_sec = int(str(profile.get("target_duration")).replace("s", ""))
        except ValueError:
            target_dur_sec = 15

    # ── NEW (P1): prefer Router Agent 4-beat scenes when available ──
    # router_config.scenes = [{id, duration, purpose, prompt_template}, ...] from the
    # chosen recipe schema (pas/comparison/secret_hook). This makes the script follow
    # the actual recipe beats (hook→agitate→solve→cta etc.) instead of hardcoded 3 segments.
    router_config = profile.get("router_config", {}) if profile else {}
    scenes = router_config.get("scenes") if isinstance(router_config, dict) else None

    if isinstance(scenes, list) and len(scenes) >= 2:
        target_audience = profile.get("target_audience", "") if profile else ""
        profile_feature = profile.get("features", "") if profile else ""
        # Owner rule 2026-08-24: spoken name = Thai-dominant variant, name spoken ONCE
        # (derive from FULL product_name — product_short may be hard-chopped mid-word)
        spoken_name = _tts_product_name(product_name or product_short)
        segments = []
        for sc in scenes:
            beat_text = _resolve_scene_text(
                sc, spoken_name, customer_problem, main_benefit, target_audience, profile_feature
            )
            # Gender-register normalize for spoken Thai
            beat_text = _normalize_thai_gender_register(beat_text, is_female)
            dur = sc.get("duration", 0) or 0
            if not beat_text:
                continue
            # Trim the beat so it fits its scene duration (keeps tts_speed near 1.0x
            # instead of the old fallback that overshoots -> forces 1.3x fast speech).
            beat_text = _fit_beat_text(beat_text, dur)
            segments.append({"key": sc.get("id", "beat"), "text": beat_text, "duration_sec": dur, "timing": ""})

        # Owner script rules: name at most ONCE — later mentions dropped, no 'ตัวนี้'
        _drop_later_name_mentions(segments, _owner_script_variants(spoken_name))
        _scrub_placeholder_words(segments)

        # Recompute timings sequentially from durations (sum of scene durations ≈ duration)
        if segments:
            acc = 0.0
            for seg in segments:
                seg["timing"] = f"{int(round(acc))}-{int(round(acc + seg['duration_sec']))}"
                acc += seg["duration_sec"]
            total_ok = True
            max_speed_needed = 1.0
            for seg in segments:
                estimated = _estimate_speech_duration(seg["text"])
                seg["estimated_sec"] = round(estimated, 1)
                dur = seg["duration_sec"] if seg["duration_sec"] else target_dur_sec
                seg["ok"] = estimated <= max(dur, 1)
                if not seg["ok"]:
                    total_ok = False
                    needed = estimated / max(dur, 1)
                    if needed > max_speed_needed:
                        max_speed_needed = needed
            tts_speed = min(max(max_speed_needed, 1.0), 1.3)
            full = " ".join(s["text"] for s in segments if s.get("text"))
            # Keep backward-compat keys (hook/value/cta) so downstream consumers don't break
            out = {"segments": segments, "beats": segments,
                   "tts_speed": tts_speed, "full_script": full, "tts_script": full,
                   "product_short_for_tts": product_short,
                   "all_segments_fit": total_ok, "total_duration": target_dur_sec,
                   "recipe": router_config.get("recipe_type", "")}
            # Map common beat ids → legacy keys where present
            for legacy_key in ("hook", "value", "cta"):
                for seg in segments:
                    if seg["key"] == legacy_key:
                        out[legacy_key] = seg
                        break
            return out

    # ── Fallback: original 3-segment hook/value/cta (no router scenes) ──
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
    # Owner script rules (2026-08-24): Thai-dominant name + speak ONCE, no 'ตัวนี้'
    _spoken_fb = _tts_product_name(product_short)
    _drop_later_name_mentions(segments, _owner_script_variants(_spoken_fb))
    _scrub_placeholder_words(segments)
    
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
    full = " ".join(s["text"] for s in segments if s.get("text"))
    
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

