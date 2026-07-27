"""
TikTok UGC Studio — AI Script Generator
ใช้ AiBot Auto-Gen v4.5 prompt system + Gemini API
✨ PERSONA-AWARE — น้ำเสียงสอดคล้องกับ Persona ที่เลือกไว้
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

# ─── Import shared modules ──────────────────────────────────────────
_pb_path = _erp_stack / "prompt-builder-service"
if str(_pb_path) not in sys.path:
    sys.path.insert(0, str(_pb_path))

from shared_config import GEMINI_API_KEY
from persona_engine import PERSONA_TEMPLATES, _select_persona
from config import DEFAULT_DURATION

logger = logging.getLogger("tiktok-ugc.script_gen")

PROMPTS_DIR = Path(__file__).parent / "prompts"


# ═══════════════════════════════════════════════════════════════════════
# ─── Persona-Aware System Prompt Builder ────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

def build_script_system_prompt(persona: dict, duration: str = f"{DEFAULT_DURATION}s") -> str:
    """Build a persona-injected system prompt for Gemini script generation.
    
    Takes the persona dict (from persona_engine._select_persona()) and
    generates a system prompt layer that controls tone, voice, pacing and timing.
    
    Args:
        persona: dict from _select_persona()
        duration: "8s", "15s", or "16s"
    """
    persona_name = persona.get("vibe", "ทั่วไป").split(",")[0].strip()
    persona_age = persona.get("model_age", "25-35")
    speech_style = persona.get("speech_style", "พูดเป็นกันเอง ธรรมชาติ")
    pacing = persona.get("pacing", "ธรรมชาติ")
    forbidden = persona.get("forbidden_phrases", "")

    base = """คุณคือ Copywriter มืออาชีพที่เขียนสคริปต์โฆษณา UGC สั้นๆ สำหรับ TikTok
สคริปต์ต้องสั้น กระชับ เข้าใจง่าย เหมาะกับ Voiceover

[STRICT TONE & VOICE CONTROL]
ให้สวมบทบาทเป็นบุคคลที่มีบุคลิกดังนี้:
- ลักษณะ: {persona_name} (อายุช่วง {persona_age})
- รูปแบบการพูด: {speech_style}
- จังหวะการเล่าเรื่อง: {pacing}
- ข้อห้าม: {forbidden}

[OUTPUT FORMAT]
13 คำสั่งต่อไปนี้ STRICT มาก:
1. ภาษาไทยเท่านั้น ไม่มีภาษาอังกฤษปนเว้นแต่จำเป็น
2. ห้ามใส่เครื่องหมายวรรคตอนในสคริปต์หลัก (ห้าม . , ! ? " ")
3. ห้ามใช้ตัวเลข ห้ามใส่ emoji
4. ห้ามมีคำว่า Hook Value CTA หรือ [วงเล็บ]
5. ห้ามมีคำว่า "สวัสดี" "วันนี้" "เพื่อนๆ" "ทุกคน" "ครับ" ทุกต้นคลิป
6. ห้ามขึ้นต้นด้วยคำว่า ว่าไง/ว่าไงบ้าง/ว่าไงครับ
7. ห้ามบอกว่ากดติดตาม กดไลค์ กดแชร์ แชร์เลย คลิปนี้
8. ห้ามพูดถึงหัวข้อเดิมซ้ำ
9. ให้พูดเฉพาะเนื้อหาสินค้า ห้ามพูดนอกเรื่อง
10. ส่งออกเฉพาะสคริปต์เท่านั้น ห้ามมีคำอธิบายเพิ่มเติม
11. ตอบกลับด้วยสคริปต์ภาษาไทยที่พร้อมใช้วางใน TikTok Voiceover ทันที
12. ห้ามใช้ Hook Value CTA ในสคริปต์
13. ห้ามมีตัวเลขและ emoji ในสคริปต์เด็ดขาด"""

    base = base.format(
        persona_name=persona_name,
        persona_age=persona_age,
        speech_style=speech_style,
        pacing=pacing,
        forbidden=forbidden,
    )
    
    # ─── Append duration timing constraints ──────────────────────────
    # Normalize: "15" → "15s", "16" → "16s", "30" → "30s"
    dur_normalized = duration if duration.endswith("s") else f"{duration}s"
    if dur_normalized in ("15s", "16s", "30s"):
        base += adjust_prompt_for_duration(dur_normalized)
    
    return base


# ─── Gemini Config ─────────────────────────────────────────────────────────

# ─── Duration Timing Constraints ──────────────────────────────────────────

def adjust_prompt_for_duration(duration_type: str = "15s") -> str:
    """Return timing constraint prompt layer for longer videos."""
    if duration_type == "15s":
        return (
            "\\n[TIMING CONSTRAINT for 15 วินาที]"
            "\\n- สคริปต์ทั้งหมดต้องมีความยาวรวมกันประมาณ 45-55 คำ (ภาษาไทย) เพื่อให้พูดจบภายใน 15 วินาที"
            "\\n- ระยะเวลา 15 วินาทีให้ใช้คำพูด 45-55 คำเท่านั้น"
            "\\n- แบ่งเวลาเป็น 3-4 ช่วง ช่วงละ 3-5 วินาที"
            "\\n- ห้ามน้ำท่วมทุ่ง ให้เข้าประเด็นตามโครงสร้างที่กำหนด"
            "\\n- ห้ามมีเนื้อหาซ้ำหรืออธิบายยืดเยื้อ"
            "\\n- CTA ต้องสั้นและชัดเจนภายใน 2 วินาทีสุดท้าย"
        )
    elif duration_type == "30s":
        return (
            "\n[TIMING CONSTRAINT for 30 วินาที]"
            "\n- สคริปต์ทั้งหมดต้องมีความยาวรวมกันประมาณ 90-110 คำ (ภาษาไทย)"
            "\n- ระยะเวลา 30 วินาทีให้ใช้คำพูด 90-110 คำเท่านั้น"
            "\n- แบ่งเวลาเป็น 4-5 ช่วง ช่วงละ 5-7 วินาที"
            "\n- Hook 3-4 วินาทีแรก ติดเบ็ดให้อยู่"
            "\n- Content 18-20 วินาที อธิบายละเอียดกว่า 15s"
            "\n- CTA 3-4 วินาทีสุดท้าย ปิดการขายให้ชัดเจน"
            "\n- ห้ามยืดเนื้อหาเกินจำเป็น ให้กระชับในทุกช่วง"
        )
    elif duration_type == "16s":
        return (
            "\\n[TIMING CONSTRAINT for 16 วินาที]"
            "\\n- สคริปต์ทั้งหมดต้องมีความยาวรวมกันประมาณ 48-60 คำ (ภาษาไทย)"
            "\\n- ระยะเวลา 16 วินาทีให้ใช้คำพูด 48-60 คำเท่านั้น"
            "\\n- แบ่งเป็น Hook (3s), Value (10s), CTA (3s)"
            "\\n- ห้ามน้ำท่วมทุ่ง ให้เข้าประเด็นตามโครงสร้างที่กำหนด"
        )
    return ""
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
    duration: str = f"{DEFAULT_DURATION}s",
    extra_rules: str = "",
    persona: Optional[dict] = None,
    persona_category: str = "beauty",
    features: str = "",
    product_appearance: str = "",
    style: str = "review",
) -> dict:
    """Generate a TikTok UGC review script using AiBot prompts
    
    Args:
        product_name: ชื่อสินค้า
        customer_problem: ปัญหาที่สินค้าแก้
        main_benefit: ประโยชน์หลัก
        target_audience: กลุ่มเป้าหมาย
        tone: โทนเสียง (ถ้าไม่ระบุ จะใช้จาก persona)
        cta: คำกระตุ้นการซื้อ
        duration: ความยาวคลิป (8s/16s)
        extra_rules: กฎเพิ่มเติม
        persona: dict persona จาก persona_engine (ถ้า None จะสุ่มใหม่)
        persona_category: หมวดหมู่สำหรับสุ่ม persona (ถ้า persona=None)
    """
    # ─── Persona sync ──────────────────────────────────────────────────
    if persona is None:
        persona = _select_persona(persona_category, product_name)
    persona_name = persona.get("vibe", "ทั่วไป").split(",")[0].strip()
    
    # ─── Load prompts ─────────────────────────────────────────────────
    #      system_script_gen.prompt.txt = clean script-only rules
    #      system.prompt.txt (legacy)   = bloated (video rules mixed) — kept only for 16s
    #      master.prompt.txt            = video gen rules only — NOT loaded for script gen
    if style == "product_demo":
        # Product demo — เน้นอธิบายฟังก์ชัน ไม่มีโครงสร้าง CTA
        system = load_prompt("system_script_gen.prompt.txt")
        user_tpl = load_prompt("user_product_demo.prompt.txt")
    elif duration == "16s":
        # 16s still uses legacy prompts (separate fix later)
        system = load_prompt("system_16s.prompt.txt")
        user_tpl = load_prompt("user_16s.prompt.txt")
    else:
        # Review/UGC styles — user_review has timing structure for Hook/Value/CTA flow
        system = load_prompt("system_script_gen.prompt.txt")
        user_tpl = load_prompt("user_review.template.prompt.txt")

    # ─── Build user data ──────────────────────────────────────────────
    # tone จาก persona ถ้าไม่ override
    effective_tone = tone or persona_name
    
    user_data = {
        "product_name": product_name,
        "customer_problem": customer_problem or "ปัญหาที่พบเจอบ่อย",
        "main_benefit": main_benefit or "คุณภาพดี ใช้งานได้จริง",
        "target_audience": target_audience or "ทุกคนที่กำลังมองหา",
        "tone": effective_tone,
        "cta": cta or "กดดูในตะกร้าเลย",
        "extra_rules": extra_rules or "-",
        "features": features or "-",
        "product_appearance": product_appearance or "-",
    }

    user_prompt = fill_template(user_tpl, user_data)
    
    # ─── Build persona-aware system prompt ────────────────────────────
    persona_layer = build_script_system_prompt(persona, duration)
    combined_system = f"{persona_layer}\n\n{system}" if system else persona_layer

    # ─── Try LLM with persona injection ───────────────────────────────
    raw = _call_gemini(combined_system, user_prompt)

    if raw:
        return {
            "script": raw,
            "uses_llm": True,
            "duration": duration,
            "product": product_name,
            "persona": persona_name,
        }

    # Fallback: template-based script
    script = _template_script(user_data, duration)
    return {
        "script": script,
        "uses_llm": False,
        "duration": duration,
        "product": product_name,
        "persona": persona_name,
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
    persona: Optional[dict] = None,
) -> dict:
    """
    Generate UGC video prompt by style.
    If persona provided, also pass persona name in result for traceability.
    """
    style_map = {
        "holding_product": "Holding_Product",
        "product_usage": "Product_Usage",
        "ugc_review": "UGC_Review",
        "talking": "UGC_Review",
        "pov_lifehack": "POV_Lifehack",
        "asmr_texture": "ASMR_Texture",
        "split_comparison": "Split_Comparison",
        "street_interview": "Street_Interview",
        "greenscreen_react": "Greenscreen_React",
        "aesthetic_vlog": "Aesthetic_Vlog",
    }

    folder = style_map.get(style)
    if not folder:
        return {"error": f"Unknown style: {style}"}

    system = load_prompt(f"UGC_prompts/{folder}/system.prompt")
    master = load_prompt(f"UGC_prompts/{folder}/master.prompt")
    user_tpl = load_prompt(f"UGC_prompts/{folder}/user.template.prompt")
    file_negative = load_prompt(f"UGC_prompts/{folder}/negative.prompt")
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

    raw = _call_gemini(system_full, f"{master}\n\n{user_prompt}")

    result = {
        "style": style,
        "prompt": raw or f"{system_full}\n\n{master}\n\n{user_prompt}",
        "negative_prompt": negative,
        "merged_negative_prompt": negative,
        "product": product_name,
        "uses_llm": raw is not None,
    }
    if persona:
        persona_name = persona.get("vibe", "").split(",")[0].strip()
        result["persona"] = persona_name
    return result


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
    "15s": {
        "hook": ["เปิดด้วยคำถามลึก", "หยุดก่อนซื้อ", "ทำไมคนถึงเปลี่ยน"],
        "value": ["ขยายปัญหา", "อธิบายจุดต่าง", "เหตุผลที่เหนือกว่า"],
        "cta": ["เปลี่ยนเลยวันนี้", "ได้สิทธิพิเศษ", "กดลิงก์เลย"],
    },
    "16s": {
        "hook": ["เปิดเรื่อง", "ดึงดูดความสนใจ"],
        "value": ["อธิบายรายละเอียด", "บอกประโยชน์"],
        "cta": ["สรุป + เชิญชวน"],
    },
}
