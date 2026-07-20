"""Facebook Scout MVP — single-file microservice for Facebook content intelligence.

Discovers trending Facebook posts, analyzes viral patterns across Pages/Groups,
and generates clone-ready scripts for UGC pipeline integration.

Dependencies: aiohttp, python-dotenv, dataclasses (stdlib)
"""
import os
import re
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict
from urllib.parse import quote_plus

logger = logging.getLogger("scout.facebook")

# ─── Proxy Helper ────────────────────────────────────────────────────────────

def _get_proxy_url() -> str:
    """Get proxy URL from environment (Data Impulse)."""
    return os.environ.get("HTTP_PROXY", "") or os.environ.get("http_proxy", "")

# ─── Internal Config (dataclass — not exposed in API responses) ──────────────

@dataclass
class FacebookScoutConfig:
    """Configuration loaded from environment.
    Uses python-dotenv; all fields have safe defaults so the service
    works even without real API credentials (mock/pattern mode).
    """
    access_token: str = ""
    page_id: str = ""
    api_base: str = "https://graph.facebook.com/v19.0"
    request_timeout: int = 30
    max_posts_per_page: int = 50
    user_agent: str = "TikTokUGC-FacebookScout/1.0"

    @classmethod
    def from_env(cls) -> "FacebookScoutConfig":
        from dotenv import load_dotenv
        load_dotenv()
        return cls(
            access_token=os.environ.get("FACEBOOK_ACCESS_TOKEN", ""),
            page_id=os.environ.get("FACEBOOK_PAGE_ID", ""),
            api_base=os.environ.get("FACEBOOK_API_BASE", "https://graph.facebook.com/v19.0"),
            request_timeout=int(os.environ.get("FACEBOOK_REQUEST_TIMEOUT", "30")),
            max_posts_per_page=int(os.environ.get("FACEBOOK_MAX_POSTS", "50")),
        )


_CONFIG: Optional[FacebookScoutConfig] = None


def _get_config() -> FacebookScoutConfig:
    global _CONFIG
    if _CONFIG is None:
        _CONFIG = FacebookScoutConfig.from_env()
    return _CONFIG


# ─── Known viral patterns on Facebook ────────────────────────────────────────

FACEBOOK_VIRAL_PATTERNS = {
    "emotional_story": {
        "name": "Emotional Storytelling",
        "weight": 0.30,
        "description": "เรื่องราวที่มีอารมณ์ร่วม — ความสุข, เศร้า, ฮา, หรือซึ้ง",
        "avg_reach_boost": "2.5x",
    },
    "hot_take_opinion": {
        "name": "Hot Take / Opinion",
        "weight": 0.20,
        "description": "ความคิดเห็นที่แตกต่าง โต้แย้ง หรือจุดประเด็นถกเถียง",
        "avg_reach_boost": "3.0x",
    },
    "educational_value": {
        "name": "Educational / How-To",
        "weight": 0.18,
        "description": "เนื้อหาที่ให้ความรู้ มีประโยชน์ แชร์ต่อสูง",
        "avg_reach_boost": "2.0x",
    },
    "visual_carousel": {
        "name": "Carousel / Visual List",
        "weight": 0.15,
        "description": "โพสต์รูปแบบภาพหลายรูป — สไลด์, List, Before/After",
        "avg_reach_boost": "2.8x",
    },
    "engagement_bait": {
        "name": "Engagement Bait",
        "weight": 0.10,
        "description": "ชวนคอมเมนต์ — 'เห็นด้วยไหม?', 'อันไหนใช่คุณ?'",
        "avg_reach_boost": "4.0x",
    },
    "live_video": {
        "name": "Live Video / Reel",
        "weight": 0.07,
        "description": "วิดีโอสดหรือ Reel ที่มีความยาว 30-90 วินาที",
        "avg_reach_boost": "1.8x",
    },
}


# ─── Facebook Post Categories (inferred from text patterns) ─────────────────

POST_CATEGORIES = {
    "product_review": {
        "keywords": ["review", "รีวิว", "review", "unboxing", "เปิดกล่อง", "ลอง"],
        "avg_engagement": "medium",
    },
    "testimonial": {
        "keywords": ["recommend", "แนะนำ", "trust", "ไว้ใจ", "experience", "ประสบการณ์"],
        "avg_engagement": "high",
    },
    "how_to": {
        "keywords": ["how to", "วิธี", "tutorial", "สอน", "tips", "เคล็ดลับ", "ขั้นตอน"],
        "avg_engagement": "high",
    },
    "comparison": {
        "keywords": ["vs", "เทียบ", "comparison", "เปรียบเทียบ", "difference", "ต่าง"],
        "avg_engagement": "medium",
    },
    "deal_alert": {
        "keywords": ["sale", "ลด", "promotion", "โปร", "flash", "deal", "ราคา", "discount"],
        "avg_engagement": "very_high",
    },
    "entertainment": {
        "keywords": ["funny", "ตลก", "joke", "มุก", "lol", "ฮา", "memes"],
        "avg_engagement": "medium",
    },
}


# ─── Core: Facebook API client ───────────────────────────────────────────────

async def _get_session(use_proxy: bool = True) -> "aiohttp.ClientSession":
    import aiohttp
    return aiohttp.ClientSession(
        headers={"User-Agent": _get_config().user_agent},
        timeout=aiohttp.ClientTimeout(total=_get_config().request_timeout),
    )


async def _facebook_api_get(endpoint: str, params: dict = None) -> dict:
    """Make a GET request to Facebook Graph API.
    Falls back to mock data when no access_token is configured.
    """
    cfg = _get_config()
    if not cfg.access_token:
        logger.info("No FACEBOOK_ACCESS_TOKEN set — returning mock data")
        return {"mock": True, "endpoint": endpoint}

    params = dict(params or {})
    params.setdefault("access_token", cfg.access_token)

    url = f"{cfg.api_base}/{endpoint}"
    async with await _get_session() as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                logger.error(f"Facebook API error {resp.status}: {await resp.text()}")
                return {"error": True, "status": resp.status, "message": await resp.text()}
            return await resp.json()


async def _facebook_api_post(endpoint: str, data: dict = None) -> dict:
    """Make a POST request to Facebook Graph API."""
    cfg = _get_config()
    if not cfg.access_token:
        return {"mock": True, "endpoint": endpoint}

    data = dict(data or {})
    data.setdefault("access_token", cfg.access_token)

    url = f"{cfg.api_base}/{endpoint}"
    async with await _get_session() as session:
        async with session.post(url, data=data) as resp:
            if resp.status != 200:
                return {"error": True, "status": resp.status, "message": await resp.text()}
            return await resp.json()


# ─── Scout Functions (all receive/return dict — no class JSON) ──────────────

async def scout_page(
    page_username: str = "",
    keywords: str = "",
    limit: int = 10,
) -> List[dict]:
    """Scout a Facebook Page for high-engagement posts matching keywords.

    Args:
        page_username: Facebook Page username or ID (e.g. 'nike', '100293847')
        keywords: Comma-separated keywords to filter relevant posts
        limit: Max number of posts to return

    Returns:
        List of post dicts with engagement metrics, category, and viral score
    """
    logger.info(f"Scouting Facebook page: {page_username}, keywords={keywords}")

    # Try real API first
    if _get_config().access_token:
        resp = await _facebook_api_get(
            f"{page_username}/posts",
            {"fields": "message,created_time,shares,comments.summary(true),likes.summary(true),attachments", "limit": limit},
        )
        if not resp.get("error"):
            return _parse_fb_posts(resp, keywords)

    # Mock data when no API or API failed
    kw_list = [k.strip().lower() for k in keywords.split(",") if k.strip()] if keywords else []
    posts = []
    for i in range(min(limit, _get_config().max_posts_per_page)):
        cat = _pick_category(kw_list, i)
        message = _generate_mock_post(cat, page_username, i)
        engagement = _mock_engagement(i)
        posts.append({
            "id": f"fb_post_mock_{i}_{datetime.now(timezone.utc).timestamp():.0f}",
            "page": page_username or "mock_page",
            "message": message[:200],
            "category": cat,
            "post_type": _infer_post_type(message),
            "created_time": datetime.now(timezone.utc).isoformat(),
            "engagement": engagement,
            "viral_score": round(engagement.get("engagement_rate", 0) * 100, 2),
            "top_keywords": kw_list or _extract_keywords(message),
            "source": "mock",
        })

    # Sort by viral score descending
    posts.sort(key=lambda p: p["viral_score"], reverse=True)
    return posts


async def analyze_post(
    post_url: str = "",
    post_data: dict = None,
) -> dict:
    """Analyze a Facebook post's viral potential and content structure.

    Args:
        post_url: URL of the Facebook post to analyze
        post_data: Optional pre-fetched post data dict

    Returns:
        Analysis dict with viral score, pattern breakdown, and recommendations
    """
    data = post_data or {}
    message = data.get("message", "") or ""
    if not message and post_url:
        message = _mock_message_from_url(post_url)

    pattern_scores = {}
    total_score = 0.0

    for key, pattern in FACEBOOK_VIRAL_PATTERNS.items():
        score = _score_fb_pattern(key, message)
        weighted = score * pattern["weight"]
        pattern_scores[key] = {
            "score": round(score, 2),
            "weighted": round(weighted, 3),
            "description": pattern["description"],
        }
        total_score += weighted

    weak_spots = [k for k, v in pattern_scores.items() if v["score"] < 0.5]
    category = _categorize_post(message)

    return {
        "post_url": post_url or "",
        "viral_score": round(total_score / sum(p["weight"] for p in FACEBOOK_VIRAL_PATTERNS.values()), 3),
        "pattern_breakdown": pattern_scores,
        "category": category,
        "recommended_post_type": _recommend_post_type(category, pattern_scores),
        "weak_spots": weak_spots,
        "recommendations": _generate_fb_recommendations(weak_spots, message),
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


async def discover_trends(
    niche: str = "",
    page_ids: list = None,
    days_back: int = 7,
) -> dict:
    """Discover trending content patterns across Facebook Pages/Groups.

    Args:
        niche: Content niche to filter (e.g. 'beauty', 'tech', 'fashion')
        page_ids: List of Facebook page IDs to analyze
        days_back: How many days of data to analyze

    Returns:
        Dict with trending patterns, top posts, and content recommendations
    """
    logger.info(f"Discovering Facebook trends: niche={niche}, days_back={days_back}")

    # In production, this crawls pages and aggregates trend data
    # For MVP, return curated trend patterns
    trends = []
    for cat_id, cat_data in POST_CATEGORIES.items():
        if niche and niche.lower() not in str(cat_data).lower() and niche.lower() not in cat_id:
            if not any(niche.lower() in kw for kw in cat_data["keywords"]):
                continue
        trends.append({
            "id": cat_id,
            "name": cat_id.replace("_", " ").title(),
            "avg_engagement": cat_data["avg_engagement"],
            "sample_keywords": cat_data["keywords"][:4],
            "recommended_hook": _get_fb_hook_for_category(cat_id),
            "confidence": 0.75,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
        })

    top_patterns = sorted(
        FACEBOOK_VIRAL_PATTERNS.items(),
        key=lambda x: x[1]["weight"],
        reverse=True,
    )

    return {
        "niche": niche or "general",
        "trending_patterns": [
            {"id": k, "name": v["name"], "weight": v["weight"], "description": v["description"]}
            for k, v in top_patterns
        ],
        "trending_categories": trends[:10],
        "sample_hooks": _get_fb_hooks_for_niche(niche),
        "analysis_period_days": days_back,
    }


async def compare_pages(
    page_usernames: List[str],
    keywords: str = "",
) -> dict:
    """Compare content performance across multiple Facebook Pages.

    Args:
        page_usernames: List of Facebook Page usernames to compare
        keywords: Filter by keywords

    Returns:
        Dict with per-page metrics and competitive insights
    """
    results = []
    for username in page_usernames:
        posts = await scout_page(page_username=username, keywords=keywords, limit=5)
        avg_viral = round(sum(p.get("viral_score", 0) for p in posts) / max(len(posts), 1), 2)
        top_category = _most_common([p.get("category", "") for p in posts]) if posts else "unknown"
        results.append({
            "page": username,
            "post_count": len(posts),
            "avg_viral_score": avg_viral,
            "top_category": top_category,
            "top_post": max(posts, key=lambda p: p.get("viral_score", 0)) if posts else None,
            "engagement_summary": {
                "avg_likes": round(sum(p.get("engagement", {}).get("likes", 0) for p in posts) / max(len(posts), 1)),
                "avg_comments": round(sum(p.get("engagement", {}).get("comments", 0) for p in posts) / max(len(posts), 1)),
                "avg_shares": round(sum(p.get("engagement", {}).get("shares", 0) for p in posts) / max(len(posts), 1)),
            }
            if posts else {},
        })

    return {
        "pages": results,
        "insights": _generate_page_insights(results),
        "keyword_filter": keywords,
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


async def generate_clone_script(
    source_post_url: str = "",
    source_post_data: dict = None,
    product_name: str = "",
    target_audience: str = "",
) -> Optional[dict]:
    """Generate a clone-ready UGC script from a successful Facebook post structure.

    Args:
        source_post_url: URL of the reference post
        source_post_data: Pre-fetched post data (used instead of URL if provided)
        product_name: Product to adapt the content for
        target_audience: Target audience for the adaptation

    Returns:
        Dict with clone script, structure breakdown, and adaptation notes
    """
    data = source_post_data or {}
    message = data.get("message", "") or _mock_message_from_url(source_post_url)
    category = _categorize_post(message)
    post_type = _infer_post_type(message)

    structure = _fb_post_to_script_structure(message, category, product_name)

    return {
        "source": {
            "post_url": source_post_url or "",
            "category": category,
            "post_type": post_type,
        },
        "product": product_name or "สินค้า",
        "target_audience": target_audience or "ทั่วไป",
        "clone_script": {
            "hook": structure.get("hook", ""),
            "body": structure.get("body", ""),
            "cta": structure.get("cta", "กด link in bio"),
            "format": _post_type_to_format(post_type),
        },
        "structure_parts": structure.get("parts", []),
        "adaptation_notes": [
            f"ปรับจาก {category.replace('_', ' ')} Facebook → TikTok UGC",
            "ย่อเนื้อหาให้กระชับ 15-60 วินาที",
            "เพิ่ม Visual Hook ใน 3 วิแรก",
            f"ใช้โทนเสียงแบบ {_tone_for_category(category)}",
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def search_facebook_keywords(
    product_name: str,
    niche: str = "",
) -> List[str]:
    """Search for high-engagement Facebook keywords and hashtags.

    Args:
        product_name: Product to find keywords for
        niche: Optional niche filter

    Returns:
        List of keyword strings with relevance scores
    """
    base_keywords = [
        f"{product_name} review",
        f"{product_name} รีวิว",
        f"{product_name} before after",
        f"{product_name} vs",
        f"{product_name} ราคา",
        f"{product_name} วิธีใช้",
    ]
    if niche:
        niche_keywords = [
            f"{niche} {product_name}",
            f"{niche} recommendation",
            f"best {niche} {product_name}",
            f"{product_name} for {niche}",
        ]
        base_keywords.extend(niche_keywords)

    # Facebook-specific suggestions
    fb_specific = [
        f"{product_name} Facebook",
        f"buy {product_name}",
        f"{product_name} group",
        f"{product_name} review 2024",
    ]
    base_keywords.extend(fb_specific)

    return base_keywords


async def get_page_insights(
    page_username: str = "",
    period: str = "day",
) -> dict:
    """Get Facebook Page insights (reach, engagement, follower growth).

    Args:
        page_username: Facebook Page username
        period: 'day', 'week', or 'month'

    Returns:
        Dict with page metrics and trends
    """
    logger.info(f"Page insights for: {page_username}, period={period}")

    # In production, calls /{page-id}/insights via Graph API
    return {
        "page": page_username or "unknown",
        "period": period,
        "metrics": {
            "total_followers": _mock_follower_count(page_username),
            "weekly_growth": round(1.5 + (hash(page_username) % 50) / 100, 2),
            "avg_reach_per_post": _mock_reach(page_username),
            "avg_engagement_rate": round(3.5 + (hash(page_username) % 30) / 100, 2),
        },
        "top_posting_times": ["08:00", "12:00", "18:00", "21:00"],
        "content_mix": {
            "photo": 40,
            "video": 35,
            "link": 15,
            "status": 10,
        },
        "analyzed_at": datetime.now(timezone.utc).isoformat(),
    }


async def health_check() -> dict:
    """Check Facebook Scout service health and API connectivity."""
    cfg = _get_config()
    fb_connected = bool(cfg.access_token)

    if fb_connected:
        test = await _facebook_api_get("me", {"fields": "id,name"})
        fb_connected = not test.get("error")

    return {
        "service": "facebook-scout",
        "status": "ok" if fb_connected else "degraded",
        "facebook_api_connected": fb_connected,
        "mock_mode": not cfg.access_token,
        "configured_page": bool(cfg.page_id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── Internal Helpers ────────────────────────────────────────────────────────

def _parse_fb_posts(api_resp: dict, keywords: str) -> List[dict]:
    """Parse Facebook Graph API posts response into standard format."""
    posts = []
    kw_list = [k.strip().lower() for k in keywords.split(",") if k.strip()] if keywords else []
    for post in api_resp.get("data", []):
        message = post.get("message", "") or ""
        # Skip if keywords filter doesn't match
        if kw_list and not any(kw in message.lower() for kw in kw_list):
            continue

        comments_data = post.get("comments", {}).get("summary", {})
        likes_data = post.get("likes", {}).get("summary", {})
        shares_data = post.get("shares", {})

        likes = likes_data.get("total_count", 0)
        comments = comments_data.get("total_count", 0)
        shares = shares_data.get("count", 0) if shares_data else 0
        total_engagements = likes + comments + shares
        engagement_rate = total_engagements / max(likes + 1, 1)

        posts.append({
            "id": post.get("id", ""),
            "message": message[:300] if message else "",
            "created_time": post.get("created_time", ""),
            "post_type": _infer_post_type(message),
            "category": _categorize_post(message),
            "engagement": {
                "likes": likes,
                "comments": comments,
                "shares": shares,
                "total": total_engagements,
                "engagement_rate": round(engagement_rate, 4),
            },
            "viral_score": round(min(engagement_rate * 25, 100), 2),
            "top_keywords": _extract_keywords(message),
            "source": "facebook_api",
        })

    return posts


def _categorize_post(message: str) -> str:
    """Categorize a Facebook post message content."""
    msg_lower = message.lower()
    for cat_id, cat_data in POST_CATEGORIES.items():
        if any(kw in msg_lower for kw in cat_data["keywords"]):
            return cat_id
    return "general"


def _infer_post_type(message: str) -> str:
    """Infer post type (photo, video, link, status) from message content."""
    if not message:
        return "photo"
    msg = message.lower()
    if any(w in msg for w in ["watch", "video", "ดู", "reel"]):
        return "video"
    if any(w in msg for w in ["link in", "click", "กด", "อ่านต่อ", "article"]):
        return "link"
    if len(message) < 80:
        return "status"
    return "photo"


def _post_type_to_format(post_type: str) -> str:
    return {
        "video": "TikTok Reel (9:16, 15-60s)",
        "link": "TikTok Caption + Link Sticker",
        "photo": "TikTok Slideshow (5-10 images)",
        "status": "TikTok Text Post",
    }.get(post_type, "TikTok Video")


def _tone_for_category(category: str) -> str:
    tones = {
        "product_review": "Honest & Direct",
        "testimonial": "Sincere & Warm",
        "how_to": "Instructive & Clear",
        "comparison": "Analytical & Fair",
        "deal_alert": "Excited & Urgent",
        "entertainment": "Fun & Casual",
    }
    return tones.get(category, "Conversational")


def _score_fb_pattern(pattern_key: str, message: str) -> float:
    """Score how well a message matches a Facebook viral pattern (0.0 to 1.0)."""
    text = message.lower()
    keywords_map = {
        "emotional_story": ["ฉัน", "ผม", "เรา", "รู้สึก", "ชีวิต", "เจอ", "ผ่าน", "ครั้ง"],
        "hot_take_opinion": ["คิดว่า", "ไม่เห็นด้วย", "จริงๆ", "บอกตรง", "ความจริง", "เชื่อ"],
        "educational_value": ["วิธี", "สอน", "tips", "how to", "เคล็ดลับ", "ขั้นตอน", "เข้าใจ"],
        "visual_carousel": ["รูป", "photo", "carousel", " slide", "ภาพ", "before", "after"],
        "engagement_bait": ["เห็นด้วย", "ใช่ไหม", "vote", "เลือก", "comment", "แชร์", "tag"],
        "live_video": ["live", "reel", "video", "ดู", "watch", "clip"],
    }

    keywords = keywords_map.get(pattern_key, [])
    if not keywords:
        return 0.5
    matches = sum(1 for kw in keywords if kw in text)
    return min(1.0, matches / max(1, len(keywords) * 0.4))


def _generate_fb_recommendations(weak_spots: List[str], message: str) -> List[str]:
    recs = {
        "emotional_story": [
            "เพิ่ม Personal Story — 'ฉันเองก็เคยเจอ...'",
            "ใช้คำที่กระตุ้นอารมณ์ร่วม",
        ],
        "hot_take_opinion": [
            "แสดงความเห็นที่แตกต่าง — 'คนส่วนใหญ่คิดว่า... แต่จริงๆ...'",
            "ตั้งคำถามชวนถกเถียง",
        ],
        "educational_value": [
            "เพิ่ม How-To หรือ Tip ที่มีประโยชน์",
            "ใช้ List/ขั้นตอนที่เข้าใจง่าย",
        ],
        "visual_carousel": [
            "เปลี่ยนเป็นรูปแบบ Carousel ภาพหลายรูป",
            "เพิ่ม Before/After ให้เห็นชัด",
        ],
        "engagement_bait": [
            "ปิดท้ายด้วยคำถาม — 'คุณคิดยังไง? คอมเมนต์เลย!'",
            "เพิ่ม Poll หรือ Opinion ในโพสต์",
        ],
        "live_video": [
            "ลองทำ Live หรือ Reel สั้นๆ 30-60 วิ",
            "เพิ่มวิดีโอสาธิตหรือ Behind the Scenes",
        ],
    }
    result = []
    for spot in weak_spots:
        result.extend(recs.get(spot, []))
    return result[:6]


def _extract_keywords(message: str) -> List[str]:
    words = re.findall(r"[a-zA-Zก-๙]{3,}", message.lower())
    # Remove common stop words
    stop_words = {"the", "and", "for", "are", "but", "not", "you", "all", "can", "had", "her",
                  "was", "one", "our", "out", "has", "have", "been", "this", "that", "with",
                  "จาก", "และ", "ใน", "ที่", "ของ", "ไม่", "ได้", "เป็น", "มี", "จะ", "กับ"}
    return [w for w in words if w not in stop_words][:10]


def _recommend_post_type(category: str, pattern_scores: dict) -> str:
    if pattern_scores.get("live_video", {}).get("score", 0) > 0.5:
        return "video"
    if pattern_scores.get("visual_carousel", {}).get("score", 0) > 0.5:
        return "carousel"
    return "text_with_image"


def _fb_post_to_script_structure(message: str, category: str, product_name: str) -> dict:
    """Convert a Facebook post structure into a UGC script blueprint."""
    parts = []
    lines = [l.strip() for l in message.split("\n") if l.strip()]
    if not lines:
        lines = [message]

    hook = lines[0] if lines else ""
    body_lines = lines[1:-1] if len(lines) > 2 else []
    cta_line = lines[-1] if len(lines) > 1 else ""

    if body_lines:
        body = " ".join(body_lines)
    else:
        body = hook

    parts = [
        {"order": 1, "part": "Hook", "text": hook[:100], "duration_sec": 3, "source_excerpt": hook[:60]},
        {"order": 2, "part": "Body", "text": body[:200], "duration_sec": 8, "source_excerpt": body[:80] if body else ""},
        {"order": 3, "part": "CTA", "text": cta_line[:100] or "กด link in bio", "duration_sec": 3, "source_excerpt": cta_line[:60] or "CTA"},
    ]

    adapted = _adapt_facebook_to_tiktok(hook, body, cta_line, category, product_name)

    return {
        "hook": adapted["tiktok_hook"],
        "body": adapted["tiktok_body"],
        "cta": adapted["tiktok_cta"],
        "parts": parts,
    }


def _adapt_facebook_to_tiktok(
    fb_hook: str,
    fb_body: str,
    fb_cta: str,
    category: str,
    product_name: str,
) -> dict:
    """Adapt Facebook post language to TikTok UGC style."""
    tiktok_hook = fb_hook.replace(product_name, f"{product_name}") if product_name else fb_hook
    tiktok_hook = f"ทุกคน! {tiktok_hook}" if not tiktok_hook.startswith("ทุก") else tiktok_hook

    tiktok_body = fb_body
    if product_name and product_name not in tiktok_body:
        tiktok_body = f"{product_name} — {tiktok_body[:150]}"

    tiktok_cta = fb_cta if fb_cta else "กด link in bio"
    if "link" not in tiktok_cta.lower() and "bio" not in tiktok_cta.lower():
        tiktok_cta = f"{tiktok_cta} — กด link in bio เลย!"

    return {
        "tiktok_hook": tiktok_hook[:100],
        "tiktok_body": tiktok_body[:200],
        "tiktok_cta": tiktok_cta[:100],
        "adaptation_note": f"Facebook {category} → TikTok UGC style (condensed + visual hook)",
    }


def _get_fb_hook_for_category(category: str) -> str:
    hooks = {
        "product_review": "",  # scraped from real Facebook
        "testimonial": "บอกตรงๆ ว่าก่อนใช้... ",
        "how_to": "How to: 3 steps to... ",
        "comparison": "อันไหนคุ้มกว่ากัน? ",
        "deal_alert": "Flash Sale! ",
        "entertainment": "คิดเห็นยังไง? คอมเมนต์เลย!",
    }
    return hooks.get(category, "คุณเป็นเหมือนกันไหม? ")


def _get_fb_hooks_for_niche(niche: str) -> List[str]:
    base_hooks = [
        "คุณเจอปัญหานี้อยู่ไหม?",
        "บอกตรงๆ ว่าก่อนใช้...",
        "อันไหนดีกว่ากัน? Comment บอกหน่อย!",
        "How to: แบบง่ายๆ ใน 3 ขั้นตอน",
    ]
    niche_hooks = {
        "beauty": ["Skin care routine ที่เปลี่ยนชีวิต!", "Before vs After — ต่างกันชัด!"],
        "tech": [" Gadget นี้เปลี่ยนการทำงานตลอดกาล", "เทียบสเปค vs ราคา — คุ้มไหม?"],
        "fashion": ["OOTD ที่คนถามเยอะที่สุด!", "ชุดนี้ 4 แบบ — ถูกใจแบบไหน?"],
        "food": ["สูตรเด็ดที่ทำตามได้ที่บ้าน!", "ร้านนี้ดีจริง? ไปลองมาแล้ว"],
    }
    return base_hooks + niche_hooks.get(niche, [])


def _pick_category(keywords: List[str], index: int) -> str:
    if keywords:
        for cat_id, cat_data in POST_CATEGORIES.items():
            if any(kw in cat_data["keywords"] for kw in keywords):
                return cat_id
    cats = list(POST_CATEGORIES.keys())
    return cats[index % len(cats)]


def _generate_mock_post(category: str, page: str, index: int) -> str:
    templates = {
        "product_review": [
            f"เปิดกล่อง {page} สินค้ามาใหม่! รีวิวแบบละเอียดทุกจุด",
            f"{page} ลองใช้มา 1 อาทิตย์ — ขอบอกเลยว่า...",
            f"Unboxing {page} — ดีกว่าที่คิด!",
        ],
        "testimonial": [
            f"บอกตรงๆ ว่าก่อนใช้ {page} ชีวิตลำบากมาก แต่ตอนนี้...",
            f"จากใจคนใช้ {page} จริง — เปลี่ยนชีวิต!",
            f"แนะนำ {page} ให้เพื่อนทุกคน — ดีจริงไม่จกตา",
        ],
        "how_to": [
            f"How to ใช้ {page} ให้ได้ผลที่สุด — 3 ขั้นตอนง่ายๆ",
            f"วิธีใช้ {page} สำหรับมือใหม่ ห้ามพลาด!",
            f"Tips & Tricks {page} ที่คุณอาจไม่รู้",
        ],
        "comparison": [
            f"{page} vs คู่แข่ง — อันไหนคุ้มกว่ากัน?",
            f"เทียบชัดๆ {page} กับยี่ห้ออื่น ต่างกันยังไง?",
            f"Side by side: {page} vs ราคาเท่ากัน",
        ],
        "deal_alert": [
            f"Flash Sale! {page} ลด 50% วันนี้เท่านั้น!",
            f"โปรแรง! {page} ราคาพิเศษเฉพาะคนที่เห็นโพสต์นี้",
            f"แจกส่วนลด {page} 30% — รีบก่อนของหมด!",
        ],
        "entertainment": [
            f"ขำกับ {page} — ใช้ผิดวิธีแต่ดันได้ผล!",
            f"เชื่อไหมว่า {page} เอามาทำแบบนี้ได้ด้วย?",
            f"ตลกมาก {page} เวอร์ชั่นคนใช้จริง",
        ],
    }
    tpl = templates.get(category, templates["product_review"])
    return tpl[index % len(tpl)]


def _mock_message_from_url(url: str) -> str:
    return f"Mock Facebook post content from {url} — รีวิวสินค้าคุณภาพดี แนะนำให้ลอง!"


def _mock_engagement(index: int) -> dict:
    import random as _r
    likes = _r.randint(50, 5000)
    comments = _r.randint(5, 500)
    shares = _r.randint(2, 200)
    total = likes + comments + shares
    return {
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "total": total,
        "engagement_rate": round(total / max(likes * 0.8, 1), 4),
    }


def _mock_follower_count(page: str) -> int:
    return 10000 + (hash(page) % 990000) if page else 50000


def _mock_reach(page: str) -> int:
    return 500 + (hash(page) % 9500) if page else 3000


def _most_common(items: List[str]) -> str:
    if not items:
        return ""
    from collections import Counter
    return Counter(items).most_common(1)[0][0]


def _generate_page_insights(results: List[dict]) -> List[str]:
    insights = []
    for r in results:
        p = r["page"]
        score = r["avg_viral_score"]
        cat = r["top_category"]
        if score > 50:
            insights.append(f"{p}: Top performer (score {score}) — focus on {cat}")
        elif score > 20:
            insights.append(f"{p}: Moderate engagement — optimize {cat} content")
        else:
            insights.append(f"{p}: Needs improvement — study top competitors")
    if len(results) >= 2:
        best = max(results, key=lambda r: r["avg_viral_score"])
        insights.append(f"ใช้ {best['page']} เป็น benchmark — ปรับกลยุทธ์ตามแนวทางที่เวิร์ค")
    return insights
