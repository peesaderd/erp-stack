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
    product-only triptych + no-human video branch instead of the holding/
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
    """Return a line-broken version of a triptych/3-panel image prompt for
    readability (display only). Wan/image API still uses the single-line
    `image_prompt`. Splits at 'Panel N (...): ' boundaries and the header.
    """
    if not image_prompt:
        return image_prompt
    # Split at each 'Panel N (...): ' marker into separate lines.
    parts = re.split(r"(?=Panel \d+\s*\()", image_prompt)
    lines = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        lines.append(p)
    # First line is the header (may contain '16:9 vertical triptych...')
    # Force the 'Product:' / appearance into its own line for readability.
    # Do the split BEFORE joining so 'Product:' doesn't get glued to Panel 3.
    rebuilt = "\n".join(lines)
    rebuilt = rebuilt.replace(" Product:", "\nProduct:")
    # Keep each Panel on its own line; ensure no stray double newlines.
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
    """Build a cover-page product description for the triptych cover panel.

    Panel 1 is a DESIGNED cover page — NOT a raw "exactly as shown in reference"
    (that made the model cram the product photo in whole and clip the label text).
    Tell the model to design a clean commercial cover using the brand from the
    reference, with the product(s) placed on it as a styled studio shot.
    """
    appearance = (profile or {}).get("product_appearance", "") or ""
    brand = _clean_brand_name(product_name)
    # Owner: NO 'OFFICIAL STORE' watermark — the model keeps painting that text
    # onto product/background panels and it looks cluttered/unwanted. Keep only a
    # subtle brand logo; instruct the model NOT to add any invented text/captions.
    logo = f"a subtle '{brand}' logo in the upper corner" if brand else "no extra text or logos"
    # Design a cover, don't copy the reference wholesale. Reference defines the
    # product/brand only; the model composes the layout so text stays legible.
    # Use the cleaned brand so the cover label matches the actual product.
    # NO invented text: brand text only from the real product label, never add
    # words like OFFICIAL STORE, BEST, 100%, etc. (owner: those leak onto panels).
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
    """Generate image prompt — triptych 16:9 (3-panel) when router scenes exist.

    Left = cover/hook, middle = model + product (solve), right = result/end (cta).
    Falls back to a single 9:16 frame when the profile has no router scenes / triptych.
    Uses _ai_select() for scene/action/camera/lighting from category_mapping, plus
    product_appearance / colors from Mistral analysis (P3).
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
    # Room/setting: prefer profile['setting'] (user set), else ai_select scene
    room = (profile.get("setting") or "").strip() or scene
    room_desc = room

    # ── NEW (P2): triptych / 3-panel composition from router beats ──
    router_config = profile.get("router_config", {}) if isinstance(profile, dict) else {}
    scenes = router_config.get("scenes") if isinstance(router_config, dict) else None
    use_triptych = (
        isinstance(scenes, list) and len(scenes) >= 2
        and profile.get("use_triptych") is not False
    )

    if use_triptych:
        # ── No-human styles (product_demo, pov): 3-panel triptych with NO person ──
        # Styles whose SSOT has_person flag is False must NOT show a person in
        # frame. The old code let every style enter the holding triptych template
        # before the legacy no-human branch could run, so no-human styles ended up
        # with people. We now build a dedicated no-human triptych and append the
        # style's prompt_anchor (SSOT ugc_styles.json) so the first frame matches
        # the video's no-human shot. product_demo = pure product; pov = first-person
        # (only the hands visible, no face), which is how POV video reads.
        if _is_no_human_style(ugc_style):
            style_l = (ugc_style or "").strip().lower()
            if style_l == "product_demo":
                cover_hint = _cover_product_desc(profile, product_name)
                # Panel 2 = close-up product detail (rotate to show packaging/label)
                mid_hint = (
                    f"{product_name} close-up product shot showing label and packaging "
                    f"details, product centered on clean background, {room_desc}"
                )
                # Panel 3 = feature/hero product shot (no person)
                result_hint = (
                    f"{product_name} feature product shot, product standing upright "
                    f"center frame, clean studio lighting, {lighting}"
                )
                no_human_clause = (
                    "NO humans, NO people, NO hands in any panel; pure product photography."
                )
            else:  # pov — first-person, hands visible holding/using the product
                cover_hint = _cover_product_desc(profile, product_name)
                # Panel 2 = first-person hands holding the product in a daily scene
                mid_hint = (
                    f"first-person POV of the user holding "
                    f"{product_name}, only the hands and product visible in frame, "
                    f"natural daily setting {room_desc}"
                )
                # Panel 3 = first-person using the product in daily context
                result_hint = (
                    f"first-person POV using {product_name} in a daily lifestyle context, "
                    f"only hands and product in frame, no face visible, {lighting}"
                )
                no_human_clause = (
                    "First-person POV throughout; no face of the person in any panel, "
                    "only hands and product visible."
                )
            colors = profile.get("colors", "") or ""
            parts_colors = f"color palette: {', '.join(colors)}. " if colors else ""
            image_prompt = (
                f"16:9 landscape triptych, three equal horizontal panels placed side "
                f"by side touching edge to edge with zero pixels of space between panels, "
                f"joined as one seamless 16:9 image. "
                f"{no_human_clause} "
                f"Panel 1 (left): {cover_hint}. "
                f"Panel 2 (center): {mid_hint}. "
                f"Panel 3 (right): {result_hint}. "
                f"Product: show exactly the item(s) from the reference product image — "
                f"render every variant/color that appears in it. "
                f"{parts_colors}{lighting}. "
                f"NO text, letters, words, labels, logos or watermark on panels 2 and 3 — "
                f"only the product, cleanly. "
                f"Cohesive consistent style, high quality product photography. "
                f"Render the full 16:9 frame edge to edge as one continuous surface; the "
                f"three panels touch one another with 0 pixels of gap or margin between "
                f"panels — no divider, no seam, no spacing anywhere in the image."
            )
            logger.info(f"  Image prompt (no-human {style_l} triptych, {len(image_prompt)} chars)")
            # Append the style's image anchor (from SSOT ugc_styles.json) so the
            # composition matches the video's no-human shot.
            image_prompt = _apply_prompt_anchor(ugc_style, image_prompt, product_name)
            negative = build_negative_prompt(profile, ugc_style)
            return image_prompt, negative

        # Panel 1 (cover): designed from the reference product image — let the
        # image model compose the cover itself (no hardcoded count).
        cover_hint = _cover_product_desc(profile, product_name)

        # Panel 2 (model + product): model holds the product(s) EXACTLY as shown
        # in the reference image — we do NOT hardcode the item count/variants
        # (that hardcoding made Wan render two identical items). "as shown in the
        # reference image" keeps count + labels + colors from the ground truth.
        # Compact wording (owner: too wordy) — one clean visual line.
        # NEW: only force the APPLY action when special_target is set (e.g. a
        # pregnancy cream that must be applied to face/belly). All other products
        # (incl. body_part=whole-body) stay as a plain HOLD — "ถือสินค้าพูด" is the
        # default fallback when no special apply audience is known. Having body_part
        # alone must NOT turn a normal unbox/holding video into a smear demo.
        _app_hint = _apply_hint(subcategory, category, profile)
        if profile.get("special_target", "").strip():
            mid_hint = (
                f"{model_desc} applying the product from the reference image, "
                f"{_app_hint}, {room_desc}"
            )
        else:
            mid_hint = (
                f"{model_desc} holding the product(s) from the reference image, "
                f"bottles facing the camera, {room_desc}"
            )

        # Panel 3 (result/end): pick the result-specific end scene from the SSOT
        # Prompt Library (keyed by subcategory → category → other) and STORE it on
        # the profile so build_video_prompt() reuses the SAME blueprint → image &
        # video end scenes stay consistent (they no longer drift apart).
        es = _pick_end_scene(category, subcategory=subcategory, profile=profile)
        profile["_end_scene"] = es  # bind: video prompt reuses this same instance
        _outfit = f"; outfit: {es['outfit']}" if es.get("outfit") else ""
        _result = es.get("result_focus") or "a happy result"
        _expr = es.get("expression") or "smiling"
        _placement = es.get("product_placement") or "product still in hand"
        result_hint = (
            f"the same {model_desc} from panel 2, wearing the same outfit as "
            f"panel 2, {_expr}, showing {_result}; {_placement}{_outfit}"
        )

        # Map recipe beats onto the three panels — but only where it fits the
        # recipe meaning (solve/us/value → panel 2, cta → panel 3). We deliberately
        # do NOT force agitate/them into the image (that belongs in the video script).
        # NOTE: panel 3 (result) already carries the product-specific end scene from
        # the SSOT Library (outfit + result_focus + expression + product_placement),
        # which is richer + product-specific than the generic "cta" beat hint — so we
        # do NOT let the cta beat override it. Only middle panel reads beat hints.
        # NEW (A): when the recipe scene carries a "visual" hint (e.g. the solve/us/value
        # beat), prefer it over the generic holding template so the center panel follows
        # the recipe (pas=solve, comparison=us, secret_hook=value). Resolve placeholders.
        for sidx, sc in enumerate(scenes):
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

        image_prompt = (
            f"16:9 landscape triptych, three equal horizontal panels placed side "
            f"by side touching edge to edge with zero pixels of space between panels, "
            f"joined as one seamless 16:9 image. "
            f"Panel 1 (left): {cover_hint}. "
            f"Panel 2 (center): {mid_hint} (same model appears in panels 2 and 3). "
            f"Panel 3 (right): {result_hint} (same setting/background as panel 2). "
            f"Product: show exactly the item(s) from the reference product image — "
            f"render every variant/color that appears in it. "
            f"{parts_colors}{lighting}. "
            f"NO text, letters, words, labels, logos or watermark on panels 2 and 3 — "
            f"only the model and product, cleanly. "
            f"Cohesive consistent style, high quality product photography. "
            f"Render the full 16:9 frame edge to edge as one continuous surface; the "
            f"three panels touch one another with 0 pixels of gap or margin between "
            f"panels — no divider, no seam, no spacing anywhere in the image."
        )
        logger.info(f"  Image prompt (triptych {len(image_prompt)} chars): {image_prompt[:100]}...")
        # Append the style's image anchor (from SSOT ugc_styles.json) so the first
        # frame matches the video's composition — video already applies it for every
        # style, image now does too (holding/usage/review/talking_head/… all read the
        # same anchor source -> image & video stay aligned).
        image_prompt = _apply_prompt_anchor(ugc_style, image_prompt, product_name)
        negative = build_negative_prompt(profile, ugc_style)
        return image_prompt, negative

    # ── Legacy single-frame path (no triptych) ──
    if ugc_style == "product_demo":
        image_prompt = f"{product_name} centered, {scene}. {lighting}. --ar 9:16"
    elif ugc_style in ("talking", "talking_head"):
        # Talking-head framing: face directly to camera, upper body, mouth visible,
        # so Wan 2.7 lip-sync (audio-driven) has a clean face to animate instead of melting.
        # Use a clean talking background, NOT the holding-style product scene.
        talking_bg = (
            "clean bright studio background, soft even light"
        )
        image_prompt = (f"Thai {gender_en}, upper body, facing directly to camera, "
                        f"presenting {product_name} to the viewers while speaking, "
                        f"natural Thai presenter, {talking_bg}. --ar 9:16")
    else:
        image_prompt = f"Thai {gender_en}, {action} {product_name}, {scene}, {lighting}. --ar 9:16"

    negative = build_negative_prompt(profile, ugc_style)

    logger.info(f"  Image prompt ({len(image_prompt)} chars): {image_prompt[:80]}...")
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


def _short_pair_tagline(profile: dict) -> str:
    """Short tagline for the person-holding panels: names the two distinct products
    without repeating the full appearance. E.g. 'pink GLUTA + orange TRIPLE C'."""
    appearance = (profile or {}).get("product_appearance", "") or ""
    # Extract short label/brand tokens like 'GLUTA' / 'TRIPLE C' if present.
    import re
    m = re.findall(r"\b([A-Za-z][A-Za-z0-9 ]{2,20})\b", appearance)
    keep = []
    from collections import OrderedDict
    for tok in m:
        t = tok.strip()
        low = t.lower()
        if low in {"bottle", "bottles", "the", "one", "two", "with", "a", "label",
                   "labels", "and", "of", "orange", "pink", "1000", "250"}:
            continue
        if t not in keep:
            keep.append(t)
        if len(keep) >= 3:
            break
    if keep:
        caps = [t if t.isupper() else t.title() for t in keep]
        return "pink GLUTA + orange TRIPLE C" if "GLUTA" in appearance and "TRIPLE" in appearance else " + ".join(caps[:2])
    return "two distinct bottles as a matched pair, both labels clearly visible"


def _beat_panel_hint(profile, product_name, model_desc, action, scene, panel_role: str) -> str:
    """Derive a clean English visual hint for one triptych panel.

    Builds a compact visual instruction Nano Banana understands — panel_role is
    cover / middle / right. Uses the product's appearance (Mistral) to add detail.
    Keeps hints visual (English) rather than raw Thai script text.
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
                f"{_app_hint}, {scene}"
            )
        else:
            base = (
                f"{model_desc} holding the product(s) from the reference image, "
                f"bottles facing the camera, {scene}"
            )
    else:  # right
        base = (
            f"the same {model_desc} from panel 2, wearing the same outfit as "
            f"panel 2, smiling showing a happy result, product(s) still in hand"
        )
    return base


def img_desc_sentences(text: str) -> list:
    """Split image_description into sentences."""
    return [s.strip() for s in text.split(".") if s.strip()]


def _apply_hint(subcategory=None, category=None, profile=None):
    """BEAT 2 'apply' action - concise, no squeeze/cap/scoop (Wan 2.7 warps).
    Always 'a little' so Wan doesn't smear too much.

    NEW: uses profile['body_part'] / profile['special_target'] when present so the
    video shows the product applied to the RIGHT body area (e.g. a pregnancy/facial
    cream goes on her face/belly, NOT a full-body smear). Rules:
      - whole-body/body -> hand (owner rule: never show full-body smearing)
      - special_target=pregnant -> face or belly
      - face/belly/hair/hands -> the matching area
    Falls back to subcategory -> category mapping.
    """
    key = (subcategory or "").lower()

    # NEW: deep-analysis fields take priority over the subcategory mapping.
    bp = ""
    st = ""
    if isinstance(profile, dict):
        bp = (profile.get("body_part") or "").strip().lower()
        st = (profile.get("special_target") or "").strip().lower()

    # special_target first (pregnancy/sensitive audience is the strongest signal).
    if st in ("pregnant", "pregnancy", "maternity"):
        # Pregnancy cream: belly is the hero area, face for facial pregnancy cream.
        if bp in ("face", "whole-body", "body"):
            return "she applies a little on her face and belly"
        return "she applies a little on her belly"

    # body_part mapping (owner: whole-body -> hand, never full-body smear).
    area_map = {
        "face": "her face", "belly": "her belly", "hair": "her hair",
        "hands": "her hand", "hand": "her hand", "nails": "her nails",
        "lips": "her lips", "body": "her hand", "whole-body": "her hand",
        "whole body": "her hand",
    }
    if bp in area_map:
        return "she applies a little on " + area_map[bp]

    area = {
        "underarm_cream": "her underarm", "deodorant": "her underarm",
        "face_whitening": "her face", "body_whitening": "her arm",
        "acne": "the affected spot", "serum": "her face",
        "moisturizer": "her skin", "sunscreen": "her face",
        "lipstick": "her lips", "foundation": "her face",
        "mascara": "her lashes", "blush": "her cheeks",
        "hair_care": "her hair", "shampoo": "her hair",
        "conditioner": "her hair", "stretch_marks": "the stretch marks",
        "eye_cream": "around her eyes", "toner": "her face",
    }.get(key)
    if not area:
        area = {"skincare": "her face", "beauty": "her face"}.get((category or "").lower(), "her skin")
    return "she applies a little on " + area


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
    ) and False:  # 4-beat ปิด — owner 2026-08-23: video ใช้ single long prompt ไม่แบ่ง scene
        vp_product = _clean_product_name_for_video(product_name)
        gender_en = {"female": "Woman", "male": "Man", "unisex": "Person"}.get(model_gender, "Woman")

        # SSOT end scene (same one image panel 3 uses) → beat 3 result + closing.
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
            f"she holds {vp_product} up toward the camera"
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
                f"Scene 1: {gender_en} holds {vp_product} steady toward the camera, product stays sharp and centered",
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
    # The first/only frame comes from the matching no-human triptych (image) so
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
    
    if customer_problem and main_benefit and len(customer_problem) > 5:
        # Shorten problem and benefit for natural spoken Thai and normalize polite particle by gender
        hook_text = _normalize_thai_gender_register(_safe_thai_truncate(customer_problem, 40), is_female)
        value_text = _normalize_thai_gender_register(f"{product_short} {_safe_thai_truncate(main_benefit, 45)}", is_female)
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
        segments = []
        for sc in scenes:
            beat_text = _resolve_scene_text(
                sc, product_short, customer_problem, main_benefit, target_audience, profile_feature
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
            full = " ".join(s["text"] for s in segments)
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

