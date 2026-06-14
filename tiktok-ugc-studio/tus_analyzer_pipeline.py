"""
TUS Analyzer Pipeline — Bridge between Product Analyzer & TikTok UGC Studio
============================================================================
- Call Product Analyzer API (/api/v1/analyze) from TUS
- Filter products by viral score, category, trending
- Download product images via DataImpulse Proxy (hdnet.workers.dev is 403)
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

# Local image storage สำหรับรูปสินค้า
PRODUCT_IMAGE_DIR = Path(__file__).parent / "storage" / "product_images"
PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

# TUS static route prefix (served by FastAPI StaticFiles)
IMAGE_URL_PREFIX = "/static/product_images"

# DataImpulse Proxy config (from .env)
DATAIMPULSE_PROXY = os.environ.get("DATAIMPULSE_PROXY", "")
PROXY_DICT = {
    "http": DATAIMPULSE_PROXY,
    "https": DATAIMPULSE_PROXY,
} if DATAIMPULSE_PROXY else None


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
        "min_commission": 10,
        "min_rating": 0,
        "min_sold": 0,
        "min_viral": 0,
        "trending_only": False,
    },
    "trending_now": {
        "description": "Trending products right now",
        "trending_only": True,
        "min_rating": 0,
        "min_sold": 0,
        "min_viral": 0,
    },
    "low_cost": {
        "description": "Low price products (impulse buy)",
        "max_price": 100,
        "min_rating": 0,
        "min_sold": 0,
        "min_viral": 0,
    },
}


# ─── Download Helpers ────────────────────────────────────────────────────

def _download_product_image(img_url: str) -> tuple:
    """
    Download product image via DataImpulse proxy.

    Args:
        img_url: hdnet.workers.dev URL

    Returns:
        (bytes | None, str) — content and extension
    """
    ext = img_url.rsplit(".", 1)[-1].split("?")[0]
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"

    import requests
    try:
        resp = requests.get(
            img_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "image/webp,image/*,*/*;q=0.8",
                "Referer": "https://shop.tiktok.com/",
            },
            proxies=PROXY_DICT,
            timeout=15,
        )
        if resp.status_code == 200 and len(resp.content) > 1000:
            logger.info(f"  Downloaded via proxy: {len(resp.content)} bytes")
            return resp.content, ext
        else:
            logger.warning(f"  Proxy download failed: {resp.status_code}")
    except Exception as e:
        logger.warning(f"  Proxy download error: {e}")

    return None, ext


# ─── Main: fetch_trending_for_tus ─────────────────────────────────────────

async def fetch_trending_for_tus(
    preset: str = "auto_affiliate",
    limit: int = 10,
    category: str = None,
) -> dict:
    """Fetch analyzed products filtered for TikTok UGC Studio post generation.
    
    Returns TUS-ready data with LOCAL image URLs (downloaded via DataImpulse proxy).
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

        # ── Download images via DataImpulse Proxy ──
        for p in filtered:
            # Add TikTok product link
            product_id = p.get("product_id", "")
            p["link"] = f"https://shop.tiktok.com/view/product/{product_id}" if product_id else ""

            old_images = p.get("images", [])
            local_images = []

            for img_url in old_images:
                if not img_url:
                    continue

                # Already local?
                if img_url.startswith("/static/"):
                    local_images.append(img_url)
                    continue

                # Download via proxy
                content, ext = _download_product_image(img_url)
                if content:
                    local_name = f"{p['product_id']}_{uuid.uuid4().hex[:4]}.{ext}"
                    local_path = PRODUCT_IMAGE_DIR / local_name
                    with open(local_path, "wb") as f:
                        f.write(content)
                    local_url = f"{IMAGE_URL_PREFIX}/{local_name}"
                    local_images.append(local_url)
                    logger.info(f"  Saved: {local_name}")
                else:
                    # Fallback: keep original URL (may 403 in UI)
                    local_images.append(img_url)

            if local_images:
                p["images"] = local_images
                p["images_local"] = True

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
        # Step 1: Get raw data
        if raw_products is None:
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
                "preset": preset,
                "auto_generate": True,
            }
            try:
                async with httpx.AsyncClient() as hx:
                    r = await hx.post(
                        f"{TUS_API}/postforme/post",
                        json=post_data,
                        timeout=30,
                    )
                    if r.status_code == 200:
                        posted = r.json().get("posted", [])
                        logger.info(f"Auto-posted {len(posted)} products")
                    else:
                        logger.warning(f"Auto-post returned {r.status_code}: {r.text}")
            except Exception as e:
                logger.error(f"Auto-post failed: {e}")

        return {
            "status": "ok",
            "preset": preset,
            "analyzed_count": analyzed.get("count", 0),
            "tus_ready": tus_data.get("count", 0),
            "auto_posted": len(posted),
        }

    except Exception as e:
        logger.exception("analyze_and_push_to_tus failed")
        return {"status": "error", "error": str(e)}
    finally:
        await client.client.aclose()


def fetch_trending(preset: str = "auto_affiliate", limit: int = 10, category: str = None) -> dict:
    """Sync entry point for cli usage."""
    import asyncio
    return asyncio.run(fetch_trending_for_tus(preset=preset, limit=limit, category=category))


def run_pipeline(
    apify_dataset_id: str = None,
    json_file: str = None,
    source: str = "tiktok",
    preset: str = "auto_affiliate",
    auto_post: bool = False,
) -> dict:
    """Sync entry point: pass JSON file path or Apify dataset id."""
    if json_file:
        with open(json_file) as f:
            raw_products = json.load(f)
        return asyncio.run(analyze_and_push_to_tus(
            raw_products=raw_products, source=source, preset=preset, auto_post=auto_post,
        ))
    else:
        return asyncio.run(analyze_and_push_to_tus(
            apify_dataset_id=apify_dataset_id, source=source, preset=preset, auto_post=auto_post,
        ))


# ─── CLI ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TUS Analyzer Pipeline")
    parser.add_argument("--apify-dataset", help="Apify dataset ID")
    parser.add_argument("--json-file", help="Product JSON file")
    parser.add_argument("--source", default="tiktok", help="Data source")
    parser.add_argument("--preset", default="auto_affiliate", help="Filter preset")
    parser.add_argument("--auto-post", action="store_true", help="Auto post to TikTok")
    parser.add_argument("--fetch", action="store_true", help="Just fetch trending products")
    parser.add_argument("--limit", type=int, default=10, help="Max products")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.fetch:
        result = fetch_trending(preset=args.preset, limit=args.limit)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        result = run_pipeline(
            apify_dataset_id=args.apify_dataset,
            json_file=args.json_file,
            source=args.source,
            preset=args.preset,
            auto_post=args.auto_post,
        )
        print(f"Status: {result.get('status')}")
        print(json.dumps(result, indent=2, ensure_ascii=False))
