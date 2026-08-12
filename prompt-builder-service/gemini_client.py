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

PRODUCT_ANALYSIS_SYSTEM = """คุณคือนักวิเคราะห์สินค้าสำหรับ TikTok Shop (Gemini-powered)
วิเคราะห์สินค้าที่ได้รับ และตอบกลับเป็น JSON ONLY (ไม่มีข้อความอื่น)

กฎสำคัญ:
- ส่ง JSON ครบทุก field เสมอ ห้ามละเว้น field ใด ห้ามเว้นว่าง ถ้าข้อมูลไม่พอให้ใช้ค่าเริ่มต้นที่เหมาะสม
- target_gender ต้องเลือกเพียง 1 เพศ: "male" หรือ "female" เท่านั้น ห้ามใช้ "person" หรือ "unisex" โดยเด็ดขาด
- ถ้าไม่ได้ระบุเพศกลุ่มเป้าหมาย: ให้วิเคราะห์จากชื่อสินค้า + คำอธิบายเอง
  ตัวอย่าง: "เบลเซอร์ผู้ชาย", "กล่องน้ำหอมผู้ชาย" → male / "ชุดเดรสผู้หญิง", "กระโปรงสตรี" → female
  ถ้าหาข้อบ่งชี้ไม่ได้จริงๆ (สินค้ากลางๆ เช่น สายชาร์จ, ปลั๊กไฟ) → ใช้ "female" เป็นค่าเริ่มต้น
- customer_problem: ระบุปัญหาเฉพาะที่เจาะจง ไม่กว้างเกินไป
- image_description: ภาษาอังกฤษล้วน 100% ห้ามมีภาษาไทยเด็ดขาด ⚠️ IMPORTANT: You are a TEXT-ONLY analyst — you CANNOT see the product image. Do NOT describe colors, container, closure, label, fabric, or any visual detail you cannot confirm from the text alone. If the product is clothing/fashion, do NOT guess the outfit — a separate VISION system (which sees the actual photo) writes the authoritative image_description. Set image_description to "" unless the product name/description states the physical appearance unambiguously (e.g. "ชุดเดรสสีแดง" → "red dress").

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

🔴 🔴 รายละเอียดบรรจุภัณฑ์ต้องใส่ใน **product_appearance** (ไม่ใช่ image_description) — วิดีโอใช้กำหนดท่าเปิด/ใช้สินค้า:
- container type: bottle/jar/tube/compact/pen
- closure: twist cap/pump/spray/flip-top/click mechanism
- product color/texture (visible through packaging if clear)
- label colors and design elements
⚠️ คุณเป็น TEXT-ONLY (ไม่เห็นรูปภาพ): ระบุ container/closure ที่อนุมานได้จากชื่อ/คำอธิบาย (เช่น "สเปรย์"→spray, "ปั๊ม"→pump, "หลอด"→tube) โดยไม่แต่งสีเนื้อที่ไม่ปรากฏ และตั้ง image_description: "" เสมอ เพราะ Vision system (เห็นรูปจริง) จะเขียนฉากเต็มที่ถูกต้อง

JSON ที่ต้องตอบ:
{
  "category": "beauty/fashion/electronics/food/home/tools/health/other",
  "target_gender": "male/female",
  "target_age": "",
  "target_audience": "กลุ่มเป้าหมายหลัก เช่น สาววัยทำงานที่มีปัญหาริมฝีปากแห้ง",
  "setting": "สถานที่ถ่ายวิดีโอ เช่น vanity room หรือ bathroom",
  "customer_problem": "ปัญหาที่สินค้านี้แก้ (เจาะจง) เช่น ริมฝีปากแห้งแตก ไม่ฉ่ำ ใต้ตาคล้ำจากนอนดึก",
  "main_benefit": "คุณประโยชน์หลักของสินค้า เช่น ให้ริมฝีปากชุ่มชื้น ฉ่ำวาว ตลอดวัน",
  "packaging_action": "click_to_release/pump/spray/roll/smooth_application/glossy_shine/blend/dab_press/click_pen/generic_hold",
  "action_desc": "คำอธิบายภาษาไทยสั้นๆ ว่าแพ็กเกจจิ้งทำงานยังไง",
  "features": "ENGLISH ONLY — ALL product properties from description แยกเป็นรายการ เช่น USB rechargeable, 400ml capacity, wireless, motion sensor, one-button operation, adjustable speed, compact size, LED indicator, refillable, BPA-free, waterproof, dishwasher-safe (4-6 short phrases — extract EVERY spec in the description, do not skip any)",
  "product_appearance": "ENGLISH ONLY — physical packaging description from name/description (keep under 120 chars) เช่น white plastic bottle with spray nozzle, LED indicator. จำเป็นสำหรับวิดีโอ (ท่าเปิด/ใช้สินค้า): ระบุ container (bottle/jar/tube/box), closure (twist cap/pump/spray/lid) และเนื้อ/สีตามชื่อหรือคำอธิบายบอก (อย่าแต่งสีที่ไม่มี — ไม่แน่ใจให้ละเว้น). Vision system จะทับค่าที่ถูกต้องจากรูปจริงเมื่อมีภาพ",
  "hashtags": ["hashtag1", "hashtag2", "hashtag3", "hashtag4", "hashtag5"],
  "price": "ราคาสินค้าตามที่ให้ เช่น 499 บาท (ถ้าไม่ระบุ: ไม่ระบุ)",
  "product_id": "ID สินค้าตามที่ให้ (ถ้าไม่ระบุ: ไม่ระบุ)",
  "product_category": "หมวดหมู่ย่อย เช่น t-shirt, lipstick, phone-case (ถ้าไม่ระบุ: ไม่ระบุ)",
  "image_description": "ENGLISH ONLY — absolutely NO Thai language. Describe the scene for AI image generation.

🔴 CRITICAL — First Frame Rule (บังคับ):
- สำหรับสินค้าประเภทเสื้อผ้า/แฟชั่น/เครื่องประดับ: นางแบบต้อง "สวมใส่" (wearing/draped) สินค้า ไม่ใช่ "ถือ"
  • clothing/fashion/apparel → model WEARING the garment
  🔴 CRITICAL: For clothing products — model wears ONLY the product garment itself (exactly as in product_appearance). Do NOT invent random outfits (denim jacket, jeans, T-shirt). The product IS the outfit piece ON the model body. Never describe the product as "resting nearby" — it must be ON the model as the main visible garment.
  • accessories/jewelry/watch → model WEARING/ADORNED with the accessory
  • bags/shoes → model WEARING/CARRYING naturally
- สำหรับสินค้าประเภทอื่น (บิวตี้/เครื่องใช้ไฟฟ้า/ฯลฯ): นางแบบ "ถือ" (holding) สินค้า
- image_description = FIRST FRAME ของวิดีโอ (Wan 2.7 ใช้เป็น reference image)
- ต้องตรงกับท่าเริ่มต้นของ Video Prompt Scene แรกเป๊ะๆ
- สำหรับ Holding/UGC Style: นางแบบต้อง "ถือสินค้าที่ระดับอก" (holding at chest level) — ยังไม่เริ่มใช้
- ห้ามระบุว่านางแบบกำลังใช้สินค้า (กำลังทา, กำลังปั๊ม, กำลังฉีด) ใน image_description
- การทำงานที่ถูกต้อง:
  • Image (First Frame): ถือสินค้าที่ระดับอกเฉยๆ
  • Video Scene 1: เริ่มขยับจากท่าถือ → เริ่มใช้สินค้า
  • Video Scene 2+: ใช้สินค้าจริง

🔴 ต้องระบุรายละเอียดบรรจุภัณฑ์: container type (bottle/jar/tube), closure (twist cap/pump/spray/flip-top), สีและดีไซน์ของฉลาก

Include: model appearance MUST match target_gender AND the country field (e.g. "Ethnic Thai woman" for thai/female, "Ethnic Korean man" for korean/male, "Caucasian woman" for western/female) — with the appropriate ethnicity features for the selected country. Pose: Model MUST be STANDING (not sitting, not on floor, not kneeling) — full body visible from mid-thigh up. If product is clothing/fashion/apparel → model WEARING/DRAPED in the garment naturally (the garment IS the product — do NOT add denim, jeans, or other random clothing). The product must be ON the body, never "resting nearby." For all other products → HOLDING product at chest level, OR actively using/applying it (e.g. applying lipstick, spraying mist, pumping) — show the product in natural use. Expression: confident smile. CRITICAL: Model is STANDING upright — NOT sitting on floor, NOT cross-legged, NOT kneeling, NOT leaning on walls. Setting: MATCH the product_analysis.setting and env_context — use the appropriate setting per category (beauty: vanity/bathroom, clothing: closet/boutique/bedroom, electronics: desk/office, home: living/kitchen, food: kitchen/cafe, health: bathroom/bedroom). Lighting: soft natural window light. Mood: warm, inviting. Focus on product being clearly visible and in focus. You MAY describe the product being used/applied (e.g. applying lipstick, spraying mist) — the 6-scene video continues naturally from this first frame. ระบุ container type (bottle/jar/tube), closure (twist cap/pump/spray/flip-top) และสีของสินค้าใน product_appearance ด้วย (ไม่ใช่ image_description)

Examples (match target_gender):
  • If target_gender=female: 'An ethnic [country] woman with a happy smile, STANDING, holding the product at chest level — packaging details such as container and cap are defined in product_appearance, not guessed here — product visible and in focus, in an appropriate setting with soft natural window lighting, warm and inviting atmosphere'
  • If target_gender=male: 'An ethnic [country] man with a confident smile, STANDING, holding the product at chest level — packaging details such as container and colour are defined in product_appearance, not guessed here — product visible and in focus, in a modern office with soft natural window lighting, professional atmosphere'",

🔴 image_description CRITICAL — ต้องแยก "model appearance" (ethnicity + gender from target_gender, features) ออกจาก "product packaging" (container, cap, color) ให้ชัดเจน
}"""


PRODUCT_VISION_SYSTEM = """You are an expert Product Analyst. Analyze the product from the provided image and text, and extract its exact physical details so it can be accurately recreated in an AI image generator.

IGNORE the background, props, or setting of the input image. Focus ONLY on the product itself.

Categorize the product and provide details based on its category:
1. IF CATEGORY IS "BEAUTY/SKINCARE":
   - Extract packaging type (bottle, jar, tube, dropper, pump).
   - Extract material/color (e.g., frosted glass, glossy plastic).
   - Extract texture if visible (e.g., clear gel, white cream).
2. IF CATEGORY IS "FASHION/APPAREL":
   - Extract clothing type (e.g., crop top, maxi dress, short-sleeve shirt).
   - Extract fabric details, cut, fit, color, and patterns.

Return JSON ONLY.

JSON format:
{
  "category": "beauty/fashion/electronics/food/home/tools/health/other",
  "product_type": "what this product is (e.g. wall-mounted motion sensor light, electric toothbrush)",
  "target_gender": "female/male",
  "target_age": "",
  "setting": "where this product is typically used/installed (English, general location)",
  "env_context": "specific environment: hallway entrance, bathroom sink, bedroom vanity, kitchen counter",
  "colors": ["color1", "color2", "color3"],
  "customer_problem": "what problem this product solves (Thai natural register, match target_gender — คะ/ค่ะ for female, ครับ for male) เช่น ต้องเดินคลำทางในที่มืด, ปั่นผลไม้ยากลำบาก",
  "main_benefit": "key benefit (Thai natural register, match target_gender — ค่ะ/คะ for female, ครับ for male) เช่น เปิดไฟอัตโนมัติเมื่อเดินผ่าน, ปั่นละเอียดแรงสูงพกพาสะดวก",
  "product_appearance": "ENGLISH ONLY. A highly detailed visual description of the PRODUCT ONLY (no person, no scene). For beauty/cosmetics: include packaging type (bottle/jar/tube/compact/pen), material/color (e.g. frosted glass, glossy plastic), closure (twist cap/pump/spray/flip-top/click), and texture if visible (e.g. clear gel, white cream). For clothing/fashion: include clothing type, fabric details, cut, fit, color, and patterns. This field is used for VIDEO generation (how to open/use the product), so be specific about the physical details.",
  "features": "ENGLISH ONLY. Key product properties/benefits visible or implied (e.g. portable USB rechargeable, powerful motor, BPA-free, measurement markings, one-button operation, motion sensor, automatic on/off). 1-3 short phrases.",
  "usage_action": "ENGLISH ONLY. A SPECIFIC, ACTION-ORIENTED description of exactly HOW a person interacts with this product — the physical motion of opening/using/wearing it. This drives VIDEO generation, so be precise about the mechanics. Examples by category: BEAUTY (e.g. 'twisting open the cap and squeezing a pea-sized amount of the white cream onto her fingers, then massaging it into her face'), FASHION (e.g. 'already wearing the high-waisted A-line skirt, she smooths the pleats and turns slowly to show the silhouette and the side zipper'), ELECTRONICS (e.g. 'pressing the single power button and holding the device up to her ear'), FOOD (e.g. 'twisting off the lid and pouring the golden honey into a spoon'), TOOLS (e.g. 'gripping the handle and pressing the trigger to spray'). ALWAYS include: (1) the specific opening/closure mechanism (twist cap, pump, spray, flip-top, zipper, button, plug), (2) the exact body motion (squeeze, pump, spray, zip, step into, press, pour, grip), (3) the product's texture/consistency if relevant (cream, gel, serum, lotion, pleated fabric, liquid). Do NOT write generic phrases like 'using the product' — describe the real physical interaction.",
  "image_description": "ENGLISH ONLY. Describe the SCENE for AI image generation — the MODEL (person) in the scene, NOT the product details. The product image is already provided as reference, so DO NOT re-describe the product's physical details (container, cap, color, fabric) in detail. Instead describe: (1) room setting / environment, (2) the model — ethnicity matching the country field (e.g. 'Ethnic Thai woman' for thai/female / 'Ethnic Korean man' for korean/male), with age, hair style, and the outfit/dress they are wearing, (3) whether the model is WEARING the garment (for clothing/fashion) or HOLDING the product at chest level (for other products). Keep it concise — the product itself is visible in the reference image. Example: 'An ethnic Thai woman, 25 years old, long black hair, wearing a red knit dress, standing in a bright bedroom with soft natural window light, warm inviting atmosphere.'"
}
RULES:
- target_gender MUST be "female" or "male" — image gen NEEDS a specific gender
- target_age: number only if inferred from product/image, otherwise empty string
- IGNORE the input image's background, props, or setting — focus ONLY on the product itself
- product_appearance describes the product PHYSICALLY — not a scene, not a person. Be specific about container/closure/color for video use.
- image_description describes the SCENE with the MODEL (person) — room setting, Thai ethnicity, age, hair style, outfit/dress, and whether wearing or holding the product. Do NOT re-describe product physical details (they are in product_appearance and visible in the reference image).
- features describes PROPERTIES you can confirm from the image or label (not made up claims)
- setting = general location type. env_context = specific spot"""





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

MEDIA_GENERATION_SYSTEM = """You are an expert AI Prompt Engineer for UGC product videos (image + video generation).

You produce TWO separate prompts with DIFFERENT purposes:

=== IMAGE PROMPT (first frame / thumbnail) ===
Purpose: a clean, beautiful still of the product (with a model ONLY for person-focused styles).
- Keep it SHORT. Do NOT re-describe the product's appearance in detail.
- Focus on: framing, and LIGHTING (e.g. "natural window light", "soft diffused daylight", "warm golden-hour light").
- CLOTHING/FASHION products (category=fashion/clothing/skirt/dress/top/shoes/apparel): The model WEARS the product elegantly on body. Never hold clothing in hands.
- BOTTLES/COSMETICS/CONTAINERS: Model holds container steadily at chest level or sitting on an aesthetic surface.
- PRODUCT-ONLY styles (ugc_style=product_demo/unboxing/comparison/split_comparison): NO person/model in frame — show product ALONE on clean surface.

=== VIDEO PROMPT (motion / action & END SCENE CREATIVE GUIDANCE) ===
Purpose: describe PURE MOTION, CAMERA ACTION, and a CREATIVE DYNAMIC END SCENE. Do NOT re-describe product appearance or ethnicity.

1. ANALYZE THE ULTIMATE PRODUCT RESULT (End Scene / Result Scene):
   - Reason about the most emotionally satisfying result of using this product.
   - Fabric softener / Laundry: model touching or smelling freshly washed fabric to cheek with a relaxed, fragrant smile, sunny laundry background.
   - Skincare / Cosmetics: model showcasing radiant glowing skin beside product with a confident happy smile.
   - Food / Beverage: model tasting/sipping with genuine delight and presenting product.
   - Tech / Electronics / Home: sleek device or clean environment, model showing satisfaction with product featured prominently.

2. CREATIVE FREEDOM & DIVERSITY:
   - Be creative! Invent realistic, diverse, and authentic UGC end scenes that fit the specific product.
   - Never restrict yourself to a single repetitive scene. Use the environment, lighting, and genuine human reactions appropriate for the specific item.

3. COMPOSITION & CLOTHING RULES:
   - CLOTHING/FASHION: Pose/body movement and fabric sway ONLY. STRICTLY NO holding or hand-adjusting clothing.
   - BOTTLES/CONTAINERS: Steady product presentation, subtle camera zoom/tilt. STRICTLY NO unscrewing caps, clicking buttons, or complex finger manipulations.
   - Preserve lower-left composition space for TikTok basket overlay button.

Output JSON only:
{
  "image_prompt": "...",
  "video_prompt": "..."
}"""

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
