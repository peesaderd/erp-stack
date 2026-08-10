#!/usr/bin/env python3
"""Enrichment runner v2 — with4 Mistral keys, proper delays, fixed title_th & images.
Reads raw_data from scraper.db → Normalize → Enrich → Store to PostgreSQL.
"""
import asyncio, json, sqlite3, sys, os, logging, re, time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("enrich_runner")

sys.path.insert(0, "/home/openhands/erp-stack")

# Load .env
from dotenv import load_dotenv
load_dotenv("/home/openhands/erp-stack/.env")

from product.analyze_pipeline import (
    ProductNormalizer, ProductEnricher, ProductExporter,
    _load_mistral_keys, _download_images_local, _analyze_and_select_images,
    PRODUCT_IMAGE_DIR, _call_mistral,
)
from product.analyzer_db import store_analyzed

SCRAPER_DB = "/home/openhands/erp-stack/modules/product/scraper.db"
# Delay between products (seconds) to avoid 429
PRODUCT_DELAY = 3.0
# Delay after 429 (seconds)
RATE_LIMIT_DELAY = 5.0


def load_raw_products():
    """Load all raw_data from scraped_products table."""
    conn = sqlite3.connect(SCRAPER_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT p.id, p.raw_data, p.images, p.url, p.source_site, p.scraped_at
        FROM scraped_products p
        ORDER BY p.scraped_at
    """).fetchall()
    conn.close()
    
    products = []
    for row in rows:
        raw = json.loads(row["raw_data"]) if row["raw_data"] else {}
        if not raw.get("images") and row["images"]:
            raw["images"] = json.loads(row["images"]) if isinstance(row["images"], str) else row["images"]
        if not raw.get("url") and row["url"]:
            raw["url"] = row["url"]
        products.append(raw)
    
    return products


def _fix_title_th(title_th: str, original_title: str) -> str:
    """Fix broken title_th from Mistral (returns instruction text instead of translation)."""
    if not title_th:
        return original_title
    # Detect Mistral instruction text leaked into title_th
    bad_prefixes = (
        "นี่คือคำแปล", "Here's", "Here are", "The title", "Below",
        "This is", "Here is", "Here's the", "ให้ฉัน", "ลอง", " earthqu",
    )
    for bp in bad_prefixes:
        if title_th.strip().startswith(bp):
            return original_title
    # If title_th is just the original title repeated, keep it
    if title_th.strip() == original_title.strip():
        return original_title
    return title_th


async def enrich_one(raw: dict, index: int, total: int):
    """Normalize → Enrich → Store one product."""
    pid = raw.get("product_id", raw.get("id", "?"))
    title = (raw.get("title") or raw.get("product_name") or "")[:60]
    logger.info(f"[{index+1}/{total}] {pid} — {title}")
    
    try:
        # 1. Normalize
        normalized = await ProductNormalizer.normalize(raw, source_hint="tiktok")
        logger.info(f"  ✓ Normalized: {normalized.title[:50]}")
        
        # 2. Enrich (downloads images, Mistral analysis, keywords, hashtags, gender)
        enriched = await ProductEnricher.enrich(normalized)
        
        # 3. Fix title_th (Mistral sometimes returns instruction text)
        fixed_title_th = _fix_title_th(enriched.title_th, enriched.title)
        enriched.title_th = fixed_title_th
        
        # 4. If images still empty, use original scraped images
        if not enriched.images:
            enriched.images = normalized.images
        
        logger.info(f"  ✓ Enriched: title_th={enriched.title_th[:40]}")
        logger.info(f"    gender={enriched.gender}, viral={enriched.viral_score}")
        logger.info(f"    images={len(enriched.images)}, keywords={len(enriched.keywords)}, hashtags={len(enriched.hashtags)}")
        
        # 5. Store to PostgreSQL
        store_record = {
            "product_id": enriched.product_id,
            "title": enriched.title,
            "title_th": enriched.title_th,
            "description": enriched.description,
            "price_min": enriched.price_min,
            "price_max": enriched.price_max,
            "price_avg": enriched.price_avg,
            "currency": enriched.currency,
            "rating": enriched.rating,
            "review_count": enriched.review_count,
            "sold_total": enriched.sold_total,
            "sold_week": enriched.sold_week,
            "sold_month": enriched.sold_month,
            "sales_gmv_7d": enriched.sales_gmv_7d,
            "sales_gmv_30d": enriched.sales_gmv_30d,
            "sales_gmv_total": enriched.sales_gmv_total,
            "seller_name": enriched.seller_name,
            "seller_id": enriched.seller_id,
            "categories": enriched.categories,
            "category": enriched.category,
            "images": enriched.images,
            "commission_rate": enriched.commission_rate,
            "influencer_count": enriched.influencer_count,
            "video_count": enriched.video_count,
            "rank": enriched.rank,
            "source": enriched.source,
            "scrape_timestamp": enriched.scrape_timestamp,
            "viral_score": enriched.viral_score,
            "trending": enriched.trending,
            "keywords": enriched.keywords,
            "hashtags": enriched.hashtags,
            "gender": enriched.gender,
            "target_age": enriched.target_age,
            "enriched": True,
        }
        
        record_id = await store_analyzed(store_record)
        logger.info(f"  ✓ Stored to PostgreSQL: id={record_id}")
        return True
        
    except Exception as e:
        logger.error(f"  ✗ FAILED: {e}", exc_info=True)
        return False


async def main():
    logger.info("=" * 60)
    logger.info("ENRICHMENT RUNNER v2 —4 Mistral keys + delays")
    logger.info("=" * 60)
    
    logger.info("Loading raw products from scraper.db...")
    products = load_raw_products()
    logger.info(f"Found {len(products)} products to enrich")
    
    if not products:
        logger.error("No products found!")
        return
    
    _load_mistral_keys()
    logger.info(f"Mistral keys loaded: {len(os.environ.get('MISTRAL_API_KEY', '') and [1] or []) + len([k for k in [os.environ.get(f'MISTRAL_API_KEY_{i}') for i in range(2,10)] if k])}")
    
    success = 0
    failed = 0
    
    for i, raw in enumerate(products):
        ok = await enrich_one(raw, i, len(products))
        if ok:
            success += 1
        else:
            failed += 1
        
        # Delay between products to respect rate limits
        if i < len(products) - 1:
            delay = PRODUCT_DELAY
            if not ok:
                delay = RATE_LIMIT_DELAY  # Longer delay after failure
            logger.info(f"  ⏳ Waiting {delay:.0f}s before next product...")
            await asyncio.sleep(delay)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"ENRICHMENT COMPLETE: {success} success, {failed} failed out of {len(products)}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
