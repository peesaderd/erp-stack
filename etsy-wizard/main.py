from pydantic import validator

import sys

"""
Etsy Wizard — Micro Service
Mini MVP: Shop Setup Wizard + Rules Validator + AI Assistant
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from rules.validator import (
    validate_title, validate_tags, validate_description,
    validate_price, validate_listing, validate_image_requirements,
    validate_policies,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("etsy-wizard")

app = FastAPI(
    title="Etsy Wizard Microservice",
    version="0.1.0",
    description="AI Shop Setup Wizard + Rules Validator — Mini MVP",
)

# HACK: Load keys from tiktok-ugc-studio .env since etsy-wizard doesn't have its own
_env_file = os.path.join(os.path.dirname(__file__), '..', 'tiktok-ugc-studio', '.env')
_fal_from_env = None
if os.path.exists(_env_file):
    _env_content = open(_env_file).read()
    for _line in _env_content.split('\n'):
        _line = _line.strip()
        if _line.startswith('FAL_KEY='):
            _k, _v = _line.split('=', 1)
            if 'FAL_KEY' not in os.environ:
                os.environ['FAL_KEY'] = _v
                _fal_from_env = _v
        elif _line.startswith('MISTRAL_API_KEY='):
            _k, _v = _line.split('=', 1)
            if 'MISTRAL_API_KEY' not in os.environ:
                os.environ['MISTRAL_API_KEY'] = _v
        elif _line.startswith('GEMINI_API_KEY='):
            _k, _v = _line.split('=', 1)
            if 'GEMINI_API_KEY' not in os.environ:
                os.environ['GEMINI_API_KEY'] = _v
        elif _line.startswith('GEMINI_MODEL='):
            _k, _v = _line.split('=', 1)
            if 'GEMINI_MODEL' not in os.environ:
                os.environ['GEMINI_MODEL'] = _v

# Add tiktok-ugc-studio to sys.path so we can import gemini_agent
_ugc_path = os.path.join(os.path.dirname(__file__), '..', 'tiktok-ugc-studio')
if _ugc_path not in sys.path:
    sys.path.append(_ugc_path)  # append not insert(0) to avoid shadowing local main.py

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── In-memory Shop Data (MVP — will migrate to DB later) ─────────────────

shops: dict[str, dict] = {}
listings: dict[str, list] = {}

# --- SQLite persistence ---
DB_PATH = Path(__file__).parent / "etsy_wizard.db"

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("CREATE TABLE IF NOT EXISTS shops (shop_id TEXT PRIMARY KEY, data TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS listings (shop_id TEXT, draft_id TEXT, data TEXT, PRIMARY KEY(shop_id, draft_id))")
    conn.commit()
    conn.close()

def load_from_db():
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute("SELECT shop_id, data FROM shops")
        for row in cur.fetchall():
            shops[row[0]] = json.loads(row[1])
        cur = conn.execute("SELECT shop_id, draft_id, data FROM listings")
        for row in cur.fetchall():
            sid = row[0]
            if sid not in listings:
                listings[sid] = []
            d = json.loads(row[2])
            d["draft_id"] = row[1]
            listings[sid].append(d)
    finally:
        conn.close()

def save_shop(shop_id: str):
    if shop_id not in shops:
        return
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("INSERT OR REPLACE INTO shops (shop_id, data) VALUES (?, ?)",
                     (shop_id, json.dumps(shops[shop_id], default=str)))
        conn.commit()
    finally:
        conn.close()

def save_listing(shop_id: str, draft_id: str, data: dict):
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("INSERT OR REPLACE INTO listings (shop_id, draft_id, data) VALUES (?, ?, ?)",
                     (shop_id, draft_id, json.dumps(data, default=str)))
        conn.commit()
    finally:
        conn.close()

def delete_listing_db(shop_id: str, draft_id: str):
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.execute("DELETE FROM listings WHERE shop_id=? AND draft_id=?", (shop_id, draft_id))
        conn.commit()
    finally:
        conn.close()

# Initialize on startup
init_db()
load_from_db()

# MEDIUM: Configure static file serving for product images
# This should match the path used in the analyze endpoint
try:
    static_path = Path(__file__).parent / "static" / "product_images"
    static_path.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/static/product_images",
        StaticFiles(directory=str(static_path)),
        name="product_images"
    )
    logger.info(f"Static file serving configured for: {static_path}")
except Exception as e:
    logger.error(f"Failed to configure static file serving: {e}")
# --- end SQLite ---


# ─── Pydantic Models ───────────────────────────────────────────────────────

class Listing(BaseModel):
    title: str
    description: str
    tags: list[str] = []
    price: float
    quantity: int = 1
    materials: list[str] = []
    who_made_it: str = "i_did"
    when_made: str = "2020_2026"
    is_supply: str = "a_finished_product"

class ShopProfile(BaseModel):
    name: str
    banner_url: Optional[str] = None
    about: Optional[str] = None
    policies: dict = {}

class ImageCheck(BaseModel):
    width: int
    height: int
    file_size_mb: float = 0
    file_type: str = "JPEG"

class WizardStep(BaseModel):
    shop_id: str
    step: str
    data: dict


# ─── Health ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "etsy-wizard",
        "version": "0.1.0",
        "rules_loaded": True,
    }


# ─── Validator Endpoints ───────────────────────────────────────────────────

@app.post("/validate/listing")
def check_listing(listing: Listing):
    """ตรวจสอบ Listing ว่าผ่าน Etsy Rules หรือไม่"""
    result = validate_listing(listing.model_dump())
    return result


@app.post("/validate/image")
def check_image(image: ImageCheck):
    """ตรวจสอบ Image Metadata ก่อน Upload"""
    result = validate_image_requirements(image.model_dump())
    return result.to_dict()


@app.post("/validate/policies")
def check_policies(policies: dict):
    """ตรวจสอบ Shop Policies"""
    result = validate_policies(policies)
    return result.to_dict()


# ─── Wizard Endpoints ──────────────────────────────────────────────────────

@app.post("/wizard/start")
def start_wizard():
    """เริ่ม Wizard — สร้าง Shop ID ใหม่"""
    import uuid
    shop_id = str(uuid.uuid4())[:8]
    shops[shop_id] = {
        "id": shop_id,
        "created_at": datetime.now().isoformat(),
        "steps_completed": [],
        "profile": {},
        "listings": [],
    }
    save_shop(shop_id)
    logger.info(f"Wizard started: {shop_id}")
    return {"shop_id": shop_id, "next_step": "shop_name"}


@app.get("/wizard/flow")
def wizard_flow():
    """รายการขั้นตอน Wizard ทั้งหมด (Mini App ใช้ render UI)"""
    return {
        "wizard": "etsy-shop-setup",
        "version": "1.0",
        "steps": [
            {"id": "shop_name",       "title": "ชื่อร้าน",        "icon": "🏪"},
            {"id": "shop_banner",     "title": "Banner ร้าน",     "icon": "🖼️"},
            {"id": "shop_about",      "title": "เรื่องราวร้าน",   "icon": "📖"},
            {"id": "policies",        "title": "นโยบายร้าน",     "icon": "📋"},
            {"id": "first_listing",   "title": "Listing แรก",    "icon": "📝"},
            {"id": "upload_photos",   "title": "รูปสินค้า",       "icon": "📸"},
            {"id": "review",          "title": "ตรวจสอบก่อนเปิด", "icon": "✅"},
        ],
        "total_steps": 7,
    }


@app.post("/wizard/step")
def save_step(step: WizardStep):
    """บันทึกข้อมูลแต่ละขั้นตอนของ Wizard"""
    shop = shops.get(step.shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail=f"ไม่พบ Shop ID: {step.shop_id}")

    shop["steps_completed"].append(step.step)
    shop["profile"][step.step] = step.data
    shops[step.shop_id] = shop
    save_shop(step.shop_id)

    # หา next step
    flow = wizard_flow().get("steps", [])
    step_ids = [s["id"] for s in flow]
    current_idx = step_ids.index(step.step) if step.step in step_ids else -1
    next_step = step_ids[current_idx + 1] if current_idx + 1 < len(step_ids) else None

    logger.info(f"Shop {step.shop_id}: step '{step.step}' saved")
    return {
        "ok": True,
        "shop_id": step.shop_id,
        "step": step.step,
        "next_step": next_step,
        "progress": f"{len(shop['steps_completed'])}/{len(step_ids)}",
    }


@app.get("/wizard/status/{shop_id}")
def wizard_status(shop_id: str):
    """ดูสถานะ Wizard ของ Shop"""
    shop = shops.get(shop_id)
    if not shop:
        raise HTTPException(status_code=404, detail=f"ไม่พบ Shop ID: {shop_id}")

    flow = wizard_flow().get("steps", [])
    step_ids = [s["id"] for s in flow]
    completed = shop["steps_completed"]
    current_step_idx = len(completed)

    return {
        "shop_id": shop_id,
        "progress": f"{len(completed)}/{len(step_ids)}",
        "completed_steps": completed,
        "current_step": step_ids[current_step_idx] if current_step_idx < len(step_ids) else "complete",
        "is_complete": current_step_idx >= len(step_ids),
        "profile_summary": {
            k: v for k, v in shop["profile"].items()
            if k in ["shop_name", "shop_about"]
        },
    }


@app.post("/listing/draft")
def save_listing_draft(shop_id: str, listing: Listing):
    """Save draft listing (ยังไม่ push ไป Etsy)"""
    if shop_id not in listings:
        listings[shop_id] = []

    draft = listing.model_dump()
    draft["id"] = len(listings[shop_id]) + 1
    draft["status"] = "draft"
    draft["created_at"] = datetime.now().isoformat()

    # Validate ก่อน save
    validation = validate_listing(draft)
    draft["validation"] = validation

    listings[shop_id].append(draft)
    draft_id = str(draft["id"])
    save_listing(shop_id, draft_id, draft)
    return {
        "ok": True,
        "listing_id": draft["id"],
        "validation": validation,
    }


@app.get("/listing/drafts/{shop_id}")
def list_drafts(shop_id: str):
    """รายการ Draft Listing ทั้งหมด"""
    return {
        "shop_id": shop_id,
        "listings": listings.get(shop_id, []),
        "total": len(listings.get(shop_id, [])),
    }


# ─── AI Assistant Endpoints ──────────────────────────────────────────────

class ProductInfo(BaseModel):
    name: str
    description: str = ""
    category: str = ""
    material: str = ""
    size: str = ""
    color: str = ""
    style: str = "product"


class ImageGenRequest(BaseModel):
    product_name: str = ""
    description: str = ""
    style: str = "product"
    prompt: str = ""  # custom prompt — overrides auto-generated prompt
    model_tier: str = "quality"
    upscale: bool = True
    aspect_ratio: str = ""  # "9:16", "16:9", "1:1", "4:5", "3:2"
    product_image_url: Optional[str] = None  # URL of real product image for compositing
    product_id: str = ""  # optional product ID for logging
    position: Optional[str] = None  # JSON bbox from Gemini
    provider: str = "fal"
    @validator('product_image_url', pre=True)
    def validate_product_image_url(cls, v):
        if v is None:
            return None
        if not isinstance(v, str) or not v.strip():
            raise ValueError("product_image_url must be a non-empty string or None")
        if not v.startswith(('http://', 'https://')):
            raise ValueError("product_image_url must be a valid HTTP/HTTPS URL")
        return v.strip()

    @validator('aspect_ratio', pre=True)
    def validate_aspect_ratio(cls, v):
        if not v:
            return ""
        valid_ratios = ["9:16", "16:9", "1:1", "4:5", "3:2"]
        if v not in valid_ratios:
            raise ValueError(f"aspect_ratio must be one of {valid_ratios}")
        return v


class BatchGenRequest(BaseModel):
    shop_id: str
    product_names: list[str]
    style: str = "product"
    model_tier: str = "fast"


@app.get("/ai/providers")
def ai_providers():
    """List available AI image providers"""
    import os as _os
    from image_gen import PROVIDER_CONFIG, UPSCALE_MODELS, ImageProvider
    providers = {}
    for provider in ImageProvider:
        config = PROVIDER_CONFIG.get(provider)
        if not config:
            continue
        # Check both config key (compile-time) and env (runtime, loaded via env hack)
        key = config.get("key") or ""
        if key:
            providers[provider.value] = {
                "models": list(config["models"].keys()),
                "default_model": config["default_model"],
                "cost_per_image": config["models"][config["default_model"]]["cost_per_image"],
                "key_loaded": bool(key),
            }
    return {
        "providers": providers,
        "upscale_models": list(UPSCALE_MODELS.keys()),
        "default_provider": "fal",
    }


@app.post("/ai/generate-image")
def ai_generate_image(req: ImageGenRequest):
    """
    AI Generate product image:
    1. Create Etsy-optimized prompt
    2. Generate via Fal.ai
    3. Upscale to ≥2000px if needed
    4. Validate Etsy compliance
    """
    from image_gen import generate_product_image, make_etsy_compliant_prompt

    if req.prompt:
        prompt = req.prompt
    elif req.product_name:
        prompt = make_etsy_compliant_prompt(req.product_name, req.description, req.style)
    else:
        raise HTTPException(status_code=400, detail="Either prompt or product_name required")

    try:
        ar = req.aspect_ratio if req.aspect_ratio else None
        result = generate_product_image(
            prompt,
            model_tier=req.model_tier,
            upscale=req.upscale,
            aspect_ratio=ar,
            product_image_url=req.product_image_url,
            product_id=req.product_id or None,
            position=req.position,
            provider=req.provider,
        )
        return {
            "ok": True,
            "image_url": result["image_url"],
            "width": result["width"],
            "height": result["height"],
            "validation": result["validation"],
            "cost": result["cost"],
            "provider": result["provider"],
            "prompt_used": prompt,
        }
    except Exception as e:
        logger.error(f"Image generation failed: {str(e)}", exc_info=True)
        error_msg = str(e)
        if "400" in error_msg or "404" in error_msg or "invalid" in error_msg.lower():
            raise HTTPException(status_code=400, detail=f"Invalid request: {error_msg}")
        elif "401" in error_msg or "403" in error_msg or "key" in error_msg.lower():
            raise HTTPException(status_code=401, detail=f"Authentication failed: {error_msg}")
        elif "timeout" in error_msg.lower() or "504" in error_msg:
            raise HTTPException(status_code=504, detail=f"Service timeout: {error_msg}")
        else:
            raise HTTPException(status_code=502, detail=f"Image generation failed: {error_msg}")


@app.post("/ai/generate-product")
def ai_generate_product(product: ProductInfo):
    """
    AI Generate ทั้ง Concept + Image ในครั้งเดียว:
    1. AI สร้าง title, tags, description, price, image_prompt
    2. Generate image ตาม prompt ที่ AI สร้าง
    3. Validate ทุกอย่าง
    4. Save draft listing
    """
    from assistant import generate_product_concept
    from image_gen import generate_product_image

    # Step 1: AI สร้าง concept
    concept = generate_product_concept(product.model_dump())

    # Step 2: Save draft
    draft = {
        "title": concept.get("title", product.name),
        "description": concept.get("description", ""),
        "tags": concept.get("tags", []),
        "price": concept.get("price", 19.99),
        "materials": concept.get("materials", []),
        "quantity": 1,
        "status": "ai_generated",
        "created_at": datetime.now().isoformat(),
        "image_prompt": concept.get("image_prompt", ""),
        "image_style": concept.get("image_style", "product"),
    }

    # Step 3: Try image generation
    image_result = None
    try:
        prompt = concept.get("image_prompt", "")
        if not prompt:
            from image_gen import make_etsy_compliant_prompt
            prompt = make_etsy_compliant_prompt(concept.get("product_name", product.name), product.description, concept.get("image_style", "product"))
        
        img = generate_product_image(prompt, model_tier="quality", upscale=True)
        image_result = {
            "image_url": img["image_url"],
            "width": img["width"],
            "height": img["height"],
            "validation": img["validation"],
            "cost": img["cost"],
        }
        draft["image_url"] = img["image_url"]
    except Exception as e:
        logger.warning(f"Image gen failed (non-blocking): {e}")
        image_result = {"error": str(e)}

    return {
        "ok": True,
        "product_name": concept.get("product_name", product.name),
        "title": draft["title"],
        "tags": draft["tags"],
        "description": draft["description"][:300],
        "price": draft["price"],
        "materials": draft["materials"],
        "image": image_result,
        "draft": draft,
    }


@app.post("/ai/batch-generate")
def ai_batch_generate(req: BatchGenRequest):
    """
    AI Batch Generate หลายสินค้าพร้อมกัน
    ใช้ model_tier="fast" เพื่อประหยัด cost
    """
    from assistant import generate_product_concept
    from image_gen import generate_product_image, make_etsy_compliant_prompt

    results = []
    total_cost = 0

    if req.shop_id not in listings:
        listings[req.shop_id] = []

    for i, pname in enumerate(req.product_names):
        product_info = {"name": pname, "description": "", "style": req.style}
        try:
            concept = generate_product_concept(product_info)
            prompt = concept.get("image_prompt", "") or make_etsy_compliant_prompt(pname, "", req.style)

            img = None
            try:
                img = generate_product_image(prompt, model_tier=req.model_tier, upscale=True)
                total_cost += img["cost"]
            except Exception as e:
                logger.warning(f"Image fail for {pname}: {e}")

            draft = {
                "id": len(listings[req.shop_id]) + 1,
                "title": concept.get("title", pname),
                "status": "ai_generated",
                "image_url": img["image_url"] if img else None,
                "created_at": datetime.now().isoformat(),
            }
            listings[req.shop_id].append(draft)
            save_listing(req.shop_id, str(draft["id"]), draft)

            results.append({
                "index": i,
                "product_name": concept.get("product_name", pname),
                "title": draft["title"],
                "image_url": draft["image_url"],
                "price": concept.get("price", 19.99),
                "listing_id": draft["id"],
            })
        except Exception as e:
            results.append({"index": i, "product_name": pname, "error": str(e)})

    return {
        "ok": True,
        "shop_id": req.shop_id,
        "total": len(req.product_names),
        "succeeded": sum(1 for r in results if "error" not in r),
        "failed": sum(1 for r in results if "error" in r),
        "total_cost": total_cost,
        "results": results,
    }


@app.post("/ai/generate-listing")
def ai_generate_listing(product: ProductInfo):
    """AI สร้าง Listing (title + tags + description) จากข้อมูลสินค้า"""
    from assistant import generate_listing
    result = generate_listing(product.model_dump())
    return result


@app.post("/ai/fix-listing")
def ai_fix_listing(listing: Listing, shop_id: str = "default"):
    """ตรวจสอบ + AI แก้ไข Listing อัตโนมัติ"""
    from assistant import fix_listing
    validation = validate_listing(listing.model_dump())
    fix_result = fix_listing(listing.model_dump(), validation)
    return {
        "original": listing.model_dump(),
        "validation": validation,
        "fix": fix_result,
        "summary": {
            "needs_fix": not validation["valid"],
            "issues_found": len(validation["results"]),
        }
    }


@app.post("/ai/optimize-tags")
def ai_optimize_tags(product: ProductInfo):
    """AI สร้าง 13 SEO Tags ที่ดีที่สุด"""
    from assistant import optimize_tags
    result = optimize_tags(product.model_dump())
    # Validate tags หลัง gen
    from rules.validator import validate_tags
    validation = validate_tags(result.get("tags", [])).to_dict()
    return {
        "tags": result.get("tags", []),
        "search_volume_hints": result.get("search_volume_hints", []),
        "validation": validation,
    }


@app.post("/ai/validate-and-fix")
def ai_validate_and_fix(listing: Listing):
    """Validate + AI Fix ใน endpoint เดียว — ใช้จาก Mini App ได้เลย"""
    from assistant import fix_listing
    listing_data = listing.model_dump()
    # Validate
    validation = validate_listing(listing_data)
    # Fix ถ้ามีปัญหา
    fix_result = fix_listing(listing_data, validation) if not validation["valid"] else None
    return {
        "valid": validation["valid"],
        "validation": validation,
        "fix": fix_result,
        "summary": validation.get("summary", {}),
    }


@app.post("/ai/assist-wizard-step")
def ai_assist_wizard_step(shop_id: str, step: str, context: dict = {}):
    """AI แนะนำเนื้อหาสำหรับแต่ละ Wizard step"""
    from assistant import generate_shop_banner_description
    step_prompts = {
        "shop_about": "ช่วยเขียน 'About Shop' สำหรับร้าน Etsy",
        "shop_banner": "แนะนำการออกแบบ Banner",
        "policies": "ช่วยเขียนนโยบายร้าน Etsy",
    }
    prompt = step_prompts.get(step, f"ช่วยเขียนเนื้อหาสำหรับขั้นตอน {step}")
    suggestion = generate_shop_banner_description({"step": step, **context})
    return {
        "step": step,
        "shop_id": shop_id,
        "suggestion": suggestion,
    }


# ─── Stats ─────────────────────────────────────────────────────────────────

@app.get("/stats")
def stats():
    return {
        "active_shops": len(shops),
        "total_listings": sum(len(v) for v in listings.values()),
        "version": "0.1.0",
    }
class ProductResearchRequest(BaseModel):
    product_name: str = ''
    product_image_base64: str = ''
    description: str = ''
    category: str = ''

@app.post('/product/research')
def api_product_research(req: ProductResearchRequest):
    from gemini_agent import research_product
    # Step 1: AI Vision Analysis
    research = research_product(
        product_name=req.product_name or 'product',
        description=req.description,
        category=req.category,
        image_base64=req.product_image_base64 or None,
    )
    # Step 2: Web Search — improve relevance with product type + Thai context
    web_data = {'specs': [], 'reviews': [], 'prices': []}
    if req.product_name:
        try:
            from duckduckgo_search import DDGS
            # Use category from research if available
            _cat = research.get('category', '') or req.category or ''
            _type = research.get('product_type', '') or ''
            with DDGS() as ddgs:
                # Specs: English + Thai search for better coverage
                _spec_q = f"{req.product_name} {' '.join(_type.split()[:3])} specifications technical details"[:200]
                specs = list(ddgs.text(_spec_q, max_results=3))
                web_data['specs'] = [r.get('body','')[:500] for r in specs if r.get('body','')]
                # Reviews: site-limited + Thai mixing
                _rev_q = f"{req.product_name} {' '.join(_cat.split()[:2]) if _cat else ''} review รีวิว"[:200]
                reviews = list(ddgs.text(_rev_q, max_results=3))
                web_data['reviews'] = [r.get('body','')[:500] for r in reviews if r.get('body','')]
                # Prices: Shopee/Lazada preferred for Thai market
                _price_q = f"{req.product_name} price ราคา shopee lazada"[:200]
                prices = list(ddgs.text(_price_q, max_results=3))
                web_data['prices'] = [r.get('title','')[:200] for r in prices if r.get('title','')]
        except Exception as e:
            logger.warning(f'Web search failed: {e}')
    return {'ok': True, 'product_name': req.product_name, 'research': research, 'web_data': web_data}

# ─── Payment Module (PromptPay QR) ────────────────────────────────────

class PaymentQRRequest(BaseModel):
    amount: float = 0
    phone: str = ''  # PromptPay phone number (default from env or empty)
    name: str = 'I2M Studio'
    reference: str = ''

@app.post('/payment/create-qr')
def create_payment_qr(req: PaymentQRRequest):
    """
    Generate Thai PromptPay QR Code for payment.
    Uses the standard EMVCo PromptPay payload.
    """
    import qrcode
    from io import BytesIO
    import base64

    phone = req.phone or os.environ.get('PROMPTPAY_PHONE', '')
    if not phone:
        # Generate a static QR code with just the reference if no phone
        phone = '0000000000'  # Placeholder — user must configure

    # EMVCo PromptPay payload format
    # https://www.emvco.com/emvco-qr-code-specification/
    # Thai PromptPay: Application ID A000000677010111 (Merchant)

    # Strip non-digits from phone
    phone_clean = ''.join(c for c in phone if c.isdigit())

    # Build EMVCo QR payload
    # 00 Payload Format Indicator (01 fixed)
    emv = '000201'

    # 01 Point of Initiation Method (12 = static QR)
    emv += '010212'

    # 26 Merchant Account Information (Thai PromptPay)
    # 00: AID = A000000677010111
    # 01: PromptPay identifier (phone number or tax ID)
    # If phone: 01 followed by length (2 digits) and "00" + country code "66" + phone without leading 0
    pp_id = phone_clean
    if pp_id.startswith('0'):
        pp_id = '66' + pp_id[1:]  # 0X... → 66X...
    elif not pp_id.startswith('66'):
        pp_id = '66' + pp_id

    aid_tag = '0016A000000677010111'
    phone_tag = f'01{len(pp_id):02d}{pp_id}'
    merchant_account = aid_tag + phone_tag
    emv += f'26{len(merchant_account):02d}{merchant_account}'

    # 59 Merchant Name
    name = req.name[:25]
    emv += f'59{len(name):02d}{name}'

    # 60 Merchant City (Bangkok)
    city = 'Bangkok'
    emv += f'60{len(city):02d}{city}'

    # 61 Postal Code
    postal = '10100'
    emv += f'61{len(postal):02d}{postal}'

    if req.amount > 0:
        amount_str = f'{req.amount:.2f}'
        emv += f'54{len(amount_str):02d}{amount_str}'

    # 62 Additional Data (reference)
    if req.reference:
        ref_tag = f'08{len(req.reference):02d}{req.reference}'
        emv += f'62{len(ref_tag):02d}{ref_tag}'

    # 63 CRC (calculated)
    # CRC-CCITT (0xFFFF) on the data
    crc_data = emv.encode()
    crc = 0xFFFF
    for byte in crc_data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0x8408
            else:
                crc >>= 1
    emv += f'63{crc:04X}'

    # Generate QR code image
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(emv)
    qr.make(fit=True)
    img = qr.make_image(fill_color='black', back_color='white')

    buf = BytesIO()
    img.save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode()

    return {
        'ok': True,
        'qr_base64': b64,
        'qr_payload': emv,
        'amount': req.amount,
        'phone': phone_clean,
        'name': name,
        'reference': req.reference or '',
    }


# ─── Product Scraping Module ──────────────────────────────────────────

class ScrapeRequest(BaseModel):
    url: str
    max_pages: int = 1

@app.post('/product/scrape')
def scrape_product(req: ScrapeRequest):
    """
    Scrape product info from e-commerce URLs.
    Supports general e-commerce sites via BeautifulSoup + heuristics.
    For JS-heavy sites (Shopee, Lazada), falls back to web search.
    """
    import requests
    from bs4 import BeautifulSoup
    import re

    url = req.url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    result = {
        'ok': True,
        'url': url,
        'title': '',
        'price': '',
        'description': '',
        'images': [],
        'specs': {},
        'source': 'unknown',
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'th-TH,th;q=0.9,en;q=0.8',
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        # Fallback: use product/research with image
        result['error'] = f'Cannot fetch URL: {e}'
        result['ok'] = False
        return result

    soup = BeautifulSoup(resp.text, 'lxml' if 'lxml' else 'html.parser')

    # Detect site
    domain = url.lower().split('/')[2] if '//' in url else ''
    if 'shopee' in domain:
        result['source'] = 'shopee'
    elif 'lazada' in domain:
        result['source'] = 'lazada'
    elif 'amazon' in domain:
        result['source'] = 'amazon'
    elif 'etsy' in domain:
        result['source'] = 'etsy'
    else:
        result['source'] = 'generic'

    # Extract title from various meta/og tags
    title = ''
    for sel in ['meta[property="og:title"]', 'meta[name="twitter:title"]', 'h1', 'h1[class*="title"]', 'h1[class*="product"]', '[class*="product-name"]', '[class*="product-title"]', 'title']:
        tag = soup.select_one(sel)
        if tag:
            if tag.name == 'meta':
                title = tag.get('content', '')
            else:
                title = tag.get_text(strip=True)
            if title:
                break

    result['title'] = title

    # Extract description
    for sel in ['meta[property="og:description"]', 'meta[name="description"]', '[class*="description"]', '[class*="detail"]', '#productDescription', '[itemprop="description"]']:
        tag = soup.select_one(sel)
        if tag:
            if tag.name == 'meta':
                result['description'] = tag.get('content', '').strip()
            else:
                result['description'] = tag.get_text(strip=True)[:500]
            if result['description']:
                break

    # Extract price
    for sel in ['[class*="price"]', '[class*="Price"]', '[itemprop="price"]', 'meta[property="product:price:amount"]', 'meta[itemprop="price"]', '[class*="current-price"]', '[data-testid="price"]']:
        tag = soup.select_one(sel)
        if tag:
            if tag.name == 'meta':
                result['price'] = tag.get('content', '')
            else:
                price_text = tag.get_text(strip=True)
                price_match = re.search(r'[\d,]+(?:\.\d+)?', price_text.replace(',', ''))
                if price_match:
                    result['price'] = price_match.group()
            if result['price']:
                break

    # Extract images
    for sel in ['meta[property="og:image"]', 'meta[name="twitter:image"]', '[class*="gallery"] img', '[class*="product-image"] img', '[id*="main-img"]', '[class*="main-image"] img', '.image-gallery img', 'img[itemprop="image"]']:
        tags = soup.select(sel)
        for tag in tags:
            src = tag.get('src') or tag.get('data-src') or tag.get('content', '')
            if src and src.startswith(('http://', 'https://')):
                if src not in result['images']:
                    result['images'].append(src)
            if len(result['images']) >= 5:
                break
        if len(result['images']) >= 5:
            break

    # Extract specs/features table  
    for table in soup.select('table[class*="spec"], table[class*="attribute"], .product-specs table, .data-table'):
        rows = table.select('tr')
        for row in rows:
            cells = row.select('th, td')
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                val = cells[1].get_text(strip=True)
                if key and val:
                    result['specs'][key] = val

    if not result['images']:
        # Fallback: extract any large image
        for img in soup.select('img[src]'):
            src = img.get('src', '')
            if src.startswith(('http://', 'https://')) and any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                if 'logo' not in src.lower() and 'icon' not in src.lower():
                    result['images'].append(src)
                    if len(result['images']) >= 3:
                        break

    return result


# ─── POD (Print on Demand) Module ─────────────────────────────────────────────────

class ArtworkValidationRequest(BaseModel):
    """ข้อมูลรูป artwork ที่ต้องการตรวจสอบ"""
    product_id: str
    width_px: int = 0
    height_px: int = 0
    dpi: int = 0
    file_size_mb: float = 0
    file_type: str = ""
    image_base64: Optional[str] = None  # ถ้ามี → ส่งให้ AI วิเคราะห์ design ด้วย


class AIArtworkReviewRequest(BaseModel):
    """ให้ AI วิเคราะห์ artwork design"""
    product_id: str
    width_px: int = 0
    height_px: int = 0
    design_description: str = ""  # ถ้าไม่มีรูป บอก description
    image_base64: Optional[str] = None  # รูป artwork
    style: str = ""  # minimal, colorful, vintage, etc.


@app.get("/pod/products")
def pod_list_products(category: Optional[str] = None):
    """
    รายการสินค้า POD ทั้งหมด หรือกรองตาม category
    categories: apparel, drinkware, home, accessories, stationery
    """
    from pod_sizes import list_products, get_categories
    return {
        "ok": True,
        "products": list_products(category),
        "total": len(list_products(category)),
        "categories": get_categories(),
    }


@app.get("/pod/products/{category}")
def pod_products_by_category(category: str):
    """รายการสินค้า POD ตามหมวดหมู่"""
    from pod_sizes import list_products
    products = list_products(category)
    if not products:
        raise HTTPException(status_code=404, detail=f"ไม่พบหมวดหมู่: {category}")
    return {"ok": True, "category": category, "products": products, "total": len(products)}


@app.get("/pod/product/{product_id}")
def pod_get_product(product_id: str):
    """รายละเอียดสินค้า POD พร้อมขนาด artwork ที่ต้องการ"""
    from pod_sizes import get_product
    product = get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"ไม่พบ Product ID: {product_id}")
    return {"ok": True, "product": product}


@app.post("/pod/validate-artwork")
def pod_validate_artwork(req: ArtworkValidationRequest):
    """
    ตรวจสอบ artwork ว่าพอดีกับ POD product หรือไม่
    
    ส่งขนาดรูป + DPI + file type → ได้ผล validation + คะแนน + คำแนะนำ
    """
    from pod_sizes import validate_artwork
    
    image_info = {
        "width_px": req.width_px,
        "height_px": req.height_px,
        "dpi": req.dpi,
        "file_size_mb": req.file_size_mb,
        "file_type": req.file_type,
    }
    
    result = validate_artwork(image_info, req.product_id)
    return {
        "ok": result["valid"],
        "product_name": result["product_name"],
        "product_id": result["product_id"],
        "image_size_px": result["image_size_px"],
        "required_size_px": result["required_size_px"],
        "required_size_inch": result["required_size_inch"],
        "dpi": result.get("dpi", 0),
        "valid": result["valid"],
        "score": result["score"],
        "score_label": result["score_label"],
        "errors": result["errors"],
        "warnings": result["warnings"],
        "recommendations": result["recommendations"],
    }


@app.post("/pod/ai-review")
def pod_ai_review(req: AIArtworkReviewRequest):
    """
    ให้ AI (Gemini) วิเคราะห์ artwork design + แนะนำการปรับปรุง
    
    - ถ้ามี image_base64 → ส่งให้ AI ดู design จริง
    - ถ้าไม่มี → ใช้ design_description
    - AI จะแนะนำเรื่องสี, layout, text placement, print readiness
    """
    from pod_sizes import get_product
    
    product = get_product(req.product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"ไม่พบ Product ID: {req.product_id}")

    # สร้าง prompt ส่งให้ Gemini
    has_image = bool(req.image_base64)
    
    system_prompt = f"""คุณคือ POD (Print on Demand) Design Expert

สินค้า: {product['name']}
พื้นที่พิมพ์: {product['print_area']}
ขนาดที่ต้องการ: {product['width_px_300']}x{product['height_px_300']}px @ {product['dpi_recommended']}dpi
({product['width_inch']}"x{product['height_inch']}")
เทคนิคการพิมพ์: {product['print_technique']}

คำแนะนำที่ต้องให้:
1. ตรวจสอบ layout และองค์ประกอบ design
2. แนะนำการปรับตำแหน่ง text/graphic ให้เหมาะสมกับพื้นที่พิมพ์
3. บอกว่า design นี้เหมาะกับสินค้าชนิดนี้หรือไม่
4. แนะนำเรื่อง bleed, safe zone, color
5. ถ้าไม่เหมาะสม → แนะนำทางเลือก

ตอบเป็นภาษาไทย อ่านง่าย มีหัวข้อชัดเจน"""

    if has_image:
        # With image - send for Gemini vision analysis
        # For now, describe what we can check from metadata
        user_prompt = f"""วิเคราะห์ artwork design นี้:
- ขนาด: {req.width_px}x{req.height_px}px
- สไตล์: {req.style or 'N/A'}
- Product: {product['name']}
{req.design_description}

ให้คำแนะนำเต็มๆ เกี่ยวกับการปรับ design ให้เหมาะกับ {product['name']}"""
    else:
        user_prompt = f"""ออกแบบ artwork สำหรับ {product['name']}

รายละเอียด: {req.design_description or 'ไม่มี'}
สไตล์: {req.style or 'modern'}

แนะนำ:
1. ขนาด artwork ที่เหมาะสม
2. องค์ประกอบ design ที่ควรมี
3. สีที่ใช้ (CMYK vs RGB)
4. Tips เฉพาะสินค้าชนิดนี้
5. ตัวอย่าง layout ที่แนะนำ"""

    from assistant import _call_gemini
    raw = _call_gemini(system_prompt, user_prompt)
    
    if raw:
        return {
            "ok": True,
            "product_name": product["name"],
            "product_id": req.product_id,
            "ai_analysis": raw,
            "source": "gemini",
        }
    
    # Fallback — ให้คำแนะนำตาม template
    return {
        "ok": True,
        "product_name": product["name"],
        "product_id": req.product_id,
        "ai_analysis": f"💡 คำแนะนำสำหรับ {product['name']}:\n\n"
            f"• ขนาดไฟล์: {product['width_px_300']}x{product['height_px_300']}px @ 300dpi\n"
            f"• พื้นที่พิมพ์: {product['width_inch']}x{product['height_inch']} นิ้ว\n"
            f"• ใช้ PNG (พื้นหลังโปร่งใส) เพื่อคุณภาพดีที่สุด\n"
            f"• เลือก Bleed: {product.get('notes', 'ระวังขอบตัด')}\n"
            f"• หลีกเลี่ยง text ชิดขอบเกิน 1 นิ้ว (เผื่อตัด)\n"
            f"• สี: แปลงเป็น CMYK ก่อนส่งพิมพ์ (ถ้าทำได้)\n",
        "source": "template",
    }


# ─── POD Create Product Wizard ──────────────────────────────────────────────

class WizardStartRequest(BaseModel):
    """เริ่ม Wizard session ใหม่"""
    pass


class WizardStepRequest(BaseModel):
    """ร้องขอข้อมูลในแต่ละ step"""
    session_id: str
    action: str  # "next" | "back" | "set"
    data: dict = {}


from pod_wizard import get_manager, WizardSession, handle_step_provider, handle_step_category
from pod_wizard import handle_step_product, handle_step_variant, handle_step_artwork
from pod_wizard import handle_step_mockup, handle_step_content, handle_step_pricing, handle_step_summary
from pod_data import get_providers

STEP_HANDLERS = {
    "provider": handle_step_provider,
    "category": handle_step_category,
    "product": handle_step_product,
    "variant": handle_step_variant,
    "artwork": handle_step_artwork,
    "mockup": handle_step_mockup,
    "content": handle_step_content,
    "pricing": handle_step_pricing,
    "summary": handle_step_summary,
}


@app.get("/pod/wizard/steps")
def pod_wizard_steps():
    """
    แสดงขั้นตอนทั้งหมดของ POD Create Product Wizard
    """
    from pod_wizard import WIZARD_STEPS
    return {
        "ok": True,
        "steps": WIZARD_STEPS,
        "total": len(WIZARD_STEPS),
    }


@app.post("/pod/wizard/start")
def pod_wizard_start():
    """
    เริ่ม Wizard session ใหม่ — สร้าง session + return step แรก
    """
    mgr = get_manager()
    session = mgr.create_session()

    return {
        "ok": True,
        "session": session.to_dict(),
        "current_step": session.get_current_step(),
        "providers": get_providers(),
    }


@app.get("/pod/wizard/{session_id}")
def pod_wizard_status(session_id: str):
    """
    ดูสถานะปัจจุบันของ wizard session
    """
    mgr = get_manager()
    session = mgr.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return {
        "ok": True,
        "session": session.to_dict(),
        "current_step": session.get_current_step(),
    }


@app.post("/pod/wizard/step")
def pod_wizard_step(req: WizardStepRequest):
    """
    ดำเนินการใน Wizard step

    action: "next" → ข้าม step | "back" → ย้อนกลับ | "set" → ตั้งค่าใน step ปัจจุบัน
    data: dict ของข้อมูลที่แต่ละ step ต้องการ
    """
    mgr = get_manager()
    session = mgr.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {req.session_id}")

    if req.action == "back":
        result = session.go_back()
        return {"ok": True, **result}

    # Handle current step
    current_step = session.get_current_step()
    step_id = current_step["id"]

    if step_id == "completed":
        return {"ok": True, "message": "Wizard เสร็จสิ้นแล้ว", "session": session.to_dict()}

    handler = STEP_HANDLERS.get(step_id)
    if handler:
        result = handler(session, **req.data)
        if not result.get("ok"):
            return {"ok": False, "error": result.get("error"), "step": step_id, "available": result.get("available")}

    # Advance step
    if req.action == "next":
        advance = session.advance_step()
        return {
            "ok": True,
            "step_result": result,
            "advance": advance,
            "session": session.to_dict(),
        }

    return {
        "ok": True,
        "step_result": result,
        "session": session.to_dict(),
    }


@app.post("/pod/wizard/{session_id}/cancel")
def pod_wizard_cancel(session_id: str):
    """ยกเลิก session"""
    mgr = get_manager()
    session = mgr.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    session.status = "cancelled"
    return {"ok": True, "message": "Session cancelled", "session_id": session_id}
