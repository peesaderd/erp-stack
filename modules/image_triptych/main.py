"""
Image Triptych FastAPI Service — Prodia-only
==============================================

POST /api/v1/triptych/generate
{
  "prompt": "...",
  "reference_image": "data:image/png;base64,..." | URL | path,
  "aspect_ratio": "16:9",
  "rembg_panels": [1],
  "n_panels": 3,
  "upscale_factor": 2
}

Returns:
{
  "triptych": { "path", "url", "size" },
  "triptych_2x": { "path", "url", "size" },
  "panels": [{"index", "url", "size"}, ...],
  "rembg": { "1": { "foreground_url", "mask_url", "size" } },
  "costs": [...],
  "total_usd": 0.045,
  "durations_sec": {...}
}
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

# Local imports
from pipeline import run_triptych

SERVICE_VERSION = "2.0.0"  # Prodia-only rewrite
DEFAULT_PORT = 8112
STORAGE_DIR = Path(os.environ.get("TRIPTYCH_STORAGE", "/tmp/triptych_storage"))
PUBLIC_URL_PREFIX = os.environ.get("TRIPTYCH_PUBLIC_URL", "/storage")

STORAGE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Image Triptych Service",
    description="16:9 triptych → upscale 2x → 3 panels 9:16 → remove BG (all via Prodia)",
    version=SERVICE_VERSION,
)


class TriptychRequest(BaseModel):
    prompt: str = Field(..., description="Text prompt for triptych generation")
    reference_image: str = Field(
        ..., description="URL, file path, base64, or data URL of reference image"
    )
    aspect_ratio: str = Field(default="16:9", description="Output aspect ratio")
    rembg_panels: Optional[List[int]] = Field(
        default_factory=lambda: [1],
        description="Panel indices (1-based) to apply remove-background",
    )
    n_panels: int = Field(default=3, ge=1, le=10)
    upscale_factor: int = Field(default=2, ge=1, le=8)


def _path_to_url(p: str) -> str:
    """Convert absolute file path to public URL."""
    rel = Path(p).relative_to(STORAGE_DIR)
    return f"{PUBLIC_URL_PREFIX}/{rel.as_posix()}"


@app.get("/health")
def health():
    return {
        "service": "image-triptych",
        "version": SERVICE_VERSION,
        "storage": str(STORAGE_DIR),
        "public_url_prefix": PUBLIC_URL_PREFIX,
        "engine": "prodia-sync-only",
    }


@app.post("/api/v1/triptych/generate")
def generate(req: TriptychRequest):
    """Run full triptych pipeline."""
    import uuid
    out_dir = STORAGE_DIR / f"run_{uuid.uuid4().hex[:12]}"

    try:
        result = run_triptych(
            prompt=req.prompt,
            reference_image=req.reference_image,
            out_dir=str(out_dir),
            aspect_ratio=req.aspect_ratio,
            rembg_panels=req.rembg_panels or [],
            n_panels=req.n_panels,
            upscale_factor=req.upscale_factor,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")

    # Convert paths to URLs
    triptych_url = _path_to_url(result["triptych"])
    triptych_2x_url = _path_to_url(result["triptych_2x"])

    panels_out = []
    for p in result["panels"]:
        panels_out.append({
            "index": p["index"],
            "path": p["path"],
            "url": _path_to_url(p["path"]),
            "size": p["size"],
        })

    rembg_out = {}
    for k, v in result["rembg"].items():
        rembg_out[k] = {
            "foreground": v["foreground"],
            "foreground_url": _path_to_url(v["foreground"]),
            "mask": v["mask"],
            "mask_url": _path_to_url(v["mask"]),
            "size": v["size"],
        }

    return {
        "triptych": {"path": result["triptych"], "url": triptych_url},
        "triptych_2x": {"path": result["triptych_2x"], "url": triptych_2x_url},
        "panels": panels_out,
        "rembg": rembg_out,
        "costs": result["costs"],
        "total_usd": result["total_usd"],
        "durations_sec": result["durations_sec"],
    }


if __name__ == "__main__":
    port = int(os.environ.get("TRIPTYCH_PORT", DEFAULT_PORT))
    uvicorn.run(app, host="0.0.0.0", port=port)
