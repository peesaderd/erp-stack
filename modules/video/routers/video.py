"""Video generation routes (moved from main.py, Phase B — move-only)."""
import asyncio
import logging
import random

from fastapi import APIRouter

from .deps import VideoRequest, VIDEOS_DIR, _resolve_age, validate_ugc_style

logger = logging.getLogger("video-module")

router = APIRouter(tags=["video"])

# Owner 2026-09-09 16:05: 8111 = single-process BLOCKING pipeline. Multiple concurrent
# clients (web UI + API) used to fire jobs that preempted/interleaved each other, causing
# stale/wrong-product output. Guard with a single global asyncio lock so jobs strictly run
# one-at-a-time; concurrent requests queue and wait instead of colliding.
_pipeline_lock = asyncio.Lock()


@router.post("/api/v1/video/generate")
async def generate_video(req: VideoRequest):
    """Generate AI video via Affiliate Pipeline (unified).

    All content types now route through pipeline_affiliate.
    The pipeline handles: Gemini Vision → SAM3 → Script Gen → TTS → Nano Banana → Wan 2.7 → FFmpeg
    """
    from video.pipeline_affiliate import run_pipeline

    # Build script from hook + value + cta if no explicit script provided.
    # Owner 2026-09-06: NEVER fall back to product_title as the spoken Thai script.
    # product_title is a long romanized name (e.g. "ลายกิ่งไม้ กางเกงยีนส์ขากว้าง... สไตล์อเมริกัน")
    # that Wan mispronounces. If there is no real hook/value/cta/script, leave script empty
    # so pipeline generate_script() writes a proper Thai sales line from the product profile.
    script = req.script or ""
    if not script:
        parts = [p for p in [req.hook, req.value, req.cta] if p]
        script = " ".join(parts)

    # Build scene prompts from request
    scene_prompts = []
    if req.scenes:
        scene_prompts = [s.script or s.mood for s in req.scenes]
    if not scene_prompts:
        # Default: single scene from product title
        scene_prompts = [req.product_title or "สินค้าน่าสนใจ วางบนพื้นผิวสวยงาม แสงธรรมชาติ"]

    product_image = req.product_image or req.image_url or ""

    try:
        # Owner 2026-09-09: serialize pipeline runs — one job at a time globally.
        # Holding the lock across the whole blocking run_pipeline queues concurrent
        # /api/v1/video/generate requests so they never interleave.
        async with _pipeline_lock:
            result = run_pipeline(
                product_name=req.product_name or req.product_title or (script[:60] if script else "สินค้า"),
                product_image=product_image if product_image else None,
                product_images=req.product_images or [],
                recipe_name=req.recipe or "tus",
                voice=req.voice or "Aoede",
                bgm_style=req.bgm_style or random.choices(
                    ["chill_loft", "luxury_jazz", "upbeat_pop", "energetic_edm", "informative_jazz", "asmr", "relaxing"],
                    weights=[15, 15, 20, 12, 12, 4, 22], k=1
                )[0],
                description=req.product_description or "",
                gender=(req.target_gender or req.gender or "female"),
                age=_resolve_age(req.target_age or req.age or ""),
                ugc_style=validate_ugc_style(req.ugc_style),
                external_job_id=req.job_id,
                duration=req.duration,
                features=req.features or "",
                # SSOT deep-analysis fields
                body_part=req.body_part or "",
                special_target=req.special_target or "",
                usage_howto=req.usage_howto or "",
                ingredient_highlight=req.ingredient_highlight or "",
                category=req.category or "",
                subcategory=req.subcategory or "",
                image_prompt=req.image_prompt or "",
                video_prompt=req.video_prompt or "",
                video_prompts=req.video_prompts or [],
                negative_prompt=req.negative_prompt or "",
                script=script or "",
                first_frame=req.first_frame or "",
                reference_image=req.reference_image or "",
                last_frame=req.last_frame or "",
                thai_script=req.thai_script or "",
                use_tus_voice=req.use_tus_voice,
                prompt_extend=req.prompt_extend,
                audio_path=req.audio or "",
            )
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        return {"success": False, "error": str(e)}


@router.post("/api/v1/video/resume/{job_id}")
async def resume_video(job_id: str):
    """Resume a FAILED pipeline job WITHOUT regenerating the still image.

    owner 2026-09-14: Prodia Wan 2.7 flakily fails; the still + prompts are already paid
    for. This re-runs ONLY the video + compose steps against the SAME still image, so no
    image credit is wasted. Reads image path / prompts / script from pipeline_logs.db.
    """
    from video.pipeline_affiliate import resume_pipeline

    try:
        async with _pipeline_lock:
            result = resume_pipeline(job_id)
        return {"success": True, "resumed_from": job_id, "result": result}
    except Exception as e:
        logger.error(f"Resume error ({job_id}): {e}")
        return {"success": False, "job_id": job_id, "error": str(e)}


@router.get("/api/v1/videos/gallery")
async def video_gallery():
    """List generated videos from storage."""
    files = []
    for f in sorted(VIDEOS_DIR.glob("**/*.*"))[:50]:
        if f.suffix.lower() in (".mp4", ".webm", ".mov"):
            files.append({"name": f.name, "size": f.stat().st_size, "path": f"/static/videos/{f.name}"})
    return {"success": True, "videos": files}
