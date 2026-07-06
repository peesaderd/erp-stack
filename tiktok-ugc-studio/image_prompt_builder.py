#!/usr/bin/env python3
"""
Prompt Builder — Unified Pipeline
====================================
Uses Gemini for:
  - Product analysis (category, gender, age, problem, benefit)
  - UGC prompt generation (image_prompt, video_prompt, negative_prompt)
  - Script generation

Single import for all prompt-related work.
"""

import os
import sys
import json
import logging
import re
import random
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger("prompt_builder")

# ─── Paths ───────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent  # erp-stack/
PROMPTS_DIR = BASE_DIR / "modules" / "video" / "prompts"
UGC_DIR = PROMPTS_DIR / "UGC_prompts"

# ─── Gemini Config ───────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# ─── Style / Category Maps (fallback when Gemini fails) ──────────────

STYLE_MAP = {
    "holding": {
        "model_action": "holding the product in both hands, product packaging facing camera, smiling naturally",
        "camera": "mid shot, waist up, product visible at chest level",
        "vibe": "friendly, approachable, product-focused",
        "keywords": "both hands holding product, product clearly visible and in focus",
        "video_motion": "model holding product, gentle hand movement showing packaging, natural breathing motion, slight head tilt",
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
}

PRODUCT_CATEGORY_MAP = {
    "ลิปสติก":    {"category": "beauty",  "gender": "female", "age": "18-30", "setting": "vanity room or bedroom with mirror"},
    "ลิป":        {"category": "beauty",  "gender": "female", "age": "18-30", "setting": "vanity room or bedroom with mirror"},
    "คอนซีลเลอร์": {"category": "beauty",  "gender": "female", "age": "18-30", "setting": "vanity room with mirror, good lighting"},
    "บลัช":       {"category": "beauty",  "gender": "female", "age": "18-30", "setting": "vanity or bedroom, soft natural lighting"},
    "มาส์ก":      {"category": "beauty",  "gender": "female", "age": "20-35", "setting": "bathroom or bedroom, clean modern background"},
    "สบู่":        {"category": "beauty",  "gender": "unisex", "age": "20-40", "setting": "bathroom, clean tiled wall, modern"},
    "ครีม":       {"category": "beauty",  "gender": "female", "age": "25-40", "setting": "bathroom or bedroom vanity"},
    "เซรั่ม":      {"category": "beauty",  "gender": "female", "age": "25-40", "setting": "bathroom vanity, clean white background"},
    "กันแดด":     {"category": "beauty",  "gender": "unisex", "age": "18-40", "setting": "outdoor or near window, natural light"},
    "สกินแคร์":    {"category": "beauty",  "gender": "female", "age": "20-35", "setting": "bedroom vanity, soft natural lighting"},
    "หูฟัง":      {"category": "electronics", "gender": "unisex", "age": "18-30", "setting": "modern room, desk with tech accessories"},
    "ลำโพง":     {"category": "electronics", "gender": "unisex", "age": "20-40", "setting": "living room or desk, modern decor"},
    "ขนม":        {"category": "food",    "gender": "unisex", "age": "18-35", "setting": "kitchen table or cafe, natural lighting"},
    "เครื่องดื่ม": {"category": "food",    "gender": "unisex", "age": "18-40", "setting": "cafe corner or modern kitchen"},
    "เสื้อผ้า":    {"category": "fashion", "gender": "unisex", "age": "18-35", "setting": "modern wardrobe, clean background"},
    "รองเท้า":    {"category": "fashion", "gender": "unisex", "age": "18-35", "setting": "streetwear style, urban background"},
    "ไขควง":      {"category": "tools",   "gender": "male",   "age": "25-50", "setting": "workshop or garage, tool bench background"},
    "เครื่องมือ":  {"category": "tools",   "gender": "male",   "age": "25-50", "setting": "workshop background with tool rack"},
    "ของใช้ในบ้าน": {"category": "home",  "gender": "unisex", "age": "25-50", "setting": "bright living room or kitchen"},
    "เฟอร์นิเจอร์": {"category": "home",  "gender": "unisex", "age": "25-50", "setting": "bright modern room display"},
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

# ─── Variation templates (fallback) ──────────────────────────────────
VARIATIONS = {
    "hooks": [
        "ปัญหาที่เจอบ่อย", "จุดเด่นที่โดดเด่น", "ความแตกต่างจากสินค้าอื่น",
        "ประโยชน์ที่ได้จริง", "รีวิวจากผู้ใช้จริง", "ใครกำลังมองหา",
        "ถ้าคุณต้องการ", "ลองดูสินค้านี้", "รีบมาดูเลย",
        "ของดีมาแล้ว", "ไม่ต้องรอแล้ว", "สินค้านี้เหมาะกับ",
        "แนะนำสินค้าดี", "มีสินค้ามาแนะนำ", "ของดีที่อยากบอกต่อ",
        "สินค้าที่น่าสนใจ", "รีวิวสินค้าดี", "ลองมาดูกัน",
        "ของดีราคาถูก", "สินค้าคุณภาพ"
    ],
    "tones": [
        "เป็นกันเอง พูดเร็ว", "จริงใจ น่าเชื่อถือ",
        "ตื่นเต้น ประทับใจ", "สบายๆ ไม่เป็นทางการ",
        "กระชับ ตรงประเด็น"
    ],
    "ctas": [
        "กดตะกร้าเลย", "สั่งเลยวันนี้", "ของดีราคาถูก",
        "กดสั่งซื้อเลย", "ดูรายละเอียดในตะกร้า"
    ],
    "benefits": [
        "คุณภาพดี ใช้งานได้จริง", "คุ้มค่า ราคาไม่แพง",
        "ใช้งานง่าย สะดวก", "ทนทาน ใช้งานได้นาน",
        "ดีไซน์สวย ใช้งานได้หลากหลาย"
    ],
}

# Try to load variation.json for richer content
try:
    var_path = PROMPTS_DIR / "variation.json"
    if var_path.exists():
        with open(var_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            if isinstance(loaded, dict):
                for k in ["hooks", "tones", "ctas", "benefits"]:
                    if k in loaded and isinstance(loaded[k], list) and len(loaded[k]) > 0:
                        VARIATIONS[k] = loaded[k]
except Exception:
    pass


# ═══════════════════════════════════════════════════════════════════════
# ─── Core: Load UGC Prompt Templates ─────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

UGC_STYLE_FOLDER = {
    "holding": "Holding_Product",
    "review": "UGC_Review",
    "usage": "Product_Usage",
    "talking": "UGC_Review",
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
    """Extract JSON from Gemini response."""
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
# ─── Gemini API Call ──────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

def _call_gemini(system_prompt: str, user_text: str, temperature: float = 0.3) -> Optional[str]:
    """Call Gemini API with system instruction."""
    if not GEMINI_API_KEY:
        logger.warning("No GEMINI_API_KEY set in environment")
        return None
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_text}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": 2048},
        }
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            logger.error(f"Gemini API error ({resp.status_code}): {resp.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════
# ─── Product Analysis ─────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

PRODUCT_ANALYSIS_SYSTEM = """คุณคือนักวิเคราะห์สินค้าสำหรับ TikTok Shop
วิเคราะห์สินค้าที่ได้รับ และตอบกลับเป็น JSON ONLY (ไม่มีข้อความอื่น)

JSON ที่ต้องตอบ:
{
  "category": "beauty/fashion/electronics/food/home/tools/health/other",
  "target_gender": "male/female/unisex",
  "target_age": "ช่วงอายุ เช่น 18-30",
  "target_audience": "กลุ่มเป้าหมายหลัก เช่น สาววัยทำงานที่มีปัญหาตาคล้ำ",
  "setting": "สถานที่ถ่ายวิดีโอ เช่น vanity room หรือ bathroom",
  "customer_problem": "ปัญหาที่สินค้านี้แก้ เช่น ใต้ตาคล้ำ หน้าหมองคล้ำ",
  "main_benefit": "คุณประโยชน์หลักของสินค้า เช่น ปกปิดรอยคล้ำ ให้ใต้ตาสว่าง",
  "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"],
  "image_description": "บรรยายภาพที่ควรสร้าง: เพศ, อายุ, ลักษณะ, ท่าทาง, ฉากหลัง, แสง, อารมณ์"
}"""


def analyze_product(product_name: str, description: str = "", keywords: Optional[List[str]] = None) -> dict:
    """Analyze product via Gemini and return profile dict.
    
    Falls back to category map if Gemini fails.
    """
    keywords = keywords or []
    kw_str = ", ".join(keywords[:5]) if keywords else "ไม่มี"
    
    user_text = f"""ชื่อสินค้า: {product_name}
คำอธิบาย: {description if description else 'ไม่มี'}
Keywords: {kw_str}"""

    raw = _call_gemini(PRODUCT_ANALYSIS_SYSTEM, user_text, temperature=0.3)
    gemini_profile = _extract_json(raw) if raw else None

    if not gemini_profile:
        logger.warning("Gemini analysis failed — using category map fallback")
        cinfo = _match_category(product_name, description)
        gender_label = {"female": "หญิง", "male": "ชาย", "unisex": "ทุกเพศ"}.get(cinfo["gender"], "หญิง")
        gemini_profile = {
            "category": cinfo["category"],
            "target_gender": cinfo["gender"],
            "target_age": cinfo["age"],
            "target_audience": f"ผู้{gender_label}วัย {cinfo['age']} ปี",
            "setting": cinfo["setting"],
            "customer_problem": "ปรับปรุงรูปลักษณ์/ฟังก์ชันการใช้งาน",
            "main_benefit": "คุณภาพดี คุ้มค่า",
            "hashtags": keywords[:5] if len(keywords) >= 5 else [product_name[:20]],
            "image_description": f"{gender_label}ไทย {cinfo['age']} ปี ใน {cinfo['setting']}",
        }
        if isinstance(gemini_profile.get("hashtags"), str):
            gemini_profile["hashtags"] = [h.strip().replace("#", "") for h in gemini_profile["hashtags"].split(",")][:5]
        elif not isinstance(gemini_profile.get("hashtags"), list):
            gemini_profile["hashtags"] = [product_name.replace(" ", "")[:20]]

    # Normalize
    h = gemini_profile.get("hashtags", [])
    if isinstance(h, list):
        h = [x.strip().replace("#", "") for x in h if x.strip()]
        while len(h) < 5:
            h.append(product_name.replace(" ", "").replace("\n", "")[:20])
        gemini_profile["hashtags"] = h[:5]
    else:
        gemini_profile["hashtags"] = [product_name.replace(" ", "")[:20]] * 5

    return gemini_profile


# ═══════════════════════════════════════════════════════════════════════
# ─── Image & Video Prompt Generation ──────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

def build_image_prompt(profile: dict, product_name: str, ugc_style: str = "holding") -> str:
    """Generate image prompt using UGC_prompts templates + product profile.
    
    Falls back to hardcode if template not available.
    """
    templates = load_ugc_templates(ugc_style)
    style_info = STYLE_MAP.get(ugc_style, STYLE_MAP["holding"])
    category = profile.get("category", "other")
    model_gender = profile.get("target_gender", "unisex")
    model_age = profile.get("target_age", "20-35")
    model_setting = profile.get("setting", "clean modern lifestyle setting")
    lighting = _get_lighting(category)
    customer_problem = profile.get("customer_problem", "")
    main_benefit = profile.get("main_benefit", "")
    gender_en = {"female": "woman", "male": "man", "unisex": "person"}.get(model_gender, "person")

    data = {
        "product_name": product_name,
        "customer_problem": customer_problem,
        "main_benefit": main_benefit,
        "model_gender": gender_en,
        "model_age": model_age,
        "setting": model_setting,
        "style": ugc_style,
        "tone": "professional",
        "composition": lighting["composition"],
        "lighting": lighting["lighting"],
        "atmosphere": lighting["atmosphere"],
        "color_palette": lighting["color_palette"],
        "background": lighting.get("background", "clean minimal background"),
        "model_action": style_info["model_action"],
        "camera": style_info["camera"],
        "vibe": style_info["vibe"],
        "keywords": style_info.get("keywords", ""),
        "hashtags": ", ".join(profile.get("hashtags", [])),
    }

    if templates.get("master") and templates.get("user.template"):
        # Use UGC_prompts templates
        master = fill_template(templates["master"], data)
        user_tpl = fill_template(templates["user.template"], data)
        negative = templates.get("negative", "")
        image_prompt = f"{master}\n\n{user_tpl}"
    else:
        # Fallback hardcode
        image_prompt = (
            f"A beautiful Thai {gender_en}, {model_age} years old, "
            f"glowing skin, pretty face, professional model quality, "
            f"{style_info['model_action']}. "
            f"Setting: {model_setting}. "
            f"{style_info['camera']}, {style_info['vibe']}. "
            f"{lighting['composition']}, {lighting['atmosphere']}, {lighting['color_palette']}. "
            f"The {product_name} is clearly in frame. "
            f"Product benefit: {main_benefit}. "
            f"{lighting['lighting']}. "
            f"Wearing casual everyday outfit. Professional e-commerce quality. "
            f"--ar 9:16"
        )
        negative = templates.get("negative", "")
    
    return image_prompt, negative


def build_video_prompt(profile: dict, product_name: str, ugc_style: str = "holding") -> str:
    """Generate video prompt for Wan 2.7 img2vid."""
    style_info = STYLE_MAP.get(ugc_style, STYLE_MAP["holding"])
    category = profile.get("category", "other")
    model_gender = profile.get("target_gender", "unisex")
    model_age = profile.get("target_age", "20-35")
    model_setting = profile.get("setting", "clean modern lifestyle setting")
    lighting = _get_lighting(category)
    gender_en = {"female": "woman", "male": "man", "unisex": "person"}.get(model_gender, "person")

    video_prompt = (
        f"Thai {gender_en} {model_age}, {style_info['video_motion']}. "
        f"{product_name} visible in frame. "
        f"Setting: {model_setting}. "
        f"{lighting['lighting']}. {lighting['atmosphere']}. "
        f"9:16 portrait, smooth natural motion"
    )
    return video_prompt


def build_negative_prompt(profile: dict, ugc_style: str = "holding") -> str:
    """Build negative prompt — merge template + defaults."""
    templates = load_ugc_templates(ugc_style)
    default = (
        "no text, no watermark, no logo, no UI overlay, "
        "no blurred face, no distorted hands, no extra fingers, "
        "no manga, no cartoon, no illustration, no 3D render, "
        "no low resolution, no pixelation, no artifacts, "
        "no cluttered background, no messy room"
    )
    tpl_neg = templates.get("negative", "")
    if tpl_neg:
        return f"{tpl_neg}, {default}"
    return default


# ═══════════════════════════════════════════════════════════════════════
# ─── Script Generation ────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

SCRIPT_SYSTEM = """คุณคือนักรีวิวขายสินค้าใน TikTok ระดับมืออาชีพ
พูดกระชับ น่าเชื่อถือ เป็นกันเอง จบไว

CRITICAL RULES:
✅ ใบหน้าต้องตรงกับภาพ reference 100%
❌ ห้ามใช้เสื้อผ้าจากภาพ reference
⚠️ ความยาวคลิป: 8 วินาที ต้องจบภายใน 8 วินาที

โครงสร้างเวลาบังคับ:
1) Hook (0-2 วินาที): เปิดด้วยปัญหาที่เข้าถึงกลุ่มเป้าหมาย
2) Value (2-6 วินาที): บอกประโยชน์หลัก 1 อย่างที่เฉพาะเจาะจง
3) CTA (6-8 วินาที): ต้องจบด้วย CTA ภาษาไทย

⚠️ เสียงพากย์มนุษย์ ชัดเจนระดับสตูดิโอ 48kHz
⚠️ ครบ 8 วินาที = จบ
⚠️ ตอบเป็น JSON:
{
  "hook": "ข้อความ 3-5 คำ",
  "script": "สคริปต์เต็ม 8 วินาที พูดปกติ ไม่ต้องบอกเวลากำกับ"
}"""


def _template_script(
    product_name: str,
    customer_problem: str = "",
    main_benefit: str = "",
    target_audience: str = "",
    tone: str = "",
) -> dict:
    """Generate script from template (fallback when Gemini fails)."""
    if not tone:
        tone = random.choice(VARIATIONS["tones"])
    if not customer_problem:
        customer_problem = random.choice(VARIATIONS["hooks"])
    if not main_benefit:
        main_benefit = random.choice(VARIATIONS["benefits"])
    
    cta = random.choice(VARIATIONS["ctas"])
    
    hook = f"{customer_problem} ใช่ไหมคะ"
    body = f"วันนี้เรามี {product_name} มาบอกต่อ {main_benefit} ค่ะ"
    full_script = f"{hook} {body} {cta} ค่ะ"
    
    return {
        "hook": hook,
        "script": full_script,
        "tone": tone,
        "cta": cta,
    }


def generate_script(
    product_name: str,
    customer_problem: str = "",
    main_benefit: str = "",
    target_audience: str = "",
    tone: str = "",
    extra_rules: str = "",
    profile: Optional[dict] = None,
) -> dict:
    """Generate TikTok review script using Gemini.
    
    Args:
        product_name: ชื่อสินค้า
        customer_problem: ปัญหาที่ลูกค้าเจอ (optional)
        main_benefit: จุดเด่นหลัก (optional)
        target_audience: กลุ่มเป้าหมาย (optional)
        tone: โทนเสียง (optional, random from variation.json)
        extra_rules: กฎเพิ่มเติม (optional)
        profile: profile dict จาก analyze_product() (optional)
    
    Returns:
        dict: { hook, script, tone, cta }
    """
    # Use profile data if available
    if profile:
        customer_problem = customer_problem or profile.get("customer_problem", "")
        main_benefit = main_benefit or profile.get("main_benefit", "")
        target_audience = target_audience or profile.get("target_audience", "")
    
    if not tone:
        tone = random.choice(VARIATIONS["tones"])
    
    user_text = f"""ชื่อสินค้า: {product_name}
ปัญหาที่ลูกค้าเจอ: {customer_problem if customer_problem else 'ยังไม่ระบุ'}
จุดเด่นหลัก: {main_benefit if main_benefit else 'ยังไม่ระบุ'}
กลุ่มเป้าหมาย: {target_audience if target_audience else 'ยังไม่ระบุ'}
โทนการพูด: {tone}
{extra_rules if extra_rules else ''}"""

    raw = _call_gemini(SCRIPT_SYSTEM, user_text, temperature=0.7)
    script_data = _extract_json(raw) if raw else None

    if script_data:
        return {
            "hook": script_data.get("hook", ""),
            "script": script_data.get("script", ""),
            "tone": tone,
            "cta": random.choice(VARIATIONS["ctas"]),
        }
    
    # Fallback to template
    logger.warning("Gemini script gen failed — using template fallback")
    return _template_script(product_name, customer_problem, main_benefit, target_audience, tone)


def get_script_variations() -> dict:
    """Return all variation options for frontend use."""
    return dict(VARIATIONS)


# ═══════════════════════════════════════════════════════════════════════
# ─── Main Public API (combine everything) ─────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

async def analyze_and_build_prompts(
    product_name: str,
    description: str = "",
    keywords: Optional[List[str]] = None,
    ugc_style: str = "holding",
    product_id: str = "",
    price: float = 0.0,
) -> dict:
    """
    Full pipeline:
      1. Analyze product via Gemini → product profile
      2. Build image prompt, video prompt, negative prompt (from UGC_prompts)
      3. Return everything in one dict
    """
    # Step 1: Analyze
    profile = analyze_product(product_name, description, keywords)
    
    # Step 2: Build prompts
    image_prompt, negative_prompt = build_image_prompt(profile, product_name, ugc_style)
    video_prompt = build_video_prompt(profile, product_name, ugc_style)
    if not negative_prompt:
        negative_prompt = build_negative_prompt(profile, ugc_style)
    
    result = {
        "product_id": product_id,
        "analysis": {
            "category": profile.get("category", "other"),
            "target_gender": profile.get("target_gender", "unisex"),
            "target_age": profile.get("target_age", "20-35"),
            "target_audience": profile.get("target_audience", ""),
            "setting": profile.get("setting", ""),
            "customer_problem": profile.get("customer_problem", ""),
            "main_benefit": profile.get("main_benefit", ""),
            "hashtags": profile.get("hashtags", []),
            "image_description": profile.get("image_description", ""),
        },
        "image_prompt": image_prompt,
        "video_prompt": video_prompt,
        "negative_prompt": negative_prompt,
        "metadata": {
            "ugc_style": ugc_style,
            "used_gemini": True,
        },
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
    use_mistral: bool = True
) -> dict:
    """Legacy API wrapper."""
    return await analyze_and_build_prompts(
        product_name=product_name,
        description=description,
        ugc_style=ugc_style,
    )