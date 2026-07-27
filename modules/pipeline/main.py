"""
Pipeline Service — Microservice
================================
Orchestrates full UGC pipeline (9 steps). 
Calls video service (8111), image service (8110), prompt-builder (8117).

Port: 8118
"""

import os
import sys
import json
import logging
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ─── Path setup ───────────────────────────────────────────────────────
_this_dir = Path(__file__).parent
_modules_dir = _this_dir.parent  # modules/
_erp_stack = _modules_dir.parent  # erp-stack/
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))
if str(_modules_dir) not in sys.path:
    sys.path.insert(0, str(_modules_dir))

# ─── Import pipeline logic from modules/video/ ──────────────────────
# (No file moves — we import from existing location)
sys.path.insert(0, str(_modules_dir / "video"))
from pipeline_affiliate import run_pipeline
from pipeline_logger import list_jobs, get_job, get_stats

# ─── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pipeline-service")

# ─── FastAPI ──────────────────────────────────────────────────────────
app = FastAPI(title="Pipeline Service", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ─── Models ───────────────────────────────────────────────────────────
class FullPipelineRequest(BaseModel):
    product_name: str = ""
    product_url: str = ""
    product_image: str = ""
    product_description: Optional[str] = None
    product_price: Optional[float] = None
    hook: str = ""
    value_proposition: str = ""
    cta: str = ""
    duration: int = 5
    aspect_ratio: str = "9:16"
    tts_lang: str = "th"
    bg_music: Optional[str] = None
    negative_prompt: Optional[str] = None
    ugc_style: str = "holding"
    recipe: Optional[str] = None
    run_tts: bool = True
    run_video_gen: bool = True
    run_compose: bool = True
    job_id: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "pipeline-service", "version": "0.1.0"}


@app.post("/api/v1/pipeline/run")
async def run_full_pipeline(req: FullPipelineRequest):
    """Run full UGC pipeline (9 steps)."""
    product_name = req.product_name or req.product_url
    product_image = req.product_image
    recipe_name = req.recipe or "tus"

    if not product_name:
        raise HTTPException(status_code=400, detail="product_name is required")
    if not product_image:
        raise HTTPException(status_code=400, detail="product_image is required")

    try:
        result = run_pipeline(
            product_name=product_name,
            product_image=product_image,
            recipe_name=recipe_name,
            voice="Aoede",
            description=req.product_description or "",
            ugc_style=req.ugc_style or "holding",
        )

        return {
            "success": True,
            "job_id": result["run_id"],
            "final_video": result["final_path"],
            "duration_seconds": result["duration"],
            "cost_estimate": result["cost_estimate"],
            "cost_breakdown": result.get("cost_breakdown", {}),
        }
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/pipeline/{job_id}/status")
async def pipeline_get_status(job_id: str):
    """Get pipeline job status."""
    try:
        job = get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        return {"success": True, "job": job}
    except Exception as e:
        logger.error(f"Status error for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/pipeline/list")
async def pipeline_list(limit: int = 20):
    """List pipeline jobs."""
    try:
        jobs = list_jobs(limit=limit)
        return {"success": True, "jobs": jobs}
    except Exception as e:
        logger.error(f"List error: {e}")
        return {"success": True, "jobs": []}


@app.get("/api/v1/logs")
async def list_pipeline_logs(limit: int = 100, status: Optional[str] = None, days: Optional[int] = None):
    """List pipeline logs."""
    try:
        jobs = list_jobs(limit=limit)
        if status:
            jobs = [j for j in jobs if j.get("status") == status]
        return {"success": True, "logs": jobs}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/v1/logs/{job_id}")
async def get_pipeline_log(job_id: str):
    """Get specific pipeline log."""
    try:
        job = get_job(job_id)
        return {"success": True, "log": job}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/v1/logs/stats/summary")
async def pipeline_stats_summary(days: int = 7):
    """Get pipeline statistics."""
    try:
        stats = get_stats(days=days)
        return {"success": True, "stats": stats}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/v1/product/analyze")
async def analyze_product(req: dict):
    """Analyze product via pipeline's analyze step."""
    from pipeline_affiliate import analyze_product
    try:
        result = analyze_product(
            product_name=req.get("product_name", ""),
            product_image=req.get("product_image"),
            description=req.get("description", ""),
            ugc_style=req.get("ugc_style", "holding"),
        )
        return {"success": True, "product_profile": result}
    except Exception as e:
        logger.error(f"Analyze error: {e}")
        return {"success": False, "error": str(e)}


# ─── Entrypoint ───────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8118))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
