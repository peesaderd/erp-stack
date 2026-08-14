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
    
    scene = rng.choice(mapping.get("scene", ["clean modern surface"]))
    action = mapping.get("action", "holds product")
    camera = mapping.get("camera", "medium close-up")
    lighting = mapping.get("lighting", "soft natural lighting")
    mood = mapping.get("mood", "clean")
    
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


def _pick_end_scene(category="other"):
    """Pick end scene from JSON."""
    sources = _load_prompt_sources()
    end_scenes = sources.get("end_scenes", {})
    pool = end_scenes.get(category, end_scenes.get("other", []))
    if not pool:
        return {"scene": "product prominently displayed", "camera": "medium shot"}
    return _random.choice(pool)


def _pick_transition():
    sources = _load_prompt_sources()
    return _random.choice(sources.get("transitions", ["fade to white"]))


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

    raw = _call_gemini(PRODUCT_ANALYSIS_SYSTEM, user_text, temperature=0.3, max_output_tokens=700)
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


def build_image_prompt(profile: dict, product_name: str, ugc_style: str = "holding", loop_count: int = 0) -> tuple:
    """Generate SHORT image prompt — ~70 chars.

    Uses _ai_select() to pick scene/action/camera/lighting from category_mapping.
    No persona description in prompt — reference image handles appearance.
    """
    model_gender = profile.get("target_gender", "female")
    category = profile.get("category", "other")
    subcategory = profile.get("subcategory", "")

    # AI select from category_mapping
    selected = _ai_select(category, subcategory, model_gender, product_name, loop_count)

    scene = selected["scene"]
    action = selected["action"]
    lighting = selected["lighting"]

    # Build short prompt
    gender_en = {"female": "woman", "male": "man", "unisex": "person"}.get(model_gender, "woman")

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


def img_desc_sentences(text: str) -> list:
    """Split image_description into sentences."""
    return [s.strip() for s in text.split(".") if s.strip()]


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

    # Build short video prompt with end scene (start + transition + end)
    # Wan 2.7 generates 1 continuous clip from a single image ref.
    # Integrating the end scene into the SAME prompt lets the model
    # animate a natural open → close arc in one pass (no separate clips).
    end = _pick_end_scene(category)
    transition = _pick_transition()

    if ugc_style in ("talking", "talking_head"):
        # Talking-head: presenter faces camera, upper body, clean background.
        # The "scene" from category_mapping + the product-demo end-scene are
        # written for a HAND-HELD product shot (e.g. "soft-lit dressing table",
        # "medium shot, model admiring result") — those are wrong for a talking
        # head and make Wan warp the frame. So talking uses its OWN framing and
        # end (no "admiring result" arc) so Wan keeps the face forward and just
        # moves the mouth/head subtly.
        talking_scene = (
            "presenting from a clean bright background, upper body, "
            "facing directly to the camera"
        )
        # Option A: put the spoken Thai script DIRECTLY in the Wan video prompt.
        # Prodia Wan 2.7 lip-sync from audio is unreliable, so instead of relying
        # on audio we let Wan see the exact Thai text it should be reading, which
        # drives mouth movement that matches the TTS Thai voiceover merged later.
        # A short English description is kept so Wan knows what product to keep
        # in frame (fixes "product vanishes in wide shots").
        _vp_product = _clean_product_name_for_video(product_name)
        if script:
            # Trim to a safe short chunk so the prompt stays readable; Wan reads
            # this text to drive mouth motion.
            _spoken = script.strip()
            if len(_spoken) > 200:
                _spoken = _spoken[:200]
            start_part = (
                f"{gender_en} presenting the cream sachet to the camera, reading "
                f"the Thai message aloud, holding the product: '{_spoken}'."
            )
        else:
            start_part = f"{gender_en} speaking naturally to the camera about {_vp_product}, Thai presenter style. {talking_scene}."
        # Talking end: STOP talking and show the product.
        # Replace the old "continues talking" (which made Wan ramble on after
        # finishing the script) with an explicit stop + close mouth + hold product.
        end_part = (
            "Face kept clear, then she finishes reading, stops talking, "
            "closes her mouth, holds the product toward the camera, smiling."
        )
        transition = ""
        # Mouth/head-only motion: keep face forward, avoid warping the frame.
        # This does NOT rely on audio lip-sync anymore (audio sync is dropped)
        # — it just tells Wan to keep subtle mouth/head motion while staying.
        lipsync_part = (
            " subtle head movement, face kept clear and forward, "
            f"the product held still in front of the presenter"
        )
    else:
        start_part = f"{gender_en} {action}. {scene}."
        end_part = f"{end.get('camera', 'medium shot')}, {end.get('scene', 'product shown to camera')}."
        lipsync_part = (
            " lips moving subtly, smooth natural motion, "
            "product held still, no warping"
        )

    # Compose: opening action → gentle transition → end scene
    # Keep it natural-language so Wan's motion model flows smoothly.
    # Talking-head end_part is self-contained (start + finish + stop + show product),
    # so don't inject "transition, then" which would produce a broken " , then Face".
    if ugc_style in ("talking", "talking_head"):
        video_prompt = f"{start_part} {end_part} 9:16.{lipsync_part}"
    else:
        video_prompt = f"{start_part} {transition}, then {end_part} 9:16.{lipsync_part}"

    # Clean up
    video_prompt = re.sub(r'\s+', ' ', video_prompt).strip()

    logger.info(f"  Video prompt ({len(video_prompt)} chars): {video_prompt[:80]}...")
    return video_prompt
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


def build_negative_prompt(profile: dict, ugc_style: str = "holding") -> str:
    """Build negative prompt — defaults (text/watermark/hands/distortion)
    + Wan identity-stability terms (anti-morph / anti-melt).
    Caller no longer needs to merge — this is the complete negative."""
    # Identity-stability terms added for Wan 2.7 (prevents face morph/melt,
    # finger warping, and "speaks gibberish" drifting at the tail).
    return (
        "no text, no watermark, no logo, no UI overlay, "
        "no blurred face, no distorted hands, no extra fingers, "
        "no manga, no cartoon, no illustration, no 3D render, "
        "no low resolution, no pixelation, no artifacts, "
        "no cluttered background, no messy room, "
        "stable face, consistent identity, no facial morphing, "
        "no melting, no warping, realistic proportions"
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
    category: str = "",
    loop_count: int = 0,
    product_category: str = "",
    target_duration: int = 15,
    target_age: Any = "",
    target_gender: str = "",
    country: str = "",
    script: str = "",
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
                "hook": tv.get("hook", {}).get("text", "") if isinstance(tv.get("hook"), dict) else str(tv.get("hook", "")),
                "value": tv.get("value", {}).get("text", "") if isinstance(tv.get("value"), dict) else str(tv.get("value", "")),
                "cta": tv.get("cta", {}).get("text", "") if isinstance(tv.get("cta"), dict) else str(tv.get("cta", "")),
            },
            "tts_speed": tv.get("tts_speed", 1.0),
            "product_short_for_tts": tv.get("product_short_for_tts", ""),
            "all_segments_fit": tv.get("all_segments_fit", True),
            "total_duration": tv.get("total_duration", 15),
        },
        "scripts": {
            "full_script": tv.get("full_script", ""),
            "tts_script": tv.get("tts_script", ""),
            "breakdown": {
                "hook": tv.get("hook", {}).get("text", "") if isinstance(tv.get("hook"), dict) else str(tv.get("hook", "")),
                "value": tv.get("value", {}).get("text", "") if isinstance(tv.get("value"), dict) else str(tv.get("value", "")),
                "cta": tv.get("cta", {}).get("text", "") if isinstance(tv.get("cta"), dict) else str(tv.get("cta", "")),
            }
        },
        "hashtags": profile.get("hashtags", []),
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
    # FIX (thai speaking-rate calibration): old rate 18 chars/sec over-estimated
    # how fast Thai is spoken, so duration came out too short and the resulting
    # tts_speed came out too low (voice not sped up enough). Measured real EdgeTTS:
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

