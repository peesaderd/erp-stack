"""Video routes — full UGC pipeline generation, status, completed list.

Largest module extracted from main.py (was ~447 lines).
"""
import json
import logging
import os
import shutil
import sqlite3
import uuid
import asyncio
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from models import SceneBlock, VideoRequest
from pipeline_db import (
    create_job as _create_pipeline_job,
    update_step as _update_pipeline_step,
    enrich_from_logs as _enrich_job_from_logs_db,
)
from config import DEFAULT_VIDEO_DURATION
from connect.aitoearn_client import client as aitoearn

BASE_DIR = Path(__file__).resolve().parent.parent

from .deps import (
    logger, STORAGE_DIR, TTS_DIR, IMAGES_DIR, VIDEOS_DIR,
    PRODUCT_IMAGE_DIR, PIPELINE_DB_PATH, LOGS_DB_PATH,
    _proxy, _pipeline_results,
)

router = APIRouter(tags=["video"])


def _product_image_to_web_url(image_src: str) -> str:
    """Normalize product image refs to a URL fetchable by prompt-builder/video-gen.

    Handles all historical formats so broken-image errors are eliminated regardless
    of which format the DB/frontend currently uses.
    """
    if not image_src:
        return ""
    s = image_src.strip()
    # Already absolute URL — use as-is
    if s.startswith("http://") or s.startswith("https://"):
        return s
    # protocol-relative URL (e.g. //cdn...) → make it http
    if s.startswith("//"):
        return "http:" + s
    # Local virtual paths → resolve to the running TUS backend on this host.
    # /ugc/static/product_images/xxx is served by tiktok-ugc-studio (port 8105).
    for prefix in ("/ugc/static/product_images/", "/tiktok/storage/product_images/", "/storage/product_images/"):
        if s.startswith(prefix):
            filename = s.rsplit("/", 1)[-1]
            return f"http://localhost:8105/ugc/static/product_images/{filename}"
    # Bare filename (legacy) → same treatment
    if "/" not in s:
        return f"http://localhost:8105/ugc/static/product_images/{s}"
    return s
@router.post("/video/generate")
async def generate_video(req: VideoRequest):
    """Full UGC pipeline with scenes and metadata."""
    job_id = f"vid_{uuid.uuid4().hex[:8]}"
    # Register in Pipeline Monitor DB
    _create_pipeline_job(account_id="", product_url=req.product_url or req.product_title or "", job_id=job_id)

    # Extract product name from URL if no title given
    import urllib.parse as _ul
    _product_title = req.product_title or ""
    _product_url = req.product_url or ""
    if not _product_title and _product_url:
        try:
            _parsed = _ul.urlparse(_product_url)
            _parts = [p for p in _parsed.path.split("/") if p]
            _product_title = _ul.unquote(_parts[-1]) if _parts else ""
            _product_title = _product_title.replace("-", " ").replace("_", " ").strip()
        except Exception:
            _product_title = _product_url.split("/")[-1] or ""
        if not _product_title or len(_product_title) < 3:
            _product_title = "สินค้า"

    if req.hook and req.value and req.cta:
        script_parts = [req.hook, req.value, req.cta]
        full_script = " ".join(script_parts)
    elif req.script:
        full_script = req.script
    elif req.prompt:
        full_script = req.prompt
    elif req.ugc_style == "product_demo" and _product_title:
        # Product Demo: spec narration from Gemini Vision analysis, not review hook/value/cta
        # The product specs come from Vision analysis (features + product_appearance)
        # or fallback to raw product_description if no vision analysis yet
        desc = req.product_description or ""
        full_script = f"{_product_title}: {desc}" if desc else f"{_product_title}"
    elif _product_title:
        full_script = f"{_product_title} ตัวนี้ใช้งานดีมาก คุณภาพดี คุ้มค่าสุดๆ แนะนำเลยค่ะ กดสั่งในตะกร้าได้เลยนะคะ"
    else:
        full_script = "สินค้าตัวนี้ใช้งานดีมาก คุณภาพดี คุ้มค่าสุดๆ แนะนำเลยค่ะ กดสั่งในตะกร้าได้เลยนะคะ"

    scenes = []
    if req.scenes:
        scenes = req.scenes
    elif req.duration <= 15:  # single scene for wan2.7 (max 15s)
        if req.ugc_style == "product_demo":
            mood, snd = "clean", "none"
        else:
            mood, snd = "energetic", "upbeat_pop"
        scenes = [SceneBlock(
            script=full_script,
            duration=req.duration,
            mood=mood,
            sound_style=snd,
            style=req.ugc_style,
        )]
    else:
        scenes = [
            SceneBlock(
                script=f"{req.hook or ''} Let me show you this!" if req.hook else f"Check out {_product_title}!",
                duration=req.duration // 2,
                mood="energetic",
                sound_style="upbeat_pop",
                style="holding_product",
            ),
            SceneBlock(
                script=f"{req.value or ''} {req.cta or 'Link in bio!'}" if req.value else f"Amazing right? {req.cta or 'Link in bio! 🛍️'}",
                duration=req.duration - (req.duration // 2),
                mood="calm",
                sound_style="chill_loft",
                style="product_usage",
            ),
        ]

    async def _run():
        try:
            # Query product details (description, features, keywords, image) from tus_products.db if available
            _db_desc = req.product_description or ""
            _db_keywords = req.tags or []
            _db_category = getattr(req, "category", "") or ""
            _db_image = req.product_image or ""
            _db_gender = getattr(req, "gender", "") or ""
            _db_age = getattr(req, "age", "") or ""
            try:
                tconn = sqlite3.connect(str(BASE_DIR / "tus_products.db"))
                trow = tconn.execute(
                    "SELECT description_th, description, keywords, images, category, gender, target_age FROM tus_products WHERE title LIKE ? OR title_th LIKE ? OR product_id = ? LIMIT 1",
                    (f"%{_product_title}%", f"%{_product_title}%", req.product_url or "")
                ).fetchone()
                tconn.close()
                if trow:
                    _db_desc = trow[0] or trow[1] or _db_desc
                    _db_category = trow[4] or _db_category
                    _db_gender = trow[5] or getattr(req, "gender", "") or ""
                    _db_age = trow[6] or getattr(req, "age", "") or "" 
                    if trow[2] and not _db_keywords:
                        try:
                            _db_keywords = json.loads(trow[2])
                        except Exception:
                            pass
                    if trow[3] and not _db_image:
                        try:
                            imgs = json.loads(trow[3])
                            if isinstance(imgs, list) and imgs:
                                _db_image = imgs[0]
                            elif isinstance(trow[3], str) and trow[3].strip():
                                _db_image = trow[3]
                        except Exception:
                            _db_image = trow[3] if isinstance(trow[3], str) else ""
            except Exception as dbe:
                logger.debug(f"DB lookup exception: {dbe}")

            _update_pipeline_step(job_id, "prompt_builder", "processing")
            pb_result = await _proxy("POST", "prompt-builder", "/api/v1/build", {
                "product_name": _product_title,
                "description": _db_desc,
                "features": _db_desc,
                "keywords": _db_keywords,
                "ugc_style": req.ugc_style or "holding",
                "category": _db_category,
                "target_gender": _db_gender or "",
                "target_age": _db_age or "",
                "product_id": job_id,
                "price": float(req.product_price) if req.product_price else 0.0,
                "product_image": _product_image_to_web_url(_db_image),
                "duration": req.duration or 15,
                "target_duration": req.duration or 15,
            })

            if isinstance(pb_result, dict) and pb_result.get("image_prompt"):
                pb_data = pb_result
                
                # Product Demo: override scene script with Gemini Vision analysis
                if req.ugc_style == "product_demo" and scenes:
                    analysis = pb_data.get("analysis", {}) or {}
                    feat_raw = analysis.get("features", "")
                    feat_str = feat_raw if isinstance(feat_raw, str) else \
                        ", ".join(f.strip() for f in feat_raw if f.strip()) if isinstance(feat_raw, list) else ""
                    product_appearance = (analysis.get("product_appearance", "") or "")
                    
                    parts = [f"{_product_title}"]
                    if feat_str:
                        parts.append(feat_str)
                    elif product_appearance:
                        parts.append(product_appearance[:200])
                    elif req.product_description:
                        parts.append(req.product_description[:200])
                    scenes[0].script = ": ".join(parts)
                
                img_prompt = pb_data.get("image_prompt", "")
                video_prompts = [pb_data.get("video_prompt", "")] * len(scenes)
                neg_prompt = pb_data.get("negative_prompt", req.negative_prompt)
                _update_pipeline_step(job_id, "prompt_builder", "success", {
                    "image_prompt": (img_prompt or "")[:200],
                    "video_prompt": ((video_prompts or [""])[0] or "")[:200],
                    "negative_prompt": (neg_prompt or "")[:200],
                })
            else:
                _update_pipeline_step(job_id, "prompt_builder", "error", {"error": f"Prompt builder failed: {pb_result}"})
                raise HTTPException(status_code=500, detail=f"Prompt Builder Service Failed: {pb_result}")

            selected_sound_style = scenes[0].sound_style if scenes else "upbeat_pop"

            prod_img_src = req.product_image or _db_image
            # Normalize to a URL fetchable by prompt-builder / video-gen (all formats)
            product_img_local = _product_image_to_web_url(prod_img_src) if prod_img_src else None

            _update_pipeline_step(job_id, "video_generation", "processing")
            affiliate_result = await _proxy("POST", "video", "/api/v1/video/generate", {
                "product_title": req.product_title or "",
                "product_name": _product_title or req.product_title or "สินค้า",
                "product_image": product_img_local or "",
                "product_price": req.product_price,
                "product_commission": req.product_commission,
                "hook": req.hook or "",
                "value": req.value or "",
                "cta": req.cta or "",
                "duration": req.duration or (scenes[0].duration if scenes else DEFAULT_VIDEO_DURATION),
                "scenes": [s.dict() for s in scenes] if scenes else [],
                "tags": req.tags or [],
                "content_type": req.content_type or "affiliate",
                "ugc_style": req.ugc_style or "holding",
                "aspect_ratio": req.aspect_ratio or "9:16",
                "negative_prompt": neg_prompt or req.negative_prompt,
                "bgm_style": req.bgm_style or "",
                "image_prompt": img_prompt or "",
                "video_prompt": (video_prompts or [""])[0],
                "video_prompts": video_prompts or [],
                "job_id": job_id,
                "script": pb_data.get("scripts", {}).get("tts_script") or pb_data.get("full_script") or full_script or "",
                "voice": getattr(req, "voice", None) or "",
            }, timeout=300.0)  # Video pipeline takes 90-180s

            if isinstance(affiliate_result, dict) and (affiliate_result.get("success") or affiliate_result.get("ok")):
                result = affiliate_result.get("result") or affiliate_result.get("data", {}).get("result", {})
                _update_pipeline_step(job_id, "video_generation", "success", {"output": str(result.get("final_path", ""))[:100]})
            else:
                _update_pipeline_step(job_id, "video_generation", "error", {"error": affiliate_result.get("error", "Pipeline affiliate run failed")})
                raise Exception(affiliate_result.get("error", "Pipeline affiliate run failed"))
            VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
            final_path = result.get("final_path", "")

            import shutil
            final_video_path = VIDEOS_DIR / f"final_{job_id}.mp4"
            shutil.copy2(final_path, final_video_path)

            # ── Generated image URL — copy to permanent gallery storage ──
            img_src = result.get("perm_image_path", "") or result.get("image_path", "")
            image_url = ""
            if img_src and os.path.exists(img_src):
                perm_name = f"gen_{job_id}_{Path(img_src).name}"
                perm_path = IMAGES_DIR / perm_name
                shutil.copy2(img_src, perm_path)
                image_url = f"/api/tiktok/static/images/{perm_name}"

            # Store final rich result
            video_web_url = f"/api/tiktok/static/videos/final_{job_id}.mp4"
            
            _update_pipeline_step(job_id, "result", "success", {
                "product_name": (req.product_title or "")[:100],
                "product_price": req.product_price,
                "product_image": _product_image_to_web_url(req.product_image or ""),
                "script_hook": (req.hook or "")[:200],
                "script_value": (req.value or "")[:200],
                "script_cta": (req.cta or "")[:200],
                "image_prompt": (img_prompt or "")[:300],
                "video_prompt": ((video_prompts or [""])[0] or "")[:300],
                "negative_prompt": (neg_prompt or "")[:200],
                "tags": (", ".join(req.tags or []))[:200],
                "hashtags": json.dumps(result.get("hashtags", [])),
                "video_url": video_web_url,
                "video_path": str(final_path),
                "image_url": image_url,
                "cost_estimate": result.get("cost_estimate", 0),
                "duration": req.duration,
                "ugc_style": req.ugc_style or "",
                "aspect_ratio": req.aspect_ratio or "9:16",
            })

            _pipeline_results[job_id] = {
                "status": "completed",
                "video_url": f"/api/tiktok/static/videos/final_{job_id}.mp4",
                "cost": result.get("cost_estimate", 0),
                "metadata": {
                    "product_name": req.product_title or "",
                    "product_url": req.product_url or "",
                    "product_image": _product_image_to_web_url(req.product_image or ""),
                    "product_price": req.product_price,
                    "product_commission": req.product_commission,
                    "tags": req.tags,
                    "hashtags": result.get("hashtags", []),
                    "hook": req.hook,
                    "value": req.value,
                    "cta": req.cta,
                    "content_type": req.content_type,
                    "ugc_style": req.ugc_style,
                    "duration": req.duration,
                    "aspect_ratio": req.aspect_ratio or "9:16",
                    "image_prompt": img_prompt or "",
                    "video_prompts": video_prompts or [],
                    "negative_prompt": neg_prompt or "",
                    "image_url": image_url,
                },
                "job_id": job_id,
            }
        except Exception as e:
            logger.exception(f"Pipeline {job_id} failed")
            _update_pipeline_step(job_id, "video_generation", "error", {"error": str(e)})
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
            "product": _product_title,
            "style": req.ugc_style,
            "content_type": req.content_type,
            "scenes": len(scenes),
            "tags": req.tags,
        },
    }

@router.get("/video/status/{job_id}")
def video_pipeline_status(job_id: str):
    result = _pipeline_results.get(job_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return result

@router.post("/video/status/{task_id}")
async def video_status(task_id: str):
    result = await _proxy("GET", "video", f"/api/v1/video/status/{task_id}")
    return result

@router.get("/video/completed")
def list_completed_videos():
    """List completed videos — from in-memory pipeline results + filesystem scan.
    
    Survives PM2 restarts by scanning storage/videos/*.mp4 + pipeline.db.
    """
    seen = set()
    jobs = []

    # 1) In-memory pipeline results (fast path, survives during uptime)
    for job_id, result in _pipeline_results.items():
        if result.get("status") == "completed":
            meta = result.get("metadata", {})
            video_url = result.get("video_url", "")
            seen.add(job_id)
            htags = meta.get("hashtags", [])
            if isinstance(htags, str):
                try:
                    htags = json.loads(htags)
                except Exception:
                    htags = [t.strip("# ") for t in htags.split(",")] if htags else []
            product_name = meta.get("product_name", "") or ""
            style_label = meta.get("ugc_style", "") or ""
            # Build title and description
            title = f"{product_name} | {style_label}" if product_name and style_label else (product_name or f"Video {job_id[:8]}")
            description = (meta.get("hook", "") or "")[:500]
            script_val = (meta.get("script_value", "") or meta.get("value", "") or "")[:300]
            if script_val:
                description = f"{description}\n\n{script_val}"
            jobs.append({
                "job_id": job_id,
                "video_url": video_url,
                "cost": result.get("cost", 0),
                "product_name": product_name,
                "title": title,
                "description": description.strip()[:800],
                "hashtags": htags,
                "duration": meta.get("duration", DEFAULT_VIDEO_DURATION),
                "style": meta.get("ugc_style", ""),
            })

    # 2) Filesystem scan — find videos stored on disk (survives PM2 restart)
    mp4_files = sorted(VIDEOS_DIR.glob("final_*.mp4"), key=lambda p: p.stat().st_mtime, reverse=True)
    for mp4 in mp4_files:
        job_id = mp4.stem.replace("final_", "")  # final_vid_049e078c → vid_049e078c
        if job_id in seen:
            continue
        seen.add(job_id)
        size_mb = mp4.stat().st_size / (1024 * 1024)
        mtime = datetime.fromtimestamp(mp4.stat().st_mtime).strftime("%Y-%m-%d")
        pname = mp4.stem.replace("final_vid_", "Video ").replace("final_", "")
        jobs.append({
            "job_id": job_id,
            "video_url": f"/api/tiktok/static/videos/{mp4.name}",
            "cost": 0,
            "product_name": pname,
            "title": pname,
            "description": "",
            "hashtags": [],
            "duration": 8,
            "style": "ugc",
            "size_mb": round(size_mb, 1),
            "created": mtime,
        })

    # 3) Enrich from logs DB (has product_title, duration, ugc_style, cost, hashtags, script)
    if os.path.exists(str(LOGS_DB_PATH)):
        try:
            conn = sqlite3.connect(str(LOGS_DB_PATH))
            conn.row_factory = sqlite3.Row
            for j in jobs:
                row = conn.execute(
                    "SELECT product_title, product_description, ugc_style, total_duration_seconds, cost_total, hashtags, script, timestamp FROM pipeline_jobs WHERE job_id = ?",
                    (j["job_id"],)
                ).fetchone()
                if row:
                    if row["product_title"]:
                        j["product_name"] = row["product_title"]
                    if row["ugc_style"]:
                        j["style"] = row["ugc_style"]
                    if row["total_duration_seconds"]:
                        j["duration"] = int(row["total_duration_seconds"])
                    if row["cost_total"] is not None:
                        j["cost"] = round(row["cost_total"], 4)
                    if row["timestamp"]:
                        j["created"] = row["timestamp"]
                    # Enrich hashtags
                    if row["hashtags"]:
                        try:
                            htags = json.loads(row["hashtags"])
                            if isinstance(htags, list) and htags:
                                j["hashtags"] = htags
                        except Exception:
                            pass
                    # Enrich description from script (first 500 chars)
                    if row["script"] and not j.get("description"):
                        j["description"] = row["script"][:500]
                    # Enrich from product_description (overrides script) 
                    if row["product_description"]:
                        j["description"] = row["product_description"][:800]
                    # Build better title
                    pn = j.get("product_name", "")
                    st = j.get("style", "")
                    # Override generic filesystem-generated titles with DB enrichment
                    if pn and st:
                        j["title"] = f"{pn} | {st}"
            conn.close()
        except Exception as e:
            logger.warning(f"Logs DB enrich: {e}")

    # 4) Fallback enrich from pipeline.db (only for jobs still showing auto-generated names)
    if os.path.exists(PIPELINE_DB_PATH):
        try:
            conn = sqlite3.connect(PIPELINE_DB_PATH)
            conn.row_factory = sqlite3.Row
            for j in jobs:
                pn = j.get("product_name", "")
                # Skip if already enriched from logs DB (real product name, not URL/auto)
                if pn and not pn.startswith("Video ") and not pn.startswith("final_") and not pn.startswith("http"):
                    continue
                row = conn.execute(
                    "SELECT product_url, created_at FROM pipeline_jobs WHERE job_id = ?",
                    (j["job_id"],)
                ).fetchone()
                if row:
                    if row["product_url"]:
                        j["product_name"] = row["product_url"][:60]
                    if row["created_at"] and not j.get("created"):
                        j["created"] = row["created_at"]
            conn.close()
        except Exception:
            pass

    # Sort: newest first (reverse chronological)
    def _job_sort_key(j):
        ts = j.get("created", "") or j.get("created_at", "") or ""
        return ts
    jobs.sort(key=_job_sort_key, reverse=True)
    
    return {"jobs": jobs, "total": len(jobs)}


@router.get("/active-model")
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

@router.post("/active-model")
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

@router.get("/opencode-models")
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

@router.get("/video/providers")
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

