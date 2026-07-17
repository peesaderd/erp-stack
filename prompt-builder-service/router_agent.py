#!/usr/bin/env python3
"""
Router Agent — Gemini-Powered Content Strategy Picker
=====================================================
อ่านข้อมูลสินค้า (ชื่อ, ราคา, รูป) → ตัดสินใจ recipe, style, duration, persona
→ ส่งออก JSON config ให้ Orchestrator ใช้ต่อ

Zero hardcoded rules — ให้ Gemini ใช้ความฉลาดเลือกเองทั้งหมด
"""

import json
import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger("router-agent")

# ─── Default fallback ──────────────────────────────────────────────────
FALLBACK_CONFIG = {
    "recipe_type": "pas",
    "duration": "8s",
    "visual_style": "usage",
    "persona": "gen_z_trendy",
    "scenes": [
        {"id": "hook", "duration": 1.6, "purpose": "เปิดด้วยปัญหา"},
        {"id": "agitate", "duration": 2.4, "purpose": "ขยายปัญหา"},
        {"id": "solve", "duration": 2.8, "purpose": "เสนอสินค้า"},
        {"id": "cta", "duration": 1.2, "purpose": "CTA"},
    ],
}


def _call_gemini_router(system_prompt: str, user_prompt: str) -> Optional[str]:
    """Call Gemini API for router decision. Returns raw JSON text."""
    from gemini_client import _call_gemini
    return _call_gemini(system_prompt, user_prompt)


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from Gemini response."""
    if not text:
        return None
    # Try to find JSON block
    json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if json_match:
        text = json_match.group(1).strip()
    # Try parsing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find {...} block
    brace_match = re.search(r'\{[\s\S]*\}', text)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass
    return None


def _build_router_prompt() -> str:
    """Return system prompt for the router agent."""
    return """คุณคือผู้เชี่ยวชาญการตลาด TikTok ระดับสูง ที่เข้าใจพฤติกรรมผู้บริโภคและเทรนด์วิดีโอ

[หน้าที่]
วิเคราะห์สินค้าที่ได้รับ (รูปภาพ + ชื่อ + คำอธิบาย) แล้วตัดสินใจว่า 
ควรใช้ Content Structure แบบไหนถึงจะขายสินค้านี้ได้ปังที่สุดบน TikTok

[ตัวเลือก Recipe]
1. "pas" — Problem → Agitate → Solve: สำหรับสินค้าที่แก้ปัญหาเฉพาะ (skincare, สุขภาพ, ของใช้ในบ้าน)
2. "comparison" — Us vs Them: สำหรับสินค้าที่เหนือกว่าคู่แข่งชัดเจน (tech, อุปกรณ์, แฟชั่น)
3. "secret_hook" — Secret/Gatekeeping: สำหรับสินค้าที่น่าสนใจ/เทรนดี้ (อาหาร, แฟชั่น, ความงาม)

[ตัวเลือก Duration]
- "8s" — สั้น เร็ว เข้าใจง่าย (สินค้าทั่วไป)
- "15s" — ต้องอธิบายเพิ่ม มีหลายประเด็น (skincare ที่ต้องอธิบายวิธีใช้, อุปกรณ์ซับซ้อน)

[ตัวเลือก Visual Style]
- "holding" — ถือสินค้าเฉยๆ พรีเซ็นต์ตรงๆ
- "usage" — โชว์การใช้จริง
- "review" — เหมือนรีวิว พูดคุยกับกล้อง
- "pov_lifehack" — แฮ็กชีวิต มุมมองคนใช้
- "asmr_texture" — โฟกัสที่ texture/สัมผัส
- "split_comparison" — จอแบ่งครึ่ง Before/After
- "street_interview" — เหมือนสัมภาษณ์ข้างถนน
- "greenscreen_react" — พูดหน้าจอเขียว มี overlay
- "aesthetic_vlog" — ภาพสวย เหมือน Vlog

[ตัวเลือก Persona]
- "busy_mom" — แม่บ้าน ต้องการความสะดวก ไม่มีเวลา
- "gen_z_trendy" — วัยรุ่น ชอบของเทรนด์ ภาษาแรง
- "calm_professional" — คนทำงาน พูดน่าเชื่อถือ
- "aesthetic_minimalist" — สายมินิมอล ภาพสวย หรู
- "gen_x_practical" — วัยทำงานปลาย ต้องการของคุ้มค่า
- "fitness_enthusiast" — สายออกกำลังกาย สุขภาพ

[กฎสำคัญ]
1. ดูรูปสินค้าให้ดี — วิเคราะห์ packaging, ลักษณะ, กลุ่มเป้าหมาย
2. เลือกให้เหมาะกับ PRODUCT จริง — ไม่ใช่แค่ type
3. ถ้าสินค้าต้องอธิบาย → 15s + PAS
4. ถ้าสินค้ามีคู่แข่งชัด → comparison
5. ถ้าสินค้าเทรนดี้/น่าสนใจ → secret_hook
6. ส่ง JSON เท่านั้น ไม่มีคำอธิบายเพิ่ม
7. ห้ามส่ง Markdown หรือ code block"""


def _build_user_prompt(
    product_name: str,
    description: str = "",
    price: Optional[float] = None,
    image_available: bool = False,
    keywords: Optional[list] = None,
) -> str:
    """Build user prompt for router."""
    parts = [f"ชื่อสินค้า: {product_name}"]
    if description:
        parts.append(f"คำอธิบาย: {description}")
    if price:
        parts.append(f"ราคา: {price} บาท")
    if keywords:
        parts.append(f"คีย์เวิร์ด: {', '.join(keywords[:10])}")
    if image_available:
        parts.append("\n[มีภาพสินค้าแนบ — ให้วิเคราะห์ packaging, ดีไซน์, และกลุ่มเป้าหมายจากภาพด้วย]")
    return "\n".join(parts)


def router_decide(
    product_name: str,
    description: str = "",
    price: Optional[float] = None,
    image_base64: Optional[str] = None,
    keywords: Optional[list] = None,
) -> Dict[str, Any]:
    """Main entry — decide content strategy for a product.
    
    Returns:
        dict with keys: recipe_type, duration, visual_style, persona, scenes, reason
    """
    system = _build_router_prompt()
    user = _build_user_prompt(product_name, description, price, image_base64 is not None, keywords)

    if image_base64:
        # Vision call — analyze image + text
        from gemini_client import _call_gemini_vision
        raw = _call_gemini_vision(system, user, image_base64)
        result = _extract_json(raw)
    else:
        # Text-only call
        raw = _call_gemini_router(system, user)
        result = _extract_json(raw)

    if not result:
        logger.warning(f"Router returned invalid JSON for '{product_name}', using fallback")
        return dict(FALLBACK_CONFIG, product=product_name, reason="fallback")

    # Validate required fields
    result.setdefault("recipe_type", FALLBACK_CONFIG["recipe_type"])
    result.setdefault("duration", FALLBACK_CONFIG["duration"])
    result.setdefault("visual_style", FALLBACK_CONFIG["visual_style"])
    result.setdefault("persona", FALLBACK_CONFIG["persona"])
    result.setdefault("reason", "")
    result["product"] = product_name

    # Load schema → build scenes with actual durations
    result["scenes"] = _build_scenes(result["recipe_type"], result["duration"])
    
    return result


def _build_scenes(recipe_type: str, duration: str) -> list:
    """Load schema JSON → calculate scene durations from timing_ratio."""
    import os
    schema_path = os.path.join(os.path.dirname(__file__), "schemas", f"{recipe_type}_schema.json")
    
    if not os.path.exists(schema_path):
        logger.warning(f"Schema '{recipe_type}' not found, using fallback scenes")
        return FALLBACK_CONFIG["scenes"]
    
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load schema {recipe_type}: {e}")
        return FALLBACK_CONFIG["scenes"]
    
    # Parse duration
    seconds = int(duration.replace("s", ""))
    scenes = schema.get("scenes", [])
    if not scenes:
        return FALLBACK_CONFIG["scenes"]
    
    # Build scene list with calculated durations
    result = []
    for scene in scenes:
        ratio = scene.get("timing_ratio", 1.0 / len(scenes))
        dur = round(seconds * ratio, 1)
        result.append({
            "id": scene["id"],
            "duration": dur,
            "purpose": scene.get("purpose", ""),
            "prompt_template": scene.get("prompt", ""),
        })
    
    return result


def router_decide_batch(
    products: list,
    max_concurrent: int = 5,
) -> list[Dict[str, Any]]:
    """Process multiple products in batch."""
    results = []
    for product in products:
        config = router_decide(
            product_name=product.get("name", ""),
            description=product.get("description", ""),
            price=product.get("price"),
            image_base64=product.get("image_base64"),
            keywords=product.get("keywords"),
        )
        results.append(config)
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test with a sample product
    config = router_decide(
        product_name="เซรั่มวิตามินซี Vitamin C Serum",
        description="เซรั่มช่วยให้ผิวขาวใส กระจ่างใส ลดจุดด่างดำ",
        price=299,
    )
    print(json.dumps(config, indent=2, ensure_ascii=False))
