"""
Image Generation Module — Microservice
=======================================
Nano Banana img2img + Wan 2.7 Lip Sync + Mistral Pixtral Vision
Port: 8110

Prodia API is simple — all jobs use the same endpoint.
  POST /v2/job  with JSON body {type, config}
  Sync models:  set Accept: image/png → get image bytes directly
  Async models: response JSON has job ID → poll /v2/job/async/{id}/job.state.current
"""

import os, sys, json, uuid, logging, requests, io, time, re, base64
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
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

app = FastAPI(title="Image Generation Module", version="4.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

PORT = int(os.environ.get("PORT", 8110))
STORAGE_DIR = Path(__file__).parent / "storage" / "images"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Mirror to shared storage so nginx /storage/ alias can serve it
SHARED_STORAGE_DIR = Path("/home/openhands/erp-stack/tiktok-ugc-studio/storage/images")
SHARED_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

PRODIA_BASE = "https://inference.prodia.com"
PRODIA_ASYNC = f"{PRODIA_BASE}/v2/job/async"
PRODIA_SYNC = f"{PRODIA_BASE}/v2/job"


# ─── Models ───────────────────────────────────────────────────────

class ImageGenRequest(BaseModel):
    prompt: str
    inputImage: Optional[str] = None
    negative_prompt: Optional[str] = ""
    width: int = 512
    height: int = 896
    style: Optional[str] = "thai_realistic"
    model: Optional[str] = "nano-banana"
    aspectRatio: Optional[str] = "9:16"


class LipSyncRequest(BaseModel):
    """Wan 2.7 Lip Sync — animate portrait with audio-driven speech"""
    imageUrl: str
    audioUrl: Optional[str] = None
    prompt: str = ""
    duration: int = 5
    aspectRatio: str = "9:16"


# ─── Helpers ──────────────────────────────────────────────────────

def _token() -> str:
    t = PRODIA_TOKEN()
    if not t:
        raise ValueError("PRODIA_TOKEN not configured")
    return t


def _save(data: bytes, prefix: str = "prodia") -> str:
    filename = f"{prefix}_{uuid.uuid4().hex[:12]}.png"
    path = STORAGE_DIR / filename
    with open(path, "wb") as f:
        f.write(data)
    # Mirror to shared storage so nginx /storage/ alias can serve it
    try:
        import shutil
        shutil.copy2(path, SHARED_STORAGE_DIR / filename)
    except Exception as e:
        logger.warning(f"Mirror to shared storage failed: {e}")
    return f"/storage/images/{filename}"


def _load_image(url: str) -> bytes:
    """Load image from URL, file path, or base64 data."""
    if not url:
        raise ValueError("Empty image URL")

    # Handle base64 data URLs (data:image/...;base64,...)
    if url.startswith("data:image/"):
        _, b64data = url.split(",", 1)
        return base64.b64decode(b64data)

    # Handle raw base64 strings (no data: prefix, but looks like base64)
    if len(url) > 100 and not url.startswith(("http://", "https://", "/")) \
            and re.match(r'^[A-Za-z0-9+/=\n\r]+$', url):
        try:
            return base64.b64decode(url)
        except Exception:
            pass  # Not valid base64, treat as URL

    filename = os.path.basename(url)

    if os.path.exists(url) and os.path.isfile(url):
        with open(url, "rb") as f:
            return f.read()

    search_dirs = [
        STORAGE_DIR,
        Path("/home/openhands/erp-stack/tiktok-ugc-studio/storage/product_images"),
        Path("/home/openhands/erp-stack/tiktok-ugc-studio/storage"),
        Path("/home/openhands/erp-stack/modules/image/storage/images"),
    ]
    for d in search_dirs:
        p = d / filename
        if p.exists() and p.is_file():
            logger.info(f"Found image on disk: {p}")
            with open(p, "rb") as f:
                return f.read()

    clean_url = re.sub(r"https?://(https?://)", r"", url)
    if clean_url != url:
        logger.warning(f"Fixed double-prefix URL: {url} -> {clean_url}")
    logger.info(f"Downloading: {clean_url}")
    resp = requests.get(clean_url, timeout=30, verify=False)
    resp.raise_for_status()
    return resp.content


def _resize(data: bytes, max_px: int = 2048) -> bytes:
    img = Image.open(io.BytesIO(data))
    if img.width > max_px or img.height > max_px:
        ratio = min(max_px / img.width, max_px / img.height)
        new_w, new_h = int(img.width * ratio), int(img.height * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        logger.info(f"  Resized: {img.width}x{img.height} -> {new_w}x{new_h}")
        return buf.getvalue()
    return data


def _call_prodia(type_: str, config: dict, accept: str = "image/png", files: dict = None, timeout: int = 120) -> bytes:
    """Call Prodia /v2/job — returns image bytes directly for sync models."""
    body = {"type": type_, "config": config}
    headers = {"Authorization": f"Bearer {_token()}", "Accept": accept}

    logger.info(f"Prodia {type_} | {json.dumps(config, ensure_ascii=False)[:120]}")

    if files:
        # Multipart upload — job JSON as file entry + input files
        all_files = [("job", ("job.json", json.dumps(body), "application/json"))] + list(files)
        resp = requests.post(
            PRODIA_SYNC, headers=headers, files=all_files, timeout=timeout
        )
    else:
        resp = requests.post(PRODIA_SYNC, headers=headers, json=body, timeout=timeout)

    ct = resp.headers.get("content-type", "")
    logger.info(f"  → {resp.status_code} | content-type={ct[:50]} | len={len(resp.content)}")

    if resp.status_code == 200 and any(t in ct for t in ("image/", "application/octet-stream")):
        return resp.content

    # Error handling
    err = ""
    try:
        err = json.dumps(resp.json(), indent=2)[:300]
    except Exception:
        err = resp.text[:300] if resp.text else ""

    if resp.status_code == 400:
        raise HTTPException(status_code=400, detail=f"Prodia validation: {err}")
    elif resp.status_code in (401, 403):
        raise HTTPException(status_code=502, detail="Prodia auth failed")
    elif resp.status_code >= 500:
        raise HTTPException(status_code=502, detail=f"Prodia server error: {err}")
    else:
        raise HTTPException(status_code=502, detail=f"Prodia {resp.status_code}: {err}")


# ═══════════════════════════════════════════════════════════════════
#  Nano Banana img2img — Sync API (single call, no polling)
# ═══════════════════════════════════════════════════════════════════

# Prodia Nano Banana img2img (see Prodia docs): the model ALREADY SEES the input image.
# "Describe the change, not the whole scene" + anchor preservation ("keep everything else
# exactly the same"). Re-describing the person's look/outfit overrides the real photo with
# guessed text. Anchor the reference instead.
IMG2IMG_ANCHOR = (
    "Keep the product exactly as shown in the reference image, and keep the same "
    "person, pose, outfit, and setting. Only adjust the scene as described. "
    "Do NOT change the product or the person's look."
)

THAI_NEGATIVE = (
    "Chinese face, Korean face, East Asian anime style, plastic surgery face, "
    "V-shaped chin, double eyelid surgery, glass skin, k-pop style, Japanese face, "
    "white skin bleaching, caucasian features, western face, 3D render, illustration, cartoon, "
    "low quality, blurry, distorted face, unnatural proportions, blemish"
)


def nano_banana_img2img(prompt: str, input_image: str, negative_prompt: str = "", aspect_ratio: str = "9:16", width: int = None, height: int = None) -> dict:
    """Generate Thai product image via Nano Banana img2img.

    Prodia sync model: POST /v2/job with multipart → image/png response.
    No polling. No async. Single call.
    """
    # Prodia img2img: describe the CHANGE anchored to the reference image.
    # Only prepend the preserve-anchor when the caller did NOT already request an
    # explicit composition (e.g. 'triptych' / '3 panels' / 'side by side'); otherwise
    # anchoring to 'keep composition exactly' would override the requested layout.
    prompt = prompt.rstrip(",. ")
    _lower = prompt.lower()
    _wants_layout = any(
        k in _lower for k in ("triptych", "panel", "side by side", "split into", "collage", "three equal")
    )
    if not _wants_layout and not any(k in _lower for k in ("keep", "same as", "reference")):
        prompt = IMG2IMG_ANCHOR + " " + prompt
    if not negative_prompt:
        negative_prompt = THAI_NEGATIVE

    image_data = _load_image(input_image)
    image_data = _resize(image_data)

    files = [
        ("input", ("image.png", image_data, "image/png")),
    ]

    config = {"prompt": prompt, "aspect_ratio": aspect_ratio}
    # Nano Banana reads aspect_ratio directly (per Prodia API); width/height aren't
    # supported params for this model — rely on aspect_ratio only so 16:9 actually sticks.

    result_bytes = _call_prodia(
        type_="inference.nano-banana.img2img.v2",
        config=config,
        files=files,
    )

    path = _save(result_bytes, prefix="nano")
    cost = get_price_for_sync_image("nano-banana.img2img.v2")
    logger.info(f"  Image OK ({len(result_bytes)}B) | cost=${cost['dollars']}")

    return {
        "ok": True,
        "images": [{"url": path, "full_url": f"http://localhost:{PORT}{path}"}],
        "provider": "prodia",
        "model": "nano-banana.img2img.v2",
        "cost": cost,
    }


# ═══════════════════════════════════════════════════════════════════
#  Wan 2.7 Lip Sync — Async API (img2vid with audio input)
# ═══════════════════════════════════════════════════════════════════

def wan_lip_sync(image_url: str, audio_url: str = None, prompt: str = "", duration: int = 5) -> dict:
    """Submit Wan 2.7 img2vid with audio-driven lip-sync.

    Async job: POST /v2/job/async → poll /v2/job/async/{id}/job.state.current
    Audio: WAV/MP3, 2-30s, max 15MB
    Returns job_id for polling.
    """
    headers = {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"}

    # Download and prepare image
    image_bytes = _load_image(image_url)

    config = {
        "prompt": prompt or "person speaking naturally, natural facial expressions, professional lighting",
        "duration": duration,
        "ratio": "9:16",
    }

    # Build multipart: json body + input image + optional audio
    files = [
        ("job", ("job.json", json.dumps({"type": "inference.wan2-7.img2vid.v1", "config": config}), "application/json")),
        ("input", ("image.png", image_bytes, "image/png")),
    ]

    if audio_url:
        audio_data = _load_image(audio_url)  # reuse image loader — handles URL + disk paths
        files.append(("audio", ("audio.mp3", audio_data, "audio/mpeg")))

    logger.info(f"Wan 2.7 Lip Sync | duration={duration}s | audio={yes if audio_url else no}")

    resp = requests.post(
        PRODIA_ASYNC,
        headers={"Authorization": f"Bearer {_token()}"},
        files=files,
        timeout=30,
    )

    if resp.status_code not in (200, 201, 202):
        err = ""
        try:
            err = json.dumps(resp.json())[:300]
        except Exception:
            err = resp.text[:300] if resp.text else ""
        raise HTTPException(status_code=502, detail=f"Wan 2.7 submit failed ({resp.status_code}): {err}")

    result = resp.json()
    job_id = result.get("id") or result.get("jobId", "")

    logger.info(f"  Wan 2.7 job submitted: {job_id}")

    return {
        "ok": True,
        "jobId": job_id,
        "status": "queued",
        "pollUrl": f"/api/v1/image/lipsync/{job_id}",
        "note": "Video generation takes ~200s. Poll /api/v1/image/lipsync/{job_id} for status.",
    }


def poll_lip_sync(job_id: str) -> dict:
    """Poll Wan 2.7 async job status."""
    headers = {"Authorization": f"Bearer {_token()}"}
    url = f"{PRODIA_BASE}/v2/job/async/{job_id}/job.state.current"

    resp = requests.get(url, headers=headers, timeout=10)

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Poll failed ({resp.status_code})")

    data = resp.json()
    state = data.get("state", "unknown")
    progress = data.get("progress", 0)

    if state == "completed":
        output_url = data.get("output", {}).get("url") or data.get("outputUrl", "")
        return {
            "ok": True,
            "jobId": job_id,
            "status": "completed",
            "videoUrl": output_url,
        }
    elif state == "failed":
        error = data.get("error", "Unknown error")
        return {"ok": False, "jobId": job_id, "status": "failed", "error": error}

    return {"ok": True, "jobId": job_id, "status": state, "progress": progress}


# ═══════════════════════════════════════════════════════════════════
#  Mistral Pixtral Vision
# ═══════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════
#  API Endpoints
# ═══════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "image-module",
        "version": "4.1.0",
        "providers": {
            "prodia": ["nano-banana.img2img.v2", "wan2-7.img2vid.v1 (lip-sync)"],
        },
        "mistral_vision": True,
    }


@app.get("/active-model")
def get_active_model():
    return {"active": "prodia", "models": ["nano-banana", "wan2-7"]}


@app.post("/api/v1/image/generate")
async def generate_image(req: ImageGenRequest):
    logger.info(f"Image gen: {req.model} | {req.prompt[:60]}...")

    if req.inputImage:
        # img2img path — nano-banana anchored to reference image
        return nano_banana_img2img(
            prompt=req.prompt,
            input_image=req.inputImage,
            negative_prompt=req.negative_prompt or "",
            aspect_ratio=req.aspectRatio or "9:16",
            width=req.width,
            height=req.height,
        )

    # txt2img fallback — no reference image, use Flux 2 Dev
    aspect = req.aspectRatio or "9:16"
    cfg = {"prompt": req.prompt, "aspect_ratio": aspect}
    if req.negative_prompt:
        cfg["negative_prompt"] = req.negative_prompt
    result_bytes = _call_prodia(
        type_="inference.flux-2.dev.txt2img.v1",
        config=cfg,
        timeout=180,
    )
    path = _save(result_bytes, prefix="flux")
    cost = get_price_for_sync_image("flux-2.dev.txt2img.v1")
    logger.info(f"  Txt2Img OK ({len(result_bytes)}B) | cost=${cost['dollars']}")
    return {
        "ok": True,
        "images": [{"url": path, "full_url": f"http://localhost:{PORT}{path}"}],
        "provider": "prodia",
        "model": "flux-2.dev.txt2img.v1",
        "cost": cost,
    }

# Backward-compatible alias for older clients that sent /api/v1/image/img2img
@app.post("/api/v1/image/img2img")
async def legacy_img2img(req: ImageGenRequest):
    return await generate_image(req)


@app.post("/api/v1/image/lipsync")
async def create_lip_sync(req: LipSyncRequest):
    """Submit Wan 2.7 lip-sync video generation."""
    logger.info(f"Lip Sync: duration={req.duration}s")
    return wan_lip_sync(
        image_url=req.imageUrl,
        audio_url=req.audioUrl,
        prompt=req.prompt,
        duration=req.duration,
    )


@app.get("/api/v1/image/lipsync/{job_id}")
async def get_lip_sync_status(job_id: str):
    """Poll Wan 2.7 lip-sync job status."""
    return poll_lip_sync(job_id)


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
