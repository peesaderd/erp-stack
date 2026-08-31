


"""Pipeline routes — health, TTS, pipeline status/run, scripts."""
import json
import logging
import os
import sqlite3
import asyncio
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from models import (
    ScriptRequest, UGCRequest, TTSRequest, ScriptTTSRequest,
    FullPipelineRequest,
)
from pipeline_db import (
    create_job as _create_pipeline_job,
    update_step as _update_pipeline_step,
    get_job as _get_pipeline_job,
    list_jobs as _list_pipeline_jobs,
    enrich_from_logs as _enrich_job_from_logs_db,
    _path_to_web_url,
)
from config import DEFAULT_VIDEO_DURATION
from connect.aitoearn_client import client as aitoearn

from .deps import logger, PIPELINE_DB_PATH, LOGS_DB_PATH, _proxy, _pipeline_results, IMAGES_DIR, VIDEOS_DIR
from recipes import list_recipes, get_recipe


def _resolve_video_recipe(recipe_name: str | None) -> str:
    """Map Web UI recipe catalog name → Schema Engine video_recipe name.

    Web UI sends recipe.name (e.g. 'tus_review'), but Schema Engine seeds
    actual recipe rows as e.g. 'tus_review_15s'. Each catalog entry optionally
    declares its target via 'recipe_name'. Falls back to 'tus' (voiceover)."""
    if not recipe_name:
        return "tus"
    # Direct hit on a recipe_name we know exists in Schema Engine
    if recipe_name in ("tus", "tus_15s", "tus_novoice", "tus_novoice_15s", "tus_review_15s"):
        return recipe_name
    # Look up catalog entry → its declared recipe_name
    rec = get_recipe(recipe_name)
    declared = (rec or {}).get("recipe_name")
    return declared or recipe_name

router = APIRouter(tags=["pipeline"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "tiktok-ugc-studio", "version": "0.2.0"}


@router.post("/tts/generate")
async def generate_tts(req: TTSRequest):
    """Generate TTS audio from text using Gemini via video module."""
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    result = await _proxy("POST", "video", "/api/v1/tts/generate", {
        "text": req.text.strip(),
        "voice": "Aoede"
    })
    if result.get("success"):
        filepath = result.get("filepath", "")
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


@router.post("/tts/script")
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
    if result.get("success"):
        result["success"] = True
        return result
    else:
        raise HTTPException(status_code=502, detail=result.get("error", "Script TTS failed"))


@router.get("/pipeline/{job_id}/status")
def pipeline_status(job_id: str):
    job = _get_pipeline_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"success": True, "job": job}


@router.get("/pipeline/list")
def pipeline_list(limit: int = 20):
    conn = sqlite3.connect(PIPELINE_DB_PATH)
    rows = conn.execute(
        "SELECT job_id, account_id, status, product_url, created_at, updated_at, steps_data FROM pipeline_jobs ORDER BY REPLACE(created_at, ' ', 'T') DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    jobs = []
    for r in rows:
        job = {"job_id": r[0], "account_id": r[1], "status": r[2], "product_url": r[3], "created_at": r[4], "updated_at": r[5], "steps_data": r[6] if len(r) > 6 else "{}", "product_image": "", "generated_image": "", "product_title": ""}
        # Try to enrich with images + title from pipeline_logs.db
        try:
            lconn = sqlite3.connect(str(LOGS_DB_PATH))
            lrow = lconn.execute("SELECT product_image_path, generated_image_path, product_title, final_video_path, raw_video_path, recipe_name, ugc_style FROM pipeline_jobs WHERE job_id = ?", (r[0],)).fetchone()
            lconn.close()
            if lrow:
                job["product_image"] = _path_to_web_url(lrow[0]) if lrow[0] else ""
                job["generated_image"] = _path_to_web_url(lrow[1]) if lrow[1] else ""
                job["product_title"] = lrow[2] or ""
                # Expose raw (true Prodia) + final video on the job card + detail
                job["raw_video_path"] = lrow[4] or ""
                job["raw_video_web_url"] = _path_to_web_url(lrow[4]) if lrow[4] else ""
                job["final_video_path"] = lrow[3] or ""
                job["final_video_web_url"] = _path_to_web_url(lrow[3]) if lrow[3] else ""
                # Expose Recipe & UGC style on the job card so the UI can show what
                # recipe/ugc_style each job actually ran with (owner 2026-08-30).
                job["recipe"] = lrow[5] if len(lrow) > 5 and lrow[5] else ""
                job["ugc_style"] = lrow[6] if len(lrow) > 6 and lrow[6] else ""
        except Exception:
            pass
        jobs.append(job)
    return {"success": True, "jobs": jobs}


# Example: old monolith endpoint /pipeline/run now proxies to video service
@router.post("/pipeline/run")
async def run_full_pipeline(req: FullPipelineRequest):
    """Run the full UGC pipeline: script → TTS → video gen → compose."""
    job_id = _create_pipeline_job(account_id="", product_url=req.product_url or "")

    try:
        # Voice mode A (use_tus_voice=True, Wan พูด Thai script) = ค่าเริ่มต้น → ข้าม run_tts
        # (กัน Gemini TTS ถูกสร้างซ้ำซ้อนที่ proxy เสียเปล่า; เสียงใช้ Wan เองowner-12:22)
        _mode_a = bool(getattr(req, "use_tus_voice", True))
        if req.run_tts and not _mode_a:
            _update_pipeline_step(job_id, "tts", "processing")
            full_text = " ".join(filter(None, [req.hook, req.value_proposition, req.cta]))
            if not full_text.strip():
                full_text = req.product_title or req.product_description or ""

            if full_text.strip():
                tts_result = await _proxy("POST", "video", "/api/v1/tts/generate", {
                    "text": full_text.strip(),
                    "lang": req.tts_lang or "th",
                })
                if tts_result.get("success"):
                    tts_file = tts_result.get("filepath") or tts_result.get("audio_path", "")
                    _update_pipeline_step(job_id, "tts", "success", {"filepath": tts_file})
                else:
                    raise Exception(tts_result.get("error", "TTS proxy call failed"))
            else:
                _update_pipeline_step(job_id, "tts", "skipped")

        if req.run_video_gen:
            _update_pipeline_step(job_id, "video_gen", "processing")
            if req.product_image:
                vid_result = await _proxy("POST", "video-gen", "/api/v1/video/generate", {
                    "product_title": req.product_title or "",
                    "product_description": req.product_description or "",
                    "product_image": req.product_image,
                    "hook": req.hook or "",
                    "value": req.value_proposition or "",
                    "cta": req.cta or "",
                    "duration": req.duration or DEFAULT_VIDEO_DURATION,
                    "ugc_style": req.ugc_style or "holding",
                    "category": req.category or "",
                    "subcategory": req.subcategory or "",
                    "recipe": _resolve_video_recipe(req.recipe),
                    "negative_prompt": req.negative_prompt or "",
                    "first_frame": req.first_frame or "",
                    "reference_image": req.reference_image or "",
                    "last_frame": req.last_frame or "",
                    "thai_script": req.thai_script or "",
                    "use_tus_voice": req.use_tus_voice,
                    "audio": req.audio or "",
                    # SSOT deep-analysis fields
                    "body_part": req.body_part or "",
                    "special_target": req.special_target or "",
                    "usage_howto": req.usage_howto or "",
                    "ingredient_highlight": req.ingredient_highlight or "",
                }, timeout=300.0)
                if vid_result.get("success"):
                    result_data = vid_result.get("result", {})
                    final_path = result_data.get("final_path", "")
                    _update_pipeline_step(job_id, "video_gen", "success", {
                        "video_url": final_path,
                        "duration": req.duration,
                        "run_id": result_data.get("run_id", ""),
                    })
                else:
                    _update_pipeline_step(job_id, "video_gen", "error", {"error": vid_result.get("error", "Proxy failed")})
            else:
                _update_pipeline_step(job_id, "video_gen", "skipped", {"message": "No product image"})

        _update_pipeline_step(job_id, "pipeline", "success")

        # Auto-enqueue for posting
        job = _get_pipeline_job(job_id)
        job = _enrich_job_from_logs_db(job)
        final_video = job.get("logs", {}).get("final_video_path", "")
        if final_video:
            try:
                # Build rich metadata
                product_name = job.get("logs", {}).get("product_name", "") or ""
                ugc_style = job.get("logs", {}).get("ugc_style", "") or ""
                script_text = job.get("logs", {}).get("script", "") or ""
                hook_text = job.get("logs", {}).get("script_hook", "") or ""
                htags = job.get("logs", {}).get("hashtags", [])
                if isinstance(htags, str):
                    try:
                        htags = json.loads(htags)
                    except Exception:
                        htags = [t.strip("# ") for t in htags.split(",")] if htags else []

                title = f"{product_name} | {ugc_style}" if product_name and ugc_style else product_name
                description = (hook_text or script_text)[:500] or product_name
                caption = (script_text or product_name)[:200]

                from publisher import enqueue as pq_enqueue
                pq_enqueue(
                    job_id=job_id,
                    video_path=final_video,
                    title=title,
                    description=description,
                    caption=caption,
                    hashtags=htags,
                    affiliate_link="",
                )
                logger.info(f"Auto-enqueued {job_id} for posting — title: {title[:50]}")
            except Exception as e:
                logger.warning(f"Auto-enqueue failed: {e}")

        # Sync with AitoEarn (fire-and-forget)
        asyncio.create_task(aitoearn.sync_with_pipeline(job))

        return {"success": True, "job_id": job_id, "status": "completed"}
    except Exception as e:
        import traceback
        logger.error(f"Pipeline {job_id} failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        _update_pipeline_step(job_id, "pipeline", "error", {"error": str(e)})
        return {"success": False, "job_id": job_id, "status": "error", "error": str(e)}


# ─── Script Generation ─────────────────────────────────────────────────────

@router.post("/scripts/generate")
async def generate_script(req: ScriptRequest):
    """Generate TikTok review script via Video Module"""
    try:
        result = await _proxy("POST", "video", "/api/v1/scripts/generate", req.model_dump())
        if result.get("success"):
            return result.get("data", {})
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scripts/ugc")
async def generate_ugc_script(req: UGCRequest):
    """Generate UGC video prompt via Video Module"""
    try:
        result = await _proxy("POST", "video", "/api/v1/scripts/ugc", req.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scripts/variations")
async def script_variations():
    result = await _proxy("GET", "video", "/api/v1/scripts/variations")
    return result


@router.get("/scripts/templates")
async def script_templates():
    result = await _proxy("GET", "video", "/api/v1/scripts/templates")
    return {
        "durations": ["8s", "15s"],
        "ugc_styles": ["holding_product", "product_usage", "ugc_review"],
        "templates": result.get("templates", {}),
    }



@router.get("/pipeline/recipes")
def get_pipeline_recipes():
    """Get pipeline recipe templates from recipes.py (single source of truth)."""
    return {"recipes": list_recipes()}


# ─── Missing Endpoints (Frontend Compatibility) ──────────────────────

@router.get("/pipeline/detail/{job_id}")
async def pipeline_detail(job_id: str):
    """Get pipeline job details with enriched data from logs DB."""
    # Start with pipeline.db data (has steps, created_at, etc.)
    job = _get_pipeline_job(job_id)
    if not job:
        # Fall back to in-memory results
        result = _pipeline_results.get(job_id)
        if result:
            return {"job": _enrich_job_from_logs_db(result)}
        return {"error": "Job not found"}
    
    # Merge in-memory results if available (has video_url, metadata, etc.)
    mem = _pipeline_results.get(job_id, {})
    if mem:
        job["video_url"] = mem.get("video_url", "")
        job["cost"] = mem.get("cost", 0)
        job["metadata"] = mem.get("metadata", {})
        # Update status if in-memory differs
        if mem.get("status") in ("completed", "failed"):
            job["status"] = mem["status"]
    
    return {"job": _enrich_job_from_logs_db(job)}

@router.post("/dashboard/track-event")
async def track_event():
    """Track dashboard events (no-op for now)."""
    return {"ok": True}

@router.get("/pipeline/assets")
async def pipeline_assets():
    """List generated images + videos from storage for Asset Gallery."""
    try:
        images = []
        if IMAGES_DIR.exists():
            for f in sorted(IMAGES_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:100]:
                if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                    images.append({
                        "name": f.name,
                        "path": f"images/{f.name}",
                        "url": f"/api/tiktok/static/images/{f.name}",
                        "size": f.stat().st_size,
                        "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                    })

        videos = []
        if VIDEOS_DIR.exists():
            for f in sorted(VIDEOS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:100]:
                if f.suffix.lower() == ".mp4":
                    videos.append({
                        "name": f.name,
                        "path": f"videos/{f.name}",
                        "url": f"/api/tiktok/static/videos/{f.name}",
                        "size": f.stat().st_size,
                        "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                    })

        return {"success": True, "images": images, "videos": videos}
    except Exception as e:
        logger.error(f"pipeline/assets error: {e}")
        return {"success": False, "images": [], "videos": [], "error": str(e)}

@router.get("/posts/scheduled")
async def posts_scheduled():
    """Get scheduled posts list."""
    return {"posts": [], "count": 0}

@router.post("/pipeline/{job_id}/retry")
async def pipeline_retry(job_id: str):
    """Retry a failed pipeline job by re-triggering execution."""
    conn = sqlite3.connect(str(PIPELINE_DB_PATH))
    row = conn.execute("SELECT product_url, steps_data FROM pipeline_jobs WHERE job_id = ?", (job_id,)).fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "Job not found"}
    
    # Reset status to pending
    conn.execute("UPDATE pipeline_jobs SET status = 'pending' WHERE job_id = ?", (job_id,))
    conn.commit()
    conn.close()

    # Also update pipeline_logs.db if present
    try:
        lconn = sqlite3.connect(str(LOGS_DB_PATH))
        lconn.execute("UPDATE pipeline_jobs SET status = 'pending', error_message = NULL WHERE job_id = ?", (job_id,))
        lconn.commit()
        lconn.close()
    except Exception:
        pass

    # Trigger async execution
    import asyncio, httpx
    async def _async_trigger():
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post("http://localhost:8111/api/v1/video/generate", json={
                    "product_name": "สินค้า TikTok",
                    "product_url": row[0] or "",
                    "recipe": "tus",
                    "job_id": job_id
                })
        except Exception:
            pass
    
    asyncio.create_task(_async_trigger())
    return {"success": True, "message": "Job retry triggered"}


@router.post("/pipeline/{job_id}/cancel")
async def pipeline_cancel(job_id: str):
    """Cancel a running pipeline job."""
    return {"success": False, "error": "Not implemented yet"}
