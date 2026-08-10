"""Product routes — scrape, list, analyze (SQLite + PostgreSQL), dashboard, sheets.

Extracted from main.py monolith.
"""
import base64
import json
import os
import re
import shutil
import sqlite3
from pathlib import Path

import asyncpg
import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from models import ScrapeAndGenerateRequest
from .deps import logger, STORAGE_DIR, PRODUCT_IMAGE_DIR, PIPELINE_DB_PATH, _proxy, SCRAPER_API_URL

BASE_DIR = Path(__file__).resolve().parent.parent

# PostgreSQL DSN for Gemini-scraped products
PRODUCTDB_DSN = os.environ.get("PRODUCTDB_DSN", "postgresql://openhands:OpenHands%40ERP2026@127.0.0.1:5432/erp_stack")

router = APIRouter(tags=["product"])
@router.post("/product/scrape-and-generate")
async def scrape_and_generate(req: ScrapeAndGenerateRequest):
    """Scrape product URL, then auto-generate script."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        key_resp = await client.post(
            f"{SCRAPER_API_URL}/api/v1/keys/create",
            json={"name": "tiktok-ugc-studio"},
            headers={"x-user-id": "tiktok-ugc"}
        )
        key_data = key_resp.json()
        api_key = key_data.get("key", "")

        scrape_resp = await client.post(
            f"{SCRAPER_API_URL}/api/v1/scrape",
            json={"url": req.url, "use_vision": req.use_vision},
            headers={
                "Authorization": f"Bearer {api_key}",
                "x-user-id": "tiktok-ugc",
                "Content-Type": "application/json"
            }
        )
        scrape_data = scrape_resp.json()

    if not scrape_data.get("success"):
        raise HTTPException(status_code=502, detail=f"Product scraper failed: {scrape_data.get('error', 'unknown')}")

    product = scrape_data.get("product", {}) or {}
    product_name = product.get("name", "") or ""
    description = product.get("description", "") or ""
    price = product.get("price")
    brand = product.get("brand", "") or ""
    images = product.get("images", []) or []
    source_site = product.get("source_site", "") or ""

    if not product_name:
        raise HTTPException(status_code=400, detail="Could not extract product name from URL")

    try:
        extra_context = f"Product: {product_name}\nBrand: {brand}\nPrice: {price}\nSource: {source_site}\nDescription: {description[:300]}"

        script_result = await _proxy("POST", "video", "/api/v1/scripts/generate", {
            "product_name": product_name,
            "customer_problem": req.tone or f"Finding the right {product_name}",
            "main_benefit": description[:200] if description else "",
            "target_audience": "",
            "tone": req.tone,
            "cta": req.cta,
            "duration": req.duration,
            "extra_rules": extra_context,
            "max_chars": 350,
        })

        return {
            "success": True,
            "product": {
                "name": product_name,
                "price": price,
                "brand": brand,
                "description": description[:500],
                "images": images[:6],
                "source_site": source_site,
                "source_url": req.url,
            },
            "script": script_result,
        }
    except Exception as e:
        logger.error(f"Script generation failed: {e}")
        return {
            "success": True,
            "product": {
                "name": product_name,
                "price": price,
                "brand": brand,
                "description": description[:500],
                "images": images[:6],
                "source_site": source_site,
                "source_url": req.url,
            },
            "script": None,
            "script_error": str(e),
        }

# ─── TTS ───────────────────────────────────────────────────────────────────

@router.get("/products/list")
def list_products(limit: int = 200, preset: str = "all", search: str = ""):
    """List products from tus_products.db for the frontend product grid."""
    db_path = str(BASE_DIR / "tus_products.db")
    if not os.path.exists(db_path):
        return {"products": []}
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    if search:
        like = f"%{search}%"
        rows = conn.execute(
            "SELECT * FROM tus_products WHERE title LIKE ? ORDER BY viral_score DESC LIMIT ?",
            (like, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tus_products ORDER BY viral_score DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    
    products = []
    for row in rows:
        row_dict = dict(row)
        # Parse JSON fields
        try:
            row_dict["images"] = json.loads(row_dict["images"] or "[]")
        except (json.JSONDecodeError, TypeError):
            row_dict["images"] = []
        try:
            row_dict["keywords"] = json.loads(row_dict["keywords"] or "[]")
        except (json.JSONDecodeError, TypeError):
            row_dict["keywords"] = []
        try:
            row_dict["hashtags"] = json.loads(row_dict["hashtags"] or "[]")
        except (json.JSONDecodeError, TypeError):
            row_dict["hashtags"] = []
        row_dict["image_count"] = len(row_dict["images"])
        products.append(row_dict)
    
    return {"products": products, "total": len(products)}


PRODUCTDB_DSN = os.environ.get("PRODUCTDB_DSN", "postgresql://openhands:OpenHands%40ERP2026@127.0.0.1:5432/erp_stack")

@router.get("/products/scraped")
async def list_scraped_products(limit: int = 100, search: str = ""):
    """List products from PostgreSQL productdb.products (Gemini-scraped).
    
    Uses ai_analysis JSON column for container/closure details.
    """
    try:
        conn = await asyncpg.connect(PRODUCTDB_DSN)
        if search:
            like = f"%{search}%"
            rows = await conn.fetch(
                "SELECT id, name, description, price, category, tags, ai_analysis, image_urls, source_url "
                "FROM products WHERE name ILIKE $1 ORDER BY id ASC LIMIT $2",
                like, limit
            )
        else:
            rows = await conn.fetch(
                "SELECT id, name, description, price, category, tags, ai_analysis, image_urls, source_url "
                "FROM products ORDER BY id ASC LIMIT $1", limit
            )
        await conn.close()
        products = []
        for r in rows:
            aa = r["ai_analysis"] or {}
            if isinstance(aa, str):
                aa = json.loads(aa)
            imgs = r["image_urls"] or []
            if isinstance(imgs, str):
                imgs = json.loads(imgs)
            products.append({
                "id": r["id"],
                "title": r["name"],
                "description": r["description"] or "",
                "category": r["category"] or "General",
                "price_thb": float(r["price"] or 0),
                "commission": aa.get("commission_rate", ""),
                "source_url": r["source_url"] or "",
                "hook_concept": aa.get("script", ""),
                "container_type": aa.get("container_type", "ขวด/ภาชนะทรงมาตรฐาน"),
                "closure_type": aa.get("closure_type", "ฝาปิดมาตรฐาน"),
                "label_colors": aa.get("label_colors", "สีบรรจุภัณฑ์ตามภาพ"),
                "product_color": aa.get("product_color", "เนื้อสัมผัสธรรมชาติ"),
                "tags": r["tags"] if isinstance(r["tags"], list) else [],
                "images": imgs if isinstance(imgs, list) else [],
                "image_count": len(imgs) if isinstance(imgs, list) else 0,
                "source": "scraped",
            })
        return {"success": True, "products": products, "total": len(products)}
    except Exception as e:
        logger.error(f"list_scraped_products failed: {e}")
        return {"success": False, "products": [], "total": 0, "error": str(e)}


@router.post("/products/analyze-scraped")
async def analyze_scraped_products():
    """Read scraped products -> Normalize -> Enrich (Mistral) -> Store in analyzed_products -> Write to tus_products.db.

    No fallbacks. If enrichment fails, the product is skipped with error logged.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from modules.product.analyze_pipeline import ProductNormalizer, ProductEnricher
    from modules.product.analyzer_db import store_analyzed, store_analyzed_batch

    # 1. Read from PostgreSQL products table
    try:
        conn = await asyncpg.connect(PRODUCTDB_DSN)
        rows = await conn.fetch(
            "SELECT id, name, description, price, category, source_url, image_urls, ai_analysis, sku FROM products ORDER BY id ASC"
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
            price = float(r["price"] or 0)
            description = r["description"] or ""
            category = r["category"] or ""
            source_url = r["source_url"] or ""
            image_urls_raw = r["image_urls"]
            sku = r["sku"] or ""
            ai_analysis = r["ai_analysis"]

            # Parse image_urls (might be JSON string or list)
            if isinstance(image_urls_raw, str):
                try:
                    image_urls = json.loads(image_urls_raw)
                except Exception:
                    image_urls = [image_urls_raw] if image_urls_raw else []
            elif isinstance(image_urls_raw, list):
                image_urls = image_urls_raw
            else:
                image_urls = []

            # Skip if already in analyzed_products (check via store_analyzed dedup)
            # store_analyzed does upsert by product_id+source, so we check if enriched=True
            # For now, just proceed - store_analyzed will handle dedup

            # 2. Normalize
            raw = {
                "product_id": str(row_id),
                "name": name,
                "title": name,
                "description": description,
                "price": price,
                "category": category,
                "source_url": source_url,
                "url": source_url,
                "images": image_urls,
                "sku": sku,
                "seller_name": "",
                "seller_id": "",
                "commission_rate": "0",
                "source_site": "tiktok",
            }
            product = await ProductNormalizer.normalize(raw, source_hint="tiktok")

            # 3. Enrich (Mistral) - NO FALLBACK, let errors propagate
            product = await ProductEnricher.enrich(product)
            if not product.enriched:
                raise Exception(f"Enrichment failed for product {row_id}: {product.title}")

            # 4. Store in analyzed_products (SSOT)
            product_dict = {
                "product_id": product.product_id,
                "title": product.title,
                "title_th": product.title_th or product.title,
                "description": product.description,
                "price_min": product.price_min or 0,
                "price_max": product.price_max or 0,
                "price_avg": product.price_avg or 0,
                "price_thb": product.price_min or 0,
                "source": product.source or "tiktok",
                "category": product.category or "",
                "commission_rate": product.commission_rate or 0,
                "seller_name": product.seller_name or "",
                "seller_id": product.seller_id or "",
                "keywords": product.keywords or [],
                "hashtags": product.hashtags or [],
                "gender": product.gender or "",
                "target_age": product.target_age or "",
                "images": product.images or [],
                "sold_total": product.sold_total or 0,
                "viral_score": product.viral_score or 0,
                "enriched": product.enriched or False,
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


# ─── UGC Frontend API Compatibility ───────────────────────────────────────

@router.post("/product/analyze")
async def analyze_product(
    product_name: str = Form(...),
    description: str = Form(""),
    age_group: str = Form(""),
    gender: str = Form(""),
    file: UploadFile = File(None),
):
    """Analyze product via Gemini vision."""
    from gemini_agent import analyze_product as gemini_analyze
    
    image_base64 = None
    if file and file.filename:
        contents = await file.read()
        if contents:
            image_base64 = base64.b64encode(contents).decode("utf-8")
    
    try:
        result = gemini_analyze(
            product_name=product_name,
            description=description,
            category="",
            target_audience="",
            age_group=age_group or None,
            gender=gender,
            image_base64=image_base64,
        )
        return {
            "success": True,
            "analysis": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── Dashboard Summary ──────────────────────────────────────────────────

@router.get("/dashboard/summary")
def dashboard_summary():
    """Dashboard summary: credits, counts, recent jobs, quick actions."""
    total_videos = 0
    total_products = 0
    recent_jobs = []

    # Read pipeline.db -> total_videos + recent_jobs
    if os.path.exists(PIPELINE_DB_PATH):
        try:
            conn = sqlite3.connect(PIPELINE_DB_PATH)
            # Total jobs count
            row = conn.execute("SELECT COUNT(*) FROM pipeline_jobs").fetchone()
            total_videos = row[0] if row else 0

            # Recent jobs (last 10)
            rows = conn.execute(
                "SELECT job_id, account_id, status, product_url, created_at, updated_at "
                "FROM pipeline_jobs ORDER BY REPLACE(created_at, ' ', 'T') DESC LIMIT 10"
            ).fetchall()
            conn.close()
            for r in rows:
                recent_jobs.append({
                    "id": r[0],
                    "account_id": r[1],
                    "status": r[2],
                    "product_url": r[3],
                    "created_at": r[4],
                    "updated_at": r[5],
                })
        except Exception as e:
            logger.warning(f"Dashboard pipeline.db read error: {e}")

    # Read tus_products.db -> total_products
    products_db_path = str(BASE_DIR / "tus_products.db")
    if os.path.exists(products_db_path):
        try:
            conn = sqlite3.connect(products_db_path)
            row = conn.execute("SELECT COUNT(*) FROM tus_products").fetchone()
            total_products = row[0] if row else 0
            conn.close()
        except Exception as e:
            logger.warning(f"Dashboard products.db read error: {e}")

    # Credit balance (placeholder / from file)
    credit_balance = 0.0
    credit_file = str(BASE_DIR / "credit_balance.txt")
    if os.path.exists(credit_file):
        try:
            with open(credit_file) as f:
                credit_balance = float(f.read().strip() or "0")
        except Exception:
            pass

    return {
        "success": True,
        "credit_balance": credit_balance,
        "total_videos": total_videos,
        "total_products": total_products,
        "recent_jobs": recent_jobs,
        "quick_actions": ["generate_video", "import_products", "post_tiktok", "scheduled_posts"],
    }

# ─── Google Sheets Status ───────────────────────────────────────────────

@router.get("/products/sheets/status")
async def sheets_status():
    """Check Google Sheets credentials configuration."""
    try:
        # Try to import sheets export_service
        try:
            from export_service import is_ready as sheets_is_ready
            from export_service import get_setup_instructions as sheets_instructions
            configured = sheets_is_ready()
            instructions = sheets_instructions() if not configured else None
        except ImportError:
            configured = False
            instructions = {"steps": ["pip install gspread google-auth"]}
        
        creds_path = str(BASE_DIR / "modules" / "product" / "sheets_credentials.json")
        sheet_id = os.environ.get("MEDIA_SHEET_ID", "")
        return {
            "success": True,
            "configured": configured,
            "credentials_file_exists": os.path.exists(creds_path),
            "credentials_path": creds_path,
            "spreadsheet_id": sheet_id,
            "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit" if sheet_id else "",
            "instructions": instructions,
        }
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}

# ─── Pipeline Recipes ────────────────────────────────────────────────────

