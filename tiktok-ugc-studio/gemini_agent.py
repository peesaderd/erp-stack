"""
Product Analyzer — ใช้ Gemini API (Vision + Text) สำหรับวิเคราะห์สินค้า + สร้าง Image Prompts
"""

import os
import json
import logging
import re
import base64
import httpx
from typing import Optional, Any
import requests
import json

logger = logging.getLogger("product-analyzer")

# ─── Gemini Config ─────────────────────────────────────────────────────

# Gemini — centralized config
from shared_config import GEMINI_API_KEY as _get_gemini
GEMINI_API_KEY = _get_gemini()
TEXT_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-2.5-flash")
VISION_MODEL = os.environ.get("GEMINI_VISION_MODEL", "gemini-2.5-flash")



RESEARCH_SYSTEM_PROMPT = '''คุณคือผู้เชี่ยวชาญด้านการวิจัยสินค้า วิเคราะห์รูปภาพและข้อมูลสินค้าอย่างละเอียด
Output ONLY valid JSON:
{
  "product_type": "ประเภทสินค้า (เช่น ไมโครโฟนไร้สาย ครีมบำรุงผิว อุปกรณ์ครัว)",
  "material": "วัสดุที่มองเห็นและผิวสัมผัส",
  "category": "หมวดหมู่การตลาด",
  "target_audience": "กลุ่มเป้าหมายที่ชัดเจน (ภาษาไทย)",
  "key_features": ["จุดเด่น 1", "จุดเด่น 2"],
  "visual_style_recommendation": "สไตล์ภาพที่แนะนำ",
  "age_group": "ช่วงอายุเป้าหมาย",
  "gender": "male/female/neutral",
  "environment": "ฉาก/สถานที่ที่แนะนำ",
  "pain_points": ["ปัญหา 1", "ปัญหา 2"],
  "hooking_angle": "มุมการตลาดที่ดีที่สุด (ภาษาไทย)"
}'''

PRESET_IMAGE_STYLES = [
    {"id": "holding_product", "name": "ถือสินค้า", "description": "สินค้าวางบนพื้นผิวเรียบสวยงาม", "suffix": "Product placed on a beautiful clean flat surface like marble or wood countertop, flat-lay photography, aesthetic composition, soft natural lighting, no hands, no person"},
    {"id": "product_usage", "name": "ใช้งานสินค้า", "description": "สินค้าในบรรยากาศการใช้งานจริงบนพื้นผิว", "suffix": "Product on a natural surface in a lifestyle setting, bathroom counter or vanity table, soft natural lighting, clean aesthetic, lifestyle flat-lay, no hands, no person"},
    {"id": "lifestyle", "name": "ไลฟ์สไตล์", "description": "สินค้าในชีวิตประจำวัน", "suffix": "Product integrated into everyday lifestyle scene on a clean surface, aesthetic composition, warm tones, no hands, no person in frame"},
    {"id": "close_up", "name": "Close-up", "description": "ถ่ายใกล้แสดงรายละเอียดสินค้า", "suffix": "Extreme close-up of product texture and details on a clean surface, macro photography, shallow depth of field, no hands"},
    {"id": "review_style", "name": "รีวิว", "description": "สไตล์รีวิว TikTok", "suffix": "Review-style setup, product on clean flat-lay or table, authentic lighting, social media aesthetic, no hands"},
]


def _call_gemini(
    system_prompt: str,
    user_text: str,
    image_base64: Optional[str] = None,
    model: Optional[str] = None,
    temperature: float = 0.1,
) -> str:
    """Call Gemini API — text-only or vision (with base64 image)"""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not configured")

    use_model = model or (VISION_MODEL if image_base64 else TEXT_MODEL)
    
    try:
        gen_model = genai.GenerativeModel(
            use_model,
            system_instruction=system_prompt,
            generation_config={
                "temperature": temperature,
                "max_output_tokens": 8192,
            },
        )

        contents = [user_text]
        if image_base64:
            img_data = image_base64.strip()
            if ";" in img_data:
                import re as _re
                m = _re.match(r'data:image/(\w+);base64,(.+)', img_data)
                if m:
                    img_data = m.group(2)
            contents.append(
                genai.upload_file_from_bytes(
                    base64.b64decode(img_data),
                    mime_type="image/jpeg",
                    display_name="product_image"
                )
            )

        response = gen_model.generate_content(contents)
        return response.text
    except Exception as e:
        raise RuntimeError(f"Gemini call failed: {e}")


def _parse_json(text: str) -> dict:
    """Parse JSON from Gemini response"""
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()
    raw = raw.replace(chr(10), " ").replace(chr(13), " ")
    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    raw = re.sub(r',\s*}', '}', raw)
    raw = re.sub(r',\s*]', ']', raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    stack = []
    start = -1
    for i, ch in enumerate(raw):
        if ch == '{':
            if not stack:
                start = i
            stack.append(ch)
        elif ch == '}':
            if stack:
                stack.pop()
                if not stack and start >= 0:
                    try:
                        return json.loads(raw[start:i+1])
                    except json.JSONDecodeError:
                        pass

    raise ValueError("Cannot parse JSON from Gemini response")


def extract_brand_protocol(image_base64: str) -> dict:
    """Extract Brand Identity Protocol from product image using Gemini Vision"""
    prompt_text = """วิเคราะห์รูปภาพสินค้านี้และ extract Brand Identity Protocol เป็น JSON

Extract EXACTLY:
1. product_name: ชื่อแบรนด์ + สินค้าตามที่เห็นบน包装
2. bottle: shape (รูปทรง), material (glass/plastic/matte/glossy), cap_type (dropper/pump/screw), primary_color
3. label: colors (สีบนฉลาก), text (ข้อความทั้งหมดที่เห็น)
4. brand_colors: สีหลักของแบรนด์ (2-4 สี)
5. logo: คำอธิบายโลโก้

Output ONLY valid JSON:
{
  "product_name": "",
  "bottle": {"shape": "", "material": "", "cap_type": "", "primary_color": ""},
  "label": {"colors": [], "text": []},
  "brand_colors": [],
  "logo": "",
  "packaging_type": ""
}"""
    response = _call_gemini(system_prompt=prompt_text, user_text="วิเคราะห์รูปภาพสินค้า", image_base64=image_base64)
    return _parse_json(response)


def analyze_product(
    product_name: str,
    description: str,
    category: str = "",
    target_audience: str = "",
    image_url: Optional[str] = None,
    image_base64: Optional[str] = None,
) -> dict:
    """Analyze product via Gemini — returns image_prompts, video_prompt, hooks, copy"""
    research = research_product(product_name, description, category, image_base64)

    brand_protocol = {}
    if image_base64:
        try:
            brand_protocol = extract_brand_protocol(image_base64)
        except Exception:
            brand_protocol = {}

    system_prompt = f"""# บทบาท
คุณคือผู้เชี่ยวชาญด้านการถ่ายภาพสินค้า AI และ Creative Director

# BRAND IDENTITY PROTOCOL
{json.dumps(brand_protocol, ensure_ascii=False, indent=2) if brand_protocol else 'วิเคราะห์จากรูปภาพสินค้า'}

# ข้อกำหนด
1. สินค้าต้องเป็น HERO คมชัด มีแสงที่ดี
2. พื้นหลังสวยงาม แสงธรรมชาติ โทนอบอุ่น สไตล์ไทย
3. ไม่มีมือ ไม่มีคน ไม่มีบุคคล — ถ่ายบนพื้นผิวเรียบเท่านั้น
4. ห้ามระบุสี โลโก้ ข้อความ บนสินค้า — ให้บอกว่า "blank placeholder"

# ต้องการ Image Prompts 5 รูป:
{json.dumps([s["id"] for s in PRESET_IMAGE_STYLES], ensure_ascii=False)}

# Video Prompt:
- Camera movement, 15-25 วินาที, 9:16
- การแสดงสินค้า ภาษาไทย

# ข้อความการตลาด:
- ภาษาไทยทั้งหมด
- 3 hooks, 1 marketing copy, hashtags

Research Context:
{json.dumps(research, ensure_ascii=False, indent=2)}

Output ONLY valid JSON:
{{
  "image_prompts": [
    {{"id": "holding_product", "name": "ถือสินค้า", "prompt": "...", "bbox": {{"x": 0, "y": 0, "width": 0, "height": 0, "angle": 0}}}},
    {{"id": "product_usage", "name": "ใช้งานสินค้า", "prompt": "...", "bbox": {{"x": 0, "y": 0, "width": 0, "height": 0, "angle": 0}}}},
    {{"id": "lifestyle", "name": "ไลฟ์สไตล์", "prompt": "...", "bbox": {{"x": 0, "y": 0, "width": 0, "height": 0, "angle": 0}}}},
    {{"id": "close_up", "name": "ซูมระยะใกล้", "prompt": "...", "bbox": {{"x": 0, "y": 0, "width": 0, "height": 0, "angle": 0}}}},
    {{"id": "review_style", "name": "รีวิว", "prompt": "...", "bbox": {{"x": 0, "y": 0, "width": 0, "height": 0, "angle": 0}}}}
  ],
  "video_prompt": {{"description": "...", "movement": [], "lighting": "...", "storytelling": "..."}},
  "hook_suggestions": ["...", "...", "..."],
  "marketing_copy": "...",
  "hashtags": ["...", "..."]
}}"""

    has_vision = bool(image_base64)
    user_prompt = f"""{'วิเคราะห์จากรูปสินค้าที่แนบมา' if has_vision else 'จากข้อมูลสินค้าต่อไปนี้'}:
Product Name: {product_name}
Description: {description}
Category: {category or 'N/A'}
Target Audience: {target_audience or 'General TikTok users'}

**Research Results:**
{json.dumps(research, ensure_ascii=False, indent=2)}
"""

    if image_url and not image_base64:
        user_prompt += f"\nProduct Image URL: {image_url}"

    try:
        raw = _call_gemini(
            system_prompt=system_prompt,
            user_text=user_prompt,
            image_base64=image_base64,
        )
        result = _parse_json(raw)
        logger.info(f"Gemini analysis successful ({'Vision' if has_vision else 'Text'})")
        return result
    except Exception as e:
        logger.warning(f"Gemini failed, using fallback: {e}")
        return _fallback_analysis(product_name, description, category)


def _placeholder_term_for_category(category: str = "") -> str:
    cat = (category or "").lower()
    if any(kw in cat for kw in ["cream", "moisturizer", "lotion", "serum", "oil", "toner", "essence", "ampoule"]):
        return "a blank minimal bottle (no labels, no text)"
    if any(kw in cat for kw in ["powder", "compact", "blush", "foundation", "palette", "eyeshadow"]):
        return "a blank minimal compact case (no labels)"
    if any(kw in cat for kw in ["lip", "lipstick", "lip gloss"]):
        return "a blank minimal lipstick tube (no labels)"
    if any(kw in cat for kw in ["face wash", "cleanser", "shampoo", "body wash", "sunscreen"]):
        return "a blank minimal squeeze tube (no labels)"
    if any(kw in cat for kw in ["supplement", "vitamin", "pill", "capsule", "powder", "collagen"]):
        return "a blank minimal sachet pouch (no labels)"
    if any(kw in cat for kw in ["perfume", "cologne", "fragrance", "spray", "mist"]):
        return "a blank minimal bottle with spray nozzle (no labels)"
    if any(kw in cat for kw in ["phone", "smartphone", "tablet"]):
        return "a hand holding a blank minimal smartphone (no screen content, no labels)"
    if any(kw in cat for kw in ["power bank", "charger", "battery"]):
        return "a hand holding a blank minimal power bank (rectangular, no labels)"
    if any(kw in cat for kw in ["earphone", "headphone", "earbuds"]):
        return "a hand holding blank minimal wireless earbuds (no labels)"
    if any(kw in cat for kw in ["watch", "smartwatch"]):
        return "a wrist wearing a blank minimal smartwatch (no screen content, no labels)"
    return "a blank minimal container (no text, no labels, no branding)"


def generate_image_prompt(brand_protocol: dict, creative_brief: dict, product_name: str, description: str) -> dict:
    """Generate ONLY image prompts (5 styles) using Gemini"""
    prompt_text = f"""Based on this Brand Protocol and Creative Brief, generate 5 detailed image prompts.

Brand Protocol: {json.dumps(brand_protocol, ensure_ascii=False, indent=2)}
Creative Brief: {json.dumps(creative_brief, ensure_ascii=False, indent=2)}
Product Name: {product_name}

Generate 5 prompts for these styles: holding_product, product_usage, lifestyle, close_up, review_style
Each prompt: CLEAN SURFACE, blank container, NO hands/people, warm Thai-style, soft lighting.

Output:
{{
  "image_prompts": [
    {{"id": "holding_product", "prompt": "..."}},
    {{"id": "product_usage", "prompt": "..."}},
    {{"id": "lifestyle", "prompt": "..."}},
    {{"id": "close_up", "prompt": "..."}},
    {{"id": "review_style", "prompt": "..."}}
  ]
}}"""
    return _parse_json(_call_gemini(system_prompt="You are an expert AI image prompt engineer.", user_text=prompt_text))


def generate_video_prompt(brand_protocol: dict, creative_brief: dict, product_name: str) -> str:
    """Generate video prompt using Gemini"""
    prompt_text = f"""Generate a video prompt for this product.

Brand Protocol: {json.dumps(brand_protocol, ensure_ascii=False, indent=2)}
Creative Brief: {json.dumps(creative_brief, ensure_ascii=False, indent=2)}
Product Name: {product_name}

Requirements: cinematic motion, pan/zoom/tilt, product interaction,
15-25 seconds, 9:16 vertical, consistent with Brand Protocol.

Output ONLY the video prompt as a single paragraph:"""
    return _call_gemini(system_prompt="You are an expert video director. Generate video prompts.", user_text=prompt_text)


def _fallback_analysis(product_name: str, description: str, category: str) -> dict:
    image_prompts = []
    for style in PRESET_IMAGE_STYLES:
        image_prompts.append({
            "id": style["id"],
            "name": style["name"],
            "bbox": {"x": 0, "y": 0, "width": 0, "height": 0, "angle": 0},
            "prompt": f"ภาพถ่ายสินค้า {product_name} ในสไตล์ {style['name']} วางบนพื้นผิวเรียบสวยงาม แสงธรรมชาติ โทนอบอุ่น สไตล์ไทย",
        })

    return {
        "image_prompts": image_prompts,
        "video_prompt": f"วิดีโอรีวิวสินค้า {product_name} แสดงการใช้งานจริงในสถานที่แบบไทย แสงธรรมชาติ โทนอบอุ่น",
        "hook_suggestions": [
            f"กำลังมองหาสินค้าแบบนี้อยู่เหรอ?",
            f"สินค้า {product_name} แบบนี้หายากเลย!",
            f"อยากได้ของดีๆ แบบนี้ต้องรีบจัดไปเลย",
        ],
        "marketing_copy": f"รีวิวสินค้า {product_name} ที่คุณต้องรู้! {description[:100]}",
        "hashtags": ["#" + product_name.replace(" ", ""), "#รีวิวสินค้า", "#TikTokUGC", "#แนะนำสินค้า"],
    }


def research_product(product_name, description='', category='', image_base64=None):
    """Research product via Gemini Vision analysis"""
    has_vision = bool(image_base64)
    user_prompt = f'Analyze this product:\nProduct Name: {product_name}\nDescription: {description or "N/A"}\nCategory: {category or "N/A"}'
    if has_vision:
        user_prompt += '\n\n(Product image attached)'
    try:
        raw = _call_gemini(
            system_prompt=RESEARCH_SYSTEM_PROMPT,
            user_text=user_prompt,
            image_base64=image_base64,
        )
        result = _parse_json(raw)
        logger.info(f'Gemini research successful for "{product_name}"')
        return result
    except Exception as e:
        logger.warning(f'Gemini research failed: {e}')
        return {
            'product_type': category or 'unknown',
            'material': '',
            'category': category or 'general',
            'target_audience': 'General consumers',
            'key_features': [],
            'visual_style_recommendation': 'lifestyle',
            'age_group': '20-35',
            'gender': 'neutral',
            'environment': 'modern lifestyle setting',
            'pain_points': [],
            'hooking_angle': f'Highlight benefits of {product_name}',
        }
