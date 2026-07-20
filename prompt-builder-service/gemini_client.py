# ─── Gemini API Client ──────────────────────────────────────────
# Low-level Gemini API calls + product image analysis
# ═══════════════════════════════════════════════════════════════════════

import os
import json
import base64
import logging
from typing import Optional, List, Dict, Any

import requests

logger = logging.getLogger("prompt-builder-service")

from shared_config import GEMINI_API_KEY as _GEMINI_API_KEY_LAZY
from shared_config import GEMINI_MODEL
from prompt_templates import _extract_json

# ─── Gemini API Calls ────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

GEMINI_MODEL_NAME = GEMINI_MODEL if isinstance(GEMINI_MODEL, str) else "gemini-2.5-flash"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"


def _get_gemini_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "")
    if key:
        return key
    try:
        key = _GEMINI_API_KEY_LAZY() if callable(_GEMINI_API_KEY_LAZY) else _GEMINI_API_KEY_LAZY
        if key:
            return key
    except Exception:
        pass
    return ""


def _call_gemini(system_prompt: str, user_text: str, temperature: float = 0.3) -> Optional[str]:
    """Call Gemini API with system instruction."""
    api_key = _get_gemini_key()
    if not api_key:
        logger.warning("No GEMINI_API_KEY set in environment")
        return None
    try:
        model = GEMINI_MODEL_NAME
        url = f"{GEMINI_API_URL}/{model}:generateContent"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_text}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": 2048},
        }
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            json=payload,
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            logger.error(f"Gemini API error ({resp.status_code}): {resp.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
        return None


import base64


def _call_gemini_vision(system_prompt: str, user_text: str, image_url: str, temperature: float = 0.3) -> Optional[str]:
    """Call Gemini API with image input (multimodal)."""
    api_key = _get_gemini_key()
    if not api_key:
        logger.warning("No GEMINI_API_KEY set in environment")
        return None
    if not image_url:
        return None
    try:
        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()
        img_b64 = base64.b64encode(img_resp.content).decode("utf-8")
        mime = img_resp.headers.get("content-type", "image/jpeg")
        model = GEMINI_MODEL_NAME
        url = f"{GEMINI_API_URL}/{model}:generateContent"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [
                {"text": user_text},
                {"inlineData": {"mimeType": mime, "data": img_b64}}
            ]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": 2048},
        }
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            json=payload,
            timeout=60,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            logger.error(f"Gemini Vision API error ({resp.status_code}): {resp.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Gemini Vision call failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════
# ─── Product Analysis ─────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

PRODUCT_ANALYSIS_SYSTEM = """คุณคือนักวิเคราะห์สินค้าสำหรับ TikTok Shop (Gemini-powered)
วิเคราะห์สินค้าที่ได้รับ และตอบกลับเป็น JSON ONLY (ไม่มีข้อความอื่น)

กฎสำคัญ:
- target_gender ต้องเลือกเพียง 1 เพศเท่านั้น: "male" หรือ "female" ห้ามใช้ "unisex"
- customer_problem: ระบุปัญหาเฉพาะที่เจาะจง ไม่กว้างเกินไป
- image_description: ภาษาอังกฤษล้วน 100% ห้ามมีภาษาไทยเด็ดขาด

🔴 กฎการวิเคราะห์ Packaging Action (บังคับ):
- อ่านชื่อสินค้า + คำอธิบาย แล้วค้นหาคำที่บ่งบอกกลไกการใช้งานของแพ็กเกจจิ้ง
- คำสำคัญที่ต้องระบุให้เจอ:
  • "Click", "คลิก", "กด", "กดกิ๊ก" → packaging_action: "click_to_release" + action_desc: "กดที่ตูดลิปเพื่อให้เนื้อลิปไหลขึ้นมา"
  • "Pump", "ปั๊ม", "กดปั๊ม" → packaging_action: "pump" + action_desc: "กดปั๊มเพื่อป้อนเนื้อผลิตภัณฑ์"
  • "Spray", "สเปรย์", "ฉีด" → packaging_action: "spray" + action_desc: "ฉีดพ่นลงบนผิว/ใบหน้า"
  • "Roll", "กลิ้ง", "โรลออน" → packaging_action: "roll" + action_desc: "กลิ้งลูกกลิ้งบนผิว"
  • "Matte", "แมทท์" → packaging_action: "smooth_application" + action_desc: "เกลี่ยเนื้อแมทท์ให้เนียน"
  • "Glossy", "ฉ่ำ", "วาว", "ชุ่มชื้น" → packaging_action: "glossy_shine" + action_desc: "อวดเนื้อลิปแวววาวฉ่ำ เม้มปากให้เห็นความฉ่ำ"
  • "Cream", "ครีม", "เนื้อครีม" → packaging_action: "blend" + action_desc: "เกลี่ยครีมซึมซาบสู่ผิว"
  • "Cushion", "คุชชั่น", "แพด" → packaging_action: "dab_press" + action_desc: "แตะคุมชั่นบนใบหน้าเบาๆ"
  • "Pen", "ปากกา", "คลิก Pen" → packaging_action: "click_pen" + action_desc: "คลิกปากกาแล้วเขียน/วาด"

- ถ้าไม่มีคำเหล่านี้เลย → packaging_action: "generic_hold" + action_desc: "ถือสินค้าและใช้งานทั่วไป"
- action_desc ให้เขียนภาษาไทย สั้น กระชับ

JSON ที่ต้องตอบ:
{
  "category": "beauty/fashion/electronics/food/home/tools/health/other",
  "target_gender": "male/female",
  "target_age": "25",
  "target_audience": "กลุ่มเป้าหมายหลัก เช่น สาววัยทำงานที่มีปัญหาริมฝีปากแห้ง",
  "setting": "สถานที่ถ่ายวิดีโอ เช่น vanity room หรือ bathroom",
  "customer_problem": "ปัญหาที่สินค้านี้แก้ (เจาะจง) เช่น ริมฝีปากแห้งแตก ไม่ฉ่ำ ใต้ตาคล้ำจากนอนดึก",
  "main_benefit": "คุณประโยชน์หลักของสินค้า เช่น ให้ริมฝีปากชุ่มชื้น ฉ่ำวาว ตลอดวัน",
  "packaging_action": "click_to_release/pump/spray/roll/smooth_application/glossy_shine/blend/dab_press/click_pen/generic_hold",
  "action_desc": "คำอธิบายภาษาไทยสั้นๆ ว่าแพ็กเกจจิ้งทำงานยังไง",
  "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"],
  "image_description": "ENGLISH ONLY — absolutely NO Thai language. Describe the scene for AI image generation.

🔴 CRITICAL — First Frame Rule (บังคับ):
- image_description = FIRST FRAME ของวิดีโอ (Wan 2.7 ใช้เป็น reference image)
- ต้องตรงกับท่าเริ่มต้นของ Video Prompt Scene แรกเป๊ะๆ
- สำหรับ Holding/UGC Style: นางแบบต้อง "ถือสินค้าที่ระดับอก" (holding at chest level) — ยังไม่เริ่มใช้
- ห้ามระบุว่านางแบบกำลังใช้สินค้า (กำลังทา, กำลังปั๊ม, กำลังฉีด) ใน image_description
- การทำงานที่ถูกต้อง:
  • Image (First Frame): ถือสินค้าที่ระดับอกเฉยๆ
  • Video Scene 1: เริ่มขยับจากท่าถือ → เริ่มใช้สินค้า
  • Video Scene 2+: ใช้สินค้าจริง

Include: model appearance (Thai woman/man, age 25, glowing skin), pose (HOLDING product at chest level — NOT applying yet), expression (confident smile / happy), setting (vanity room, cafe), lighting (soft natural window light), mood (warm, inviting). Focus on product being clearly visible and in focus. Do NOT describe the product being used/applied — that happens in the video.

Example (correct for Holding style): 'A beautiful Thai woman, 25 years old, glowing skin, happy smile, holding a lip product at chest level, product visible and in focus, in a vanity room with soft natural window lighting, warm and inviting atmosphere'",
}"""


PRODUCT_VISION_SYSTEM = """You are a product image analyst for TikTok Shop (Gemini-powered).
Analyze the product image and return JSON ONLY (no other text).

CRITICAL RULES:
- target_gender MUST be "male" or "female" — NEVER "unisex"
- image_description must be 100% English with NO Thai language

JSON format:
{
  "category": "beauty/fashion/electronics/food/home/tools/health/other",
  "product_type": "lipstick/cream/headphones/etc.",
  "target_gender": "male/female",
  "target_age": "25",
  "target_audience": "primary target audience (specific, in Thai for script)",
  "setting": "suggested video setting (English, e.g. vanity room, bathroom, cafe)",
  "colors": ["dominant color 1", "dominant color 2", "dominant color 3"],
  "packaging_style": "luxury/minimal/colorful/modern",
  "estimated_product_size": "small/medium/large",
  "customer_problem": "specific problem this product solves (in Thai for script)",
  "main_benefit": "specific main benefit (in Thai for script)",
  "image_description": "ENGLISH ONLY — absolutely NO Thai. Describe the ideal scene for AI image gen. Include: model appearance (Thai woman/man, age 25, glowing skin), pose (how they hold/use product, e.g. applying on lips showing glossy texture), expression, setting, lighting, mood. Focus on product texture/usage. Example: 'A beautiful Thai woman, 25 years old, glowing skin, happy smile, applying product on lips, vanity room, soft natural window lighting, glossy texture visible, warm atmosphere'
}"""





def analyze_product_image(product_image: str, product_name: str, description: str = "") -> Optional[dict]:
    """Analyze product image via Mistral Pixtral Vision API."""
    if not product_image:
        return None
    user_text = f"Analyze this product image. Product name: {product_name}. Description: {description if description else 'N/A'}"
    raw = _call_gemini_vision(PRODUCT_VISION_SYSTEM, user_text, product_image, temperature=0.3)
    if raw:
        result = _extract_json(raw)
        if result:
            logger.info(f"Vision analysis result: {result.get('category', 'unknown')} / {result.get('product_type', 'unknown')}")
            return result
    return None



