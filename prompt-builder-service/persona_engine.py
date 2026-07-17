# ─── Persona Engine ─────────────────────────────────────────────
# Persona selection and injection for UGC diversity
# ═══════════════════════════════════════════════════════════════════════

import random
import logging
from typing import Dict, Optional

logger = logging.getLogger("prompt-builder-service")

PERSONA_TEMPLATES = {
    "energetic_young": {
        "model_age": "22-26",
        "vibe": "high energy, trendy, fast talker, Gen Z slang",
        "environment": "bedroom with led lights, trendy cafe",
        "lighting_variation": "neon pink/purple, bright indoor",
        "motion_speed": "fast, snappy cuts",
        "speech_style": "พูดเร็ว ใช้ศัพท์วัยรุ่น อินเทรนด์ มีมุก มีคำฮิต 'ออมายก็อด' 'จึ้ง' 'ปัง' 'ตัวแม่' 'แก'",
        "pacing": "เร็ว กระชับ ตื่นเต้น เปลี่ยนท่อนเร็ว",
        "forbidden_phrases": "ห้ามใช้ภาษาเป็นทางการ ห้ามใช้ 'ครับ/ค่ะ' มากเกินไป ห้ามพูดยืดยาว",
    },
    "calm_professional": {
        "model_age": "28-35",
        "vibe": "calm, authoritative, measured speech, professional",
        "environment": "modern office, clean white studio",
        "lighting_variation": "soft neutral, ring light style",
        "motion_speed": "slow, deliberate pans",
        "speech_style": "พูดชัด ฉะฉาน มีหลักการ ใช้ศัพท์วิชาการพอประมาณ น่าเชื่อถือ ใช้ 'ครับ/ค่ะ' สุภาพ",
        "pacing": "ช้า กลาง เน้นคำสำคัญ เว้นจังหวะให้ข้อมูลซึม",
        "forbidden_phrases": "ห้ามใช้ศัพท์วัยรุ่น ห้ามพูดเร็วเกินไป ห้ามใช้คำไม่เป็นทางการ",
    },
    "mom_at_home": {
        "model_age": "30-40",
        "vibe": "warm, relatable, busy mom energy",
        "environment": "home kitchen, living room with kids toys",
        "lighting_variation": "warm golden, natural window",
        "motion_speed": "natural, slightly rushed",
        "speech_style": "พูดกันเองเหมือนคุยกับเพื่อน บ่นบ้าง 'งานบ้านเยอะ' 'เวลาไม่พอ' 'เจอของดีมา' ใช้ภาษาไทยธรรมชาติ",
        "pacing": "ธรรมชาติ บางทีเร็วเพราะรีบ บางทีช้าเพราะกำลังทำอะไรไปด้วย",
        "forbidden_phrases": "ห้ามใช้ภาษาอังกฤษเยอะ ห้ามใช้ศัพท์ทางการ ห้ามพูดยืดเยื้อ",
    },
    "college_student": {
        "model_age": "19-23",
        "vibe": "casual, budget-conscious, honest reactions",
        "environment": "dorm room, campus, library",
        "lighting_variation": "cool fluorescent, mixed daylight",
        "motion_speed": "casual, natural hand gestures",
        "speech_style": "พูดตรงๆ ไม่ปรุงแต่ง 'คือแบบ...' '实话实说' ประหยัดตัง 'เดี๋ยวกูทดลองให้ดู'",
        "pacing": "ธรรมชาติ กึ่งช้า ไม่ต้องเร่ง ไม่ต้องเก่ง",
        "forbidden_phrases": "ห้ามโฆษณาชัดเกินไป ห้ามใช้ภาษาเชฟหรือผู้ใหญ่",
    },
    "minimalist_zen": {
        "model_age": "25-32",
        "vibe": "calm, aesthetic, slow living, premium feel",
        "environment": "minimalist room with plants, yoga space",
        "lighting_variation": "soft diffused, morning light",
        "motion_speed": "slow, graceful movements",
        "speech_style": "พูดช้า นุ่มนวล มีสมาธิ เน้น mindful 'ลองหายใจลึกๆ แล้วมาดูกัน' ใช้คำสวยๆ",
        "pacing": "ช้า มีพื้นที่ให้หายใจ แต่ละประโยคมีน้ำหนัก",
        "forbidden_phrases": "ห้ามพูดเร็ว ห้ามใช้คำตลาด ห้ามขายของตรงเกินไป",
    },
    "tech_enthusiast": {
        "model_age": "22-30",
        "vibe": "excited, gadget-focused, fast demo style",
        "environment": "desk with monitors, gaming setup",
        "lighting_variation": "RGB lighting, cool blue/white",
        "motion_speed": "fast, demonstrative",
        "speech_style": "พูดเร็ว ตื่นเต้นกับสเปค ใช้ศัพท์เทคนิค 'แรงม้าจัด' '60fps เนียนกริ๊บ' 'ชิปตัวนี้แรงกว่าเดิมเท่าตัว'",
        "pacing": "เร็ว เร้าใจ มีลูกเล่น ตื่นเต้นตลอดเวลา",
        "forbidden_phrases": "ห้ามใช้ภาษาเพ้อเจ้อ ห้ามไม่รู้เรื่องที่พูด ห้ามไม่ถูกต้องทางเทคนิค",
    },
}
def _select_persona(category: str, product_name: str = "") -> dict:
    import random
    cat_persona_map = {
        "beauty": ["energetic_young", "calm_professional", "mom_at_home", "minimalist_zen"],
        "electronics": ["tech_enthusiast", "college_student", "calm_professional"],
        "food": ["mom_at_home", "college_student", "energetic_young"],
        "fashion": ["energetic_young", "minimalist_zen", "calm_professional"],
        "home": ["mom_at_home", "minimalist_zen", "calm_professional"],
        "tools": ["calm_professional", "tech_enthusiast", "mom_at_home"],
        "health": ["calm_professional", "minimalist_zen", "energetic_young"],
    }
    pool = cat_persona_map.get(category, list(PERSONA_TEMPLATES.keys()))
    chosen = random.choice(pool)
    return PERSONA_TEMPLATES[chosen]


def _apply_persona_to_profile(profile: dict, persona: dict) -> dict:
    if persona.get("model_age"):
        profile["persona_age"] = persona["model_age"]
    if persona.get("vibe"):
        profile["persona_vibe"] = persona["vibe"]
    if persona.get("environment"):
        profile["setting"] = persona["environment"]
    if persona.get("lighting_variation"):
        profile["persona_lighting"] = persona["lighting_variation"]
    if persona.get("motion_speed"):
        profile["persona_motion"] = persona["motion_speed"]
    base_audience = profile.get("target_audience", "")
    if persona.get("vibe") and base_audience:
        profile["target_audience"] = f"{base_audience} -- {persona['vibe']}"
    return profile

