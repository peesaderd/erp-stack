"""
TikTok UGC Studio — AI Script Generator (Gemini)
ใช้ Gemini API สำหรับสร้าง Script ภาษาไทย
"""

import os
import json
import logging
import random
import re
import requests
import json
import httpx
from pathlib import Path
from typing import Optional

logger = logging.getLogger("tiktok-ugc.script_gen")

# ─── Gemini Config ─────────────────────────────────────────────────────

# Gemini — centralized config
from shared_config import GEMINI_API_KEY as _get_gemini
GEMINI_API_KEY = _get_gemini()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")



# ─── Prompt Studio Config ──────────────────────────────────────────────

PROMPT_STUDIO_URL = os.environ.get("PROMPT_STUDIO_URL", "http://localhost:8108")
PROMPTS_DIR = Path(__file__).parent / "prompts"

_client = httpx.Client(timeout=10)


def load_prompt_from_studio(module: str, name: str) -> Optional[str]:
    try:
        resp = _client.get(f"{PROMPT_STUDIO_URL}/prompts/{module}/{name}")
        if resp.status_code == 200:
            return resp.json().get("content", "")
    except Exception:
        pass
    return None


def _fill_template(template: str, data: dict) -> str:
    def replacer(m):
        key = m.group(1)
        v = data.get(key)
        return str(v) if v is not None else ""
    return re.sub(r'\{\{(\w+)\}\}', replacer, template)


# ─── Gemini LLM Call ──────────────────────────────────────────────────

def _call_gemini(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call Gemini API"""
    if not GEMINI_API_KEY:
        logger.warning("No GEMINI_API_KEY configured — using template fallback")
        return None

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048},
        }
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return text
        else:
            logger.error(f"Gemini API error ({resp.status_code}): {resp.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
        return None


def _resolve_prompt(module: str, name: str, local_path: str) -> str:
    content = load_prompt_from_studio(module, name)
    if content:
        return content
    full_path = PROMPTS_DIR / local_path
    if full_path.exists():
        return full_path.read_text(encoding="utf-8")
    logger.warning(f"Prompt not found: {module}/{name}, {local_path}")
    return ""


def truncate_script_text(text: str, max_chars: int = 350) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    for sep in ('.', '!'):
        pos = truncated.rfind(sep)
        if pos > max_chars * 0.7:
            return text[:pos + 1]
    return truncated[:max(max_chars - 3, 0)] + "..."


# ─── Script Generators ────────────────────────────────────────────────

def generate_tiktok_review_script(
    product_name: str,
    customer_problem: str = "",
    main_benefit: str = "",
    target_audience: str = "",
    tone: str = "",
    cta: str = "",
    duration: str = "8s",
    extra_rules: str = "",
    max_chars: int = 350,
) -> dict:
    """Generate TikTok UGC review script using Gemini"""

    if duration == "16s":
        system = _resolve_prompt("tiktok", "system_16s.prompt.txt", "system_16s.prompt.txt")
        master = _resolve_prompt("tiktok", "master_16s_3step.prompt.txt", "master_16s_3step.prompt.txt")
        user_tpl = _resolve_prompt("tiktok", "user_16s.prompt.txt", "user_16s.prompt.txt")
    else:
        system = _resolve_prompt("tiktok", "system.prompt.txt", "system.prompt.txt")
        master = _resolve_prompt("tiktok", "master.prompt.txt", "master.prompt.txt")
        user_tpl = _resolve_prompt("tiktok", "user.template.prompt.txt", "user.template.prompt.txt")

    user_data = {
        "product_name": product_name,
        "customer_problem": customer_problem or "ปัญหาที่พบเจอบ่อย",
        "main_benefit": main_benefit or "คุณภาพดี ใช้งานได้จริง",
        "target_audience": target_audience or "ทุกคนที่กำลังมองหา",
        "tone": tone or "เป็นกันเอง พูดเร็ว",
        "cta": cta or "กดดูในตะกร้าเลย",
        "extra_rules": extra_rules or "-",
    }

    user_prompt = _fill_template(user_tpl, user_data)

    structured_instruction = (
        "\n\n"
        "🚨 IMPORTANT — Return as JSON ONLY with these keys:\n"
        '{"hook": "...", "body": "...", "cta": "...", '
        '"scene": "...", "voice": "...", "prompt": "...", '
        '"mood": "...", "hashtags": "..."}\n'
        'hook = ช่วงเปิด 1-2 ประโยค (ภาษาไทย)\n'
        'body = เนื้อหาคุณค่าสินค้า (ภาษาไทย)\n'
        'cta = เชิญชวนซื้อ (ภาษาไทย)\n'
        'scene = บรรยายฉาก เช่น "สาวไทยถือสินค้าหน้าฉากเรียบ"\n'
        'voice = บรรยายเสียง เช่น "หญิงไทย อายุ 20-30 เป็นกันเอง"\n'
        'prompt = full AI prompt สำหรับสร้างวิดีโอ\n'
        'mood = อารมณ์ เช่น "เป็นกันเอง, เชื่อถือได้"\n'
        'hashtags = คั่นด้วยช่องว่าง เช่น "#UGC #รีวิวสินค้า"\n'
        "Return ONLY valid JSON, no markdown, no extra text.\n"
        f"\n"
        f"🚨 LENGTH CONSTRAINT: TOTAL hook + body + cta "
        f"must be UNDER {max_chars} characters.\n"
    )

    raw = _call_gemini(system, f"{master}\n\n{user_prompt}\n\n{structured_instruction}")

    if raw:
        try:
            # Strip markdown fences if present
            clean = raw.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
            if clean.endswith("```"):
                clean = clean.rsplit("```", 1)[0]
            clean = clean.strip()
            parsed = json.loads(clean)

            hook = parsed.get("hook", "")
            body = parsed.get("body", "")
            cta = parsed.get("cta", "")

            combined = f"{hook} {body} {cta}"
            if len(combined) > max_chars:
                combined = truncate_script_text(combined, max_chars)

            return {
                "script": {"hook": hook, "body": body, "value_proposition": body, "cta": cta},
                "hook": hook,
                "value_proposition": body,
                "value": body,
                "body": body,
                "cta": cta,
                "scene": parsed.get("scene", ""),
                "voice": parsed.get("voice", ""),
                "voice_style": parsed.get("voice", ""),
                "prompt": parsed.get("prompt", ""),
                "video_prompt": parsed.get("prompt", ""),
                "mood": parsed.get("mood", ""),
                "mood_tone": parsed.get("mood", ""),
                "hashtags": parsed.get("hashtags", ""),
                "uses_llm": True,
                "duration": duration,
                "product": product_name,
                "_prompt_source": "gemini",
            }
        except Exception as e:
            logger.warning(f"Gemini JSON parse failed: {e}")

    # Fallback
    variation_json = _resolve_prompt("tiktok", "variation.json", "variation.json")
    variations_d = json.loads(variation_json) if variation_json else {}
    hook_text = f"{random.choice(variations_d.get('hooks', ['แนะนำสินค้าดี']))}! {product_name} ต้องดู!"
    body_text = f"{product_name} {main_benefit or 'คุณภาพดี'} ใช้งานง่าย ได้ผลจริง ลองใช้แล้วประทับใจมาก"
    cta_text = f"{random.choice(variations_d.get('ctas', ['กดตะกร้าเลย']))}! {product_name} ราคาพิเศษวันนี้เท่านั้น!"

    return {
        "script": {"hook": hook_text, "body": body_text, "value_proposition": body_text, "cta": cta_text},
        "hook": hook_text,
        "value_proposition": body_text,
        "value": body_text,
        "body": body_text,
        "cta": cta_text,
        "scene": "สาวไทยถือสินค้าหน้าฉากหลังเรียบ แต่งตัวสบายๆ",
        "voice": "หญิงไทย อายุ 20-30 ปี น้ำเสียงเป็นกันเอง พูดชัด",
        "voice_style": "หญิงไทย อายุ 20-30 ปี น้ำเสียงเป็นกันเอง พูดชัด",
        "prompt": f"Thai female model holding {product_name}, smiling at camera, soft natural lighting, {product_name} clearly visible, authentic Thai setting, studio background, professional quality",
        "video_prompt": f"Thai female model holding {product_name}, smiling, soft lighting, studio background",
        "mood": "เป็นกันเอง, เชื่อถือได้, อบอุ่น",
        "mood_tone": "เป็นกันเอง, เชื่อถือได้, อบอุ่น",
        "hashtags": "#UGC #รีวิวสินค้า #ของดีบอกต่อ",
        "uses_llm": raw is not None,
        "duration": duration,
        "product": product_name,
        "_prompt_source": "local_fallback",
    }


def generate_ugc_script(
    style: str,
    product_name: str,
    gender: str = "female",
    age: str = "25-35",
    scene: str = "home",
    custom_negative_prompt: Optional[str] = None,
) -> dict:
    """Generate UGC video prompt by style using Gemini"""
    style_map = {
        "holding_product": "Holding_Product",
        "product_usage": "Product_Usage",
        "ugc_review": "UGC_Review",
    }
    folder = style_map.get(style)
    if not folder:
        return {"error": f"Unknown style: {style}"}

    module = "ugc"
    system = _resolve_prompt(module, f"{folder}/system.prompt", f"UGC_prompts/{folder}/system.prompt")
    master = _resolve_prompt(module, f"{folder}/master.prompt", f"UGC_prompts/{folder}/master.prompt")
    user_tpl = _resolve_prompt(module, f"{folder}/user.template.prompt", f"UGC_prompts/{folder}/user.template.prompt")
    file_negative = _resolve_prompt(module, f"{folder}/negative.prompt", f"UGC_prompts/{folder}/negative.prompt")

    if custom_negative_prompt:
        negative = custom_negative_prompt + ", " + file_negative if file_negative else custom_negative_prompt
    else:
        negative = file_negative

    user_data = {
        "product": product_name,
        "gender": gender,
        "age": age,
        "scene": scene,
        "background": "clean",
    }

    user_prompt = _fill_template(user_tpl, user_data)
    system_full = f"{system}\n\n{negative}" if negative else system

    raw = _call_gemini(system_full, f"{master}\n\n{user_prompt}")

    return {
        "style": style,
        "prompt": raw or f"{system_full}\n\n{master}\n\n{user_prompt}",
        "negative_prompt": negative,
        "merged_negative_prompt": negative,
        "product": product_name,
        "uses_llm": raw is not None,
        "_prompt_source": "gemini",
    }


def get_script_variations() -> dict:
    content = _resolve_prompt("tiktok", "variation.json", "variation.json")
    try:
        return json.loads(content) if content else {}
    except (json.JSONDecodeError, TypeError):
        return {
            "hooks": ["แนะนำสินค้าดี", "ของดีมาแล้ว"],
            "tones": ["เป็นกันเอง", "จริงใจ"],
            "ctas": ["กดตะกร้าเลย", "สั่งเลยวันนี้"],
            "benefits": ["คุณภาพดี", "คุ้มค่า"],
        }


SCRIPT_TEMPLATES = {
    "8s": {
        "hook": ["เปิดด้วยปัญหา", "เปิดด้วยคำถาม", "เปิดด้วยความว้าว"],
        "value": ["บอกประโยชน์หลัก", "บอกจุดเด่น"],
        "cta": ["เชิญชวนซื้อ", "บอกให้กดลิงก์"],
    },
    "16s": {
        "hook": ["เปิดเรื่อง", "ดึงดูดความสนใจ"],
        "value": ["อธิบายรายละเอียด", "บอกประโยชน์"],
        "cta": ["สรุป + เชิญชวน"],
    },
}
