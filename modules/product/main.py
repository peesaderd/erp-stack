"""Product Scraper Micro-Service
FastAPI server on port 8106 - Scrape product URLs with Playwright + AI Vision.
Includes: API key auth, caching, usage tracking, per-user billing."""
import os, json, logging, sys, re, secrets
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

_module_dir = os.path.dirname(os.path.abspath(__file__))
_modules_dir = os.path.dirname(_module_dir)
if _modules_dir not in sys.path:
    sys.path.insert(0, _modules_dir)

from shared.database import Base, engine, async_session_factory, init_db
from product.models import ScrapeRequest, ScrapeResponse, ProductData
from product.scraper import scrape_url, _try_http_extract
from product.analyzer import analyze_with_vision
from product.db_models import SCRAPE_TIERS, get_tier_config
from product.export_service import (
    export_products_to_sheet, is_ready as sheets_ready, get_setup_instructions,
)
from product.scraper_service import (
    create_api_key, validate_api_key, list_api_keys, revoke_api_key,
    get_cached_product, cache_product,
    log_scrape, get_user_usage, scrape_with_tracking,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("product_service")

_env_file = os.path.join(_modules_dir, "tiktok-ugc-studio", ".env")
if os.path.exists(_env_file):
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k not in os.environ:
                    os.environ[k] = v


# ─── Request/Response Models ──────────────────────────────────────────

class ApiKeyCreateRequest(BaseModel):
    name: str = "API Key"

class ApiKeyCreateResponse(BaseModel):
    success: bool
    id: str = ""
    key: str = ""        # shown once
    prefix: str = ""
    name: str = ""
    error: Optional[str] = None

class ApiKeyListResponse(BaseModel):
    success: bool
    keys: list = []
    error: Optional[str] = None

class ApiKeyRevokeRequest(BaseModel):
    key_id: str

class ApiKeyRevokeResponse(BaseModel):
    success: bool
    error: Optional[str] = None

class ScrapeResponseV2(BaseModel):
    success: bool
    method: str
    product: Optional[ProductData] = None
    cost: float = 0.0
    cached: bool = False
    remaining_quota: Optional[int] = None
    error: Optional[str] = None

class ExportRequest(BaseModel):
    spreadsheet_id: str
    user_id: str = ""
    sheet_name: str = "Products"
    append: bool = False
    limit: int = 100

class ExportResponse(BaseModel):
    success: bool
    sheet_name: str = ""
    rows_written: int = 0
    updated_range: str = ""
    setup_instructions: Optional[list] = None
    error: Optional[str] = None

class UsageResponse(BaseModel):
    success: bool
    total_scrapes: int = 0
    total_cost: float = 0.0
    unique_urls: int = 0
    tier: str = "free"
    monthly_limit: int = 10
    remaining: int = 10
    cost_per_extra: float = 0.0
    recent_logs: list = []
    error: Optional[str] = None

class PricingResponse(BaseModel):
    success: bool
    tiers: dict = {}
    error: Optional[str] = None


# ─── Lifespan ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.begin() as conn:
            # Also create scraper-specific tables
            from product.db_models import ApiKey, ScrapedProduct, ScrapeLog, CreditUsage
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ready")
    except Exception as e:
        logger.warning(f"DB init skipped: {e}")

    # Register with ERP Modular
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post("http://localhost:8102/api/v1/modules/register", json={
                "name": "Product Scraper",
                "slug": "product-scraper",
                "version": "2.0.0",
                "endpoint": "http://localhost:8106",
                "description": "Product scraper with API keys, caching, usage tracking, per-user billing",
            })
            logger.info("Registered with ERP Modular")
    except Exception as e:
        logger.warning(f"ERP registration skipped: {e}")

    yield


app = FastAPI(title="Product Scraper V2", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ─── Helpers ──────────────────────────────────────────────────────────

async def _resolve_auth(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
) -> dict:
    """Resolve authentication from header. Returns {user_id, api_key_id, tier}."""
    raw_key = None
    if authorization and authorization.startswith("Bearer "):
        raw_key = authorization[7:]
    elif x_api_key:
        raw_key = x_api_key
    
    if raw_key:
        result = await validate_api_key(raw_key)
        if result:
            # Get user tier — for now default to free
            return {
                "user_id": result["user_id"],
                "api_key_id": result["id"],
                "tier": "free",  # TODO: query from auth module
                "authenticated": True,
            }
    
    return {
        "user_id": "anonymous",
        "api_key_id": None,
        "tier": "free",
        "authenticated": False,
    }


async def _get_tier_and_limit(tier: str) -> tuple:
    """Return (tier_name, monthly_limit)."""
    cfg = get_tier_config(tier)
    return tier, cfg["scrapes_per_month"]


# ─── Health ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "product-scraper", "version": "2.0.0"}


# ═══════════════════════════════════════════════════════════════════════
# API Key Management
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/keys/create", response_model=ApiKeyCreateResponse)
async def create_new_api_key(
    req: ApiKeyCreateRequest,
    x_user_id: Optional[str] = Header(None),
):
    """Create new API key for a user."""
    user_id = x_user_id or req.name
    if not user_id or user_id == "API Key":
        return ApiKeyCreateResponse(success=False, error="x-user-id header required")
    
    result = await create_api_key(user_id, name=req.name)
    return ApiKeyCreateResponse(
        success=True,
        id=result["id"],
        key=result["key"],
        prefix=result["prefix"],
        name=result["name"],
    )


@app.get("/api/v1/keys/list", response_model=ApiKeyListResponse)
async def list_user_api_keys(
    x_user_id: Optional[str] = Header(None),
):
    """List all API keys for a user."""
    if not x_user_id:
        return ApiKeyListResponse(success=False, error="x-user-id header required")
    keys = await list_api_keys(x_user_id)
    return ApiKeyListResponse(success=True, keys=keys)


@app.post("/api/v1/keys/revoke", response_model=ApiKeyRevokeResponse)
async def revoke_api_key_endpoint(
    req: ApiKeyRevokeRequest,
    x_user_id: Optional[str] = Header(None),
):
    """Revoke an API key."""
    if not x_user_id:
        return ApiKeyRevokeResponse(success=False, error="x-user-id header required")
    ok = await revoke_api_key(req.key_id, x_user_id)
    if not ok:
        return ApiKeyRevokeResponse(success=False, error="Key not found or not yours")
    return ApiKeyRevokeResponse(success=True)


# ═══════════════════════════════════════════════════════════════════════
# Pricing & Tiers
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/v1/pricing", response_model=PricingResponse)
async def get_pricing():
    """List available pricing tiers."""
    return PricingResponse(success=True, tiers=SCRAPE_TIERS)




# ═══════════════════════════════════════════════════════════════════════
# Google Sheets Export
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/v1/export/setup")
async def export_setup_instructions():
    """Get instructions for setting up Google Sheets integration."""
    from product.export_service import is_ready as _sr, get_setup_instructions as _gsi
    if _sr():
        return {"success": True, "configured": True, "message": "Google Sheets credentials configured."}
    return {"success": True, "configured": False, "setup": _gsi()}


@app.post("/api/v1/export/sheets")
async def export_to_sheets(
    spreadsheet_id: str,
    x_user_id: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    sheet_name: str = "Products",
    append: bool = False,
    limit: int = 100,
):
    """Export scraped products to a Google Sheet."""
    from product.export_service import export_products_to_sheet, is_ready as _sr, get_setup_instructions as _gsi

    if not _sr():
        return {"success": False, "error": "Google Sheets not configured.", "setup": _gsi()["steps"]}

    auth = await _resolve_auth(authorization, x_api_key)
    user_id = x_user_id or auth["user_id"]

    # Query products from DB
    async with async_session_factory() as session:
        from sqlalchemy import select, desc
        from product.db_models import ScrapeLog, ScrapedProduct

        log_query = (
            select(ScrapeLog.product_id)
            .where(ScrapeLog.user_id == user_id)
            .where(ScrapeLog.product_id.isnot(None))
            .order_by(desc(ScrapeLog.created_at))
            .limit(limit)
        )
        result = await session.execute(log_query)
        product_ids = [row[0] for row in result.fetchall() if row[0]]

        if not product_ids:
            return {"success": False, "error": "No scraped products found."}

        prod_query = select(ScrapedProduct).where(ScrapedProduct.id.in_(product_ids))
        result = await session.execute(prod_query)
        products_raw = result.scalars().all()

        seen = set()
        products = []
        for p in products_raw:
            if p.url_hash not in seen:
                seen.add(p.url_hash)
                products.append({
                    "name": p.name, "price": p.price, "currency": p.currency,
                    "images": p.images or [], "description": p.description,
                    "sku": p.sku, "brand": p.brand, "source_url": p.url, "source_site": p.source_site,
                })

    if not products:
        return {"success": False, "error": "No products to export."}

    result = await export_products_to_sheet(spreadsheet_id, products, sheet_name, append)
    if result["success"]:
        return {"success": True, "rows_written": result["rows_written"], "updated_range": result["updated_range"]}
    return {"success": False, "error": result["error"], "setup": _gsi()["steps"]}

# ═══════════════════════════════════════════════════════════════════════
# Scrape Endpoint (V2 with tracking)
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/scrape", response_model=ScrapeResponseV2)
async def scrape_product_v2(
    req: ScrapeRequest,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_forwarded_for: Optional[str] = Header(None),
):
    """Scrape a product URL with auth, caching, and billing."""
    if not req.url or not req.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")

    auth = await _resolve_auth(authorization, x_api_key)
    user_id = x_user_id or auth["user_id"]
    ip = x_forwarded_for or "127.0.0.1"

    logger.info(f"Scrape [{auth['tier']}] user={user_id[:12]}... url={req.url[:60]}...")

    # Check remaining quota
    usage = await get_user_usage(user_id)
    tier_cfg = get_tier_config(auth["tier"])
    remaining = max(0, tier_cfg["scrapes_per_month"] - usage.get("total_scrapes", 0))

    # Execute with tracking
    result = await scrape_with_tracking(
        url=req.url,
        user_id=user_id,
        api_key_id=auth.get("api_key_id"),
        use_vision=req.use_vision,
        proxy_url=req.proxy,
        rotate_proxy=req.rotate_proxy,
        user_tier=auth["tier"],
        ip_address=ip,
    )

    # Vision fallback (if scraper failed and vision is enabled)
    if not result["success"] and req.use_vision:
        product_data = result.get("product", {})
        if isinstance(product_data, dict) and product_data.get("images"):
            logger.info(f"Vision fallback on image")
            vision_data = await analyze_with_vision(product_data["images"][0])
            if vision_data:
                for k, v in vision_data.items():
                    if v and not product_data.get(k):
                        product_data[k] = v
                if product_data.get("name"):
                    result["success"] = True
                    result["method"] = "vision"

    # Build response
    product = result.get("product")
    product_obj = None
    if product and isinstance(product, dict):
        product_obj = ProductData(
            name=product.get("name"),
            price=product.get("price"),
            currency=product.get("currency", "THB"),
            images=product.get("images", []),
            description=product.get("description"),
            sku=product.get("sku"),
            brand=product.get("brand"),
            source_url=product.get("source_url", req.url),
            source_site=product.get("source_site", ""),
        )

    return ScrapeResponseV2(
        success=result["success"],
        method=result.get("method", "failed"),
        product=product_obj,
        cost=result.get("cost", 0.0),
        cached=result.get("cached", False),
        remaining_quota=remaining,
        error=result.get("error"),
    )


# ═══════════════════════════════════════════════════════════════════════
# Usage & Billing
# ═══════════════════════════════════════════════════════════════════════

@app.get("/api/v1/usage", response_model=UsageResponse)
async def get_usage(
    x_user_id: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
):
    """Get usage summary for authenticated user."""
    auth = await _resolve_auth(authorization, x_api_key)
    user_id = x_user_id or auth["user_id"]

    usage = await get_user_usage(user_id)
    tier_cfg = get_tier_config(auth["tier"])
    remaining = max(0, tier_cfg["scrapes_per_month"] - usage.get("total_scrapes", 0))

    return UsageResponse(
        success=True,
        total_scrapes=usage.get("total_scrapes", 0),
        total_cost=usage.get("total_cost", 0.0),
        unique_urls=usage.get("unique_urls", 0),
        tier=auth["tier"],
        monthly_limit=tier_cfg["scrapes_per_month"],
        remaining=remaining,
        cost_per_extra=tier_cfg["cost_per_scrape"],
        recent_logs=usage.get("recent_logs", []),
    )


# ═══════════════════════════════════════════════════════════════════════
# Legacy endpoints (backward compat)
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/v1/product/scrape", response_model=ScrapeResponse)
async def scrape_product_legacy(req: ScrapeRequest):
    """Legacy scrape endpoint (no auth/billing)."""
    if not req.url or not req.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")

    logger.info(f"Legacy scrape: {req.url}")
    result = await scrape_url(req.url, proxy_url=req.proxy, rotate_proxy=req.rotate_proxy)

    if not result["success"] and req.use_vision:
        images = result.get("product", {}).get("images", [])
        if images:
            vision_data = await analyze_with_vision(images[0])
            if vision_data:
                product = result.get("product", {})
                for k, v in vision_data.items():
                    if v and not product.get(k):
                        product[k] = v
                if product.get("name"):
                    result["success"] = True
                    result["method"] = "vision"

    return ScrapeResponse(
        success=result["success"],
        method=result.get("method", "failed"),
        product=result.get("product"),
        error=result.get("error"),
    )


@app.post("/api/v1/product/extract-html", response_model=ScrapeResponse)
async def extract_html(req: ScrapeRequest):
    if not req.url or not req.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")

    data = await _try_http_extract(req.url)
    if data:
        return ScrapeResponse(
            success=True,
            method="http",
            product={
                "name": data.get("name"),
                "price": data.get("price"),
                "images": data.get("images", []),
                "description": data.get("description"),
                "sku": data.get("sku"),
                "source_url": req.url,
            }
        )
    return ScrapeResponse(
        success=False,
        method="http_failed",
        product=None,
        error="HTTP extraction returned no data."
    )


def main():
    port = int(os.environ.get("PRODUCT_PORT", 8106))
    uvicorn.run("product.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
