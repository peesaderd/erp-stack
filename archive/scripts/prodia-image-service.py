#!/usr/bin/env python3
"""
Prodia Image Service v2 — รับ request /api/image/v1/generate จาก TUS
ใช้ Prodia v2 multipart API (รูปแบบเดียวกับที่ sam3_client.py ใช้)
"""

import os
import sys
import json
import uuid
import logging
import time
import requests
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("prodia-service")

# ─── Config ────────────────────────────────────────────────

STORAGE_DIR = os.environ.get(
    "STORAGE_DIR",
    "/home/openhands/.openclaw/workspace/business-os/services/image-gen/storage/images"
)
Path(STORAGE_DIR).mkdir(parents=True, exist_ok=True)

PRODIA_TOKEN = os.environ.get("PRODIA_TOKEN", "")
PRODIA_BASE = "https://inference.prodia.com/v2"
PORT = int(os.environ.get("PORT", "8110"))

app = FastAPI(title="Prodia Image Service", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ─── Models ──────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    prompt: str = ""
    negative_prompt: Optional[str] = None
    aspectRatio: Optional[str] = "1:1"
    modelTier: Optional[str] = "sd-1.8"
    provider: Optional[str] = "prodia"
    count: Optional[int] = 1
    thaiModel: Optional[bool] = False
    inputImage: Optional[str] = ""
    image_url: Optional[str] = ""
    width: Optional[int] = 512
    height: Optional[int] = 896


# ─── Helpers ────────────────────────────────────────────────

ASPECT_MAP = {
    "1:1": (1024, 1024),
    "9:16": (512, 896),
    "16:9": (896, 512),
    "4:5": (800, 960),
    "3:4": (768, 1024),
    "4:3": (1024, 768),
}


def _save_image(image_data: bytes, prefix: str = "prodia") -> str:
    ext = "png"
    filename = f"{prefix}_{uuid.uuid4().hex[:12]}.{ext}"
    filepath = os.path.join(STORAGE_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(image_data)
    logger.info(f"Saved: {filepath}")
    return f"/storage/images/{filename}"


def _headers():
    return {"Authorization": f"Bearer {PRODIA_TOKEN}"}


def _poll_job(job_url: str, max_polls: int = 60, sleep_s: int = 2) -> dict:
    """Poll a Prodia v2 job URL until completed."""
    for attempt in range(max_polls):
        time.sleep(sleep_s)
        try:
            resp = requests.get(job_url, headers=_headers(), timeout=30)
            if resp.status_code != 200:
                continue
            data = resp.json()
        except Exception as e:
            logger.debug(f"Poll attempt {attempt}: {e}")
            continue

        status = data.get("status", "")

        if status in ("completed", "success"):
            return data
        elif status in ("failed", "error"):
            raise RuntimeError(f"Prodia job failed: {data}")
        # else: "processing", "queued" — keep polling

    raise TimeoutError("Prodia job timed out after 120s")


def _extract_output_urls(data: dict) -> list:
    """Extract image URLs from Prodia job result in various formats."""
    urls = []
    output = data.get("output", [])
    if isinstance(output, list):
        urls.extend(output)
    elif isinstance(output, str):
        urls.append(output)

    for key in ("imageUrl", "result", "image_url", "url"):
        val = data.get(key)
        if val and isinstance(val, str):
            urls.append(val)

    return urls


# ─── Prodia v2 API — multipart form ─────────────────────────

def prodia_generate_txt2img(
    prompt: str,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 896,
    steps: int = 25,
    cfg_scale: float = 7.0,
    model: str = "sd-1.8",
) -> dict:
    """
    Generate image via Prodia v2 multipart API.
    Job type: inference.<model>.txt2img[.v1]
    """
    # Map model names to Prodia v2 job types (SD-1.8 deprecated, use FLUX now)
    MODEL_MAP = {
        "sd-1.8": "inference.flux-2.dev.txt2img.v1",
        "standard": "inference.flux-2.dev.txt2img.v1",
        "klein.9b": "inference.flux-2.klein.9b.txt2img.v1",
        "klein-2b": "inference.flux-2.klein.4b.txt2img.v1",
        "flux-schnell": "inference.flux-2.schnell.txt2img.v2",
        "flux-dev": "inference.flux-2.dev.txt2img.v1",
        "flux-dev-v2": "inference.flux-2.dev.txt2img.v2",
        "sdxl": "inference.sdxl.txt2img.v1",
        "flux-2-dev": "inference.flux-2.dev.txt2img.v1",
        "flux-2-klein-9b": "inference.flux-2.klein.9b.txt2img.v1",
    }
    # Also handle dotted formats like "inference.xxx.yyy" or any inference-prefixed
    if model.startswith("inference.") or model.startswith("inference-"):
        job_type = model
    else:
        job_type = MODEL_MAP.get(model, model)

    config = {
        "type": job_type,
        "config": {
            "prompt": prompt,
            "negative_prompt": negative_prompt[:500],
            "steps": steps,
            "cfg_scale": cfg_scale,
            "width": width,
            "height": height,
        }
    }

    files = {
        "job": ("job.json", json.dumps(config), "application/json"),
    }

    logger.info(f"Prodia {job_type} | {prompt[:60]}... | {width}x{height} | steps={steps}")

    resp = requests.post(f"{PRODIA_BASE}/job", files=files, headers=_headers(), timeout=30)

    # Prodia v2 API returns 400 with JSON body for queued jobs (not 200!)
    data = {}
    job_id = None
    
    if resp.status_code == 200:
        # Direct image response (img2img with Accept: image/jpeg)
        ct = resp.headers.get("content-type", "")
        if "image" in ct:
            path = _save_image(resp.content)
            return {"ok": True, "images": [{"url": path, "full_url": f"http://localhost:{PORT}{path}"}], "provider": "prodia"}
        data = resp.json() if resp.text.strip() else {}
    elif resp.status_code == 400:
        try:
            data = resp.json()
        except:
            logger.error(f"Prodia non-JSON 400: {resp.text[:200]}")
            raise HTTPException(status_code=502, detail=f"Prodia error: {resp.text[:200]}")
    else:
        logger.error(f"Prodia submit error {resp.status_code}: {resp.text[:200]}")
        raise HTTPException(status_code=502, detail=f"Prodia submit error: {resp.text[:200]}")

    job_id = data.get("id") or data.get("job")
    if not job_id:
        logger.error(f"No job_id. Data: {json.dumps(data)[:200]}")
        raise HTTPException(status_code=502, detail=f"No job_id in response")

    logger.info(f"Job submitted: {job_id}")

    # Poll for completion
    status_url = f"{PRODIA_BASE}/job/{job_id}"
    try:
        result_data = _poll_job(status_url)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))

    # Get images
    image_urls = _extract_output_urls(result_data)
    logger.info(f"Job {job_id}: {len(image_urls)} output images")

    results = []
    for img_url in image_urls:
        try:
            img_resp = requests.get(img_url, timeout=30)
            if img_resp.status_code == 200:
                path = _save_image(img_resp.content)
                results.append({
                    "url": path,
                    "full_url": f"http://localhost:{PORT}{path}",
                })
        except Exception as e:
            logger.warning(f"Failed to download {img_url}: {e}")

    return {
        "ok": True,
        "images": results,
        "job_id": job_id,
        "provider": "prodia",
        "model": model,
    }


# ─── Endpoints ────────────────────────────────────────────────

@app.get("/api/image/v1/health")
async def health():
    return {
        "status": "ok",
        "service": "prodia-image-service",
        "version": "2.0.0",
        "provider": "prodia",
        "storage": STORAGE_DIR,
        "has_token": bool(PRODIA_TOKEN),
    }


@app.post("/api/image/v1/generate")
async def generate_image(req: GenerateRequest):
    """Main generate endpoint called by TUS /video/generate."""
    w, h = req.width, req.height
    if not w or not h:
        ar = req.aspectRatio or "9:16"
        w, h = ASPECT_MAP.get(ar, (512, 896))

    prompt = req.prompt or ""
    neg = req.negative_prompt or "blurry, low quality, deformed, ugly, text, watermark"

    result = prodia_generate_txt2img(
        prompt=prompt,
        negative_prompt=neg,
        width=w,
        height=h,
        steps=30,
    )
    return result


@app.post("/api/image/v1/remove-bg")
async def remove_bg(image_url: str = ""):
    if not image_url:
        raise HTTPException(400, "image_url required")
    return {"ok": True, "image_url": image_url, "note": "bg-removal via Prodia not available, returning original"}


@app.post("/api/image/v1/edit")
async def edit_image(prompt: str = "", image_url: str = ""):
    if not image_url and not prompt:
        raise HTTPException(400, "prompt or image_url required")
    result = prodia_generate_txt2img(prompt=prompt or "edit", steps=25)
    return result


@app.post("/api/image/v1/upscale")
async def upscale_image(image_url: str = ""):
    if not image_url:
        raise HTTPException(400, "image_url required")
    return {"ok": True, "image_url": image_url, "note": "upscale via Prodia not available, returning original"}


@app.get("/api/image/v1/templates")
async def list_templates():
    return {"ok": True, "templates": []}


@app.post("/api/image/v1/product/generate")
async def generate_product_image(productName: str = "", description: str = "", category: str = ""):
    prompt = f"Product photography of {productName}, {description}, clean white background, studio lighting"
    result = prodia_generate_txt2img(prompt=prompt)
    return result


@app.post("/api/image/v1/ugc/generate-frames")
async def ugc_generate_frames():
    return {"ok": False, "error": "ugc/generate-frames not available on Prodia proxy"}


@app.get("/storage/images/{filename}")
async def serve_image(filename: str):
    filepath = os.path.join(STORAGE_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(404, "Image not found")
    return FileResponse(filepath)


@app.get("/static/images/{filename}")
async def serve_static_image(filename: str):
    return await serve_image(filename)


if __name__ == "__main__":
    logger.info(f"Starting Prodia Image Service v2 on port {PORT}")
    logger.info(f"Storage: {STORAGE_DIR}")
    logger.info(f"Prodia token set: {bool(PRODIA_TOKEN)}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
