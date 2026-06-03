"""
Product Analyzer — uses Mistral API for AI product analysis + prompt generation
Supports text-only (mistral-small) and vision (pixtral via base64 images)
"""

import os
import json
import logging
import requests
from typing import Optional, Any

logger = logging.getLogger("product-analyzer")

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
TEXT_MODEL = "mistral-small-latest"
VISION_MODEL = "pixtral-12b-2409"
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
RESEARCH_SYSTEM_PROMPT = '''You are a product research expert. Analyze the product image and information carefully.
Output ONLY valid JSON:
{
  "product_type": "what kind of product (e.g. wireless microphone, skincare cream, kitchen tool)",
  "material": "visible materials and finish",
  "category": "marketing category",
  "target_audience": "who would buy this, be specific",
  "key_features": ["feature 1", "feature 2"],
  "visual_style_recommendation": "recommended visual style",
  "age_group": "target age range",
  "gender": "male/female/neutral based on typical user",
  "environment": "recommended setting/background",
  "pain_points": ["problem 1", "problem 2"],
  "hooking_angle": "best marketing hook angle in Thai"
}'''

PRESET_IMAGE_STYLES = [
    {
        "id": "holding_product",
        "name": "ถือสินค้า",
        "description": "มือถือสินค้าในมุมที่เป็นธรรมชาติ",
        "suffix": "Holding the product naturally in hand, well-lit, realistic product photography style",
    },
    {
        "id": "product_usage",
        "name": "ใช้งานสินค้า",
        "description": "สาธิตการใช้งานจริง",
        "suffix": "Person using the product in a real-life setting, candid lifestyle shot, soft natural lighting",
    },
    {
        "id": "lifestyle",
        "name": "ไลฟ์สไตล์",
        "description": "สินค้าในชีวิตประจำวัน",
        "suffix": "Product integrated into everyday lifestyle scene, aesthetic composition, warm tones",
    },
    {
        "id": "close_up",
        "name": "Close-up",
        "description": "ถ่ายใกล้แสดงรายละเอียดสินค้า",
        "suffix": "Extreme close-up of product texture and details, macro photography, shallow depth of field",
    },
    {
        "id": "review_style",
        "name": "รีวิว",
        "description": "สไตล์รีวิว TikTok",
        "suffix": "Review-style setup, product on clean flat-lay or table, authentic lighting, social media aesthetic",
    },
]


def _call_mistral(
    system_prompt: str,
    user_text: str,
    image_base64: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Call Mistral API — text-only or vision (Pixtral with base64 image)

    Args:
        system_prompt: System instruction
        user_text: User message text
        image_base64: Optional base64-encoded image (triggers Pixtral)
        model: Model override (default: TEXT_MODEL, VISION_MODEL if image)
    """
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY not configured")

    use_model = model or (VISION_MODEL if image_base64 else TEXT_MODEL)

    # Build messages
    user_content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    if image_base64:
        # Ensure proper padding
        img = image_base64.strip()
        if ";" in img:  # data URI format
            # Already has mime prefix — pass as-is
            user_content.append({"type": "image_url", "image_url": {"url": img}})
        else:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img}"},
            })

    payload: dict[str, Any] = {
        "model": use_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.1,
        "max_tokens": 4096,
    }

    resp = requests.post(
        MISTRAL_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
        },
        json=payload,
        timeout=90,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"Mistral error ({resp.status_code}): {resp.text[:300]}")

    data = resp.json()
    return data["choices"][0]["message"]["content"]


def _parse_json(text: str) -> dict:
    """Parse JSON from AI response, handling markdown fences and common formatting issues"""
    import re
    raw = text.strip()
    # Strip markdown fences
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()
    # Replace literal newlines in JSON strings with spaces (Mistral/Pixtral often includes them)
    raw = raw.replace(chr(10), " ").replace(chr(13), " ")
    # Remove control characters (except \n, \r, \t)
    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw)
    # Fix unescaped newlines inside JSON strings: replace \n inside quotes with \\n
    # This is a common issue with Mistral/Pixtral
    in_string = False
    escaped = False
    result = []
    for ch in raw:
        if ch == '"' and not escaped:
            in_string = not in_string
            result.append(ch)
        elif ch == '\\' and not escaped:
            escaped = True
            result.append(ch)
        elif ch == '\n' and in_string:
            result.append('\\n')
            escaped = False
        elif ch == '\r' and in_string:
            result.append('\\r')
            escaped = False
        elif ch == '\t' and in_string:
            result.append('\\t')
            escaped = False
        else:
            if escaped:
                escaped = False
            result.append(ch)
    raw = ''.join(result)
    # Try parsing directly first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Try fixing common issues: trailing commas
    raw = re.sub(r',\s*}', '}', raw)
    raw = re.sub(r',\s*]', ']', raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Try removing single-line comments (// style)
    raw = re.sub(r'//[^\n]*', '', raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # If still fails, try extracting JSON-like content with regex
    match = re.search(r'\{[^{}]*"image_prompts"[^{}]*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    # Final attempt: find outermost balanced braces
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
    # Show what we're trying to parse (just the first/last bits)
    # Try to fix the JSON by removing extra closing brackets
    import re as _re
    
    # Try 1: If brackets are unbalanced, remove extra closing brackets from end
    _open_arr = raw.count('[')
    _close_arr = raw.count(']')
    if _close_arr > _open_arr and _open_arr > 0:
        # Find all positions of ] and only keep the rightmost ones
        _parts = list(raw)
        _to_remove = _close_arr - _open_arr
        _removed = 0
        _i = len(_parts) - 1
        while _removed < _to_remove and _i >= 0:
            if _parts[_i] == ']':
                _parts[_i] = ''
                _removed += 1
            _i -= 1
        raw = ''.join(_parts)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    
    # Try 2: Try fixing trailing commas after removing newlines
    raw = raw.replace(chr(10), " ").replace(chr(13), " ")
    raw = _re.sub(r',\s*}', '}', raw)
    raw = _re.sub(r',\s*]', ']', raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    
    raise ValueError("Cannot parse JSON from response")


def analyze_product(
    product_name: str,
    description: str,
    category: str = "",
    target_audience: str = "",
    image_url: Optional[str] = None,
    image_base64: Optional[str] = None,
) -> dict:
    """Analyze product via AI — returns image_prompts, video_prompt, hooks, copy

    Step 1: Research product
    Step 2: Generate prompts based on research

    Uses Pixtral vision if image_base64 provided, else text-only Mistral.
    Falls back to template analysis on any error.
    """
    research = research_product(product_name, description, category, image_base64)


    system_prompt = f"""You are a TikTok UGC marketing expert. Analyze the product image and generate content in THAI language only.

REQUIREMENTS:

1. **5 Image Prompts** — Describe each scene in full detail for AI image generation:
   - styles: holding_product, product_usage, lifestyle, close_up, review_style
   - Describe product APPEARANCE from what you see: color, shape, material, packaging, labels, texture
   - MUST specify Thai/SE Asian model (young Thai woman, light brown skin, Southeast Asian features, natural look)
   - Use warm Thai-style setting, natural lighting, pastel or soft tones

2. **1 Video Prompt** — output as JSON object with keys: description, movement, lighting, storytelling for video generation

3. **3 Hook Ideas** — attention-grabbing opening lines in THAI language (product-specific, NOT generic)

4. **Marketing Copy** — short THAI caption + CTA + hashtags in THAI

IMPORTANT: All text content MUST be in THAI language, EXCEPT the prompt fields (which describe visual scenes for English AI image generators).

Research Context:
{json.dumps(research, ensure_ascii=False, indent=2)}

Output ONLY valid JSON. No markdown fences. No trailing commas. No newlines inside JSON strings. Escape all double quotes inside strings with backslash. No control characters in strings:
{{
  "image_prompts": [
    {{"id": "holding_product", "name": "ถือสินค้า", "prompt": "..."}},
    {{"id": "product_usage", "name": "ใช้งานสินค้า", "prompt": "..."}},
    {{"id": "lifestyle", "name": "ไลฟ์สไตล์", "prompt": "..."}},
    {{"id": "close_up", "name": "ซูมระยะใกล้", "prompt": "..."}},
    {{"id": "review_style", "name": "รีวิว", "prompt": "..."}}
  ],
  "video_prompt": {{
    "description": "...",
    "movement": [...],
    "lighting": "...",
    "storytelling": "..."
  }},
  "hook_suggestions": ["...", "...", "..."],
  "marketing_copy": "...",
  "hashtags": ["...", "..."]
}}"""

    has_vision = bool(image_base64)
    model_hint = " (with product image for visual analysis)" if has_vision else ""

    user_prompt = f"""{'วิเคราะห์จากรูปสินค้าที่แนบมาและข้อมูลต่อไปนี้ (สินค้าที่เห็นในภาพ: สี รูปร่าง วัสดุ รายละเอียด)' if has_vision else 'จากข้อมูลสินค้าต่อไปนี้'}:
Product Name: {product_name}
Description: {description}
Category: {category or 'N/A'}
Target Audience: {target_audience or 'General TikTok users'}{model_hint}

{'สินค้าในภาพมีสี [ระบุสี] รูปร่าง [ระบุรูปร่าง] วัสดุ [ระบุวัสดุ] และรายละเอียดอื่นๆ ที่เห็น' if has_vision else ''}

**Research Results:**
{json.dumps(research, ensure_ascii=False, indent=2)}
"""

    if image_url and not image_base64:
        user_prompt += f"\nProduct Image URL: {image_url}"

    try:
        raw = _call_mistral(
            system_prompt=system_prompt,
            user_text=user_prompt,
            image_base64=image_base64,
        )

        result = _parse_json(raw)
        logger.info(
            f"AI analysis successful ({'Pixtral vision' if has_vision else 'Mistral text'})"
        )
        return result
    except Exception as e:
        logger.warning(f"AI failed, using fallback: {e}")
        return _fallback_analysis(product_name, description, category)


def _fallback_analysis(product_name: str, description: str, category: str) -> dict:
    """Fallback analysis when AI fails - generate Thai content with product appearance"""
    image_prompts = []
    for style in PRESET_IMAGE_STYLES:
        image_prompts.append({
            "id": style["id"],
            "name": style["name"],
            "prompt": f"ภาพถ่ายสินค้า {product_name} ในสไตล์ {style['name']} แสดงรายละเอียดสี รูปร่าง วัสดุ และบรรจุภัณฑ์อย่างชัดเจน เหมาะสำหรับการรีวิวสินค้า",
        })

    return {
        "image_prompts": image_prompts,
        "video_prompt": (
            f"วิดีโอรีวิวสินค้า {product_name} แสดงการใช้งานจริงในสถานที่แบบไทย "
            f"โดยคนไทยผิวสีอ่อน ถือและสาธิตการใช้งานสินค้า "
            f"ด้วยแสงสว่างธรรมชาติและโทนสีอบอุ่น"
        ),
        "hook_suggestions": [
            f"กำลังมองหาสินค้าแบบนี้อยู่เหรอ?",
            f"สินค้า {product_name} แบบนี้หายากเลย!",
            f"อยากได้ของดีๆ แบบนี้ต้องรีบจัดไปเลย",
        ],
        "marketing_copy": f"รีวิวสินค้า {product_name} ที่คุณต้องรู้! {description[:100]}",
        "hashtags": [
            "#" + product_name.replace(" ", ""),
            "#รีวิวสินค้า",
            "#TikTokUGC",
            "#รีวิว",
            "#แนะนำสินค้า",
        ],
    }
def research_product(product_name, description='', category='', image_base64=None):
    """Step 1: Research product via AI vision analysis — returns structured dict"""
    has_vision = bool(image_base64)
    user_prompt = f'Analyze this product:\nProduct Name: {product_name}\nDescription: {description or "N/A"}\nCategory: {category or "N/A"}'
    if has_vision:
        user_prompt += '\n\n(Product image attached)'
    try:
        raw = _call_mistral(
            system_prompt=RESEARCH_SYSTEM_PROMPT,
            user_text=user_prompt,
            image_base64=image_base64,
        )
        result = _parse_json(raw)
        logger.info(f'Product research successful for "{product_name}"')
        return result
    except Exception as e:
        logger.warning(f'Product research failed: {e}')
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
            'hooking_angle': f'Highlight benefits of {product_name}'
        }
