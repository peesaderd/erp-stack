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

TIKTOK_ACCOUNTS_FILE = STORAGE_DIR / "tiktok_accounts.json"

from fastapi import FastAPI, HTTPException, Query, Request, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import base64
import uuid
import sqlite3
import requests
import httpx

import sys
sys.path.insert(0, os.path.dirname(__file__))

# Module service URLs
MODULE_URLS = {
    "image-gen": "http://localhost:8110",
    "video-gen": "http://localhost:8111",
    "video": "http://localhost:8111",
    "prompt-builder": "http://localhost:8117",
    "payment": "http://localhost:8122",
    "profile": "http://localhost:8107",
    "auth": "http://localhost:8101",
}

async def _proxy(method: str, module: str, path: str, body: dict = None, timeout: float = 90.0) -> dict:
    """Proxy request to a module, return normalized response."""
    base = MODULE_URLS.get(module)
    if not base:
        raise HTTPException(status_code=400, detail=f"Unknown module: {module}")
    url = f"{base}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
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
    except Exception as e:
        return {"ok": False, "status": 0, "error": str(e), "data": None}

# Load .env file for API keys
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
    description="AI UGC video pipeline - Script gen, TTS, Wan 2.7 I2V, FFmpeg compose, TikTok integration",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file serving
(STORAGE_DIR / "tts").mkdir(parents=True, exist_ok=True)
(STORAGE_DIR / "composed").mkdir(parents=True, exist_ok=True)
(STORAGE_DIR / "videos").mkdir(parents=True, exist_ok=True)
try:
    app.mount("/static", StaticFiles(directory=str(STORAGE_DIR)), name="static")
except Exception as e:
    logger.warning(f"Static mount: {e}")

PRODUCT_IMAGE_DIR = STORAGE_DIR / "product_images"
PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

# In-memory pipeline results
_pipeline_results = {}

# ─── Pydantic Models ───────────────────────────────────────────────────────

class ScriptRequest(BaseModel):
    product_name: str = ""
    customer_problem: str = ""
    main_benefit: str = ""
    target_audience: str = ""
    tone: str = ""
    cta: str = ""
    duration: str = "8s"
    extra_rules: str = ""
    product_url: str = ""
    product_title: str = ""
    product_details: str = ""
    ugc_style: str = ""

class UGCRequest(BaseModel):
    style: str = "ugc_review"
    product_name: str
    product_desc: str = ""
    gender: str = "female"
    age: str = "25-35"
    scene: str = "home"
    negative_prompt: Optional[str] = None

class TTSRequest(BaseModel):
    text: str
    lang: str = "th"
    slow: bool = False

class ScriptTTSRequest(BaseModel):
    hook: str
    value_proposition: str = ""
    cta: str = ""
    lang: str = "th"

class SceneBlock(BaseModel):
    script: str
    duration: int = 8
    mood: str = "energetic"
    sound_style: str = "upbeat_pop"
    style: str = "product_usage"

class VideoRequest(BaseModel):
    product_title: str = ""
    product_url: str = ""
    product_image: str = ""
    product_price: Optional[float] = None
    product_description: Optional[str] = ""
    product_commission: Optional[float] = None
    tags: list[str] = []
    hook: str = ""
    value: str = ""
    cta: str = ""
    content_type: str = "affiliate"
    ugc_style: str = "product_usage"
    aspect_ratio: str = "9:16"
    duration: int = 8
    scenes: list[SceneBlock] = []
    prompt: str = ""
    provider: str = "prodia"
    model_tier: str = "standard"
    image_url: Optional[str] = None
    script: Optional[str] = None
    negative_prompt: Optional[str] = None

class VideoPostRequest(BaseModel):
    job_id: str
    account_id: str
    affiliate_link: str = ""
    caption: str = ""
    schedule_at: Optional[str] = None

class FullPipelineRequest(BaseModel):
    product_url: Optional[str] = ""
    product_title: Optional[str] = ""
    product_description: Optional[str] = ""
    product_image: Optional[str] = None
    model_image: Optional[str] = None
    ugc_style: str = "holding"
    hook: Optional[str] = ""
    value_proposition: Optional[str] = ""
    cta: Optional[str] = ""
    provider: str = "prodia"
    duration: int = 8
    aspect_ratio: str = "9:16"
    negative_prompt: Optional[str] = ""
    tts_lang: str = "th"
    bg_music: Optional[str] = None
    preset: Optional[str] = None
    recipe: Optional[str] = None
    run_tts: bool = True
    run_video_gen: bool = True
    run_compose: bool = True
    platforms: Optional[list] = None
    schedule_time: Optional[str] = "immediate"

class ScrapeAndGenerateRequest(BaseModel):
    url: str
    duration: str = "8s"
    tone: str = ""
    cta: str = ""
    ugc_style: str = "ugc_review"
    use_vision: bool = False

# ─── Auth Proxy Routes ─────────────────────────────────────────────────────

@app.post("/api/auth/register")
async def auth_register(req: dict):
    return await _proxy("POST", "auth", "/api/v1/auth/register", req)

@app.post("/api/auth/login")
async def auth_login(req: dict):
    return await _proxy("POST", "auth", "/api/v1/auth/login", req)

@app.get("/api/auth/me")
async def auth_me(request: Request):
    base = MODULE_URLS["auth"]
    url = f"{base}/api/v1/auth/me"
    headers = {"Authorization": request.headers.get("authorization", "")}
    async with httpx.AsyncClient(timeout=90, verify=False) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code >= 400:
            return {"ok": False, "status": resp.status_code, "error": resp.text[:300], "data": None}
        return {"ok": True, "status": resp.status_code, "data": resp.json()}

@app.get("/api/auth/{provider}/login")
async def auth_oauth_login(provider: str):
    return await _proxy("GET", "auth", f"/api/v1/auth/{provider}/login")

@app.get("/api/auth/{provider}/callback")
async def auth_oauth_callback(provider: str, code: str = "", state: str = "", error: str = ""):
    return await _proxy("GET", "auth", f"/api/v1/auth/{provider}/callback?code={code}&state={state}&error={error}")

# ─── Health ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "tiktok-ugc-studio", "version": "0.2.0"}

# ─── Product Scraper ───────────────────────────────────────────────────────

SCRAPER_API_URL = "http://localhost:8106"

@app.post("/product/scrape-and-generate")
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

@app.post("/tts/generate")
async def generate_tts(req: TTSRequest):
    """Generate TTS audio from text using Gemini via video module."""
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    result = await _proxy("POST", "video", "/api/v1/tts/generate", {
        "text": req.text.strip(),
        "voice": "Aoede"
    })
    if result.get("ok"):
        data = result.get("data", {})
        filepath = data.get("filepath", "")
        filename = os.path.basename(filepath)
        return {
            "success": True,
            "audio_url": f"/static/tts/{filename}",
            "filepath": filepath,
            "filename": filename,
            "duration_estimate": len(req.text.strip()) / 12,
        }
    else:
        raise HTTPException(status_code=502, detail=result.get("error", "TTS generation failed"))

@app.post("/tts/script")
async def generate_script_tts(req: ScriptTTSRequest):
    """Generate TTS for full UGC script (hook + value + CTA) as segments."""
    result = await _proxy("POST", "video", "/api/v1/tts/script", {
        "script": {
            "hook": req.hook,
            "body": req.value_proposition,
            "cta": req.cta
        },
        "voice": "Aoede"
    })
    if result.get("ok"):
        data = result.get("data", {})
        data["success"] = True
        return data
    else:
        raise HTTPException(status_code=502, detail=result.get("error", "Script TTS failed"))

# ─── Pipeline Database ─────────────────────────────────────────────────────

PIPELINE_DB_PATH = os.path.join(os.path.dirname(__file__), "pipeline.db")

def _init_pipeline_db():
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
    job = _get_pipeline_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"success": True, "job": job}

@app.get("/pipeline/list")
def pipeline_list(limit: int = 20):
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    rows = conn.execute(
        "SELECT job_id, account_id, status, product_url, created_at, updated_at FROM pipeline_jobs ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return {"success": True, "jobs": [{"job_id": r[0], "account_id": r[1], "status": r[2], "product_url": r[3], "created_at": r[4], "updated_at": r[5]} for r in rows]}

@app.post("/pipeline/run")
async def run_full_pipeline(req: FullPipelineRequest):
    """Run the full UGC pipeline: script → TTS → video gen → compose."""
    job_id = _create_pipeline_job(account_id="", product_url=req.product_url or "")

    try:
        if req.run_tts:
            _update_pipeline_step(job_id, "tts", "processing")
            full_text = " ".join(filter(None, [req.hook, req.value_proposition, req.cta]))
            if not full_text.strip():
                full_text = req.product_title or req.product_description or ""

            if full_text.strip():
                tts_result = await _proxy("POST", "video", "/api/v1/tts/generate", {
                    "text": full_text.strip(),
                    "lang": req.tts_lang or "th",
                })
                if tts_result.get("ok"):
                    tts_file = tts_result["data"].get("filepath") or tts_result["data"].get("audio_path", "")
                    _update_pipeline_step(job_id, "tts", "success", {"filepath": tts_file})
                else:
                    raise Exception(tts_result.get("error", "TTS proxy call failed"))
            else:
                _update_pipeline_step(job_id, "tts", "skipped")

        if req.run_video_gen:
            _update_pipeline_step(job_id, "video_gen", "processing")
            if req.product_image:
                img_result = await _proxy("POST", "video", "/api/v1/image/generate", {
                    "image_path": req.product_image,
                    "prompt": req.hook or req.product_title or "Product showcase",
                    "duration": min(req.duration or 8, 8),
                    "negative_prompt": req.negative_prompt or "low resolution, error, worst quality",
                })
                vid_path = (img_result.get("data") or {}).get("video_path") or (img_result.get("data") or {}).get("filepath")
                if vid_path:
                    _update_pipeline_step(job_id, "video_gen", "success", {"video_url": vid_path, "duration": req.duration})
                else:
                    _update_pipeline_step(job_id, "video_gen", "error", {"error": "No video returned"})
            else:
                _update_pipeline_step(job_id, "video_gen", "skipped", {"message": "No product image"})

        _update_pipeline_step(job_id, "pipeline", "success")
        return {"success": True, "job_id": job_id, "status": "completed"}
    except Exception as e:
        logger.error(f"Pipeline {job_id} failed: {e}")
        _update_pipeline_step(job_id, "pipeline", "error", {"error": str(e)})
        return {"success": False, "job_id": job_id, "status": "error", "error": str(e)}

# ─── Script Generation ─────────────────────────────────────────────────────

@app.post("/scripts/generate")
async def generate_script(req: ScriptRequest):
    """Generate TikTok review script via Prompt Builder service"""
    try:
        result = await _proxy("POST", "prompt-builder", "/api/v1/build", req.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/scripts/ugc")
async def generate_ugc_script(req: UGCRequest):
    """Generate UGC video prompt via Video Module"""
    try:
        result = await _proxy("POST", "video", "/api/v1/scripts/ugc", req.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/scripts/variations")
async def script_variations():
    result = await _proxy("GET", "video", "/api/v1/scripts/variations")
    return result

@app.get("/scripts/templates")
async def script_templates():
    result = await _proxy("GET", "video", "/api/v1/scripts/templates")
    return {
        "durations": ["8s", "16s"],
        "ugc_styles": ["holding_product", "product_usage", "ugc_review"],
        "templates": result.get("templates", {}),
    }

# ─── Video Generation ──────────────────────────────────────────────────────

@app.post("/video/generate")
async def generate_video(req: VideoRequest):
    """Full UGC pipeline with scenes and metadata."""
    job_id = f"vid_{uuid.uuid4().hex[:8]}"

    if req.hook and req.value and req.cta:
        script_parts = [req.hook, req.value, req.cta]
        full_script = " ".join(script_parts)
    elif req.script:
        full_script = req.script
    elif req.prompt:
        full_script = req.prompt
    elif req.product_title:
        full_script = f"Check out this {req.product_title}! Amazing quality, great value! Link in bio! 🛍️"
    else:
        full_script = "Check out this amazing product!"

    scenes = []
    if req.scenes:
        scenes = req.scenes
    elif req.duration <= 8:
        scenes = [SceneBlock(
            script=full_script,
            duration=min(req.duration, 8),
            mood="energetic",
            sound_style="upbeat_pop",
            style=req.ugc_style,
        )]
    else:
        scenes = [
            SceneBlock(
                script=f"{req.hook or ''} Let me show you this!" if req.hook else f"Check out {req.product_title}!",
                duration=8,
                mood="energetic",
                sound_style="upbeat_pop",
                style="holding_product",
            ),
            SceneBlock(
                script=f"{req.value or ''} {req.cta or 'Link in bio!'}" if req.value else f"Amazing right? {req.cta or 'Link in bio! 🛍️'}",
                duration=8,
                mood="calm",
                sound_style="chill_loft",
                style="product_usage",
            ),
        ]

    async def _run():
        try:
            pb_result = await _proxy("POST", "prompt-builder", "/api/v1/build", {
                "product_name": req.product_title or "",
                "description": req.product_description or "",
                "keywords": req.tags or [],
                "ugc_style": req.ugc_style or "holding",
                "product_id": job_id,
                "price": float(req.product_price) if req.product_price else 0.0,
            })

            if pb_result.get("ok") and pb_result.get("data"):
                pb_data = pb_result["data"]
                img_prompt = pb_data.get("image_prompt", "")
                video_prompts = [pb_data.get("video_prompt", "")] * len(scenes)
                neg_prompt = pb_data.get("negative_prompt", req.negative_prompt)
            else:
                img_prompt = scenes[0].script if scenes else (req.product_title or "product")
                video_prompts = [s.script for s in scenes] if scenes else [req.product_title or "product"]
                neg_prompt = req.negative_prompt

            selected_sound_style = scenes[0].sound_style if scenes else "upbeat_pop"

            product_img_local = None
            if req.product_image:
                # แปลง /ugc/static/product_images/xxx → local file path
                if req.product_image.startswith("/ugc/static/product_images/"):
                    filename = req.product_image.replace("/ugc/static/product_images/", "")
                    product_img_local = str(STORAGE_DIR / "product_images" / filename)
                # แปลง external IP → localhost
                elif "89.167.82.205" in req.product_image and "8105" in req.product_image:
                    product_img_local = req.product_image.replace("http://89.167.82.205:8105", "http://localhost:8105")
                else:
                    product_img_local = req.product_image

            affiliate_result = await _proxy("POST", "video", "/api/v1/video/generate", {
                "product_title": req.product_title or "",
                "product_image": product_img_local or "",
                "product_price": req.product_price,
                "product_commission": req.product_commission,
                "hook": req.hook or "",
                "value": req.value or "",
                "cta": req.cta or "",
                "duration": min(scenes[0].duration, 8) if scenes else 8,
                "scenes": [s.dict() for s in scenes] if scenes else [],
                "tags": req.tags or [],
                "content_type": req.content_type or "affiliate",
                "ugc_style": req.ugc_style or "product_usage",
                "aspect_ratio": req.aspect_ratio or "9:16",
                "negative_prompt": req.negative_prompt,
            }, timeout=300.0)  # Video pipeline takes 90-180s

            if not affiliate_result.get("ok"):
                raise Exception(affiliate_result.get("error", "Pipeline affiliate run failed"))
            
            # Video module returns {"success": bool, "result": {...}}
            api_data = affiliate_result.get("data", {})
            if not api_data.get("success"):
                raise Exception(api_data.get("error", "Video generation failed"))
            
            result = api_data.get("result", {})
            VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
            final_path = result.get("final_path", "")

            import shutil
            final_video_path = VIDEOS_DIR / f"final_{job_id}.mp4"
            shutil.copy2(final_path, final_video_path)

            _pipeline_results[job_id] = {
                "status": "completed",
                "video_url": f"/static/videos/final_{job_id}.mp4",
                "cost": result.get("cost_estimate", 0),
                "metadata": {
                    "product_name": req.product_title or "",
                    "product_url": req.product_url or "",
                    "product_image": req.product_image or "",
                    "product_price": req.product_price,
                    "product_commission": req.product_commission,
                    "tags": req.tags,
                    "hook": req.hook,
                    "value": req.value,
                    "cta": req.cta,
                    "content_type": req.content_type,
                    "ugc_style": req.ugc_style,
                    "duration": req.duration,
                    "aspect_ratio": req.aspect_ratio or "9:16",
                },
                "job_id": job_id,
            }
        except Exception as e:
            logger.exception(f"Pipeline {job_id} failed")
            _pipeline_results[job_id] = {"status": "failed", "error": str(e), "job_id": job_id}

    asyncio.create_task(_run())

    _pipeline_results[job_id] = {
        "status": "processing",
        "job_id": job_id,
        "message": f"Pipeline running... Style: {req.ugc_style}, Content: {req.content_type}",
    }

    return {
        "status": "queued",
        "job_id": job_id,
        "duration": req.duration,
        "metadata_preview": {
            "product": req.product_title,
            "style": req.ugc_style,
            "content_type": req.content_type,
            "scenes": len(scenes),
            "tags": req.tags,
        },
    }

@app.get("/video/status/{job_id}")
def video_pipeline_status(job_id: str):
    result = _pipeline_results.get(job_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return result

@app.post("/video/status/{task_id}")
async def video_status(task_id: str):
    result = await _proxy("GET", "video", f"/api/v1/video/status/{task_id}")
    return result

@app.get("/video/completed")
def list_completed_videos():
    jobs = []
    for job_id, result in _pipeline_results.items():
        if result.get("status") == "completed":
            meta = result.get("metadata", {})
            jobs.append({
                "job_id": job_id,
                "video_url": result.get("video_url", ""),
                "cost": result.get("cost", 0),
                "product_name": meta.get("product_name", ""),
                "duration": meta.get("duration", 8),
                "style": meta.get("ugc_style", ""),
            })
    jobs.reverse()
    return {"jobs": jobs, "total": len(jobs)}

@app.get("/active-model")
async def get_active_model():
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("http://127.0.0.1:8777/v1/active-model")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return {"model": "opencode-go/deepseek-v4-flash"}

@app.post("/active-model")
async def set_active_model(req: dict):
    import httpx
    model = req.get("model")
    if not model:
        raise HTTPException(status_code=400, detail="model required")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post("http://127.0.0.1:8777/v1/active-model", json={"model": model})
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Proxy error: {e}")
    return {"success": False}

@app.get("/opencode-models")
async def get_opencode_models():
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("http://127.0.0.1:8777/v1/models")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    # Fallback list of models
    fallback = [
        {"id": "opencode-go/deepseek-v4-flash", "object": "model"},
        {"id": "opencode-go/deepseek-v4-pro", "object": "model"},
        {"id": "opencode-go/qwen3.7-max", "object": "model"},
        {"id": "opencode-go/glm-5.2", "object": "model"}
    ]
    return {"object": "list", "data": fallback}

@app.get("/video/providers")
async def video_providers():
    return {
        "ok": True,
        "providers": ["prodia", "nanobanana"],
        "models": {
            "nanobanana": "Nano Banana Pro (Img2Img)",
            "flux-2-klein": "FLUX.2 Klein (Txt2Img)",
            "wan-2-7": "Wan 2.7 (Img2Vid)"
        },
    }

# ─── TikTok Accounts & Upload ──────────────────────────────────────────────

def _load_tiktok_accounts() -> dict:
    if TIKTOK_ACCOUNTS_FILE.exists():
        try:
            return json.loads(TIKTOK_ACCOUNTS_FILE.read_text())
        except Exception:
            return {}
    return {}

def _save_tiktok_accounts(accounts: dict):
    TIKTOK_ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2))

@app.get("/tiktok/accounts")
async def list_tiktok_accounts():
    accounts = _load_tiktok_accounts()
    return {"success": True, "accounts": [{"id": k, **v} for k, v in accounts.items()]}

@app.post("/tiktok/accounts")
async def save_tiktok_account(req: dict):
    account_id = req.get("account_id", "")
    if not account_id:
        raise HTTPException(status_code=400, detail="account_id required")
    accounts = _load_tiktok_accounts()
    accounts[account_id] = req
    _save_tiktok_accounts(accounts)
    return {"success": True, "account_id": account_id}

@app.delete("/tiktok/accounts/{account_id}")
async def delete_tiktok_account(account_id: str):
    accounts = _load_tiktok_accounts()
    if account_id in accounts:
        del accounts[account_id]
        _save_tiktok_accounts(accounts)
    return {"success": True}

@app.post("/tiktok/upload")
async def upload_to_tiktok(req: dict):
    """Upload video to TikTok with session token."""
    video_path = req.get("video_path", "")
    caption = req.get("caption", "")
    session_token = req.get("session_token", "")

    if not video_path or not session_token:
        raise HTTPException(status_code=400, detail="video_path and session_token required")

    os.environ["TIKTOK_SESSION"] = session_token
    try:
        from simple_tiktok_uploader import upload
        result = upload(video_path, caption)
        post_id = getattr(result, "id", "") or getattr(result, "video_id", "")
        return {"success": True, "video_id": post_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/video/post")
async def post_video_to_tiktok(req: VideoPostRequest):
    """Post a completed video to TikTok."""
    result = _pipeline_results.get(req.job_id)
    if not result or result.get("status") != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")

    video_url = result.get("video_url", "")
    video_filename = video_url.replace("/static/videos/", "")
    video_path = VIDEOS_DIR / video_filename
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")

    meta = result.get("metadata", {})
    hook = meta.get("hook", "") or meta.get("product_name", "Check this out!")
    caption = req.caption or hook
    if req.affiliate_link:
        caption += f"\n\n🔗 {req.affiliate_link}"

    accounts = _load_tiktok_accounts()
    acct = accounts.get(req.account_id.lstrip("@"))
    if not acct or not acct.get("session_token"):
        raise HTTPException(status_code=400, detail="No session token for account")

    os.environ["TIKTOK_SESSION"] = acct["session_token"]
    try:
        from simple_tiktok_uploader import upload
        upl_result = upload(str(video_path), caption)
        post_id = getattr(upl_result, "id", "") or getattr(upl_result, "video_id", "")
        return {"success": True, "video_id": post_id, "account_id": req.account_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

# ─── Payment & Profile Proxies ────────────────────────────────────────────

@app.post("/payment/create-checkout")
async def payment_create_checkout(req: dict):
    return await _proxy("POST", "payment", "/api/v1/checkout", req)

@app.post("/payment/create-qr")
async def payment_create_qr(req: dict):
    return await _proxy("POST", "payment", "/api/v1/qr", req)

@app.get("/payment/plans")
async def payment_plans():
    return await _proxy("GET", "payment", "/api/v1/plans")

@app.get("/payment/health")
async def payment_health():
    return await _proxy("GET", "payment", "/health")

@app.get("/profile/health")
async def profile_health():
    return await _proxy("GET", "profile", "/health")

@app.post("/profile/register")
async def profile_register(req: dict):
    return await _proxy("POST", "profile", "/api/v1/profiles", req)

@app.get("/profile/tier/{user_id}")
async def profile_tier(user_id: str):
    return await _proxy("GET", "profile", f"/api/v1/profiles/{user_id}/tier")

# ─── Products List ───────────────────────────────────────────────────────

@app.get("/products/list")
def list_products(limit: int = 50, preset: str = "all"):
    """List products from tus_products.db for the frontend product grid."""
    db_path = os.path.join(os.path.dirname(__file__), "tus_products.db")
    if not os.path.exists(db_path):
        return {"products": []}
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
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
        row_dict["image_count"] = len(row_dict["images"])
        products.append(row_dict)
    
    return {"products": products}

# ─── UGC Frontend API Compatibility ───────────────────────────────────────

@app.post("/ugc/scripts/generate")
async def ugc_scripts_generate(req: dict):
    """Frontend compatibility endpoint for script generation."""
    result = await _proxy("POST", "prompt-builder", "/api/v1/build", req)
    if result.get("ok"):
        return result.get("data", {})
    raise HTTPException(status_code=500, detail=result.get("error", "Script generation failed"))

@app.post("/ugc/images/build-prompt")
async def ugc_images_build_prompt(req: dict):
    """Frontend compatibility endpoint for image prompt generation."""
    result = await _proxy("POST", "prompt-builder", "/api/v1/build", req)
    if result.get("ok"):
        data = result.get("data", {})
        return {"prompt": data.get("image_prompt", "")}
    raise HTTPException(status_code=500, detail=result.get("error", "Prompt generation failed"))

@app.post("/ugc/images/generate")
async def ugc_images_generate(req: dict):
    """Frontend compatibility endpoint for image generation."""
    result = await _proxy("POST", "image-gen", "/api/v1/image/generate", req)
    if result.get("ok"):
        return result.get("data", {})
    raise HTTPException(status_code=500, detail=result.get("error", "Image generation failed"))

from fastapi.staticfiles import StaticFiles

# Mount static file serving for product images
product_images_dir = os.path.join(os.path.dirname(__file__), "storage", "product_images")
os.makedirs(product_images_dir, exist_ok=True)
app.mount("/ugc/static/product_images", StaticFiles(directory=product_images_dir), name="product_images")

# ─── Product Analysis ─────────────────────────────────────────────────────

@app.post("/product/analyze")
async def analyze_product(
    product_name: str = Form(...),
    description: str = Form(""),
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
            image_base64=image_base64,
        )
        return {
            "success": True,
            "analysis": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── Dashboard Summary ──────────────────────────────────────────────────

@app.get("/dashboard/summary")
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
                "FROM pipeline_jobs ORDER BY created_at DESC LIMIT 10"
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
    products_db_path = os.path.join(os.path.dirname(__file__), "tus_products.db")
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
    credit_file = os.path.join(os.path.dirname(__file__), "credit_balance.txt")
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

@app.get("/products/sheets/status")
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
        
        creds_path = os.path.join(os.path.dirname(__file__), '..', 'modules', 'product', 'sheets_credentials.json')
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

@app.get("/pipeline/recipes")
def get_pipeline_recipes():
    """Get pipeline recipe templates."""
    recipes = [
        {
            "name": "skincare",
            "label": "🧴 Skincare Glow",
            "description": "Soft luxury vibes, calm music, slow transitions",
            "ugc_style": "product_usage",
            "sound_style": "luxury_jazz",
            "mood": "calm",
            "duration": 10,
            "bgm_style": "luxury_jazz",
        },
        {
            "name": "gadget",
            "label": "📱 Gadget Unboxing",
            "description": "Fast-paced, energetic, quick cuts",
            "ugc_style": "holding_product",
            "sound_style": "upbeat_pop",
            "mood": "energetic",
            "duration": 8,
            "bgm_style": "upbeat_pop",
        },
        {
            "name": "fashion",
            "label": "👗 Fashion Lookbook",
            "description": "Elegant slow-mo, chic aesthetic",
            "ugc_style": "talking_head",
            "sound_style": "chill_loft",
            "mood": "luxurious",
            "duration": 8,
            "bgm_style": "chill_loft",
        },
        {
            "name": "food",
            "label": "🍜 Food Review",
            "description": "Warm ASMR-style close-up shots",
            "ugc_style": "ugc_review",
            "sound_style": "asmr",
            "mood": "fun",
            "duration": 10,
            "bgm_style": "asmr",
        },
        {
            "name": "asmr",
            "label": "🎧 ASMR Unboxing",
            "description": "Quiet ambient, gentle sounds, relaxing",
            "ugc_style": "product_usage",
            "sound_style": "asmr",
            "mood": "calm",
            "duration": 12,
            "bgm_style": "asmr",
        },
        {
            "name": "makeup",
            "label": "💄 Makeup Tutorial",
            "description": "Soft upbeat, beauty close-ups, trendy",
            "ugc_style": "talking_head",
            "sound_style": "upbeat_pop",
            "mood": "energetic",
            "duration": 10,
            "bgm_style": "upbeat_pop",
        },
        {
            "name": "fitness",
            "label": "💪 Fitness/Supplement",
            "description": "High energy, motivating, fast tempo",
            "ugc_style": "holding_product",
            "sound_style": "energetic_edm",
            "mood": "energetic",
            "duration": 8,
            "bgm_style": "energetic_edm",
        },
    ]
    return {"recipes": recipes}

# ─── Missing Endpoints (Frontend Compatibility) ──────────────────────

@app.get("/pipeline/detail/{job_id}")
async def pipeline_detail(job_id: str):
    """Get pipeline job details (frontend expects /pipeline/detail/{id})."""
    result = _pipeline_results.get(job_id)
    if not result:
        return {"error": "Job not found"}
    return {"job": result}

@app.post("/dashboard/track-event")
async def track_event():
    """Track dashboard events (no-op for now)."""
    return {"ok": True}

@app.get("/pipeline/assets")
async def pipeline_assets():
    """Get pipeline assets list."""
    return {"assets": [], "count": 0}

@app.get("/posts/scheduled")
async def posts_scheduled():
    """Get scheduled posts list."""
    return {"posts": [], "count": 0}

@app.post("/pipeline/{job_id}/retry")
async def pipeline_retry(job_id: str):
    """Retry a failed pipeline job."""
    return {"success": False, "error": "Not implemented yet"}

@app.post("/pipeline/{job_id}/cancel")
async def pipeline_cancel(job_id: str):
    """Cancel a running pipeline job."""
    return {"success": False, "error": "Not implemented yet"}


# ═══════════════════════════════════════════════════════════════════════════
# MONITOR ROUTES — Performance tracking & content strategy optimization
# ═══════════════════════════════════════════════════════════════════════════

from monitor import tracker as monitor_tracker
from monitor import optimizer as monitor_optimizer


@app.get("/monitor/performance")
async def monitor_performance(hours: int = Query(168, ge=1, le=8760), account_id: str = ""):
    """Get performance summary for a time window."""
    return await monitor_tracker.compute_performance_summary(account_id=account_id, hours=hours)


@app.get("/monitor/videos")
async def monitor_videos(account_id: str = "", limit: int = Query(50, ge=1, le=500)):
    """Get published videos list."""
    return {"videos": await monitor_tracker.get_published_videos(account_id=account_id, limit=limit)}


@app.get("/monitor/strategy")
async def monitor_get_strategy():
    """Get current content strategy."""
    return {"strategy": await monitor_optimizer.get_strategy()}


@app.post("/monitor/optimize")
async def monitor_optimize(req: dict):
    """Analyze performance and optimize strategy."""
    hours = req.get("hours", 168)
    perf = await monitor_tracker.compute_performance_summary(hours=hours)
    return await monitor_optimizer.analyze_and_optimize({"summary": perf})


@app.post("/monitor/strategy/reset")
async def monitor_reset_strategy():
    """Reset strategy to defaults."""
    return {"strategy": await monitor_optimizer.reset_strategy()}


# ═══════════════════════════════════════════════════════════════════════════
# SCOUT ROUTES — Trend intelligence & competitive analysis
# ═══════════════════════════════════════════════════════════════════════════

from scout import targets as scout_targets_mod
from scout import trends as scout_trends_mod
from scout import templates as scout_templates_mod


@app.get("/scout/targets")
async def scout_list_targets():
    """List all tracked competitor accounts."""
    return {"targets": await scout_targets_mod.list_targets()}


@app.post("/scout/targets")
async def scout_create_target(req: dict):
    """Add a target account to track."""
    return await scout_targets_mod.create_target(req)


@app.get("/scout/targets/{target_id}")
async def scout_get_target(target_id: int):
    """Get target account details with clips."""
    t = await scout_targets_mod.get_target(target_id)
    if not t:
        raise HTTPException(404, "Target not found")
    return t


@app.post("/scout/targets/{target_id}/delete")
async def scout_delete_target(target_id: int):
    """Delete a target account."""
    await scout_targets_mod.delete_target(target_id)
    return {"success": True}


@app.post("/scout/targets/analyze")
async def scout_analyze_targets(req: dict):
    """Batch analyze multiple targets."""
    target_ids = req.get("target_ids", [])
    return await scout_targets_mod.batch_analyze_targets(target_ids)


@app.post("/scout/targets/{target_id}/clips")
async def scout_add_clip(target_id: int, req: dict):
    """Add a clip to a target account."""
    result = await scout_targets_mod.add_clip(target_id, req)
    if not result:
        raise HTTPException(404, "Target not found")
    return result


@app.post("/scout/targets/{target_id}/clone")
async def scout_clone_target(target_id: int, req: dict):
    """Generate clone script from a target's content."""
    t = await scout_targets_mod.get_target(target_id)
    if not t:
        raise HTTPException(404, "Target not found")
    product_name = req.get("product_name", "สินค้า")
    fill_values = req.get("fill_values", {})
    # Use first target clip as source if available
    if t.get("clips"):
        clip = t["clips"][0]
        return await scout_templates_mod.generate_clone_script(
            source_template_id=clip.get("template_id", "problem_solution"),
            product_name=product_name,
            fill_values=fill_values,
        )
    return await scout_templates_mod.generate_from_template(
        template_id="problem_solution",
        product_name=product_name,
        fill_values=fill_values,
    )


@app.get("/scout/trends")
async def scout_trends(category: str = "", keyword: str = "", limit: int = Query(10, ge=1, le=50)):
    """Discover trending content patterns."""
    return {"trends": await scout_trends_mod.discover_trends(category=category, keyword=keyword, limit=limit)}


@app.get("/scout/templates")
async def scout_templates_list(category: str = ""):
    """List content templates."""
    return {"templates": await scout_templates_mod.get_templates(category=category)}


@app.post("/scout/templates/generate")
async def scout_templates_generate(req: dict):
    """Generate a script from a template."""
    result = await scout_templates_mod.generate_from_template(
        template_id=req.get("template_id", "problem_solution"),
        product_name=req.get("product_name", "สินค้า"),
        price=req.get("price", ""),
        fill_values=req.get("fill_values", {}),
        cta=req.get("cta", "กด link in bio"),
    )
    if not result:
        raise HTTPException(404, "Template not found")
    return result


@app.get("/tiktok/published")
async def tiktok_published(account_id: str = "", limit: int = Query(50, ge=1, le=500)):
    """Get published TikTok videos."""
    return {"videos": await monitor_tracker.get_published_videos(account_id=account_id, limit=limit)}


# ─── Startup Event ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info("TikTok UGC Studio starting up...")
    logger.info(f"Storage: {STORAGE_DIR}")
    logger.info(f"Module URLs: {MODULE_URLS}")

# ─── Root ─────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "service": "TikTok UGC Studio",
        "version": "0.2.0",
        "status": "running",
        "docs": "/docs",
    }
