#!/usr/bin/env python3
"""
TUS Product Importer — Import new products from Analysis Module into TUS system.

1. Fetches all analyzed products from Product Scraper API (:8106/api/v1/analyze/export)
2. Compares against TUS local product tracking DB
3. Imports NEW products (not yet in TUS)
4. Logs results

Usage:
    python3 tus_import_products.py
    python3 tus_import_products.py --limit 30
    python3 tus_import_products.py --preset auto_affiliate
"""

import os, sys, json, sqlite3, uuid, httpx, asyncio, logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tus-import")

# ─── Config ────────────────────────────────────────────────────────────
ANALYZER_API = os.environ.get("ANALYZER_API", "http://localhost:8106")
TUS_DB_PATH = os.path.join(os.path.dirname(__file__), "tus_products.db")
TUS_API = os.environ.get("TUS_API", "http://localhost:8105")

# ─── TUS Product DB ───────────────────────────────────────────────────

def _init_db():
    """Initialize TUS product tracking database."""
    os.makedirs(os.path.dirname(TUS_DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(TUS_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tus_products (
            product_id TEXT PRIMARY KEY,
            title TEXT,
            title_th TEXT,
            price_thb REAL,
            rating REAL,
            sold_total INTEGER,
            viral_score REAL,
            trending INTEGER DEFAULT 0,
            category TEXT,
            commission_rate REAL,
            seller_name TEXT,
            seller_id TEXT,
            url TEXT,
            description TEXT,
            description_th TEXT,
            images TEXT DEFAULT '[]',
            keywords TEXT DEFAULT '[]',
            source TEXT DEFAULT 'tiktok',
            imported_at TEXT,
            tus_status TEXT DEFAULT 'pending',
            notes TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS import_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            product_id TEXT,
            action TEXT,
            status TEXT,
            message TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()
    logger.info(f"DB ready: {TUS_DB_PATH}")


def _get_tus_product_ids():
    """Get all product IDs currently in TUS tracking DB."""
    conn = sqlite3.connect(TUS_DB_PATH)
    rows = conn.execute("SELECT product_id FROM tus_products").fetchall()
    conn.close()
    return set(r[0] for r in rows)


def _insert_product(p: dict, run_id: str):
    """Insert a new product from analysis into TUS DB."""
    images_json = json.dumps(p.get("images", []), ensure_ascii=False)
    keywords_json = json.dumps(p.get("keywords", []), ensure_ascii=False)

    conn = sqlite3.connect(TUS_DB_PATH)
    conn.execute("""
        INSERT OR REPLACE INTO tus_products (
            product_id, title, title_th, price_thb, rating, sold_total,
            viral_score, trending, category, commission_rate,
            seller_name, seller_id, url, description, description_th,
            images, keywords, source, imported_at, tus_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        p.get("product_id", ""),
        p.get("title", ""),
        p.get("title_th", ""),
        p.get("price_thb", 0),
        p.get("rating", 0),
        p.get("sold_total", 0),
        p.get("viral_score", 0),
        1 if p.get("trending") else 0,
        p.get("category", ""),
        p.get("commission_rate", 0),
        p.get("seller_name", ""),
        p.get("seller_id", ""),
        p.get("url", "") or p.get("link", ""),
        p.get("description", ""),
        p.get("description_th", ""),
        images_json,
        keywords_json,
        p.get("source", "tiktok"),
        datetime.utcnow().isoformat(),
        "pending",
    ))
    conn.commit()
    conn.close()

    # Log import
    conn = sqlite3.connect(TUS_DB_PATH)
    conn.execute("""
        INSERT INTO import_log (run_id, product_id, action, status, message, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (run_id, p.get("product_id", ""), "import", "success", f"Imported: {p.get('title', '')[:80]}", datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()


# ─── Analysis API Client ──────────────────────────────────────────────

async def fetch_analyzed_products(
    min_rating: float = None,
    min_sold: int = None,
    commission: float = None,
    category: str = None,
    limit: int = 100,
) -> list:
    """Fetch analyzed products from Product Scraper's Analysis module."""
    params = {"limit": limit}
    if min_rating is not None: params["min_rating"] = min_rating
    if min_sold is not None: params["min_sold"] = min_sold
    if commission is not None: params["commission"] = commission
    if category is not None: params["category"] = category

    url = f"{ANALYZER_API}/api/v1/analyze/export"
    logger.info(f"Fetching from: {url} params={params}")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        products = data.get("products", [])
        logger.info(f"Got {len(products)} products from Analysis module")
        return products


# ─── Main Import Logic ────────────────────────────────────────────────

async def import_new_products(
    limit: int = 50,
    preset: str = "auto_affiliate",
    dry_run: bool = False,
) -> dict:
    """Import new products from Analysis into TUS system."""
    _init_db()

    run_id = f"import_{uuid.uuid4().hex[:8]}"
    logger.info(f"=== TUS Product Import Run: {run_id} === (preset={preset}, limit={limit})")

    # Fetch from Analysis
    products = await fetch_analyzed_products(limit=limit)

    if not products:
        logger.warning("No products from Analysis module!")
        return {"run_id": run_id, "status": "empty", "products": []}

    # Get existing TUS product IDs
    existing_ids = _get_tus_product_ids()
    logger.info(f"Existing TUS products: {len(existing_ids)}")

    # Find new products
    new_products = [p for p in products if p.get("product_id") not in existing_ids]
    logger.info(f"New products to import: {len(new_products)}")

    # Apply preset-like filtering
    FILTERS = {
        "auto_affiliate": {"min_rating": 4.0, "min_sold": 10000, "min_viral": 20},
        "viral_short": {"min_rating": 4.0, "min_sold": 50000, "min_viral": 50},
        "carousel": {"min_rating": 4.5, "min_sold": 10000, "min_viral": 10},
        "all": {},
    }

    preset_filter = FILTERS.get(preset, FILTERS["all"])
    filtered = []
    for p in new_products:
        fr = preset_filter
        if fr.get("min_rating") and (p.get("rating") or 0) < fr["min_rating"]:
            continue
        if fr.get("min_sold") and (p.get("sold_total") or 0) < fr["min_sold"]:
            continue
        if fr.get("min_viral") and (p.get("viral_score") or 0) < fr["min_viral"]:
            continue
        filtered.append(p)

    logger.info(f"After preset filter '{preset}': {len(filtered)} products")

    if dry_run:
        logger.info(f"=== DRY RUN — no products imported ===")
        return {
            "run_id": run_id,
            "status": "dry_run",
            "total_available": len(products),
            "new_found": len(new_products),
            "after_filter": len(filtered),
            "products": [
                {
                    "product_id": p.get("product_id"),
                    "title": p.get("title", "")[:80],
                    "price": p.get("price_thb"),
                    "viral_score": p.get("viral_score"),
                    "sold_total": p.get("sold_total"),
                    "category": p.get("category"),
                    "commission_rate": p.get("commission_rate"),
                }
                for p in filtered
            ],
        }

    # Import products
    imported = []
    for p in filtered:
        try:
            _insert_product(p, run_id)
            imported.append({
                "product_id": p.get("product_id"),
                "title": p.get("title", "")[:80],
                "status": "imported",
            })
            logger.info(f"  ✓ Imported: {p.get('title', '')[:60]} ({p.get('product_id')})")
        except Exception as e:
            logger.error(f"  ✗ Failed to import {p.get('product_id')}: {e}")

    summary = {
        "run_id": run_id,
        "status": "completed",
        "total_available": len(products),
        "existing_in_tus": len(existing_ids),
        "new_found": len(new_products),
        "after_filter": len(filtered),
        "imported": len(imported),
        "products": imported,
        "timestamp": datetime.utcnow().isoformat(),
    }

    logger.info(f"=== Import Summary ===")
    logger.info(f"  Available: {summary['total_available']}")
    logger.info(f"  Existing in TUS: {summary['existing_in_tus']}")
    logger.info(f"  New found: {summary['new_found']}")
    logger.info(f"  After filter: {summary['after_filter']}")
    logger.info(f"  Imported: {summary['imported']}")

    return summary


def list_tus_products(status: str = None, limit: int = 20) -> list:
    """List products currently in TUS tracking DB."""
    _init_db()
    conn = sqlite3.connect(TUS_DB_PATH)
    if status:
        rows = conn.execute(
            "SELECT product_id, title, price_thb, category, viral_score, commission_rate, tus_status, imported_at FROM tus_products WHERE tus_status = ? ORDER BY imported_at DESC LIMIT ?",
            (status, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT product_id, title, price_thb, category, viral_score, commission_rate, tus_status, imported_at FROM tus_products ORDER BY imported_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()

    return [
        {
            "product_id": r[0],
            "title": r[1],
            "price": r[2],
            "category": r[3],
            "viral_score": r[4],
            "commission_rate": r[5],
            "tus_status": r[6],
            "imported_at": r[7],
        }
        for r in rows
    ]


def import_log(limit: int = 20) -> list:
    """Show recent import log entries."""
    _init_db()
    conn = sqlite3.connect(TUS_DB_PATH)
    rows = conn.execute(
        "SELECT id, run_id, product_id, action, status, message, created_at FROM import_log ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "run_id": r[1],
            "product_id": r[2],
            "action": r[3],
            "status": r[4],
            "message": r[5],
            "created_at": r[6],
        }
        for r in rows
    ]


# ─── CLI entry point ──────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TUS Product Importer")
    parser.add_argument("--limit", type=int, default=50, help="Max products to fetch from Analysis")
    parser.add_argument("--preset", type=str, default="auto_affiliate",
                        choices=["auto_affiliate", "viral_short", "carousel", "all"],
                        help="Filter preset for product selection")
    parser.add_argument("--dry-run", action="store_true", help="Preview without importing")
    parser.add_argument("--list", action="store_true", help="List TUS products")
    parser.add_argument("--list-status", type=str, default=None, help="Filter TUS list by status")
    parser.add_argument("--log", action="store_true", help="Show import log")

    args = parser.parse_args()

    if args.list:
        products = list_tus_products(status=args.list_status, limit=args.limit)
        print(json.dumps({"products": products, "count": len(products)}, indent=2, ensure_ascii=False))
        sys.exit(0)

    if args.log:
        entries = import_log(limit=args.limit)
        print(json.dumps({"log": entries, "count": len(entries)}, indent=2, ensure_ascii=False))
        sys.exit(0)

    result = asyncio.run(import_new_products(
        limit=args.limit,
        preset=args.preset,
        dry_run=args.dry_run,
    ))

    print(json.dumps(result, indent=2, ensure_ascii=False))
