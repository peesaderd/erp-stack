#!/usr/bin/env python3
"""Enrich gender + hashtags for products missing them in tus_products.db.
Run: cd /home/openhands/erp-stack && python3 enrich_gender.py [--limit 10]
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

from product.analyze_pipeline import _call_mistral, _extract_gender_age_hashtags, _split_hashtags

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger("enrich_gender")

TUS_DB = str(Path(__file__).resolve().parent / 'tiktok-ugc-studio' / 'tus_products.db')


def get_products_missing_gender(limit=10):
    """Get products missing gender from tus_products.db."""
    conn = sqlite3.connect(TUS_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT product_id, title, description, category, gender, target_age, hashtags
        FROM tus_products
        WHERE (gender IS NULL OR gender = '')
        ORDER BY product_id
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows


async def enrich_gender_for_product(product):
    """Enrich gender, target_age, and hashtags for a single product."""
    pid = product['product_id']
    title = product['title'] or ''
    description = product['description'] or ''
    category = product['category'] or ''
    
    # Call Mistral for gender/age/hashtags
    meta = await _extract_gender_age_hashtags(title, description, category)
    
    gender = meta.get('gender', '')
    target_age = meta.get('target_age', '')
    hashtags = _split_hashtags(meta.get('hashtags', []))
    
    return {
        'gender': gender,
        'target_age': target_age,
        'hashtags': hashtags,
    }


def update_product_in_db(conn, pid, gender, target_age, hashtags):
    """Update gender, target_age, and hashtags in tus_products.db."""
    conn.execute("""
        UPDATE tus_products SET
            gender = ?,
            target_age = ?,
            hashtags = ?
        WHERE product_id = ?
    """, (gender, target_age, json.dumps(hashtags), pid))
    conn.commit()
    
    # Sync to PostgreSQL analyzed_products
    try:
        import asyncio
        async def _sync_pg():
            import asyncpg
            DSN = os.environ.get('PRODUCTDB_DSN', 'postgresql://openhands:OpenHa…2026@127.0.0.1:5432/erp_stack')
            conn_pg = await asyncpg.connect(DSN)
            await conn_pg.execute("""
                UPDATE analyzed_products
                SET gender = $1, target_age = $2, hashtags = $3, updated_at = NOW()::text
                WHERE product_id = $4
            """, gender, target_age, json.dumps(hashtags), pid)
            await conn_pg.close()
        asyncio.run(_sync_pg())
    except Exception as e:
        logger.warning(f"PostgreSQL sync failed for {pid}: {e}")


async def enrich_batch(limit=10):
    """Main enrichment loop."""
    products = get_products_missing_gender(limit)
    total = len(products)
    logger.info(f"Found {total} products missing gender")
    
    if total == 0:
        logger.info("Nothing to enrich!")
        return

    conn = sqlite3.connect(TUS_DB)
    enriched = 0
    errors = 0
    
    for i, product in enumerate(products):
        pid = product['product_id']
        title = product['title'][:40] if product['title'] else f"product_{pid}"
        
        logger.info(f"[{i+1}/{total}] {title}...")
        
        try:
            result = await enrich_gender_for_product(product)
            
            update_product_in_db(conn, pid, result['gender'], result['target_age'], result['hashtags'])
            
            enriched += 1
            logger.info(f"  ✅ gender={result['gender']!r} age={result['target_age']!r} hashtags={len(result['hashtags'])}")
            
            # Rate limit: wait between products
            await asyncio.sleep(10)
            
        except Exception as e:
            errors += 1
            logger.error(f"  ❌ {pid}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    conn.close()
    logger.info(f"\n=== DONE: {enriched} enriched, {errors} errors out of {total} ===")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10, help="Number of products to process")
    args = parser.parse_args()
    
    asyncio.run(enrich_batch(limit=args.limit))
