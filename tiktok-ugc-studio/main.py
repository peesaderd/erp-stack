"""
TikTok UGC Studio — Micro Service
AI UGC Video Script Generator + AI Video Generation
"""

import os
import json
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

# ─── Storage paths ────────────────────────────────────────────────────────
STORAGE_DIR = Path(__file__).parent / "storage"
TTS_DIR = STORAGE_DIR / "tts"
IMAGES_DIR = STORAGE_DIR / "images"
VIDEOS_DIR = STORAGE_DIR / "videos"
for d in [STORAGE_DIR, TTS_DIR, IMAGES_DIR, VIDEOS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# TikTok accounts storage
TIKTOK_ACCOUNTS_FILE = STORAGE_DIR / "tiktok_accounts.json"

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from io import BytesIO
from fastapi import File, Form, UploadFile
from typing import Literal
from postforme_integration import (
    get_accounts as pfm_get_accounts,
    post_to_platform as pfm_post,
    get_post_status as pfm_post_status,
)
from pydantic import BaseModel
import base64
import uuid
import sqlite3

import sys
sys.path.insert(0, os.path.dirname(__file__))

import os
# Load .env file for API keys (avoids OpenClaw redaction issues in PM2)
_env_file = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                if _k not in os.environ:
                    os.environ[_k] = _v


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tiktok-ugc")

app = FastAPI(
    title="TikTok UGC Studio",
    version="0.2.0",
    description="AI UGC video pipeline + Scout + Monitor. Script gen, TTS, Fal.ai Wan I2V, FFmpeg compose, TikTok Scout (trends), Monitor Loop (optimization)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving for generated assets (TTS, composed videos)
from fastapi.staticfiles import StaticFiles
STORAGE_DIR = os.path.join(os.path.dirname(__file__), "storage")
os.makedirs(os.path.join(STORAGE_DIR, "tts"), exist_ok=True)
os.makedirs(os.path.join(STORAGE_DIR, "composed"), exist_ok=True)
os.makedirs(os.path.join(STORAGE_DIR, "videos"), exist_ok=True)
try:
    app.mount("/static", StaticFiles(directory=STORAGE_DIR), name="static")
except Exception as e:
    logger.warning(f"Static mount (may already exist): {e}")

# ─── Pydantic Models ───────────────────────────────────────────────────────

class ScriptRequest(BaseModel):
    product_name: str
    customer_problem: str = ""
    main_benefit: str = ""
    target_audience: str = ""
    tone: str = ""
    cta: str = ""
    duration: str = "8s"
    extra_rules: str = ""


class UGCRequest(BaseModel):
    style: str = "ugc_review"  # holding_product, product_usage, ugc_review
    product_name: str
    product_desc: str = ""
    gender: str = "female"
    age: str = "25-35"
    scene: str = "home"
    negative_prompt: Optional[str] = None  # Custom negative prompt override


class VideoRequest(BaseModel):
    prompt: str
    provider: str = "kling"
    model_tier: str = "standard"
    duration: int = 8
    aspect_ratio: str = "9:16"
    image_url: Optional[str] = None
    script: Optional[str] = None
    ugc_style: Optional[str] = None
    negative_prompt: Optional[str] = None  # Added for P1: negative prompt support


class VideoTaskRequest(BaseModel):
    provider: str
    task_id: str


class QueueVideoRequest(BaseModel):
    prompt: str
    provider: str = "wavespeed"
    model_tier: str = "standard"
    duration: int = 8
    aspect_ratio: str = "9:16"
    image_url: Optional[str] = None
    face_image_url: Optional[str] = None
    webhook_url: Optional[str] = None


class TaskStatusRequest(BaseModel):
    task_id: str


class AffiliateConfig(BaseModel):
    # Platform affiliate link configs
    shopee_url: Optional[str] = None
    lazada_url: Optional[str] = None
    facebook_url: Optional[str] = None
    tiktok_url: Optional[str] = None


class AffiliateScriptRequest(ScriptRequest):
    """Script generation with affiliate links"""
    platforms: list[str] = []  # e.g. ["shopee", "lazada", "facebook", "tiktok"]


class ProductAnalysisRequest(BaseModel):
    product_name: str
    description: str
    category: Optional[str] = ""
    target_audience: Optional[str] = ""
    image_url: Optional[str] = None
    image_base64: Optional[str] = None  # base64-encoded image for vision

class ScrapeAndGenerateRequest(BaseModel):
    url: str
    duration: str = "8s"
    tone: str = ""
    cta: str = ""
    ugc_style: str = "ugc_review"
    use_vision: bool = False


class UserProfileRequest(BaseModel):
    user_id: str
    name: str
    email: str
    tier: str = "free"


# ─── Product Scraper Integration ─────────────────────────────────────────

SCRAPER_API_URL = "http://localhost:8106"

@app.post("/product/scrape-and-generate")
async def scrape_and_generate(req: ScrapeAndGenerateRequest):
    """Scrape product URL via Product Scraper :8106, then auto-generate script."""
    import httpx

    # 1. Scrape product
    logger.info(f"Scraping product: {req.url}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        # First get/create an API key
        key_resp = await client.post(
            f"{SCRAPER_API_URL}/api/v1/keys/create",
            json={"name": "tiktok-ugc-studio"},
            headers={"x-user-id": "tiktok-ugc"}
        )
        key_data = key_resp.json()
        api_key = key_data.get("key", "")

        # Scrape the URL
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
        raise HTTPException(
            status_code=502,
            detail=f"Product scraper failed: {scrape_data.get('error', 'unknown')}"
        )

    product = scrape_data.get("product", {}) or {}
    product_name = product.get("name", "") or ""
    description = product.get("description", "") or ""
    price = product.get("price")
    brand = product.get("brand", "") or ""
    images = product.get("images", []) or []
    source_site = product.get("source_site", "") or ""

    if not product_name:
        raise HTTPException(status_code=400, detail="Could not extract product name from URL")

    # 2. Generate script from scraped product data
    try:
        from script_gen import generate_tiktok_review_script

        # Build context from scraped data
        extra_context = f"""
Product: {product_name}
Brand: {brand}
Price: {price}
Source: {source_site}
Description: {description[:300]}
"""

        script_result = generate_tiktok_review_script(
            product_name=product_name,
            customer_problem=req.tone or f"Finding the right {product_name}",
            main_benefit=description[:200] if description else "",
            target_audience="",
            tone=req.tone,
            cta=req.cta,
            duration=req.duration,
            extra_rules=extra_context
        )

        # 3. Return combined result
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
                "scrape_method": scrape_data.get("method", ""),
                "cached": scrape_data.get("cached", False),
            },
            "script": script_result,
        }

    except Exception as e:
        logger.error(f"Script generation failed: {e}")
        # Return product data even if script fails
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


# ─── Health ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "tiktok-ugc-studio", "version": "0.2.0"}


# ─── TTS (Text-to-Speech) ─────────────────────────────────────────────────

class TTSRequest(BaseModel):
    text: str
    lang: str = "th"
    slow: bool = False


@app.post("/tts/generate")
def generate_tts(req: TTSRequest):
    """Generate TTS audio from text using gTTS."""
    from tts_gen import text_to_speech
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    try:
        filepath = text_to_speech(
            text=req.text.strip(),
            lang=req.lang or "th",
            slow=req.slow,
        )
        filename = os.path.basename(filepath)
        return {
            "success": True,
            "audio_url": f"/static/tts/{filename}",
            "filepath": filepath,
            "filename": filename,
            "duration_estimate": len(req.text.strip()) / 12,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


class ScriptTTSRequest(BaseModel):
    hook: str
    value_proposition: str = ""
    cta: str = ""
    lang: str = "th"


@app.post("/tts/script")
def generate_script_tts(req: ScriptTTSRequest):
    """Generate TTS for full UGC script (hook + value + CTA) as segments."""
    from tts_gen import script_to_speech
    try:
        result = script_to_speech(
            hook=req.hook,
            value_proposition=req.value_proposition,
            cta=req.cta,
            lang=req.lang or "th",
        )
        result["success"] = True
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ─── Pipeline Database ─────────────────────────────────────────────────────

PIPELINE_DB_PATH = os.path.join(os.path.dirname(__file__), "pipeline.db")

def _init_pipeline_db():
    """Initialize pipeline job tracking database."""
    os.makedirs(os.path.dirname(PIPELINE_DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_jobs (
            job_id TEXT PRIMARY KEY,
            account_id TEXT,
            product_url TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            updated_at TEXT,
            steps_data TEXT DEFAULT '{}'
        )
    """)
    conn.commit()
    conn.close()

_init_pipeline_db()

def _create_pipeline_job(account_id: str = "", product_url: str = "") -> str:
    """Create a new pipeline job and return job_id."""
    job_id = str(uuid.uuid4())[:8]
    now = datetime.utcnow().isoformat()
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    conn.execute(
        "INSERT INTO pipeline_jobs (job_id, account_id, product_url, status, created_at, updated_at, steps_data) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (job_id, account_id, product_url, "pending", now, now, "{}")
    )
    conn.commit()
    conn.close()
    return job_id

def _update_pipeline_step(job_id: str, step_name: str, status: str, result: dict = None):
    """Update a specific step in pipeline job."""
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    row = conn.execute("SELECT steps_data FROM pipeline_jobs WHERE job_id = ?", (job_id,)).fetchone()
    if not row:
        conn.close()
        return
    steps = json.loads(row[0])
    steps[step_name] = {"status": status, **(result or {})}
    now = datetime.utcnow().isoformat()
    all_done = all(s.get("status") in ("success", "error") for s in steps.values()) if steps else False
    overall = "completed" if all_done else "running"
    conn.execute(
        "UPDATE pipeline_jobs SET steps_data = ?, status = ?, updated_at = ? WHERE job_id = ?",
        (json.dumps(steps), overall, now, job_id)
    )
    conn.commit()
    conn.close()

def _get_pipeline_job(job_id: str) -> dict:
    """Get full pipeline job details."""
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    row = conn.execute("SELECT * FROM pipeline_jobs WHERE job_id = ?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "job_id": row[0],
        "account_id": row[1],
        "product_url": row[2],
        "status": row[3],
        "created_at": row[4],
        "updated_at": row[5],
        "steps": json.loads(row[6]),
    }

@app.get("/pipeline/{job_id}/status")
def pipeline_status(job_id: str):
    """Get pipeline job status."""
    job = _get_pipeline_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"success": True, "job": job}

@app.get("/pipeline/list")
def pipeline_list(limit: int = 20):
    """List pipeline jobs."""
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    rows = conn.execute(
        "SELECT job_id, account_id, status, product_url, created_at, updated_at FROM pipeline_jobs ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return {"success": True, "jobs": [{"job_id": r[0], "account_id": r[1], "status": r[2], "product_url": r[3], "created_at": r[4], "updated_at": r[5]} for r in rows]}

# ─── TikTok Scout (R&D) ──────────────────────────────────────────────────────

from scout.trends import discover_trends, analyze_viral_structure, search_trending_keywords
from scout.analyzer import analyze_video, compare_with_competitors, extract_trending_elements
from scout.templates import get_templates, generate_from_template, generate_clone_script


@app.get("/scout/trends")
async def scout_discover_trends(
    category: str = "",
    keyword: str = "",
    limit: int = 10,
):
    """Discover trending TikTok content patterns."""
    results = await discover_trends(category=category, keyword=keyword, limit=limit)
    return {"success": True, "trends": results, "count": len(results)}


@app.post("/scout/analyze")
async def scout_analyze(req: dict):
    """Analyze a video/viral structure for a product."""
    product_name = req.get("product_name", "")
    description = req.get("description", "")
    video_url = req.get("video_url", "")

    analysis = await analyze_video(
        video_url=video_url,
        description=description,
        product_name=product_name,
    )
    structure = await analyze_viral_structure(
        product_name=product_name,
        category=req.get("category", ""),
    )
    return {
        "success": True,
        "analysis": analysis,
        "recommended_structure": structure,
    }


@app.post("/scout/compare")
async def scout_compare(req: dict):
    """Compare content strategy against competitors."""
    result = await compare_with_competitors(
        product_name=req.get("product_name", ""),
        competitor_names=req.get("competitors", []),
    )
    return {"success": True, **result}


@app.get("/scout/templates")
async def scout_list_templates(category: str = ""):
    """List available content templates."""
    templates = await get_templates(category=category)
    return {"success": True, "templates": templates}


@app.post("/scout/templates/generate")
async def scout_generate_template(req: dict):
    """Generate a video script from a template."""
    result = await generate_from_template(
        template_id=req.get("template_id", ""),
        product_name=req.get("product_name", ""),
        price=req.get("price", ""),
        fill_values=req.get("fill_values"),
        cta=req.get("cta", "กด link in bio"),
    )
    if not result:
        return {"success": False, "error": "Template not found"}
    return {"success": True, "script": result}


@app.post("/scout/clone")
async def scout_clone(req: dict):
    """Clone a trending video structure for a new product."""
    result = await generate_clone_script(
        source_template_id=req.get("template_id", ""),
        product_name=req.get("product_name", ""),
        fill_values=req.get("fill_values"),
    )
    if not result:
        return {"success": False, "error": "Template not found"}
    return {"success": True, "clone": result}


@app.post("/scout/keywords")
async def scout_keywords(req: dict):
    """Search trending keywords for a product."""
    keywords = await search_trending_keywords(
        product_name=req.get("product_name", ""),
        niche=req.get("niche", ""),
    )
    return {"success": True, "keywords": keywords}


@app.post("/scout/extract")
async def scout_extract(req: dict):
    """Extract trending elements from a description."""
    result = await extract_trending_elements(
        description=req.get("description", ""),
    )
    return {"success": True, **result}




# ─── Scout Targets ──────────────────────────────────────────────────────────

from scout.targets import (
    list_targets, get_target, create_target, update_target, delete_target,
    add_clip, remove_clip, batch_analyze_targets,
)


@app.get("/scout/targets")
async def scout_list_targets():
    """List all scout target accounts."""
    targets = await list_targets()
    return {"success": True, "targets": targets, "count": len(targets)}


@app.get("/scout/targets/{target_id}")
async def scout_get_target(target_id: int):
    """Get a specific target account with clips."""
    target = await get_target(target_id)
    if not target:
        from fastapi import HTTPException as HE
        raise HE(status_code=404, detail=f"Target {target_id} not found")
    return {"success": True, "target": target}


@app.post("/scout/targets")
async def scout_create_target(req: dict):
    """Create a new scout target account."""
    target = await create_target(req)
    return {"success": True, "target": target}


@app.put("/scout/targets/{target_id}")
async def scout_update_target(target_id: int, req: dict):
    """Update a scout target account."""
    target = await update_target(target_id, req)
    if not target:
        from fastapi import HTTPException as HE
        raise HE(status_code=404, detail=f"Target {target_id} not found")
    return {"success": True, "target": target}


@app.delete("/scout/targets/{target_id}")
async def scout_delete_target(target_id: int):
    """Delete a scout target account and its clips."""
    await delete_target(target_id)
    return {"success": True}


@app.post("/scout/targets/{target_id}/clips")
async def scout_add_clip(target_id: int, req: dict):
    """Add a clip to a target."""
    result = await add_clip(target_id, req)
    if not result:
        from fastapi import HTTPException as HE
        raise HE(status_code=404, detail=f"Target {target_id} not found")
    return {"success": True, "clip": result}


@app.delete("/scout/clips/{clip_id}")
async def scout_remove_clip(clip_id: int):
    """Remove a clip from a target."""
    await remove_clip(clip_id)
    return {"success": True}


@app.post("/scout/targets/{target_id}/delete")
async def scout_delete_target_post(target_id: int):
    """POST wrapper for DELETE target (frontend compat)."""
    await delete_target(target_id)
    return {"success": True}


@app.post("/scout/clips/{clip_id}/delete")
async def scout_remove_clip_post(clip_id: int):
    """POST wrapper for DELETE clip (frontend compat)."""
    await remove_clip(clip_id)
    return {"success": True}


@app.post("/scout/targets/analyze")
async def scout_analyze_targets(req: dict):
    """Batch analyze selected targets and return insights."""
    target_ids = req.get("target_ids", [])
    results = await batch_analyze_targets(target_ids)
    return {"success": True, **results}


@app.post("/scout/targets/{target_id}/clone")
async def scout_clone_from_target(target_id: int, req: dict):
    """Generate a clone script from a target's top clip."""
    from scout.templates import generate_clone_script
    target = await get_target(target_id)
    if not target:
        from fastapi import HTTPException as HE
        raise HE(status_code=404, detail=f"Target {target_id} not found")
    clips = target.get("clips", [])
    if not clips:
        return {"success": False, "error": "Target has no clips to clone from"}
    # Use the top clip (most views) as reference
    top = max(clips, key=lambda c: c.get("views", 0))
    product_name = req.get("product_name", "สินค้า")
    fill_values = req.get("fill_values", {})
    result = await generate_clone_script(
        source_template_id=top.get("template_id", "") or "problem_solution",
        product_name=product_name,
        fill_values=fill_values,
    )
    if not result:
        return {"success": False, "error": "Could not generate clone"}
    return {"success": True, "clone": result, "source_clip": top}

# ─── Monitor Loop ─────────────────────────────────────────────────────────────

from monitor.tracker import (
    get_published_videos, record_analytics, get_video_analytics,
    compute_performance_summary,
)
from monitor.optimizer import (
    get_strategy, reset_strategy, update_strategy,
    analyze_and_optimize,
)


@app.get("/monitor/performance")
async def monitor_performance(
    account_id: str = "",
    hours: int = 168,
):
    """Get video performance summary over a time window."""
    summary = await compute_performance_summary(
        account_id=account_id,
        hours=hours,
    )
    return {"success": True, **summary}


@app.get("/monitor/videos")
async def monitor_videos(
    account_id: str = "",
    limit: int = 50,
):
    """Get published videos with their performance data."""
    videos = await get_video_analytics(account_id=account_id, limit=limit)
    return {"success": True, "videos": videos, "total": len(videos)}


@app.post("/monitor/analytics/record")
async def monitor_record_analytics(req: dict):
    """Record analytics data for a video."""
    await record_analytics(req)
    return {"success": True}


@app.get("/monitor/strategy")
async def monitor_get_strategy():
    """Get current content optimization strategy."""
    strategy = await get_strategy()
    return {"success": True, "strategy": strategy}


@app.post("/monitor/strategy/update")
async def monitor_update_strategy(req: dict):
    """Update content strategy parameters."""
    strategy = await update_strategy(req)
    return {"success": True, "strategy": strategy}


@app.post("/monitor/strategy/reset")
async def monitor_reset_strategy():
    """Reset strategy to defaults."""
    strategy = await reset_strategy()
    return {"success": True, "strategy": strategy}


@app.post("/monitor/optimize")
async def monitor_run_optimizer(req: dict):
    """Run full optimization loop — analyze performance & update strategy."""
    performance_data = req.get("performance_data", {})

    # If no performance data provided, compute from recent analytics
    if not performance_data:
        summary = await compute_performance_summary(
            account_id=req.get("account_id", ""),
            hours=req.get("hours", 168),
        )
        videos = await get_video_analytics(
            account_id=req.get("account_id", ""),
            hours=req.get("hours", 168),
        )

        # Build structured performance data
        category_perf = {}
        hooks_perf = {}
        hourly_perf = {}
        tpl_perf = {}

        for v in videos:
            cat = v.get("category", "unknown")
            if cat not in category_perf:
                category_perf[cat] = {"count": 0, "avg_views": 0, "total_views": 0}
            category_perf[cat]["count"] += 1
            category_perf[cat]["total_views"] += v.get("views", 0)

            hook = v.get("hook_type", "unknown")
            if hook not in hooks_perf:
                hooks_perf[hook] = {"count": 0, "avg_views": 0}
            hooks_perf[hook]["count"] += 1
            hooks_perf[hook]["avg_views"] = (
                hooks_perf[hook].get("avg_views", 0)
                * (hooks_perf[hook]["count"] - 1)
                + v.get("views", 0)
            ) / hooks_perf[hook]["count"]

            tpl = v.get("template_id", "unknown")
            if tpl not in tpl_perf:
                tpl_perf[tpl] = {"count": 0, "avg_views": 0}
            tpl_perf[tpl]["count"] += 1
            tpl_perf[tpl]["avg_views"] = (
                tpl_perf[tpl].get("avg_views", 0)
                * (tpl_perf[tpl]["count"] - 1)
                + v.get("views", 0)
            ) / tpl_perf[tpl]["count"]

            hour = v.get("post_hour", 12)
            if hour not in hourly_perf:
                hourly_perf[str(hour)] = {"avg_views": 0, "count": 0}
            hourly_perf[str(hour)]["count"] += 1
            hourly_perf[str(hour)]["avg_views"] = (
                hourly_perf[str(hour)].get("avg_views", 0)
                * (hourly_perf[str(hour)]["count"] - 1)
                + v.get("views", 0)
            ) / hourly_perf[str(hour)]["count"]

        for cat, data in category_perf.items():
            data["avg_views"] = round(data["total_views"] / data["count"])
            del data["total_views"]

        performance_data = {
            "summary": summary,
            "hooks_performance": hooks_perf,
            "templates_performance": tpl_perf,
            "category_performance": category_perf,
            "videos_by_hour": hourly_perf,
        }

    result = await analyze_and_optimize(
        performance_data=performance_data,
    )
    return {"success": True, **result}


# ─── Orchestrator: Full Pipeline ──────────────────────────────────────────

class FullPipelineRequest(BaseModel):
    """Full pipeline: script → TTS → image → video → compose."""
    # Product
    product_url: Optional[str] = ""
    product_title: Optional[str] = ""
    product_description: Optional[str] = ""
    product_image: Optional[str] = None  # base64 or URL
    model_image: Optional[str] = None  # base64 or URL for face ref
    # Script
    ugc_style: str = "holding"
    hook: Optional[str] = ""
    value_proposition: Optional[str] = ""
    cta: Optional[str] = ""
    # Video
    provider: str = "fal"
    duration: int = 10
    aspect_ratio: str = "9:16"
    negative_prompt: Optional[str] = ""
    # Audio
    tts_lang: str = "th"
    bg_music: Optional[str] = None  # URL or path to bg music
    # Pipeline control
    run_tts: bool = True
    run_video_gen: bool = True
    run_compose: bool = True


@app.post("/pipeline/run")
async def run_full_pipeline(req: FullPipelineRequest):
    """Run the full UGC pipeline: script → TTS → video gen → compose.

    Returns a pipeline job_id for status tracking.
    """
    import asyncio, os, tempfile
    from tts_gen import text_to_speech
    from composer import compose_video

    # Check if Fal.ai is available
    FAL_AVAILABLE = bool(os.environ.get("FAL_API_KEY") or os.environ.get("FAL_KEY"))

    # Create pipeline job
    job_id = _create_pipeline_job(account_id="", product_url=req.product_url or "")

    try:
        # Step 1: TTS
        if req.run_tts:
            _update_pipeline_step(job_id, "tts", "processing")
            full_text = " ".join(filter(None, [req.hook, req.value_proposition, req.cta]))
            if not full_text.strip():
                full_text = req.product_title or req.product_description or ""

            if full_text.strip():
                try:
                    tts_file = text_to_speech(
                        text=full_text.strip(),
                        lang=req.tts_lang or "th",
                    )
                    _update_pipeline_step(job_id, "tts", "success", {"filepath": tts_file})
                except Exception as e:
                    _update_pipeline_step(job_id, "tts", "error", {"error": str(e)})
                    raise
            else:
                _update_pipeline_step(job_id, "tts", "skipped")

        # Step 2: Video Gen — Fal.ai Wan I2V
        if req.run_video_gen:
            _update_pipeline_step(job_id, "video_gen", "processing")
            video_path = None
            if FAL_AVAILABLE and req.product_image:
                try:
                    from fal_client import generate_video_async
                    # Determine if product_image is a URL or base64
                    image_source = req.product_image
                    if image_source.startswith("data:") or image_source.startswith("file://"):
                        # Save base64 to temp file
                        import base64
                        if "," in image_source:
                            img_data = base64.b64decode(image_source.split(",", 1)[1])
                        else:
                            img_data = base64.b64decode(image_source)
                        tmp_img = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                        tmp_img.write(img_data)
                        tmp_img.close()
                        image_source = tmp_img.name

                    video_result = await generate_video_async(
                        image_path=image_source,
                        prompt=req.hook or req.product_title or "Product showcase",
                        duration=req.duration,
                        aspect_ratio=req.aspect_ratio,
                        negative_prompt=req.negative_prompt or None,
                    )
                    if video_result.get("success"):
                        video_path = video_result.get("video_url") or video_result.get("output")
                        _update_pipeline_step(job_id, "video_gen", "success", {
                            "video_url": video_path,
                            "duration": video_result.get("duration", req.duration),
                        })
                    else:
                        _update_pipeline_step(job_id, "video_gen", "error", {
                            "error": video_result.get("error", "Fal.ai API returned no video")
                        })
                except ImportError:
                    _update_pipeline_step(job_id, "video_gen", "skipped", {
                        "message": "fal_client module not available"
                    })
                except Exception as e:
                    logger.exception(f"Video gen failed: {e}")
                    _update_pipeline_step(job_id, "video_gen", "error", {"error": str(e)})
            elif FAL_AVAILABLE and not req.product_image:
                _update_pipeline_step(job_id, "video_gen", "skipped", {
                    "message": "No product image provided; skipping video gen"
                })
            else:
                _update_pipeline_step(job_id, "video_gen", "skipped", {
                    "message": "Fal.ai not configured. Set FAL_API_KEY or FAL_KEY"
                })

            if not video_path and req.run_compose and req.run_tts:
                # If video gen failed but we have TTS, still allow compose
                video_path = None

        # Step 3: Compose (merge TTS audio + video + bgm)
        if req.run_compose and video_path and req.run_tts:
            _update_pipeline_step(job_id, "compose", "processing")
            try:
                # Get TTS file path from step
                tts_step = _get_pipeline_job(job_id).get("steps", {}).get("tts", {})
                tts_path = tts_step.get("filepath", "")
                if tts_path and os.path.exists(tts_path):
                    output_path = os.path.join(
                        os.path.dirname(tts_path),
                        f"composed_{job_id}.mp4"
                    )
                    composed = compose_video(
                        video_path=video_path,
                        audio_path=tts_path,
                        output_path=output_path,
                    )
                    # Also add bg_music if provided
                    if req.bg_music and composed.get("success"):
                        final_path = output_path.replace(".mp4", "_bgm.mp4")
                        from composer import add_sound_effects
                        bgm_result = add_sound_effects(
                            video_path=output_path,
                            sound_path=req.bg_music,
                            output_path=final_path,
                        )
                        if bgm_result.get("success"):
                            output_path = final_path
                    _update_pipeline_step(job_id, "compose", "success", {
                        "output_path": output_path,
                    })
                else:
                    _update_pipeline_step(job_id, "compose", "skipped", {
                        "message": "No TTS audio to compose"
                    })
            except Exception as e:
                logger.exception(f"Compose failed: {e}")
                _update_pipeline_step(job_id, "compose", "error", {"error": str(e)})

        # Mark overall success
        _update_pipeline_step(job_id, "pipeline", "success")

        return {
            "success": True,
            "job_id": job_id,
            "status": "completed",
        }

    except Exception as e:
        logger.error(f"Pipeline {job_id} failed: {e}")
        _update_pipeline_step(job_id, "pipeline", "error", {"error": str(e)})
        return {
            "success": False,
            "job_id": job_id,
            "status": "error",
            "error": str(e),
        }


# ─── Script Generation Endpoints ──────────────────────────────────────────

@app.post("/scripts/generate")
def generate_script(req: ScriptRequest):
    """Generate TikTok review script using AiBot prompt system"""
    from script_gen import generate_tiktok_review_script
    try:
        result = generate_tiktok_review_script(
            product_name=req.product_name,
            customer_problem=req.customer_problem,
            main_benefit=req.main_benefit,
            target_audience=req.target_audience,
            tone=req.tone,
            cta=req.cta,
            duration=req.duration,
            extra_rules=req.extra_rules,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scripts/ugc")
def generate_ugc_script(req: UGCRequest):
    """Generate UGC video prompt by style"""
    from script_gen import generate_ugc_script
    try:
        result = generate_ugc_script(
            style=req.style,
            product_name=req.product_name,
            gender=req.gender,
            age=req.age,
            scene=req.scene,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/scripts/variations")
def script_variations():
    """Get available hook/tone/CTA variations"""
    from script_gen import get_script_variations
    return get_script_variations()


@app.get("/scripts/templates")
def script_templates():
    """List available script templates and UGC styles"""
    from script_gen import SCRIPT_TEMPLATES
    return {
        "durations": ["8s", "16s"],
        "ugc_styles": ["holding_product", "product_usage", "ugc_review"],
        "templates": {
            k: {
                "hook": v["hook"],
                "value": v["value"],
                "cta": v["cta"],
            }
            for k, v in SCRIPT_TEMPLATES.items()
        },
    }


# ─── Video Generation Endpoints ───────────────────────────────────────────

@app.post("/video/generate")
def generate_video(req: VideoRequest):
    """Start video generation task with optional negative prompt"""
    from video_gen import generate_video, build_video_prompt, VideoProvider

    prompt = req.prompt

    # If script is provided, build a video prompt from it
    if req.script and req.ugc_style:
        prompt = build_video_prompt(req.script, req.ugc_style)

    try:
        provider = VideoProvider(req.provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")

    try:
        result = generate_video(
            prompt=prompt,
            provider=provider,
            model_tier=req.model_tier,
            duration=req.duration,
            aspect_ratio=req.aspect_ratio,
            image_url=req.image_url,
            negative_prompt=req.negative_prompt,
        )
        # Include negative_prompt used in response
        result["negative_prompt"] = req.negative_prompt or ""
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.post("/video/status")
def video_status(req: VideoTaskRequest):
    """Check video generation status"""
    from video_gen import check_status, VideoProvider

    try:
        provider = VideoProvider(req.provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {req.provider}")

    try:
        result = check_status(provider, req.task_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/video/providers")
def video_providers():
    """List available and configured video providers"""
    from video_gen import get_available_providers, UGC_PRESETS

    return {
        "providers": get_available_providers(),
        "ugc_styles": list(UGC_PRESETS.keys()),
        "aspect_ratios": ["9:16", "16:9", "1:1"],
        "durations": [5, 8, 10, 15, 30, 60],
    }


# ─── Prompts Management ───────────────────────────────────────────────────

@app.get("/prompts/list")
def list_prompts():
    """List available prompt files in the system"""
    from pathlib import Path
    prompts_dir = Path(__file__).parent / "prompts"

    files = []
    for f in sorted(prompts_dir.rglob("*")):
        if f.is_file() and f.suffix in (".txt", ".json", ".prompt"):
            rel = f.relative_to(prompts_dir)
            files.append({
                "path": str(rel),
                "size": f.stat().st_size,
                "content_preview": f.read_text(encoding="utf-8")[:200],
            })

    return {"total": len(files), "files": files}


@app.get("/prompts/{path:path}")
def get_prompt(path: str):
    """Get a specific prompt file by path"""
    from pathlib import Path
    full_path = (Path(__file__).parent / "prompts" / path).resolve()
    prompts_dir = Path(__file__).parent / "prompts"

    if not str(full_path).startswith(str(prompts_dir.resolve())):
        raise HTTPException(status_code=403, detail="Path outside prompts directory")

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Prompt not found")

    return {
        "path": path,
        "size": full_path.stat().st_size,
        "content": full_path.read_text(encoding="utf-8"),
    }


# ─── Affiliate Integration ───────────────────────────────────────────────

AFFILIATE_CONFIG = {
    "shopee": AffiliateConfig(shopee_url=os.environ.get("AFFILIATE_SHOPEE_URL", "https://shopee.co.th")),
    "lazada": AffiliateConfig(lazada_url=os.environ.get("AFFILIATE_LAZADA_URL", "https://lazada.co.th")),
    "facebook": AffiliateConfig(facebook_url=os.environ.get("AFFILIATE_FACEBOOK_URL", "https://facebook.com/marketplace")),
    "tiktok": AffiliateConfig(tiktok_url=os.environ.get("AFFILIATE_TIKTOK_URL", "https://tiktok.com/shop")),
}


@app.post("/scripts/generate-with-affiliate")
def generate_script_with_affiliate(req: AffiliateScriptRequest):
    """Generate TikTok script + affiliate links"""
    from script_gen import generate_tiktok_review_script
    try:
        script = generate_tiktok_review_script(
            product_name=req.product_name,
            customer_problem=req.customer_problem,
            main_benefit=req.main_benefit,
            target_audience=req.target_audience,
            tone=req.tone,
            cta=req.cta or "กดลิงก์ด้านล่าง",
            duration=req.duration,
            extra_rules=req.extra_rules,
        )
        # Build affiliate links for requested platforms
        affiliate_links = {}
        for p in req.platforms:
            if p in AFFILIATE_CONFIG:
                cfg = AFFILIATE_CONFIG[p]
                url = getattr(cfg, f"{p}_url", f"https://{p}.com")
                affiliate_links[p] = url
        
        script["affiliate_links"] = affiliate_links
        if affiliate_links:
            platforms_str = ", ".join(a.title() for a in affiliate_links.keys())
            script["script"] += f"\n\n🛒 สั่งซื้อได้ที่: {platforms_str}"
            script["affiliate_cta"] = f"Check out on {', '.join(affiliate_links.keys())}!"
        return script
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/affiliate/config")
def get_affiliate_config():
    """Get current affiliate link configuration"""
    return {
        k: {"url": getattr(v, f"{k}_url", "")}
        for k, v in AFFILIATE_CONFIG.items()
    }


# ─── Task Queue ────────────────────────────────────────────────────────────

@app.post("/video/queue")
def queue_video(req: QueueVideoRequest):
    """Enqueue video generation task (background), returns task_id immediately"""
    from video_gen import enqueue_video_task
    try:
        task_id = enqueue_video_task(
            prompt=req.prompt,
            provider=req.provider,
            model_tier=req.model_tier,
            duration=req.duration,
            aspect_ratio=req.aspect_ratio,
            image_url=req.image_url,
            face_image_url=req.face_image_url,
        )
        return {"task_id": task_id, "status": "queued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/video/queue-status")
def queue_status(req: TaskStatusRequest):
    """Check queued task status — normalizes response for frontend"""
    from video_gen import get_task_status
    try:
        raw = get_task_status(req.task_id)
        status = raw.get("status", "unknown")
        normalized = {
            "task_id": req.task_id,
            "status": status,
            "url": "",
            "video_url": "",
        }
        if status == "completed":
            result_str = raw.get("result", "{}")
            # result is stored as JSON string from json.dumps
            if isinstance(result_str, str):
                try:
                    gen_result = json.loads(result_str)
                except json.JSONDecodeError:
                    # Might be a Python repr string from str(dict) — parse manually
                    gen_result = {}
            else:
                gen_result = result_str or {}
            video_url = gen_result.get("video_url", "") or gen_result.get("url", "")
            normalized["url"] = video_url
            normalized["video_url"] = video_url
        elif status == "failed":
            normalized["error"] = raw.get("error", "Unknown error")
        return normalized
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Video with Fallback ───────────────────────────────────────────────────

@app.post("/video/generate-with-fallback")
def generate_video_with_fallback(req: VideoRequest):
    """Generate video with automatic provider fallback chain"""
    from video_gen import generate_video_with_fallback, build_video_prompt
    prompt = req.prompt
    if req.script and req.ugc_style:
        prompt = build_video_prompt(req.script, req.ugc_style)
    try:
        result = generate_video_with_fallback(
            prompt=prompt,
            duration=req.duration,
            aspect_ratio=req.aspect_ratio,
            image_url=req.image_url,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# ─── Product Analysis ───────────────────────────────────────────────────────

@app.post("/product/analyze")
async def analyze_product(
    product_name: str = Form(...),
    description: str = Form(""),
    file: UploadFile = File(None),
):
    """Analyze product via Mistral — accepts multipart (image + text fields).
    Returns normalized JSON matching frontend expectations.
    """
    from gemini_agent import analyze_product

    # MEDIUM: Input validation
    if not product_name or not isinstance(product_name, str) or len(product_name.strip()) < 2:
        raise HTTPException(status_code=400, detail="Product name must be at least 2 characters")

    product_name = product_name.strip()
    description = description.strip()

    # Convert uploaded file to base64 and save for compositing
    image_base64 = None
    product_image_url = ""
    if file and file.filename:
        contents = await file.read()
        # MEDIUM: Validate file type and size
        if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
            raise HTTPException(status_code=400, detail="Only PNG, JPG, JPEG, WEBP images are supported")

        # Limit file size to 10MB
        if len(contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image size exceeds 10MB limit")

        await file.seek(0)  # Reset file pointer after reading

        if contents:
            image_base64 = base64.b64encode(contents).decode("utf-8")
            # Save product image so it can be referenced for compositing
            try:
                import os
                import time
                save_dir = "/home/openhands/erp-stack/etsy-wizard/static/product_images"
                os.makedirs(save_dir, exist_ok=True)
                safe_name = f"{int(time.time())}_{file.filename}"
                # MEDIUM: Sanitize filename to prevent path traversal
                import re
                safe_name = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', file.filename)
                safe_name = f"{int(time.time())}_{safe_name}"
                save_path = os.path.join(save_dir, safe_name)
                with open(save_path, "wb") as f:
                    f.write(contents)
                product_image_url = f"http://{os.environ.get('HOST_IP','localhost')}:8104/static/product_images/{safe_name}"
                logger.info(f"Saved product image for compositing: {save_path}")
            except Exception as e:
                logger.warning(f"Failed to save product image: {e}")
                product_image_url = ""

    try:
        result = analyze_product(
            product_name=product_name,
            description=description,
            category="",
            target_audience="",
            image_base64=image_base64,
        )
        # Normalize gemini_agent response to frontend format
        image_prompts_dict = {}
        for item in result.get("image_prompts", []):
            if isinstance(item, dict):
                img_id = item.get("id", "")
                prompt = item.get("prompt", "")
                bbox = item.get("bbox", {})
                if img_id:
                    image_prompts_dict[img_id] = prompt
        # Also include all as dict keys for easy access
        if not image_prompts_dict:
            # Maybe already in dict format
            image_prompts_dict = result.get("image_prompts", {})
            if not isinstance(image_prompts_dict, dict):
                image_prompts_dict = {}

        # Normalize video_prompt: if it's a dict, extract description field
        video_prompt_raw = result.get("video_prompt", "")
        if isinstance(video_prompt_raw, dict):
            video_prompt = video_prompt_raw.get("description", str(video_prompt_raw))
        else:
            video_prompt = video_prompt_raw

        normalized = {
            "image_prompts": image_prompts_dict,
            "video_prompt": video_prompt,
            "hooks": result.get("hook_suggestions", []),
            "copy": result.get("marketing_copy", ""),
            "seo_keywords": result.get("hashtags", []),
            "product_name": product_name,
            "product_desc": description,
            "product_image_url": product_image_url or None,
            "brand_protocol": result.get("brand_protocol", {}),
            "research": {
                "product_type": result.get("product_type", ""),
                "material": result.get("material", ""),
                "category": result.get("category", ""),
                "target_audience": result.get("target_audience", ""),
                "key_features": result.get("key_features", []),
            }
        }
        return normalized
    except Exception as e:
        logger.error(f"Product analysis failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=502, detail=str(e))


# ─── Export Endpoint ────────────────────────────────────────────────────────

class ExportRequest(BaseModel):
    url: str
    type: str = "image"
    prompt: str = ""

@app.post("/export")
def export_asset(req: ExportRequest):
    """Export generated asset to channel — stub for now, returns success"""
    logger.info(f"Export request: type={req.type}, url={req.url[:60]}...")
    return {
        "ok": True,
        "message": f"{req.type} exported successfully",
        "url": req.url,
        "type": req.type,
    }


# ═══════════════════════════════════════════════════════════════════════
# Module Integrations — Image Gen, Video Gallery, Payment
# ═══════════════════════════════════════════════════════════════════════

import httpx

MODULE_URLS = {
    "image-gen": "http://localhost:8110",
    "video-gen": "http://localhost:8116",
    "payment":   "http://localhost:8122",
    "profile":   "http://localhost:8107",
}


async def _proxy(method: str, module: str, path: str, body: dict = None) -> dict:
    """Proxy request to a module, return normalized response."""
    base = MODULE_URLS.get(module)
    if not base:
        raise HTTPException(status_code=400, detail=f"Unknown module: {module}")
    url = f"{base}{path}"
    try:
        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            if method == "GET":
                resp = await client.get(url)
            else:
                resp = await client.post(url, json=body or {})
            if resp.status_code >= 400:
                return {"ok": False, "status": resp.status_code, "error": resp.text[:300], "data": None}
            try:
                return {"ok": True, "status": resp.status_code, "data": resp.json()}
            except Exception:
                return {"ok": True, "status": resp.status_code, "data": {"text": resp.text}}
    except httpx.ConnectError:
        return {"ok": False, "status": 0, "error": f"Cannot reach {module} at {base}", "data": None}
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e), "data": None}


# ─── Image Gallery (proxy to Image Gen Module :8110) ─────────────────────

class ImageGenerateRequest(BaseModel):
    prompt: str
    model: str = "fast"
    image_url: str = ""
    template_id: str = ""
    size: str = "1024x1024"
    count: int = 1


@app.post("/images/generate")
async def generate_image(req: ImageGenerateRequest):
    """Generate product image via Image Gen module."""
    result = await _proxy("POST", "image-gen", "/api/image/v1/generate", req.model_dump())
    return result


@app.post("/images/remove-bg")
async def remove_bg(image_url: str = ""):
    """Remove background from image via Image Gen module."""
    result = await _proxy("POST", "image-gen", "/api/image/v1/remove-bg", {"imageUrl": image_url})
    return result


@app.post("/images/edit")
async def edit_image(prompt: str = "", image_url: str = ""):
    """Edit image via Image Gen module."""
    result = await _proxy("POST", "image-gen", "/api/image/v1/edit", {"prompt": prompt, "imageUrl": image_url})
    return result


@app.post("/images/upscale")
async def upscale_image(image_url: str = ""):
    """Upscale image via Image Gen module."""
    result = await _proxy("POST", "image-gen", "/api/image/v1/upscale", {"imageUrl": image_url})
    return result


@app.get("/images/templates")
async def list_image_templates():
    """List available image templates from Image Gen module."""
    result = await _proxy("GET", "image-gen", "/api/image/v1/templates")
    return result


@app.post("/images/product")
async def generate_product_image(product_name: str = "", description: str = "", category: str = ""):
    """Generate product image via Image Gen module's product pipeline."""
    result = await _proxy("POST", "image-gen", "/api/image/v1/product/generate", {
        "productName": product_name, "description": description, "category": category,
    })
    return result


@app.get("/images/gallery")
async def image_gallery():
    """List generated images from Image Gen module storage."""
    import glob
    storage = "/home/openhands/.openclaw/workspace/business-os/services/image-gen/storage/images"
    files = []
    for f in sorted(glob.glob(f"{storage}/**/*.*", recursive=True))[:50]:
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            files.append({
                "path": f.replace(storage, "").lstrip("/"),
                "url": f"http://localhost:8110/static/images/{os.path.basename(f)}",
            })
    return {"ok": True, "total": len(files), "items": files}


# ─── Video Gallery — see what's been generated ────────────────────────────

@app.get("/videos/gallery")
async def video_gallery():
    """List generated videos from task queue + Video Gen module."""
    from video_gen import task_queue
    import glob
    storage = os.environ.get("STORAGE_DIR", "/home/openhands/erp-stack/tiktok-ugc-studio/storage/videos")
    files = []
    for f in sorted(glob.glob(f"{storage}/**/*.*", recursive=True))[:50]:
        if f.lower().endswith((".mp4", ".mov", ".webm", ".gif")):
            files.append({"path": os.path.basename(f), "url": f"/static/videos/{os.path.basename(f)}"})
    # Also try query Video Gen module's jobs
    vg_jobs = await _proxy("GET", "video-gen", "/api/video/v1/jobs")
    return {
        "ok": True,
        "local_videos": len(files),
        "items": files,
        "video_gen_jobs": vg_jobs.get("data", vg_jobs.get("jobs", [])) if vg_jobs.get("ok") else [],
    }


# ─── Payment Integration (proxy to Payment Module :8122) ──────────────────

class CheckoutRequest(BaseModel):
    customer_email: str = ""
    plan_id: str = ""
    success_url: str = "https://wpilot.ai/success"
    cancel_url: str = "https://wpilot.ai/cancel"


class QRRequest(BaseModel):
    amount: int = 0
    currency: str = "thb"


@app.post("/payment/create-checkout")
async def payment_checkout(req: CheckoutRequest):
    """Create Stripe checkout session via Payment module."""
    result = await _proxy("POST", "payment", "/api/payment/checkout/create-session", {
        "customerEmail": req.customer_email,
        "planId": req.plan_id,
        "successUrl": req.success_url,
        "cancelUrl": req.cancel_url,
    })
    return result


@app.post("/payment/create-qr")
async def payment_qr(req: QRRequest):
    """Create QR PromptPay via Payment module."""
    result = await _proxy("POST", "payment", "/api/payment/qr/generate", {
        "amount": req.amount,
        "currency": req.currency,
    })
    return result


@app.get("/payment/plans")
async def payment_plans():
    """List subscription plans from Payment module."""
    result = await _proxy("GET", "payment", "/api/payment/subscriptions/plans")
    return result


@app.get("/payment/health")
async def payment_health():
    """Check Payment module health."""
    result = await _proxy("GET", "payment", "/api/payment/health")
    return result


# ─── Profile/Tier Integration (Profile Module :8107) ─────────────────────

@app.get("/profile/health")
async def profile_health():
    """Check Profile Module health."""
    result = await _proxy("GET", "profile", "/health")
    return result


@app.post("/profile/register")
async def profile_register(req: UserProfileRequest):
    """Register user via Profile Module."""
    result = await _proxy("POST", "profile", "/api/v1/profiles/client", req.model_dump())
    return result


@app.get("/profile/tier/{user_id}")
async def profile_get_tier(user_id: str):
    """Get user tier from Profile Module."""
    result = await _proxy("GET", "profile", f"/api/v1/profiles/client/{user_id}")
    return result


# ═══════════════════════════════════════════════════════════════════════

def _load_tiktok_accounts() -> dict:
    """Load saved TikTok accounts from disk."""
    TIKTOK_ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TIKTOK_ACCOUNTS_FILE.exists():
        try:
            with open(TIKTOK_ACCOUNTS_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_tiktok_accounts(accounts: dict):
    """Save TikTok accounts to disk."""
    TIKTOK_ACCOUNTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TIKTOK_ACCOUNTS_FILE, "w") as f:
        json.dump(accounts, f, indent=2, ensure_ascii=False)


class TikTokAccountConfig(BaseModel):
    """TikTok account configuration."""
    account_id: str = ""
    username: str = ""
    password: str = ""  # Optional
    use_qr: bool = False
    session_token: str = ""  # Token from 'tiktok-upload auth'


class TikTokUploadRequest(BaseModel):
    """Request to upload a video to TikTok."""
    account_id: str
    video_path: str
    caption: str = ""
    hashtags: list[str] = []
    schedule_hours: Optional[int] = None  # Schedule N hours from now
    allow_duet: bool = True
    allow_stitch: bool = True
    allow_comment: bool = True
    visibility: str = "public"
    # Video generation pipeline integration
    generate_from_prompt: Optional[str] = None  # If set, generate video first
    ugc_style: Optional[str] = None  # UGC style for video gen
    product_url: Optional[str] = None  # Scrape product + generate + upload pipeline
    negative_prompt: Optional[str] = None  # Added P1: negative prompt for video gen


class TikTokSessionRequest(BaseModel):
    """Check TikTok session status."""
    account_id: str


class PipelineJobStatusRequest(BaseModel):
    """Get pipeline job status."""
    job_id: str


# ═══════════════════════════════════════════════════════════════════════
# UGC Studio v2 — TTS, Fal.ai, Composer, Wav2Lip Pipeline
# ═══════════════════════════════════════════════════════════════════════

class BatchUploadRequest(BaseModel):
    """Batch upload multiple videos to TikTok."""
    account_id: str
    videos: list[TikTokUploadRequest]
    stagger_minutes: int = 30  # Minutes between each post


@app.post("/tiktok/batch-upload")
async def tiktok_batch_upload(req: BatchUploadRequest):
    """Upload multiple videos in sequence with staggered timing."""
    results = []
    schedule_offset = 0

    for i, video_req in enumerate(req.videos):
        video_req.account_id = req.account_id

        if schedule_offset > 0:
            video_req.schedule_hours = (video_req.schedule_hours or 0) + schedule_offset

        try:
            result = await tiktok_upload_video(video_req)
            results.append({"index": i, **result})
        except HTTPException as e:
            results.append({"index": i, "success": False, "error": e.detail})
        except Exception as e:
            results.append({"index": i, "success": False, "error": str(e)})

        schedule_offset += req.stagger_minutes / 60.0  # Convert to hours

    return {
        "success": True,
        "total": len(req.videos),
        "succeeded": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "results": results,
    }


# ─── TikTok Uploaded Videos ──────────────────────────────────────────────

@app.get("/tiktok/published")
async def tiktok_list_published(account_id: str = "", limit: int = 50):
    """List published videos from the tracker log."""
    published_log = Path(__file__).parent / "storage" / "published.json"
    if not published_log.exists():
        return {"success": True, "videos": [], "total": 0}

    try:
        with open(published_log) as f:
            entries = json.load(f)
        if account_id:
            entries = [e for e in entries if e.get("account_id") == account_id]
        return {
            "success": True,
            "videos": entries[-limit:],
            "total": len(entries),
        }
    except Exception as e:
        return {"success": False, "error": str(e)[:200], "videos": []}


# ─── TikTok Account Management ──────────────────────────────────────────

@app.get("/tiktok/accounts")
async def tiktok_list_accounts():
    """List all TikTok accounts with login status."""
    accounts = _load_tiktok_accounts()
    session_dir = Path(__file__).parent / "sessions" / "tiktok"
    account_list = []
    for aid, cfg in accounts.items():
        session_file = session_dir / f"{aid}.json"
        has_token = bool(cfg.get("session_token", ""))
        account_list.append({
            "id": aid,
            "username": cfg.get("username", aid),
            "use_qr": cfg.get("use_qr", False),
            "session_token": has_token,
            "is_logged_in": session_file.exists() or has_token,
        })
    return {"accounts": account_list, "total": len(account_list)}


@app.post("/tiktok/accounts")
async def tiktok_add_account(req: TikTokAccountConfig):
    """Add a new TikTok account."""
    accounts = _load_tiktok_accounts()
    account_id = req.account_id or req.username
    if not account_id:
        return {"success": False, "error": "Username required"}

    acct_data = req.model_dump(exclude_none=True, exclude={"session_token"})
    account_id = account_id.lstrip("@")
    acct_data["account_id"] = account_id
    acct_data["is_logged_in"] = bool(req.session_token)
    if req.session_token:
        acct_data["session_token"] = req.session_token
    accounts[account_id] = acct_data
    _save_tiktok_accounts(accounts)

    return {"success": True, "account_id": account_id}


@app.delete("/tiktok/accounts/{account_id}")
async def tiktok_remove_account(account_id: str):
    """Remove a TikTok account and its session."""
    accounts = _load_tiktok_accounts()
    accounts.pop(account_id, None)
    _save_tiktok_accounts(accounts)

    # Clean up session file
    session_file = Path(__file__).parent / "sessions" / "tiktok" / f"{account_id}.json"
    if session_file.exists():
        session_file.unlink()
    # Clean up QR screenshot
    qr_file = Path(__file__).parent / "sessions" / "tiktok" / f"{account_id}_qr.png"
    if qr_file.exists():
        qr_file.unlink()

    return {"success": True}


@app.post("/tiktok/login")
async def tiktok_login(req: TikTokSessionRequest):
    """Login to TikTok. Uses password login if available, otherwise QR code."""
    account_id = req.account_id.lstrip("@")
    accounts = _load_tiktok_accounts()
    acct = accounts.get(account_id, {})
    if not acct:
        # Also try without @
        acct = accounts.get(f"@{account_id}", {})
    if not acct:
        return {"success": False, "error": f"Account not found ({req.account_id})"}

    session_dir = Path(__file__).parent / "sessions" / "tiktok"
    session_dir.mkdir(parents=True, exist_ok=True)

    # If password provided, try password login first
    password = acct.get("password", "")
    if password and not acct.get("use_qr", False):
        logger.info(f"Using password login for {account_id}...")
        try:
            from tiktok_browser import login_tiktok
            result = await login_tiktok(
                account_id=account_id,
                username=acct.get("username", account_id),
                password=password,
                use_qr=False,
                timeout_seconds=120,
            )
            # Return whatever we got
            resp = {
                "success": result.get("success", False),
                "account_id": account_id,
                "method": "password",
                "session_valid": result.get("session_valid", False),
                "error": result.get("error", "")[:300],
            }
            if result.get("session_valid"):
                accounts[account_id]["is_logged_in"] = True
                _save_tiktok_accounts(accounts)
            return resp
        except Exception as e:
            logger.error(f"Password login error: {e}")
            return {"success": False, "account_id": account_id, "error": f"Password login failed: {str(e)[:200]}"}

    # Otherwise use QR (desktop viewport)
    logger.info(f"Using QR login for {account_id}...")
    try:
        from patchright.async_api import async_playwright

        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox", "--disable-setuid-sandbox",
                "--disable-dev-shm-usage", "--disable-gpu",
                "--window-size=1280,720",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        page = await context.new_page()

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)

        # Step 1: Go to /login
        logger.info(f"Navigating to TikTok login page (desktop)...")
        await page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        # Step 2: Click "Use QR code"
        logger.info(f"Clicking 'Use QR code'...")
        qr_btn = page.locator('text="Use QR code"').first
        await qr_btn.wait_for(timeout=10000)
        await qr_btn.click()
        await page.wait_for_timeout(3000)

        # Step 3: Wait for QR canvas
        logger.info(f"Waiting for QR code to render...")
        await page.wait_for_selector('canvas, img[src*="qr"], [class*="qr"]', timeout=15000)
        await page.wait_for_timeout(1000)

        # Step 4: Screenshot QR
        qr_path = str(session_dir / f"{account_id}_qr.png")
        await page.screenshot(path=qr_path, full_page=False)
        logger.info(f"QR code captured: {qr_path}")

        with open(qr_path, "rb") as f:
            qr_b64 = base64.b64encode(f.read()).decode()

        # Step 5: Start background polling
        asyncio.create_task(_poll_tiktok_qr_login_v2(account_id, p, context, browser, page))

        return {
            "success": True,
            "qr_code": f"data:image/png;base64,{qr_b64}",
            "account_id": account_id,
            "method": "qr",
            "session_valid": False,
            "note": "Scan QR with TikTok app, then confirm on your phone",
        }

    except Exception as e:
        logger.error(f"QR login error: {e}")
        return {"success": False, "error": f"QR login failed: {str(e)[:300]}"}


async def _poll_tiktok_qr_login_v2(account_id: str, playwright_inst, context, browser, page):
    """Background task: poll TikTok QR login page until scan completes."""
    try:
        logger.info(f"QR poll started for {account_id} - waiting for scan (180s)...")
        start = time.time()
        timeout_seconds = 180
        logged_in = False

        while time.time() - start < timeout_seconds:
            await asyncio.sleep(3)
            try:
                current_url = page.url
                # Check if redirected away from login (means success)
                if "login" not in current_url.lower():
                    logged_in = True
                    break

                # Check for user avatar (logged-in indicator)
                has_avatar = await page.evaluate("""
                    () => {
                        const avatar = document.querySelector('[data-e2e="user-avatar"]');
                        const profileIcon = document.querySelector('[class*="profile"]');
                        return !!(avatar || profileIcon);
                    }
                """)
                if has_avatar:
                    logged_in = True
                    break

                # Check if QR scan was accepted
                scan_ok = await page.evaluate("""
                    () => {
                        const text = document.body?.innerText || '';
                        return text.includes('Confirm') || text.includes('success') || text.includes('scan successful');
                    }
                """)
                if scan_ok:
                    logger.info(f"QR scan detected for {account_id}, waiting for confirmation...")
                    await asyncio.sleep(5)
            except Exception:
                try:
                    current_url = page.url
                    if "login" not in current_url.lower() and "tiktok.com" in current_url:
                        logged_in = True
                        break
                except Exception:
                    break

        if logged_in:
            from tiktok_browser import save_session
            await save_session(account_id, context)
            logger.info(f"QR login successful for {account_id}!")

            accounts = _load_tiktok_accounts()
            if account_id in accounts:
                accounts[account_id]["is_logged_in"] = True
                _save_tiktok_accounts(accounts)
        else:
            logger.warning(f"QR login timed out for {account_id}")

    except Exception as e:
        logger.error(f"QR poll error for {account_id}: {e}")
    finally:
        try:
            await page.close()
            await context.close()
            await browser.close()
            await playwright_inst.stop()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════
# TikTok QR Login — Server Endpoints (for frontend QR modal)
# ═══════════════════════════════════════════════════════════════════════

# In-memory store for QR login tokens
_qr_login_tokens: dict[str, dict] = {}


@app.post("/tiktok/qr-login")
async def tiktok_qr_login(req: Optional[TikTokSessionRequest] = None):
    """
    Generate TikTok QR code for login. Returns QR image URL + token_id for polling.
    This is used by the frontend QR Login modal.
    """
    token_id = f"qr_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    logger.info(f"QR login requested, token_id={token_id}")

    try:
        from patchright.async_api import async_playwright

        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox",
                  "--disable-dev-shm-usage", "--disable-gpu",
                  "--window-size=480,800"],
        )
        context = await browser.new_context(
            viewport={"width": 480, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Mobile Safari/537.36"
            ),
            locale="en-US",
        )
        page = await context.new_page()

        await page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)

        # Click QR code option
        try:
            qr_btn = page.locator('text="Use QR code"').first
            await qr_btn.wait_for(timeout=10000)
            await qr_btn.click()
        except Exception:
            # Maybe already on QR screen
            pass
        await page.wait_for_timeout(3000)

        # Capture QR screenshot
        qr_dir = Path(__file__).parent / "storage" / "qr_codes"
        qr_dir.mkdir(parents=True, exist_ok=True)
        qr_path = str(qr_dir / f"{token_id}.png")
        await page.screenshot(path=qr_path, full_page=False)

        # Convert to base64 for frontend
        with open(qr_path, "rb") as f:
            qr_b64 = base64.b64encode(f.read()).decode()

        # Store state for polling
        _qr_login_tokens[token_id] = {
            "status": "pending",
            "playwright": p,
            "browser": browser,
            "context": context,
            "page": page,
            "created_at": time.time(),
            "account_id": req.account_id if req else None,
        }

        # Start background poller
        asyncio.create_task(_poll_qr_login_page(token_id))

        return {
            "success": True,
            "token_id": token_id,
            "qr_code": f"data:image/png;base64,{qr_b64}",
            "qr_url": f"data:image/png;base64,{qr_b64}",
            "message": "📱 สแกน QR ด้วยแอป TikTok เพื่อล็อกอิน (QR หมดอายุ 300 วิ)",
            "expires_in": 300,
        }

    except Exception as e:
        logger.error(f"QR login error: {e}")
        return {"success": False, "error": f"สร้าง QR ไม่สำเร็จ: {str(e)[:200]}"}


async def _poll_qr_login_page(token_id: str):
    """Background task: poll QR login page and extract session cookies."""
    entry = _qr_login_tokens.get(token_id)
    if not entry:
        return

    page = entry["page"]
    timeout_seconds = 300
    start = time.time()

    try:
        while time.time() - start < timeout_seconds:
            await asyncio.sleep(3)

            try:
                current_url = page.url

                # Success: redirected away from login
                if "login" not in current_url.lower() and "tiktok.com" in current_url:
                    entry["status"] = "completed"
                    logger.info(f"QR [{token_id}] Login successful! URL: {current_url}")

                    # Extract session cookies
                    cookies = await context.cookies()
                    session_cookies = {
                        c["name"]: c["value"]
                        for c in cookies
                        if c["name"] in ("sessionid", "sid_ucp_v1", "sid_tt", "passport_csrf_token")
                    }

                    if session_cookies.get("sessionid"):
                        entry["session_cookies"] = session_cookies
                        entry["session_id"] = session_cookies["sessionid"]

                        # Save to accounts
                        if entry["account_id"]:
                            accounts = _load_tiktok_accounts()
                            aid = entry["account_id"]
                            if aid in accounts:
                                accounts[aid]["session_token"] = session_cookies["sessionid"]
                                accounts[aid]["is_logged_in"] = True
                                _save_tiktok_accounts(accounts)

                    entry["status"] = "completed"
                    return

                # Check scan detected
                scan_text = await page.evaluate("""
                    () => document.body?.innerText?.toLowerCase() || ''
                """)
                if "confirm" in scan_text or "scan successful" in scan_text:
                    logger.info(f"QR [{token_id}] Scan detected, waiting for confirm...")
                    await asyncio.sleep(5)

            except Exception as e:
                logger.debug(f"QR [{token_id}] poll error (normal if page closed): {e}")
                break

        if entry["status"] == "pending":
            entry["status"] = "expired"
            logger.info(f"QR [{token_id}] Timed out")

    except Exception as e:
        logger.error(f"QR [{token_id}] Poll error: {e}")
        entry["status"] = "failed"
    finally:
        try:
            await page.close()
            await context.close()
            await browser.close()
            await playwright_inst.stop()
        except Exception:
            pass


@app.get("/tiktok/qr-status/{token_id}")
async def tiktok_qr_status(token_id: str):
    """Check the status of a QR login attempt."""
    entry = _qr_login_tokens.get(token_id)
    if not entry:
        return {"status": "not_found", "error": "Token not found or expired"}

    result = {
        "status": entry.get("status", "pending"),
        "logged_in": entry.get("status") == "completed",
    }

    if entry.get("session_id"):
        result["session_id"] = entry["session_id"][:20] + "..."

    if entry.get("account_id"):
        result["account_id"] = entry["account_id"]

    # Clean up expired tokens
    if entry.get("status") in ("completed", "expired", "failed"):
        if time.time() - entry.get("created_at", 0) > 3600:
            _qr_login_tokens.pop(token_id, None)

    return result


@app.post("/tiktok/check-session")
async def tiktok_check_session(req: TikTokSessionRequest):
    """Check if saved TikTok session is valid."""
    try:
        from tiktok_browser import check_session
        result = await check_session(req.account_id)

        # Update stored login status
        accounts = _load_tiktok_accounts()
        if req.account_id in accounts:
            accounts[req.account_id]["is_logged_in"] = result.get("valid", False)
            _save_tiktok_accounts(accounts)

        return result
    except Exception as e:
        return {"valid": False, "error": str(e)[:200]}


@app.post("/tiktok/upload")
async def tiktok_upload_video(req: TikTokUploadRequest):
    """Upload a video to TikTok using session token."""
    try:
        accounts = _load_tiktok_accounts()
        acct = accounts.get(req.account_id.lstrip("@"))
        if not acct:
            return {"success": False, "error": "Account not found"}

        token = acct.get("session_token", "")
        if not token:
            return {"success": False, "error": "No session token. Run 'tiktok-upload auth' first"}

        video_path = Path(req.video_path)
        if not video_path.exists():
            return {"success": False, "error": f"Video not found: {req.video_path}"}

        import os
        from simple_tiktok_uploader import upload
        os.environ["TIKTOK_SESSION"] = token

        caption = req.caption
        if req.hashtags:
            caption += " " + " ".join(f"#{h}" for h in req.hashtags)

        result = upload(str(video_path), caption)
        return {
            "success": True,
            "video_id": getattr(result, "id", "") or getattr(result, "video_id", ""),
            "url": getattr(result, "url", "") or getattr(result, "share_url", ""),
            "account_id": req.account_id,
        }
    except Exception as e:
        return {"success": False, "error": str(e)[:200]}


# ─── TikTok Pipeline Status ──────────────────────────────────────────────

@app.post("/tiktok/pipeline")
async def tiktok_full_pipeline(req: TikTokUploadRequest):
    """
    Full pipeline: Scrape → Generate Script → Generate Video → Upload to TikTok
    Returns a job_id for tracking step-by-step progress.
    """
    import httpx

    # Create pipeline job
    job_id = _create_pipeline_job(req.account_id, req.product_url or "")
    _update_pipeline_step(job_id, "init", "success", {"account": req.account_id})

    pipeline_steps = {}
    pipeline_steps["account_valid"] = True
    logger.info(f"Pipeline [{job_id}] started for account {req.account_id}")

    # Step 1: Validate account
    accounts = _load_tiktok_accounts()
    if req.account_id not in accounts:
        _update_pipeline_step(job_id, "account_check", "error", {"error": "Account not found"})
        return {"success": False, "job_id": job_id, "error": f"Account {req.account_id} not found"}
    _update_pipeline_step(job_id, "account_check", "success")

    # Step 2: Scrape (if product_url provided)
    scraped_data = {}
    if req.product_url:
        _update_pipeline_step(job_id, "scrape", "running")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                key_resp = await client.post(
                    f"{SCRAPER_API_URL}/api/v1/keys/create",
                    json={"name": "tiktok-pipeline"},
                    headers={"x-user-id": "tiktok-ugc"}
                )
                key_data = key_resp.json()
                api_key = key_data.get("key", "")

                scrape_resp = await client.post(
                    f"{SCRAPER_API_URL}/api/v1/scrape",
                    json={"url": req.product_url, "use_cache": True},
                    headers={"x-api-key": api_key}
                )
                scrape_data = scrape_resp.json()

                if scrape_data.get("success"):
                    product_data = scrape_data.get("data", {})
                    scraped_data = product_data
                    pipeline_steps["scrape"] = {"success": True, "product": product_data.get("name", "")}
                    _update_pipeline_step(job_id, "scrape", "success", {
                        "product": product_data.get("name", ""),
                        "source": req.product_url
                    })
                else:
                    pipeline_steps["scrape"] = {"success": False, "error": scrape_data.get("error")}
                    _update_pipeline_step(job_id, "scrape", "error", {"error": scrape_data.get("error")})
        except Exception as e:
            pipeline_steps["scrape"] = {"success": False, "error": str(e)[:100]}
            _update_pipeline_step(job_id, "scrape", "error", {"error": str(e)[:100]})

    # Step 3: Generate Script
    _update_pipeline_step(job_id, "script_gen", "running")
    try:
        product_name = scraped_data.get("name", req.caption or "สินค้า")
        from script_gen import generate_tiktok_review_script
        script_result = generate_tiktok_review_script(
            product_name=product_name,
            duration="8s",
        )
        script_text = script_result.get("script", "")
        pipeline_steps["script_gen"] = {"success": True, "length": len(script_text)}
        _update_pipeline_step(job_id, "script_gen", "success", {"length": len(script_text)})
    except Exception as e:
        pipeline_steps["script_gen"] = {"success": False, "error": str(e)[:100]}
        _update_pipeline_step(job_id, "script_gen", "error", {"error": str(e)[:100]})

    # Step 4: Generate Video (placeholder — actual gen is async)
    _update_pipeline_step(job_id, "video_gen", "running")
    pipeline_steps["video_gen"] = {"note": "See /video/generate for async generation"}
    _update_pipeline_step(job_id, "video_gen", "pending", {"note": "Use /video/generate for actual generation"})

    # Step 5: Upload (simulated — actual upload via Playwright)
    _update_pipeline_step(job_id, "upload", "running")
    try:
        from tiktok_browser import watch_for_schedule
        pipeline_steps["upload"] = {
            "success": True,
            "simulated": True,
            "note": "Use /tiktok/upload for actual upload"
        }
        _update_pipeline_step(job_id, "upload", "success", {"simulated": True})
    except Exception as e:
        pipeline_steps["upload"] = {"success": False, "error": str(e)[:200]}
        _update_pipeline_step(job_id, "upload", "error", {"error": str(e)[:200]})

    final_success = pipeline_steps.get("upload", {}).get("success", False) or pipeline_steps.get("script_gen", {}).get("success", False)
    return {
        "success": final_success,
        "job_id": job_id,
        "status": "completed",
        "pipeline_steps": pipeline_steps,
        "job_url": f"/pipeline/{job_id}/status",
    }


# ═══════════════════════════════════════════════════════════════════════
# Post For Me Integration — Social Media Auto Post
# ═══════════════════════════════════════════════════════════════════════


class PFMConnectionRequest(BaseModel):
    """Connect a social account via Post For Me."""
    platform: Literal["tiktok", "instagram", "facebook", "youtube", "x", "linkedin", "threads", "pinterest", "bluesky"]
    callback_url: str = "http://89.167.82.205:8105/tiktok/auth/callback"


class PFMPostRequest(BaseModel):
    """Post content via Post For Me."""
    account_id: str
    caption: str
    media_urls: list[str] = []
    schedule_at: Optional[str] = None


@app.get("/pfm/accounts")
async def pfm_list_accounts():
    """List all Post For Me connected accounts."""
    try:
        accounts = pfm_get_accounts()
        return {"success": True, "accounts": accounts, "total": len(accounts)}
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


@app.post("/pfm/post")
async def pfm_create_post(req: PFMPostRequest):
    """Post content to a social account via Post For Me."""
    try:
        result = pfm_post(
            account_id=req.account_id,
            text=req.caption,
            media_urls=req.media_urls,
            schedule_at=req.schedule_at,
        )
        return {
            "success": True,
            "post_id": result.get("id", ""),
            "status": result.get("status", ""),
            "result": result
        }
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


@app.get("/pfm/post/{post_id}")
async def pfm_post_status(post_id: str):
    """Check the status of a post."""
    try:
        result = pfm_post_status(post_id)
        return {"success": True, "status": result.get("status", ""), "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


@app.post("/pfm/auto-publish")
async def pfm_auto_publish(req: TikTokUploadRequest):
    """
    Full auto: Generate clip → Auto Post via Post For Me.
    Reuses TikTokUploadRequest schema for compatibility.
    """
    try:
        # Map account_id → PFM social account ID
        # Currently hardcoded; will sync from PFM in future
        pfm_accounts = pfm_get_accounts()
        target_account = None
        for acc in pfm_accounts:
            a_id = acc.get("id", "")
            platform = acc.get("platform", "")
            username = acc.get("username", "")
            # Match by account_id or username
            if req.account_id in (a_id, username, f"@{username}"):
                target_account = a_id
                break

        if not target_account:
            # Fallback: use first connected TikTok
            tiktok_accs = [a["id"] for a in pfm_accounts if a.get("platform") == "tiktok"]
            if tiktok_accs:
                target_account = tiktok_accs[0]

        if not target_account:
            return {"success": False, "error": "No connected TikTok account found"}

        caption = req.caption
        if req.hashtags:
            caption += " " + " ".join(f"#{h}" for h in req.hashtags)

        result = pfm_post(
            account_id=target_account,
            text=caption,
            media_urls=[req.video_path] if req.video_path else [],
            schedule_at=str(req.schedule_hours) if req.schedule_hours else None,
        )

        # Track in published log
        published_log = Path(__file__).parent / "storage" / "published.json"
        try:
            if published_log.exists():
                with open(published_log) as f:
                    published = json.load(f)
            else:
                published = []
            published.append({
                "id": result.get("id", ""),
                "caption": caption[:100],
                "account_id": req.account_id,
                "pfm_account_id": target_account,
                "video_path": req.video_path,
                "timestamp": datetime.now().isoformat(),
                "status": result.get("status", ""),
            })
            with open(published_log, "w") as f:
                json.dump(published[-100:], f, indent=2)
        except Exception:
            pass

        return {
            "success": True,
            "method": "post_for_me",
            "post_id": result.get("id", ""),
            "status": result.get("status", ""),
            "pfm_account_id": target_account,
            "result": result
        }
    except Exception as e:
        return {"success": False, "error": str(e)[:300]}


@app.get("/stats")
def stats():
    return {
        "service": "tiktok-ugc-studio",
        "version": "0.2.0",
        "prompts_loaded": True,
    }

# ═══════════════════════════════════════════════════════════════════════
# ERP Modular Registration (startup)
# ═══════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def register_with_erp():
    """Register this service with ERP Modular on startup."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post("http://localhost:8102/api/v1/modules/register", json={
                "name": "TikTok UGC Studio",
                "slug": "tiktok-ugc-studio",
                "version": "0.2.0",
                "endpoint": "http://localhost:8105",
                "description": "AI UGC video pipeline + Scout + Monitor. "
                               "Script gen, TTS, Fal.ai Wan I2V, FFmpeg compose, "
                               "TikTok Scout (trends), Monitor Loop (optimization)",
            })
            if resp.status_code < 400:
                logger.info("✅ Registered with ERP Modular")
            else:
                logger.warning(f"ERP registration returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"ERP registration skipped: {e}")
