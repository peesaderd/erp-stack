@router.post("/products/analyze-scraped")
async def analyze_scraped_products():
    """Read scraped products -> Normalize -> Enrich (Mistral) -> Store in analyzed_products -> Write to tus_products.db.

    No fallbacks. If enrichment fails, the product is skipped with error logged.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from product.analyze_pipeline import ProductNormalizer, ProductEnricher
    from product.analyzer_db import store_analyzed_batch, get_analyzed_product

    # 1. Read from PostgreSQL products table
    try:
        conn = await asyncpg.connect(PRODUCTDB_DSN)
        rows = await conn.fetch(
            "SELECT id, name, data::text, source_site FROM products ORDER BY id ASC"
        )
        await conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PostgreSQL read failed: {e}")

    db_path = str(BASE_DIR / "tus_products.db")
    tus_conn = sqlite3.connect(db_path)
    enriched = 0
    skipped = 0
    errors = []

    for r in rows:
        try:
            row_id = r["id"]
            name = r["name"]
            data = json.loads(r["data"]) if isinstance(r["data"], str) else {}
            source_site = r.get("source_site", "tiktok")

            # Skip if already in analyzed_products and enriched
            existing = await get_analyzed_product(str(row_id))
            if existing and existing.get("enriched"):
                skipped += 1
                continue

            # 2. Normalize
            raw = {**data, "name": name, "product_id": str(row_id), "source_site": source_site}
            product = ProductNormalizer.normalize(raw, source=source_site)

            # 3. Enrich (Mistral) - NO FALLBACK, let errors propagate
            product = await ProductEnricher.enrich(product)
            if not product.enriched:
                raise Exception(f"Enrichment failed for product {row_id}: {product.title}")

            # 4. Store in analyzed_products (SSOT)
            product_dict = {
                "product_id": product.product_id,
                "title": product.title,
                "title_th": product.title_th,
                "description": product.description,
                "price_min": product.price_min,
                "price_max": product.price_max,
                "price_avg": (product.price_min + product.price_max) / 2 if product.price_min and product.price_max else product.price_min or product.price_max or 0,
                "price_thb": product.price_min or 0,
                "source": product.source,
                "category": product.category,
                "commission_rate": product.commission_rate,
                "seller_name": product.seller_name,
                "seller_id": product.seller_id,
                "url": product.url,
                "keywords": product.keywords,
                "hashtags": product.hashtags,
                "gender": product.gender,
                "target_age": product.target_age,
                "images": product.images,
                "sold_total": product.sold_total,
                "viral_score": product.viral_score,
            }
            await store_analyzed_batch([product_dict])

            # 5. Write to tus_products.db
            existing_tus = tus_conn.execute(
                "SELECT keywords FROM tus_products WHERE product_id = ?",
                (product.product_id,)
            ).fetchone()
            if existing_tus:
                try:
                    existing_kw = json.loads(existing_tus[0]) if existing_tus[0] else []
                except Exception:
                    existing_kw = []
                if len(existing_kw) > 2:
                    skipped += 1
                    continue

            tus_conn.execute("""
                INSERT OR REPLACE INTO tus_products
                (product_id, title, title_th, price_thb, rating, sold_total, viral_score,
                 trending, category, commission_rate, seller_name, seller_id, url,
                 description, description_th, images, keywords, hashtags, gender, target_age,
                 source, imported_at, tus_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), 'pending')
            """, (
                product.product_id,
                product.title,
                product.title_th or product.title,
                product.price_min or 0,
                0,
                product.sold_total or 0,
                product.viral_score or 0,
                1 if (product.viral_score or 0) >= 18 else 0,
                product.category or "",
                product.commission_rate or 0,
                product.seller_name or "",
                product.seller_id or "",
                product.url or "",
                product.description or "",
                product.description or "",
                json.dumps(product.images),
                json.dumps(product.keywords),
                json.dumps(product.hashtags),
                product.gender or "",
                product.target_age or "",
                product.source or "tiktok",
            ))
            enriched += 1
            logger.info(f"  OK {product.product_id[:18]} | gender={product.gender!r} | age={product.target_age!r} | kw={len(product.keywords)}")

        except Exception as e:
            error_msg = f"Row {r.get('id','?')}: {e}"
            logger.error(f"analyze-scraped FAILED: {error_msg}")
            errors.append(error_msg)

    tus_conn.commit()
    total = tus_conn.execute("SELECT count(*) FROM tus_products").fetchone()[0]
    tus_conn.close()

    return {
        "success": len(errors) == 0,
        "enriched": enriched,
        "skipped": skipped,
        "errors": errors,
        "total_in_tus": total,
        "message": f"Enriched {enriched}, skipped {skipped}, errors {len(errors)}",
    }
