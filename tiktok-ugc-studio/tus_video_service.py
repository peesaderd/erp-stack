"""
TikTok UGC Studio — AI Video Generation Service
================================================
Micro-service for video generation, script & TTS generation.
แยกออกจาก TUS main.py เพื่อให้ maintainable และ scale ได้

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
_this_dir = Path(__file__).parent
sys.path.insert(0, str(_this_dir))

# ─── Storage ──────────────────────────────────────────────────────────
STORAGE_DIR = _this_dir.parent / "storage"
TTS_DIR = STORAGE_DIR / "tts"
VIDEOS_DIR = STORAGE_DIR / "videos"
COMPOSED_DIR = STORAGE_DIR / "composed"
for d in [TTS_DIR, VIDEOS_DIR, COMPOSED_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tus-video")

# ─── FastAPI App ──────────────────────────────────────────────────────
app = FastAPI(
    title="TUS Video Service",
    version="0.1.0",
    description="AI UGC Video Generation — Script, TTS, Video Gen, Compose",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    duration: str = "8s"
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
    duration: int = 8
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
    duration: int = 8
    scenes: list[SceneBlock] = []
    prompt: str = ""
    provider: str = "prodia"
    model_tier: str = "standard"
    image_url: Optional[str] = None
    script: Optional[str] = None
    negative_prompt: Optional[str] = None

class FullPipelineRequest(BaseModel):
    product_title: str = ""
    product_description: str = ""
    product_url: str = ""
    product_image: str = ""
    product_price: Optional[float] = None
    hook: str = ""
    value_proposition: str = ""
    cta: str = ""
    duration: int = 8
    aspect_ratio: str = "9:16"
    tts_lang: str = "th"
    bg_music: Optional[str] = None
    negative_prompt: Optional[str] = None
    run_tts: bool = True
    run_video_gen: bool = True
    run_compose: bool = True

class VideoTaskRequest(BaseModel):
    provider: str
    task_id: str

class QueueVideoRequest(BaseModel):
    prompt: str
    provider: str = "prodia"
    model_tier: str = "standard"
    duration: int = 8
    aspect_ratio: str = "9:16"
    image_url: Optional[str] = None
    face_image_url: Optional[str] = None
    webhook_url: Optional[str] = None

class TaskStatusRequest(BaseModel):
    task_id: str

class AffiliateScriptRequest(ScriptRequest):
    platforms: list[str] = []

class VideoQueueRequest(BaseModel):
    prompt: str
    provider: str = "prodia"
    duration: int = 8
    aspect_ratio: str = "9:16"
    image_url: Optional[str] = None

class GenerateWithFallbackRequest(BaseModel):
    prompt: str
    image_url: Optional[str] = None
    duration: int = 8
    aspect_ratio: str = "9:16"

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
    return {"status": "ok", "service": "tus-video"}

# ─── Script Generation Endpoints ───────────────────────────────────────

@app.post("/scripts/generate")
async def generate_script(req: ScriptRequest):
    """Generate TikTok UGC review script using AI."""
    from script_gen import generate_tiktok_review_script
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

@app.post("/scripts/ugc")
async def generate_ugc_script(req: UGCRequest):
    """Generate UGC-style script for a product."""
    from script_gen import generate_ugc_script
    result = generate_ugc_script(
        style=req.style,
        product_name=req.product_name,
        product_desc=req.product_desc,
        gender=req.gender,
        age=req.age,
        scene=req.scene,
    )
    return {"success": True, "script": result, "style": req.style}

@app.get("/scripts/variations")
async def get_script_variations():
    """List available script variation templates."""
    from script_gen import get_script_variations
    return {"success": True, "variations": get_script_variations()}

@app.get("/scripts/templates")
async def list_script_templates():
    """List all available script templates."""
    from script_gen import SCRIPT_TEMPLATES
    return {"success": True, "templates": SCRIPT_TEMPLATES}

@app.post("/scripts/generate-with-affiliate")
async def generate_affiliate_script(req: AffiliateScriptRequest):
    """Generate script with affiliate links for platforms."""
    from script_gen import generate_tiktok_review_script
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

@app.get("/affiliate/config")
async def get_affiliate_config():
    """Get current affiliate link configuration."""
    return {"success": True, "config": {}}

# ─── TTS Endpoints ────────────────────────────────────────────────────

@app.post("/tts/generate")
async def generate_tts(req: dict):
    """Generate TTS audio from text."""
    from tts_gen import text_to_speech
    text = req.get("text", "")
    lang = req.get("lang", "th")
    if not text:
        return {"success": False, "error": "No text provided"}
    filepath = text_to_speech(text=text, lang=lang)
    return {"success": True, "filepath": filepath}

@app.post("/tts/script")
async def generate_script_tts(req: dict):
    """Generate TTS from a full script (hook + value + cta)."""
    from tts_gen import script_to_speech
    result = script_to_speech(req.get("script", {}))
    return result

# ─── Video Generation Endpoints ───────────────────────────────────────

@app.post("/video/generate")
async def generate_video(req: VideoRequest):
    """Generate AI video from product data. Routes to pipeline provider."""
    if req.provider == "prodia":
        from pipeline_default import run_pipeline
        result = await run_pipeline(
            product_title=req.product_title,
            product_image=req.product_image or req.image_url or "",
            hook=req.hook,
            value=req.value,
            cta=req.cta,
            duration=req.duration,
            aspect_ratio=req.aspect_ratio,
        )
    elif req.content_type == "affiliate":
        from pipeline_affiliate import run_pipeline as affiliate_run
        result = await affiliate_run(
            product_title=req.product_title,
            product_image=req.product_image or req.image_url or "",
            hook=req.hook,
            value=req.value,
            cta=req.cta,
            duration=req.duration,
        )
    elif req.content_type == "cartoon":
        from pipeline_cartoon import run_pipeline as cartoon_run
        result = await cartoon_run(
            product_title=req.product_title,
            product_image=req.product_image or req.image_url or "",
            hook=req.hook,
            value=req.value,
            cta=req.cta,
            duration=req.duration,
        )
    else:
        from video_gen import generate_video as gen_video
        result = await gen_video(
            prompt=req.prompt or req.product_title,
            image_url=req.image_url or req.product_image,
            duration=req.duration,
            aspect_ratio=req.aspect_ratio,
            provider=req.provider,
        )
    return {"success": True, "result": result}

@app.get("/video/status/{job_id}")
async def video_status(job_id: str):
    """Check video generation status for a job."""
    from video_gen import check_status
    status = check_status(job_id)
    job = _get_job(job_id)
    return {"success": True, "job_id": job_id, "status": status, "pipeline": job}

@app.post("/video/status")
async def video_status_bulk(req: VideoTaskRequest):
    """Check status for a specific provider task."""
    from video_gen import check_status
    status = check_status(req.task_id)
    return {"success": True, "provider": req.provider, "task_id": req.task_id, "status": status}

@app.get("/video/providers")
async def list_video_providers():
    """List available video generation providers with config."""
    from video_gen import get_available_providers, UGC_PRESETS
    return {
        "success": True,
        "providers": get_available_providers(),
        "presets": UGC_PRESETS,
    }

@app.post("/video/queue")
async def enqueue_video(req: QueueVideoRequest):
    """Enqueue a video generation task."""
    from video_gen import enqueue_video_task
    task_id = enqueue_video_task(
        prompt=req.prompt,
        provider=req.provider,
        model_tier=req.model_tier,
        duration=req.duration,
        aspect_ratio=req.aspect_ratio,
        image_url=req.image_url,
        face_image_url=req.face_image_url,
    )
    return {"success": True, "task_id": task_id}

@app.post("/video/queue-status")
async def queue_status(req: VideoTaskRequest):
    """Check queue task status."""
    from video_gen import get_task_status
    status = get_task_status(req.task_id)
    return {"success": True, "task_id": req.task_id, "status": status}

@app.post("/video/concat")
async def concat_videos(req: ConcatRequest):
    """Concatenate multiple video clips."""
    from composer import compose_video
    results = []
    for i, url in enumerate(req.video_urls):
        output = str(COMPOSED_DIR / f"concat_{i}_{uuid.uuid4().hex[:4]}.mp4")
        result = compose_video(video_path=url, audio_path="", output_path=output)
        results.append(result)
    return {"success": True, "results": results}

@app.post("/video/generate-with-fallback")
async def generate_with_fallback(req: GenerateWithFallbackRequest):
    """Generate video with automatic provider fallback."""
    from video_gen import generate_video_with_fallback, build_video_prompt
    prompt = build_video_prompt(req.prompt) if not req.prompt else req.prompt
    result = await generate_video_with_fallback(
        prompt=prompt,
        image_url=req.image_url or "",
        duration=req.duration,
        aspect_ratio=req.aspect_ratio,
    )
    return {"success": True, "result": result}

@app.get("/videos/gallery")
async def video_gallery():
    """List generated videos from storage."""
    files = []
    for f in sorted(VIDEOS_DIR.glob("**/*.*"))[:50]:
        if f.suffix.lower() in (".mp4", ".webm", ".mov"):
            files.append({"name": f.name, "size": f.stat().st_size, "path": f"/static/videos/{f.name}"})
    return {"success": True, "videos": files}

# ─── Pipeline Endpoints ───────────────────────────────────────────────

@app.get("/pipeline/{job_id}/status")
async def pipeline_get_status(job_id: str):
    """Get pipeline job status."""
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "job": job}

@app.get("/pipeline/list")
async def pipeline_list(limit: int = 20):
    """List recent pipeline jobs."""
    jobs = sorted(_pipeline_jobs.values(), key=lambda j: j.get("created_at", ""), reverse=True)[:limit]
    return {"success": True, "jobs": jobs, "total": len(_pipeline_jobs)}

@app.post("/pipeline/run")
async def run_full_pipeline(req: FullPipelineRequest):
    """Run the full UGC pipeline: TTS → video gen → compose."""
    import tempfile
    from tts_gen import text_to_speech
    from composer import compose_video

    FAL_AVAILABLE = bool(os.environ.get("FAL_API_KEY") or os.environ.get("FAL_KEY"))
    job_id = _create_job(account_id="", product_url=req.product_url or "")

    try:
        # Step 1: TTS
        if req.run_tts:
            _update_step(job_id, "tts", "processing")
            full_text = " ".join(filter(None, [req.hook, req.value_proposition, req.cta]))
            if not full_text.strip():
                full_text = req.product_title or req.product_description or ""
            if full_text.strip():
                try:
                    tts_file = text_to_speech(text=full_text.strip(), lang=req.tts_lang or "th")
                    _update_step(job_id, "tts", "success", {"filepath": tts_file})
                except Exception as e:
                    _update_step(job_id, "tts", "error", {"error": str(e)})
                    raise
            else:
                _update_step(job_id, "tts", "skipped")

        # Step 2: Video Gen
        if req.run_video_gen:
            _update_step(job_id, "video_gen", "processing")
            video_path = None
            if FAL_AVAILABLE and req.product_image:
                try:
                    from fal_client import generate_video_async
                    image_source = req.product_image
                    if image_source.startswith("data:") or image_source.startswith("file://"):
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
                        _update_step(job_id, "video_gen", "success", {"video_url": video_path})
                    else:
                        _update_step(job_id, "video_gen", "error", {"error": video_result.get("error", "Failed")})
                except Exception as e:
                    logger.exception(f"Video gen failed: {e}")
                    _update_step(job_id, "video_gen", "error", {"error": str(e)})
            else:
                _update_step(job_id, "video_gen", "skipped")

        # Step 3: Compose
        if req.run_compose and req.run_tts and video_path:
            _update_step(job_id, "compose", "processing")
            try:
                tts_step = _get_job(job_id).get("steps", {}).get("tts", {})
                tts_path = tts_step.get("result", {}).get("filepath", "")
                if tts_path and os.path.exists(tts_path):
                    output_path = str(COMPOSED_DIR / f"composed_{job_id}.mp4")
                    composed = compose_video(video_path=video_path, audio_path=tts_path, output_path=output_path)
                    _update_step(job_id, "compose", "success", {"output_path": output_path})
                else:
                    _update_step(job_id, "compose", "skipped")
            except Exception as e:
                logger.exception(f"Compose failed: {e}")
                _update_step(job_id, "compose", "error", {"error": str(e)})

        _update_step(job_id, "pipeline", "success")
        return {"success": True, "job_id": job_id, "status": "completed"}
    except Exception as e:
        logger.error(f"Pipeline {job_id} failed: {e}")
        _update_step(job_id, "pipeline", "error", {"error": str(e)})
        return {"success": False, "job_id": job_id, "status": "error", "error": str(e)}

# ─── Product Analysis (proxy to gemini_agent) ─────────────────────────

@app.post("/product/analyze")
async def analyze_product(req: dict):
    """Analyze product using AI (Gemini/Mistral)."""
    from gemini_agent import analyze_product
    result = analyze_product(
        product_name=req.get("product_name", ""),
        description=req.get("description", ""),
        category=req.get("category", ""),
        target_audience=req.get("target_audience", ""),
        image_url=req.get("image_url", ""),
        image_base64=req.get("image_base64", ""),
    )
    return {"success": True, "analysis": result}

# ─── Startup ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8111))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
