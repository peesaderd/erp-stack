"""
TUS Analyzer Pipeline — Bridge between Product Analyzer & TikTok UGC Studio
============================================================================
- Call Product Analyzer API (/api/v1/analyze) from TUS
- Filter products by viral score, category, trending
- Auto-feed into TikTok UGC Studio Post For Me pipeline
- Cron-ready for scheduled analysis
"""

import os, json, logging, httpx
from typing import Optional, List, Dict
from datetime import datetime, timedelta

logger = logging.getLogger("tus-analyzer-pipeline")

# API Base (proxy through TUS frontend or direct)
ANALYZER_API = os.environ.get("ANALYZER_API", "http://localhost:8106")
TUS_API = os.environ.get("TUS_API", "http://localhost:8105")

# ─── Analyzer Client ────────────────────────────────────────────────────

class AnalyzerClient:
    """Client for Product Analyzer API"""

    def __init__(self, base_url: str = ANALYZER_API):
        self.base = base_url
        self.client = httpx.AsyncClient(timeout=120)

    async def get_stats(self) -> dict:
        """GET /api/v1/analyze/stats"""
        r = await self.client.get(f"{self.base}/api/v1/analyze/stats")
        r.raise_for_status()
        return r.json()

    async def analyze(self, raw_data: dict, source: str = "") -> dict:
        """POST /api/v1/analyze"""
        r = await self.client.post(
            f"{self.base}/api/v1/analyze",
            json={"raw_data": raw_data, "source": source},
        )
        r.raise_for_status()
        return r.json()

    async def batch_analyze(self, raw_data_list: list, source: str = "", filters: dict = None) -> dict:
        """POST /api/v1/analyze/batch"""
        r = await self.client.post(
            f"{self.base}/api/v1/analyze/batch",
            json={"raw_data_list": raw_data_list, "source": source, "filters": filters or {}},
        )
        r.raise_for_status()
        return r.json()

    async def export(self, **filters) -> dict:
        """GET /api/v1/analyze/export with optional filters"""
        params = {k: v for k, v in filters.items() if v is not None}
        r = await self.client.get(f"{self.base}/api/v1/analyze/export", params=params)
        r.raise_for_status()
        return r.json()


# ─── Filter Presets ─────────────────────────────────────────────────────

FILTER_PRESETS = {
    "auto_affiliate": {
        "description": "Best products for auto affiliate video generation",
        "min_rating": 0,
        "min_sold": 0,
        "category": None,
        "min_viral": 0,
        "trending_only": False,
    },
    "top_performers": {
        "description": "Highest viral score products",
        "min_rating": 3.5,
        "min_sold": 10,
        "min_viral": 30,
        "trending_only": False,
    },
    "high_commission": {
        "description": "Best commission rate products",
        "min_commission": 5.0,
        "min_sold": 10,
        "min_viral": 10,
        "trending_only": False,
    },
    "new_trending": {
        "description": "Recently trending products with traction",
        "min_sold": 0,
        "trending_only": False,
        "min_viral": 0,
    },
}

# ─── Pipeline Functions ─────────────────────────────────────────────────

async def fetch_trending_for_tus(
    preset: str = "auto_affiliate",
    limit: int = 10,
    category: str = None,
) -> dict:
    """Fetch analyzed products filtered for TikTok UGC Studio post generation.
    
    Returns TUS-ready data:
    {
        "products": [{
            "title": "เสื้อผ้าแฟชั่น",
            "title_th": "...",
            "viral_score": 85.5,
            "trending": True,
            "category": "แฟชั่น",
            "keywords": ["แฟชั่น", "เสื้อผ้า"],
            "price_thb": 299,
            "rating": 4.5,
            "commission": "10%",
            "images": ["..."],
        }],
        "preset": "auto_affiliate",
        "count": 5,
        "generated_at": "2026-06-12T..."
    }
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

        # Log to TUS pipeline
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
        # Step 1: Get raw data
        if raw_products is None:
            # Fetch from Apify dataset
            apify_key = os.environ.get("APIFY_API_KEY", "")
            if not apify_key or not apify_dataset_id:
                raise ValueError("Need apify_dataset_id + APIFY_API_KEY, or raw_products")

            async with httpx.AsyncClient() as hx:
                r = await hx.get(
                    f"https://api.apify.com/v2/datasets/{apify_dataset_id}/items",
                    params={"token": apify_key, "clean": "true", "format": "json"},
                    timeout=60,
                )
                r.raise_for_status()
                raw_products = r.json()

            logger.info(f"Fetched {len(raw_products)} products from Apify dataset {apify_dataset_id}")

        # Step 2: Analyze
        analyzed = await client.batch_analyze(raw_products, source=source)
        logger.info(f"Analyzed {analyzed.get('count', 0)} products")

        # Step 3: Apply TUS preset filter
        tus_data = await fetch_trending_for_tus(preset=preset, category=None, limit=10)

        # Step 4: Auto-post if requested
        posted = []
        if auto_post and tus_data.get("products"):
            post_data = {
                "products": tus_data["products"],
                "campaign": preset,
                "batch_id": datetime.utcnow().strftime("%Y%m%d_%H%M%S"),
            }
            async with httpx.AsyncClient() as hx:
                pr = await hx.post(
                    f"{TUS_API}/api/auto-post",
                    json=post_data,
                    timeout=300,
                )
                if pr.status_code == 200:
                    posted = pr.json().get("posts", [])
                    logger.info(f"Auto-posted {len(posted)} videos")

        return {
            "status": "success",
            "raw_count": len(raw_products) if raw_products else 0,
            "analyzed_count": analyzed.get("count", 0),
            "tus_ready": tus_data,
            "auto_posted": posted if auto_post else None,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        return {"status": "error", "error": str(e), "timestamp": datetime.utcnow().isoformat()}
    finally:
        await client.client.aclose()


# ─── Sync Entry Points for Scripting ────────────────────────────────────

def fetch_trending(preset: str = "auto_affiliate", limit: int = 10, category: str = None) -> dict:
    """Sync version for CLI/script usage."""
    import asyncio
    return asyncio.run(fetch_trending_for_tus(preset, limit, category))


def run_pipeline(
    apify_dataset_id: str = None,
    raw_products_file: str = None,
    source: str = "tiktok",
    preset: str = "auto_affiliate",
    auto_post: bool = False,
) -> dict:
    """Sync entry point: pass JSON file path or Apify dataset id."""
    import asyncio

    raw = None
    if raw_products_file:
        with open(raw_products_file) as f:
            raw = json.load(f)

    return asyncio.run(analyze_and_push_to_tus(
        apify_dataset_id=apify_dataset_id,
        raw_products=raw,
        source=source,
        preset=preset,
        auto_post=auto_post,
    ))
