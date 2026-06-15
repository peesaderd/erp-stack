"""
TikTok UGC Studio — Image Prompt Builder
วิเคราะห์สินค้า + UGC Style → สร้าง Image Prompt ที่ Dynamic
"""

import os
import json
import logging
import httpx
from typing import Optional, Dict, Any
from fastapi import HTTPException

logger = logging.getLogger("tiktok-ugc.image_prompt_builder")

# ─── UGC Style → Image Style Mapping ─────────────────────────────────────

STYLE_MAP = {
    "holding": {
        "model_action": "holding the product in both hands, product packaging facing camera, smiling naturally",
        "camera": "mid shot, waist up, product visible at chest level",
        "vibe": "friendly, approachable, product-focused",
        "keywords": "both hands holding product, product clearly visible and in focus",
    },
    "usage": {
        "model_action": "actively using the product in a natural daily setting, candid moment, product in use",
        "camera": "medium shot showing product usage context, slightly zoomed for action",
        "vibe": "authentic, lifestyle, in-the-moment",
        "keywords": "product in use, daily routine, natural hands-on moment",
    },
    "review": {
        "model_action": "holding product up showing packaging to camera, excited expression, like unboxing reaction",
        "camera": "close up to mid shot, product front and center, model slightly off-center",
        "vibe": "enthusiastic, honest, review energy",
        "keywords": "product held up, packaging visible, model reacting to product",
    },
    "talking": {
        "model_action": "talking while casually holding product, relaxed hand gesture, product naturally present",
        "camera": "close up, talking head style, product in lower frame",
        "vibe": "conversational, vlog-style, personal",
        "keywords": "talking head, casually holding, natural conversation pose",
    },
}

# ─── Product Category Analyzer ───────────────────────────────────────────

PRODUCT_CATEGORY_MAP = {
    # Beauty / Cosmetics
    "ลิปสติก": {"category": "beauty", "gender": "female", "age": "18-30", "setting": "vanity room or bedroom with mirror"},
    "ลิป": {"category": "beauty", "gender": "female", "age": "18-30", "setting": "vanity room or bedroom with mirror"},
    "ครีม": {"category": "beauty", "gender": "female", "age": "25-40", "setting": "bathroom or bedroom vanity"},
    "เซรั่ม": {"category": "beauty", "gender": "female", "age": "25-40", "setting": "bathroom vanity, clean white background"},
    "กันแดด": {"category": "beauty", "gender": "unisex", "age": "18-40", "setting": "outdoor or near window, natural light"},
    "สกินแคร์": {"category": "beauty", "gender": "female", "age": "20-35", "setting": "bedroom vanity, soft natural lighting"},
    "เครื่องสำอาง": {"category": "beauty", "gender": "female", "age": "18-30", "setting": "vanity table with makeup mirror"},
    "แป้ง": {"category": "beauty", "gender": "female", "age": "18-30", "setting": "modern vanity, clean bright space"},
    "น้ำหอม": {"category": "beauty", "gender": "unisex", "age": "20-40", "setting": "elegant setting, soft mood lighting"},
    
    # Tools / Hardware
    "ไขควง": {"category": "tools", "gender": "male", "age": "25-50", "setting": "workshop or garage, tool bench background"},
    "ค้อน": {"category": "tools", "gender": "male", "age": "25-50", "setting": "workshop with tool wall"},
    "ประแจ": {"category": "tools", "gender": "male", "age": "25-50", "setting": "garage or workshop, industrial background"},
    "สว่าน": {"category": "tools", "gender": "male", "age": "25-45", "setting": "workshop, professional tool wall"},
    "เครื่องมือ": {"category": "tools", "gender": "male", "age": "25-50", "setting": "workshop background with tool rack"},
    
    # Electronics / Tech
    "หูฟัง": {"category": "electronics", "gender": "unisex", "age": "18-30", "setting": "modern room, desk with tech accessories"},
    "ลำโพง": {"category": "electronics", "gender": "unisex", "age": "20-40", "setting": "living room or desk, modern decor"},
    "สายชาร์จ": {"category": "electronics", "gender": "unisex", "age": "18-40", "setting": "desk setup, clean modern background"},
    "เคสโทรศัพท์": {"category": "electronics", "gender": "unisex", "age": "18-35", "setting": "desk, modern lifestyle background"},
    "แกดเจ็ต": {"category": "electronics", "gender": "unisex", "age": "18-35", "setting": "clean tech desk setup, modern interior"},
    
    # Food / Snacks
    "ขนม": {"category": "food", "gender": "unisex", "age": "18-35", "setting": "kitchen table or cafe, natural lighting"},
    "เครื่องดื่ม": {"category": "food", "gender": "unisex", "age": "18-40", "setting": "cafe corner or modern kitchen"},
    "ชา": {"category": "food", "gender": "unisex", "age": "20-45", "setting": "warm cozy corner, tea table setting"},
    "กาแฟ": {"category": "food", "gender": "unisex", "age": "22-40", "setting": "cafe-style or home coffee corner"},
    "อาหาร": {"category": "food", "gender": "unisex", "age": "20-45", "setting": "dining table, warm ambient lighting"},
    
    # Fashion
    "เสื้อผ้า": {"category": "fashion", "gender": "unisex", "age": "18-35", "setting": "modern wardrobe, clean background"},
    "รองเท้า": {"category": "fashion", "gender": "unisex", "age": "18-35", "setting": "streetwear style, urban background"},
    "กระเป๋า": {"category": "fashion", "gender": "unisex", "age": "20-35", "setting": "modern lifestyle setting, clean and bright"},
    "เครื่องประดับ": {"category": "fashion", "gender": "female", "age": "20-35", "setting": "elegant setting, soft lighting, mirror"},
    
    # Home / Living
    "ของใช้ในบ้าน": {"category": "home", "gender": "unisex", "age": "25-50", "setting": "bright living room or kitchen"},
    "ทำความสะอาด": {"category": "home", "gender": "unisex", "age": "25-50", "setting": "kitchen or bathroom, bright and clean"},
    "เฟอร์นิเจอร์": {"category": "home", "gender": "unisex", "age": "25-50", "setting": "bright modern room display"},
}

# ─── Lighting & Composition by Category ──────────────────────────────────

LIGHTING_MAP = {
    "beauty": {
        "lighting": "soft diffused natural window lighting, warm and gentle",
        "composition": "model centered or slightly off-center, eye-level angle",
        "background": "clean minimal background, soft pastel tones or white",
        "color_palette": "warm pastels, pink tones, natural skin tones",
        "atmosphere": "warm, inviting, feminine, premium",
    },
    "tools": {
        "lighting": "bright functional lighting, cool to neutral white balance",
        "composition": "model holding tool in working posture, slightly low angle for strength",
        "background": "workshop wall with tool rack or pegboard",
        "color_palette": "neutral grays, blue tones, wood workshop tones",
        "atmosphere": "practical, sturdy, professional",
    },
    "electronics": {
        "lighting": "clean bright studio lighting with soft shadows",
        "composition": "model holding device at chest level, tech-focused framing",
        "background": "modern minimalist room, blurred ambient background",
        "color_palette": "cool whites, blue-grays, tech blue accent",
        "atmosphere": "modern, sleek, innovative",
    },
    "food": {
        "lighting": "warm golden hour lighting, natural and appetizing",
        "composition": "close up of product and model's hands, upper body shot",
        "background": "cafe, kitchen counter, blurred warm background",
        "color_palette": "warm amber, creamy beige, natural green accents",
        "atmosphere": "cozy, appetizing, lifestyle",
    },
    "fashion": {
        "lighting": "bright studio lighting, fashion editorial style",
        "composition": "full body or 3/4 shot, dynamic pose",
        "background": "modern clean background, studio or urban setting",
        "color_palette": "neutral fashion tones, monochrome or bold accent",
        "atmosphere": "stylish, trendy, confident",
    },
    "home": {
        "lighting": "bright natural daylight, clean and fresh",
        "composition": "medium shot showing product in home context",
        "background": "bright clean living space, lifestyle setting",
        "color_palette": "clean whites, wood tones, natural greens",
        "atmosphere": "clean, organized, practical",
    },
    "other": {
        "lighting": "soft natural lighting, clean and professional",
        "composition": "upper body shot, product visible and in focus",
        "background": "clean minimal background, lifestyle appropriate",
        "color_palette": "natural tones, neutral background",
        "atmosphere": "authentic, professional, relatable",
    },
}


def _match_category(product_name: str, description: str = "") -> dict:
    """Match product to a category based on name keywords."""
    combined = (product_name + " " + description).lower()
    
    # Default fallback
    best_match = {"category": "other", "gender": "unisex", "age": "20-35",
                  "setting": "clean modern lifestyle setting"}
    
    # Try to match by keyword
    for keyword, info in PRODUCT_CATEGORY_MAP.items():
        if keyword.lower() in combined:
            if info["category"] != "other":
                return info
            best_match = info
    
    # Return the best match found (or fallback)
    return best_match


def _get_lighting(category: str) -> dict:
    """Get lighting and composition guidance for a category."""
    return LIGHTING_MAP.get(category, LIGHTING_MAP["other"])


def build_prompt(
    product_name: str,
    description: str = "",
    ugc_style: str = "holding",
    mistral_analysis: Optional[dict] = None
) -> dict:
    """
    Main function — build a complete image generation prompt.
    
    Args:
        product_name: ชื่อสินค้า
        description: รายละเอียดสินค้า
        ugc_style: holding / usage / review / talking
        mistral_analysis: output from /product/analyze (optional)
    
    Returns:
        dict with prompt, negative_prompt, aspect_ratio, model_info
    """
    
    # 1. วิเคราะห์สินค้า
    category_info = _match_category(product_name, description)
    category = category_info["category"]
    
    # 2. กำหนด model spec
    model_gender = category_info["gender"]
    model_age = category_info["age"]
    model_setting = category_info["setting"]
    
    # 3. กำหนด lighting
    lighting = _get_lighting(category)
    
    # 4. UGC Style action
    style_info = STYLE_MAP.get(ugc_style, STYLE_MAP["holding"])
    
    # 5. ใช้ Mistral analysis ถ้ามี
    prompt_text = ""
    if mistral_analysis and isinstance(mistral_analysis, dict):
        image_prompts = mistral_analysis.get("image_prompts", {})
        copy_text = mistral_analysis.get("copy", "")
        keywords = mistral_analysis.get("seo_keywords", [])
        
        # เลือก style prompt จาก Mistral
        style_key_map = {
            "holding": "holding_product",
            "usage": "product_usage",
            "review": "review_style",
            "talking": "lifestyle",
        }
        mistral_style_key = style_key_map.get(ugc_style, "holding_product")
        mistral_style_prompt = image_prompts.get(mistral_style_key, "")
        
        # สร้าง prompt
        if mistral_style_prompt:
            prompt_text = f"{mistral_style_prompt} A Thai {model_gender} model standing in the scene, {style_info['model_action']}, {model_age} years old, wearing casual everyday outfit appropriate for the Thai lifestyle setting. {style_info['camera']}, {style_info['vibe']}, {lighting['composition']}. {lighting['atmosphere']}, {lighting['color_palette']}. Product: {product_name}, {description}. {lighting['lighting']}. --ar 9:16"
        else:
            # Fallback — build from components
            prompt_text = _build_component_prompt(
                product_name, description, category_info, style_info, lighting
            )
    else:
        # Fallback — build from components
        prompt_text = _build_component_prompt(
            product_name, description, category_info, style_info, lighting
        )
    
    # 6. Negative prompt
    negative_prompt = _build_negative_prompt(category, model_gender)
    
    # 7. Build result
    return {
        "prompt": prompt_text,
        "negative_prompt": negative_prompt,
        "aspect_ratio": "9:16",
        "width": 576,
        "height": 1024,
        "model_gender": model_gender,
        "model_age": model_age,
        "model_setting": model_setting,
        "category": category,
        "ugc_style": ugc_style,
        "lighting": lighting["lighting"],
        "composition": lighting["composition"],
        "atmosphere": lighting["atmosphere"],
    }


def _build_component_prompt(
    product_name: str,
    description: str,
    category_info: dict,
    style_info: dict,
    lighting: dict,
) -> str:
    """Build prompt from components when Mistral analysis is not available."""
    model_gender = category_info["gender"]
    model_age = category_info["age"]
    setting = category_info["setting"]
    
    gender_th = "beautiful Thai woman" if model_gender == "female" else ("Thai man" if model_gender == "male" else "Thai person")
    
    prompt = (
        f"A {gender_th}, {model_age} years old, "
        f"glowing skin, pretty face, professional model quality, "
        f"influencer-quality, high-end e-commerce photography, "
        f"{style_info['model_action']}. "
        f"Setting: {setting}. "
        f"{style_info['camera']}, {style_info['vibe']}. "
        f"{lighting['composition']}, {lighting['atmosphere']}, {lighting['color_palette']}. "
        f"The {product_name} is clearly in frame, held by the model, {description}. "
        f"{lighting['lighting']}. "
        f"Wearing casual everyday outfit appropriate for the scene. "
        f"Professional e-commerce quality, high detail, realistic skin texture. "
        f"--ar 9:16"
    )
    
    return prompt


def _build_negative_prompt(category: str, model_gender: str) -> str:
    """Build negative prompt based on category and gender."""
    parts = [
        "no text, no watermark, no logo, no UI overlay",
        "no blurred face, no distorted hands, no extra fingers",
        "no manga, no cartoon, no illustration, no 3D render",
        "no low resolution, no pixelation, no artifacts",
        "no cluttered background, no messy room",
    ]
    
    if model_gender == "female":
        parts.append("no male models, no men in frame")
    elif model_gender == "male":
        parts.append("no female models, no women in frame")
    
    if category == "beauty":
        parts.append("no dirty or messy background, no harsh shadows")
    elif category == "tools":
        parts.append("no pink or pastel colors, no feminine decor")
    elif category == "food":
        parts.append("no raw ingredients visible in background")
    
    return ", ".join(parts)


# ─── API Endpoint Wrapper ────────────────────────────────────────────────

async def process_image_prompt_request(
    product_name: str,
    description: str = "",
    ugc_style: str = "holding",
    use_mistral: bool = True
) -> dict:
    """
    Full pipeline: analyze product → build prompt
    
    This is the main function called by the FastAPI endpoint.
    """
    mistral_analysis = None
    
    # Optionally call Mistral for deep analysis
    if use_mistral:
        try:
            mistral_api_key = os.environ.get("MISTRAL_API_KEY", "")
            mistral_base_url = os.environ.get("MISTRAL_BASE_URL", "https://api.mistral.ai")
            
            if mistral_api_key:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    mistral_resp = await client.post(
                        f"{mistral_base_url}/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {mistral_api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "mistral-large-latest",
                            "messages": [
                                {
                                    "role": "system",
                                    "content": (
                                        "You are a professional e-commerce product analyst. "
                                        "Analyze this product and return ONLY a JSON object with: "
                                        "category, target_gender (male/female/unisex), target_age, "
                                        "image_style_description (short), best_setting, vibe. "
                                        "Example: {\"category\":\"beauty\",\"target_gender\":\"female\","
                                        "\"target_age\":\"18-30\",\"image_style_description\":"
                                        "\"Thai woman holding makeup product in vanity room with soft natural lighting\","
                                        "\"best_setting\":\"vanity room or bedroom with mirror\",\"vibe\":\"warm, feminine, premium\"}"
                                    ),
                                },
                                {
                                    "role": "user",
                                    "content": f"Product: {product_name}. Description: {description}. UGC Style: {ugc_style}",
                                },
                            ],
                            "temperature": 0.3,
                            "max_tokens": 500,
                        },
                        timeout=30,
                    )
                    if mistral_resp.status_code == 200:
                        content = mistral_resp.json()["choices"][0]["message"]["content"]
                        # Extract JSON
                        import re
                        json_match = re.search(r'\{.*\}', content, re.DOTALL)
                        if json_match:
                            mistral_analysis = json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"Mistral analysis failed: {e}")
    
    # Build prompt
    result = build_prompt(
        product_name=product_name,
        description=description,
        ugc_style=ugc_style,
        mistral_analysis=mistral_analysis,
    )
    
    # Add mistral info if used
    if mistral_analysis:
        result["mistral_analysis"] = mistral_analysis
    result["used_mistral"] = mistral_analysis is not None
    
    return result
