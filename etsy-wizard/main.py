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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
    product_name: str
    description: str = ""
    style: str = "product"
    model_tier: str = "quality"
    upscale: bool = True


class BatchGenRequest(BaseModel):
    shop_id: str
    product_names: list[str]
    style: str = "product"
    model_tier: str = "fast"


@app.get("/ai/providers")
def ai_providers():
    """List available AI image providers"""
    from image_gen import PROVIDER_CONFIG, UPSCALE_MODELS, ImageProvider
    providers = {}
    for provider in ImageProvider:
        config = PROVIDER_CONFIG.get(provider)
        if config and config.get("key"):
            providers[provider.value] = {
                "models": list(config["models"].keys()),
                "default_model": config["default_model"],
                "cost_per_image": config["models"][config["default_model"]]["cost_per_image"],
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

    prompt = make_etsy_compliant_prompt(req.product_name, req.description, req.style)

    try:
        result = generate_product_image(prompt, model_tier=req.model_tier, upscale=req.upscale)
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
        raise HTTPException(status_code=502, detail=f"Image gen failed: {str(e)}")


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
