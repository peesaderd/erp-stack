#!/usr/bin/env python3
"""Fix images for products that have images=0 in PostgreSQL.
Downloads images from original URLs and stores them back."""
import asyncio, json, sqlite3, sys, os, logging, uuid
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("fix_images")

sys.path.insert(0, "/home/openhands/erp-stack")
from dotenv import load_dotenv
load_dotenv("/home/openhands/erp-stack/.env")

from product.analyze_pipeline import _download_images_local, PRODUCT_IMAGE_DIR
from product.analyzer_db import store_analyzed
import httpx

SCRAPER_DB = "/home/openhands/erp-stack/modules/product/scraper.db"
DATAIMPULSE_PROXY = os.environ.get("DATAIMPULSE_PROXY", "")
PROXY_DICT = {"http": DATAIMPULSE_PROXY, "https": DATAIMPULSE_PROXY} if DATAIMPULSE_PROXY else None


def load_raw_products():
    conn = sqlite3.connect(SCRAPER_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, raw_data, images FROM scraped_products ORDER BY scraped_at").fetchall()
    conn.close()
    products = []
    for row in rows:
        raw = json.loads(row["raw_data"]) if row["raw_data"] else {}
        if not raw.get("images") and row["images"]:
            raw["images"] = json.loads(row["images"]) if isinstance(row["images"], str) else row["images"]
        products.append(raw)
    return products


async def fix_one(raw, index, total):
    pid = raw.get("product_id", "?")
    images = raw.get("images", [])
    title = raw.get("title", "")[:50]
    logger.info(f"[{index+1}/{total}] {pid} — {title} — {len(images)} images")

    if not images:
        logger.warning(f"  No images in raw data, skipping")
        return False

    # Download images to local storage
    try:
        downloaded = await _download_images_local(pid, images)
        local_urls = [img["url"] for img in downloaded if img.get("url")]
        logger.info(f"  Downloaded: {len([d for d in downloaded if d.get('size', 0) > 0])}/{len(images)} → {len(local_urls)} URLs")

        if local_urls:
            # Update PostgreSQL
            store_record = {
                "product_id": pid,
                "images": local_urls,
                "source": "tiktok",
            }
            record_id = await store_analyzed(store_record)
            logger.info(f"  ✓ Updated images in PostgreSQL: {len(local_urls)} images, id={record_id}")
            return True
        else:
            logger.warning(f"  All image downloads failed, keeping original URLs")
            store_record = {
                "product_id": pid,
                "images": images,  # Keep original URLs as fallback
                "source": "tiktok",
            }
            record_id = await store_analyzed(store_record)
            logger.info(f"  ✓ Set original URLs as fallback, id={record_id}")
            return True
    except Exception as e:
        logger.error(f"  ✗ FAILED: {e}")
        return False


async def main():
    logger.info("=" * 60)
    logger.info("FIX IMAGES — Download + store for all 15 products")
    logger.info("=" * 60)

    products = load_raw_products()
    logger.info(f"Found {len(products)} products")

    success = 0
    for i, raw in enumerate(products):
        ok = await fix_one(raw, i, len(products))
        if ok:
            success += 1
        if i < len(products) - 1:
            await asyncio.sleep(1)

    logger.info(f"\n{'='*60}")
    logger.info(f"COMPLETE: {success}/{len(products)} images fixed")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
