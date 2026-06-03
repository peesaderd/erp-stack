"""
Product Analyzer — uses Mistral API for AI product analysis + prompt generation
Provides image prompts, video prompts, hooks, and marketing copy.
"""

import os
import json
import logging
import requests
from typing import Optional, Any

logger = logging.getLogger("product-analyzer")

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_MODEL = "mistral-small-latest"
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

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


def _call_mistral(system_prompt: str, user_prompt: str) -> str:
    """Call Mistral API with system + user prompts"""
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY not configured")

    payload: dict[str, Any] = {
        "model": MISTRAL_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 2048,
    }

    resp = requests.post(
        MISTRAL_URL,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
        },
        json=payload,
        timeout=60,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"Mistral error ({resp.status_code}): {resp.text[:300]}")

    data = resp.json()
    return data["choices"][0]["message"]["content"]


def analyze_product(
    product_name: str,
    description: str,
    category: str = "",
    target_audience: str = "",
    image_url: Optional[str] = None,
) -> dict:
    """Analyze product via AI and return image_prompts, video_prompt, hooks, copy"""

    system_prompt = """You are a TikTok UGC marketing expert. Analyze the product and generate:
1. **5 Image Prompts** (for Fal.ai / Stable Diffusion)
2. **1 Video Prompt** (for WaveSpeed video generation)
3. **3 Hook Ideas** in Thai
4. **Marketing Copy** + hashtags

Output ONLY valid JSON, no markdown fences:
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
        raw = _call_mistral(system_prompt, user_prompt)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
        raw = raw.strip()
        result = json.loads(raw)
        logger.info("AI analysis successful (Mistral)")
        return result
    except Exception as e:
        logger.warning(f"AI failed, using fallback: {e}")
        return _fallback_analysis(product_name, description, category)


def _fallback_analysis(product_name: str, description: str, category: str) -> dict:
    """Fallback analysis when AI fails"""
    image_prompts = []
    for style in PRESET_IMAGE_STYLES:
        image_prompts.append({
            "id": style["id"],
            "name": style["name"],
            "prompt": f"{product_name} — {description[:100]} {style['suffix']}",
        })

    return {
        "image_prompts": image_prompts,
        "video_prompt": f"Product showcase for {product_name}: {description[:200]}. "
                        f"Natural handheld camera, authentic lighting, "
                        f"person holding and demonstrating product.",
        "hook_suggestions": [
            f"คุณกำลังเจอปัญหานี้อยู่ใช่ไหม?",
            f"เจอ {product_name} ดีๆ แบบนี้ต้องบอกต่อ!",
            f"ก่อนจะเสียเงินลองอันอื่น มาดูอันนี้ก่อน",
        ],
        "marketing_copy": f"Review ของ {product_name} ที่คุณต้องดู! {description[:100]}",
        "hashtags": ["#" + product_name.replace(" ", ""), "#review", "#TikTokUGC", "#unboxing", "#recommended"],
    }
