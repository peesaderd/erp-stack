"""
TikTok UGC Studio — AI Script Generator
ใช้ AiBot Auto-Gen v4.5 prompt system + LLM API
"""

import os
import json
import logging
import random
import sys
from pathlib import Path
from typing import Optional

_erp_stack = Path(__file__).parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))
from shared_config import GEMINI_API_KEY

logger = logging.getLogger("tiktok-ugc.script_gen")

PROMPTS_DIR = Path(__file__).parent / "prompts"

# ─── Gemini Config ─────────────────────────────────────────────────────────

def _call_gemini(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call Gemini API for script generation."""
    api_key = GEMINI_API_KEY()
    if not api_key:
        logger.warning("No GEMINI_API_KEY configured — using template fallback")
        return None

    try:
        import httpx
        gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2000},
        }
        resp = httpx.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        else:
            logger.warning(f"Gemini API error ({resp.status_code}): {resp.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
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

    # Try LLM
    raw = _call_gemini(system, f"{master}\n\n{user_prompt}")

    if raw:
        return {
            "script": raw,
            "uses_llm": True,
            "duration": duration,
            "product": product_name,
        }

    # Fallback: template-based script
    script = _template_script(user_data, duration)
    return {
        "script": script,
        "uses_llm": False,
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
    raw = _call_gemini(system_full, f"{master}\n\n{user_prompt}")

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
