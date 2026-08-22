"""
UGC Presets, Styles & Combos — Central Configuration
Recipe Presets (12), Content Styles (9), Recommended Combos

This replaces the flat 11-style system with structured:
  Preset → Style → Shot Plan → Prompt
"""

import json as _json
from pathlib import Path as _Path

_UGC_JSON = None
def _load_ugc_styles_json():
    """Load UGC_STYLES + UGC_COMBOS from ugc_styles.json (SSOT).

    Single source of truth — shared with prompt_builder.py. Kept here so
    auto_select_preset/auto_select_style/build_shot_prompts still work while
    the data itself lives in one JSON file (no duplicated Python dicts).
    """
    global _UGC_JSON
    if _UGC_JSON is None:
        p = _Path(__file__).parent / "ugc_styles.json"
        with open(p) as f:
            _UGC_JSON = _json.load(f)
        if "UGC_STYLES" not in _UGC_JSON:
            raise ValueError("ugc_styles.json: missing 'UGC_STYLES'")
    return _UGC_JSON



# ─────────────────────────────────────────────────────────────────────
# 1. RECIPE PRESETS (หมวดหมู่สินค้า & Mood)
# ─────────────────────────────────────────────────────────────────────
UGC_PRESETS = {
    "skincare_glow": {
        "name": "Skincare Glow",
        "description": "Soft luxury vibes, calm music, slow transitions",
        "mood": "soft, luxurious, calming",
        "lighting": "soft daylighting, clean shadows",
        "shot_dynamics": "cinematic, slow-motion",
        "camera_motion": "slow push in, gentle pan, soft rack focus",
        "bgm_style": "chill_loft",
        "sound_style": "ambient",
        "compatible_categories": ["beauty", "health"],
        "compatible_styles": ["holding", "review", "usage", "talking_head"],
        "compatible_personas": ["calm_professional", "minimalist_zen", "energetic_young"],
    },
    "gadget_unboxing": {
        "name": "Gadget Unboxing",
        "description": "Fast-paced, energetic, quick cuts",
        "mood": "energetic, exciting, tech-forward",
        "lighting": "high contrast, sharp focus, studio lighting",
        "shot_dynamics": "dynamic pan/zoom",
        "camera_motion": "fast whip pans, punch-in zooms, quick cuts",
        "bgm_style": "energetic_edm",
        "sound_style": "dynamic",
        "compatible_categories": ["electronics"],
        "compatible_styles": ["unboxing", "product_demo", "talking_head"],
        "compatible_personas": ["tech_enthusiast", "energetic_young", "college_student"],
    },
    "fashion_lookbook": {
        "name": "Fashion Lookbook",
        "description": "Elegant slow-mo, chic aesthetic",
        "mood": "elegant, chic, premium",
        "lighting": "neutral tone, soft diffused",
        "shot_dynamics": "portrait framing, soft tracking shots",
        "camera_motion": "soft tracking, slow dolly, subtle tilt",
        "bgm_style": "chill_loft",
        "sound_style": "elegant",
        "compatible_categories": ["fashion"],
        "compatible_styles": ["holding", "review", "pov"],
        "compatible_personas": ["minimalist_zen", "calm_professional", "energetic_young"],
    },
    "food_review": {
        "name": "Food Review",
        "description": "Warm ASMR-style close-up shots",
        "mood": "warm, appetizing, satisfying",
        "lighting": "warm lighting",
        "shot_dynamics": "macro zoom, appetizing depth of field",
        "camera_motion": "slow macro pull, gentle hand-held sway",
        "bgm_style": "informative_jazz",
        "sound_style": "asmr",
        "compatible_categories": ["food"],
        "compatible_styles": ["review", "pov", "usage"],
        "compatible_personas": ["mom_at_home", "college_student", "energetic_young"],
    },
    "asmr_unboxing": {
        "name": "ASMR Unboxing",
        "description": "Quiet ambient, gentle sounds, relaxing",
        "mood": "calm, relaxing, mindful",
        "lighting": "soft indoor light",
        "shot_dynamics": "close-up macro, minimal camera movement",
        "camera_motion": "static, very slow push, gentle drift",
        "bgm_style": "chill_loft",
        "sound_style": "asmr",
        "compatible_categories": ["home", "beauty", "other"],
        "compatible_styles": ["unboxing", "product_demo"],
        "compatible_personas": ["minimalist_zen", "calm_professional"],
    },
    "makeup_tutorial": {
        "name": "Makeup Tutorial",
        "description": "Soft upbeat, beauty close-ups, trendy",
        "mood": "soft, upbeat, trendy",
        "lighting": "front ring-light aesthetic",
        "shot_dynamics": "sharp close-ups, smooth motion",
        "camera_motion": "steady hand-held, slow pans",
        "bgm_style": "upbeat_pop",
        "sound_style": "upbeat",
        "compatible_categories": ["beauty", "fashion"],
        "compatible_styles": ["usage", "talking_head", "holding"],
        "compatible_personas": ["energetic_young", "calm_professional"],
    },
    "fitness_supplement": {
        "name": "Fitness/Supplement",
        "description": "High energy, motivating, fast tempo",
        "mood": "energetic, motivating, powerful",
        "lighting": "high contrast, punchy",
        "shot_dynamics": "punchy motion, dramatic angles",
        "camera_motion": "fast pan, action follow, whip zoom",
        "bgm_style": "energetic_edm",
        "sound_style": "dynamic",
        "compatible_categories": ["health", "tools"],
        "compatible_styles": ["usage", "talking_head", "comparison"],
        "compatible_personas": ["tech_enthusiast", "energetic_young", "calm_professional"],
    },
    "product_demo": {
        "name": "Product Demo",
        "description": "No person, product on table, feature showcase",
        "mood": "clean, informative, professional",
        "lighting": "clean studio light, evenly diffused",
        "shot_dynamics": "centered framing, slow rotation or linear pan",
        "camera_motion": "slow push in, static, slow pan",
        "bgm_style": "informative_jazz",
        "sound_style": "clean",
        "compatible_categories": ["electronics", "home", "tools", "home_appliance", "health_hygiene"],
        "compatible_styles": ["product_demo", "product_usage"],
        "compatible_personas": ["calm_professional", "minimalist_zen", "mom_at_home"],
    },
    "home_living": {
        "name": "Home & Living",
        "description": "Clean, soothing, satisfying, aesthetic",
        "mood": "clean, soothing, cozy",
        "lighting": "cozy ambient light, natural wooden/white textures",
        "shot_dynamics": "steady tracking, aesthetic framing",
        "camera_motion": "steady tracking, slow slide",
        "bgm_style": "chill_loft",
        "sound_style": "ambient",
        "compatible_categories": ["home", "home_appliance"],
        "compatible_styles": ["product_demo", "usage", "pov"],
        "compatible_personas": ["mom_at_home", "minimalist_zen", "calm_professional"],
    },
    "travel_edc": {
        "name": "Travel & EDC",
        "description": "Dynamic, outdoor, practical, compact",
        "mood": "dynamic, adventurous, practical",
        "lighting": "natural daylight, diffused outdoor",
        "shot_dynamics": "fast movement, hands-on action framing",
        "camera_motion": "action follow, hand-held dynamic",
        "bgm_style": "upbeat_pop",
        "sound_style": "dynamic",
        "compatible_categories": ["fashion", "tools", "other"],
        "compatible_styles": ["pov", "usage", "product_demo"],
        "compatible_personas": ["energetic_young", "tech_enthusiast", "college_student"],
    },
    "mom_baby": {
        "name": "Mom & Baby",
        "description": "Warm, gentle, safe, trustworthy",
        "mood": "warm, gentle, nurturing",
        "lighting": "pastel tones, soft warm light",
        "shot_dynamics": "gentle tilt/pan, soft framing",
        "camera_motion": "gentle tilt, slow pan, soft float",
        "bgm_style": "chill_loft",
        "sound_style": "gentle",
        "compatible_categories": ["home", "health"],
        "compatible_styles": ["talking_head", "usage", "review"],
        "compatible_personas": ["mom_at_home", "calm_professional", "minimalist_zen"],
    },
    "pet_care": {
        "name": "Pet Care",
        "description": "Cute, cheerful, playful, energetic",
        "mood": "cheerful, playful, bright",
        "lighting": "bright colorful, natural window",
        "shot_dynamics": "eye-level animal framing",
        "camera_motion": "quick tracking, bouncy follow",
        "bgm_style": "upbeat_pop",
        "sound_style": "playful",
        "compatible_categories": ["home", "other"],
        "compatible_styles": ["usage", "pov", "review"],
        "compatible_personas": ["mom_at_home", "energetic_young", "college_student"],
    },
}

# ─────────────────────────────────────────────────────────────────────
# 2. UGC CONTENT STYLES (รูปแบบการเสนอ & มุมกล้อง)
# ─────────────────────────────────────────────────────────────────────
UGC_STYLES = _load_ugc_styles_json()["UGC_STYLES"]
# (SSOT: values live in ugc_styles.json — do NOT hardcode here)

# ─────────────────────────────────────────────────────────────────────
# 3. RECOMMENDED COMBINATIONS
# ─────────────────────────────────────────────────────────────────────
UGC_COMBOS = _load_ugc_styles_json()["UGC_COMBOS"]
# (SSOT: values live in ugc_styles.json — do NOT hardcode here)


# ─────────────────────────────────────────────────────────────────────
# 4. Helpers
# ─────────────────────────────────────────────────────────────────────

def auto_select_preset(category: str) -> dict:
    """Auto-select best preset based on product category."""
    # Map flat categories to combo keys
    cat_to_combo = {
        "electronics": "electronics_gadget",
        "home_appliance": "home_appliance",
        "home": "home_decor",
        "food": "food_beverage",
        "beauty": "skincare_beauty",
        "fashion": "fashion_accessory",
        "health_hygiene": "health_hygiene",
        "health": "health_hygiene",
        "fitness": "fitness_sport",
        "tools": "electronics_gadget",
    }
    combo_key = cat_to_combo.get(category, "health_hygiene")
    combo = UGC_COMBOS.get(combo_key, UGC_COMBOS["health_hygiene"])
    preset = UGC_PRESETS.get(combo["preset"], UGC_PRESETS["product_demo"])
    return {
        "combo": combo,
        "preset": preset,
        "preset_id": combo["preset"],
        "suggested_styles": combo["styles"],
    }


def auto_select_style(styles_list: list, has_person: bool = True) -> str:
    """Auto-select best style from a list of candidates."""
    # Prefer styles that match has_person requirement
    for style_id in styles_list:
        s = UGC_STYLES.get(style_id)
        if s and s["has_person"] == has_person:
            return style_id
    # Fallback to first
    return styles_list[0] if styles_list else "product_demo"


def build_shot_prompts(style_id: str, product_appearance: str, preset: dict) -> list:
    """Build multi-shot video prompts from style + preset config."""
    style = UGC_STYLES.get(style_id)
    if not style:
        return []
    
    env_str = "a modern space"
    lighting = preset.get("lighting", "soft diffused lighting")
    
    prompts = []
    for shot in style["shots"]:
        prompt = f"{shot['desc']}. {product_appearance[:200]}"
        prompt += f" Camera: {shot['camera']}. {lighting}. 9:16 portrait, smooth motion"
        prompts.append(prompt)
    
    return prompts
