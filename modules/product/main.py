"""Product Scraper Micro-Service
FastAPI server on port 8106 - Scrape product URLs with Playwright + AI Vision."""
import os, json, logging, sys, re
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

_module_dir = os.path.dirname(os.path.abspath(__file__))
_modules_dir = os.path.dirname(_module_dir)
if _modules_dir not in sys.path:
    sys.path.insert(0, _modules_dir)

from shared.database import Base, engine, async_session_factory, init_db
# from shared.models import Product
from product.models import ScrapeRequest, ScrapeResponse, ProductData
from product.scraper import scrape_url, _try_http_extract
from product.analyzer import analyze_with_vision

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ready")
    except Exception as e:
        logger.warning(f"DB init skipped: {e}")

    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post("http://localhost:8101/api/v1/register", json={
                "name": "product-scraper",
                "port": 8106,
                "description": "Product URL scraper with Playwright + Vision AI",
                "endpoints": [
                    {"path": "/api/v1/product/scrape", "method": "POST", "description": "Scrape product URL"},
                    {"path": "/health", "method": "GET", "description": "Health check"},
                ]
            })
            logger.info("Registered with erp_bridge")
    except Exception as e:
        logger.warning(f"Bridge registration skipped: {e}")

    yield


app = FastAPI(title="Product Scraper", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "product-scraper"}


@app.post("/api/v1/product/scrape", response_model=ScrapeResponse)
async def scrape_product(req: ScrapeRequest):
    if not req.url or not req.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Invalid URL")

    logger.info(f"Scraping: {req.url}")
    result = await scrape_url(req.url)

    if not result["success"] and req.use_vision:
        images = result.get("product", {}).get("images", [])
        if images:
            logger.info(f"Vision fallback on {images[0]}")
            vision_data = await analyze_with_vision(images[0])
            if vision_data:
                product = result.get("product", {})
                for k, v in vision_data.items():
                    if v and not product.get(k):
                        product[k] = v
                result["product"] = product
                if product.get("name"):
                    result["success"] = True
                    result["method"] = "vision"

    if not result["success"] and req.use_vision:
        logger.info("HTML fallback for images")
        try:
            import httpx
            async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
                resp = await client.get(req.url)
                html = resp.text
                img_urls = re.findall(r'https?://[^\s"]+\.(?:jpg|jpeg|png|webp)[^\s"]*', html)
                seen = set()
                valid_imgs = []
                for u in img_urls:
                    clean = u.split("?")[0]
                    if clean not in seen and len(u) < 500 and "logo" not in u.lower():
                        seen.add(clean)
                        valid_imgs.append(u)
                if valid_imgs:
                    vision_data = await analyze_with_vision(valid_imgs[0])
                    if vision_data:
                        result["product"] = {
                            "name": vision_data.get("name"),
                            "price": vision_data.get("price"),
                            "currency": "THB",
                            "images": valid_imgs[:5],
                            "description": vision_data.get("description"),
                            "sku": vision_data.get("sku"),
                            "brand": vision_data.get("brand"),
                            "source_url": req.url,
                            "source_site": "unknown",
                        }
                        result["success"] = True
                        result["method"] = "vision"
        except Exception as e:
            logger.warning(f"HTML fallback failed: {e}")

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
        error="HTTP extraction returned no data. Server may be blocking requests."
    )


def main():
    port = int(os.environ.get("PRODUCT_PORT", 8106))
    uvicorn.run("product.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
