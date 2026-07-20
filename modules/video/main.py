"""
Video Generation Module — Microservice
=======================================
AI UGC Video Generator: Script → TTS → Video Gen (Prodia/Fal) → Compose
Part of Business OS, registered with ERP Modular.

Port: 8111
"""

import os
import sys
import json
import uuid
import time
import asyncio
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ─── Path setup ───────────────────────────────────────────────────────
_module_dir = os.path.dirname(os.path.abspath(__file__))
_modules_dir = os.path.dirname(_module_dir)
if _modules_dir not in sys.path:
    sys.path.insert(0, _modules_dir)
if _module_dir not in sys.path:
    sys.path.insert(0, _module_dir)

# ─── Storage ──────────────────────────────────────────────────────────
STORAGE_DIR = Path(__file__).parent / "storage"
TTS_DIR = STORAGE_DIR / "tts"
VIDEOS_DIR = STORAGE_DIR / "videos"
COMPOSED_DIR = STORAGE_DIR / "composed"
for d in [TTS_DIR, VIDEOS_DIR, COMPOSED_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Config ควบคุมค่า default — แก้ที่ config.py ที่เดียว
from config import DEFAULT_DURATION

# ─── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("video-module")

# ─── FastAPI App ──────────────────────────────────────────────────────
app = FastAPI(
    title="Video Generation Module",
    version="0.1.0",
    description="AI UGC Video Generation — Script, TTS, Video Gen, Pipeline, Compose",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files for generated assets
try:
    app.mount("/static", StaticFiles(directory=str(STORAGE_DIR)), name="static")
except Exception:
    pass

# ─── Pydantic Models ──────────────────────────────────────────────────

class ScriptRequest(BaseModel):
    product_name: str
    customer_problem: str = ""
    main_benefit: str = ""
    target_audience: str = ""
    tone: str = ""
    cta: str = ""
    duration: str = f"{DEFAULT_DURATION}s"
    extra_rules: str = ""

class UGCRequest(BaseModel):
    style: str = "ugc_review"
    product_name: str
    product_desc: str = ""
    gender: str = "female"
    age: str = "25-35"
    scene: str = "home"
    negative_prompt: Optional[str] = None

class ConcatRequest(BaseModel):
    video_urls: list[str]
    output_duration: int = 16

class SceneBlock(BaseModel):
    script: str = ""
    duration: int = DEFAULT_DURATION
    mood: str = "energetic"
    sound_style: str = "upbeat_pop"
    style: str = "product_usage"

class VideoRequest(BaseModel):
    product_title: str = ""
    product_url: str = ""
    product_image: str = ""
    product_price: Optional[float] = None
    product_commission: Optional[float] = None
    tags: list[str] = []
    hook: str = ""
    value: str = ""
    cta: str = ""
    content_type: str = "affiliate"
    ugc_style: str = "product_usage"
    aspect_ratio: str = "9:16"
    duration: int = DEFAULT_DURATION
    scenes: list[SceneBlock] = []
    prompt: str = ""
    provider: str = "prodia"
    model_tier: str = "standard"
    image_url: Optional[str] = None
    script: Optional[str] = None
    negative_prompt: Optional[str] = None
    product_description: Optional[str] = None
    recipe: Optional[str] = None
    job_id: Optional[str] = None  # external job_id from caller — used to keep pipeline_logs.db in sync

class FullPipelineRequest(BaseModel):
    product_title: str = ""
    product_description: str = ""
    product_url: str = ""
    product_image: str = ""
    product_price: Optional[float] = None
    hook: str = ""
    value_proposition: str = ""
    cta: str = ""
    duration: int = DEFAULT_DURATION
    aspect_ratio: str = "9:16"
    tts_lang: str = "th"
    bg_music: Optional[str] = None
    negative_prompt: Optional[str] = None
    ugc_style: str = "product_usage"
    recipe: Optional[str] = None
    run_tts: bool = True
    run_video_gen: bool = True
    run_compose: bool = True

class AffiliateScriptRequest(ScriptRequest):
    platforms: list[str] = []

# ─── Pipeline Job Store (in-memory) ────────────────────────────────────
_pipeline_jobs: dict = {}

def _create_job(account_id: str = "", product_url: str = "") -> str:
    job_id = str(uuid.uuid4())[:8]
    _pipeline_jobs[job_id] = {
        "id": job_id,
        "created_at": datetime.now().isoformat(),
        "status": "created",
        "steps": {},
    }
    return job_id

def _update_step(job_id: str, step: str, status: str, result: dict = None):
    if job_id in _pipeline_jobs:
        _pipeline_jobs[job_id]["steps"][step] = {
            "status": status,
            "result": result or {},
            "updated_at": datetime.now().isoformat(),
        }

def _get_job(job_id: str) -> dict:
    return _pipeline_jobs.get(job_id, {})

# ─── Health ────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "video-module", "version": "0.1.0"}

# ─── Script Generation ────────────────────────────────────────────────

@app.post("/api/v1/scripts/generate")
async def generate_script(req: ScriptRequest):
    """Generate TikTok UGC review script using AI."""
    from video.script_gen import generate_tiktok_review_script
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
    return {"success": True, "script": result}

@app.post("/api/v1/scripts/ugc")
async def generate_ugc_script(req: UGCRequest):
    """Generate UGC-style script."""
    from video.script_gen import generate_ugc_script
    result = generate_ugc_script(
        style=req.style,
        product_name=req.product_name,
        product_desc=req.product_desc,
        gender=req.gender,
        age=req.age,
        scene=req.scene,
    )
    return {"success": True, "script": result, "style": req.style}

@app.get("/api/v1/scripts/variations")
async def get_script_variations():
    """List available script variation templates."""
    from video.script_gen import get_script_variations
    return {"success": True, "variations": get_script_variations()}

@app.get("/api/v1/scripts/templates")
async def list_script_templates():
    """List all available script templates."""
    from video.script_gen import SCRIPT_TEMPLATES
    return {"success": True, "templates": SCRIPT_TEMPLATES}

@app.post("/api/v1/scripts/affiliate")
async def generate_affiliate_script(req: AffiliateScriptRequest):
    """Generate script with affiliate links."""
    from video.script_gen import generate_tiktok_review_script
    script = generate_tiktok_review_script(
        product_name=req.product_name,
        customer_problem=req.customer_problem,
        main_benefit=req.main_benefit,
        target_audience=req.target_audience,
        tone=req.tone,
        cta=req.cta,
        duration=req.duration,
        extra_rules=req.extra_rules + "\nInclude affiliate links",
    )
    return {"success": True, "script": script, "platforms": req.platforms}

@app.get("/api/v1/affiliate/config")
async def get_affiliate_config():
    return {"success": True, "config": {}}

# ─── TTS (Gemini) ──────────────────────────────────────────────────────

@app.post("/api/v1/tts/generate")
async def generate_tts(req: dict):
    """Generate TTS audio from text using Gemini."""
    from video.gemini_tts import gemini_text_to_speech
    text = req.get("text", "")
    voice = req.get("voice", "Aoede")
    if not text:
        return {"success": False, "error": "No text provided"}
    output_path = str(TTS_DIR / f"tts_{uuid.uuid4().hex[:8]}.mp3")
    filepath = gemini_text_to_speech(text, output_path=output_path, voice=voice)
    return {"success": True, "filepath": filepath}

@app.post("/api/v1/tts/script")
async def generate_script_tts(req: dict):
    """Generate TTS from a full script using Gemini."""
    from video.gemini_tts import gemini_text_to_speech
    script = req.get("script", {})
    hook = script.get("hook", "")
    body = script.get("body", "") or script.get("value_proposition", "")
    cta = script.get("cta", "")
    full_text = " ".join(filter(None, [hook, body, cta]))
    if not full_text.strip():
        return {"success": False, "error": "No text in script"}
    voice = req.get("voice", "Aoede")
    output_path = str(TTS_DIR / f"script_{uuid.uuid4().hex[:8]}.mp3")
    filepath = gemini_text_to_speech(full_text, output_path=output_path, voice=voice)
    return {"success": True, "filepath": filepath}

# ─── Video Generation ────────────────────────────────────────────────

@app.post("/api/v1/video/generate")
async def generate_video(req: VideoRequest):
    """Generate AI video via Affiliate Pipeline (unified).
    
    All content types now route through pipeline_affiliate.
    The pipeline handles: Gemini Vision → SAM3 → Script Gen → TTS → Nano Banana → Wan 2.7 → FFmpeg
    """
    from video.pipeline_affiliate import run_pipeline
    
    # Build script from hook + value + cta if no explicit script provided
    script = req.script or ""
    if not script:
        parts = [p for p in [req.hook, req.value, req.cta] if p]
        script = " ".join(parts) if parts else req.product_title or "รีวิวสินค้า"
    
    # Build scene prompts from request
    scene_prompts = []
    if req.scenes:
        scene_prompts = [s.script or s.mood for s in req.scenes]
    if not scene_prompts:
        # Default: single scene from product title
        scene_prompts = [req.product_title or "สินค้าน่าสนใจ วางบนพื้นผิวสวยงาม แสงธรรมชาติ"]
    
    product_image = req.product_image or req.image_url or ""
    
    try:
        result = run_pipeline(
            product_name=req.product_title or script[:60] if script else "สินค้า",
            product_image=product_image if product_image else None,
            recipe_name=req.recipe or "tus",
            voice="Aoede",
            bgm_style="chill_loft",
            description=req.product_description or "",
            ugc_style=req.ugc_style or "holding",
            external_job_id=req.job_id,
            duration=req.duration,
        )
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        return {"success": False, "error": str(e)}



@app.get("/api/v1/videos/gallery")
async def video_gallery():
    """List generated videos from storage."""
    files = []
    for f in sorted(VIDEOS_DIR.glob("**/*.*"))[:50]:
        if f.suffix.lower() in (".mp4", ".webm", ".mov"):
            files.append({"name": f.name, "size": f.stat().st_size, "path": f"/static/videos/{f.name}"})
    return {"success": True, "videos": files}

# ─── Pipeline ─────────────────────────────────────────────────────────

@app.get("/api/v1/pipeline/{job_id}/status")
async def pipeline_get_status(job_id: str):
    """Get pipeline job status."""
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "job": job}

@app.get("/api/v1/pipeline/list")
async def pipeline_list(limit: int = 20):
    """List recent pipeline jobs."""
    jobs = sorted(_pipeline_jobs.values(), key=lambda j: j.get("created_at", ""), reverse=True)[:limit]
    return {"success": True, "jobs": jobs, "total": len(_pipeline_jobs)}

@app.post("/api/v1/pipeline/run")
async def run_full_pipeline(req: FullPipelineRequest):
    """Run full UGC pipeline v6: Analyze → Recipe → Script → Image → Video → Compose."""
    from video.pipeline_affiliate import run_pipeline
    
    product_name = req.product_title or "Product"
    product_image = req.product_image or ""
    recipe_name = req.recipe or ("etsy" if req.duration == 16 else "tus")
    
    try:
        result = run_pipeline(
            product_name=product_name,
            product_image=product_image,
            recipe_name=recipe_name,
            description=req.product_description or "",
            ugc_style=req.ugc_style or "holding",
        )
        
        return {
            "success": True,
            "job_id": result["run_id"],
            "final_video": result["final_path"],
            "duration_seconds": result["duration"],
            "cost_estimate": result["cost_estimate"],
            "script": result["script"],
            "scenes": len(result["video_paths"]),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")

# ─── Pipeline Logs ────────────────────────────────────────────────────

@app.get("/api/v1/logs")
async def list_pipeline_logs(limit: int = 100, status: Optional[str] = None, days: Optional[int] = None):
    """List recent pipeline jobs with full details."""
    from video.pipeline_logger import list_jobs
    jobs = list_jobs(limit=limit, status=status, days=days)
    return {"success": True, "jobs": jobs, "total": len(jobs)}

@app.get("/api/v1/logs/{job_id}")
async def get_pipeline_log(job_id: str):
    """Get full details of a specific pipeline job."""
    from video.pipeline_logger import get_job
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "job": job}

@app.get("/api/v1/logs/stats/summary")
async def pipeline_stats_summary(days: int = 7):
    """Get aggregate statistics for pipeline jobs."""
    from video.pipeline_logger import get_stats
    stats = get_stats(days=days)
    return {"success": True, "stats": stats}

# ─── Product Analysis ─────────────────────────────────────────────────

@app.post("/api/v1/product/analyze")
async def analyze_product(req: dict):
    """Analyze product using AI (Gemini/Mistral)."""
    from video.gemini_agent import analyze_product
    result = analyze_product(
        product_name=req.get("product_name", ""),
        description=req.get("description", ""),
        category=req.get("category", ""),
        target_audience=req.get("target_audience", ""),
        image_url=req.get("image_url", ""),
        image_base64=req.get("image_base64", ""),
    )
    return {"success": True, "analysis": result}

# ─── Entry Point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8111))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
