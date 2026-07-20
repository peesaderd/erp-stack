"""
Etsy AI Assistant — AI-driven listing gen + fix + optimize
ใช้ LLM (Gemini) ผ่าน API endpoint
Fallback: DeepSeek → Template-based suggestions เมื่อไม่มี API key
"""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger("etsy.assistant")

# ─── LLM Config ────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
OPENCODE_URL = os.environ.get("OPENCODE_URL", "http://127.0.0.1:8777/v1/chat/completions")
OPENCODE_MODEL = os.environ.get("OPENCODE_MODEL", "opencode-go/deepseek-v4-flash")


def _call_opencode(system_prompt: str, user_prompt: str) -> Optional[str]:
    """เรียก OpenCode proxy (local, always available)"""
    try:
        import httpx
        resp = httpx.post(
            OPENCODE_URL,
            headers={"Content-Type": "application/json"},
            json={
                "model": OPENCODE_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 2000,
            },
            timeout=60,
        )
        if resp.status_code != 200:
            logger.warning(f"OpenCode error: {resp.status_code} {resp.text[:150]}")
            return None
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"OpenCode call failed: {e}")
        return None


def _call_gemini(system_prompt: str, user_prompt: str) -> Optional[str]:
    """เรียก Gemini API (primary provider) — return None ถ้าไม่ได้"""
    if not GEMINI_API_KEY:
        logger.debug("Gemini: no API key, skipping")
        return None

    try:
        import httpx
        # Gemini API endpoint
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        resp = httpx.post(
            url,
            params={"key": GEMINI_API_KEY},
            headers={"Content-Type": "application/json"},
            json={
                "contents": [
                    {"role": "user", "parts": [{"text": system_prompt + "\n\n---\n\n" + user_prompt}]}
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": 2048,
                    "topP": 0.95,
                },
            },
            timeout=45,
        )
        if resp.status_code != 200:
            logger.warning(f"Gemini API error: {resp.status_code} {resp.text[:150]}")
            return None
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            logger.warning("Gemini: no candidates in response")
            return None
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        return text
    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
        return None


def _call_mistral(system_prompt: str, user_prompt: str) -> Optional[str]:
    """เรียก Mistral API (primary — has working key)"""
    if not MISTRAL_API_KEY:
        return None

    try:
        import httpx
        resp = httpx.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "mistral-large-latest",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 2000,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning(f"Mistral API error: {resp.status_code} {resp.text[:150]}")
            return None
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Mistral call failed: {e}")
        return None


def _call_deepseek(system_prompt: str, user_prompt: str) -> Optional[str]:
    """เรียก DeepSeek API (fallback) — return None ถ้าไม่ได้"""
    if not LLM_API_KEY:
        return None

    try:
        import httpx
        resp = httpx.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 2000,
            },
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning(f"DeepSeek API error: {resp.status_code} {resp.text[:100]}")
            return None
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"DeepSeek call failed: {e}")
        return None


def _call_llm(system_prompt: str, user_prompt: str) -> Optional[str]:
    """
    เรียก LLM โดยพยายาม providers ตามลำดับ:
    1. OpenCode (local proxy — always available)
    2. Mistral (fallback)
    3. Gemini (fallback)
    4. DeepSeek (fallback)
    5. None → ใช้ template fallback
    """
    # Primary: OpenCode proxy (local, no key needed)
    result = _call_opencode(system_prompt, user_prompt)
    if result:
        logger.debug("LLM: used OpenCode")
        return result

    # Fallback: Mistral
    result = _call_mistral(system_prompt, user_prompt)
    if result:
        logger.debug("LLM: used Mistral")
        return result

    # Fallback: Gemini
    result = _call_gemini(system_prompt, user_prompt)
    if result:
        logger.debug("LLM: used Gemini")
        return result

    # Last fallback: DeepSeek
    result = _call_deepseek(system_prompt, user_prompt)
    if result:
        logger.debug("LLM: used DeepSeek")
        return result

    logger.info("LLM: no provider available, using template fallback")
    return None


def _parse_json(text: str) -> Optional[dict]:
    """พยายาม parse JSON จาก response"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # อาจมี markdown ```json ... ``` ลอง extract
        import re
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        return None


# ─── Template-based Fallbacks ──────────────────────────────────────────────

ETSY_RULES_TEMPLATE = """
Etsy Rules ที่ต้องรู้:
- Title: 1-140 chars
- Tags: max 13 tags, แต่ละ tag max 20 chars
- Description: max 5000 chars
- Image: main 2000px+, พื้นหลัง clean
- Price: min $0.20
"""


def _template_fix_listing(listing: dict, problems: list) -> dict:
    """Template fallback — suggestions based on rules"""
    suggestions = []
    fixed_title = listing.get("title", "")
    fixed_tags = list(listing.get("tags", []))
    fixed_desc = listing.get("description", "")

    for p in problems:
        if "Title" in p and "ยาว" in p:
            fixed_title = fixed_title[:137] + "..."
            suggestions.append("ตัด title ให้สั้นลง")
        elif "Title" in p and "สั้น" in p:
            suggestions.append("เพิ่ม keyword หลักไว้ต้น title")
        elif "Tags" in p and "เกิน" in p:
            fixed_tags = fixed_tags[:13]
            suggestions.append(f"ตัด tags เหลือ 13")
        elif "Tags" in p and "ซ้ำ" in p:
            fixed_tags = list(dict.fromkeys(fixed_tags))
            suggestions.append("ลบ tags ซ้ำ")
        elif "Description" in p and "สั้น" in p:
            fixed_desc += " " + "รายละเอียดเพิ่มเติม: ผลิตจากวัสดุคุณภาพดี ผลิตด้วยมือ งานประณีต"
            suggestions.append("เพิ่มรายละเอียดสินค้าใน description")
        elif "ราคา" in p:
            suggestions.append("ปรับราคาให้มากกว่า $0.20")

    if not suggestions:
        suggestions = [
            "ใส่ keyword หลักไว้ต้น title",
            "เพิ่ม tags ให้ครบ 13 เพื่อ SEO",
            "เพิ่มรายละเอียดขนาดและวัสดุใน description",
            "เพิ่ม lifestyle photo เพื่อเพิ่ม conversion",
        ]

    return {
        "fixed_title": fixed_title,
        "fixed_tags": fixed_tags,
        "fixed_description": fixed_desc,
        "changes": suggestions,
        "explanation": "แก้ไขตามกฎ Etsy อัตโนมัติ (AI mode: template fallback)",
    }


# ─── Listing Generator ─────────────────────────────────────────────────────


def generate_listing(product_info: dict) -> dict:
    """AI generate ทั้ง Listing (title, tags, description) จากข้อมูลสินค้า"""
    system_prompt = f"""คุณคือ AI Assistant สำหรับสร้าง Listing ขายของบน Etsy
{ETSY_RULES_TEMPLATE}
ตอบเป็น JSON เสมอ: {{"title": "...", "tags": [...13 tags...], "description": "..."}}
ใช้ภาษาไทยผสมอังกฤษ"""

    user_prompt = f"ช่วยสร้าง Etsy listing จากข้อมูลนี้:\n{json.dumps(product_info, ensure_ascii=False)}"
    raw = _call_llm(system_prompt, user_prompt)

    if raw:
        parsed = _parse_json(raw)
        if parsed:
            return parsed

    # Fallback template
    name = product_info.get("name", "สินค้า")
    return {
        "title": f"Handmade {name} - Premium Quality - Unique Design",
        "tags": [
            "handmade", name.lower(), "gift", "unique", "craft",
            "best gift", "quality", "trendy", "artisan",
            "present", "decor", "accessory", "collection",
        ],
        "description": f"Handmade {name} crafted with care.高品质  handmade  products. เหมาะสำหรับเป็นของขวัญ",
    }


def fix_listing(listing: dict, validation: dict) -> dict:
    """AI แก้ไข Listing ตามผล validation"""
    problems = []
    for category, result in validation.get("results", {}).items():
        for fail in result.get("failed", []):
            problems.append(fail)

    if not problems:
        return {"fixed": False, "message": "ไม่มีปัญหา — ไม่ต้องแก้"}

    # Try LLM first
    system_prompt = f"""คุณคือ Etsy Listing Optimizer
{ETSY_RULES_TEMPLATE}
แก้ไข listing ให้ผ่านกฎ Etsy
ตอบ JSON: {{"fixed_title": "...", "fixed_tags": [...], "fixed_description": "...", "changes": ["..."], "explanation": "..."}}"""

    user_prompt = f"""แก้ไข listing นี้:
{json.dumps(listing, ensure_ascii=False)}

ปัญหาที่เจอ:
{json.dumps(problems, ensure_ascii=False)}"""

    raw = _call_llm(system_prompt, user_prompt)
    if raw:
        parsed = _parse_json(raw)
        if parsed:
            return parsed

    # Fallback template
    return _template_fix_listing(listing, problems)


def optimize_tags(product_info: dict) -> dict:
    """AI สร้าง 13 tags ที่ดีที่สุดสำหรับ SEO"""
    system_prompt = f"""คุณคือ Etsy SEO Specialist
สร้าง tags 13 อัน (แต่ละอัน ≤ 20 chars) สำหรับ Etsy listing
ตอบ JSON: {{"tags": [...], "search_volume_hints": [...]}}"""

    user_prompt = f"สร้าง 13 tags SEO สำหรับ: {json.dumps(product_info, ensure_ascii=False)}"
    raw = _call_llm(system_prompt, user_prompt)

    if raw:
        parsed = _parse_json(raw)
        if parsed:
            return parsed

    # Fallback template
    name = product_info.get("name", "สินค้า").lower()
    return {
        "tags": [
            "handmade", name, "gift", "unique", "craft",
            "best gift", "quality", "trendy", "artisan",
            "present", "decor", "accessory", "collection",
        ],
        "search_volume_hints": ["gift > handmade > unique"],
    }


def generate_product_concept(product_info: dict) -> dict:
    """AI generate สินค้าทั้ง concept — name, title, tags, description, price, image_prompt"""
    system_prompt = f"""คุณคือ AI Product Creator สำหรับ Etsy
{ETSY_RULES_TEMPLATE}
สร้าง concept สินค้าที่สมบูรณ์สำหรับ Etsy
ตอบ JSON:
{{
  "product_name": "...",
  "title": "...",
  "tags": [13 tags],
  "description": "...",
  "price": 12.99,
  "materials": ["..."],
  "image_prompt": "prompt for AI image generation (English, no watermark, no text)",
  "image_style": "pop_art | product | vintage | minimal | colorful"
}}"""

    user_prompt = f"สร้าง concept สินค้าจาก info นี้:\n{json.dumps(product_info, ensure_ascii=False)}"
    raw = _call_llm(system_prompt, user_prompt)

    if raw:
        parsed = _parse_json(raw)
        if parsed:
            return parsed

    # Fallback template
    name = product_info.get("name", "Handmade Item")
    return {
        "product_name": name,
        "title": f"Handmade {name} - Premium Quality",
        "tags": ["handmade", name.lower(), "gift", "artisan", "quality",
                  "unique", "craft", "decor", "trendy", "present",
                  "accessory", "collection", "best gift"],
        "description": f"Handmade {name} crafted with care. High quality materials.",
        "price": 19.99,
        "materials": ["cotton", "thread"],
        "image_prompt": f"A high quality {name} on white background, product photography, clean studio lighting, no watermark, no text",
        "image_style": "product",
    }


def generate_shop_banner_description(shop_info: dict) -> str:
    """AI generate คำอธิบายสำหรับออกแบบ banner"""
    system_prompt = """คุณคือ Graphic Design Consultant สำหรับ Etsy Shop
ให้คำแนะนำในการออกแบบ Shop Banner (3360×840 px)"""
    user_prompt = f"ออกแบบ banner สำหรับร้าน: {json.dumps(shop_info, ensure_ascii=False)}"

    raw = _call_llm(system_prompt, user_prompt)
    if raw:
        return raw

    # Template fallback
    return (
        "แนะนำ Banner: ใช้พื้นหลังขาวหรือโทนอ่อน "
        "วางชื่อร้านและสินค้าหลักตรงกลาง "
        "ขนาด 3360×840 px "
        "หลีกเลี่ยงข้อความเยอะ — เน้นรูปสินค้าคุณภาพสูง"
    )
