"""
UGC Style Schema Client

Central source of truth for UGC styles.
Reads from Schema Engine (port 8100) with local fallback.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SCHEMA_ENGINE_URL = os.getenv("SCHEMA_ENGINE_URL", "http://localhost:8100")

# ── Local fallback (used when Schema Engine is unreachable) ─────────
_FALLBACK_STYLES: Dict[str, Dict[str, Any]] = {
    "holding": {
        "model_action": "Ethnic Thai woman with porcelain white glowing skin, monolid eyes, Southeast Asian features. NOT applying or using product, NOT opening product, just holding and showing the product gently in both hands at chest level, packaging facing camera. CRITICAL: The cap is CLOSED and sealed. Both hands hold the closed product only.",
        "camera": "medium shot, chest-up framing, product visible in hands, shallow depth of field",
        "vibe": "authentic, gentle, product-focused, soft presentation",
        "keywords": "holding product, NOT applying, product showcase, hands holding, packaging visible",
        "video_motion": "model gently holding product, slight slow rotation of hands showing packaging, subtle breathing motion, NO squeezing or pumping motion",
        "negative_emphasis": "Do NOT open or apply the product. No squeezing, no pumping, no spraying. No usage actions.",
        "video_resolution": "720P",
        "aspect_ratio": "9:16",
    },
    "usage": {
        "model_action": "applying product to skin/face in real-time natural motions, showing texture absorption, gentle patting motion",
        "camera": "close-up medium shot, product and application area visible, natural lighting",
        "vibe": "demonstrative, practical, results-focused, how-to",
        "keywords": "product usage, apply, how to use, demonstration, texture, absorption",
        "video_motion": "hand applying product, close up of skin application, product texture spread, gentle massage motion",
    },
    "review": {
        "model_action": "talking to camera, holding product, pointing at packaging features, excited expressions",
        "camera": "medium shot, eye-level, product occasionally in frame, natural background",
        "vibe": "honest, enthusiastic, personal opinion, conversational",
        "keywords": "review, honest review, product review, unboxing, first impression",
        "video_motion": "model talking naturally, occasional product bring-up to camera, head gestures",
    },
    "talking": {
        "model_action": "headshot talking directly to camera, conversational tone, natural expressions, product mentioned but not focused",
        "camera": "close-up, face filling frame, shallow depth of field, professional lighting",
        "vibe": "intimate, direct, personal, storytelling",
        "keywords": "talking head, direct to camera, storytelling, personal, relatable",
        "video_motion": "model talking naturally, subtle head movements, genuine facial expressions",
    },
    "pov_lifehack": {
        "model_action": "POV angle, hands visible doing task, product solving a specific problem in real-time",
        "camera": "over-the-shoulder, chest-mounted POV, focus on hands and product action",
        "vibe": "authentic, problem-solving, instructional",
        "keywords": "POV, life hack, hands-on solution, real-time problem solving",
        "video_motion": "first-person POV motion, hands demonstrating product use, natural hand movements",
    },
    "asmr_texture": {
        "model_action": "extreme close-up, product being opened/applied, slow deliberate movements, no talking first 3 seconds",
        "camera": "macro close-up, extreme close up of product texture, slow zoom",
        "vibe": "satisfying, sensory, focused",
        "keywords": "ASMR, texture close-up, satisfying sounds, product details",
        "video_motion": "very slow pan across product texture, product being clicked/opened/closed, slow-motion liquid flow",
    },
    "split_comparison": {
        "model_action": "before and after comparison, showing old way vs new way, split screen effect",
        "camera": "two shots side by side, same framing for before and after",
        "vibe": "dramatic, transformative, convincing",
        "keywords": "before after, comparison, transformation, old vs new",
        "video_motion": "split screen motion, left side showing struggle, right side showing ease, wipe transition effect",
    },
    "street_interview": {
        "model_action": "excited reaction, showing product as if discovered randomly, genuine surprise",
        "camera": "shaky handheld style, vlog style, product front and center",
        "vibe": "surprised, genuine, authentic discovery",
        "keywords": "street find, random discovery, honest reaction, impulse buy",
        "video_motion": "handheld camera motion, product being brought into frame suddenly, excited presenter gestures",
    },
    "greenscreen_react": {
        "model_action": "reacting to product content on greenscreen, pointing at overlay, expressive reactions",
        "camera": "medium shot in front of greenscreen, product overlay top corner",
        "vibe": "reactive, humorous, commentary, opinionated",
        "keywords": "reaction, greenscreen, react video, funny reaction, commentary",
        "video_motion": "model reacting with body language, pointing at greenscreen area, head turns",
    },
    "aesthetic_vlog": {
        "model_action": "slow lifestyle montage, product integrated into daily routine, aesthetic shots",
        "camera": "varied shots, 24fps cinematic, golden hour lighting, smooth gimbal",
        "vibe": "serene, aesthetic, aspirational, calming",
        "keywords": "aesthetic, vlog, lifestyle, slow living, daily routine, cinematic",
        "video_motion": "slow motion, smooth transitions, product in lifestyle context, cinematic pans",
    },
}

VALID_STYLES = list(_FALLBACK_STYLES.keys())
DEFAULT_STYLE = "holding"


# ── Schema Engine Client ───────────────────────────────────────────

def _fetch_from_engine(endpoint: str) -> Optional[dict]:
    """Fetch from Schema Engine, return None on failure."""
    try:
        import urllib.request
        url = f"{SCHEMA_ENGINE_URL}{endpoint}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.warning(f"Schema Engine unavailable ({e}), using fallback")
        return None


def get_styles_from_engine() -> Optional[List[Dict[str, Any]]]:
    """Fetch all active UGC styles from Schema Engine."""
    result = _fetch_from_engine("/api/v1/data/ugc_style")
    if result and result.get("success"):
        return result.get("data", [])
    return None


def is_valid_style(style_key: str) -> bool:
    """Check if style key exists (via Engine or fallback)."""
    if not style_key:
        return False
    records = get_styles_from_engine()
    if records is not None:
        return any(r.get("data", {}).get("style_key") == style_key
                   and r.get("data", {}).get("is_active", True)
                   for r in records)
    return style_key in _FALLBACK_STYLES


def get_default_style() -> str:
    """Get the system default style from Schema Engine."""
    records = get_styles_from_engine()
    if records is not None:
        for r in records:
            d = r.get("data", {})
            if d.get("is_default") and d.get("is_active", True):
                return d["style_key"]
    return DEFAULT_STYLE


def get_style_config(style_key: str) -> Dict[str, Any]:
    """Get full config for a style from Schema Engine, with fallback."""
    records = get_styles_from_engine()
    if records is not None:
        for r in records:
            d = r.get("data", {})
            if d.get("style_key") == style_key:
                return d
    # Fallback
    return _FALLBACK_STYLES.get(style_key, {})


def validate_ugc_style(style_key: Optional[str]) -> str:
    """Return valid style key (or default if invalid)."""
    if not style_key or not is_valid_style(style_key):
        return get_default_style()
    return style_key
