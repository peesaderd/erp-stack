#!/usr/bin/env python3
"""Batch enrich products — processes 5 at a time with proper rate limiting.
Run: cd /home/openhands/erp-stack && python3 enrich_batch.py [--batch 5] [--skip-enriched]
"""
import asyncio, sqlite3, sys, os, json, time, logging

# Load .env
from pathlib import Path
_env_path = os.path.join(Path(__file__).resolve().parent, '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# Add modules to path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / 'modules'))
sys.path.insert(0, str(Path(__file__).resolve().parent / 'tiktok-ugc-studio'))

from product.analyze_pipeline import ProductEnricher, ProductNormalizer

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
logger = logging.getLogger("enrich_batch")

TUS_DB = str(Path(__file__).resolve().parent / 'tiktok-ugc-studio' / 'tus_products.db')
ANALYZED_DB = str(Path(__file__).resolve().parent / 'modules' / 'product' / 'scraper.db')


def get_unenriched_products(skip_enriched=True):
    """Get products from tus_products.db that need enrichment."""
    conn = sqlite3.connect(TUS_DB)
    conn.row_factory = sqlite3.Row
    if skip_enriched:
        rows = conn.execute("""
            SELECT * FROM tus_products
            WHERE (keywords IS NULL OR keywords = '[]' OR length(keywords) <= 5)
            ORDER BY product_id
        """).fetchall()
    else:
        rows = conn.execute("SELECT * FROM tus_products ORDER BY product_id").fetchall()
    conn.close()
    return rows


def update_product(conn, pid, product):
    """Update a single product in tus_products.db with enriched data."""
    conn.execute("""
        UPDATE tus_products SET
            title_th = ?,
            keywords = ?,
            hashtags = ?,
            gender = ?,
            target_age = ?,
            images = ?,
            category = ?,
            viral_score = ?,
            trending = ?,
            rating = ?,
            sold_total = ?,
            commission_rate = ?,
            seller_name = ?,
            notes = ?
        WHERE product_id = ?
    """, (
        product.title_th or product.title,
        json.dumps(product.keywords),
        json.dumps(product.hashtags),
        product.gender or "",
        product.target_age or "",
        json.dumps(product.images),
        product.category or "",
        product.viral_score or 0,
        1 if (product.viral_score or 0) >= 18 else 0,
        product.rating or 0,
        product.sold_total or 0,
        product.commission_rate or 0,
        product.seller_name or "",
        json.dumps({"source": product.source, "enriched_at": time.time()}),
        pid,
    ))
    conn.commit()
    
    # Sync to PostgreSQL analyzed_products (thread to avoid asyncio.run conflict)
    try:
        import threading
        def _sync_pg():
            import asyncio as _aio, asyncpg
            async def _do():
                DSN = os.environ.get('PRODUCTDB_DSN', 'postgresql://openhands:OpenHands%40ERP2026@127.0.0.1:5432/erp_stack')
                pg = await asyncpg.connect(DSN)
                await pg.execute('''
                    UPDATE analyzed_products
                    SET gender = $1, target_age = $2, hashtags = $3, updated_at = NOW()::text
                    WHERE product_id = $4
                ''', product.gender or '', product.target_age or '', json.dumps(product.hashtags), pid)
                await pg.close()
            _aio.run(_do())
        threading.Thread(target=_sync_pg, daemon=True).start()
    except Exception as e:
        logger.warning(f"PostgreSQL sync failed for {pid}: {e}")


async def enrich_batch(batch_size=5, skip_enriched=True):
    """Main enrichment loop — processes batch_size products at a time."""
    products = get_unenriched_products(skip_enriched)
    total = len(products)
    logger.info(f"Found {total} products to enrich (batch_size={batch_size})")
    
    if total == 0:
        logger.info("Nothing to enrich!")
        return

    conn = sqlite3.connect(TUS_DB)
    enriched = 0
    errors = 0
    
    for i, row in enumerate(products):
        pid = row['product_id']
        name = row['title'] or row['title_th'] or f"product_{pid}"
        
        logger.info(f"[{i+1}/{total}] Processing {name[:40]}...")
        
        try:
            # Build raw dict for normalizer
            raw = {
                "product_id": pid,
                "name": name,
                "title": name,
                "description": row['description'] or "",
                "price": row['price_thb'] or 0,
                "category": row['category'] or "",
                "source_url": row['url'] or "",
                "url": row['url'] or "",
                "images": json.loads(row['images']) if row['images'] else [],
                "sku": "",
                "seller_name": row['seller_name'] or "",
                "seller_id": "",
                "commission_rate": row['commission_rate'] or "0",
                "source_site": "tiktok",
            }
            
            # Normalize
            product = await ProductNormalizer.normalize(raw, source_hint="tiktok")
            
            # Enrich via Mistral
            product = await ProductEnricher.enrich(product)
            
            if not product.enriched:
                logger.warning(f"  SKIP enrichment failed for {pid}")
                errors += 1
                continue
            
            # Commit to DB immediately
            update_product(conn, pid, product)
            enriched += 1
            logger.info(f"  OK {pid[:18]} | gender={product.gender!r} | age={product.target_age!r} | kw={len(product.keywords)}")
            
            # Rate limit: wait between products
            await asyncio.sleep(10)
            
            # Checkpoint: print progress every batch_size
            if (i + 1) % batch_size == 0:
                logger.info(f"--- Checkpoint: {enriched}/{i+1} enriched, {errors} errors ---")
            
        except Exception as e:
            errors += 1
            logger.error(f"  FAILED {pid}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    conn.close()
    logger.info(f"\n=== DONE: {enriched} enriched, {errors} errors out of {total} products ===")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=5, help="Batch size for logging")
    parser.add_argument("--all", action="store_true", help="Re-enrich all products (not just unenriched)")
    args = parser.parse_args()
    
    asyncio.run(enrich_batch(batch_size=args.batch, skip_enriched=not args.all))
