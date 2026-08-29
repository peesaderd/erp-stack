"""
Unified Product Pipeline — Scraper → Analyzer → TUS Product

Single entry point for all product ingestion.
No matter how a product enters (Apify, URL, Agent), it goes through this pipeline.

Flow:
  1. Scrape (Playwright/Apify) → PostgreSQL scraped_products
  2. Analyze (Mistral Vision + Enrich) → PostgreSQL analyzed_products
  3. Sync → tus_products.db (read-only cache for frontend + video gen)

SSOT: PostgreSQL analyzed_products
Cache: tus_products.db (synced, never written directly)
"""
import asyncio
import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger("pipeline_service")

# ── Path setup ───────────────────────────────────────────────────────────────
_ERP_ROOT = str(Path(__file__).resolve().parents[2])
_TUS_STUDIO = str(Path(_ERP_ROOT) / "tiktok-ugc-studio")
_TUS_DB = str(Path(_TUS_STUDIO) / "tus_products.db")
_PRODUCT_IMG_DIR = str(Path(_TUS_STUDIO) / "storage" / "product_images")

sys.path.insert(0, _ERP_ROOT)
sys.path.insert(0, str(Path(_ERP_ROOT) / "modules"))

# ── Pipeline status store ────────────────────────────────────────────────────
_pipeline_status: Dict[str, Dict] = {}


class PipelineResult:
    """Result of a pipeline run."""
    def __init__(self, product_id: str = "", source: str = ""):
        self.product_id = product_id
        self.source = source
        self.step_scrape = {"status": "pending", "data": None, "error": None}
        self.step_analyze = {"status": "pending", "data": None, "error": None}
        self.step_sync = {"status": "pending", "error": None}
        self.total_time_ms = 0
        self.success = False
        self.duplicate = False
        self.sync_action = None

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "source": self.source,
            "duplicate": self.duplicate,
            "sync_action": self.sync_action,
            "steps": {
                "scrape": self.step_scrape,
                "analyze": self.step_analyze,
                "sync": self.step_sync,
            },
            "total_time_ms": self.total_time_ms,
            "success": self.success,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


async def ingest_from_url(
    url: str,
    source: str = "url",
    use_vision: bool = True,
    user_id: str = "pipeline",
) -> PipelineResult:
    """
    Single entry point: URL → Pipeline → TUS Product.
    
    This is the ONLY way products should enter the system.
    """
    run_id = str(uuid.uuid4())[:8]
    result = PipelineResult(source=source)
    start = time.time()

    logger.info(f"[{run_id}] Pipeline START: url={url[:60]} source={source}")

    # ── Step 1: Scrape ───────────────────────────────────────────────────
    try:
        result.step_scrape["status"] = "running"
        scrape_data = await _step_scrape(url, use_vision, user_id)
        result.step_scrape["status"] = "done"
        result.step_scrape["data"] = scrape_data
        result.product_id = scrape_data.get("product_id", "")
        logger.info(f"[{run_id}] Step 1 SCRAPE OK: pid={result.product_id[:20]}")
    except Exception as e:
        result.step_scrape["status"] = "failed"
        result.step_scrape["error"] = str(e)
        result.total_time_ms = int((time.time() - start) * 1000)
        logger.error(f"[{run_id}] Step 1 SCRAPE FAILED: {e}")
        _save_status(run_id, result)
        return result

    # ── Step 2: Analyze ──────────────────────────────────────────────────
    try:
        result.step_analyze["status"] = "running"
        analyze_data = await _step_analyze(scrape_data)
        result.step_analyze["status"] = "done"
        result.step_analyze["data"] = analyze_data
        logger.info(f"[{run_id}] Step 2 ANALYZE OK: title={analyze_data.get('title', '')[:40]}")
    except Exception as e:
        result.step_analyze["status"] = "failed"
        result.step_analyze["error"] = str(e)
        result.total_time_ms = int((time.time() - start) * 1000)
        logger.error(f"[{run_id}] Step 2 ANALYZE FAILED: {e}")
        _save_status(run_id, result)
        return result

    # ── Step 3: Sync to tus_products.db ──────────────────────────────────
    try:
        result.step_sync["status"] = "running"
        await _step_sync(analyze_data)
        result.step_sync["status"] = "done"
        logger.info(f"[{run_id}] Step 3 SYNC OK: pid={result.product_id[:20]}")
    except Exception as e:
        result.step_sync["status"] = "failed"
        result.step_sync["error"] = str(e)
        result.total_time_ms = int((time.time() - start) * 1000)
        logger.error(f"[{run_id}] Step 3 SYNC FAILED: {e}")
        _save_status(run_id, result)
        return result

    result.success = True
    result.total_time_ms = int((time.time() - start) * 1000)
    logger.info(f"[{run_id}] Pipeline COMPLETE in {result.total_time_ms}ms")
    _save_status(run_id, result)
    return result


async def ingest_from_apify(
    apify_data: dict,
    source: str = "apify",
    user_id: str = "pipeline",
) -> PipelineResult:
    """
    Single entry point: Apify scraped data → Pipeline → TUS Product.
    Used when Apify actor has already scraped the product.
    """
    run_id = str(uuid.uuid4())[:8]
    result = PipelineResult(source=source)
    start = time.time()

    logger.info(f"[{run_id}] Pipeline (Apify) START: source={source}")

    # Skip scrape step — data already scraped
    result.step_scrape["status"] = "skipped"
    result.step_scrape["data"] = apify_data
    result.product_id = apify_data.get("product_id", "") or apify_data.get("id", "")

    # ── Step 2: Analyze ──────────────────────────────────────────────────
    try:
        result.step_analyze["status"] = "running"
        analyze_data = await _step_analyze(apify_data)
        result.step_analyze["status"] = "done"
        result.step_analyze["data"] = analyze_data
        result.product_id = analyze_data.get("product_id", result.product_id)
        logger.info(f"[{run_id}] Step 2 ANALYZE OK")
    except Exception as e:
        result.step_analyze["status"] = "failed"
        result.step_analyze["error"] = str(e)
        result.total_time_ms = int((time.time() - start) * 1000)
        logger.error(f"[{run_id}] Step 2 ANALYZE FAILED: {e}")
        _save_status(run_id, result)
        return result

    # ── Step 3: Sync ─────────────────────────────────────────────────────
    try:
        result.step_sync["status"] = "running"
        sync_action = await _step_sync(analyze_data)
        result.step_sync["status"] = "done"
        result.sync_action = sync_action
        result.duplicate = (sync_action == "duplicate")
        logger.info(f"[{run_id}] Step 3 SYNC OK (action={sync_action})")
    except Exception as e:
        result.step_sync["status"] = "failed"
        result.step_sync["error"] = str(e)
        result.total_time_ms = int((time.time() - start) * 1000)
        logger.error(f"[{run_id}] Step 3 SYNC FAILED: {e}")
        _save_status(run_id, result)
        return result

    result.success = True
    result.total_time_ms = int((time.time() - start) * 1000)
    logger.info(f"[{run_id}] Pipeline (Apify) COMPLETE in {result.total_time_ms}ms")
    _save_status(run_id, result)
    return result


async def sync_all_to_tus() -> Dict[str, Any]:
    """
    Sync ALL products from PostgreSQL → tus_products.db.
    This is the ONLY way tus_products.db should be updated.
    """
    from product.analyzer_db import get_analyzed_products
    import sqlite3

    logger.info("SYNC ALL: PostgreSQL → tus_products.db")
    result = await get_analyzed_products(limit=500)
    products = result.get("products", [])
    logger.info(f"PostgreSQL: {len(products)} products")

    conn = sqlite3.connect(_TUS_DB)
    conn.row_factory = sqlite3.Row

    existing = {
        r["product_id"]: dict(r)
        for r in conn.execute("SELECT * FROM tus_products").fetchall()
    }

    synced = 0
    created = 0
    for p in products:
        pid = p.get("product_id", "")
        if not pid or len(pid) < 10:
            continue

        row = _build_tus_row(p)

        if pid in existing:
            sets = ", ".join(f"{k} = ?" for k in row.keys())
            conn.execute(
                f"UPDATE tus_products SET {sets} WHERE product_id = ?",
                list(row.values()) + [pid],
            )
            synced += 1
        else:
            cols = ", ".join(row.keys())
            placeholders = ", ".join(["?"] * len(row))
            conn.execute(
                f"INSERT INTO tus_products ({cols}) VALUES ({placeholders})",
                list(row.values()),
            )
            created += 1

    conn.commit()
    conn.close()

    logger.info(f"SYNC DONE: {synced} updated, {created} created = {synced + created} total")
    return {"synced": synced, "created": created, "total": synced + created}


def get_pipeline_status(run_id: str = None) -> dict:
    """Get pipeline run status."""
    if run_id:
        return _pipeline_status.get(run_id, {"error": "not found"})
    return {
        "runs": len(_pipeline_status),
        "recent": list(_pipeline_status.values())[-10:],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Internal Step Functions
# ═══════════════════════════════════════════════════════════════════════════════

async def _step_scrape(url: str, use_vision: bool, user_id: str) -> dict:
    """Step 1: Scrape product URL → PostgreSQL scraped_products."""
    from product.scraper_service import scrape_with_tracking

    result = await scrape_with_tracking(
        url=url,
        user_id=user_id,
        api_key_id=None,
        use_vision=use_vision,
        proxy_url=None,
        rotate_proxy=False,
        user_tier="free",
        ip_address="127.0.0.1",
    )

    if not result.get("success"):
        raise Exception(f"Scrape failed: {result.get('error', 'unknown')}")

    product = result.get("product", {})
    if not product or not product.get("name"):
        raise Exception("Scrape returned no product data")

    # Generate product_id from URL
    import hashlib
    product_id = hashlib.sha256(url.encode()).hexdigest()[:19]

    return {
        "product_id": product_id,
        "name": product.get("name", ""),
        "description": product.get("description", ""),
        "price": product.get("price"),
        "currency": product.get("currency", "THB"),
        "images": product.get("images", []),
        "brand": product.get("brand", ""),
        "sku": product.get("sku", ""),
        "source_url": url,
        "source_site": product.get("source_site", ""),
        "method": result.get("method", "scraper"),
    }


async def _step_analyze(raw_data: dict) -> dict:
    """Step 2: Analyze product → PostgreSQL analyzed_products."""
    from product.analyze_pipeline import ProductNormalizer, ProductEnricher, ProductExporter

    # Normalize
    normalized = await ProductNormalizer.normalize(raw_data, raw_data.get("source_site", ""))

    # Enrich (Mistral Vision, keywords, etc.)
    enriched = await ProductEnricher.enrich(normalized)

    # Export for TUS
    export = ProductExporter.export_for_tus([enriched])
    products = export.get("products", [])

    if not products:
        raise Exception("Analysis produced no products")

    analyzed = products[0]

    # Store to PostgreSQL (SSOT)
    from product.analyzer_db import store_analyzed
    await store_analyzed(analyzed)

    return analyzed


def _normalize_title(title: str) -> str:
    """Normalize a product title for duplicate detection.

    Strips casing, whitespace, and removes emoji / punctuation so that the
    same product listed under slightly different title casing or spacing is
    still matched as a duplicate.
    """
    if not title:
        return ""
    # Lowercase + collapse whitespace
    t = re.sub(r"\s+", " ", str(title).lower()).strip()
    # Drop emoji / non-word, non-space chars (keep letters, digits, spaces)
    t = re.sub(r"[^\w\s]+", "", t)
    return t


def _find_duplicate_seller_title(conn, seller_id: str, title: str):
    """Return an existing product_id whose (seller_id + normalized title)
    matches, i.e. the same physical product from the same shop even when
    TikTok assigned a different product_id (common across different links).

    Returns None if no duplicate found (safe to insert).
    """
    if not seller_id:
        return None
    norm = _normalize_title(title)
    if not norm:
        return None
    # Fetch candidate rows for this seller and compare normalized titles
    rows = conn.execute(
        "SELECT product_id, title FROM tus_products WHERE seller_id = ?",
        (seller_id,),
    ).fetchall()
    for r in rows:
        if _normalize_title(r["title"]) == norm:
            return r["product_id"]
    return None


async def _step_sync(product_data: dict):
    """Step 3: Sync analyzed product → tus_products.db.

    Returns one of: 'inserted', 'updated', or 'duplicate'.
    'duplicate' means the same product (same seller_id + normalized title)
    already exists under a different product_id, so we skip inserting to
    avoid duplicate products from the same shop.
    """
    import sqlite3

    pid = product_data.get("product_id", "")
    if not pid:
        raise Exception("No product_id to sync")

    conn = sqlite3.connect(_TUS_DB)
    conn.row_factory = sqlite3.Row

    existing = conn.execute(
        "SELECT product_id FROM tus_products WHERE product_id = ?", (pid,)
    ).fetchone()

    row = _build_tus_row(product_data)

    if existing:
        sets = ", ".join(f"{k} = ?" for k in row.keys())
        conn.execute(
            f"UPDATE tus_products SET {sets} WHERE product_id = ?",
            list(row.values()) + [pid],
        )
        conn.commit()
        conn.close()
        return "updated"

    # NEW: dedup by (seller_id, normalized title) — same product from the same
    # shop can carry a different product_id if pulled from a different link.
    dup_of = _find_duplicate_seller_title(conn, row.get("seller_id", ""), row.get("title", ""))
    if dup_of:
        conn.close()
        logger.info(f"  SKIP duplicate (same seller+title, existing id {dup_of}): {row.get('title', '')[:50]}")
        return "duplicate"

    cols = ", ".join(row.keys())
    placeholders = ", ".join(["?"] * len(row))
    conn.execute(
        f"INSERT INTO tus_products ({cols}) VALUES ({placeholders})",
        list(row.values()),
    )
    conn.commit()
    conn.close()
    return "inserted"


def _build_tus_row(product: dict) -> dict:
    """Build a tus_products row from analyzed product data."""
    pid = product.get("product_id", "")
    images_raw = product.get("images", [])
    keywords = product.get("keywords", [])
    hashtags = product.get("hashtags", [])

    # Convert CDN URLs to local paths if available
    images = []
    for img_url in (images_raw if isinstance(images_raw, list) else []):
        if isinstance(img_url, str):
            local_file = os.path.join(_PRODUCT_IMG_DIR, f"{pid}.jpg")
            if os.path.exists(local_file):
                images.append(f"/ugc/static/product_images/{pid}.jpg")
            else:
                images.append(img_url)

    viral = product.get("viral_score", 0) or 0
    gender = product.get("gender", "")
    # NEW: carry the deeply-analyzed fields (body_part, usage, special_target,
    # ingredient) into tus_products.notes so the TUS video pipeline can read them.
    body_part = product.get("body_part", "")
    usage_howto = product.get("usage_howto", "")
    special_target = product.get("special_target", "")
    ingredient = product.get("ingredient_highlight", "")

    return {
        "product_id": pid,
        "title": product.get("title", ""),
        "title_th": product.get("title_th", "") or product.get("title", ""),
        "price_thb": product.get("price_thb", 0) or product.get("price_avg", 0) or product.get("price_min", 0),
        "rating": product.get("rating", 0),
        "sold_total": product.get("sold_total", 0),
        "viral_score": viral,
        "trending": 1 if viral >= 18 else 0,
        "category": product.get("category", ""),
        "commission_rate": product.get("commission_rate", 0),
        "seller_name": product.get("seller_name", ""),
        "seller_id": product.get("seller_id", ""),
        "url": product.get("url", f"https://www.tiktok.com/@product/{pid}"),
        "description": product.get("description", ""),
        "description_th": "",
        "images": json.dumps(images),
        "keywords": json.dumps(keywords if isinstance(keywords, list) else []),
        "hashtags": json.dumps(hashtags if isinstance(hashtags, list) else []),
        "source": product.get("source", "pipeline"),
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "tus_status": "ready",
        "gender": gender,
        "target_age": product.get("target_age", ""),
        "notes": json.dumps({
            "gender": gender,
            "target_age": product.get("target_age", ""),
            "body_part": body_part,
            "usage_howto": usage_howto,
            "special_target": special_target,
            "ingredient_highlight": ingredient,
        }),
    }


def _save_status(run_id: str, result: PipelineResult):
    """Save pipeline status for monitoring."""
    _pipeline_status[run_id] = result.to_dict()
    # Keep only last 100 entries
    if len(_pipeline_status) > 100:
        oldest = list(_pipeline_status.keys())[:50]
        for k in oldest:
            del _pipeline_status[k]
