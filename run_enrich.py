#!/usr/bin/env python3
"""Run enrichment pipeline for all scraped products.
Reads raw_data from scraper.db, normalizes, enriches (downloads images + Mistral vision),
and stores to PostgreSQL via analyzer_db.
"""
import asyncio, json, sqlite3, sys, os, logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("enrich_runner")

# Ensure product module is importable
sys.path.insert(0, "/home/openhands/erp-stack")

from product.analyze_pipeline import (
    ProductNormalizer, ProductEnricher, ProductExporter,
    _load_mistral_keys, _download_images_local, _analyze_and_select_images,
    PRODUCT_IMAGE_DIR,
)
from product.analyzer_db import store_analyzed

SCRAPER_DB = "/home/openhands/erp-stack/modules/product/scraper.db"


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
        # Inject images from scraped_products.images (JSON array)
        if not raw.get("images") and row["images"]:
            raw["images"] = json.loads(row["images"]) if isinstance(row["images"], str) else row["images"]
        # Inject URL
        if not raw.get("url") and row["url"]:
            raw["url"] = row["url"]
        products.append(raw)
    
    return products


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
        logger.info(f"  ✓ Enriched: title_th={enriched.title_th[:30]}, gender={enriched.gender}, viral={enriched.viral_score}")
        logger.info(f"    images: {len(enriched.images)}, keywords: {len(enriched.keywords)}, hashtags: {len(enriched.hashtags)}")
        
        # 3. Export for TUS
        exported = ProductExporter.export_for_tus([enriched])
        tus_data = exported["products"][0] if exported["products"] else {}
        
        # 4. Store to PostgreSQL
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
    logger.info("Loading raw products from scraper.db...")
    products = load_raw_products()
    logger.info(f"Found {len(products)} products to enrich")
    
    if not products:
        logger.error("No products found!")
        return
    
    _load_mistral_keys()
    
    success = 0
    failed = 0
    
    for i, raw in enumerate(products):
        ok = await enrich_one(raw, i, len(products))
        if ok:
            success += 1
        else:
            failed += 1
        # Small delay between products to avoid rate limits
        if i < len(products) - 1:
            await asyncio.sleep(1.0)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"ENRICHMENT COMPLETE: {success} success, {failed} failed out of {len(products)}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
