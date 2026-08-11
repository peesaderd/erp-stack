#!/usr/bin/env python3
"""Sync enriched products from PostgreSQL → tus_products.db (TUS Product).
Overwrites old data with fresh enriched data."""
import asyncio, json, sqlite3, sys, os, logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("sync_tus")

sys.path.insert(0, "/home/openhands/erp-stack")
from dotenv import load_dotenv
load_dotenv("/home/openhands/erp-stack/.env")

from product.analyzer_db import get_analyzed_products

TUS_DB = "/home/openhands/erp-stack/tiktok-ugc-studio/tus_products.db"


async def sync():
    logger.info("=" * 60)
    logger.info("SYNC: PostgreSQL enriched → TUS products.db")
    logger.info("=" * 60)

    # Get all enriched products from PostgreSQL
    result = await get_analyzed_products(limit=200)
    products = result.get("products", [])
    logger.info(f"PostgreSQL: {len(products)} products")

    # Connect to TUS DB
    conn = sqlite3.connect(TUS_DB)
    conn.row_factory = sqlite3.Row

    # Check existing
    existing = {r["product_id"]: dict(r) for r in conn.execute("SELECT * FROM tus_products").fetchall()}
    logger.info(f"TUS existing: {len(existing)} products")

    synced = 0
    created = 0
    for p in products:
        pid = p.get("product_id", "")
        if not pid or len(pid) < 10:
            # Skip empty or short/junk product IDs
            continue

        images_raw = p.get("images", [])
        keywords = p.get("keywords", [])
        hashtags = p.get("hashtags", [])
        viral = p.get("viral_score", 0)
        gender = p.get("gender", "")

        # Convert CDN URLs to local paths if local file exists
        images = []
        img_dir = "/home/openhands/erp-stack/tiktok-ugc-studio/storage/product_images"
        for img_url in images_raw:
            local_file = os.path.join(img_dir, f"{pid}.jpg")
            if os.path.exists(local_file):
                images.append(f"/ugc/static/product_images/{pid}.jpg")
            else:
                images.append(img_url)  # fallback to CDN URL

        # Build URL from images or TikTok
        url = f"https://www.tiktok.com/@product/{pid}" if not p.get("url") else p.get("url", "")

        # Determine category from keywords or title
        category = p.get("category", "")
        if not category and keywords:
            cat_map = {"lipstick": "cosmetics", "lip": "cosmetics", "serum": "skincare", 
                       "cream": "skincare", "vitamin": "health", "diaper": "baby",
                       "soap": "personal_care", "trash": "household"}
            for kw in keywords[:5]:
                for k, v in cat_map.items():
                    if k in kw.lower():
                        category = v
                        break
                if category:
                    break

        row = {
            "product_id": pid,
            "title": p.get("title", ""),
            "title_th": p.get("title_th", "") or p.get("title", ""),
            "price_thb": p.get("price_thb", 0) or p.get("price_avg", 0) or p.get("price_min", 0),
            "rating": p.get("rating", 0),
            "sold_total": p.get("sold_total", 0),
            "viral_score": viral,
            "trending": 1 if viral >= 18 else 0,
            "category": category,
            "commission_rate": p.get("commission_rate", 0),
            "seller_name": p.get("seller_name", ""),
            "seller_id": p.get("seller_id", ""),
            "url": url,
            "description": p.get("description", ""),
            "description_th": "",
            "images": json.dumps(images),
            "keywords": json.dumps(keywords),
            "hashtags": json.dumps(hashtags),
            "source": "tiktok",
            "imported_at": datetime.utcnow().isoformat(),
            "tus_status": "pending",
            "gender": gender,
            "target_age": p.get("target_age", ""),
            "notes": json.dumps({"gender": gender, "target_age": p.get("target_age", "")}),
        }

        if pid in existing:
            # Update existing
            sets = ", ".join(f"{k} = ?" for k in row.keys())
            conn.execute(f"UPDATE tus_products SET {sets} WHERE product_id = ?", list(row.values()) + [pid])
            synced += 1
        else:
            # Insert new
            cols = ", ".join(row.keys())
            placeholders = ", ".join(["?"] * len(row))
            conn.execute(f"INSERT INTO tus_products ({cols}) VALUES ({placeholders})", list(row.values()))
            created += 1

        logger.info(f"  ✓ {pid[:18]} | imgs={len(images)} kw={len(keywords)} ht={len(hashtags)} viral={viral} cat={category}")

    conn.commit()
    conn.close()

    logger.info(f"\n{'='*60}")
    logger.info(f"SYNC COMPLETE: {synced} updated, {created} created = {synced + created} total")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(sync())
