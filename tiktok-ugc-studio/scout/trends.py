"""Trend discovery — identifies trending content patterns and topics."""
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List

logger = logging.getLogger("scout.trends")

# Pre-defined trending content patterns (expandable via web search / LLM)
TREND_CATEGORIES = {
    "product_review": {
        "name": "Product Review / Unboxing",
        "avg_duration": 30,
        "hook_types": ["problem", "question", "result"],
        "sound_vibe": "upbeat_excited",
        "pacing": "fast",
    },
    "before_after": {
        "name": "Before & After Transformation",
        "avg_duration": 15,
        "hook_types": ["shock", "visual", "comparison"],
        "sound_vibe": "dramatic_reveal",
        "pacing": "medium",
    },
    "tutorial": {
        "name": "How-To / Tutorial",
        "avg_duration": 45,
        "hook_types": ["problem", "benefit"],
        "sound_vibe": "calm_instructive",
        "pacing": "slow",
    },
    "comedy_skit": {
        "name": "Comedy / Relatable Skit",
        "avg_duration": 20,
        "hook_types": ["story", "shock", "relatable"],
        "sound_vibe": "funny_quirky",
        "pacing": "fast",
    },
    "testimonial": {
        "name": "Customer Testimonial",
        "avg_duration": 25,
        "hook_types": ["story", "result", "problem"],
        "sound_vibe": "sincere_trustworthy",
        "pacing": "medium",
    },
    "comparison": {
        "name": "Side-by-Side Comparison",
        "avg_duration": 20,
        "hook_types": ["shock", "comparison", "result"],
        "sound_vibe": "dramatic_contrast",
        "pacing": "fast",
    },
    "challenge": {
        "name": "Challenge / Trend",
        "avg_duration": 15,
        "hook_types": ["hook_visual", "challenge"],
        "sound_vibe": "trending_audio",
        "pacing": "fast",
    },
}

# Known trending audio vibes (descriptive, no actual copyrighted tracks)
TRENDING_SOUND_VIBES = {
    "upbeat_excited": "Fast BPM, synth/electronic, celebratory vibe",
    "dramatic_reveal": "Slow build → drop, orchestral/film score",
    "calm_instructive": "Lo-fi, soft piano, ASMR-adjacent",
    "funny_quirky": "Cartoonish, glitchy sound effects, meme audio",
    "sincere_trustworthy": "Acoustic guitar, warm piano, soft strings",
    "dramatic_contrast": "Sharp transition sounds, ding/alert effects",
    "trending_audio": "Current viral audio (check TikTok trending sounds)",
}


async def discover_trends(
    category: str = "",
    keyword: str = "",
    limit: int = 10,
) -> List[dict]:
    """Discover trending content patterns.

    Uses web search + LLM analysis to find current trending topics.
    Falls back to cached patterns if search unavailable.
    """
    logger.info(f"Discovering trends: category={category}, keyword={keyword}")

    # In production, this would call external trend APIs or web search.
    # For now, return curated trend patterns based on known categories.
    results = []
    for cat_id, cat_data in TREND_CATEGORIES.items():
        if category and cat_id != category:
            continue
        if keyword and keyword.lower() not in cat_data["name"].lower():
            continue

        results.append({
            "id": cat_id,
            "name": cat_data["name"],
            "avg_duration": cat_data["avg_duration"],
            "hook_types": cat_data["hook_types"],
            "sound_vibe": cat_data["sound_vibe"],
            "sound_description": TRENDING_SOUND_VIBES.get(cat_data["sound_vibe"], ""),
            "pacing": cat_data["pacing"],
            "confidence": 0.85,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
        })
        if len(results) >= limit:
            break

    return results


async def analyze_viral_structure(product_name: str, category: str = "") -> dict:
    """Analyze what viral video structure would work best for this product/category.

    Returns a recommended content template with hook type, pacing, structure, etc.
    """
    cat_id = category or "product_review"
    trend = TREND_CATEGORIES.get(cat_id, TREND_CATEGORIES["product_review"])

    return {
        "product": product_name,
        "recommended_format": trend["name"],
        "hook_type": trend["hook_types"][0],
        "hook_examples": _get_hook_examples(trend["hook_types"][0]),
        "pacing": trend["pacing"],
        "target_duration": trend["avg_duration"],
        "sound_vibe": trend["sound_vibe"],
        "structure": _get_structure(cat_id),
        "confidence": 0.8,
    }


async def search_trending_keywords(product_name: str, niche: str = "") -> List[str]:
    """Search for trending keywords and hashtags related to a product."""
    # In production, searches TikTok API / Google Trends.
    # For now, generate relevant keyword patterns.
    base_keywords = [
        f"{product_name} review",
        f"{product_name} unboxing",
        f"{product_name} honest review",
        f"{product_name} worth it",
        f"{product_name} before after",
    ]
    if niche:
        niche_keywords = [
            f"{niche} {product_name}",
            f"{niche} must have",
            f"{niche} finds",
        ]
        base_keywords.extend(niche_keywords)

    return base_keywords


def _get_hook_examples(hook_type: str) -> List[str]:
    """Generate example hooks for a given hook type."""
    hooks = {
        "problem": [
            "ทุกคนกำลังเจอปัญหานี้กันใช่ไหม?",
            "หยุด! อย่าเพิ่งซื้อจนกว่าคุณจะเห็นสิ่งนี้",
            "3 ข้อผิดพลาดที่คน 99% ทำ",
        ],
        "shock": [
            "สุดยอด! สิ่งนี้เปลี่ยนชีวิตฉันไปตลอดกาล",
            "บอกตรงๆ… ฉันไม่คิดว่ามันจะดีขนาดนี้",
            "ช็อก! ราคานี้กับคุณภาพนี้?",
        ],
        "question": [
            "คุณเคยสงสัยไหมว่า…",
            "ถ้าฉันบอกว่ามีวิธีที่ดีกว่านี้ คุณจะเชื่อไหม?",
            "อะไรคือสิ่งที่คุณจะซื้อถ้ามีเงินไม่จำกัด?",
        ],
        "story": [
            "ขอเล่าประสบการณ์จริงให้ฟัง…",
            "วันนั้นฉันตัดสินใจลองอะไรบางอย่าง…",
            "จากที่ไม่เชื่อ → กลายเป็น must-have ประจำบ้าน",
        ],
        "result": [
            "แค่ 7 วัน… ผลลัพธ์ที่คุณเห็นคือสิ่งนี้",
            "ก่อนใช้ vs หลังใช้ ต่างกันชัดเจน",
            "ลูกค้าบอกว่าสิ่งนี้เปลี่ยนชีวิตพวกเขา",
        ],
        "comparison": [
            "อันไหนคุ้มกว่ากัน? เปรียบเทียบให้เห็นชัดๆ",
            "Side by side — ดูด้วยตาตัวเอง",
            "แพง vs ถูก อันไหนดีกว่ากัน?",
        ],
        "visual": [
            "แค่ดูก็รู้ว่าต่างกัน…",
            "ตาเห็น — ไม่ต้องอธิบาย",
        ],
    }
    return hooks.get(hook_type, hooks["problem"])


def _get_structure(category: str) -> List[dict]:
    """Get video structure blueprint for a category."""
    structures = {
        "product_review": [
            {"time": "0:00-0:03", "element": "Hook", "description": "เปิดด้วยคำถาม/ปัญหาที่คนสนใจ"},
            {"time": "0:03-0:08", "element": "Introduce Product", "description": "โชว์สินค้า, ชื่อสินค้า, ราคา"},
            {"time": "0:08-0:20", "element": "Key Features", "description": "ไฮไลท์ฟีเจอร์เด็ด 2-3 ข้อ"},
            {"time": "0:20-0:25", "element": "Demonstration", "description": "โชว์การใช้งานจริง"},
            {"time": "0:25-0:30", "element": "CTA", "description": "ปิดท้ายด้วย CTA กระตุ้นซื้อ"},
        ],
        "before_after": [
            {"time": "0:00-0:02", "element": "Visual Hook", "description": "ก่อนใช้ — สภาพที่เป็นปัญหา"},
            {"time": "0:02-0:05", "element": "Transition", "description": " Effect transition"},
            {"time": "0:05-0:10", "element": "After Result", "description": "หลังใช้ — ผลลัพธ์ที่เปลี่ยนไป"},
            {"time": "0:10-0:15", "element": "Product & CTA", "description": "บอกสินค้า + CTA"},
        ],
        "tutorial": [
            {"time": "0:00-0:03", "element": "Hook", "description": "บอกว่าวันนี้จะสอนอะไร"},
            {"time": "0:03-0:10", "element": "Materials", "description": "ของที่ต้องใช้"},
            {"time": "0:10-0:35", "element": "Step by Step", "description": "สอนทีละขั้นตอน"},
            {"time": "0:35-0:45", "element": "Result & CTA", "description": "ผลลัพธ์ + CTA"},
        ],
    }
    return structures.get(category, structures["product_review"])
