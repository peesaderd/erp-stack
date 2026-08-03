# tiktok-ugc-studio gateway (FastAPI)
# Monolith split into routers/ — setup + router assembly only.

import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import DEFAULT_VIDEO_DURATION
from pipeline_db import (
    create_job, update_step, get_job, list_jobs,
    enrich_from_logs, _path_to_web_url,
)
from models import (
    ScriptRequest, UGCRequest, TTSRequest, ScriptTTSRequest,
    SceneBlock, VideoRequest, VideoPostRequest, PipelineRequest,
    FullPipelineRequest, ScrapeAndGenerateRequest,
)
from publisher import scheduler as publisher_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tiktok-ugc")

app = FastAPI(
    title="TikTok UGC Studio",
    version="0.2.1",
    description="AI UGC video pipeline - Script gen, TTS, Wan 2.7 I2V, FFmpeg compose, TikTok integration",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static mounts
from routers.deps import STORAGE_DIR, PRODUCT_IMAGE_DIR

for d in (STORAGE_DIR / "tts", STORAGE_DIR / "composed", STORAGE_DIR / "videos"):
    d.mkdir(parents=True, exist_ok=True)
try:
    app.mount("/static", StaticFiles(directory=str(STORAGE_DIR)), name="static")
except Exception as e:
    logger.warning(f"Static mount: {e}")

PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
try:
    app.mount("/ugc/static/product_images", StaticFiles(directory=str(PRODUCT_IMAGE_DIR)), name="product_images")
except Exception:
    pass

# ─── Routers ──────────────────────────────────────────────────────────────
from routers import (
    auth, pipeline, video, product, ugc, tiktok, payment,
    batch, aitoearn, publisher, monitor, scout,
)

for r in (
    auth.router,
    pipeline.router,
    video.router,
    product.router,
    ugc.router,
    tiktok.router,
    payment.router,
    batch.router,
    aitoearn.router,
    publisher.router,
    monitor.router,
    scout.router,
):
    app.include_router(r)


# ─── Startup / Shutdown ──────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    logger.info("TikTok UGC Studio starting up...")
    logger.info(f"Storage: {STORAGE_DIR}")
    from routers.deps import MODULE_URLS
    logger.info(f"Module URLs: {MODULE_URLS}")
    try:
        publisher_scheduler.start()
        logger.info("Publisher Scheduler: started (interval: {}s, random window: ±{}min)".format(
            publisher_scheduler.CHECK_INTERVAL_SECONDS,
            publisher_scheduler.RANDOM_WINDOW_MINUTES))
    except Exception as e:
        logger.warning(f"Publisher Scheduler: {e}")


@app.on_event("shutdown")
async def shutdown():
    try:
        publisher_scheduler.stop()
        logger.info("Publisher Scheduler: stopped")
    except Exception:
        pass


@app.get("/")
async def root():
    return {
        "service": "TikTok UGC Studio",
        "version": "0.2.0",
        "status": "running",
        "docs": "/docs",
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8105, reload=False)
