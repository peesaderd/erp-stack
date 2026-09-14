"""
Video Generation Module — Microservice
=======================================
AI UGC Video Generator: Script → TTS → Video Gen (Prodia/Fal) → Compose
Part of Business OS, registered with ERP Modular.

Port: 8111

Monolith split into routers/ — setup + router assembly only (Phase B refactor).
"""

import os
import sys
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# ─── Path setup ───────────────────────────────────────────────────────
_module_dir = os.path.dirname(os.path.abspath(__file__))
_modules_dir = os.path.dirname(_module_dir)
if _modules_dir not in sys.path:
    sys.path.insert(0, _modules_dir)
if _module_dir not in sys.path:
    sys.path.insert(0, _module_dir)

# ─── Storage (shared — see routers/deps.py for source of truth) ───────
from routers.deps import STORAGE_DIR, TTS_DIR, VIDEOS_DIR, COMPOSED_DIR
for d in [TTS_DIR, VIDEOS_DIR, COMPOSED_DIR]:
    d.mkdir(parents=True, exist_ok=True)

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

# ─── Routers ──────────────────────────────────────────────────────────
from routers import health, scripts, video, product

for r in (
    health.router,
    scripts.router,
    video.router,
    product.router,
):
    app.include_router(r)

# ─── TTS REMOVED (owner 2026-08-24) ──────────────────────────────────────
# Gemini TTS endpoints (/api/v1/tts/generate, /api/v1/tts/script) removed from
# TUS entirely. Voice = Wan 2.7 speaks thai_script directly in the pipeline.
# No TTS generation lives here anymore.

# ─── Entry Point ──────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8111))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
