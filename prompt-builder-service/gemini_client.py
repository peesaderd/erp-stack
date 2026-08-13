# ─── Gemini API Client ──────────────────────────────────────────
# Low-level Gemini API calls + product image analysis
# ═══════════════════════════════════════════════════════════════════════

import os
import json
import base64
import logging
from typing import Optional, List, Dict, Any

import requests

from mistralai.client import Mistral

logger = logging.getLogger("prompt-builder-service")

from shared_config import GEMINI_API_KEY as _GEMINI_API_KEY_LAZY
from shared_config import MISTRAL_API_KEY as _MISTRAL_API_KEY_LAZY
from shared_config import GEMINI_MODEL
from prompt_templates import _extract_json, STYLE_MAP

# ─── Country → Ethnicity descriptor ──────────────────────────────
# Single source of truth for the model's ethnicity/appearance based on
# the selected country. Kept in sync with prompt_builder.py.
COUNTRY_ETHNICITY = {
    "thai": ("ethnic Thai", "Southeast Asian ethnic Thai features"),
    "vietnamese": ("ethnic Vietnamese", "Southeast Asian Vietnamese features"),
    "korean": ("ethnic Korean", "East Asian Korean features"),
    "japanese": ("ethnic Japanese", "East Asian Japanese features"),
    "chinese": ("ethnic Chinese", "East Asian Chinese features"),
    "indian": ("ethnic Indian", "South Asian Indian features"),
    "western": ("Caucasian", "Western European features"),
}

def _country_ethnicity(country: str) -> tuple:
    """Return (ethnicity_label, features_desc) for a country code."""
    return COUNTRY_ETHNICITY.get((country or "").lower().strip(), COUNTRY_ETHNICITY["thai"])

# ─── Gemini API Calls ────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

GEMINI_MODEL_NAME = GEMINI_MODEL if isinstance(GEMINI_MODEL, str) else "gemini-2.5-flash"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"

def _resolve_image_url(image_url: str) -> str:
    """Resolve any image ref to an HTTP URL fetchable from this host.

    Fixes broken image refs that have been seen in production logs:
      1. ``openhands.m2igen.comhttps://...`` (protocol concatenated twice)
      2. ``/ugc/static/product_images/xxx.jpg`` (relative, no scheme)
      3. ``/tiktok/storage/product_images/xxx.jpg`` (new format, no scheme)
      4. bare filenames like ``17923891001.jpg`` (legacy)
    """
    if not image_url:
        return ""
    s = image_url.strip()
    # Fix double-protocol: host followed immediately by "https://" or "http://"
    if "m2igen.comhttps://" in s or "m2igen.comhttp://" in s:
        idx = s.find("https://")
        if idx == -1:
            idx = s.find("http://")
        if idx != -1:
            s = s[idx:]
    # Protocol-relative
    if s.startswith("//"):
        return "http:" + s
    if s.startswith("http://") or s.startswith("https://"):
        return s
    # Local virtual path or bare filename → served by tiktok-ugc-studio (8105)
    for prefix in ("/ugc/static/product_images/", "/tiktok/storage/product_images/", "/storage/product_images/"):
        if s.startswith(prefix):
            filename = s.rsplit("/", 1)[-1]
            return f"http://localhost:8105/ugc/static/product_images/{filename}"
    if "/" not in s:
        return f"http://localhost:8105/ugc/static/product_images/{s}"
    return s



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


def _call_gemini(system_prompt: str, user_text: str, temperature: float = 0.3, max_output_tokens: int = 500) -> Optional[str]:
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
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_output_tokens},
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


def _call_gemini_vision(system_prompt: str, user_text: str, image_url: str, temperature: float = 0.3, max_output_tokens: int = 500) -> Optional[str]:
    """Call Gemini API with image input (multimodal)."""
    api_key = _get_gemini_key()
    if not api_key:
        logger.warning("No GEMINI_API_KEY set in environment")
        return None
    if not image_url:
        return None
    try:
        image_url = _resolve_image_url(image_url)
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
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_output_tokens},
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

PRODUCT_ANALYSIS_SYSTEM = """คุณคือระบบวิเคราะห์สินค้าสำหรับ TikTok Shop

วิเคราะห์สินค้าที่ได้รับ และตอบกลับเป็น JSON ONLY (ไม่มีข้อความอื่น)

กฎสำคัญ:
- ส่ง JSON ครบทุก field เสมอ ห้ามละเว้น field ใด
- target_gender ต้องเลือกเพียง 1 เพศ: "male" หรือ "female" เท่านั้น
- ถ้าไม่ได้ระบุเพศ: วิเคราะห์จากชื่อสินค้า + คำอธิบาย
  - "เบลเซอร์ผู้ชาย" → male / "ชุดเดรสผู้หญิง" → female
  - ถ้าหาไม่ได้จริงๆ → ใช้ "female" เป็นค่าเริ่มต้น

🔴 กฎ Packaging Action (บังคับ):
- ค้นหาคำที่บ่งบอกกลไกการใช้งานจากชื่อสินค้า + คำอธิบาย
- คำสำคัญ: Click/คลิก→click_to_release, Pump/ปั๊ม→pump, Spray/สเปรย์→spray, Roll/กลิ้ง→roll, Cream/ครีม→blend, Cushion/คุชชั่น→dab_press, Pen/ปากกา→click_pen
- ถ้าไม่มีคำเหล่านี้ → packaging_action: "generic_hold"

🔴 กฎ Subcategory (บังคับ):
- ระบุ subcategory ที่เจาะจง เช่น:
  - skincare → underarm_cream / serum / moisturizer / sunscreen / cleanser / toner
  - beauty → lipstick / foundation / blush / mascara / concealer
  - food → snack / drink / supplement / meal / dessert
  - fashion → clothing / accessory / shoes / bag
  - electronics → phone_case / headphone / charger / gadget
  - health → vitamin / medicine / fitness / first_aid
  - home → cleaning / decor / kitchen / furniture
  - other → general

JSON ที่ต้องตอบ:
{
  "category": "beauty/fashion/electronics/food/home/tools/health/other",
  "subcategory": "ระบุ subcategory ที่เจาะจง เช่น underarm_cream, serum, lipstick",
  "target_gender": "male/female",
  "target_age": "ช่วงอายุ เช่น 18-25, 25-35, 35-50",
  "target_skin_tone": "light/medium/tan/dark (ถ้าไม่แน่ใจใช้ medium)",
  "target_audience": "กลุ่มเป้าหมายหลัก",
  "customer_problem": "ปัญหาที่สินค้านี้แก้ (เจาะจง)",
  "main_benefit": "คุณประโยชน์หลักของสินค้า",
  "packaging_action": "click_to_release/pump/spray/roll/smooth_application/glossy_shine/blend/dab_press/click_pen/generic_hold",
  "action_desc": "คำอธิบายภาษาไทยสั้นๆ ว่าแพ็กเกจจิ้งทำงานยังไง",
  "features": "ENGLISH ONLY — product properties 4-6 short phrases",
  "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"]
}"""


PRODUCT_VISION_SYSTEM = """You are a Product Image Analyst. Analyze the product image and extract key details.

Focus ONLY on the product itself. IGNORE background, props, or setting.

Return JSON ONLY.

JSON format:
{
  "category": "beauty/fashion/electronics/food/home/tools/health/other",
  "subcategory": "specific subcategory — e.g. underarm_cream, serum, lipstick, snack, phone_case, vitamin",
  "product_type": "what this product is (e.g. lipstick, serum, t-shirt)",
  "target_gender": "female/male",
  "target_age": "age range — e.g. 18-25, 25-35, 35-50",
  "target_skin_tone": "light/medium/tan/dark (use medium if unsure)",
  "colors": ["color1", "color2", "color3"],
  "customer_problem": "what problem this product solves (Thai, match gender — คะ/ค่ะ for female, ครับ for male)",
  "main_benefit": "key benefit (Thai, match gender — ค่ะ/คะ for female, ครับ for male)",
  "features": "ENGLISH ONLY. Key product properties visible in image. 1-3 short phrases.",
  "usage_action": "ENGLISH ONLY. Specific physical motion of how a person opens/uses this product. Include: opening mechanism, body motion, product texture. Be precise, not generic."
}
}

RULES:
- target_gender MUST be "female" or "male"
- target_age: number only if clearly visible, otherwise empty string
- IGNORE background/setting — focus ONLY on the product
- features: properties you can CONFIRM from the image or label (not made up)
- usage_action: describe the REAL physical interaction (twist, pump, spray, pour, etc.)"""





# ─── Mistral Vision ──────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

MISTRAL_MODEL = "mistral-large-latest"  # Supports text + image input



_mistral_key_counter = 0

def _call_mistral_vision(system_prompt: str, user_text: str, image_url: str, temperature: float = 0.3) -> Optional[str]:
    """Call Mistral Large with image input (vision capabilities).

    Downloads image locally and passes as base64 since Mistral's backend
    can't reliably fetch from all image CDNs.

    Supports multiple Mistral API keys (MISTRAL_API_KEY, MISTRAL_API_KEY_2,
    MISTRAL_API_KEY_3, MISTRAL_API_KEY_4) that are rotated round-robin to
    distribute quota and avoid rate limits. On 401/429 it falls through to
    the next key.
    """
    global _mistral_key_counter
    if not image_url:
        return None

    # Collect all available Mistral keys (dedup, drop empties).
    # Sources: os.environ first, then shared_config._env_dict (which loads
    # the .env files). This lets MISTRAL_API_KEY_2/3/4 from .env be used.
    keys = []
    seen = set()
    env_sources = [os.environ]
    try:
        from shared_config import _env_dict as _shared_env
        env_sources.append(_shared_env)
    except Exception:
        pass
    for i in range(1, 10):
        env_name = "MISTRAL_API_KEY" if i == 1 else f"MISTRAL_API_KEY_{i}"
        k = ""
        for src in env_sources:
            v = src.get(env_name, "")
            if v:
                k = v
                break
        if not k:
            try:
                k = _MISTRAL_API_KEY_LAZY() if callable(_MISTRAL_API_KEY_LAZY) else _MISTRAL_API_KEY_LAZY
            except Exception:
                k = ""
        if k and k not in seen:
            seen.add(k)
            keys.append(k)
    if not keys:
        logger.warning("No MISTRAL_API_KEY set in environment")
        return None

    # Resolve + download image once (shared across key attempts)
    try:
        image_url = _resolve_image_url(image_url)
        img_resp = requests.get(image_url, timeout=30)
        img_resp.raise_for_status()
        img_b64 = base64.b64encode(img_resp.content).decode("utf-8")
        mime = img_resp.headers.get("content-type", "image/jpeg")
        data_uri = f"data:{mime};base64,{img_b64}"
    except Exception as e:
        logger.error(f"Mistral vision image download failed: {e}")
        return None

    # Round-robin start index
    start = _mistral_key_counter % len(keys)
    last_err = None
    for offset in range(len(keys)):
        idx = (start + offset) % len(keys)
        api_key = keys[idx]
        try:
            client = Mistral(api_key=api_key)
            response = client.chat.complete(
                model=MISTRAL_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": data_uri},
                    ]},
                ],
                temperature=temperature,
                max_tokens=2048,
                timeout_ms=30000,  # 30s cap so Step 1 (60s) never hangs on Mistral
            )
            if response and response.choices:
                _mistral_key_counter += 1
                return response.choices[0].message.content
            else:
                logger.warning("Mistral vision returned empty response")
                return None
        except Exception as e:
            last_err = e
            msg = str(e)
            # On auth/rate-limit errors, try the next key
            if "401" in msg or "Invalid API Key" in msg or "429" in msg or "rate" in msg.lower():
                logger.warning(f"Mistral key {idx+1} failed ({msg[:80]}) — trying next key")
                continue
            # Other errors (network, timeout, etc.) — try next key too
            logger.warning(f"Mistral key {idx+1} error ({msg[:80]}) — trying next key")
            continue

    _mistral_key_counter += 1
    logger.error(f"Mistral vision call failed with all keys: {last_err}")
    return None

def analyze_product_image(product_image: str, product_name: str, description: str = "") -> Optional[dict]:
    """Analyze product image via Mistral Large (vision-capable).
    
    Uses Mistral's built-in vision to accurately extract:
    - Product type, category
    - Container type (bottle/jar/tube/compact/pen)
    - Closure type (twist cap/pump/spray/flip-top/click)
    - Label colors and design
    - Product color/texture visible through packaging
    
    Uses Mistral vision only (no Gemini fallback) so the prompt stays
    consistent in one direction.
    """
    if not product_image:
        return None
    user_text = f"Analyze this product image. Product name: {product_name}. Description: {description if description else 'N/A'}"
    
    # Primary: Mistral vision
    raw = _call_mistral_vision(PRODUCT_VISION_SYSTEM, user_text, product_image, temperature=0.3)
    
    # No Gemini fallback — Mistral is the single source of truth.
    if not raw:
        logger.warning("Mistral vision returned empty — no fallback (single direction)")
    
    if raw:
        result = _extract_json(raw)
        if result:
            logger.info(f"Vision analysis result: {result.get('category', 'unknown')} / {result.get('product_type', 'unknown')}")
            return result
        # JSON parse failed silently in production (176+ occurrences).
        # Log a bounded snippet so the raw response can be inspected without
        # dumping the entire (possibly large) payload.
        logger.warning(
            "Vision response JSON parse FAILED — raw snippet (%d chars): %s",
            len(raw), raw[:300].replace("\n", " ")[:300],
        )
    else:
        logger.warning("Vision returned empty from both Mistral and Gemini fallback (image=%s)", product_image[:80])
    return None




# ═══════════════════════════════════════════════════════════════════════
# ─── Media Generation (Step 2) ────────────────────────────────────────
# Takes the product analysis (product_appearance + usage_action) and the
# UGC style, then produces clean, non-conflicting image & video prompts.
# ═══════════════════════════════════════════════════════════════════════



PRODUCT_ONLY_STYLES = {"product_demo", "unboxing", "comparison", "split_comparison"}

def _generate_media_prompts(
    product_name: str,
    product_appearance: str,
    usage_action: str,
    ugc_style: str,
    category: str,
    model_gender: str,
    model_age: str = "",
    env_context: str = "",
    features: str = "",
    country: str = "",
) -> tuple:
    """Generate clean image + video prompts via Gemini (Step 2).

    Uses the product analysis (product_appearance + usage_action) and the
    UGC style to produce non-conflicting image & video prompts.

    Returns (image_prompt, video_prompt) — falls back to ("", "") on error.
    """
    gender_en = {"female": "woman", "male": "man"}.get(model_gender, "")
    if not gender_en:
        gender_en = "woman"  # image gen needs a specific gender

    age_seg = f", {model_age} years old" if model_age else ""
    _eth_label, _eth_features = _country_ethnicity(country)
    # For product-only styles (product_demo, unboxing, comparison, split_comparison),
    # do NOT pass a human subject — the product is the star, no person in frame.
    if ugc_style in PRODUCT_ONLY_STYLES:
        subject = "no person in frame, product only, product clearly centered"
    else:
        subject = f"An {_eth_label} {gender_en}{age_seg}, {_eth_features}, small nose bridge"

    # Pull the UGC style rule-base (model_action/camera/vibe/video_motion) from
    # STYLE_MAP so Gemini follows the selected style instead of guessing.
    _style = STYLE_MAP.get(ugc_style, STYLE_MAP.get("holding", {}))
    _style_rules = (
        f"model_action: {_style.get('model_action', '')}\n"
        f"camera: {_style.get('camera', '')}\n"
        f"vibe: {_style.get('vibe', '')}\n"
        f"video_motion: {_style.get('video_motion', '')}"
    )

    # For product-only styles, do NOT pass any human model info (gender/age)
    # so Gemini never puts a person in frame — the product is the star.
    if ugc_style in PRODUCT_ONLY_STYLES:
        # Override usage_action: vision analysis often says "holding the product"
        # which would make Gemini put a person in frame. For product-only styles
        # the product is shown alone on a surface — no person.
        usage_action = "product on clean surface, no person, product clearly centered"
        user_text = (
            f"product_reconstruction_prompt: {product_appearance or product_name}\n"
            f"usage_action: {usage_action}\n"
            f"ugc_style: {ugc_style or 'product_demo'}\n"
            f"category: {category or 'other'}\n"
            f"country: {country or 'thai'}\n"
            f"env_context: {env_context or 'a clean minimal surface'}\n"
            f"product_features: {features or 'none'}\n"
            f"subject: no person in frame, product only, product clearly centered\n"
            f"style_rules:\n{_style_rules}\n\n"
            f"Generate the image_prompt and video_prompt as JSON, following the style_rules. "
            f"IMPORTANT: NO person/model in frame — product only."
        )
    else:
        user_text = (
            f"product_reconstruction_prompt: {product_appearance or product_name}\n"
            f"usage_action: {usage_action or 'holding the product and showing it to camera'}\n"
            f"ugc_style: {ugc_style or 'holding'}\n"
            f"category: {category or 'other'}\n"
            f"model_gender: {gender_en}\n"
            f"model_age: {model_age or 'unspecified'}\n"
            f"country: {country or 'thai'}\n"
            f"env_context: {env_context or 'a modern lifestyle setting'}\n"
            f"product_features: {features or 'none'}\n"
            f"subject: {subject}\n"
            f"style_rules:\n{_style_rules}\n\n"
            f"Generate the image_prompt and video_prompt as JSON, following the style_rules."
        )

    try:
        raw = _call_gemini(MEDIA_GENERATION_SYSTEM, user_text, temperature=0.4, max_output_tokens=300)
        if not raw:
            return ("", "")
        result = _extract_json(raw)
        if not result:
            logger.warning("Media generation JSON parse failed — raw snippet: %s", raw[:200].replace("\n", " "))
            return ("", "")
        image_prompt = result.get("image_prompt", "")
        video_prompt = result.get("video_prompt", "")
        return (image_prompt, video_prompt)
    except Exception as e:
        logger.error(f"Media generation failed: {e}")
        return ("", "")
