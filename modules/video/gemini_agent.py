"""
Product Analyzer — uses Google Gemini 2.5 Flash API for high-fidelity product analysis + prompt generation
Supports text-only and vision (with base64 images)
"""

import os
import json
import logging
import requests
from typing import Optional, Any

import sys
from pathlib import Path
_erp_stack = Path(__file__).parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))
from shared_config import GEMINI_API_KEY

logger = logging.getLogger("product-analyzer")
TEXT_MODEL = "gemini-2.5-flash"
VISION_MODEL = "gemini-2.5-flash"

# Fallback Mistral config just in case
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")

PRESET_IMAGE_STYLES = [
    {
        "id": "holding_product",
        "name": "ถือสินค้า",
        "description": "สินค้าวางบนพื้นผิวเรียบสวยงาม",
        "suffix": "Product placed on a beautiful clean flat surface like marble or wood countertop, flat-lay photography, aesthetic composition, soft natural lighting, no hands, no person",
    },
    {
        "id": "product_usage",
        "name": "ใช้งานสินค้า",
        "description": "สินค้าในบรรยากาศการใช้งานจริงบนพื้นผิว",
        "suffix": "Product on a natural surface in a lifestyle setting, bathroom counter or vanity table, soft natural lighting, clean aesthetic, lifestyle flat-lay, no hands, no person",
    },
    {
        "id": "lifestyle",
        "name": "ไลฟ์สไตล์",
        "description": "สินค้าในชีวิตประจำวัน",
        "suffix": "Product integrated into everyday lifestyle scene on a clean surface, aesthetic composition, warm tones, no hands, no person in frame",
    },
    {
        "id": "close_up",
        "name": "Close-up",
        "description": "ถ่ายใกล้แสดงรายละเอียดสินค้า",
        "suffix": "Extreme close-up of product texture and details on a clean surface, macro photography, shallow depth of field, no hands",
    },
    {
        "id": "review_style",
        "name": "รีวิว",
        "description": "สไตล์รีวิว TikTok",
        "suffix": "Review-style setup, product on clean flat-lay or table, authentic lighting, social media aesthetic, no hands",
    },
]

RESEARCH_SYSTEM_PROMPT = """You are a professional product research and marketing expert. Analyze the product details and image carefully.
Provide a highly thorough, detailed analysis of the product's marketing characteristics.
Output ONLY valid JSON matching this schema:
{
  "product_type": "very specific product type (e.g. professional wireless lavalier microphone, organic hydrating face serum)",
  "material": "detailed description of visible materials, finishes, cap type, bottle texture, and overall premium feel",
  "category": "marketing category / niche (e.g. Premium Skincare, Content Creator Gear)",
  "target_audience": "in-depth target audience profile including specific demographics, pain points, behaviors, and buying motivations",
  "key_features": ["highly detailed feature 1 with benefits", "highly detailed feature 2 with benefits", "highly detailed feature 3 with benefits"],
  "visual_style_recommendation": "aesthetic visual direction (e.g. minimal warm tone lifestyle flat-lay with natural sunlight shadows)",
  "age_group": "specific target age group (e.g. 18-35 young professionals)",
  "gender": "target gender or neutral",
  "environment": "ideal shooting setting (e.g. modern aesthetic bathroom vanity, clean studio wooden desk)",
  "pain_points": ["explicit customer struggle 1 this product solves", "explicit customer struggle 2 this product solves"],
  "hooking_angle": "best attention-grabbing marketing angle in Thai focusing on transformation, result, or convenience"
}"""


def _call_gemini(
    system_prompt: str,
    user_text: str,
    image_base64: Optional[str] = None,
    response_json: bool = False,
) -> str:
    """Call Google Gemini 2.5 Flash API with vision support and optional JSON mode."""
    key = GEMINI_API_KEY()
    if not key:
        raise ValueError("GEMINI_API_KEY not configured")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}"

    # Combine system prompt and user text for Gemini
    combined_prompt = f"{system_prompt}\n\n[Input Context]:\n{user_text}"

    parts = [{"text": combined_prompt}]

    if image_base64:
        img_data = image_base64.strip()
        # Handle data URL prefix
        if "base64," in img_data:
            mime_type = img_data.split(";")[0].split(":")[1]
            img_data = img_data.split("base64,")[1]
        else:
            mime_type = "image/jpeg"
            
        parts.append({
            "inlineData": {
                "mimeType": mime_type,
                "data": img_data
            }
        })

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": parts
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
        }
    }

    if response_json:
        payload["generationConfig"]["responseMimeType"] = "application/json"

    resp = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )

    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")

    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise RuntimeError(f"Unexpected Gemini API response structure: {data}") from e


def _parse_json(text: str) -> dict:
    """Parse JSON from AI response, handling markdown fences and common formatting issues"""
    import re
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    raw = raw.strip()
    
    # Simple direct load first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
        
    # Clean control characters
    raw = raw.replace(chr(10), " ").replace(chr(13), " ")
    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', raw)
    
    # Try parsing again
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
        
    # Standard cleanup of trailing commas
    raw = re.sub(r',\s*}', '}', raw)
    raw = re.sub(r',\s*]', ']', raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
        
    # Find balanced braces
    depth = 0
    start = -1
    for i, ch in enumerate(raw):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(raw[start:i+1])
                except json.JSONDecodeError:
                    pass
                    
    raise ValueError("Failed to parse valid JSON from Gemini response")


def extract_brand_protocol(image_base64: str) -> dict:
    """Extract Brand Identity Protocol from product image using Gemini 2.5 vision.

    Returns structured JSON with exact product details.
    """
    prompt_text = """Analyze this product image and extract the following Brand Identity Protocol as valid JSON.
This is CRITICAL — the output will be used as a STRICT LOCK for generating new photos of this product.

Extract EXACTLY:
1. product_name: the brand name + product name as it appears on the packaging
2. bottle: shape (cylindrical/oval/square), material (glass/matte plastic/glossy/metallic), cap_type (dropper/pump/screw cap/spray), primary_color
3. label: list of colors on label, list of ALL text strings visible (brand name, product name, size, volume, ingredients, etc. — be complete)
4. brand_colors: the dominant brand colors (2-4 colors in HEX format or descriptive names)
5. logo: detailed description of any logo, emblem, or graphic on the packaging
6. packaging_type: bottle/box/tube/jar/sachet

Output ONLY valid JSON.
{
  "product_name": "",
  "bottle": {"shape": "", "material": "", "cap_type": "", "primary_color": ""},
  "label": {"colors": [], "text": []},
  "brand_colors": [],
  "logo": "",
  "packaging_type": ""
}
"""
    response = _call_gemini(
        system_prompt=prompt_text,
        user_text="Analyze the product image and return JSON.",
        image_base64=image_base64,
        response_json=True
    )
    return _parse_json(response)


def research_product(product_name, description='', category='', image_base64=None):
    """Step 1: Research product via AI vision/text analysis — returns structured dict"""
    has_vision = bool(image_base64)
    user_prompt = f'Analyze this product:\nProduct Name: {product_name}\nDescription: {description or "N/A"}\nCategory: {category or "N/A"}'
    if has_vision:
        user_prompt += '\n\n(Product image attached)'
    try:
        raw = _call_gemini(
            system_prompt=RESEARCH_SYSTEM_PROMPT,
            user_text=user_prompt,
            image_base64=image_base64,
            response_json=True
        )
        result = _parse_json(raw)
        logger.info(f'Product research successful for "{product_name}" via Gemini')
        return result
    except Exception as e:
        logger.warning(f'Product research failed, using default dict: {e}')
        return {
            'product_type': category or 'general',
            'material': 'premium packaging',
            'category': category or 'general',
            'target_audience': 'General consumers',
            'key_features': [f'High quality {product_name}'],
            'visual_style_recommendation': 'lifestyle',
            'age_group': '20-35',
            'gender': 'neutral',
            'environment': 'modern lifestyle setting',
            'pain_points': ['Finding a reliable product'],
            'hooking_angle': f'Highlight benefits of {product_name}'
        }


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

    # Extract Brand Protocol from image for strict lock
    brand_protocol = {}
    if image_base64:
        try:
            brand_protocol = extract_brand_protocol(image_base64)
        except Exception as e:
            logger.warning(f"Brand protocol extraction failed: {e}")
            brand_protocol = {}

    system_prompt = f"""# ROLE
You are an expert AI Product Photographer and Creative Director. Your goal is to produce high-fidelity product imagery and UGC video scripts that strictly adhere to the Brand Identity Protocol.

# BRAND IDENTITY PROTOCOL (STRICT LOCK)
These elements are IMMUTABLE - never alter or hallucinate these details:
{json.dumps(brand_protocol, ensure_ascii=False, indent=2) if brand_protocol else 'Analyze the product to determine brand details.'}

# OPERATIONAL GUIDELINES
1. ANALYZE the requested scene context from the product info
2. COMPOSITE the product as the HERO - sharp, well-lit, physically consistent
3. CONTEXTUALIZE into the scene (on table, countertop, shelf, etc.) using soft natural lighting
4. QUALITY CONTROL: never violate the Brand Protocol

# REQUIREMENTS FOR IMAGE PROMPTS (5 images):
- styles: holding_product, product_usage, lifestyle, close_up, review_style
- CRITICAL: The product is a BLANK PLACEHOLDER {_placeholder_term_for_category(category)} — NO text, NO labels, NO brand markings, NO packaging descriptions.
- Do NOT describe the actual product's label text, logo or branding in the image prompt (it is a blank container of correct color and material for compositing).
- CRITICAL: NO hands, NO people, NO person visible in any image — empty surface / flat-lay only.
- Describe a beautiful CLEAN SURFACE (marble countertop, wood table, ceramic tile, stone) as the setting.
- The product sits on the surface — it is NOT being held.
- Bounding Box (bbox): After analyzing the scene, estimate the exact relative bounding box coordinates where the product placeholder should be composited. JSON format: {{"x": float, "y": float, "width": float, "height": float, "angle": float}} (values between 0.0 and 1.0).
- Use warm Thai-style setting, natural lighting, pastel or soft tones.
 - For beauty/skincare products, describe a luxury vanity or bathroom counter setting.
 - For food/consumables, describe a clean kitchen counter or dining table.
 - For electronics, describe a desk or table surface with lifestyle elements.

# REQUIREMENTS FOR VIDEO PROMPT:
- Provide a highly detailed, comprehensive video prompt.
- description: Overview of the vertical video concept.
- movement: Detailed array of camera movements for each scene transition (e.g. ["Slow dolly zoom into product", "Smooth pan across countertop", "Close-up tilt showing bottle cap"]).
- lighting: Detailed description of lighting and mood (e.g., warm afternoon sun, diffused side-lighting with soft shadows).
- storytelling: Complete step-by-step scene-by-scene script breakdown, explaining what happens in each second of the video.
- transitions: Detailed creative video transitions (e.g., ["Whip pan transition to lifestyle setting", "Seamless overlay cut"]).
- product_interaction: Detailed actions involving the product (e.g., ["Unscrewing the dropper cap", "Dispensing product texture onto a flat surface", "Placing the bottle back down"]).

# REQUIREMENTS FOR HOOKS (3 hooks):
- THAI language, product-specific (NOT generic), attention-grabbing.
- Use female-friendly pronouns (คุณ) - never use male pronouns like ผม.
- Reference specific product benefits and pain points identified in research.
 - Include emotional triggers specific to the target audience.
 - For beauty products, focus on transformation/results.
 - For electronics, focus on convenience/time-saving.

Research Context:
{json.dumps(research, ensure_ascii=False, indent=2)}

Output ONLY valid JSON.
- CRITICAL BBOX DYNAMIC CALCULATION:
  - Do NOT copy the static numbers from examples. You must calculate dynamic coordinates (floats between 0.0 and 1.0) and dimensions based on the scene composition of each specific style:
    - "close_up": The product should dominate the frame. Use a large width/height (e.g., width: 0.7 to 0.85, height: 0.7 to 0.85) centered.
    - "lifestyle": The product should sit naturally on the surface. Use a smaller, realistic size (e.g., width: 0.2 to 0.35, height: 0.3 to 0.5) placed realistically.
    - "holding_product" / "product_usage": Position it naturally on the clean surface (e.g., centered or offset slightly).
{{
  "image_prompts": [
    {{"id": "holding_product", "name": "ถือสินค้า", "prompt": "very detailed prompt describing a blank container on a beautiful surface...", "bbox": {{"x": 0.35, "y": 0.3, "width": 0.28, "height": 0.45, "angle": 0.0}}}},
    {{"id": "product_usage", "name": "ใช้งานสินค้า", "prompt": "very detailed prompt...", "bbox": {{"x": 0.3, "y": 0.35, "width": 0.3, "height": 0.48, "angle": 0.0}}}},
    {{"id": "lifestyle", "name": "ไลฟ์สไตล์", "prompt": "very detailed prompt...", "bbox": {{"x": 0.4, "y": 0.4, "width": 0.2, "height": 0.35, "angle": 0.0}}}},
    {{"id": "close_up", "name": "ซูมระยะใกล้", "prompt": "very detailed prompt...", "bbox": {{"x": 0.15, "y": 0.15, "width": 0.7, "height": 0.7, "angle": 0.0}}}},
    {{"id": "review_style", "name": "รีวิว", "prompt": "very detailed prompt...", "bbox": {{"x": 0.35, "y": 0.25, "width": 0.3, "height": 0.5, "angle": 0.0}}}}
  ],
  "video_prompt": {{
    "description": "detailed overview...",
    "movement": ["...", "..."],
    "lighting": "...",
    "storytelling": "detailed step-by-step storyboard description...",
    "transitions": ["...", "..."],
    "product_interaction": ["...", "..."]
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
            response_json=True
        )

        result = _parse_json(raw)
        logger.info(
            f"Gemini analysis successful ({'vision' if has_vision else 'text'})"
        )
        return result
    except Exception as e:
        logger.warning(f"Gemini failed, using fallback: {e}")
        return _fallback_analysis(product_name, description, category)


def _placeholder_term_for_category(category: str = "") -> str:
    """Return a dynamic placeholder term based on product category.

    Different product shapes need different AI hand-holding poses.
    Returns the specific shape/packaging term so Flux generates
    the correct hand grip for that product type.
    """
    cat = (category or "").lower()

    # Bottles / jars (skincare, serum, oil, toner)
    if any(kw in cat for kw in ["cream", "moisturizer", "lotion", "serum", "oil",
                                "toner", "essence", "ampoule", "eye cream", "face oil"]):
        return "a blank minimal bottle (no labels, no text)"

    # Compact / palette (powder, blush, eyeshadow, foundation)
    if any(kw in cat for kw in ["powder", "compact", "blush", "foundation",
                                "palette", "eyeshadow", "highlighter", "bronzer"]):
        return "a blank minimal compact case (flat, round or square, no labels)"

    # Lip products
    if any(kw in cat for kw in ["lip", "lipstick", "lip gloss", "lip balm",
                                "lip tint", "lip liner", "lip oil"]):
        return "a blank minimal lipstick tube (cylindrical, twist-up, no labels)"

    # Tubes (face wash, cleanser, shampoo, body wash, lotion)
    if any(kw in cat for kw in ["face wash", "cleanser", "shampoo", "conditioner",
                                "body wash", "shower gel", "hand wash", "body lotion",
                                "sunscreen", "SPF", "toothpaste", "gel"]):
        return "a blank minimal squeeze tube (no labels)"

    # Supplements / sachets (vitamin, pill, powder, protein)
    if any(kw in cat for kw in ["supplement", "vitamin", "pill", "capsule",
                                "tablet", "powder", "protein", "sachet",
                                "collagen", "probiotic", "pre-workout"]):
        return "a blank minimal sachet pouch (flexible, no labels)"

    # Spray / mist (perfume, cologne, fragrance, hair spray, setting spray)
    if any(kw in cat for kw in ["perfume", "cologne", "fragrance", "spray",
                                "mist", "setting spray", "hair spray", "deodorant",
                                "dry shampoo", "face mist"]):
        return "a blank minimal bottle with spray nozzle (no labels)"

    # Sheet mask / face mask
    if any(kw in cat for kw in ["mask", "sheet mask", "face mask"]):
        return "a blank minimal flat sachet (no labels)"

    # Beauty tools (brush, sponge, puff, applicator, tool)
    if any(kw in cat for kw in ["tool", "brush", "sponge", "applicator",
                                "puff", "blender", "comb", "hair brush"]):
        return "a blank minimal handheld tool (no branding)"

    # Electronics / gadgets (vacuum, phone, power bank, charger, earphone)
    if any(kw in cat for kw in ["vacuum", "cleaner", "vacuum cleaner", "robot",
                                "phone", "smartphone", "mobile", "tablet", "ipad",
                                "power bank", "charger", "charging", "cable",
                                "earphone", "headphone", "earbuds", "speaker",
                                "bluetooth", "fan", "purifier", "air purifier",
                                "humidifier", "diffuser", "shaver", "trimmer",
                                "epilator", "massager", "massage gun",
                                "smartwatch", "watch", "fitness tracker",
                                "camera", "action camera", "drone", "gopro",
                                "laptop", "notebook", "ultrabook", "gaming laptop",
                                "monitor", "display", "keyboard", "mouse",
                                "router", "modem", "nas", "hard drive", "ssd"]):
        if any(kw in cat for kw in ["phone", "smartphone", "mobile", "tablet", "ipad"]):
            return "a hand holding a blank minimal smartphone (rectangular, no screen content, no labels)"
        if any(kw in cat for kw in ["power bank", "charger", "battery"]):
            return "a hand holding a blank minimal power bank (rectangular, no labels)"
        if any(kw in cat for kw in ["earphone", "headphone", "earbuds"]):
            return "a hand holding blank minimal wireless earbuds (no labels, no branding)"
        if any(kw in cat for kw in ["watch", "smartwatch", "fitness tracker"]):
            return "a wrist wearing a blank minimal smartwatch (no screen content, no labels)"
        else:
            return "a hand holding a blank minimal device (rectangular, no labels, no screen content)"
        return "a hand holding a blank minimal device (rectangular, no labels, no screen content)"

    # Food / drinks
    if any(kw in cat for kw in ["snack", "food", "drink", "beverage", "coffee",
                                "tea", "water", "juice", "sauce", "seasoning",
                                "oil bottle", "vinegar", "honey", "jam"]):
        return "a blank minimal bottle or pouch (no labels)"

    # Jewelry
    if any(kw in cat for kw in ["jewelry", "necklace", "ring", "bracelet", "earring",
                                "brooch", "pendant", "chain", "bangle", "anklet",
                                "watch", "cufflink", "tie clip", "hair accessory"]):
        return "a hand holding a blank minimal piece of jewelry (no branding, no text)"

    # Fashion accessories
    if any(kw in cat for kw in ["bag", "handbag", "purse", "tote", "backpack",
                                "wallet", "clutch", "belt", "scarf", "hat",
                                "cap", "gloves", "sunglasses", "umbrella"]):
        return "a hand holding a blank minimal fashion accessory (no branding, no text)"

    # Home decor
    if any(kw in cat for kw in ["candle", "vase", "frame", "mirror", "clock",
                                "lamp", "pillow", "blanket", "rug", "curtain",
                                "plant", "pot", "decor", "ornament"]):
        return "a blank minimal home decor item (no branding, no text)"

    # Default: generic container
    return "a blank minimal container (no text, no labels, no branding)"


def generate_image_prompt(brand_protocol: dict, creative_brief: dict, product_name: str, description: str) -> dict:
    """Generate ONLY image prompts (5 styles) using Gemini."""
    prompt_text = f"""Based on this Brand Protocol and Creative Brief, generate 5 detailed image prompts.

Brand Protocol: {json.dumps(brand_protocol, ensure_ascii=False, indent=2)}
Creative Brief: {json.dumps(creative_brief, ensure_ascii=False, indent=2)}
Product Name: {product_name}

Generate 5 prompts for these styles: holding_product, product_usage, lifestyle, close_up, review_style
Each prompt must:
\u2022 Describe a beautiful CLEAN SURFACE (marble, wood, countertop, table) as the main setting
\u2022 The product is described as a BLANK container with correct color, shape, and material
\u2022 CRITICAL: Do NOT describe any text, labels, logos, brand names, or markings — product is a blank placeholder
\u2022 CRITICAL: NO hands, NO people, NO person visible — empty surface only
\u2022 Include warm Thai-style setting and soft natural lighting
\u2022 The composition should look like a flat-lay or product photography on a surface

Output:
{{
  "image_prompts": [
    {{"id": "holding_product", "prompt": "..."}},
    {{"id": "product_usage", "prompt": "..."}},
    {{"id": "lifestyle", "prompt": "..."}},
    {{"id": "close_up", "prompt": "..."}},
    {{"id": "review_style", "prompt": "..."}}
  ]
}}
"""
    response = _call_gemini(
        system_prompt="You are an expert AI image prompt engineer.",
        user_text=prompt_text,
        response_json=True
    )
    return _parse_json(response)


def generate_video_prompt(brand_protocol: dict, creative_brief: dict, product_name: str) -> str:
    """Generate ONLY video prompt with camera movements and actions using Gemini."""
    prompt_text = f"""Generate a video prompt for this product. Focus on camera movement and action.

Brand Protocol: {json.dumps(brand_protocol, ensure_ascii=False, indent=2)}
Creative Brief: {json.dumps(creative_brief, ensure_ascii=False, indent=2)}
Product Name: {product_name}

Requirements:
\u2022 Cinematic motion, fluid camera movement
\u2022 Include specific camera moves: pan, zoom, tilt, dolly
\u2022 Include subject actions: reaching, applying, holding
\u2022 Duration: 15-25 seconds
\u2022 Format: 9:16 vertical video
\u2022 MUST keep the product appearance consistent with Brand Protocol

Output ONLY the video prompt as a single paragraph (no JSON, no markdown):"""
    return _call_gemini(
        system_prompt="You are an expert video director. Generate video prompts.",
        user_text=prompt_text
    )


def _fallback_analysis(product_name: str, description: str, category: str) -> dict:
    """Fallback analysis when AI fails - generate Thai content with product appearance"""
    image_prompts = []
    for style in PRESET_IMAGE_STYLES:
        image_prompts.append({
            "id": style["id"],
            "name": style["name"],
            "bbox": {"x": 0.35, "y": 0.25, "width": 0.3, "height": 0.5, "angle": 0.0},
            "prompt": f"ภาพถ่ายสินค้า {product_name} ในสไตล์ {style['name']} "
                      f"วางบนพื้นผิวเรียบสวยงาม แสงธรรมชาติ โทนอบอุ่น สไตล์ไทย",
        })

    return {
        "image_prompts": image_prompts,
        "video_prompt": {
            "description": f"วิดีโอรีวิวสินค้า {product_name} แสดงการใช้งานจริงในสถานที่แบบไทย",
            "movement": ["Slow pan", "Close-up zoom"],
            "lighting": "แสงสว่างธรรมชาติ โทนสีอบอุ่น",
            "storytelling": f"แสดงรายละเอียดสินค้า {product_name} ในชีวิตประจำวัน",
            "transitions": ["Cross dissolve"],
            "product_interaction": ["Picking up the product", "Showing features"]
        },
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
            "#" + category.replace(" ", "") if category else "#สินค้า",
        ],
    }
