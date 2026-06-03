"""
Gemini Product Analyzer — AI-powered product analysis + prompt generation
Uses Google Gemini API to analyze product images/descriptions and generate
TikTok UGC image prompts, video prompts, and marketing copy.
"""

import os
import json
import logging
import requests
from typing import Optional

logger = logging.getLogger("gemini-agent")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# ─── Template prompts ─────────────────────────────────────────────────────

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


def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    """Call Gemini API with system + user prompts"""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not configured")

    payload = {
        "contents": [{
            "parts": [{"text": f"{system_prompt}\n\n---\n\n{user_prompt}"}],
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        },
    }

    resp = requests.post(
        f"{GEMINI_URL}?key={GEMINI_API_KEY}",
        json=payload,
        timeout=60,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"Gemini error ({resp.status_code}): {resp.text[:300]}")

    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"Gemini returned no candidates: {data}")

    text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return text


def analyze_product(
    product_name: str,
    description: str,
    category: str = "",
    target_audience: str = "",
    image_url: Optional[str] = None,
) -> dict:
    """
    Analyze product via Gemini and return:
      - image_prompts: list of 5 preset prompts with AI-generated details
      - video_prompt: full video script prompt
      - hook_suggestions: list of hook ideas
      - marketing_copy: short caption + hashtags
    """

    system_prompt = """You are a TikTok UGC marketing expert. Analyze the product and generate:
1. **5 Image Prompts** (for Fal.ai / Stable Diffusion) — each tailored to a different visual style, include product details
2. **1 Video Prompt** — a detailed scene description for AI video generation (WaveSpeed), include movement, lighting, and storytelling
3. **3 Hook Ideas** — attention-grabbing first lines for TikTok
4. **Marketing Copy** — short caption + 5-8 relevant hashtags

IMPORTANT: Output ONLY valid JSON, no markdown fences, no extra text.
Format:
{
  "image_prompts": [
    {"id": "holding_product", "name": "ถือสินค้า", "prompt": "..."},
    {"id": "product_usage", "name": "ใช้งานสินค้า", "prompt": "..."},
    {"id": "lifestyle", "name": "ไลฟ์สไตล์", "prompt": "..."},
    {"id": "close_up", "name": "Close-up", "prompt": "..."},
    {"id": "review_style", "name": "รีวิว", "prompt": "..."}
  ],
  "video_prompt": "...",
  "hook_suggestions": ["...", "...", "..."],
  "marketing_copy": "...",
  "hashtags": ["...", "..."]
}"""

    user_prompt = f"""Product Name: {product_name}
Description: {description}
Category: {category or 'N/A'}
Target Audience: {target_audience or 'General TikTok users'}
"""

    if image_url:
        user_prompt += f"\nProduct Image URL: {image_url}"

    try:
        raw = _call_gemini(system_prompt, user_prompt)
        # Clean potential markdown fences
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        result = json.loads(raw)
    except Exception as e:
        logger.warning(f"Gemini parse failed, using fallback: {e}")
        result = _fallback_analysis(product_name, description, category)

    return result


def _fallback_analysis(product_name: str, description: str, category: str) -> dict:
    """Fallback product analysis when Gemini fails"""
    image_prompts = []
    for style in PRESET_IMAGE_STYLES:
        image_prompts.append({
            "id": style["id"],
            "name": style["name"],
            "prompt": f"{product_name} — {description[:100]} {style['suffix']}",
        })

    return {
        "image_prompts": image_prompts,
        "video_prompt": f"Product showcase video for {product_name}: {description[:200]}. "
                        f"Natural handheld camera movement, authentic lighting, "
                        f"person holding and demonstrating the product, smiling at camera.",
        "hook_suggestions": [
            f"คุณกำลังเจอปัญหานี้อยู่ใช่ไหม?",
            f"เจอ {product_name} ดีๆ แบบนี้ต้องบอกต่อ!",
            f"ก่อนจะเสียเงินลองอันอื่น มาดูอันนี้ก่อน",
        ],
        "marketing_copy": f"Review ของ {product_name} ที่คุณต้องดู! {description[:100]}",
        "hashtags": ["#" + product_name.replace(" ", ""), "#review", "#TikTokUGC", "#unboxing", "#recommended"],
    }


def analyze_product_with_image(
    product_name: str,
    description: str,
    image_base64: str,
    category: str = "",
    target_audience: str = "",
) -> dict:
    """
    Analyze product WITH image content (base64) using Gemini Vision.
    Useful when we have the actual product image bytes.
    """
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not configured")

    system_text = """You are a TikTok UGC marketing expert. Analyze this product image and details, then generate:
1. **5 Image Prompts** — tailored visual prompts for AI image generation (Fal.ai)
2. **1 Video Prompt** — detailed scene for AI video (WaveSpeed) 
3. **3 Hook Ideas** — TikTok hooks
4. **Marketing Copy** — caption + hashtags

Output ONLY valid JSON (no markdown fences):
{
  "image_prompts": [{"id": "holding_product", "name": "ถือสินค้า", "prompt": "..."}, ...],
  "video_prompt": "...",
  "hook_suggestions": ["...", "...", "..."],
  "marketing_copy": "...",
  "hashtags": ["...", "..."]
}"""

    user_text = f"""Product Name: {product_name}
Description: {description}
Category: {category or 'N/A'}
Target Audience: {target_audience or 'General TikTok users'}
"""

    payload = {
        "contents": [{
            "parts": [
                {"text": f"{system_text}\n\n---\n\n{user_text}"},
                {"inline_data": {"mime_type": "image/jpeg", "data": image_base64}},
            ],
        }],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        },
    }

    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json=payload,
            timeout=120,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini vision error ({resp.status_code}): {resp.text[:300]}")

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("No candidates from Gemini vision")

        raw = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()

        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Gemini vision failed, using text fallback: {e}")
        return _fallback_analysis(product_name, description, category)
