# ─── Prompt Templates ────────────────────────────────────────────
# STYLE_MAP, UGC prompt template loaders, utility functions
# ═══════════════════════════════════════════════════════════════════════

import os
import json
import re
from typing import Optional, List, Dict, Any
from pathlib import Path

BASE_DIR = Path(__file__).parent
UGC_DIR = BASE_DIR / "UGC_prompts"
RECIPES_DIR = BASE_DIR / "recipes"

STYLE_MAP = {
    "holding": {
        "model_action": "holding the product in both hands, product packaging facing camera, smiling naturally",
        "camera": "mid shot, waist up, product visible at chest level",
        "vibe": "friendly, approachable, product-focused",
        "keywords": "both hands holding product, product clearly visible and in focus",
        "video_motion": "model holding product, gentle hand movement showing product tube, natural breathing motion, slight head tilt",
    },
    "usage": {
        "model_action": "actively using the product in a natural daily setting, candid moment, product in use",
        "camera": "medium shot showing product usage context, slightly zoomed for action",
        "vibe": "authentic, lifestyle, in-the-moment",
        "keywords": "product in use, daily routine, natural hands-on moment",
        "video_motion": "model applying/using product naturally, gentle hand movements, routine motion",
    },
    "review": {
        "model_action": "holding product up showing packaging to camera, excited expression, like unboxing reaction",
        "camera": "close up to mid shot, product front and center, model slightly off-center",
        "vibe": "enthusiastic, honest, review energy",
        "keywords": "product held up, packaging visible, model reacting to product",
        "video_motion": "model showing product to camera, gentle presenter motion, slight zoom effect",
    },
    "talking": {
        "model_action": "talking while casually holding product, relaxed hand gesture, product naturally present",
        "camera": "close up, talking head style, product in lower frame",
        "vibe": "conversational, vlog-style, personal",
        "keywords": "talking head, casually holding, natural conversation pose",
        "video_motion": "model talking naturally, subtle head and hand gestures, casual vlog motion",
    },
    "pov_lifehack": {
        "model_action": "POV angle, hands visible doing task, product solving a specific problem in real-time",
        "camera": "over-the-shoulder, chest-mounted POV, focus on hands and product action",
        "vibe": "authentic, problem-solving, instructional",
        "keywords": "POV, life hack, hands-on solution, real-time problem solving",
        "video_motion": "first-person POV motion, hands demonstrating product use, natural hand movements, solution reveal",
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
        "model_action": "model pointing at content behind them, reacting to product benefits shown on screen",
        "camera": "medium shot, model off-center left/right, space for content behind",
        "vibe": "reactive, commentary-style, TikTok-native",
        "keywords": "green screen, reaction, point and comment, trending format",
        "video_motion": "model pointing and gesturing at content, head turns, reaction expressions",
    },
    "aesthetic_vlog": {
        "model_action": "model going through routine naturally, product appears organically in scene, GRWM energy",
        "camera": "variety of angles, fast cuts, cinematic b-roll, sometimes model not looking at camera",
        "vibe": "cinematic, aesthetic, aspirational, premium",
        "keywords": "vlog, daily routine, GRWM, aesthetic lifestyle, cinematic",
        "video_motion": "fast paced cuts, product smoothly appearing in frame, slow motion segments, smooth transitions",
    },
}


UGC_STYLE_FOLDER = {
    "holding": "Holding_Product",
    "review": "UGC_Review",
    "usage": "Product_Usage",
    "talking": "UGC_Review",
    "pov_lifehack": "POV_Lifehack",
    "asmr_texture": "ASMR_Texture",
    "split_comparison": "Split_Comparison",
    "street_interview": "Street_Interview",
    "greenscreen_react": "Greenscreen_React",
    "aesthetic_vlog": "Aesthetic_Vlog",
}


def load_ugc_templates(style: str) -> dict:
    """Load UGC_prompts/{style}/ template files into a dict.

    Returns: { 'system': str, 'master': str, 'user.template': str, 'negative': str }
    """
    folder_name = UGC_STYLE_FOLDER.get(style, "UGC_Review")
    base = UGC_DIR / folder_name
    result = {}
    for name in ["system", "master", "user.template", "negative"]:
        f = base / f"{name}.prompt"
        if f.exists():
            result[name] = f.read_text(encoding="utf-8")
        else:
            result[name] = ""
    return result


def fill_template(template: str, data: dict) -> str:
    """Replace {key} or {{key}} placeholders with data[key]."""
    def replacer(m):
        key = m.group(1).strip()
        v = data.get(key)
        return str(v) if v is not None else ""
    text = re.sub(r'\{\{(\w+)\}\}', replacer, template)
    text = re.sub(r'\{(\w+)\}', replacer, text)
    return text


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from Gemini/Mistral response."""
    if not text:
        return None
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            return None
    return None


# ═══════════════════════════════════════════════════════════════════════
