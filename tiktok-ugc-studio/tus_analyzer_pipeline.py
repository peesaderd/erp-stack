"""
TUS Analyzer Pipeline — Bridge between Product Analyzer & TikTok UGC Studio
============================================================================
- Call Product Analyzer API (/api/v1/analyze) from TUS
- Filter products by viral score, category, trending
- Pass data directly to TUS (no image download logic — Analysis module is source of truth)
- Auto-feed into TikTok UGC Studio Post For Me pipeline
- Cron-ready for scheduled analysis
"""

import os, json, logging, httpx, uuid
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timedelta

logger = logging.getLogger("tus-analyzer-pipeline")

# API Base (proxy through TUS frontend or direct)
ANALYZER_API = os.environ.get("ANALYZER_API", "http://localhost:8106")
TUS_API = os.environ.get("TUS_API", "http://localhost:8105")


# ─── Preset Filters ────────────────────────────────────────────────────────
# Each preset defines which products to pull from Analyzer + how to configure
# TUS Pipeline for generation.

FILTER_PRESETS: Dict[str, dict] = {
    "auto_affiliate": {
        "description": "Auto Affiliate — high viral, trending, good commission",
        "min_rating": 4.0,
        "min_sold": 10000,
        "commission": 5,
        "min_viral": 20,
        "trending_only": False,
        "category": None,
        "duration": 30,
        "cta": "Link in bio! 🛍️",
    },
    "viral_short": {
        "description": "Viral Clips — trending high-engagement products",
        "min_rating": 4.0,
        "min_sold": 50000,
        "commission": 0,
        "min_viral": 50,
        "trending_only": True,
        "category": None,
        "duration": 15,
        "cta": "Shop now! 🔥",
    },
    "carousel": {
        "description": "Image Carousel — beauty / skincare visual products",
        "min_rating": 4.5,
        "min_sold": 10000,
        "commission": 0,
        "min_viral": 10,
        "trending_only": False,
        "category": "Face Masks",
        "duration": 8,
        "cta": "Swipe up! ✨",
    },
    "all": {
        "description": "All products, no filter",
        "min_rating": 0,
        "min_sold": 0,
        "commission": 0,
        "min_viral": 0,
        "trending_only": False,
        "category": None,
        "duration": 15,
        "cta": "Check it out! 🎯",
    },
}


# ─── AnalyzerClient ────────────────────────────────────────────────────────
# Talks to the Product Analyzer microservice (the source of truth).

class AnalyzerClient:
    """HTTP client for Product Analyzer API."""

    def __init__(self):
        self.base = ANALYZER_API
        self.client = httpx.AsyncClient(timeout=30)

    async def export(
        self,
        min_rating: Optional[float] = None,
        min_sold: Optional[int] = None,
        commission: Optional[float] = None,
        category: Optional[str] = None,
        source: str = "tiktok",
        seller_id: Optional[str] = None,
        seller_name: Optional[str] = None,
        limit: int = 100,
    ) -> dict:
        """Get analyzed products (the data includes images, links, viral scores)."""
        params = {"source": source, "limit": limit}
        if min_rating is not None: params["min_rating"] = min_rating
        if min_sold is not None: params["min_sold"] = min_sold
        if commission is not None: params["commission"] = commission
        if category is not None: params["category"] = category
        if seller_id: params["seller_id"] = seller_id
        if seller_name: params["seller_name"] = seller_name

        try:
            resp = await self.client.get(f"{self.base}/api/v1/analyze/export", params=params)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"Analyzer export failed: {e}")
            return {"products": [], "count": 0}

    async def analyze_products(self, product_ids: List[str]):
        """Trigger analysis on scraped products."""
        try:
            resp = await self.client.post(
                f"{self.base}/api/v1/analyze/analyze",
                json={"product_ids": product_ids},
            )
            return resp.json()
        except Exception as e:
            logger.error(f"Analyze trigger failed: {e}")
            return {"success": False, "error": str(e)}


# ─── Main: fetch_trending_for_tus ─────────────────────────────────────────

async def fetch_trending_for_tus(
    preset: str = "auto_affiliate",
    limit: int = 10,
    category: str = None,
) -> dict:
    """Fetch analyzed products from Analyzer API (source of truth).

    Returns TUS-ready data — images, links, viral scores come directly
    from the Analysis module. No image download or FLUX gen here.
    """
    client = AnalyzerClient()
    try:
        preset_cfg = FILTER_PRESETS.get(preset, {})
        filters = {
            "min_rating": preset_cfg.get("min_rating"),
            "min_sold": preset_cfg.get("min_sold"),
            "commission": preset_cfg.get("commission") or preset_cfg.get("min_commission"),
            "category": category or preset_cfg.get("category"),
        }

        result = await client.export(**filters)
        products = result.get("products", [])

        # Apply viral score + trending filters locally
        filtered = []
        for p in products:
            if preset_cfg.get("min_viral") and (p.get("viral_score") or 0) < preset_cfg["min_viral"]:
                continue
            if preset_cfg.get("trending_only") and not p.get("trending"):
                continue
            filtered.append(p)

        filtered = filtered[:limit]

        # Analysis module already returns all fields including link, images
        # Just ensure link field is present
        for p in filtered:
            product_id = p.get("product_id", "")
            if not p.get("link"):
                p["link"] = f"https://shop.tiktok.com/view/product/{product_id}" if product_id else ""

        # Attach preset metadata
        tus_data = {
            "products": filtered,
            "preset": preset,
            "preset_description": preset_cfg.get("description", ""),
            "count": len(filtered),
            "total_available": result.get("count", 0),
            "generated_at": datetime.utcnow().isoformat(),
            "tus_ready": True,
        }

        logger.info(f"TUS Pipeline: preset={preset}, count={len(filtered)}/{result.get('count', 0)} available")

        return tus_data

    except Exception as e:
        logger.error(f"TUS Pipeline failed: {e}")
        return {"products": [], "preset": preset, "count": 0, "error": str(e), "tus_ready": False}
    finally:
        await client.client.aclose()


async def analyze_and_push_to_tus(
    apify_dataset_id: str = None,
    raw_products: list = None,
    source: str = "tiktok",
    preset: str = "auto_affiliate",
    auto_post: bool = False,
) -> dict:
    """Full pipeline: Scrape → Analyze → Push to TUS for post generation.

    If apify_dataset_id is provided, fetches from Apify first.
    If raw_products is provided, analyzes directly.
    If auto_post=True, triggers Post For Me after analysis.
    """
    client = AnalyzerClient()

    try:
        # 1. Trigger analysis on raw products
        # 2. Fetch analyzed results
        # 3. Pass to TUS pipeline
        # 4. Optionally auto-post

        logger.info(f"Analyze & push: source={source}, preset={preset}, auto_post={auto_post}")

        # Placeholder for future Apify→Analyze→TUS flow
        return {
            "success": False,
            "error": "Not fully implemented — use fetch_trending_for_tus() directly.",
        }

    except Exception as e:
        logger.error(f"analyze_and_push_to_tus failed: {e}")
        return {"success": False, "error": str(e)}
    finally:
        await client.client.aclose()
