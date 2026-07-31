"""
Image Generation Module — Microservice
=======================================
Nano Banana img2img (Prodia SYNC API) + Mistral Pixtral Vision
Port: 8110

Sync endpoint POST /v2/job returns image/png directly.
nano-banana DOES NOT support async — use sync only.
"""

import os, sys, json, uuid, logging, requests, io
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image
import uvicorn

_erp_stack = Path(__file__).parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))

from shared_config import PRODIA_TOKEN, MISTRAL_API_KEY
from prodia_pricing import get_price_for_sync_image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("image-module")

app = FastAPI(title="Image Generation Module", version="4.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

PORT = int(os.environ.get("PORT", 8110))
STORAGE_DIR = Path(__file__).parent / "storage" / "images"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

ASPECT_MAP = {
    "1:1": (1024, 1024), "9:16": (512, 896), "16:9": (896, 512),
    "4:5": (768, 960), "3:4": (768, 1024), "4:3": (1024, 768),
}


class ImageGenRequest(BaseModel):
    prompt: str
    inputImage: Optional[str] = None
    negative_prompt: Optional[str] = ""
    width: int = 512
    height: int = 896
    style: Optional[str] = "thai_realistic"
    model: Optional[str] = "nano-banana"
    aspectRatio: Optional[str] = "9:16"


# ─── Helpers ─────────────────────────────────────────────────────────

def _save_image(data: bytes, prefix: str = "nano") -> str:
    filename = f"{prefix}_{uuid.uuid4().hex[:12]}.png"
    path = STORAGE_DIR / filename
    with open(path, "wb") as f:
        f.write(data)
    return f"/storage/images/{filename}"


def _download_image(url: str) -> bytes:
    if not url:
        raise ValueError("Empty image URL provided")
    filename = os.path.basename(url)

    if os.path.exists(url) and os.path.isfile(url):
        logger.info(f"Loading image from file: {url}")
        with open(url, "rb") as f:
            return f.read()

    search_dirs = [
        STORAGE_DIR,
        Path("/home/openhands/erp-stack/tiktok-ugc-studio/storage/product_images"),
        Path("/home/openhands/erp-stack/tiktok-ugc-studio/storage"),
        Path("/home/openhands/erp-stack/modules/image/storage/images"),
        Path("/home/openhands/calm-noether/product_images"),
    ]
    for d in search_dirs:
        p = d / filename
        if p.exists() and p.is_file():
            logger.info(f"Found image on disk: {p}")
            with open(p, "rb") as f:
                return f.read()

    if url.startswith("/") or not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError(f"Cannot resolve image URL: {url}")

    logger.info(f"Downloading: {url}")
    resp = requests.get(url, timeout=30, verify=False)
    resp.raise_for_status()
    return resp.content


def _resize_for_prodia(image_data: bytes, max_px: int = 2048) -> bytes:
    img = Image.open(io.BytesIO(image_data))
    if img.width > max_px or img.height > max_px:
        ratio = min(max_px / img.width, max_px / img.height)
        new_w, new_h = int(img.width * ratio), int(img.height * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        logger.info(f"  Resized: {img.width}x{img.height} -> {new_w}x{new_h}")
        return buf.getvalue()
    return image_data


# ═══════════════════════════════════════════════════════════════
#  Image Generation — Prodia SYNC API (/v2/job)
# ═══════════════════════════════════════════════════════════════

PRODIA_SYNC_URL = "https://inference.prodia.com/v2/job"


def prodia_generate_img2img(
    prompt: str,
    input_image: str,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 896,
    thai_model: bool = True,
) -> dict:
    """Generate image via Nano Banana img2img — Prodia SYNC API"""

    if thai_model:
        if "thai" not in prompt.lower():
            prompt = prompt.rstrip(",. ") + \
                ", beautiful Thai person style, realistic skin texture, highly detailed face, soft warm lighting"
        if not negative_prompt:
            negative_prompt = (
                "Chinese face, Korean face, East Asian anime style, plastic surgery face, "
                "V-shaped chin, double eyelid surgery, glass skin, k-pop style, Japanese face, "
                "white skin bleaching, pale white skin, caucasian features, western face, "
                "3D render, illustration, cartoon, low quality, blurry, distorted face, "
                "unnatural proportions, blemish"
            )

    image_data = _download_image(input_image)
    image_data = _resize_for_prodia(image_data)

    token = PRODIA_TOKEN()

    config = {
        "type": "inference.nano-banana.img2img.v2",
        "config": {
            "prompt": prompt,
            "aspect_ratio": "9:16",
        },
    }

    files = [
        ("job", ("job.json", json.dumps(config), "application/json")),
        ("input", ("image.png", image_data, "image/png")),
    ]

    logger.info(f"Nano Banana img2img (sync) | {prompt[:80]}...")

    try:
        resp = requests.post(
            PRODIA_SYNC_URL,
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            timeout=120,
        )

        ct = resp.headers.get("content-type", "")
        logger.info(
            f"Prodia response: {resp.status_code} | content-type={ct} | "
            f"len={len(resp.content)}"
        )

        # ── Success: image returned directly ──
        if resp.status_code == 200 and any(t in ct for t in ("image/", "application/octet-stream")):
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

        # ── Prodia returned JSON (job queued or error) ──
        err_detail = ""
        try:
            body = resp.json()
            err_detail = json.dumps(body, indent=2)[:500]
            # Check for job ID (sync API queued — rare but possible)
            job_id = body.get("id") or body.get("jobId", "")
            if job_id and resp.status_code == 200:
                logger.warning(f"  Sync API queued job {job_id} — this model may need async. Retrying...")
                # Wait a few seconds and try to get the result
                import time
                for attempt in range(10):
                    time.sleep(3)
                    poll = requests.get(
                        f"https://inference.prodia.com/v2/job/{job_id}/result",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=30,
                    )
                    poll_ct = poll.headers.get("content-type", "")
                    if poll.status_code == 200 and any(t in poll_ct for t in ("image/", "application/octet-stream")):
                        path = _save_image(poll.content, prefix="nano")
                        full_url = f"http://localhost:{PORT}{path}"
                        cost = get_price_for_sync_image("nano-banana.img2img.v2")
                        logger.info(f"  Poll OK ({len(poll.content)}B) | cost=${cost['dollars']}")
                        return {
                            "ok": True,
                            "images": [{"url": path, "full_url": full_url}],
                            "provider": "prodia",
                            "model": "nano-banana.img2img.v2",
                            "cost": cost,
                        }
                    logger.info(f"  Poll {attempt+1}/10: {poll.status_code}")
                raise HTTPException(status_code=502, detail=f"Sync job {job_id} polling exhausted")
        except Exception:
            pass

        # ── Error handling ──
        if resp.status_code == 400:
            logger.error(f"Prodia 400: {err_detail}")
            raise HTTPException(status_code=400, detail=f"Invalid request: {err_detail}")
        elif resp.status_code == 401 or resp.status_code == 403:
            logger.error(f"Prodia auth error ({resp.status_code}): {err_detail}")
            raise HTTPException(status_code=502, detail="Prodia authentication failed — check PRODIA_TOKEN")
        elif resp.status_code >= 500:
            logger.error(f"Prodia server error ({resp.status_code}): {err_detail}")
            raise HTTPException(status_code=502, detail=f"Prodia server error: {err_detail}")
        else:
            logger.error(f"Prodia unexpected ({resp.status_code}): {err_detail}")
            raise HTTPException(status_code=502, detail=f"Prodia error ({resp.status_code}): {err_detail}")

    except HTTPException:
        raise
    except requests.exceptions.Timeout:
        logger.error("Prodia request timeout")
        raise HTTPException(status_code=504, detail="Prodia request timeout")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Prodia connection error: {e}")
        raise HTTPException(status_code=502, detail=f"Prodia connection failed: {e}")
    except Exception as e:
        logger.error(f"Image generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
#  Mistral Pixtral Vision
# ═══════════════════════════════════════════════════════════════

def mistral_analyze_image(image_path: str, prompt: str) -> str:
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
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image_b64}"},
                ],
            }],
            "max_tokens": 1024,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


# ═══════════════════════════════════════════════════════════════
#  API Endpoints
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "image-module",
        "version": "4.0.0",
        "provider": "prodia-sync",
        "models": ["nano.banana.v2 (img2img)"],
        "mistral_vision": True,
    }


@app.get("/active-model")
def get_active_model():
    return {"active": "prodia", "providers": ["prodia"]}


@app.post("/api/v1/image/generate")
async def generate_image(req: ImageGenRequest):
    logger.info(f"Image gen: {req.model} | {req.prompt[:60]}...")

    if not req.inputImage:
        raise HTTPException(status_code=400, detail="Missing input image for img2img")

    return prodia_generate_img2img(
        prompt=req.prompt,
        input_image=req.inputImage,
        negative_prompt=req.negative_prompt or "",
    )


@app.post("/api/v1/image/analyze")
async def analyze_product_image(req: dict):
    image_url = req.get("image_url", req.get("url", ""))
    prompt_text = req.get("prompt", "Describe this product in detail")
    if not image_url:
        raise HTTPException(status_code=400, detail="Missing image_url")
    result = mistral_analyze_image(image_url, prompt_text)
    return {"ok": True, "analysis": result}


@app.get("/storage/images/{filename}")
async def serve_image(filename: str):
    path = STORAGE_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(path)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
