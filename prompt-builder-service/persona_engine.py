# ─── Persona Engine ─────────────────────────────────────────────
# Persona selection and injection for UGC diversity
# ═══════════════════════════════════════════════════════════════════════

import random
import logging
from typing import Dict, Optional

logger = logging.getLogger("prompt-builder-service")

PERSONA_TEMPLATES = {
    "energetic_young": {
        "vibe": "high energy, trendy, fast talker, Gen Z slang",
        "environment": "bedroom with led lights, trendy cafe",
        "lighting_variation": "neon pink/purple, bright indoor",
        "motion_speed": "fast, snappy cuts",
        "clothing": "trendy crop top and high-waisted jeans, oversized t-shirt with streetwear hoodie",
        "hair_style": "long straight hair with highlights, half-up ponytail, messy bun",
        "speech_style": "\u0e1e\u0e39\u0e14\u0e40\u0e23\u0e47\u0e27 \u0e43\u0e0a\u0e49\u0e28\u0e31\u0e1e\u0e17\u0e4c\u0e27\u0e31\u0e22\u0e23\u0e38\u0e48\u0e19 \u0e2d\u0e34\u0e19\u0e40\u0e17\u0e23\u0e19\u0e14\u0e4c \u0e21\u0e35\u0e21\u0e38\u0e01 \u0e21\u0e35\u0e04\u0e33\u0e2e\u0e34\u0e15 '\u0e2d\u0e2d\u0e21\u0e32\u0e22\u0e01\u0e47\u0e2d\u0e14' '\u0e08\u0e36\u0e49\u0e07' '\u0e1b\u0e31\u0e07' '\u0e15\u0e31\u0e27\u0e41\u0e21\u0e48' '\u0e41\u0e01'",
        "pacing": "\u0e40\u0e23\u0e47\u0e27 \u0e01\u0e23\u0e30\u0e0a\u0e31\u0e1a \u0e15\u0e37\u0e48\u0e19\u0e40\u0e15\u0e49\u0e19 \u0e40\u0e1b\u0e25\u0e35\u0e48\u0e22\u0e19\u0e17\u0e48\u0e2d\u0e19\u0e40\u0e23\u0e47\u0e27",
        "forbidden_phrases": "\u0e2b\u0e49\u0e32\u0e21\u0e43\u0e0a\u0e49\u0e20\u0e32\u0e29\u0e32\u0e40\u0e1b\u0e47\u0e19\u0e17\u0e32\u0e07\u0e01\u0e32\u0e23 \u0e2b\u0e49\u0e32\u0e21\u0e43\u0e0a\u0e49 '\u0e04\u0e23\u0e31\u0e1a/\u0e04\u0e48\u0e30' \u0e21\u0e32\u0e01\u0e40\u0e01\u0e34\u0e19\u0e44\u0e1b \u0e2b\u0e49\u0e32\u0e21\u0e1e\u0e39\u0e14\u0e22\u0e36\u0e14\u0e22\u0e32\u0e27",
    },
    "calm_professional": {
        "vibe": "calm, authoritative, measured speech, professional",
        "environment": "modern office, clean white studio",
        "lighting_variation": "soft neutral, ring light style",
        "motion_speed": "slow, deliberate pans",
        "clothing": "tailored blazer and silk blouse, business casual white shirt, minimalist professional dress",
        "hair_style": "sleek straight bob, low ponytail, neat bun",
        "speech_style": "\u0e1e\u0e39\u0e14\u0e0a\u0e31\u0e14 \u0e09\u0e30\u0e09\u0e32\u0e19 \u0e21\u0e35\u0e2b\u0e25\u0e31\u0e01\u0e01\u0e32\u0e23 \u0e43\u0e0a\u0e49\u0e28\u0e31\u0e1e\u0e17\u0e4c\u0e27\u0e34\u0e0a\u0e32\u0e01\u0e32\u0e23\u0e1e\u0e2d\u0e1b\u0e23\u0e30\u0e21\u0e32\u0e13 \u0e19\u0e48\u0e32\u0e40\u0e0a\u0e37\u0e48\u0e2d\u0e16\u0e37\u0e2d \u0e43\u0e0a\u0e49 '\u0e04\u0e23\u0e31\u0e1a/\u0e04\u0e48\u0e30' \u0e2a\u0e38\u0e20\u0e32\u0e1e",
        "pacing": "\u0e0a\u0e49\u0e32 \u0e01\u0e25\u0e32\u0e07 \u0e40\u0e19\u0e49\u0e19\u0e04\u0e33\u0e2a\u0e33\u0e04\u0e31\u0e0d \u0e40\u0e27\u0e49\u0e19\u0e08\u0e31\u0e07\u0e2b\u0e27\u0e30\u0e43\u0e2b\u0e49\u0e02\u0e49\u0e2d\u0e21\u0e39\u0e25\u0e0b\u0e36\u0e21",
        "forbidden_phrases": "\u0e2b\u0e49\u0e32\u0e21\u0e43\u0e0a\u0e49\u0e28\u0e31\u0e1e\u0e17\u0e4c\u0e27\u0e31\u0e22\u0e23\u0e38\u0e48\u0e19 \u0e2b\u0e49\u0e32\u0e21\u0e1e\u0e39\u0e14\u0e40\u0e23\u0e47\u0e27\u0e40\u0e01\u0e34\u0e19\u0e44\u0e1b \u0e2b\u0e49\u0e32\u0e21\u0e43\u0e0a\u0e49\u0e04\u0e33\u0e44\u0e21\u0e48\u0e40\u0e1b\u0e47\u0e19\u0e17\u0e32\u0e07\u0e01\u0e32\u0e23",
    },
    "mom_at_home": {
        "vibe": "warm, relatable, busy mom energy",
        "environment": "home kitchen, living room with kids toys",
        "lighting_variation": "warm golden, natural window",
        "motion_speed": "natural, slightly rushed",
        "clothing": "comfortable casual blouse and leggings, relaxed wrap dress, simple cotton t-shirt and shorts",
        "hair_style": "short easy-care cut, ponytail, hair clipped back with simple clip",
        "speech_style": "\u0e1e\u0e39\u0e14\u0e01\u0e31\u0e19\u0e40\u0e2d\u0e07\u0e40\u0e2b\u0e21\u0e37\u0e2d\u0e19\u0e04\u0e38\u0e22\u0e01\u0e31\u0e1a\u0e40\u0e1e\u0e37\u0e48\u0e2d\u0e19 \u0e1a\u0e48\u0e19\u0e1a\u0e49\u0e32\u0e07 '\u0e07\u0e32\u0e19\u0e1a\u0e49\u0e32\u0e19\u0e40\u0e22\u0e2d\u0e30' '\u0e40\u0e27\u0e25\u0e32\u0e44\u0e21\u0e48\u0e1e\u0e2d' '\u0e40\u0e08\u0e2d\u0e02\u0e2d\u0e07\u0e14\u0e35\u0e21\u0e32' \u0e43\u0e0a\u0e49\u0e20\u0e32\u0e29\u0e32\u0e44\u0e17\u0e22\u0e18\u0e23\u0e23\u0e21\u0e0a\u0e32\u0e15\u0e34",
        "pacing": "\u0e18\u0e23\u0e23\u0e21\u0e0a\u0e32\u0e15\u0e34 \u0e1a\u0e32\u0e07\u0e17\u0e35\u0e40\u0e23\u0e47\u0e27\u0e40\u0e1e\u0e23\u0e32\u0e30\u0e23\u0e35\u0e1a \u0e1a\u0e32\u0e07\u0e17\u0e35\u0e0a\u0e49\u0e32\u0e40\u0e1e\u0e23\u0e32\u0e30\u0e01\u0e33\u0e25\u0e31\u0e07\u0e17\u0e33\u0e2d\u0e30\u0e44\u0e23\u0e44\u0e1b\u0e14\u0e49\u0e27\u0e22",
        "forbidden_phrases": "\u0e2b\u0e49\u0e32\u0e21\u0e43\u0e0a\u0e49\u0e20\u0e32\u0e29\u0e32\u0e2d\u0e31\u0e07\u0e01\u0e24\u0e29\u0e40\u0e22\u0e2d\u0e30 \u0e2b\u0e49\u0e32\u0e21\u0e43\u0e0a\u0e49\u0e28\u0e31\u0e1e\u0e17\u0e4c\u0e17\u0e32\u0e07\u0e01\u0e32\u0e23 \u0e2b\u0e49\u0e32\u0e21\u0e1e\u0e39\u0e14\u0e22\u0e36\u0e14\u0e40\u0e22\u0e37\u0e2d",
    },
    "college_student": {
        "vibe": "casual, budget-conscious, honest reactions",
        "environment": "dorm room, campus, library",
        "lighting_variation": "cool fluorescent, mixed daylight",
        "motion_speed": "casual, natural hand gestures",
        "clothing": "university t-shirt and shorts, graphic tee and skirt, casual student jacket and jeans",
        "hair_style": "long natural hair, two-strand twist, side braid",
        "speech_style": "\u0e1e\u0e39\u0e14\u0e15\u0e23\u0e07\u0e46 \u0e44\u0e21\u0e48\u0e1b\u0e23\u0e38\u0e07\u0e41\u0e15\u0e48\u0e07 '\u0e04\u0e37\u0e2d\u0e41\u0e1a\u0e1a...' '\u0e2a\u0e31\u0e01\u0e2b\u0e23\u0e37\u0e2d\u0e40\u0e2a\u0e35\u0e48\u0e22' '\u0e40\u0e14\u0e35\u0e49\u0e22\u0e27\u0e01\u0e39\u0e17\u0e14\u0e25\u0e2d\u0e07\u0e43\u0e2b\u0e49\u0e14\u0e39'",
        "pacing": "\u0e18\u0e23\u0e23\u0e21\u0e0a\u0e32\u0e15\u0e34 \u0e01\u0e36\u0e48\u0e07\u0e0a\u0e49\u0e32 \u0e44\u0e21\u0e48\u0e15\u0e49\u0e2d\u0e07\u0e40\u0e23\u0e48\u0e07 \u0e44\u0e21\u0e48\u0e15\u0e49\u0e2d\u0e07\u0e40\u0e01\u0e48\u0e07",
        "forbidden_phrases": "\u0e2b\u0e49\u0e32\u0e21\u0e42\u0e06\u0e29\u0e13\u0e32\u0e0a\u0e31\u0e14\u0e40\u0e01\u0e34\u0e19\u0e44\u0e1b \u0e2b\u0e49\u0e32\u0e21\u0e43\u0e0a\u0e49\u0e20\u0e32\u0e29\u0e32\u0e40\u0e0a\u0e1f\u0e2b\u0e23\u0e37\u0e2d\u0e1c\u0e39\u0e49\u0e43\u0e2b\u0e0d\u0e48",
    },
    "minimalist_zen": {
        "vibe": "calm, aesthetic, slow living, premium feel",
        "environment": "minimalist room with plants, yoga space",
        "lighting_variation": "soft diffused, morning light",
        "motion_speed": "slow, graceful movements",
        "clothing": "flowing linen dress, neutral-toned minimalist outfit, fitted short-sleeve blouse and trousers",
        "hair_style": "loose natural waves, sleek middle part down, low messy bun",
        "speech_style": "\u0e1e\u0e39\u0e14\u0e0a\u0e49\u0e32 \u0e19\u0e38\u0e48\u0e21\u0e19\u0e27\u0e25 \u0e21\u0e35\u0e2a\u0e21\u0e32\u0e18\u0e34 \u0e40\u0e19\u0e49\u0e19 mindful '\u0e25\u0e2d\u0e07\u0e2b\u0e32\u0e22\u0e43\u0e08\u0e25\u0e36\u0e01\u0e46 \u0e41\u0e25\u0e49\u0e27\u0e21\u0e32\u0e14\u0e39\u0e01\u0e31\u0e19' \u0e43\u0e0a\u0e49\u0e04\u0e33\u0e2a\u0e27\u0e22\u0e46",
        "pacing": "\u0e0a\u0e49\u0e32 \u0e21\u0e35\u0e1e\u0e37\u0e49\u0e19\u0e17\u0e35\u0e48\u0e43\u0e2b\u0e49\u0e2b\u0e32\u0e22\u0e43\u0e08 \u0e41\u0e15\u0e48\u0e25\u0e30\u0e1b\u0e23\u0e30\u0e42\u0e22\u0e04\u0e21\u0e35\u0e19\u0e49\u0e33\u0e2b\u0e19\u0e31\u0e01",
        "forbidden_phrases": "\u0e2b\u0e49\u0e32\u0e21\u0e1e\u0e39\u0e14\u0e40\u0e23\u0e47\u0e27 \u0e2b\u0e49\u0e32\u0e21\u0e43\u0e0a\u0e49\u0e04\u0e33\u0e15\u0e25\u0e32\u0e14 \u0e2b\u0e49\u0e32\u0e21\u0e02\u0e32\u0e22\u0e02\u0e2d\u0e07\u0e15\u0e23\u0e07\u0e40\u0e01\u0e34\u0e19\u0e44\u0e1b",
    },
    "tech_enthusiast": {
        "vibe": "excited, gadget-focused, fast demo style",
        "environment": "desk with monitors, gaming setup",
        "lighting_variation": "RGB lighting, cool blue/white",
        "motion_speed": "fast, demonstrative",
        "clothing": "graphic hoodie and jeans, geek-chic button-up shirt, esports jersey",
        "hair_style": "short tousled hair, cap and hood over short cut, spiky short cut",
        "speech_style": "\u0e1e\u0e39\u0e14\u0e40\u0e23\u0e47\u0e27 \u0e15\u0e37\u0e48\u0e19\u0e40\u0e15\u0e49\u0e19\u0e01\u0e31\u0e1a\u0e2a\u0e40\u0e1b\u0e04 \u0e43\u0e0a\u0e49\u0e28\u0e31\u0e1e\u0e17\u0e4c\u0e40\u0e17\u0e04\u0e19\u0e34\u0e04 '\u0e41\u0e23\u0e07\u0e21\u0e49\u0e32\u0e08\u0e31\u0e14' '60fps \u0e40\u0e19\u0e35\u0e22\u0e19\u0e01\u0e23\u0e34\u0e4a\u0e1a' '\u0e0a\u0e34\u0e1b\u0e15\u0e31\u0e27\u0e19\u0e35\u0e49\u0e41\u0e23\u0e07\u0e01\u0e27\u0e48\u0e32\u0e40\u0e14\u0e34\u0e21\u0e40\u0e17\u0e48\u0e32\u0e15\u0e31\u0e27'",
        "pacing": "\u0e40\u0e23\u0e47\u0e27 \u0e40\u0e23\u0e49\u0e32\u0e43\u0e08 \u0e21\u0e35\u0e25\u0e39\u0e01\u0e40\u0e25\u0e48\u0e19 \u0e15\u0e37\u0e48\u0e19\u0e40\u0e15\u0e49\u0e19\u0e15\u0e25\u0e2d\u0e14\u0e40\u0e27\u0e25\u0e32",
        "forbidden_phrases": "\u0e2b\u0e49\u0e32\u0e21\u0e43\u0e0a\u0e49\u0e20\u0e32\u0e29\u0e32\u0e40\u0e1e\u0e49\u0e2d\u0e40\u0e08\u0e37\u0e2d \u0e2b\u0e49\u0e32\u0e21\u0e44\u0e21\u0e48\u0e23\u0e39\u0e49\u0e40\u0e23\u0e37\u0e48\u0e2d\u0e07\u0e17\u0e35\u0e48\u0e1e\u0e39\u0e14 \u0e2b\u0e49\u0e32\u0e21\u0e44\u0e21\u0e48\u0e16\u0e39\u0e01\u0e15\u0e49\u0e2d\u0e07\u0e17\u0e32\u0e07\u0e40\u0e17\u0e04\u0e19\u0e34\u0e04",
    },
    # ── Male Persona Variants ──
    "street_guy": {
        "vibe": "casual cool, street style, confident Gen Z guy energy",
        "environment": "street corner with graffiti wall, urban rooftop, skate park",
        "lighting_variation": "harsh daylight with shadows, golden hour street glow",
        "motion_speed": "casual, relaxed swagger",
        "clothing": "oversized graphic tee and cargo pants, streetwear hoodie and joggers, denim jacket and black jeans",
        "hair_style": "textured crop with fade, messy curtain bangs, short spiky with undercut",
        "speech_style": "พูดตรง ไม่เว่อร์ คูลๆ มีสไตล์ ใช้ศัพท์ผู้ชาย",
        "pacing": "ผ่อนคลาย มั่นใจ ไม่ต้องเร่ง ไม่ต้องเก๊ก",
        "forbidden_phrases": "ห้ามใช้ค่ะ/คะ ห้ามใช้ศัพท์ผู้หญิง ใช้ ผม",
    },
    "office_guy": {
        "vibe": "professional, trustworthy, mature, confident presenter",
        "environment": "modern office with glass walls, clean studio, co-working space",
        "lighting_variation": "soft diffused office light, clean daylight white",
        "motion_speed": "steady, deliberate, minimal but confident gestures",
        "clothing": "tailored navy blazer and white shirt, business casual linen shirt and chinos, smart polo and dark jeans",
        "hair_style": "classic side part, clean crew cut, textured quiff",
        "speech_style": "พูดสุภาพ ฉะฉาน น่าเชื่อถือ ใช้ ครับ สุภาพ",
        "pacing": "กลาง ไม่ช้าไม่เร็ว เน้นข้อมูลสำคัญ",
        "forbidden_phrases": "ห้ามใช้ค่ะ/คะ ห้ามใช้ศัพท์วัยรุ่นเกินไป ใช้ ครับ เท่านั้น",
    },
    "dad_guy": {
        "vibe": "warm, relatable dad energy, practical, trustworthy",
        "environment": "living room with sofa, home kitchen, backyard garden",
        "lighting_variation": "warm afternoon light, golden natural window",
        "motion_speed": "relaxed, natural, unhurried",
        "clothing": "comfortable polo shirt and chinos, casual button-up and dark jeans, simple t-shirt and shorts",
        "hair_style": "short neat cut, natural side sweep, clean taper",
        "speech_style": "พูดกันเอง เหมือนคุยกับเพื่อน อบอุ่น ใช้ ครับ",
        "pacing": "ธรรมชาติ ไม่เร่ง เหมือนคุยเล่นแต่มีสาระ",
        "forbidden_phrases": "ห้ามใช้ค่ะ/คะ ห้ามใช้ศัพท์วัยรุ่นเกินไป ใช้ ครับ เท่านั้น",
    },
}

def _select_persona(category: str, product_name: str = "", target_gender: str = None) -> dict:
    import random
    cat_persona_map = {
        "beauty": ["energetic_young", "calm_professional", "mom_at_home", "minimalist_zen"],
        "electronics": ["tech_enthusiast", "college_student", "calm_professional"],
        "food": ["mom_at_home", "college_student", "energetic_young"],
        "fashion": ["energetic_young", "minimalist_zen", "calm_professional"],
        "home": ["mom_at_home", "minimalist_zen", "calm_professional"],
        "tools": ["calm_professional", "tech_enthusiast", "mom_at_home"],
        "health": ["calm_professional", "minimalist_zen", "mom_at_home"],
        "health_hygiene": ["calm_professional", "minimalist_zen", "mom_at_home"],
        "home_appliance": ["mom_at_home", "minimalist_zen", "calm_professional"],
    }
    male_pool = ["street_guy", "office_guy", "dad_guy"]
    female_pool = ["calm_professional", "minimalist_zen", "mom_at_home"]
    cat_persona_male = {
        "electronics": ["tech_enthusiast", "office_guy", "street_guy"],
        "tools": ["office_guy", "dad_guy", "tech_enthusiast"],
        "home": ["dad_guy", "office_guy"],
        "food": ["dad_guy", "street_guy"],
        "fashion": ["street_guy", "office_guy"],
        "health": ["office_guy", "dad_guy"],
        "beauty": ["street_guy", "office_guy"],
    }
    if target_gender == "male":
        pool = cat_persona_male.get(category, male_pool)
    elif target_gender == "female":
        pool = cat_persona_map.get(category, female_pool)
    else:
        # gender unknown — mix male + female pools equally, weighed toward category
        pool = cat_persona_map.get(category, female_pool) + cat_persona_male.get(category, male_pool)
    fallback_safe = pool if pool else female_pool + male_pool
    chosen = random.choice(pool)
    return PERSONA_TEMPLATES[chosen]


def _pick_random_option(field_value: str) -> str:
    """Split comma-separated options and pick one randomly."""
    if not field_value:
        return ""
    options = [o.strip() for o in field_value.split(",")]
    return random.choice(options).strip()


def _apply_persona_to_profile(profile: dict, persona: dict) -> dict:
    if persona.get("vibe"):
        profile["persona_vibe"] = persona["vibe"]
    if persona.get("environment"):
        profile["setting"] = persona["environment"]
    if persona.get("lighting_variation"):
        profile["persona_lighting"] = persona["lighting_variation"]
    if persona.get("motion_speed"):
        profile["persona_motion"] = persona["motion_speed"]
    if persona.get("clothing"):
        # Split by comma, pick ONE random option (not all concatenated)
        chosen = _pick_random_option(persona["clothing"])
        profile["persona_clothing"] = chosen
        profile["persona_clothing_used"] = chosen
    if persona.get("hair_style"):
        # Split by comma, pick ONE random option
        chosen = _pick_random_option(persona["hair_style"])
        profile["persona_hair"] = chosen
    base_audience = profile.get("target_audience", "")
    if persona.get("vibe") and base_audience:
        profile["target_audience"] = f"{base_audience} -- {persona['vibe']}"
    return profile
