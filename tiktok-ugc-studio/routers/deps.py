
"""Shared dependencies for all routers — paths, proxy helpers, module state.

Extracted from main.py so each router stays lean.
"""
import os
import json
import logging
import asyncio
import sqlite3
from pathlib import Path

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse

# ─── Global state (shared across routers) ────────────────────────────────
STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
TTS_DIR = STORAGE_DIR / "tts"
IMAGES_DIR = STORAGE_DIR / "images"
VIDEOS_DIR = STORAGE_DIR / "videos"

TIKTOK_ACCOUNTS_FILE = STORAGE_DIR / "tiktok_accounts.json"
PIPELINE_DB_PATH = os.path.join(os.path.dirname(STORAGE_DIR), "pipeline.db")
LOGS_DB_PATH = STORAGE_DIR / "pipeline_logs.db"
SCRAPER_API_URL = os.environ.get("SCRAPER_API_URL", "http://localhost:54444")

PRODUCT_IMAGE_DIR = STORAGE_DIR / "product_images"

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

_MODULES = {
    "video": "http://localhost:8111",
    "video-gen": "http://localhost:8111",
    "image-gen": "http://localhost:8110",
    "prompt-builder": "http://localhost:8117",
    "payment": "http://localhost:8112",
    "profile": "http://localhost:8113",
}

# In-memory pipeline results (for /video/status and /video/completed)
_pipeline_results = {}


def _load_env():
    """Load .env file into os.environ (does not override existing vars)."""
    env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k not in os.environ:
                        os.environ[k] = v


logger = logging.getLogger("tiktok-ugc")

# ─── Proxy helpers ────────────────────────────────────────────────────────
async def proxy(request: Request, target_url: str):
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.request(
                request.method,
                target_url,
                headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
                params=request.query_params,
                content=await request.body(),
                timeout=60.0,
            )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
    return StreamingResponse(
        resp.aiter_raw(),
        status_code=resp.status_code,
        headers=resp.headers,
        media_type=resp.headers.get("content-type"),
    )


async def _proxy(method: str, service: str, path: str, body: dict = None, timeout: float = 120.0):
    base = _MODULES.get(service, "http://localhost:8111")
    url = f"{base}{path}"
    async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
        if method.upper() == "GET":
            resp = await client.get(url)
        else:
            resp = await client.post(url, json=body or {})
        try:
            return resp.json()
        except Exception:
            return {"status": "ok", "text": resp.text}


async def _auth_json(method: str, path: str, req: dict = None, headers: dict = None):
    """Proxy to auth module, return the response body directly."""
    base = MODULE_URLS["auth"]
    url = f"{base}{path}"
    async with httpx.AsyncClient(timeout=90, verify=False) as cl:
        if method == "GET":
            resp = await cl.get(url, headers=headers or {})
        elif method == "DELETE":
            resp = await cl.delete(url, headers=headers or {})
        else:
            resp = await cl.post(url, json=req or {}, headers=headers or {})
        if resp.status_code >= 400:
            return JSONResponse(status_code=resp.status_code, content={"ok": False, "error": resp.text[:300]})
        return resp.json()

