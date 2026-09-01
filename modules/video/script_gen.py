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
from prompt_builder import _tts_product_name

logger = logging.getLogger("tiktok-ugc.script_gen")

PROMPTS_DIR = Path(__file__).parent / "prompts"


# ═══════════════════════════════════════════════════════════════════════
# ─── Persona-Aware System Prompt Builder ────────────────────────────
# ═══════════════════════════════════════════════════════════════════════

def build_script_system_prompt(persona: dict, duration: str = f"{DEFAULT_DURATION}s", gender: str = "female", target_age: str = "") -> str:
    """Build a persona-injected system prompt for Gemini script generation.
    
    Takes the persona dict (from persona_engine._select_persona()) and
    generates a system prompt layer that controls tone, voice, pacing and timing.
    
    Args:
        persona: dict from _select_persona()
        duration: "8s", "15s", or "16s"
    """
    persona_name = persona.get("vibe", "ทั่วไป").split(",")[0].strip()
    persona_age = target_age
    speech_style = persona.get("speech_style", "พูดเป็นกันเอง ธรรมชาติ")
    pacing = persona.get("pacing", "ธรรมชาติ")
    forbidden = persona.get("forbidden_phrases", "")

    polite = "ค่ะ" if gender == "female" else "ครับ"
    wrong_polite = "ครับ" if gender == "female" else "ค่ะ"


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
5. ห้ามมีคำว่า "สวัสดี" "วันนี้" "เพื่อนๆ" "ทุกคน" ทุกต้นคลิป
6. ห้ามขึ้นต้นด้วยคำว่า ว่าไง/ว่าไงบ้าง/ว่าไงครับ
7. ห้ามบอกว่ากดติดตาม กดไลค์ กดแชร์ แชร์เลย คลิปนี้
8. ห้ามพูดถึงหัวข้อเดิมซ้ำ
8.5 พูดชื่อสินค้าได้ครั้งเดียวเท่านั้น (ตอนเปิด/แนะนำตัว) เรื่องต่อๆ ไปห้ามเอ่ยชื่อสินค้าซ้ำอีก และห้ามใช้คำแทนชื่อ เช่น ตัวนี้/เจ้านี้/ตัวนี้เลย ห้ามใส่ทุกกรณี — ให้พูดประโยคต่อไปโดยไม่ต้องอ้างชื่อหรือประธานเดิมซ้ำ
9. ให้พูดเฉพาะเนื้อหาสินค้า ห้ามพูดนอกเรื่อง
10. ส่งออกเฉพาะสคริปต์เท่านั้น ห้ามมีคำอธิบายเพิ่มเติม
11. ตอบกลับด้วยสคริปต์ภาษาไทยที่พร้อมใช้วางใน TikTok Voiceover ทันที
12. ห้ามใช้ Hook Value CTA ในสคริปต์
13. ห้ามมีตัวเลขและ emoji ในสคริปต์เด็ดขาด
14. ใช้คำลงท้ายว่า "{polite}" เท่านั้น ห้ามใช้ "{wrong_polite}" โดยเด็ดขาด"""

    base = base.format(
        persona_name=persona_name,
        persona_age=persona_age,
        speech_style=speech_style,
        pacing=pacing, polite=polite, wrong_polite=wrong_polite,
        forbidden=forbidden,
    )
    
    # ─── Append duration timing constraints ──────────────────────────
    # Normalize: "15" → "15s", "16" → "16s", "30" → "30s"
    dur_normalized = duration if duration.endswith("s") else f"{duration}s"
    if dur_normalized in ("8s", "10s", "12s", "15s", "16s", "30s"):
        base += adjust_prompt_for_duration(dur_normalized)
    
    return base


# ─── Gemini Config ─────────────────────────────────────────────────────────

# ─── Duration Timing Constraints ──────────────────────────────────────────

def adjust_prompt_for_duration(duration_type: str = "15s") -> str:
    """Return timing constraint prompt layer for all durations."""
    dur = duration_type if duration_type.endswith("s") else f"{duration_type}s"

    if dur == "8s":
        return (
            "\n[TIMING CONSTRAINT for 8 วินาที]"
            "\n- สคริปต์ทั้งหมดต้องมีความยาวรวมกันประมาณ 22-28 คำ (ภาษาไทย) เพื่อให้พูดจบภายใน 8 วินาที"
            "\n- ระยะเวลา 8 วินาทีให้ใช้คำพูด 22-28 คำเท่านั้น"
            "\n- แบ่งเป็น Hook (2s), Value (4s), CTA (2s)"
            "\n- ห้ามน้ำท่วมทุ่ง ให้เข้าประเด็น"
            "\n- CTA ต้องสั้นและชัดเจนภายใน 2 วินาทีสุดท้าย"
        )
    elif dur == "10s":
        return (
            "\n[TIMING CONSTRAINT for 10 วินาที]"
            "\n- สคริปต์ทั้งหมดต้องมีความยาวรวมกันประมาณ 30-37 คำ (ภาษาไทย) เพื่อให้พูดจบภายใน 10 วินาที"
            "\n- ระยะเวลา 10 วินาทีให้ใช้คำพูด 30-37 คำเท่านั้น"
            "\n- แบ่งเป็น Hook (2s), Value (6s), CTA (2s)"
            "\n- Hook ต้องจั๊วะหนึ่ง น่าสนใจภายใน 2 วิ"
            "\n- CTA ต้องสั้นและชัดเจนภายใน 2 วินาทีสุดท้าย"
        )
    elif dur == "12s":
        return (
            "\n[TIMING CONSTRAINT for 12 วินาที]"
            "\n- สคริปต์ทั้งหมดต้องมีความยาวรวมกันประมาณ 28-34 คำ (ภาษาไทย) เพื่อให้พูดจบภายใน 12 วินาที"
            "\n- ระยะเวลา 12 วินาทีให้ใช้คำพูด 28-34 คำเท่านั้น"
            "\n- ใช้ feature แค่ 2-4 จุดเด่นที่สำคัญที่สุดเท่านั้น ห้ามใส่ทุก spec"
            "\n- ตัดส่วน Problem ที่ยืดเยื้อออก ให้เข้าประเด็นเร็ว"
            "\n- ใช้คำพูดสั้น กระชับ ไม่มีคำฟุ่มเฟือย"
            "\n- แบ่งเป็น Hook (3s), Value (6s), CTA (3s)"
            "\n- Hook ต้องดึงดูด จบภายใน 3 วิ"
            "\n- CTA ต้องสั้นและชัดเจนภายใน 3 วินาทีสุดท้าย"
        )
    elif dur == "15s":
        return (
            "\n[TIMING CONSTRAINT for 15 วินาที]"
            "\n- สคริปต์ทั้งหมดต้องมีความยาวรวมกันประมาณ 45-55 คำ (ภาษาไทย) เพื่อให้พูดจบภายใน 15 วินาที"
            "\n- ระยะเวลา 15 วินาทีให้ใช้คำพูด 45-55 คำเท่านั้น"
            "\n- แบ่งเวลาเป็น 3-4 ช่วง ช่วงละ 3-5 วินาที"
            "\n- ห้ามน้ำท่วมทุ่ง ให้เข้าประเด็นตามโครงสร้างที่กำหนด"
            "\n- ห้ามมีเนื้อหาซ้ำหรืออธิบายยืดเยื้อ"
            "\n- CTA ต้องสั้นและชัดเจนภายใน 2 วินาทีสุดท้าย"
        )
    elif dur == "16s":
        return (
            "\n[TIMING CONSTRAINT for 16 วินาที]"
            "\n- สคริปต์ทั้งหมดต้องมีความยาวรวมกันประมาณ 48-60 คำ (ภาษาไทย)"
            "\n- ระยะเวลา 16 วินาทีให้ใช้คำพูด 48-60 คำเท่านั้น"
            "\n- แบ่งเป็น Hook (3s), Value (10s), CTA (3s)"
            "\n- ห้ามน้ำท่วมทุ่ง ให้เข้าประเด็นตามโครงสร้างที่กำหนด"
        )
    elif dur == "30s":
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
    return ""
def _call_gemini(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call Gemini API for script generation."""
    api_key = GEMINI_API_KEY()
    if not api_key:
        logger.error("No GEMINI_API_KEY configured — cannot generate script")
        raise RuntimeError("No GEMINI_API_KEY configured")

    try:
        import httpx
        gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {
                "temperature": 0.6,
                # Gemini 3.6-flash ใช้ thoughtsTokenCount ที่สูงมากและหักออกจาก maxOutputTokens
                # (วัดจริง ~1100-3000 token เฉพาะคิด) → ต้องตั้ง maxOutputTokens ให้สูงพอ (~4096)
                # ไม่งั้นเหลือ text budget แค่ ~20-90 token → บทสั้น/ถูกตัดกลางเสมอ (root cause "แก้ไม่หาย")
                "maxOutputTokens": 4096,
            },
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

import re

def _brand_tokens(product_name: str):
    """Split product name into normalized tokens so Thai & English versions of the
    SAME brand are treated as ONE name (e.g. ครีมสกินชี ↔ Skinshe / กลูต้า ↔ GLUTA).

    Returns a list of tuples (token, norm) where norm is a case/space folded key.
    Thai tokens are kept as-is; Latin tokens are lowercased and stripped of
    diacritics so Skinshe/skinshe/SKIN-SHE all collapse to one key.
    """
    import unicodedata
    toks = []
    for raw in re.split(r"[\s\[\]()/\\,.:;|\-]+", product_name):
        w = raw.strip()
        if not w:
            continue
        # drop pure-unit/size noise (เซต, ชิ้น, 1, มี, สี, size, ml, g ฯลฯ)
        if re.fullmatch(r"(เซต|ชิ้น|มี|แถม|ขนาด|ใหม่|เจน|รุ่น|สี|แพ็ค|แพ็ก|set|pack|box|ml|g|gift|giftexeat|ครีม|cream)?", w, re.I):
            continue
        if w.isdigit():
            continue
        latin = bool(re.search(r"[A-Za-z]", w))
        if latin:
            norm = unicodedata.normalize("NFKD", w.lower())
            norm = re.sub(r"[^a-z0-9]", "", norm)
        else:
            norm = re.sub(r"[^\u0E00-\u0E7F0-9]", "", w)  # Thai keep
        if norm:
            toks.append((w, norm))
    return toks


def _dedupe_product_name(script: str, product_name: str) -> str:
    """Owner directive (2026-08-23): the product name is spoken at most ONCE.

    The script ALREADY establishes the subject/production early (e.g. "ครีมสกินชี..."
    or "Skinshe Gifteset..."), so there is no reason to name it again later. After
    the first mention we simply DROP further mentions (do NOT substitute "ตัวนี้")
    so later clauses just proceed without re-referencing the product.

    Thai & English variants of the same brand are folded to a single token so a
    mixed name (ครีมสกินชี Skinshe Gifteset Cream) never slips a duplicate past.
    """
    if not product_name or not script:
        return script
    toks = _brand_tokens(product_name)
    if not toks:
        return script
    # Find first occurrence across all normalized variants → keep the longest match
    hits = []
    for tok, norm in toks:
        idx = script.lower().find(norm) if norm.isascii() else script.find(tok)
        if idx != -1:
            hits.append((idx, len(tok), tok, norm))
    if not hits:
        return script
    hits.sort(key=lambda h: (h[0], -h[1]))  # earliest, then longest
    first_idx, first_len, first_tok, first_norm = hits[0]
    result = script[:first_idx + first_len]
    rest = script[first_idx + first_len:]
    # Remove every later mention (Thai or Latin) instead of replacing with ตัวนี้
    for tok, norm in toks:
        if norm.isascii():
            # avoid over-stripping: only drop word-boundary matches of the latin token
            rest = re.sub(r"(^|[^A-Za-z0-9])%s(?=[^A-Za-z0-9]|$)" % re.escape(norm), r"\1", rest, flags=re.I)
        else:
            rest = rest.replace(tok, "")
    # collapse doubled spaces left by removals + tidy leftover connectors
    rest = re.sub(r"\s{2,}", " ", rest)
    # a removed token left a connector glued to the previous word + a gap
    # e.g. "ครีมสกินชีและ Skinshe ทั้งสอง" → after cut → "สกินชีและ  ทั้งสอง"
    rest = re.sub(r"(และ|หรือ|กับ)\s{1,}", r" \1", rest)   # "และ  ทั้ง" → " และ ทั้ง"
    # remove a dangling connector that now floats right after the kept token
    # e.g. "สกินชี และ ทั้งสอง" (the listed item was cut) → drop the connector too
    rest = re.sub(r"\s+(และ|หรือ|กับ)\s+", r" ", rest)
    rest = re.sub(r"(และ|หรือ|กับ)\s*$", "", rest)
    return (result + rest).strip()


def _count_thai_words(text: str) -> int:
    """Approximate number of Thai 'words' in a script for timing validation.

    Thai has no spaces between words, so splitting on whitespace is useless
    (a whole clause collapses into 1 token). Instead we approximate the word
    count by total Thai characters / 3 — Thai words average ~3 graphemes
    (consonant + vowel + tone mark). Good enough to ENFORCE "don't run long".
    Counts only Thai graphemes; ignores spaces, latin, punctuation, digits.
    """
    if not text:
        return 0
    thai_chars = re.sub(r"[^\u0E00-\u0E7F]", "", text)
    if not thai_chars:
        return 0
    return max(1, len(thai_chars) // 3)



def _duration_word_range(duration: str) -> tuple:
    """Return (min, max) Thai-word budget for a duration string like '15s'."""
    dur = duration if duration.endswith("s") else f"{duration}s"
    # These bounds are in the "approx Thai words" scale produced by
    # _count_thai_words (total Thai chars // 3). 15s ≈ 45-55 words ≈ 135-165 chars.
    table = {
        "8s": (22, 28),
        "10s": (30, 37),
        "12s": (28, 34),
        "15s": (45, 55),
        "16s": (48, 60),
        "30s": (90, 110),
    }
    return table.get(dur, (45, 55))


def _timing_structure_for_duration(duration: str) -> str:
    """Return a Thai per-section timing guideline for a given duration string.
    The user template consumes this so it isn't hard-wired to 8s. Each line keeps
    the natural UGC flow (Hook/Problem → Value/Spec → CTA) without forcing the
    'ตัวนี้' pronoun (product name is spoken once in the VALUE part)."""
    dur = duration if duration.endswith("s") else f"{duration}s"
    table = {
        "8s": "Hook 0-2 วิ / Value 2-6 วิ / CTA 6-8 วิ",
        "10s": "Hook 0-2 วิ / Value 2-8 วิ / CTA 8-10 วิ",
        "12s": "Hook 0-3 วิ / Value 3-9 วิ / CTA 9-12 วิ",
        "15s": "Hook 0-3 วิ / Value 3-12 วิ / CTA 12-15 วิ",
        "16s": "Hook 0-3 วิ / Value 3-13 วิ / CTA 13-16 วิ",
        "30s": "Hook 0-4 วิ / Value 4-24 วิ / CTA 24-30 วิ",
    }
    return table.get(dur, table["15s"])



def _trim_script_by_sentences(text: str, max_words: int) -> str:
    """Safety trim: drop whole trailing clauses (split on 。.!? and Thai เw/ ) until
    the Thai word count is within budget. NEVER cuts mid-word — only drops whole
    trailing sentences. Used only if a retry still comes back too long."""
    if _count_thai_words(text) <= max_words:
        return text
    # split into clauses on common sentence enders (keep delimiter attached)
    parts = re.split(r"(?<=[。.!?！？])\s+|\s+(?=และ|หรือ|แล้ว|จากนั้น)", text)
    kept = []
    for p in parts:
        if _count_thai_words(" ".join(kept) + " " + p) > max_words:
            break
        kept.append(p)
    return " ".join(kept).strip()


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
    gender: str = "female",
    target_age: str = "",
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
        # 16s: use unified script gen prompt (cleaned of video gen pollution)
        system = load_prompt("system_script_gen.prompt.txt")
        user_tpl = load_prompt("user_16s.prompt.txt")
    else:
        # Review/UGC styles — user_review has timing structure for Hook/Value/CTA flow
        system = load_prompt("system_script_gen.prompt.txt")
        user_tpl = load_prompt("user_review.template.prompt.txt")

    # ─── Build user data ──────────────────────────────────────────────
    # tone จาก persona ถ้าไม่ override
    # 🔴 FIX (owner 2026-08-29): ทับศัพท์ product_name/features เป็นไทยล้วน
    # ก่อนส่งเข้า Gemini ไม่งั้น Gemini ทิ้ง raw อังกฤษ (SPF50+ PA++++ 50g)
    # ไว้ในบท — ต้องแปลงเป็นไทยพูดได้หมดก่อนไพลเมไป template
    _pn_thai = _tts_product_name(product_name)
    _feat_thai = _tts_product_name(features) if features else "-"
    effective_tone = tone or persona_name
    
    user_data = {
        "product_name": _pn_thai or product_name,
        "customer_problem": customer_problem or "ปัญหาที่พบเจอบ่อย",
        "main_benefit": main_benefit or "คุณภาพดี ใช้งานได้จริง",
        "target_audience": target_audience or "ทุกคนที่กำลังมองหา",
        "tone": effective_tone,
        "cta": cta or "กดดูในตะกร้าเลย",
        "extra_rules": extra_rules or "-",
        "features": _feat_thai or "-",
        "product_appearance": product_appearance or "-",
        "timing_structure": _timing_structure_for_duration(duration),
    }

    user_prompt = fill_template(user_tpl, user_data)
    
    # ─── Build persona-aware system prompt ────────────────────────────
    persona_layer = build_script_system_prompt(persona, duration, gender=gender, target_age=target_age)
    combined_system = f"{persona_layer}\n\n{system}" if system else persona_layer

    # ─── Try LLM with persona injection ───────────────────────────────
    raw = _call_gemini(combined_system, user_prompt)

    # ─── Length control (owner 2026-09-01): don't trust Gemini to self-limit. ──
    # Validate Thai word budget AFTER generation. If over OR under, retry ONCE with
    # an explicit instruction (shorter / write fuller with Value+spec+CTA); if still
    # over, safety-trim by whole trailing sentences (never mid-word). Keeps the
    # spoken script inside the cut-time of the video so Wan/TTS doesn't run over.
    _lo, _hi = _duration_word_range(duration)
    if raw:
        _wc = _count_thai_words(raw)
        if _wc > _hi:
            _shrink_hint = (f"สคริปต์ที่ให้มายาวเกิน ({_wc} คำ) แต่ต้องได้ {_lo}-{_hi} คำสำหรับ {duration} "
                            f"กรุณาตัดให้สั้นลงเหลือ {_lo}-{_hi} คำ โดยตัดเนื้อหาส่วนท้าย/ส่วนซ้ำออก "
                            "ห้ามตัดกลางคำ ห้ามลัดทับศัพท์ชื่อสินค้า ให้คงชื่อสินค้าไว้")
            _user_retry = user_prompt + f"\n\n[{_shrink_hint}]"
            logger.info(f"Script over budget ({_wc}>{_hi}) — retrying once shorter")
            raw2 = _call_gemini(combined_system, _user_retry)
            if raw2 and _count_thai_words(raw2) <= _hi:
                raw = raw2
                _wc = _count_thai_words(raw)
            else:
                # retry still over/no output → safety trim whole trailing sentences
                trimmed = _trim_script_by_sentences(raw2 or raw, _hi)
                if trimmed:
                    raw = trimmed
                    _wc = _count_thai_words(raw)
                    logger.info(f"Safety-trimmed script to {_wc} words")
        elif _wc < _lo:
            # Too short / likely Gemini truncated early (only the hook/problem).
            # Retry once telling it to WRITE THE FULL script with all 3 sections.
            _full_hint = (
                f"สคริปต์ที่ให้มาสั้นเกินไป ({_wc} คำ) แต่ต้องได้ {_lo}-{_hi} คำสำหรับ {duration} และต้องครบ 3 ส่วน "
                "(เริ่มด้วยปัญหา/ปัญหาที่เจอ, แล้วแนะนำชื่อสินค้าหนึ่งครั้งพร้อมจุดเด่นและ spec จริงจากคุณสมบัติสินค้า, "
                "จบด้วยคำกระตุ้นให้ซื้อ) อย่าเพิ่งจบแค่ประโยคเดียว ให้เขียนบทโฆษณาที่สมบูรณ์ตามระยะเวลาคลิป โดยไม่ใช้คำแทนชื่อสินค้า"
            )
            _user_retry = user_prompt + f"\n\n[{_full_hint}]"
            logger.info(f"Script too short ({_wc}<{_lo}) — retrying once fuller")
            raw2 = _call_gemini(combined_system, _user_retry)
            if raw2:
                raw = raw2
                _wc = _count_thai_words(raw)


    if raw:
        # Post-process: พูดชื่อสินค้าแค่ครั้งเดียว (ครั้งแรก) ครั้งที่เหลือแทนด้วยสรรพนาม
        script = _dedupe_product_name(raw, product_name)
        return {
            "script": script,
            "uses_llm": True,
            "duration": duration,
            "product": product_name,
            "persona": persona_name,
        }

    # No fallback — fail fast
    raise RuntimeError("Script generation failed: no content returned from Gemini")


