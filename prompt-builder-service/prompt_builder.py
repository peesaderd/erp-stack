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

    # Owner 2026-09-01: rewrite messy product title to clean "brand + product type"
    # ONCE here (analysis time). Downstream _build_timing_validated_script reads
    # profile["clean_title"] instead of recomputing it on every build (less latency,
    # AI called at most once per product name).
    profile["clean_title"] = rewrite_clean_title(product_name, profile.get("category", "other"), profile)

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
    # Owner 2026-08-29 15:28: IMAGE ไม่ทาผลิตภัณฑ์อีกต่อไป — "รูปเลิกทาไปเลย".
    # ลบ _apply_hint ออกจาก image (ภาพมีแค่ถือ/วางตาม recipe) การทาครีม/เกลี่ย
    # ให้เกิดใน VIDEO prompt scene 2 เท่านั้น.
    if ugc_style == "review":
        # Review recipe (owner 2026-08-26): image places product on the table,
        # model reviews with hands RESTING still on/near the table — NO gesturing,
        # NO raising hands (owner 2026-08-26 14:20: "ยกมือเพี้ยน" — กำจัดคำสั่งชี้มือ).
        # Owner 2026-08-26 22:48: ยิ้มแย้มชัดเจน (พี่เจอ "นางแบบไม่ยิ้ม หลายคลิป") —
        # ใส่ smile/bright cheerful ที่ต้นภาพ ไม่ใช่แค่ "speaking calmly" (ตรงข้ามยิ้ม).
        mid_hint = (
            f"{model_desc} with the product(s) from the reference image placed on the table "
            f"in front, hands resting still on the tabletop, smiling warmly with a bright "
            f"cheerful expression, speaking to camera, {room_desc}, "
            f"medium close-up framing, product large in frame, sharp and clearly readable"
        )
    else:
        # Default image pose = plain HOLD for EVERY product — no apply/smear on the
        # frame (owner 2026-08-29 15:28: "รูปเลิกทาไปเลย"). Applying the cream
        # happens only in the VIDEO prompt scene 2, never in the image. Covers both
        # normal products and special_target (cream/face/makeup) alike.
        mid_hint = (
            f"{model_desc} holding the product(s) from the reference image, "
            f"bottles facing the camera, {room_desc}, "
            f"smiling warmly with a bright cheerful expression, "
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
    # Review recipe (owner 2026-08-26): end scene must keep product on the table,
    # never "in hand" (es default), matching the placed-on-table image+video prompt.
    if ugc_style == "review":
        _placement = es.get("product_placement") or "product placed on the table in front"
    result_hint = (
        f"the same {model_desc} from the first part of the frame, wearing the same "
        f"outfit, {_expr}, showing {_result}; {_placement}{_outfit}"
    )
    # Address recipe beats (solve/us/value) from scenes onto the single frame.
    # Owner 2026-08-26 14:20: แก้ SSOT ให้ครบ loop — review ใช้ mid_hint ที่ตั้งไว้
    # (วางบนโต๊ะ + มือนิ่ง) เสมอ ไม่อนุญาตให้ loop beat ทับกลับเป็น holding/
    # bottles-facing แบบเดิม (ต้นตอ "ยกมือเพี้ยน").
    if isinstance(scenes, list) and ugc_style != "review":
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
                    # Owner 2026-08-26 22:48: ยิ้มแย้มชัดเจน ทั้งต้น/กลาง/ท้าย —
                    # เติม smile ต่อท้าย beat ทุกครั้ง กัน prompt scene แทนที่ smile หาย
                    mid_hint = f"{model_desc}, {vis}, smiling warmly with a bright cheerful expression"
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
        elif style_l == "ambient_outdoor":
            # Owner 2026-08-31: ambient outdoor = product glowing at night in a
            # garden/patio with NO person AND NO hands — the product is the star
            # (solar/outdoor lights). Must NOT reuse the human holding template or
            # the first-person POV hands branch (both would show a person).
            # Owner 2026-09-01: ONE single outdoor scene chosen per-product from
            # category_mapping (e.g. electronics.solar_light -> garden path at dusk,
            # wall_light -> house entrance gate), warm golden glow, no studio cover,
            # no logo, no mixing of grass+patio+veranda into one frame.
            _od_scene = (selected.get("scene") or "").strip()
            _od_lighting = (selected.get("lighting") or "warm golden light").strip()
            if _od_scene:
                # Owner 2026-09-01: solar/stake lights must sit LOW to the ground,
                # stakes plunged into the garden soil — the first generated image
                # looked too tall/raised. Force grounding for stake/plantable lights.
                _sub = (profile.get("subcategory") or "")
                _grounding = ""
                if _sub in ("solar_light",) or any(w in _sub for w in ("stake", "path", "plant")):
                    _grounding = " The light sits low to the ground, its stakes plunged into the garden soil, not raised high off the ground."
                feat_hint = (
                    f"{product_name} glowing softly and clearly visible, "
                    f"placed in a single, coherent outdoor setting: {_od_scene};"
                    f"{_grounding} {_od_lighting}, product centered and clearly shown, warm golden glow"
                )
            else:
                feat_hint = (
                    f"{product_name} glowing softly among garden plants at night, "
                    f"product centered and clearly shown, warm golden light, "
                    f"placed outdoors in a single garden scene, {room_desc}"
                )
            no_human_clause = (
                "NO humans, NO people, NO hands in frame; pure ambient "
                "product photography, product glowing softly, no person anywhere."
            )
        else:  # pov — first-person, hands visible, no face
            feat_hint = mid_hint  # first-person hands holding the product
            no_human_clause = (
                "First-person POV throughout; no face of the person in frame, "
                "only hands and product visible."
            )
        if style_l == "ambient_outdoor":
            _pfx = f"Single vertical 9:16 frame, ambient outdoor night scene: {feat_hint}"
        else:
            _pfx = f"Single vertical 9:16 frame: {_cover}. Featured: {feat_hint}"
        image_prompt = (
            f"{_pfx}. "
            f"Product: show exactly the item(s) from the reference product image — "
            f"render every variant/color that appears in it. "
            f"{parts_colors} "
            f"{no_human_clause} "
            f"NO text, letters, words, labels, logos or watermark. "
            f"Cohesive consistent style, high quality product photography. --ar 9:16"
        )
        logger.info(f"  Image prompt (no-human single 9:16 {style_l}, {len(image_prompt)} chars)")
        image_prompt = _apply_prompt_anchor(ugc_style, image_prompt, product_name,
                                            category=category, subcategory=subcategory,
                                            body_part=profile.get("body_part", ""))
        negative = _load_image_negative()  # SSOT prompt_sources.json (owner 2026-08-25)
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
    image_prompt = _apply_prompt_anchor(ugc_style, image_prompt, product_name,
                                        category=category, subcategory=subcategory,
                                        body_part=profile.get("body_part", ""))
    negative = _load_image_negative()  # SSOT prompt_sources.json (owner 2026-08-25)
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
        # Owner 2026-08-29 15:28: IMAGE ไม่ทาผลิตภัณฑ์อีกต่อไป — "รูปเลิกทาไปเลย"
        # (image มีแค่ท่าถือสินค้า ตาม recipe review=วาง/อื่น=ถือ) การทาครีม/เกลี่ย
        # ให้เกิดใน VIDEO prompt scene 2 เท่านั้น (ไม่ใช่ image). เดิมตรงนี้ special_target/
        # face_cream/makeup → "applying a light even layer to her face ... light even
        # coverage" (ภาพติดหน้าทุกอัน) ถูกเอาออกแล้ว เก็บไว้ท่าถือสินค้าเท่านั้น.
        # (image มีแค่ท่าถือสินค้า ตาม recipe review=วาง/อื่น=ถือ) การทาครีม/เกลี่ย
        # ให้เกิดใน VIDEO prompt scene 2 เท่านั้น (ไม่ใช่ image). ลบ path apply ทั้งหมด
        # ที่ทำให้ภาพติดหน้า/ทาหน้าทุกอัน ทิ้งไป (เดิม special_target/face_cream/makeup
        # → "applying a light even layer to her face ... light even coverage").
        base = (
            f"{model_desc} holding the product(s) from the reference image, "
            f"bottles facing the camera, smiling warmly with a bright cheerful expression, "
            f"{scene}"
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
    ugc_style: str, video_prompt: str, vp_product: str = "",
    category: str = "", subcategory: str = "", body_part: str = "",
) -> str:
    """Append the per-style prompt_anchor (from UGC_STYLES config) to the video
    prompt so Wan knows the shot/composition anchor it must follow. The anchor
    substitutes {product} / [product] placeholders with the (cleaned) product
    name. Falls back to the original prompt if the style has no anchor.

    Auto-update (owner 2026-08-29): for cream/beauty/skincare apply products the
    anchor is served from the SSOT `apply_cream` style (ugc_styles.json) with the
    target body area pulled from SSOT apply_hints — so editing the SSOT (area /
    wording) auto-updates the anchor instead of hardcoding a hold pose.
    """
    style = (ugc_style or "").strip().lower()
    # review is a TALKING style, but gets its OWN placed-on-table anchor
    # (review.prompt_anchor in ugc_styles.json, owner 2026-08-26). Only
    # talking_head keeps the stable fixed-framing anchor. review no longer
    # maps to talking_head so its dedicated anchor is used.
    if style in ("talking", "talking_head"):
        style = "talking_head"
    # ── Owner 2026-08-29 19:19: review KEEPS its own placed-on-table anchor ──
    # review = วางสินค้าบนโต๊ะ พูดรีวิว มือนิ่ง ไม่ถือ ไม่ทาครีม. The apply_cream
    # override below (for cream/beauty/skincare) must NOT replace the review
    # anchor, otherwise a cream product on a review recipe ends up smearing it
    # on the face instead of leaving it on the table (owner: "เอาตามเดิม").
    #
    # ── Owner 2026-08-30 06:04: HOLDING is exempt from the apply_cream
    # override too. holding = ถือสินค้าพูดอย่างเดียว ไม่ทา ไม่ถูกแย่งไปทาครีม
    # แม้สินค้าจะเข้าข่าย apply (skincare/beauty/apply_hints/body_part). กรณีที่
    # พี่ต้องการ "ถือพูดอย่างเดียว" ต้องไม่หลุดไปเป็น apply_cream formula.
    # (ปัญหาทาครีมไม่ตรงจุดจะแก้ละเอียดที่ apply area ทีหลัง — ไม่ใช่ตรงนี้)
    _is_review_hold = style == "review" or style == "product_demo"
    _is_hold_style = style == "holding" or _is_review_hold
    sub2 = (subcategory or "").strip().lower()
    cat2 = (category or "").strip().lower()
    bp2 = (body_part or "").strip().lower()
    _FACE_CREAM = {"sunscreen", "moisturizer", "serum", "eye_cream", "toner",
                   "face_whitening", "foundation"}
    # Owner 2026-08-29: a product is an "apply" (cream/lotion/serum) when its
    # category is skincare, or subcategory is in SSOT apply_hints (auto — covers
    # moisturizer/body_whitening/underarm_cream/stretch_marks/toner/... all spots:
    # face/arm/belly/underarm/foot), or body_part points at a body area (not hand).
    _apply_hints_keys = set()
    _ah_loaded = {}
    try:
        _ah_loaded = _load_ssot_extras()["apply_hints"]
        _apply_hints_keys = set(_ah_loaded.get("by_subcategory", {}).keys())
    except Exception:
        _apply_hints_keys = set()
    _is_apply = (
        (
            cat2 == "skincare"
            or cat2 == "beauty"
            or ("makeup" in sub2)
            or (sub2 in _FACE_CREAM)
            or (sub2 in _apply_hints_keys)
            or (bp2 and bp2.replace(" ", "-").replace("_", "-") not in ("hand", "hands"))
        )
        and not _is_hold_style  # review/product_demo วางบนโต๊ะ ไม่ทา ; holding ถืออย่างเดียว ไม่ทา (owner 2026-08-30)
    )
    if _is_apply:
        try:
            _ah = _ah_loaded or _load_ssot_extras()["apply_hints"]
            _area = (
                _ah["by_body_part"].get(bp2.replace(" ", "-").replace("_", "-"))
                or _ah["by_subcategory"].get(sub2)
                or _ah["by_category"].get(cat2)
                or _ah["default_area"]
            )
            _styles = _load_ugc_styles().get("UGC_STYLES", {})
            cream_anchor = (_styles.get("apply_cream", {}) or {}).get("prompt_anchor")
            if cream_anchor:
                anchor = (cream_anchor.replace("[product]", vp_product.strip() or "the cream")
                                    .replace("{product}", vp_product.strip() or "the cream")
                                    .replace("{area}", _area))
            else:
                anchor = None
        except Exception:
            anchor = None
        if anchor:
            # SSOT apply_cream anchor wins over the generic style anchor for cream.
            return video_prompt.rstrip() + f" Composition: {anchor.strip()}".rstrip()
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
        # Owner 2026-08-29: beauty/makeup → ใช้ท่าทำเมคอัพ (apply_hint) แทนถือสินค้า
        # เพื่อให้วิดีโอแต่งหน้าจริง ไม่ใช่แค่ถือ แล้วยิ้ม (กันไม่ยิ้มหลายคลิป)
        _sub2 = ((profile.get("subcategory") or "").strip().lower())
        _cat2 = ((profile.get("category") or "").strip().lower())
        _do_makeup = ("makeup" in _sub2) or ("beauty" == _cat2 or "beauty" in _cat2)
        # Owner 2026-08-29: face-cream products must blend onto the FACE (not hold).
        # ── Owner 2026-08-30 06:24: ตาม recipe/UGC — ถ้าผู้ใช้เลือก ugc_style เป็น
        # holding ให้ได้ฉากถือพูดอย่างเดียวเสมอ ไม่ถูกบังคับทาหน้าแค่เพราะสินค้าเป็น
        # ครีม/beauty/face-cream. การทาครีมยังทำได้ปกติเมื่อเลือก style ที่เป็นทา
        # (usage/apply_cream) เพราะตรงนี้กันแค่ holding ออกจากสูตรทาเท่านั้น.
        _FACE_CREAM = {"sunscreen", "moisturizer", "serum", "eye_cream", "toner", "face_whitening", "foundation"}
        _style_l = (ugc_style or "").strip().lower()
        _do_apply_face = (_do_makeup or (_sub2 in _FACE_CREAM)) and _style_l != "holding"
        apply_hint = _apply_hint(subcategory, category, profile) if (_is_special or _do_apply_face) else (
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
            # Product must stay SHARP and STILL-ish — Wan warps the label when the
            # prompt asks for zoom in/out or flowing camera motion (owner bug 2026-08-23).
            # So we implement the owner's 2 fixes (2026-08-26) WITHOUT moving the camera:
            #   1) FRAMING: “tight close-up, product fills the frame” (สินค้าเด่น ไม่ไกล)
            #   2) MICRO-MOTION: subtle hand turns + facial micro-expressions (ไม่นิ่งแข็ง)
            #   → แต่ห้ามบอก zoom-in/out/ดอลลี่ เพราะ Wan จะ morph เบลอสินค้า
            # วิธีทำ close-up ให้ชัด: ยึด reference image + “label crisp and clearly readable”
            # ไม่ใช่บอกกล้องขยับจ่อเข้า (เสี่ยง blur)
            # FIX 2026-08-25 (owner): sync กับ klein last-frame (วางสินค้าลงโต๊ะ)
            # เดิม Scene 4 บอก "holds toward camera" → ขัดกับ last frame ที่วางบนโต๊ะ
            # → Wan งง ถือสินค้าผิด/morph กลางคลิป (owner bug vid_e011300f)
            beats = [
                f"Scene 1: {gender_en} holds {vp_product} up close to the camera in a tight close-up, product fills the frame and dominates the shot, label crisp and clearly readable, {gender_en} gives a warm natural smile",
                f"Scene 2: keep holding {vp_product} close and steady, only a gentle natural hand motion turning the product slightly to show another angle, product stays sharp and readable",
                f"Scene 3: still holding {vp_product} in the same close-up, a subtle micro-expression (gentle eyebrow and corner-of-mouth movement) while keeping the product centered and sharp",
                f"Scene 4: {gender_en} still holding {vp_product} in the same tight close-up, a soft natural smile toward the camera, product stays sharp and centered, no putting down, no hand release",
            ]

            # Owner 2026-08-29: beauty/makeup + face-cream → เบี่ยงท่าจากถือสินค้าเป็น
            # ทาเกลี่ยบนหน้าจริง (SSOT makeup_tutorial ไม่มี field visual เลยตก fallback
            # เป็นถือสินค้า — ตรงนี้ให้ใช้ action/scene ของ product เพื่อให้ทำท่าทาผิวจริง)
            if _do_apply_face:
                _mk_action = (profile.get("action") or "").strip() or (
                    (selected.get("action") if isinstance(selected, dict) else "") or ""
                )
                if _mk_action:
                    _mk_action = re.sub(r'\s+', ' ', _mk_action).strip()
                else:
                    # No profile/selected action: use the light-even-layer / gentle
                    # blend hint (owner 2026-08-29: ครีมต้องจาง ๆ เกลี่ยเบา ๆ ไม่เป็นก้อน).
                    _mk_action = _apply_hint(subcategory, category, profile)
                # Owner 2026-08-29 17:54: start/apply/stop ชัดเจนบนหน้า — ไม่ใช่แค่ holds/continues
                # Scene 2 = เริ่มยกมือแตะครีม, Scene 3 = เกลี่ยให้ทั่วหน้า, Scene 4 = หยุดทา โชว์ผล
                beats = [
                    f"Scene 1: {gender_en} holds {vp_product} up close to the camera, label crisp, {gender_en} gives a warm natural smile",
                    f"Scene 2: {gender_en} begins applying {vp_product} by gently dabbing it onto her face with fingertips, the cream touching her cheek",
                    f"Scene 3: {gender_en} blends {vp_product} evenly over her entire face with a soft circular motion, cream fully spread on the skin, face kept clear and forward",
                    f"Scene 4: {gender_en} finishes applying, stops her hands, gently lowers them, turns her smoothened face to the camera and smiles showing the finished even result while {vp_product} stays visible beside her",
                ]

        video_prompt = (
            "A Thai woman naturally speaks the following Thai lines aloud to camera "
            "while keeping the product in a tight close-up throughout:\n\n"
            + "\n".join(beats)
            + "\n\nKeep the same woman and product in every scene, keeping the product in a tight close-up "
            "throughout, the product stays sharp and clearly readable, the model makes only small natural "
            "micro-movements (subtle hand turns and gentle facial expressions), never moving the camera away "
            "from the product. "
            # Owner guard 2026-08-30 (ภาษาไทยล้วน): กัน Wan พูดมั่วต่อท้ายสคริปต์.
            # หลังพูดจบบทแล้ว ให้หยุดพูดทันที ไม่พูดเกินกว่านั้น ไม่มีเสียงฟุ่มเฟือยตอนท้าย
            # (owner 12:28: อย่าเพิ่ม "ยิ้มอยู่นิ่ง ๆ จนจบฉากสุดท้าย" — มันทำให้ Wan freeze frame).
            "หลังจากพูดจบบททั้งหมดแล้ว ให้หยุดพูดทันที ไม่พูดอะไรเพิ่มเติม ไม่มีเสียงต่อท้าย"
        )
        logger.info(f"  Video prompt (4-beat, {len(video_prompt)} chars):")
        video_prompt = re.sub(r'[ \t]+', ' ', video_prompt).strip()
        logger.info(f"  Video prompt (4-beat, {len(video_prompt)} chars multi-line):")
        for l in video_prompt.split('\n'):
            logger.info(f"    {l}")
        return _apply_prompt_anchor(ugc_style, video_prompt, vp_product,
                                    category=profile.get("category", ""),
                                    subcategory=profile.get("subcategory", ""),
                                    body_part=profile.get("body_part", ""))

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
        elif style_l == "ambient_outdoor":
            # Owner 2026-08-31: ambient outdoor = product glowing in a night garden /
            # patio, NO person and NO hands (outdoor/solar lights). Not a studio rotate
            # (product_demo) nor a first-person hands clip (pov) — the product sits
            # among plants, softly glowing, gentle ambient motion.
            # Owner 2026-08-31 (โคมไฟติดผนัง BK-8518 "มันต้องอยู่กับ outdoor"): reuse
            # the category_mapping wall_light scene/action so wall-mounted lights get a
            # wall / fence / entrance-gate scene, not a generic garden bed.
            _amb_scene = (selected.get("scene") or "among garden plants and greenery")
            # ambient_outdoor: product is PLACED/GLOWING among plants, never held —
            # selected.action often says "holds ... showing" (person template) which
            # contradicts the no-person rule and makes Wan put hands in frame (owner
            # 2026-09-01 16:12). Swap to a passive glow verb so the clip stays person-free.
            _amb_action_raw = (selected.get("action") or "").strip()
            if any(w in _amb_action_raw.lower() for w in ("hold", "hand", "show", "pick up", "hold up")):
                # strip leading verb that implies a person; keep the light behaviour
                _amb_action = "glowing softly among the plants, its warm light gently visible"
            else:
                _amb_action = _amb_action_raw or "glowing softly"
            # Owner 2026-09-01 16:12: เปลี่ยนมุม/ซูมที่ beat 2,3 (ภายในคลิปเดี่ยว 9:16)
            # ในฉากสวนเดียวนั้น ไม่เปลี่ยน scene (พี่ยืนยัน "ใช่") — beat 2 จ่อกล้องใกล้ไฟ
            # เบา ๆ, beat 3 ถอยมุมกว้างขึ้นเล็กน้อย, beat 4 settle กลับโปรดักต์ชัด.
            # ห้ามบอก zoom/dolly ตรง ๆ หนักเพราะ Wan morph สินค้า — ใช้ perspective shift
            # แบบค่อย ๆ + ยึด product "sharp and centred" ในทุก beat (owner bug 2026-08-23).
            _ground_hint = (
                " sits low near the garden soil/stakes, not raised high off the ground"
                if ((profile.get("subcategory") or "") in ("solar_light",) or any(w in (profile.get("subcategory") or "") for w in ("stake","path","plant")))
                else ""
            )
            video_prompt = (
                f"Single continuous 9:16 shot in one night garden scene: {_amb_scene}. "
                f"The {_vp_product} {_amb_action}{_ground_hint}."
                f" Beat 1: wide establishing shot, {_vp_product} glowing softly among the plants, product visible but from a wider angle, product sharp. "
                f"Beat 2: the camera drifts in closer toward the {_vp_product}, a slightly lower angle beside the glow, warm golden light filling the frame, product stays sharp and centred. "
                f"Beat 3: the camera eases back out to a slightly wider angle taking in the whole {_amb_scene} at night, the {_vp_product} clearly glowing as the focus point, product sharp. "
                f"Beat 4: settle back on the {_vp_product} centre-frame, gentle bokeh, subtle ambient glow, product sharp and clearly shown, then {_result} at {_end_cam}. "
                f"No person, no hands in frame, smooth steady continuous motion, one unbroken shot, 9:16, warm golden light"
            )
        else:  # product_demo
            video_prompt = (
                f"Pure product shot of the {_vp_product}, clean studio background, "
                f"the product slowly rotates 360 degrees showing its label and packaging, "
                f"smooth continuous rotation, no human, no hands in frame, crisp focus, "
                f"then settles centered showing {_result} at {_end_cam}, 9:16, smooth motion"
            )
        video_prompt = _apply_prompt_anchor(ugc_style, video_prompt, _vp_product,
                                            category=profile.get("category", ""),
                                            subcategory=profile.get("subcategory", ""),
                                            body_part=profile.get("body_part", ""))
        # No-human styles have no person/hands to lip-sync — skip the mouth steer
        # even when a script exists (Wan would add fake lip micro-movements to a
        # product-only scene; ambient_outdoor in particular must stay person-free).
        logger.info(f"  Video prompt (no-human {style_l}, no mouth steer, {len(video_prompt)} chars): {video_prompt[:80]}...")
        return video_prompt

    if ugc_style in ("talking", "talking_head"):
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
    elif ugc_style == "review":
        # Review recipe (owner 2026-08-26): product PLACED ON THE TABLE, not held.
        # Split from talking/talking_head so holding/talking keep holding the product.
        _vp_product = _clean_product_name_for_video(product_name)
        review_scene = (
            "a clean bright tabletop, upper body, facing directly to the camera, "
            f"the {_vp_product} placed on the table in front"
        )
        start_part = (
            f"{gender_en} speaking naturally with a warm bright smile, subtle head movement, "
            f"hands resting still on the tabletop, with the {_vp_product} placed on the "
            f"table in front, reviewing it honestly while smiling warmly, {review_scene}"
        )
        # Review end: STOP talking, hands stay still on the table, product stays placed.
        # Guard หยุดพูด / ยิ้มจบฉาก ถูกเติมจาก apply_mouth_steer() อยู่แล้ว (จุดรวม cover ทุก
        # style) — ห้ามใส่ guard ซ้ำตรงนี้อีก ไม่งั้น video_prompt จะมีภาษาไทยซ้ำ 2 รอบ (owner-2026-08-30).
        end_part = (
            "Face kept clear, then finishes speaking, "
            "hands staying still on the tabletop, smiling warmly with a bright cheerful expression"
        )
        transition = ""
        # Mouth/head-only motion; hands stay STILL on the table (no raising, no gesturing).
        # Owner 2026-08-26 14:20: เอาคำสั่งชี้มือออก (gesturing/gestures) เพราะ Wan
        # ยกมือขึ้นมาแล้วเพี้ยน — สั่งมือนิ่งแทนเพื่อครอบคลุมทั้ง start/end/lipsync.
        # Owner 2026-08-26 22:48: smile ทั้งยิ้มแย้ม ทั้งต้น/กลาง/ท้าย (พี่เจอไม่ยิ้ม).
        lipsync_part = (
            " subtle head movement, face kept clear and forward with a warm bright smile, "
            f"hands kept still on the tabletop, the {_vp_product} stays placed on the "
            f"table, sharp, no lifting it up"
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
    video_prompt = apply_mouth_steer(video_prompt, ugc_style, is_speaking=bool((script or "").strip()))

    logger.info(f"  Video prompt ({len(video_prompt)} chars): {video_prompt[:80]}...")
    return _apply_prompt_anchor(ugc_style, video_prompt, _clean_product_name_for_video(product_name),
                                category=profile.get("category", ""),
                                subcategory=profile.get("subcategory", ""),
                                body_part=profile.get("body_part", ""))
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


def _load_image_negative() -> str:
    """Load the image negative prompt from prompt_sources.json 'image_negative.base'
    (single source of truth). Owner 2026-08-25: no hardcoded negative in code.
    Raises if the block is missing — no silent fallback."""
    sources = _load_prompt_sources()
    block = sources.get("image_negative")
    if not isinstance(block, dict) or not str(block.get("base", "")).strip():
        raise ValueError("prompt_sources.json missing or empty 'image_negative.base' — add it")
    return str(block["base"]).strip()


def build_negative_prompt(profile: dict, ugc_style: str = "holding", is_speaking: Optional[bool] = None) -> str:
    """Build negative prompt — defaults (text/watermark/hands/distortion)
    + Wan identity-stability terms (anti-morph / anti-melt).
    Caller no longer needs to merge — this is the complete negative.

    Mouth-control is style- AND speech-aware (data-driven from prompt_sources.json):
      - Speaking jobs (is_speaking=True, e.g. thai_script present / voice mode A)
        → SOFT mouth terms (restrain but allow speech) regardless of visual style.
        CRITICAL: TUS recipe "holding" + Voice A speaks Thai; visual style alone
        was non_talking → would have applied HARD lock, killing the speech we want.
      - Explicit non-speaking (is_speaking=False) → HARD lock from non_talking list.
      - Unknown (is_speaking=None, legacy) → fall back to style lists
        (talking_styles → soft, non_talking_styles → hard).
        NEVER "no open mouth" for speakers — that kills speech entirely.
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
    # Summary-first order so truncation at the 500-char Prodia cap loses the tail
    # verbs first while keeping the "closed and in hand" anchor.
    anti_open = "" if is_no_human_style else (
        "product stays closed and in hand, no opening the product, no uncapping, "
        "no squeezing, no pumping, no unpacking, no taking the product out of its box"
    )
    if is_speaking is True:
        # A talking style with a script gets the talking steer; but a NO-HUMAN style
        # (no person/hands — product_demo/pov/ambient_outdoor) never has a person's
        # mouth to control, so prefer the non-talking (no open mouth) terms instead.
        if is_no_human_style:
            mouth_terms = ", ".join(x.strip() for x in mc["negative_non_talking"])
        else:
            mouth_terms = ", ".join(x.strip() for x in mc["negative_talking"])
    elif is_speaking is False:
        mouth_terms = ", ".join(x.strip() for x in mc["negative_non_talking"])
    elif _is_talking_style(ugc_style, mc):
        mouth_terms = ", ".join(x.strip() for x in mc["negative_talking"])
    else:
        mouth_terms = ", ".join(x.strip() for x in mc["negative_non_talking"])
    # Priority order: base (must survive) → mouth_terms (must survive) → anti_open
    # (sacrificial tail). Earlier parts are more likely to be cut otherwise.
    parts = [p for p in (base, mouth_terms, anti_open) if p]
    negative = ", ".join(parts)
    # Wan 2.7 hard-caps the negative prompt at ~500 chars — trim from the tail
    # (anti_open last, lowest priority) if we ever exceed it.
    if len(negative) > 500:
        neg = negative[:500]
        # never cut mid-word
        cut = neg.rfind(", ")
        if cut > 0:
            neg = neg[:cut]
        negative = neg
    return negative


def apply_mouth_steer(video_prompt: str, ugc_style: str = "holding", is_speaking: Optional[bool] = None) -> str:
    """Append positive steer keywords to a video prompt for talking styles.
    These go in the POSITIVE prompt (not the negative) so Wan moves the mouth
    in small, natural, restrained ways instead of wide/jaw-heavy gesticulation.
    Non-talking / unknown styles get no steer (they shouldn't be talking)."""
    mc = _load_mouth_control()
    # Speaking-detection mirrors build_negative_prompt() so a "holding" visual
    # with a Thai script still gets the positive lip-sync steer (not skipped).
    if is_speaking is not None:
        if not is_speaking:
            return video_prompt
    elif not _is_talking_style(ugc_style, mc):
        return video_prompt
    steer = [x.strip() for x in mc["steer_talking_prompt"]]
    steer_text = ", ".join(steer)
    # Owner guard 2026-08-30 (ภาษาไทยล้วน): ทุก talking style (holding/talking/review/usage)
    # ตอนมีสคริปต์พูด ต้องหยุดพูดทันทีหลังจบบท (กัน Wan พูดมั่วต่อท้ายสคริปต์ — owner: "อันอื่นมันก็พูด").
    # owner 12:28: อย่าเพิ่ม "ยิ้มอยู่นิ่ง ๆ จนจบฉากสุดท้าย" — มันทำให้ Wan freeze frame
    # (ปล่อย micro-expression ธรรมชาติตาม steer เดิม). ใส่ต่อท้าย steer
    # เพราะ anchor ถูกเติมไปแล้วก่อนหน้านี้ (anchor ต้องอยู่ท้ายสุด ไม่ชนกัน).
    if is_speaking:
        steer_text += (
            ", หลังจากพูดจบบทแล้วให้หยุดพูดทันที ไม่พูดอะไรเพิ่มเติม ไม่มีเสียงต่อท้าย"
        )
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
    subcategory: str = "",
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
        # 🔴 2026-08-26: ไมเอา colors จาก Mistral vision มาใส่ profile แลว
        # เพราะ Mistral เดาสีที่ 2/3 เกินจริง (yellow/gold/light_yellow) ที่ไมมี
        # ในสินคาจริง → ทำให image prompt ได color palette เพี้ยน → Nano Banana วาดสีผิด
        # ปลอย colors วา ง -> `if colors else ""` ที่บรรทัด 659 จะไมแทรก palette
        # -> Nano Banana ยึดสีจาก reference image (pipeline บรรทัด 515 ครอบอยูแลว: same colors as input)
        # field "colors" ที่ 1412 ยังคงสงคืนใหครบ เพื่อไมให MCP/backend พัง
        if False and "colors" in vision_profile and vision_profile["colors"]:
            profile["colors"] = vision_profile["colors"]

    # Ensure target_gender is explicitly resolved
    if profile.get("target_gender", "") in ("", None):
        profile["target_gender"] = "person"

    # Override with explicit params if provided
    if category:
        profile["category"] = category
    if subcategory:
        profile["subcategory"] = subcategory
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
    # FIX (owner 2026-08-25 "เชื่อมเลย"): wire the SSOT-assembled video negative
    # into the live path. build_negative_prompt() existed but was never called,
    # so Wan received the IMAGE negative (no mouth-lock terms) and could
    # improvise speech. This is the only consumer feeding Prodia img2vid.
    # Speaking detection: if caller (or router via tv.full_script) provided a
    # spoken script (TTS voice mode A / thai_script), force SOFT mouth treatment
    # regardless of visual style. Visual style "holding" alone used to land in
    # non_talking_styles → HARD lock → contradicted the speech instruction.
    _is_speaking = bool((_spoken_script or "").strip())
    negative_prompt = build_negative_prompt(profile, ugc_style, is_speaking=_is_speaking)  
    
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


# ─── Thai transliteration for common brand/spec tokens (owner 2026-08-29) ───
# Rule-based so Wan can speak roman brand names in Thai. Only maps real brands/
# specs that appear in actual jobs; unknown Latin stays as-is. NOT a per-brand
# goldmine — missing ones fall back to the existing Latin handling below.
_THAI_NUM = ["ศูนย์", "หนึ่ง", "สอง", "สาม", "สี่", "ห้า", "หก", "เจ็ด", "แปด", "เก้า"]


def _thai_number(n: int) -> str:
    """Small integer -> Thai spoken digits (e.g. 50 -> ห้าสิบ, 1050 -> หนึ่งพันห้าสิบ)."""
    n = abs(int(n))
    if n == 0:
        return "ศูนย์"
    digits = list(str(n))
    num_map = {"0": "", "1": "หนึ่ง", "2": "สอง", "3": "สาม", "4": "สี่",
               "5": "ห้า", "6": "หก", "7": "เจ็ด", "8": "แปด", "9": "เก้า"}
    unit_map = {1: "", 2: "สิบ", 3: "ร้อย", 4: "พัน", 5: "หมื่น", 6: "แสน"}
    place = len(digits)
    out = []
    for ch in digits:
        unit = unit_map.get(place, "")
        val = num_map[ch]
        if place == 2 and ch == "1":
            val = ""  # สิบ not หนึ่งสิบ
        elif place == 2 and ch == "2":
            val = "ยี่"  # ยี่สิบ
        if place == 1 and ch == "1" and len(digits) > 1:
            val = "เอ็ด"  # 21 -> ยี่สิบเอ็ด
        if val:
            out.append(f"{val}{unit}" if unit else val)
        elif not out and place == 2:
            out.append(unit)  # handle 10 -> สิบ
        place -= 1
    return "".join(out)


_THAI_TUP_SAP = {
    # Brands seen in real jobs
    "d r . p o n g": "ดร.พงษ์",
    "dr pong": "ดร.พงษ์",
    "drpong": "ดร.พงษ์",
    "skinshe": "สกินชี",
    "gluta": "กลูต้า",
    "glutacollagen": "กลูต้าคอลลาเจน",
    "collagen": "คอลลาเจน",
    "moleculogy": "โมเลคิวโลจี้",
    "zeblanc": "เซแบล็งค์",
    "vaseline": "วาสลีน",
    "y erp all": "เยอร์พอล",
    "yerpall": "เยอร์พอล",
    # Spec / units / numeric readouts (spoken Thai)
    "spf": "เอส พี เอฟ",
    "pa": "พี เอ",
    "ml": "มิลลิลิตร",
    "g": "กรัม",
    "cream": "ครีม",
    "serum": "เซรั่ม",
    "sunscreen": "ซันสกรีน",
    "moisturizer": "มอยส์เจอร์ไรเซอร์",
    "mask": "มาส์ก",
    # Owner 2026-08-30: widen transliteration table so real product names stay spoken
    # (keep brand + series/model + unit, NOT dropped like the old "drop latin junk" logic).
    # Series / product-type words -> spoken Thai.
    "renewal": "รีนิวเวิลด์",
    "renew": "รีนิว",
    "renewing": "รีนิววิ่ง",
    "jelly": "เจลลี่",
    "eye": "อาย",
    "care": "แคร์",
    "lotion": "โลชั่น",
    "toner": "โทนเนอร์",
    "essence": "เอสเซนซ์",
    "cleanser": "คลีนเซอร์",
    "foam": "โฟม",
    "wash": "วอช",
    "face": "เฟซ",
    "body": "บอดี้",
    "hand": "แฮนด์",
    "oil": "ออยล์",
    "balm": "บาล์ม",
    "milk": "มิลค์",
    "mist": "มิสต์",
    "night": "ไนท์",
    "bright": "ไบรท์",
    "glow": "โกลว์",
    "whitening": "ไวเทนนิ่ง",
    "probiotic": "โปรไบโอติก",
    "vitamin": "วิตามิน",
    "repair": "รีแพร์",
    "repairing": "รีแพริ่ง",
    "firming": "เฟิร์มมิ่ง",
    "brightening": "ไบรท์เทนนิ่ง",
    "mineral": "มิเนอรัล",
    "active": "แอคทีฟ",
    "collagenboost": "คอลลาเจนบูสต์",
    "collagen": "คอลลาเจน",
    # Common gift/combo/set words
    "gifteset": "กิฟต์เซ็ต",
    "gift": "กิฟต์",
    "set": "เซ็ต",
    "combo": "คอมโบ",
    "starter": "สตาร์ทเตอร์",
    "kit": "คิท",
    # Brands / series seen in jobs
    "luna": "ลูน่า",
    "merlot": "แมร์โลต์",
    "skin1004": "สกินวันพันสี่",
    "centella": "เซนเทลลา",
    "karat": "คารัต",
    "aloe": "ว่านหางจระเข้",
    "cerave": "เซราวี",
    "drgroot": "ดร.กรูท",
    "plex": "เพล็กซ์",
    "line": "ไลน์",
    "tone": "โทน",
    "milky": "มิลค์กี้",
    "volume": "วอลุ่ม",
    "c": "ซี",
    # Owner 2026-08-30 10:57: keep the whole name spoken cleanly; widen the
    # table so -ing/-er/-common skincare words don't get spelled letter-by-letter
    # ("Moisturizing" was reading as single letters). Avoid cascading misreads.
    "moisturizing": "มอยส์เจอร์ไรซิ่ง",
    "moisture": "มอยส์เจอร์",
    "hydrating": "ไฮเดรติ้ง",
    "hydration": "ไฮเดรชั่น",
    "hydrate": "ไฮเดรท",
    "powder": "แป้งฝุ่น",
    "scrub": "สครับ",
    "gel": "เจล",
    "water": "วอเตอร์",
    "extract": "เอ็กซ์แทรกต์",
    "boost": "บูสต์",
    "booster": "บูสเตอร์",
    "perfect": "เพอร์เฟค",
    "vital": "ไวทัล",
    "liquid": "ลิควิด",
    "cleansing": "คลีนซิ่ง",
    "exfoliating": "เอ็กซ์โฟลิเอติ้ง",
    "exfoliant": "เอ็กซ์โฟลิเอ็นท์",
    "lifting": "ลิฟติ้ง",
    "tightening": "ไทท์เทนนิ่ง",
    "soothing": "ซูทติ้ง",
    "calming": "คาลมิ่ง",
    "nourishing": "นัวริชชิ่ง",
    "balancing": "บาลานซิ่ง",
    "purifying": "เพียวริฟายอิ้ง",
    "clarifying": "คลาริฟายอิ้ง",
    "radiance": "เรเดียนซ์",
    "radiant": "เรเดียนท์",
    "luminous": "ลูมินัส",
    "retinol": "เรตินอล",
    "niacinamide": "ไนอาซินาไมด์",
    "hyaluronic": "ไฮยาลูรอนิก",
    "hyaluron": "ไฮยาลูรอน",
    "salicylic": "ซาลิไซลิก",
    "peptide": "เปปไทด์",
    "cica": "ซิก้า",
    "acne": "สิว",
    "pore": "รูขุมขน",
    "pores": "รูขุมขน",
    "sebum": "ซีบัม",
    "spot": "จุดด่างดำ",
    "dark": "คล้ำ",
    "dull": "หมอง",
    "sun": "กันแดด",
    "tan": "แทน",
    "facial": "เฟเชียล",
    "foot": "เท้า",
    "lip": "ลิป",
    "soft": "ซอฟท์",
    "rich": "ริช",
    "deep": "ดีพ",
    "gentle": "เจนเทิล",
    "mild": "ไมลด์",
    "pro": "โปร",
    "watery": "วอเตอร์รี่",
    "toneup": "โทนอัพ",
    "coconut": "มะพร้าว",
    "rose": "กุหลาบ",
    "tea": "ชา",
    "green": "เขียว",
    "honey": "น้ำผึ้ง",
    "rice": "ข้าว",
    "sakura": "ซากุระ",
    "cherry": "เชอร์รี่",
    "matcha": "มัทฉะ",
    "orchid": "กล้วยไม้",
    "white": "ขาว",
    "gold": "ทอง",
    "silver": "เงิน",
    "snail": "หอยทาก",
    "bee": "ผึ้ง",
    "royal": "รอยัล",
    "stem": "สเต็ม",
    "shea": "เชีย",
    "argan": "อาร์แกน",
    "jojoba": "โจโจบา",
    "avocado": "อโวคาโด",
    "olive": "โอลีฟ",
    "rosehip": "โรสฮิป",
    "aha": "เอเอชเอ",
    "bha": "บีเอชเอ",
    "b5": "บีไฟว์",
    "cera": "เซร่า",
    # ── Owner 2026-08-30 14:46: พัดลมมือถือ + ไฟ solar (สินค้าใหม่) ──
    # ป้องกัน fallback สะกดทีละตัวอักษร (Ucloudsome->ยูซีแอลโอยูดี..., Solar->เอสโอแอล...)
    "ucloudsome": "ยูคลาวด์ซัม",   # แบรนด์พัดลมมือถือ
    "f88": "เอฟแปดสิบแปด",       # รุ่น
    "solar": "โซลาร์",
    "powered": "พาวเวอร์",
    "christmas": "คริสต์มาส",
    "oukeya": "โอกิยะ",       # brand (Thai name already in product_title)
    # Owner 2026-09-01: brands learned from AI (natural spoken Thai, not letter-by-letter)
    "minarita": "มินาริต้า",
    "ririko": "ริริโกะ",
    "kathy amrez": "เคธี่ แอมเรซ",
    "kathyamrez": "เคธี่ แอมเรซ",
    "kathy": "เคธี่",
    "amrez": "แอมเรซ",
    "bodana": "โบดาน่า",
    "classy": "คลาสซี่",
    "matte": "แมตต์",
    "cushion": "คุชชั่น",
    "string": "สตริง",
    "lights": "ไลท์",
    "light": "ไลท์",
    "led": "แอลอีดี",
    "rechargeable": "รีชาร์จเจอเบิล",
    "portable": "พกพา",
    "handheld": "มือถือ",
    "mini": "มินิ",
    "usb": "ยูเอสบี",
}

# ═══════════════════════════════════════════════════════════════════════
# Owner 2026-09-01 (แบบ 1b): auto-learn Thai name for unknown roman BRANDS.
# dict (_THAI_TUP_SAP) wins first; unknown pure-letter roman word falls here:
# ask Gemini ONCE for the natural spoken Thai brand name, cache it to a JSON
# file (tupsap_cache.json) so next time it is free and reused (no per-run AI).
# This replaces the old letter-by-letter spelling for brands (JOSE -> โจเซ่,
# CreamLab -> ครีมแล็บ) which sounded terrible.
# ═══════════════════════════════════════════════════════════════════════
_TUPSAP_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tupsap_cache.json")

def _load_tupsap_cache() -> dict:
    try:
        with open(_TUPSAP_CACHE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_tupsap_cache(cache: dict) -> None:
    try:
        with open(_TUPSAP_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"failed to save tupsap cache: {e}")

def _learn_thai_name(word: str) -> str:
    """Return spoken Thai name for an unknown pure-letter roman brand/word.
    Order: dict -> cache -> Gemini (once, cached). Never letter-by-letter."""
    key = re.sub(r"[^a-z0-9]", "", (word or "").lower())
    if not key:
        return word
    if key in _THAI_TUP_SAP:
        return _THAI_TUP_SAP[key]
    cache = _load_tupsap_cache()
    if key in cache:
        return cache[key]
    # ask Gemini for natural spoken Thai (NOT letter-by-letter)
    thai_name = None
    try:
        prompt = (
            "You transliterate a roman brand name into its NATURAL spoken Thai "
            "pronunciation as a Thai would say it on TikTok/Shopee. Do NOT spell "
            "letter by letter. Give the short spoken name only, no extra text. "
            "Brand: " + word + " "
            'Return JSON: {"thai":"..."}'
        )
        raw = _call_gemini("", prompt, temperature=0.2, max_output_tokens=40, response_mime_type="application/json")
        if raw:
            t = raw.get("thai") if isinstance(raw, dict) else None
            if not t and isinstance(raw, str):
                m = re.search(r'"thai"\s*:\s*"([^"]+)"', raw)
                t = m.group(1) if m else None
            if t:
                t = t.strip().strip("\"'").strip()
                if t:
                    thai_name = t
    except Exception as e:
        logger.warning(f"tupsap learn failed for {word}: {e}")
    if not thai_name:
        return word  # keep original (rare; will just be left as-is)
    cache[key] = thai_name
    _save_tupsap_cache(cache)
    return thai_name


def _tup_sap_name(name: str) -> str:
    """Transliterate roman brand/spec words to spoken Thai using _THAI_TUP_SAP.
    Whole-word, case/whitespace-insensitive. Unmatched Latin stays untouched."""
    if not name:
        return name
    def _norm_token(w: str) -> str:
        # lowercase, collapse all non-alnum to nothing for lookup
        return re.sub(r"[^a-z0-9]", "", w.lower())
    out_toks = []
    for w in re.split(r"(\s+)", name):
        if not w.strip():
            out_toks.append(w)
            continue
        key = _norm_token(w)
        if key in _THAI_TUP_SAP:
            out_toks.append(_THAI_TUP_SAP[key])
        else:
            out_toks.append(w)
    return "".join(out_toks)


def _tts_product_name(product_name: str) -> str:
    """Thai-dominant short name for SPOKEN script + BRAND kept (owner 2026-08-25:
    "มันไม่มีคำว่า Zeblanc อ่ะ" — brand must be spoken too).
    Owner 2026-08-29: transliterate roman brand/spec tokens to Thai so Wan can
    speak them (SPF50+ -> เอส พี เอฟ ห้าสิบพลัส, Dr.PONG -> ดร.พงษ์).
    Keeps Thai descriptor tokens, then appends transliterated Latin brand. Whole
    tokens only, no chopping.

    ⚠️ MARCKED BY OWNER 2026-08-30: "สคริปต์ผ่านแล้ว ตัดคำ ทับศัพท์ดีมาก ห้ามแก้".
    This function + _owner_script_variants + _drop_later_name_mentions +
    _fit_beat_text are the TRANSLITERATION baseline. DO NOT EDIT the transliteration
    / slicing logic without explicit owner instruction. Known open item: "7.5g"
    dropped earlier at product_short_for_tts/_shorten (not here) — ask before fixing.
    """
    name = (product_name or "").strip()
    if not name:
        return name

    # Owner 2026-08-29: drop bracketed promo/variant tokens like [สูตรใหม่], 【new】, (xxx)
    # so "ครีมโสมไฮยา [สูตรใหม่] เยอร์พอล" becomes "ครีมโสมไฮยา เยอร์พอล" for speech.
    name = re.sub(r"\s*[\[【（(][^\]】）)]*[\]】）)]\s*", " ", name).strip()
    # also drop leftover bare "สูตร"/"ใหม่" variant filler (e.g. "สูตรใหม่ ครีมโสม")
    name = re.sub(r"(?i)\b(?:(?:สูตร)?ใหม่|ใหม่สูตร|รุ่นใหม่|สูตร)\b", " ", name).strip()
    # Owner 2026-09-01: drop model/series CODES (รหัสรุ่น) from the spoken name.
    # Codes like "HS-090-2", "A-100-X" are inventory SKUs, NOT info a shopper
    # needs to hear; say the product NAME + selling points instead. Match latin
    # tokens that contain >=1 hyphen tying digits/letters together (a real model
    # code), which is distinct from a decimal like "U9.9" (ยูเก้าจุดเก้า, kept)
    # or hyphenless words. Also strips a leading "รุ่น" right before the code.
    name = re.sub(r"(?i)\bรุ่น\s+[a-z0-9]+(?:-[a-z0-9.]+){1,}\b", " ", name)
    name = re.sub(r"(?i)\b[a-z0-9]+(?:-[a-z0-9.]+){1,}\b", " ", name)
    # Owner 2026-09-01 15:40 (BROAD exception to the 08-30 "don't touch" mark):
    # drop the bare leading HS / brand-code prefix from a product name like
    # "HS ไฟ LED รูปต้นคริสต์มาส ..." . Plain "HS" (no hyphen) is a vendor/series
    # SKU prefix, not something a shopper needs to hear. We ONLY match the exact
    # token HS when it is followed by a Thai/known descriptor AND is NOT itself a
    # real brand in the tupsap (it isn't: brand list has no "hs"). Nothing else
    # is affected — LED/USB/solar etc are legitimate nouns that must stay.
    name = re.sub(r"(?i)\bhs\s+(?=[\u0E00-\u0E7F])", " ", name)
    name = re.sub(r"\s{2,}", " ", name).strip()

    # Numeric + plus/unit readouts first (SPF50+, PA+++, 30ml, 50g, 7.5g, 0.75ml)
    name = re.sub(r"(?i)\bspf\s*(\d+)\s*\+", lambda m: f"เอส พี เอฟ {_thai_number(int(m.group(1)))} พลัส", name)
    # PA+++ / PA++++ keep the whole readout. Match a Latin "PA" followed by at

    # followed by at least one "+" (so we never re-trigger on the already-spoken
    # "พี เอ" or on a stray "เอ"): SPF50+ PA+++ -> ... พลัส พี เอ พลัส (not "เอ").
    name = re.sub(r"(?i)\bpa\s*\++", "พี เอ พลัส", name)
    # decimal units (7.5g -> เจ็ดจุดห้ากรัม, 0.75ml -> ศูนย์จุดเจ็ดห้ามิลลิลิตร)
    name = re.sub(r"(?i)\b(\d+\.\d+)\s*ml\b", lambda m: f"{_thai_decimal(m.group(1))}มิลลิลิตร", name)
    name = re.sub(r"(?i)\b(\d+\.\d+)\s*g\b", lambda m: f"{_thai_decimal(m.group(1))}กรัม", name)
    # integer units
    name = re.sub(r"(?i)\b(\d+)\s*ml\b", lambda m: f"{_thai_number(int(m.group(1)))}มิลลิลิตร", name)
    name = re.sub(r"(?i)\b(\d+)\s*g\b", lambda m: f"{_thai_number(int(m.group(1)))}กรัม", name)
    # meter unit M/m (5M -> ห้าเมตร, 1.5M -> หนึ่งจุดห้าเมตร, 10M -> สิบเมตร)
    # placed AFTER ml/g so '30ml' is consumed as ml, not m.  Only bare M/m tokens
    # (preceded by a digit, not a letter) become เมตร.
    name = re.sub(r"(?i)\b(\d+\.\d+)\s*m\b", lambda m: f"{_thai_decimal(m.group(1))}เมตร", name)
    name = re.sub(r"(?i)\b(\d+)\s*m\b", lambda m: f"{_thai_number(int(m.group(1)))}เมตร", name)

    # Transliterate contiguous latin runs as whole units (brands, model codes).
    # Known words -> Thai via _THAI_TUP_SAP; unknown with digits -> spell as
    # model code (U9.9 -> ยูเก้าจุดเก้า); unknown pure letters -> spell by letter
    # so nothing silently disappears (owner 2026-08-30: keep whole real name).
    def _norm_key(t: str) -> str:
        return re.sub(r"[^a-z0-9]", "", t.lower())

    _LETTER = {"A":"เอ","B":"บี","C":"ซี","D":"ดี","E":"อี","F":"เอฟ","G":"จี","H":"เอช","I":"ไอ","J":"เจ","K":"เค","L":"แอล","M":"เอ็ม","N":"เอ็น","O":"โอ","P":"พี","Q":"คิว","R":"อาร์","S":"เอส","T":"ที","U":"ยู","V":"วี","W":"ดับเบิลยู","X":"เอ็กซ์","Y":"วาย","Z":"เซด"}

    def _spell_code(raw: str) -> str:
        """Spell a short latin token/run to spoken form: letters + thai digits."""
        out = []
        num = ""
        for ch in raw:
            if ch.isdigit():
                num += ch
            elif ch == ".":
                if num:
                    out.append(_thai_number(int(num))); num = ""
                out.append("จุด")
            elif ch.isalpha():
                if num:
                    out.append(_thai_number(int(num))); num = ""
                out.append(_LETTER.get(ch.upper(), ch))
            else:
                if num:
                    out.append(_thai_number(int(num))); num = ""
                out.append(ch)
        if num:
            out.append(_thai_number(int(num)))
        return "".join(out)

    def _trans_latin_runs(t: str) -> str:
        out_parts = []
        for part in re.split(r"([A-Za-z0-9.+\-]+)", t):
            if not part:
                continue
            if re.fullmatch(r"[A-Za-z0-9.+-]+", part) and re.search(r"[A-Za-z]", part):
                key = _norm_key(part)
                if key in _THAI_TUP_SAP:
                    out_parts.append(_THAI_TUP_SAP[key])
                elif re.search(r"\d", part):
                    out_parts.append(_spell_code(part))  # model code U9.9 -> ยูเก้าจุดเก้า
                else:
                    # Owner 2026-09-01 (แบบ 1b): unknown pure-letter roman -> learn
                    # Thai name via Gemini (cached), NOT letter-by-letter spelling.
                    out_parts.append(_learn_thai_name(part))
            else:
                out_parts.append(part)
        return "".join(out_parts)

    name = _trans_latin_runs(name)

    # Owner 2026-09-01 (ตัวพี่สั่ง): "ไฟแอลอีดี" must be one joined word (no space).
    # After transliteration, "ไฟ LED" becomes "ไฟ แอลอีดี" -> join to "ไฟแอลอีดี"
    # ONLY for the exact pattern <ไฟ> + <แอลอีดี> (a noun describing an LED lamp),
    # never when แอลอีดี leads ("แอลอีดี ไฟฉาย" must stay split) and never when
    # แอลอีดี is preceded by another descriptor ("โคมไฟ LED"/"หลอดไฟ LED" stay as
    # โคมไฟ แอลอีดี — only bare ไฟ joins).
    name = re.sub(r"(?<![ก-๙])ไฟ\s+แอลอีดี(?!\s*kห)", "ไฟแอลอีดี", name)


    # Owner 2026-09-01: convert any leftover plain Arabic integer counts (e.g.
    # "20 ดวง" -> "ยี่สิบดวง", "6 ชิ้น" -> "หกชิ้น") to spoken Thai. Only bare
    # integers NOT already consumed as ml/g/m units, so "30ml"/"5M" stay as
    # สามสิบมิลลิลิตร/ห้าเมตร (no double conversion). Unit word joins directly
    # (no space): "ยี่สิบดวง" not "ยี่สิบ ดวง".
    def _num_unit(m):
        n = _thai_number(int(m.group(1)))
        unit = (m.group(2) or "").strip()
        return n + unit if unit else n
    name = re.sub(r"\b(\d+)\s+([ก-๙][ก-๙\u0E47-\u0E4E]*)", _num_unit, name)
    name = re.sub(r"\b(\d+)\b", lambda m: _thai_number(int(m.group(1))), name)

    # Dedupe repeated Thai brand tokens (so "ครีมสกินชี สกินชี" stays
    # "ครีมสกินชี") but keep every latin-rendered word (owner 2026-08-25 dedupe).
    # Owner 2026-08-30: drop a transliterated brand that repeats the tail of the
    # previous Thai word (Skinshe -> "สกินชี" dup after "ครีมสกินชี") or is a
    # directly-adjacent Thai duplicate (วาสลีน วาสลีน). Do NOT drop a Thai word
    # that merely repeats an earlier word non-adjacently (SPF50+ PA+++ has two
    # "พี" from SPF and PA — both must stay: "พี เอฟ ... พี เอ พลัส").
    seen_full = set()
    kept_toks = []

    # Owner 2026-09-01 (ตัวพี่สั่ง, OUKEYA): the FULL product name sometimes repeats
    # as an ADJACENT WHOLE GROUP (e.g. "OUKEYA CLASSY MATTE CUSHION โอกิยะ คลาสซี่
    # แมตต์ คุชชั่น" -> the latin map AND the pre-existing Thai render to the SAME
    # group "โอกิยะ คลาสซี่ แมตต์ คุชชั่น โอกิยะ คลาสซี่ แมตต์ คุชชั่น"). Detect a
    # repeated adjacent group (tokens[i:i+K] == tokens[i+K:i+2K], K>=2 words) and
    # keep ONLY one copy. Works even when the repeat is not exactly half the whole
    # list (e.g. "A B C D A B C D E F"). Only exact same full-token groups collapse.
    _toks = name.split()
    _K = min(len(_toks) // 2, 5)
    _merged = False
    while _K >= 2 and not _merged:
        for i in range(0, len(_toks) - 2 * _K + 1):
            if _toks[i:i + _K] == _toks[i + _K:i + 2 * _K]:
                _toks = _toks[:i + _K] + _toks[i + 2 * _K:]
                _merged = True
                break
        if not _merged:
            _K -= 1
    if _merged:
        name = " ".join(_toks)

    for w in name.split():
        norm = re.sub(r"[^ก-๙]", "", w)
        if not norm:
            kept_toks.append(w)  # latin/mixed token, keep
            continue
        # drop directly-adjacent duplicate Thai (วาสลีน วาสลีน -> วาสลีน)
        if kept_toks:
            prev_norm = re.sub(r"[^ก-๙]", "", kept_toks[-1])
            if not prev_norm:
                kept_toks.append(w)
                continue
            # adjacent Thai duplicate
            if prev_norm == norm:
                continue
            # transliterated brand that is just the tail of the previous Thai word
            if prev_norm.endswith(norm) and len(norm) >= 3:
                continue
        kept_toks.append(w)
    cleaned = " ".join(kept_toks).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    # Strip leftover special/punctuation (keep "." for brand dot in ดร.พงษ์).
    # Owner 2026-09-01 (fix): "/" is a WORD SEPARATOR (e.g. สวน/ห้องนอน must read
    # "สวน ห้องนอน", not "สวนห้องนอน"), so turn it (and other separators) into a
    # space BEFORE removing leftover junk; never delete chars so two Thai words end
    # up glued together.
    cleaned = re.sub(r"[/\\]", " / ", cleaned)
    cleaned = re.sub(r"[\[\]()（）【】]", " ", cleaned)
    cleaned = re.sub(r"[^\u0E00-\u0E7F0-9A-Za-z.\s]+", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned or name


def _thai_decimal(dec_str: str) -> str:
    """'7.5' -> 'เจ็ดจุดห้า'; '0.75' -> 'ศูนย์จุดเจ็ดห้า'. Integer part via
    _thai_number; each decimal digit read individually."""
    _DIG = {"0":"ศูนย์","1":"หนึ่ง","2":"สอง","3":"สาม","4":"สี่","5":"ห้า","6":"หก","7":"เจ็ด","8":"แปด","9":"เก้า"}
    if "." not in dec_str:
        return _thai_number(int(dec_str)) if dec_str else ""
    whole, frac = dec_str.split(".", 1)
    if not whole or whole == "0":
        w = "ศูนย์"
    else:
        w = _thai_number(int(whole))
    f = "".join(_DIG.get(c, c) for c in frac if c.isdigit())
    return f"{w}จุด{f}"


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
    (>=4 chars) so TRUNCATED mentions (beat trimmer cuts mid-name) still match.

    ⚠️ MARCKED BY OWNER 2026-08-30 (DO NOT EDIT Latin/Thai token splitting):
    Only LATIN brand tokens are added standalone. Thai-rendered name pieces
    (พงษ์, ยูเก้าจุดเก้า, รีนิวเวิลด์) must NOT be drop targets — otherwise
    _drop_later_name_mentions chops the spoken name to "ดร. ครีม" (fix af0918cd).
    """
    import re as _re
    out = _name_variants(*bases)
    for b in bases:
        for w, _n in _brand_tokens(b):
            if len(w) >= 4:
                # Owner 2026-08-30: only add LATIN brand tokens as standalone
                # variants. Do NOT add Thai-rendered pieces (พงษ์, ยูเก้าจุดเก้า,
                # รีนิวเวิลด์) as drop targets: a Thai product-name fragment must
                # stay in the spoken name (fix: Dr.PONG ... -> "ดร.พงษ์" keeping
                # "พงษ์ ยูเก้าจุดเก้า รีนิวเวิลด์" instead of chopping to "ดร. ครีม").
                if not re.search(r"[\u0E00-\u0E7F]", w):
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


def _dedupe_cross_segment(segments: list) -> int:
    """Owner rule (2026-08-31): strip repeated CONTENT phrases across segments so
    the same meaningful claim (e.g. 'บรรยากาศอบอุ่นและรื่นเริง' appearing in both
    the hook [{problem}] and the solve [{benefit}]) is never spoken twice.

    Collects repeated substrings (>=4 clean chars) from earlier segments and
    removes any occurrence of that same substring from LATER segments (leaving
    the first intact), also cleaning dangling connectives. Returns the number of
    segments trimmed."""
    import re as _re
    # Thai has no spaces between words, so match repeated substrings of meaningful
    # length (>=4 Thai/ASCII chars, clean boundaries) instead of whitespace tokens.
    MIN_LEN = 4

    def _clean_phrases(text: str):
        """Extract candidate repeated substrings (all clean substrings >= MIN_LEN)."""
        out = set()
        t = text.strip()
        for i in range(len(t)):
            for j in range(i + MIN_LEN, min(len(t), i + 18) + 1):
                sub = t[i:j]
                # only keep substrings with no leading/trailing space and that
                # start & end on a Thai/letter boundary (avoid cutting mid-word junk)
                if sub.strip() != sub:
                    continue
                out.add(sub)
        return out

    prior_phrases = set()
    trimmed = 0
    for seg in segments:
        t = seg.get("text", "") or ""
        if not t:
            continue
        t2 = t
        # longest first so we cut the maximal repeated phrase
        for phrase in sorted(prior_phrases, key=len, reverse=True):
            if len(phrase) < MIN_LEN:
                continue
            if phrase in t2 and t2 != phrase:
                # Owner 2026-09-01 (ตัวพี่สั่ง, ไฟ LED): NEVER cut a repeated phrase
                # that sits MID-WORD in Thai (e.g. hook "บรรยากาศเทศกาลคริสต์มาส" vs
                # name "รูปต้นคริสต์มาส" — "คริสต์มาส" is a substring of a bigger
                # word here, cutting it leaves a dangling "รูปต้น"). Only strip when
                # the phrase is bounded by word-edges / non-Thai on both sides, so a
                # genuine repeated standalone phrase is removed but a Thai word that
                # merely CONTAINS the phrase is left intact.
                _mid = re.compile(
                    r"(?<![ก-๙])" + re.escape(phrase) + r"(?![ก-๙])"
                )
                if _mid.search(t2):
                    t2 = _mid.sub(" ", t2)

        if t2 != t:
            t2 = _re.sub(r"\s{2,}", " ", t2).strip()
            t2 = _re.sub(r"^(และ|หรือ|กับ|ที่|ของ|เพื่อ|เพื่อที่จะ)\s+", "", t2)
            t2 = _re.sub(r"\s+(และ|หรือ|กับ|ที่|ของ|เพื่อ)+$", "", t2).strip()
            if t2:  # guard: never empty a segment from over-aggressive dedupe
                seg["text"] = t2
                trimmed += 1
                t = t2
        # register this segment's clean phrases as prior for the NEXT segments
        prior_phrases |= _clean_phrases(t)
    return trimmed


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
    # Guard number+unit pairs (153 กรัม / 10 เมตร / 50 กรัม) as ONE token so a
    # unit is never severed from its number (owner 2026-08-31: '153 กรัม' must not
    # become a dangling '153'). We temporarily replace the space between a number
    # and a Thai unit with a non-breaking space, run the cut logic, then restore.
    _nb = "\u00A0"
    _unit_pat = re.compile(r"(\d+(\.\d+)?)\s+(กรัม|มิลลิลิตร|เมตร|มล|ลิตร|กก|กิโลกรัม|กรัม|ชิ้น|ดวง|เซนติเมตร|ซม)")
    def _lock_sep(m):
        return f"{m.group(1)}{_nb}{m.group(3)}"
    locked = _unit_pat.sub(_lock_sep, text)
    # Walk backward over the whole text, truncating at natural breaks.
    # IMPORTANT: split ONLY on plain spaces ([ \t]) so the non-breaking space
    # used to glue a number+unit stays INSIDE one token (\s would also match
    # \u00A0 and re-sever the pair).
    tokens = re.split(r"([ \t]+)", locked)
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
    # Restore real spaces from locked number+unit pairs, then trim any breakage.
    trimmed = trimmed.replace(_nb, " ")
    trimmed = re.sub(r"\s{2,}", " ", trimmed).strip()
    if not trimmed:
        # even the first word overflows — return first word (best effort)
        return tokens[0].replace(_nb, " ") if tokens else text
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


def _strip_promo_tokens(name: str) -> str:
    """Owner rule (2026-08-31): drop shop/promotional noise from a product name
    BEFORE the spoken script is built, so phrases like 'มีเก็บเงินปลายทาง',
    'COD', 'พร้อมส่ง' or bracketed prefix '【HS】' never leak into the voiceover.

    Only strips sales/marketing tokens + bracket framing. Leaves the real brand,
    attributes and quantities (153 กรัม / 5M) untouched. Does NOT touch the
    transliteration logic in _tts_product_name — this runs on the raw input only.
    """
    if not name:
        return name
    import re as _re
    t = name
    # Promotional / fulfillment / COD tokens (Thai + English), whole-word-ish.
    _promo = [
        "มีเก็บเงินปลายทาง", "เก็บเงินปลายทาง", "ปลายทาง", "พร้อมส่ง", "ส่งฟรี",
        "ส่งไว", "จัดส่ง", "มีโค้ด", "ลดราคา", "ราคาพิเศษ", "โปรโมชั่น", "โปรโมชัน",
        "ของแถม", "โค้ดลด", "official store", "best seller", "bestseller",
    ]
    for p in _promo:
        t = _re.sub(r"(?i)\s?" + _re.escape(p) + r"\s?", " ", t)
    # COD / FOB / free-ship style latin abbreviations (standalone, 2-4 letters).
    t = _re.sub(r"(?i)\b(?:cod|fob|freeship|sale|promo|deal|discount)\b", " ", t)
    # Bracket framing noise: 【HS】 / [...] / (รอบส่ง 24-48h) style prefixes.
    t = _re.sub(r"[\[\]【】]+", " ", t)
    t = _re.sub(r"\([^)]*(?:ส่ง|ราคา|โค้ด|COD|ปลายทาง)[^)]*\)", " ", t)
    # Collapse spaces / stray pipes / leading hyphens.
    # Owner 2026-09-01: drop model/series codes (HS-090-2, A-100-X) here, BEFORE
    # hyphens are stripped to spaces, so the code is removed as one unit and never
    # leaks back as "รุ่น เอชเอส เก้าสิบ สอง" after transliteration. Shopper does
    # not need to hear the inventory SKU.
    t = _re.sub(r"(?i)\b(?:รุ่น\s+)?[a-z0-9]+(?:-[a-z0-9.]+){1,}\b", " ", t)
    t = t.replace("|", " ").replace("-", " ")
    t = _re.sub(r"\s{2,}", " ", t).strip(" -")
    return t



# ─── Owner 2026-09-01: clean product title (rule + AI fallback) ───
# Owner direction: bad/messy product names in the DB are the root problem — rewrite
# the title to "clean" (brand + product type) FIRST so everything downstream (product_short,
# _tts_product_name, voiceover script) becomes good automatically. Rule-based first (free),
# only call Gemini when the rule can't produce a short clean result (falls back to AI).
_TITLE_PROMO = {
    "hs", "cod", "พร้อมส่ง", "ส่งฟรี", "จัดส่งฟรี", "เก็บเงินปลายทาง", "สั่งซื้อ",
    "โปรโมชั่น", "ซื้อ", "แถม", "ลด", "ลดราคา", "ลดราคาช็อก", "โปร", "ขายดี",
    "สินค้าขายดี", "ใหม่", "สูตรใหม่", "สูตรเก่า", "ต้นตำรับ", "ปราศจาก", "ของแท้",
    "ยกลัง", "ชุด", "เซต", "แพ็ค", "แพ็ก", "คุ้ม", "คุ้มค่า", "สุด", "มาก", "พิเศษ",
    "ราคาพิเศษ", "เฉพาะ", "ลดสนั่น", "โฮตเซล", "hot", "sale",
}
_TITLE_CUT = {
    "สำหรับ", "เพื่อ", "ใช้", "เหมาะ", "ตกแต่ง", "สร้าง", "ให้", "พร้อม", "กับ",
    "สามารถ", "ช่วย", "ทั้ง", "ขนาด", "ความ", "ยาว", "ของ", "ระยะ", "กำลัง",
    "เหมาะกับ", "ใน", "บน", "นอก", "งาน", "แบบ", "ชนิด", "เป็น", "ได้", "ไว้",
    "มา", "โดย", "และ", "หรือ", "ต่อ", "กัน", "ประหยัด", "ทนทาน", "เนียน", "นุ่ม",
    "บางเบา", "กลางวัน", "กลางคืน", "ตลอด", "วัน", "เปลี่ยน", "ดูแล", "บำรุง",
}
_TITLE_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)?[a-zA-Zก-๙]*$")

_TITLE_AI_SYSTEM = (
    "You clean a Thai e-commerce product title into a SHORT natural Thai phrase for a "
    "voiceover. Rules:\n"
    "- Output ONLY a clean phrase: brand + product type (or product type + brand).\n"
    "- MAX ~30 Thai chars. NO promotional words (ลดราคา, โปรโมชั่น, ซื้อ, แถม, COD, ส่งฟรี, "
    "เก็บเงินปลายทาง, ขายดี, ใหม่, สูตร, 100%, มี, ทาง, ชุดครบสูตร). NO model/unit codes "
    "(50g, 5M, 20ชิ้น). NO long benefit/description sentences.\n"
    "- Identify the REAL product type (ครีม, เซรั่ม, คุชชั่น, มาสคาร่า, สเปรย์, โคมไฟ, ยาสีฟัน...). "
    "NEVER echo promotional/sales phrases.\n"
    "- Keep brand as Latin if it is a roman brand (e.g. MINARITA), or Thai if the brand is "
    "already Thai. Do NOT spell a roman brand letter-by-letter.\n"
    "- Output ONLY one line of plain text. No quotes, no JSON, no explanation."
)

def rewrite_clean_title(title: str, category: str = "", profile: dict = None) -> str:
    """Owner 2026-09-01: rewrite a messy product title into a clean 'brand + product type'.
    Rule-based first (free, deterministic). Only when the rule result is too long / has leftover
    promo tokens / is empty does it call Gemini (via _call_gemini) for a short clean name.
    Does NOT touch the transliteration inner logic (_tts_product_name); it only cleans the INPUT.
    """
    if not title:
        return title
    original = title
    t = title.strip()
    # 1) bracketed promo [..]/【..】 -> drop whole bracket
    t = re.sub(r"[\[【][^\]】]*[\]】]", " ", t)
    # 2) unit brackets "(50g)", "(5M)" -> drop
    t = re.sub(r"\([^)]*(?:ml|กรัม|g|ซอง|ชิ้น|กล่อง|ชม|ชั่วโมง|เมตร|m)[^)]*\)", " ", t, flags=re.I)
    # 3) promo pattern "ซื้อ 1 แถม 1" / "1 หลอด แถมฟรี 1"
    t = re.sub(
        r"(?:ซื้อ|แถม|ลด)\s*\d+(?:\s*[a-zA-Zก-๙]+)?(?:\s*(?:แถม|ลด|ซื้อ)\s*\d+(?:\s*[a-zA-Zก-๙]+)?)*",
        " ", t,
    )
    # 4) model/series code HS-090-2 / A-100
    t = re.sub(r"\b(?:รุ่น\s*)?[A-Za-z0-9]+(?:-[A-Za-z0-9.]+){1,}\b", " ", t)
    # 5) single promo/connector words
    for w in _TITLE_PROMO:
        t = re.sub(r"(?i)(^|\s)" + re.escape(w) + r"(\s|$)", r"\1\2", t)
    t = re.sub(r"[|]", " ", t)
    t = re.sub(r"\s{2,}", " ", t).strip()
    # 6) walk tokens, stop at number/unit/cut-word
    out, cut = [], False
    for tok in t.split():
        wl = tok.strip(".,;:!()&/")
        low = wl.lower()
        if _TITLE_NUMBER_RE.fullmatch(low) or low in _TITLE_CUT or low in _TITLE_PROMO:
            cut = True
            break
        out.append(wl)
    cleaned = " ".join(out).strip()

    # Owner 2026-09-01 (guard): drop a roman token whose Thai render already appears
    # as part of a Thai word in the name, to avoid "ลูน่าอายครีม ... ลูน่า" repetition
    # (LUNA renders to ลูน่า which duplicates ลูน่า in ลูน่าอายครีม). Only drops tokens
    # we know a Thai form for (dict); does NOT call Gemini or touch transliteration.
    _rc_toks = cleaned.split()
    _rc_roman = [w for w in _rc_toks if re.fullmatch(r"[A-Za-z0-9.+\-]+", w) and re.search(r"[A-Za-z]", w)]
    _rc_thai_txt = re.sub(r"[A-Za-z0-9.\-]", "", " ".join(_rc_toks))
    def _rc_render(th):
        return th and len(th) >= 2 and re.search(re.escape(th), _rc_thai_txt)
    for _r in _rc_roman:
        _rc_th = _THAI_TUP_SAP.get(re.sub(r"[^a-z0-9]", "", _r.lower()), "")
        if _rc_render(_rc_th):
            _rc_toks = [w for w in _rc_toks if w != _r]
    cleaned = " ".join(_rc_toks).strip()

    # Rule verdict: good if 4 < len <= 45 and no leftover promo markers
    low2 = cleaned.lower()
    rule_good = (
        4 < len(cleaned) <= 45
        and "ซื้อ" not in cleaned
        and "แถม" not in cleaned
        and "โปร" not in low2
        and "ลด" not in cleaned
        and "hs" not in low2
        and "cod" not in low2
        and "พร้อมส่ง" not in cleaned
        and "ชุดครบ" not in cleaned
    )
    if rule_good:
        return cleaned

    # Rule did not produce a clean short name -> Gemini fallback
    try:
        result = _call_gemini(
            _TITLE_AI_SYSTEM,
            "Product title to clean:\n" + original,
            temperature=0.2,
            max_output_tokens=120,
        )
        if result:
            result = result.strip().strip('\"\'')
            if 2 <= len(result) <= 45:
                return result
    except Exception:
        pass
    # fallback: return the best-effort rule output (even if long), never empty the name
    return cleaned or original



def _build_timing_validated_script(product_name: str, category: str = "beauty", profile: dict = None) -> dict:
    """Build script segments with timing validation.

    Prefers the Router Agent's 4-beat scenes (router_config.scenes) so the script
    matches the chosen recipe (pas/comparison/secret_hook). Falls back to the old
    3-segment hook/value/cta structure when no scenes are present.
    Uses customer_problem + main_benefit from Gemini/Mistral analysis when available.
    Gender-aware: female register (คะ/ค่ะ) for female target_gender.
    """
    # Owner 2026-08-31: drop promotional/COD noise from the SPOKEN name first so
    # 'มีเก็บเงินปลายทาง' / '【HS】' never appear in the voiceover script.
    product_name = _strip_promo_tokens(product_name)
    # Owner 2026-09-01: rewrite messy title to clean 'brand + product type' first
    # (rule + AI fallback) so product_short / _tts_product_name / voiceover all get a clean input.
    # Owner 2026-09-01: use the clean title computed once in analyze_product
    # (profile["clean_title"]) — falls back to recompute only when called directly
    # without going through analyze_product.
    if profile and profile.get("clean_title"):
        product_name = profile["clean_title"]
    else:
        product_name = rewrite_clean_title(product_name, category, profile)
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

    # Owner 2026-08-29: spoken name = Thai transliterated from FULL product_name
    # (not product_short which may have the brand chopped off) so the beat reads the
    # brand in Thai (Dr.PONG -> ดร.พงษ์, Skinshe -> สกินชี).
    spoken_name = _tts_product_name(product_name or product_short)
    
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
        value_text = _normalize_thai_gender_register(f"{spoken_name} {_safe_thai_truncate(main_benefit, 45)}", is_female)
    elif category in ("home", "electronics", "tools"):
        hook_text = f"เจอปัญหานี้อยู่ใช่ไหม{reg_hook}"
        value_text = f"{spoken_name} ช่วยได้เยอะเลย{reg_val}"
    elif "blush" in category.lower() or "cheek" in category.lower():
        hook_text = f"อยากหน้าสดใส ดูมีมิติใช่ไหม{reg_hook}"
        value_text = f"{spoken_name} เติมแก้มสวยเป็นธรรมชาติ{reg_val}"
    elif "lip" in category.lower():
        hook_text = f"อยากปากฉ่ำวาว สวยทนนานไหม{reg_hook}"
        value_text = f"{spoken_name} ทาแล้วปากชุ่มชื้น สวยปัง{reg_val}"
    elif "mask" in category.lower() or "facial" in category.lower():
        hook_text = f"ผิวแห้ง หมองคล้ำ ต้องลองสักครั้ง{reg_hook}"
        value_text = f"{spoken_name} ช่วยบำรุงผิวชุ่มชื้นฉ่ำน้ำ{reg_val}"
    elif "serum" in category.lower() or "moisturizer" in category.lower():
        hook_text = f"อยากผิวใส ชุ่มชื้น แนะนำเลย{reg_hook}"
        value_text = f"{spoken_name} ซึมไว ไม่เหนอะหนะ{reg_val}"
    elif "concealer" in category.lower() or "corrector" in category.lower():
        hook_text = f"กลบรอยใต้ตา เนียนกริบ{reg_hook}"
        value_text = f"{spoken_name} ปกปิดเนียนสวย ไม่ตกร่อง{reg_val}"
    else:
        hook_text = f"ของดีต้องบอกต่อ{reg_hook}"
        value_text = f"{spoken_name} ใช้งานง่าย คุ้มค่ามาก{reg_val}"
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
        # Owner 2026-08-31: also drop repeated CONTENT phrases across beats so a
        # claim in both hook [{problem}] and solve [{benefit}] is spoken once only.
        _dedupe_cross_segment(segments)

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
    _spoken_fb = spoken_name or _tts_product_name(product_short)
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
