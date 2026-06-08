"""Content template generator — creates clone-ready video scripts and structure."""
import json
import logging
from typing import Optional, List, Dict
from datetime import datetime, timezone

logger = logging.getLogger("scout.templates")

TEMPLATE_LIBRARY = {
    "problem_solution": {
        "name": "Problem → Solution",
        "category": "product_review",
        "structure": [
            {"part": "Hook", "duration_sec": 3, "script_template": "คุณ{problem_verb} {problem} อยู่ใช่ไหม?"},
            {"part": "Agitate", "duration_sec": 4, "script_template": "มัน{agitation} ใช่ไหม? {agitation_detail}"},
            {"part": "Introduce", "duration_sec": 5, "script_template": "วันนี้ผม/ฉันมี{product}มาแนะนำ"},
            {"part": "Benefit", "duration_sec": 8, "script_template": "สิ่งนี้{benefit_1} และยัง{benefit_2}"},
            {"part": "Demo", "duration_sec": 5, "script_template": "ดูนี่ครับ/คะ — {demo_text}"},
            {"part": "CTA", "duration_sec": 3, "script_template": "{cta_text}"},
        ],
    },
    "before_after": {
        "name": "Before → After Transformation",
        "category": "before_after",
        "structure": [
            {"part": "Visual Hook", "duration_sec": 2, "script_template": "นี่คือสภาพ{before_subject}ของฉัน"},
            {"part": "Problem Setup", "duration_sec": 3, "script_template": "มัน{problem_description}มาก"},
            {"part": "Transition", "duration_sec": 1, "script_template": "แต่แล้ว..."},
            {"part": "After Reveal", "duration_sec": 5, "script_template": "หลังจากใช้{product} {result_text}"},
            {"part": "Benefit", "duration_sec": 4, "script_template": "เห็นความแตกต่างไหม? {benefit_text}"},
            {"part": "CTA", "duration_sec": 3, "script_template": "{cta_text}"},
        ],
    },
    "quick_review": {
        "name": "Quick Fire Review",
        "category": "product_review",
        "structure": [
            {"part": "Hook", "duration_sec": 2, "script_template": "{product} — {verdict}!"},
            {"part": "Rating", "duration_sec": 3, "script_template": "ให้คะแนน {rating}/10"},
            {"part": "Pros", "duration_sec": 5, "script_template": "ข้อดี: {pro_1}, {pro_2}, {pro_3}"},
            {"part": "Cons", "duration_sec": 4, "script_template": "ข้อเสีย: {con_1}"},
            {"part": "Price Check", "duration_sec": 3, "script_template": "ราคา {price} — {value_judgment}"},
            {"part": "CTA", "duration_sec": 2, "script_template": "{cta_text}"},
        ],
    },
    "comparison": {
        "name": "Side-by-Side Comparison",
        "category": "comparison",
        "structure": [
            {"part": "Hook", "duration_sec": 3, "script_template": "{product_a} vs {product_b} — อันไหนดีกว่ากัน?"},
            {"part": "Criteria 1", "duration_sec": 4, "script_template": "ด้าน{criterion_1}: {a_score} vs {b_score}"},
            {"part": "Criteria 2", "duration_sec": 4, "script_template": "ด้าน{criterion_2}: {a_score} vs {b_score}"},
            {"part": "Criteria 3", "duration_sec": 4, "script_template": "ด้าน{criterion_3}: {a_score} vs {b_score}"},
            {"part": "Winner", "duration_sec": 3, "script_template": "สรุป: {winner} ชนะเพราะ{reason}"},
            {"part": "CTA", "duration_sec": 2, "script_template": "{cta_text}"},
        ],
    },
    "testimonial": {
        "name": "Customer Testimonial",
        "category": "testimonial",
        "structure": [
            {"part": "Hook", "duration_sec": 3, "script_template": "ก่อนใช้{product} {before_struggle}"},
            {"part": "Discovery", "duration_sec": 4, "script_template": "แล้วฉันก็เจอ{product} โดย{discovery_method}"},
            {"part": "Experience", "duration_sec": 6, "script_template": "สิ่งที่เกิดขึ้นคือ{experience_result}"},
            {"part": "Result", "duration_sec": 5, "script_template": "ตอนนี้{result_happy}"},
            {"part": "Recommendation", "duration_sec": 4, "script_template": "ถ้าคุณ{condition} {recommendation}"},
            {"part": "CTA", "duration_sec": 3, "script_template": "{cta_text}"},
        ],
    },
}


async def get_templates(category: str = "") -> List[Dict]:
    """List available content templates, optionally filtered by category."""
    results = []
    for tid, tpl in TEMPLATE_LIBRARY.items():
        if category and tpl["category"] != category:
            continue
        results.append({
            "id": tid,
            "name": tpl["name"],
            "category": tpl["category"],
            "parts_count": len(tpl["structure"]),
            "total_duration_sec": sum(p["duration_sec"] for p in tpl["structure"]),
        })
    return results


async def generate_from_template(
    template_id: str,
    product_name: str,
    price: str = "",
    fill_values: Optional[Dict[str, str]] = None,
    cta: str = "กด link in bio",
) -> Optional[Dict]:
    """Generate a full video script from a template with filled values."""
    tpl = TEMPLATE_LIBRARY.get(template_id)
    if not tpl:
        return None

    if fill_values is None:
        fill_values = {}

    # Default fill values
    defaults = {
        "product": product_name,
        "price": price or "฿XXX",
        "cta_text": cta or "กด link in bio",
        "problem_verb": "เจอ",
        "problem": "ปัญหา",
        "agitation": "น่าเบื่อ",
        "agitation_detail": "เสียเวลาทั้งเงินทั้งเวลา",
        "benefit_1": "ช่วยประหยัดเวลา",
        "benefit_2": "ได้ผลดีกว่าที่เคยใช้",
        "demo_text": "มันทำงานยังไง? ง่ายมาก...",
        "before_subject": "ห้อง",
        "problem_description": "รก เก็บของไม่เป็นระเบียบ",
        "result_text": "ทุกอย่างเปลี่ยนไป!",
        "benefit_text": "สะอาด เป็นระเบียบ เรียบร้อยขึ้น 100%",
        "rating": "9",
        "verdict": "คุ้มมาก",
        "pro_1": "ใช้งานง่าย",
        "pro_2": "คุณภาพดี",
        "pro_3": "คุ้มค่า",
        "con_1": "ราคาสูงไปนิด",
        "value_judgment": "คุ้มค่าแก่การลงทุน",
        "product_a": "Product A",
        "product_b": "Product B",
        "criterion_1": "ราคา",
        "criterion_2": "คุณภาพ",
        "criterion_3": "บริการ",
        "a_score": "8/10",
        "b_score": "7/10",
        "winner": "Product A",
        "reason": "คุ้มค่าและใช้งานง่ายกว่า",
        "before_struggle": "เป็นคนที่ทุกข์ทรมานมาก",
        "discovery_method": "บังเอิญเจอใน TikTok",
        "experience_result": "ชีวิตง่ายขึ้นมาก",
        "result_happy": "ไม่คิดว่าจะดีขนาดนี้",
        "condition": "กำลังมองหาสิ่งที่ดีกว่า",
        "recommendation": "แนะนำให้ลองเลย",
    }

    # Merge user-provided values
    values = {**defaults, **(fill_values or {})}

    # Build script
    script_parts = []
    for i, part in enumerate(tpl["structure"]):
        try:
            text = part["script_template"].format(**values)
        except KeyError:
            text = part["script_template"]
        script_parts.append({
            "order": i + 1,
            "part": part["part"],
            "duration_sec": part["duration_sec"],
            "text": text,
        })

    total_duration = sum(p["duration_sec"] for p in script_parts)

    return {
        "template_id": template_id,
        "template_name": tpl["name"],
        "category": tpl["category"],
        "product": product_name,
        "script_parts": script_parts,
        "total_duration_sec": total_duration,
        "full_text": " ".join(p["text"] for p in script_parts),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def generate_clone_script(
    source_template_id: str,
    product_name: str,
    fill_values: Optional[Dict[str, str]] = None,
) -> Optional[Dict]:
    """Generate a 'clone' script — same structure as a trending template, applied to a new product."""
    return await generate_from_template(source_template_id, product_name, fill_values=fill_values)
