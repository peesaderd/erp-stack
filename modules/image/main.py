"""
Image Generation Module - Microservice
=======================================
Nano Banana img2img + Mistral Pixtral Vision สำหรับวิเคราะห์รูปสินค้า
Part of Business OS, registered with ERP Modular.

Port: 8110
"""

import os
import sys
import json
import uuid
import time
import logging
import requests
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uvicorn
from PIL import Image
import io

# Add erp-stack to path for shared_config
_erp_stack = Path(__file__).parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))

from shared_config import PRODIA_TOKEN, MISTRAL_API_KEY
from prodia_pricing import get_price_for_sync_image
from prodia_client import ProdiaV2Client, ProdiaV2Error, ProdiaValidationError, ProdiaJobFailedError, ProdiaTimeoutError
# ─── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger("image-module")

# ─── FastAPI ─────────────────────────────────────────────────────────
app = FastAPI(title="Image Generation Module", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

PORT = int(os.environ.get("PORT", 8110))
STORAGE_DIR = Path(__file__).parent / "storage" / "images"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# ─── Prodia Client (cached) ──────────────────────────────────────────
_prodia_client = None

def _get_prodia_client():
    global _prodia_client
    if _prodia_client is None:
        token = PRODIA_TOKEN()
        if not token:
            raise ValueError("PRODIA_TOKEN not configured")
        _prodia_client = ProdiaV2Client(token=token)
    return _prodia_client

# ─── Models ──────────────────────────────────────────────────────────
class ImageGenRequest(BaseModel):
    prompt: str
    inputImage: Optional[str] = None
    negative_prompt: Optional[str] = ""
    width: int = 512
    height: int = 896
    style: Optional[str] = "thai_realistic"
    model: Optional[str] = "nano-banana"
    aspectRatio: Optional[str] = "9:16"

class BatchImageRequest(BaseModel):
    prompts: List[str]
    inputImage: Optional[str] = None
    width: int = 512
    height: int = 896

# ─── Aspect Ratio Map ─────────────────────────────────────────────────
ASPECT_MAP = {
    "1:1": (1024, 1024),
    "9:16": (512, 896),
    "16:9": (896, 512),
    "4:5": (768, 960),
    "3:4": (768, 1024),
    "4:3": (1024, 768),
}

# ─── Image Save ──────────────────────────────────────────────────────
def _save_image(data: bytes, prefix: str = "prodia") -> str:
    filename = f"{prefix}_{uuid.uuid4().hex[:12]}.png"
    path = STORAGE_DIR / filename
    with open(path, "wb") as f:
        f.write(data)
    return f"/storage/images/{filename}"

def _download_image(url: str) -> bytes:
    """Download image from URL, handling circular self-references"""
    local_prefix = f"http://localhost:{PORT}/storage/images/"
    if url.startswith(local_prefix):
        local_path = str(STORAGE_DIR / url[len(local_prefix):])
        logger.info(f"Circular ref detected! Using local path: {local_path}")
        with open(local_path, "rb") as f:
            return f.read()
    if url.startswith("/storage/images/"):
        local_path = str(STORAGE_DIR / os.path.basename(url))
        with open(local_path, "rb") as f:
            return f.read()
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content

# ─── Health ──────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "image-module",
        "version": "3.0.0",
        "provider": "prodia",
        "models": ["nano.banana.v2 (img2img)"],
        "mistral_vision": True,
    }

# ═══════════════════════════════════════════════════════════════
# Image Generation (Sync API — Nano Banana does NOT support async)
# ═══════════════════════════════════════════════════════════════

def prodia_generate_img2img(
    prompt: str,
    input_image: str,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 896,
    thai_model: bool = True,
) -> dict:
    """
    Generate image via Nano Banana img2img (Sync API)
    Cost: $0.039 per image (Prodia pricing, Nano Banana Gemini 2.5 Flash 1K)
    """
    if thai_model:
        if "thai" not in prompt.lower():
            prompt = prompt.rstrip(",. ") + \
                ", beautiful Thai person style, realistic skin texture, highly detailed face, soft warm lighting"
        if not negative_prompt:
            negative_prompt = "Chinese face, Korean face, East Asian anime style, plastic surgery face, V-shaped chin, double eyelid surgery, glass skin, k-pop style, Japanese face, white skin bleaching, pale white skin, caucasian features, western face, 3D render, illustration, cartoon, low quality, blurry, distorted face, unnatural proportions, blemish"

    image_data = _download_image(input_image)
    # Prodia max input = 2048px - scale down, keep aspect ratio
    img = Image.open(io.BytesIO(image_data))
    if img.width > 2048 or img.height > 2048:
        ratio = min(2048 / img.width, 2048 / img.height)
        new_w = int(img.width * ratio)
        new_h = int(img.height * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_data = buf.getvalue()
        logger.info(f"  Input resized: {img.width}x{img.height} -> {new_w}x{new_h}")
    token = PRODIA_TOKEN()

    config = {
        "type": "inference.nano-banana.img2img.v2",
        "config": {
            "prompt": prompt,
            "aspect_ratio": "9:16",
        },
    }
    # 🔥 Fix: Prodia v2 sync API rejects negative_prompt in config for nano-banana
    # We keep negative_prompt text (used for thai_model filter) but don't send it to Prodia
    # Only use it internally for prompt polishing


    files = [
        ("job", ("job.json", json.dumps(config), "application/json")),
        ("input", ("image.png", image_data, "image/png")),
    ]

    logger.info(f"Nano Banana img2img (sync) | {prompt[:60]}...")

    try:
        resp = requests.post(
            "https://inference.prodia.com/v2/job",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            timeout=120,
        )

        ct = resp.headers.get("content-type", "")
        if resp.status_code == 200 and ("image" in ct or "png" in ct or "jpeg" in ct):
            path = _save_image(resp.content, prefix="nano")
            full_url = f"http://localhost:{PORT}{path}"
            cost = get_price_for_sync_image("nano-banana.img2img.v2")
            logger.info(f"  Image OK ({len(resp.content)}B) | cost=${cost['dollars']}")
            return {
                "ok": True,
                "images": [{"url": path, "full_url": full_url}],
                "provider": "prodia",
                "model": "nano-banana.img2img.v2",
                "cost": cost,
            }

        # 🔥 Fix: Prodia sync API sometimes returns job status (JSON with id) instead of image
        # Try to poll for result
        try:
            body = resp.json()
            job_id = body.get("id", "")
            status = body.get("status", "")
            logger.info(f"  Prodia job {status}: id={job_id[:20]}...")
            
            if job_id:
                # Poll for up to 180 seconds
                for attempt in range(90):
                    import time
                    time.sleep(2)
                    poll_resp = requests.get(
                        f"https://inference.prodia.com/v2/job/{job_id}/result",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=30,
                    )
                    poll_ct = poll_resp.headers.get("content-type", "")
                    if poll_resp.status_code == 200 and ("image" in poll_ct or "png" in poll_ct or "jpeg" in poll_ct):
                        path = _save_image(poll_resp.content, prefix="nano")
                        full_url = f"http://localhost:{PORT}{path}"
                        cost = get_price_for_sync_image("nano-banana.img2img.v2")
                        logger.info(f"  Poll OK ({len(poll_resp.content)}B) | cost=${cost['dollars']}")
                        return {
                            "ok": True,
                            "images": [{"url": path, "full_url": full_url}],
                            "provider": "prodia",
                            "model": "nano-banana.img2img.v2",
                            "cost": cost,
                        }
                    logger.info(f"  Poll {attempt+1}/30: status={poll_resp.status_code}")
                
                raise HTTPException(status_code=502, detail=f"Prodia polling timeout for job {job_id}")
        except HTTPException:
            raise
        except Exception as poll_err:
            logger.error(f"Poll attempt failed: {poll_err}")

        err_data = {}
        try:
            err_data = resp.json()
        except Exception:
            pass
        err_msg = err_data.get("error", resp.text[:200])
        raise HTTPException(status_code=502, detail=f"Prodia error: {err_msg}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# Mistral Pixtral Vision
# ═══════════════════════════════════════════════════════════════

def mistral_analyze_image(image_path: str, prompt: str) -> str:
    """วิเคราะห์รูปด้วย Mistral Pixtral Vision"""
    token = MISTRAL_API_KEY()
    if not token:
        raise ValueError("MISTRAL_API_KEY not configured")

    if image_path.startswith("http"):
        resp = requests.get(image_path, timeout=30)
        resp.raise_for_status()
        image_b64 = __import__("base64").b64encode(resp.content).decode()
    else:
        with open(image_path, "rb") as f:
            image_b64 = __import__("base64").b64encode(f.read()).decode()

    resp = requests.post(
        "https://api.mistral.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "model": "pixtral-12b-2409",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image_b64}"},
                    ],
                }
            ],
            "max_tokens": 1024,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════════════
# API Endpoints
# ═══════════════════════════════════════════════════════════════

@app.get("/active-model")
def get_active_model():
    return {"active": "prodia", "providers": ["prodia"]}


@app.post("/api/v1/image/generate")
async def generate_image(req: ImageGenRequest):
    """Generate image via Nano Banana img2img (Prodia sync API)"""
    logger.info(f"Image gen request: {req.model} | prompt={req.prompt[:50]}...")

    w, h = req.width, req.height
    if req.aspectRatio and req.aspectRatio in ASPECT_MAP:
        w, h = ASPECT_MAP.get(req.aspectRatio, (512, 896))

    input_img = req.inputImage
    if not input_img:
        # Fallback to default product image placeholder if none provided
        input_img = "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=512&q=80"
        logger.info("  Using fallback product image for img2img")

    return prodia_generate_img2img(
        prompt=req.prompt,
        input_image=input_img,
        negative_prompt=req.negative_prompt or "",
        width=w,
        height=h,
    )


@app.post("/api/v1/image/analyze")
async def analyze_product_image(req: dict):
    """Analyze product image using Mistral Vision"""
    image_url = req.get("image_url", req.get("url", ""))
    prompt_text = req.get("prompt", "Describe this product in detail")

    if not image_url:
        raise HTTPException(status_code=400, detail="Missing image_url")

    result = mistral_analyze_image(image_url, prompt_text)
    return {"ok": True, "analysis": result}


# ─── Static Files ────────────────────────────────────────────────────
@app.get("/storage/images/{filename}")
async def serve_image(filename: str):
    path = STORAGE_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)


# ─── Main ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
