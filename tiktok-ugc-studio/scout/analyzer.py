"""Viral video analyzer — deconstructs trending videos to understand why they work."""
import json
import logging
from typing import Optional, List, Dict
from datetime import datetime, timezone

logger = logging.getLogger("scout.analyzer")


VIRAL_PATTERNS = {
    "hook_first_3s": {
        "name": "Strong hook in first 3 seconds",
        "weight": 0.30,
        "description": "คำแรกต้องจับ attention ทันที — 'ทุกคน!' 'ช็อก!' 'หยุด!'",
    },
    "emotional_trigger": {
        "name": "Emotional trigger (FOMO, curiosity, aspiration)",
        "weight": 0.20,
        "description": "กระตุ้นอารมณ์ — กลัวพลาด, อยากรู้, อยากมี",
    },
    "clear_benefit": {
        "name": "Clear benefit visible immediately",
        "weight": 0.15,
        "description": "คนดูเห็นประโยชน์ชัดเจนภายใน 3-5 วิแรก",
    },
    "visual_appeal": {
        "name": "High visual appeal / production quality",
        "weight": 0.10,
        "description": "ภาพสวย, จัดองค์ประกอบดี, แสงชัด",
    },
    "trending_sound": {
        "name": "Uses trending audio or sound effect",
        "weight": 0.10,
        "description": "เสียง/เพลงกำลังมาแรง ช่วยเพิ่ม reach",
    },
    "fast_pacing": {
        "name": "Fast pacing — no dead air",
        "weight": 0.08,
        "description": "ตัดต่อเร็ว, ไม่มีช่วงเงียบ, ดูกระชับ",
    },
    "strong_cta": {
        "name": "Strong CTA at the end",
        "weight": 0.07,
        "description": "ปิดท้ายด้วยคำกระตุ้นที่ชัดเจน",
    },
}


async def analyze_video(
    video_url: str = "",
    description: str = "",
    product_name: str = "",
) -> Dict:
    """Analyze a video's viral potential and provide optimization suggestions.

    In production, this would use computer vision to analyze actual video frames.
    Currently provides analysis based on metadata and content strategy patterns.
    """
    logger.info(f"Analyzing video: {video_url or product_name}")

    # Score each viral pattern
    pattern_scores = {}
    total_score = 0.0

    for key, pattern in VIRAL_PATTERNS.items():
        score = _score_pattern(key, description, product_name)
        weighted = score * pattern["weight"]
        pattern_scores[key] = {
            "score": round(score, 2),
            "weighted": round(weighted, 3),
            "description": pattern["description"],
        }
        total_score += weighted

    # Generate recommendations based on weak spots
    weak_spots = [
        k for k, v in pattern_scores.items() if v["score"] < 0.5
    ]
    recommendations = _generate_recommendations(weak_spots, product_name)

    return {
        "viral_score": round(total_score / sum(p["weight"] for p in VIRAL_PATTERNS.values()), 3),
        "pattern_breakdown": pattern_scores,
        "recommendations": recommendations,
        "weak_spots": weak_spots,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


async def compare_with_competitors(
    product_name: str,
    competitor_names: List[str],
) -> Dict:
    """Compare content strategy against competitors."""
    results = []
    for comp in competitor_names:
        results.append({
            "name": comp,
            "estimated_viral_score": round(0.5 + (hash(comp) % 30) / 100, 2),
            "content_style": _guess_competitor_style(comp),
            "summary": f"{comp} มีแนวโน้มใช้ content แบบ {_guess_competitor_style(comp)}",
        })

    return {
        "product": product_name,
        "competitors": results,
        "recommendations": [
            f"สร้าง content ที่แตกต่างจาก {competitor_names[0] if competitor_names else 'คู่แข่ง'}",
            "เน้น authenticity มากกว่า production คู่แข่ง",
            "ใช้ Hook ที่แรงกว่าคู่แข่งใน 3 วิแรก",
        ],
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


async def extract_trending_elements(description: str = "") -> Dict:
    """Extract key elements from a trending video description."""
    elements = {
        "hook": "",
        "product_mention": "",
        "benefit_stated": "",
        "urgency": False,
        "social_proof": False,
        "cta": "",
    }
    if description:
        # Simple keyword extraction from description
        hook_keywords = ["ทุกคน", "ช็อก", "หยุด", "อย่า", "ใคร", "บอกตรง"]
        for kw in hook_keywords:
            if kw in description.lower():
                elements["hook"] = kw
                break
        if "ลด" in description or "ราคา" in description:
            elements["urgency"] = True
        if "คน" in description and ("บอก" in description or "รีวิว" in description):
            elements["social_proof"] = True

    return {
        "extracted_elements": elements,
        "suggested_improvements": [
            "เพิ่ม Social Proof — '1,000+ คนใช้แล้ว'",
            "เพิ่ม Urgency — 'เหลือแค่ 50 ชิ้น'",
            "ใส่ CTA ที่ชัดเจนขึ้น",
        ],
        "format_analysis": {
            "hook_strength": "medium" if elements.get("hook") else "weak",
            "has_cta": bool(elements.get("cta")),
            "has_urgency": elements.get("urgency", False),
            "has_social_proof": elements.get("social_proof", False),
        },
    }


def _score_pattern(pattern_key: str, description: str, product_name: str) -> float:
    """Score how well a video matches a viral pattern (0.0 to 1.0)."""
    text = (description + " " + product_name).lower()

    # Keyword-based scoring
    pattern_keywords = {
        "hook_first_3s": ["ทุกคน", "ช็อก", "หยุด", "อย่าเพิ่ง", "บอกตรง", "real talk"],
        "emotional_trigger": ["พลาด", "เสียดาย", "ที่สุด", "เปลี่ยน", "ชีวิต"],
        "clear_benefit": ["ดี", "คุ้ม", "ประหยัด", "เร็ว", "ง่าย", "สะดวก"],
        "visual_appeal": [],
        "trending_sound": [],
        "fast_pacing": [],
        "strong_cta": ["กด", "ซื้อ", "ตาม", "แชร์", "เซฟ", "link in bio"],
    }

    keywords = pattern_keywords.get(pattern_key, [])
    if not keywords:
        return 0.5  # neutral score for patterns we can't detect from text
    matches = sum(1 for kw in keywords if kw in text)
    return min(1.0, matches / max(1, len(keywords) * 0.5))


def _generate_recommendations(weak_spots: List[str], product_name: str) -> List[str]:
    """Generate actionable recommendations for weak viral patterns."""
    recs = {
        "hook_first_3s": [
            f"เปิดด้วย 'ทุกคน!' หรือ 'ช็อก!' — คำแรกต้องปัง",
            f"ใช้คำถามกระตุ้นความสงสัยเกี่ยวกับ {product_name}",
        ],
        "emotional_trigger": [
            f"บอกว่าถ้าไม่มี {product_name} คุณกำลังพลาดอะไร",
            "เพิ่ม FOMO — 'คนอื่นได้กันหมดแล้ว'",
        ],
        "clear_benefit": [
            f"บอกให้ชัดว่าคนดูได้อะไรจาก {product_name}",
            "ใช้ตัวเลข — 'ประหยัดเวลา 50%'",
        ],
        "visual_appeal": [
            "จัดแสงให้สว่างขึ้น",
            "ถ่ายในมุมที่เป็นระเบียบ สะอาดตา",
        ],
        "trending_sound": [
            "ใช้เสียงยอดนิยม — เปิด TikTok trending sounds",
            "ใส่ Sound Effect ตอน transition",
        ],
        "fast_pacing": [
            "ตัดช่วงเงียบออกให้หมด",
            "ใช้ transitions เร็วขึ้น",
        ],
        "strong_cta": [
            "ปิดท้ายด้วย CTA ที่ชัดเจน — 'กดลิ้งค์ใน Bio'",
            "เพิ่ม urgency — 'วันนี้เท่านั้น!'",
        ],
    }
    result = []
    for spot in weak_spots:
        result.extend(recs.get(spot, []))
    return result[:6]  # max 6 recommendations


def _guess_competitor_style(name: str) -> str:
    """Guess competitor content style from name patterns."""
    name_lower = name.lower()
    if any(w in name_lower for w in ["luxury", "premium", "pro", "gold"]):
        return "High production / Premium"
    elif any(w in name_lower for w in ["budget", "eco", "simple"]):
        return "Minimal / Budget-friendly"
    else:
        return "Mixed / Generalist"
