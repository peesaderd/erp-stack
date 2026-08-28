"""Product routes — scrape, list, dashboard, sheets.

Data flow:
  1. Scraper → PostgreSQL products table
  2. Enrich scripts → PostgreSQL analyzed_products table
  3. Sync scripts → tus_products.db (frontend cache)

Do NOT write to tus_products.db from endpoints.
"""
import asyncio
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



@router.post("/apify/scrape")
async def apify_scrape(req: dict):
    """TUS entry: share link / keyword -> Apify actor -> ingest -> TUS Product.
    Proxies to product-scraper (port 8106) /api/v1/apify/scrape.
    Body: { link?, keyword?, region?, limit? }
    """
    link = req.get("link", "") or ""
    keyword = req.get("keyword", "") or ""
    region = req.get("region", "") or ""
    limit = req.get("limit", 5)

    if not link and not keyword:
        raise HTTPException(status_code=400, detail="ต้องส่ง link หรือ keyword อย่างน้อยหนึ่งอย่าง")

    async with httpx.AsyncClient(timeout=180.0) as client:
        try:
            resp = await client.post(
                f"{SCRAPER_API_URL}/api/v1/apify/scrape",
                json={
                    "link": link,
                    "keyword": keyword,
                    "region": region,
                    "limit": int(limit),
                },
                timeout=180.0,
            )
            data = resp.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Apify scrape error: {e}")

    if not data.get("success"):
        raise HTTPException(status_code=502, detail=data.get("error", "Apify scrape failed"))

    # Ship back the product summary so the TUS UI can refresh immediately.
    return {
        "success": True,
        "product_id": data.get("product_id"),
        "actors_used": data.get("actors_used"),
        "candidates": data.get("candidates"),
        "message": "สินค้าเข้าระบบแล้ว",
    }


@router.post("/apify/scrape/batch")
async def apify_scrape_batch(req: dict):
    """TUS entry: batch import many share-links / keywords at once.
    Body: { items: ["link or keyword", ...], region?, limit? }
    Processes each item sequentially (Apify is billed per run, and we want to
    stay within the free-plan credit), collecting per-item results.
    """
    items = req.get("items") or []
    region = req.get("region", "") or ""
    try:
        limit = min(int(req.get("limit", 5)), 10)
    except Exception:
        limit = 5

    if not isinstance(items, list) or not items:
        raise HTTPException(status_code=400, detail="ต้องส่ง items (list ของ link หรือ keyword อย่างน้อย 1 รายการ)")

    # Normalize: trim + drop empty lines
    cleaned = []
    for it in items:
        if isinstance(it, str) and it.strip():
            cleaned.append(it.strip())
    if not cleaned:
        raise HTTPException(status_code=400, detail="items ว่าง หลังจากกรองบรรทัดที่ไม่มีข้อมูล")

    results = []
    ok = 0
    fail = 0
    async with httpx.AsyncClient(timeout=200.0) as client:
        for idx, item in enumerate(cleaned, start=1):
            is_link = bool(re.search(r"(vt\.tiktok\.com|shop\.tiktok\.com|tiktok\.com)", item, re.I))
            payload = {"region": region, "limit": limit}
            if is_link:
                payload["link"] = item
            else:
                payload["keyword"] = item
            entry = {"index": idx, "input": item, "is_link": is_link, "success": False}
            try:
                resp = await client.post(
                    f"{SCRAPER_API_URL}/api/v1/apify/scrape",
                    json=payload,
                    timeout=200.0,
                )
                data = resp.json()
                if resp.status_code == 200 and data.get("success"):
                    entry["success"] = True
                    entry["product_id"] = data.get("product_id")
                    entry["candidates"] = data.get("candidates")
                    entry["message"] = data.get("message", "สินค้าเข้าระบบแล้ว")
                    ok += 1
                else:
                    entry["error"] = data.get("detail") or data.get("error") or f"HTTP {resp.status_code}"
                    fail += 1
            except Exception as e:
                entry["error"] = f"การเชื่อมต่อล้มเหลว: {e}"
                fail += 1
            results.append(entry)

    return {
        "success": ok > 0,
        "total": len(cleaned),
        "ok": ok,
        "fail": fail,
        "items": results,
        "message": f"สำเร็จ {ok}/{len(cleaned)} รายการ" + (f" (ล้มเหลว {fail})" if fail else ""),
    }


@router.post("/product/scrape-pipeline")
async def scrape_pipeline(req: dict):
    """URL → Pipeline (scrape+analyze+sync) → return product data for Video Wizard."""
    url = req.get("url", "")
    if not url:
        raise HTTPException(status_code=400, detail="url is required")

    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1) Call pipeline/ingest on product-scraper (port 8106)
        try:
            resp = await client.post(
                f"{SCRAPER_API_URL}/api/v1/pipeline/ingest",
                json={"url": url},
                timeout=120.0
            )
            data = resp.json()
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Pipeline error: {e}")

    if not data.get("success"):
        raise HTTPException(status_code=502, detail=data.get("error", "Pipeline failed"))

    # 2) Read product from tus_products.db
    product_id = data.get("product_id", "")
    if not product_id:
        raise HTTPException(status_code=500, detail="No product_id returned")

    import sqlite3
    from pathlib import Path
    db_path = str(Path(__file__).resolve().parent.parent / "tus_products.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM tus_products WHERE product_id = ?", (product_id,)
    ).fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found in DB")

    # Convert to dict, parse JSON fields
    product = dict(row)
    for field in ["images", "keywords", "hashtags"]:
        if product.get(field):
            try:
                product[field] = json.loads(product[field])
            except Exception:
                pass

    return {"success": True, "product": product, "pipeline": data}
