# ─── Prompt Templates ────────────────────────────────────────────
# STYLE_MAP, category mapping, UGC prompt template loaders
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


PRODUCT_CATEGORY_MAP = {
    "ลิปสติก":    {"category": "beauty",  "gender": "female", "age": "25", "setting": "vanity room หรือ outdoor เช่น ร้านกาแฟ"},
    "ลิป":        {"category": "beauty",  "gender": "female", "age": "25", "setting": "vanity room หรือ outdoor เช่น ร้านกาแฟ"},
    "คอนซีลเลอร์": {"category": "beauty",  "gender": "female", "age": "25", "setting": "vanity room with mirror, good lighting"},
    "บลัช":       {"category": "beauty",  "gender": "female", "age": "25", "setting": "vanity or bedroom, soft natural lighting"},
    "มาส์ก":      {"category": "beauty",  "gender": "female", "age": "25", "setting": "bathroom or bedroom, clean modern background"},
    "สบู่":        {"category": "beauty",  "gender": "unisex", "age": "25", "setting": "bathroom, clean tiled wall, modern"},
    "ครีม":       {"category": "beauty",  "gender": "female", "age": "25", "setting": "bathroom หรือ bedroom vanity"},
    "เซรั่ม":     {"category": "beauty",  "gender": "female", "age": "25", "setting": "bathroom vanity, clean white background"},
    "กันแดด":     {"category": "beauty",  "gender": "unisex", "age": "25", "setting": "outdoor หรือ near window, natural light"},
    "สกินแคร์":    {"category": "beauty",  "gender": "female", "age": "25", "setting": "bedroom vanity, soft natural lighting"},
    "หูฟัง":      {"category": "electronics", "gender": "unisex", "age": "25", "setting": "modern room, desk with tech accessories"},
    "ลำโพง":     {"category": "electronics", "gender": "unisex", "age": "25", "setting": "living room หรือ desk, modern decor"},
    "ขนม":        {"category": "food",    "gender": "unisex", "age": "25", "setting": "kitchen table หรือ cafe, natural lighting"},
    "เครื่องดื่ม": {"category": "food",    "gender": "unisex", "age": "25", "setting": "cafe corner หรือ modern kitchen"},
    "เสื้อผ้า":    {"category": "fashion", "gender": "unisex", "age": "25", "setting": "modern wardrobe, clean background"},
    "รองเท้า":    {"category": "fashion", "gender": "unisex", "age": "25", "setting": "streetwear style, urban background"},
    "ไขควง":      {"category": "tools",   "gender": "male",   "age": "25", "setting": "workshop หรือ garage, tool bench background"},
    "เครื่องมือ":  {"category": "tools",   "gender": "male",   "age": "25", "setting": "workshop background with tool rack"},
    "ของใช้ในบ้าน": {"category": "home",  "gender": "unisex", "age": "25", "setting": "bright living room หรือ kitchen"},
    "เฟอร์นิเจอร์": {"category": "home",  "gender": "unisex", "age": "25", "setting": "bright modern room display"},
}


LIGHTING_MAP = {
    "beauty":     {"lighting": "soft diffused natural window lighting, warm and gentle", "composition": "model centered or slightly off-center, eye-level angle", "background": "clean minimal background, soft pastel tones or white", "color_palette": "warm pastels, pink tones, natural skin tones", "atmosphere": "warm, inviting, feminine, premium"},
    "tools":      {"lighting": "bright functional lighting, cool to neutral white balance", "composition": "model holding tool in working posture, slightly low angle for strength", "background": "workshop wall with tool rack or pegboard", "color_palette": "neutral grays, blue tones, wood workshop tones", "atmosphere": "practical, sturdy, professional"},
    "electronics": {"lighting": "clean bright studio lighting with soft shadows", "composition": "model holding device at chest level, tech-focused framing", "background": "modern minimalist room, blurred ambient background", "color_palette": "cool whites, blue-grays, tech blue accent", "atmosphere": "modern, sleek, innovative"},
    "food":       {"lighting": "warm golden hour lighting, natural and appetizing", "composition": "close up of product and model's hands, upper body shot", "background": "cafe, kitchen counter, blurred warm background", "color_palette": "warm amber, creamy beige, natural green accents", "atmosphere": "cozy, appetizing, lifestyle"},
    "fashion":    {"lighting": "bright studio lighting, fashion editorial style", "composition": "full body or 3/4 shot, dynamic pose", "background": "modern clean background, studio or urban setting", "color_palette": "neutral fashion tones, monochrome or bold accent", "atmosphere": "stylish, trendy, confident"},
    "home":       {"lighting": "bright natural daylight, clean and fresh", "composition": "medium shot showing product in home context", "background": "bright clean living space, lifestyle setting", "color_palette": "clean whites, wood tones, natural greens", "atmosphere": "clean, organized, practical"},
    "other":      {"lighting": "soft natural lighting, clean and professional", "composition": "upper body shot, product visible and in focus", "background": "clean minimal background, lifestyle appropriate", "color_palette": "natural tones, neutral background", "atmosphere": "authentic, professional, relatable"},
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


def _match_category(product_name: str, description: str = "") -> dict:
    """Match product name keywords to category map (fallback)."""
    combined = (product_name + " " + description).lower()
    best_match = {"category": "other", "gender": "unisex", "age": "20-35", "setting": "clean modern lifestyle setting"}
    for keyword, info in PRODUCT_CATEGORY_MAP.items():
        if keyword.lower() in combined:
            return info
    return best_match


def _get_lighting(category: str) -> dict:
    return LIGHTING_MAP.get(category, LIGHTING_MAP["other"])


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from Mistral response."""
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
