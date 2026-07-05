"""
TikTok UGC Studio — Product Analysis + Image/Video Prompt Builder
===============================================================
Analyzes product data via Gemini → produces:
  - Product profile: category, gender, age, setting, customer_problem, 
    main_benefit, target_audience, 5 hashtags
  - Image prompt for Klein 9B Img2Img / FLUX
  - Video prompt for Wan 2.7 img2vid
  - Negative prompt
"""

import os
import json
import logging
import re
import requests
from typing import Optional, Dict, Any, List

logger = logging.getLogger("tiktok-ugc.image_prompt_builder")

# ─── Gemini Config ─────────────────────────────────────────────────────

# Gemini — centralized config
from shared_config import GEMINI_API_KEY as _get_gemini
GEMINI_API_KEY = _get_gemini()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

# ─── UGC Style → Image/Video Style Mapping ─────────────────────────────

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


def _call_gemini(system_prompt: str, user_text: str, temperature: float = 0.3) -> Optional[str]:
    """Call Gemini API"""
    if not GEMINI_API_KEY:
        logger.warning("No GEMINI_API_KEY configured")
        return None
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_text}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": 1024},
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


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from Gemini response (handles ```json wrapping)"""
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


def _match_category(product_name: str, description: str = "") -> dict:
    """Match product name keywords to category map"""
    combined = (product_name + " " + description).lower()
    best_match = {"category": "other", "gender": "unisex", "age": "20-35", "setting": "clean modern lifestyle setting"}
    for keyword, info in PRODUCT_CATEGORY_MAP.items():
        if keyword.lower() in combined:
            return info
    return best_match


def _get_lighting(category: str) -> dict:
    return LIGHTING_MAP.get(category, LIGHTING_MAP["other"])


# ─── Main Public API ───────────────────────────────────────────────────

async def analyze_and_build_prompts(
    product_name: str,
    description: str = "",
    keywords: Optional[List[str]] = None,
    ugc_style: str = "holding",
    product_id: str = "",
    price: float = 0.0,
) -> dict:
    """
    Full pipeline (Gemini-based):
      1. Analyze product via Gemini → product profile
      2. Build image prompt, video prompt, negative prompt
      3. Return everything in one dict
    
    Args:
        product_name: ชื่อสินค้า (ภาษาไทย/อังกฤษ)
        description: คำอธิบายสินค้า (ถ้ามี)
        keywords: keywords ที่มีอยู่แล้ว (ถ้ามี)
        ugc_style: holding / usage / review / talking
        product_id: product ID (optional)
        price: ราคาสินค้า
    
    Returns:
        dict with:
          - analysis: {category, gender, age, setting, customer_problem, main_benefit, target_audience, hashtags}
          - image_prompt: prompt for Klein 9B / FLUX
          - video_prompt: prompt for Wan 2.7
          - negative_prompt: negative prompt
          - metadata: style info used
    """
    keywords = keywords or []
    kw_str = ", ".join(keywords[:5]) if keywords else "ไม่มี"

    # ── Step 1: Gemini Product Analysis ──────────────────────────────
    system_prompt = """คุณคือนักวิเคราะห์สินค้าสำหรับ TikTok Shop
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
}
หมายเหตุ:
- hashtags: 5 คำที่ใช้ได้จริงใน TikTok ภาษาไทย
- image_description: ต้องเข้ากับ ugc_style ที่เลือก
- category: เลือกให้ตรงกับหมวดของสินค้า"""

    user_text = f"""ชื่อสินค้า: {product_name}
คำอธิบาย: {description if description else 'ไม่มี'}
Keywords: {kw_str}
UGC Style: {ugc_style}
ราคา: {price} บาท"""

    raw = _call_gemini(system_prompt, user_text, temperature=0.3)
    gemini_profile = _extract_json(raw) if raw else None

    if not gemini_profile:
        logger.warning("Gemini analysis failed or returned no JSON — using category map fallback")
        # Fallback: category map + defaults
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
        # Convert hashtags to string list if they came as single string
        if isinstance(gemini_profile.get("hashtags"), str):
            gemini_profile["hashtags"] = [h.strip().replace("#","") for h in gemini_profile["hashtags"].split(",")][:5]
        elif not isinstance(gemini_profile.get("hashtags"), list):
            gemini_profile["hashtags"] = [product_name.replace(" ","")[:20]]

    logger.info(f"Gemini analysis: category={gemini_profile.get('category')} "
                f"gender={gemini_profile.get('target_gender')} "
                f"hashtags={gemini_profile.get('hashtags', [])}")

    # ── Step 2: Build Image Prompt ───────────────────────────────────
    g = gemini_profile
    category = g.get("category", "other")
    model_gender = g.get("target_gender", "unisex")
    model_age = g.get("target_age", "20-35")
    model_setting = g.get("setting", "clean modern lifestyle setting")
    lighting = _get_lighting(category)
    style_info = STYLE_MAP.get(ugc_style, STYLE_MAP["holding"])
    customer_problem = g.get("customer_problem", "")
    main_benefit = g.get("main_benefit", "")

    gender_en = {"female": "woman", "male": "man", "unisex": "person"}.get(model_gender, "person")

    # Image prompt — for Klein 9B Img2Img / FLUX
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

    # Video prompt — for Wan 2.7 img2vid (motion-focused, shorter)
    video_prompt = (
        f"Thai {gender_en} {model_age}, {style_info['video_motion']}. "
        f"{product_name} visible in frame. "
        f"Setting: {model_setting}. "
        f"{lighting['lighting']}. {lighting['atmosphere']}. "
        f"9:16 portrait, smooth natural motion"
    )

    # Negative prompt
    negative_prompt = (
        "no text, no watermark, no logo, no UI overlay, "
        "no blurred face, no distorted hands, no extra fingers, "
        "no manga, no cartoon, no illustration, no 3D render, "
        "no low resolution, no pixelation, no artifacts, "
        "no cluttered background, no messy room"
    )

    # ── Step 3: Hashtags ────────────────────────────────────────────
    hashtags = g.get("hashtags", [])
    if isinstance(hashtags, list):
        hashtags = [h.strip().replace("#","") for h in hashtags if h.strip()]
        while len(hashtags) < 5:
            hashtags.append(product_name.replace(" ","").replace("\n","")[:20])
        hashtags = hashtags[:5]
    else:
        hashtags = [product_name.replace(" ","")[:20]] * 5

    result = {
        "product_id": product_id,
        "analysis": {
            "category": category,
            "target_gender": model_gender,
            "target_age": model_age,
            "target_audience": g.get("target_audience", ""),
            "setting": model_setting,
            "customer_problem": customer_problem,
            "main_benefit": main_benefit,
            "hashtags": hashtags,
            "image_description": g.get("image_description", ""),
        },
        "image_prompt": image_prompt,
        "video_prompt": video_prompt,
        "negative_prompt": negative_prompt,
        "metadata": {
            "ugc_style": ugc_style,
            "lighting": lighting["lighting"],
            "composition": lighting["composition"],
            "atmosphere": lighting["atmosphere"],
            "used_gemini": gemini_profile is not None,
        },
    }

    logger.info(f"Prompt built for [{product_name[:30]}]: "
                f"img_prompt={len(image_prompt)}ch, "
                f"vid_prompt={len(video_prompt)}ch")

    return result


# ─── Backward Compat: build_prompt() ──────────────────────────────────

async def build_prompt(
    product_name: str,
    description: str = "",
    ugc_style: str = "holding",
    gemini_analysis: Optional[dict] = None
) -> dict:
    """
    Legacy API — calls analyze_and_build_prompts without analysis.
    Kept for compatibility with existing callers.
    """
    result = await analyze_and_build_prompts(
        product_name=product_name,
        description=description,
        ugc_style=ugc_style,
    )
    return result


async def process_image_prompt_request(
    product_name: str,
    description: str = "",
    ugc_style: str = "holding",
    use_mistral: bool = True
) -> dict:
    """Legacy API wrapper"""
    return await analyze_and_build_prompts(
        product_name=product_name,
        description=description,
        ugc_style=ugc_style,
    )
