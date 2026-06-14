"""
TikTok UGC Studio — AI Script Generator
ใช้ AiBot Auto-Gen v4.5 prompt system + LLM API
"""

import os
import json
import logging
import random
from pathlib import Path
from typing import Optional

logger = logging.getLogger("tiktok-ugc.script_gen")

PROMPTS_DIR = Path(__file__).parent / "prompts"

# ─── LLM Config ────────────────────────────────────────────────────────────

LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")
LLM_MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")


def _call_llm(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call LLM API (DeepSeek by default)"""
    if not LLM_API_KEY:
        logger.warning("No LLM_API_KEY configured — using template fallback")
        return None

    try:
        import httpx
        resp = httpx.post(
            f"{LLM_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {LLM_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": LLM_MODEL,
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
            logger.warning(f"LLM API error: {resp.status_code} {resp.text[:200]}")
            return None
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return None


# ─── Prompt Loader ─────────────────────────────────────────────────────────

def load_prompt(path: str) -> str:
    """Load a prompt file from the prompts directory"""
    full_path = PROMPTS_DIR / path
    if not full_path.exists():
        logger.warning(f"Prompt not found: {path}")
        return ""
    return full_path.read_text(encoding="utf-8")


def fill_template(template: str, data: dict) -> str:
    """Replace {{key}} with data[key]"""
    import re
    def replacer(m):
        key = m.group(1)
        v = data.get(key)
        return str(v) if v is not None else ""
    return re.sub(r'\{\{(\w+)\}\}', replacer, template)


# ─── Script Generators ─────────────────────────────────────────────────────

def generate_tiktok_review_script(
    product_name: str,
    customer_problem: str = "",
    main_benefit: str = "",
    target_audience: str = "",
    tone: str = "",
    cta: str = "",
    duration: str = "8s",
    extra_rules: str = "",
) -> dict:
    """Generate a TikTok UGC review script using AiBot prompts"""
    # Load prompts
    if duration == "16s":
        system = load_prompt("system_16s.prompt.txt")
        master = load_prompt("master_16s_3step.prompt.txt")
        user_tpl = load_prompt("user_16s.prompt.txt")
    else:
        system = load_prompt("system.prompt.txt")
        master = load_prompt("master.prompt.txt")
        user_tpl = load_prompt("user.template.prompt.txt")

    # Build user data
    user_data = {
        "product_name": product_name,
        "customer_problem": customer_problem or "ปัญหาที่พบเจอบ่อย",
        "main_benefit": main_benefit or "คุณภาพดี ใช้งานได้จริง",
        "target_audience": target_audience or "ทุกคนที่กำลังมองหา",
        "tone": tone or "เป็นกันเอง พูดเร็ว",
        "cta": cta or "กดดูในตะกร้าเลย",
        "extra_rules": extra_rules or "-",
    }

    user_prompt = fill_template(user_tpl, user_data)

    # Try LLM with structured output instruction
    structured_instruction = (
        "\n\n"
        "🚨 IMPORTANT — Return as JSON ONLY with these keys:\n"
        '{"hook": "...", "body": "...", "cta": "...", '
        '"scene": "...", "voice": "...", "prompt": "...", '
        '"mood": "...", "hashtags": "..."}\n'
        'hook = ช่วงเปิด 1-2 ประโยค\n'
        'body = เนื้อหาคุณค่าสินค้า\n'
        'cta = เชิญชวนซื้อ\n'
        'scene = บรรยายฉาก เช่น "สาวไทยถือสินค้าหน้าฉากเรียบ"\n'
        'voice = บรรยายเสียง เช่น "หญิงไทย อายุ 20-30 เป็นกันเอง"\n'
        'prompt = full AI prompt สำหรับสร้างวิดีโอ\n'
        'mood = อารมณ์ เช่น "เป็นกันเอง, เชื่อถือได้"\n'
        'hashtags = คั่นด้วยช่องว่าง เช่น "#UGC #รีวิวสินค้า"\n'
        "Return ONLY valid JSON, no markdown, no extra text."
    )
    raw = _call_llm(system, f"{master}\n\n{user_prompt}\n\n{structured_instruction}")

    if raw:
        try:
            import json as _json
            parsed = _json.loads(raw)
            return {
                "script": {
                    "hook": parsed.get("hook", ""),
                    "body": parsed.get("body", ""),
                    "value_proposition": parsed.get("body", ""),
                    "cta": parsed.get("cta", ""),
                },
                "hook": parsed.get("hook", ""),
                "value_proposition": parsed.get("body", ""),
                "value": parsed.get("body", ""),
                "body": parsed.get("body", ""),
                "cta": parsed.get("cta", ""),
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
            }
        except Exception:
            pass

    # Fallback
    variations_d = json.loads(load_prompt('variation.json') or '{}')
    hook_text = f"{random.choice(variations_d.get('hooks', ['แนะนำสินค้าดี']))}! {product_name} ต้องดู!"
    body_text = f"{product_name} {main_benefit or 'คุณภาพดี'} ใช้งานง่าย ได้ผลจริง ลองใช้แล้วประทับใจมาก"
    cta_text = f"{random.choice(variations_d.get('ctas', ['กดตะกร้าเลย']))}! {product_name} ราคาพิเศษวันนี้เท่านั้น!"
    
    script = {
        "hook": hook_text,
        "body": body_text,
        "value_proposition": body_text,
        "cta": cta_text,
    }
    
    return {
        "script": script,
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
    }


def _template_script(data: dict, duration: str) -> str:
    """Template fallback for TikTok review script"""
    pname = data.get("product_name", "สินค้านี้")
    problem = data.get("customer_problem", "ปัญหาที่เจอ")
    benefit = data.get("main_benefit", "คุณภาพดี")
    tone = data.get("tone", "เป็นกันเอง")

    variations = json.loads(load_prompt("variation.json") or "{}")
    hooks = variations.get("hooks", ["แนะนำสินค้าดี"])
    ctas = variations.get("ctas", ["กดตะกร้าเลย"])

    hook = random.choice(hooks)
    cta_phrase = random.choice(ctas)

    if duration == "16s":
        return (
            f"[Hook] {hook}! {pname} {problem} ต้องดู!\n\n"
            f"[Value] {pname} {benefit} ใช้งานง่าย ได้ผลจริง "
            f"ลองใช้แล้วประทับใจมาก\n\n"
            f"[CTA] {cta_phrase} {pname} ราคาพิเศษวันนี้เท่านั้น!"
        )
    else:
        return (
            f"[สคริปต์ 8 วินาที]\n"
            f"{hook}! {pname} {problem} ต้องดู!\n"
            f"{pname} {benefit} ลองใช้แล้วดีมาก\n"
            f"{cta_phrase}!"
        )


def generate_ugc_script(
    style: str,
    product_name: str,
    gender: str = "female",
    age: str = "25-35",
    scene: str = "home",
    custom_negative_prompt: Optional[str] = None,
) -> dict:
    """
    Generate UGC video prompt by style:
    - holding_product: โชว์สินค้าในมือ
    - product_usage: สาธิตการใช้งาน
    - ugc_review: คลิปรีวิวลูกค้าจริง
    """
    style_map = {
        "holding_product": "Holding_Product",
        "product_usage": "Product_Usage",
        "ugc_review": "UGC_Review",
    }

    folder = style_map.get(style)
    if not folder:
        return {"error": f"Unknown style: {style}"}

    system = load_prompt(f"UGC_prompts/{folder}/system.prompt")
    master = load_prompt(f"UGC_prompts/{folder}/master.prompt")
    user_tpl = load_prompt(f"UGC_prompts/{folder}/user.template.prompt")
    file_negative = load_prompt(f"UGC_prompts/{folder}/negative.prompt")
    # Merge custom negative prompt on top of file-based one
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

    user_prompt = fill_template(user_tpl, user_data)
    system_full = f"{system}\n\n{negative}" if negative else system
    full_prompt = f"{system_full}\n\n{master}\n\n{user_prompt}"

    # Try LLM
    raw = _call_llm(system_full, f"{master}\n\n{user_prompt}")

    return {
        "style": style,
        "prompt": raw or full_prompt,
        "negative_prompt": negative,
        "merged_negative_prompt": negative,
        "product": product_name,
        "uses_llm": raw is not None,
    }


def get_script_variations() -> dict:
    """Get available script variations from AiBot config"""
    var = load_prompt("variation.json")
    try:
        return json.loads(var) if var else {}
    except json.JSONDecodeError:
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
