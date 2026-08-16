"""
Image Triptych Service — FastAPI wrapper around pipeline.py

Endpoints:
  GET  /health
  POST /api/v1/triptych/generate
    body: {
      prompt: str,
      reference_image: str,     # path, URL, or base64 data URL
      aspect_ratio: "16:9",     # default
      rembg_panels: [1, 2, 3],  # default: [1]
    }
    returns: {
      ok: true,
      triptych: { url: "...", full_url: "..." },
      triptych_2x: { url, full_url },
      panels: [{ index, url, full_url, size: [w,h] }, ...],
      rembg: { 1: { url, full_url, size }, ... },
      price_usd: 0.039,
    }
"""
import os
import sys
import uuid
import base64
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Local imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from modules.image_triptych.pipeline import run_triptych

# ─── Config ────────────────────────────────────────────────────────────────

PORT = int(os.environ.get("TRIPTYCH_PORT", "8112"))
STORAGE_DIR = Path(os.environ.get("TRIPTYCH_STORAGE", "/tmp/triptych_storage"))
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="image-triptych", version="1.0.0")


# ─── Models ────────────────────────────────────────────────────────────────

class TriptychRequest(BaseModel):
    prompt: str
    reference_image: str  # URL, path, or data:image/...;base64,...
    aspect_ratio: str = "16:9"
    rembg_panels: Optional[List[int]] = None
    use_realesrgan: bool = False  # off by default (CPU is slow)


# ─── Helpers ───────────────────────────────────────────────────────────────

def _resolve_reference(ref: str) -> str:
    """Resolve reference_image to a local file path."""
    # data URL
    if ref.startswith("data:image/"):
        _, b64 = ref.split(",", 1)
        img_bytes = base64.b64decode(b64)
        path = STORAGE_DIR / f"ref_{uuid.uuid4().hex[:12]}.png"
        path.write_bytes(img_bytes)
        return str(path)

    # existing local file
    if os.path.exists(ref) and os.path.isfile(ref):
        return ref

    # URL → download
    if ref.startswith(("http://", "https://")):
        import requests
        r = requests.get(ref, timeout=30, verify=False)
        r.raise_for_status()
        path = STORAGE_DIR / f"ref_{uuid.uuid4().hex[:12]}.png"
        path.write_bytes(r.content)
        return str(path)

    raise HTTPException(status_code=400, detail=f"Cannot resolve reference_image: {ref[:80]}")


def _to_full_url(path: str) -> str:
    return f"http://localhost:{PORT}/storage/{Path(path).name}"


# ─── Endpoints ─────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "image-triptych",
        "version": "1.0.0",
        "providers": ["prodia:nano-banana.img2img.v2", "local:realesrgan+lanczos", "local:rembg"],
    }


@app.post("/api/v1/triptych/generate")
def generate(req: TriptychRequest):
    ref_path = _resolve_reference(req.reference_image)
    out_dir = STORAGE_DIR / f"job_{uuid.uuid4().hex[:12]}"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        result = run_triptych(
            prompt=req.prompt,
            reference_image_path=ref_path,
            out_dir=str(out_dir),
            aspect_ratio=req.aspect_ratio,
            rembg_panels=req.rembg_panels,
            use_realesrgan=req.use_realesrgan,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e.__class__.__name__}: {e}")

    panels_meta = []
    for i, p in enumerate(result["panels"], start=1):
        panels_meta.append({
            "index": i,
            "url": p,
            "full_url": _to_full_url(p),
            "size": list(Image.open(p).size),
        })

    rembg_meta = {}
    for idx, path in (result.get("rembg") or {}).items():
        from PIL import Image
        rembg_meta[str(idx)] = {
            "url": path,
            "full_url": _to_full_url(path),
            "size": list(Image.open(path).size),
        }

    return {
        "ok": True,
        "triptych": {
            "url": result["triptych"],
            "full_url": _to_full_url(result["triptych"]),
        },
        "triptych_2x": {
            "url": result["triptych_2x"],
            "full_url": _to_full_url(result["triptych_2x"]),
        },
        "panels": panels_meta,
        "rembg": rembg_meta,
        "price_usd": result["price_usd"],
    }


# ─── Static files ──────────────────────────────────────────────────────────

from fastapi.staticfiles import StaticFiles
app.mount("/storage", StaticFiles(directory=str(STORAGE_DIR)), name="storage")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
