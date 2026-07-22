"""
Passport Photo & Photo Restoration — FastAPI Module
====================================================
Port: 8122

Endpoints:
  GET  /api/passport/health
  GET  /api/passport/templates
  GET  /api/passport/templates/{code}
  POST /api/passport/process       (JSON base64 → passport photo)
  POST /api/passport/restore       (JSON base64 photo restoration)
  POST /api/passport/print-sheet   (generate print sheet)
  GET  /api/passport/download/{filename}  (download result)
"""

import os
import sys
import json
import uuid
import io
import logging
import base64
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel
from typing import Optional
import uvicorn
import requests

# Add erp-stack to path
_erp_stack = Path(__file__).parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("passport")

# ── App Setup ───────────────────────────────────────────────────────
app = FastAPI(title="Passport Photo Module", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Safe exception handler to avoid FastAPI crash on bytes serialization ──
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        e = {"loc": err.get("loc", []), "msg": str(err.get("msg", "")), "type": err.get("type", "")}
        errors.append(e)
    return JSONResponse(status_code=422, content={"detail": errors})

@app.exception_handler(StarletteHTTPException)
async def http_exc_handler(request: Request, exc: StarletteHTTPException):
    detail = str(exc.detail)[:500] if exc.detail else "Unknown error"
    # Clean up any binary content
    if isinstance(detail, bytes):
        detail = detail.decode("utf-8", errors="replace")
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})

@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    msg = str(exc)[:500] if str(exc) else "Internal server error"
    if isinstance(msg, bytes):
        msg = msg.decode("utf-8", errors="replace")
    return JSONResponse(status_code=500, content={"detail": f"Internal server error: {msg}"})

PORT = int(os.environ.get("PORT", 8122))
STORAGE_DIR = Path(__file__).parent / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

SCHEMA_ENGINE_URL = "http://localhost:8100"

# ── Import Engines (lazy init) ──────────────────────────────────────
def _get_template_engine():
    from .templates import engine
    engine.load()
    return engine

def _process_passport(img, code, auto_crop=True, enhance=True, auto_align=True):
    from .passport_engine import process_passport_photo
    return process_passport_photo(img, code, auto_crop, enhance, auto_align)

def _restore_photo(img, denoise=0.5, sharpen=0.5, inpaint=True, color=True, upscale=1, face=False):
    from .restoration_engine import restore_photo
    return restore_photo(img, denoise, sharpen, inpaint, color, upscale, face)

def _generate_sheet(img, w_mm, h_mm, size="4x6", dpi=300, margin_mm=3.0, add_guidelines=True):
    from .print_sheet import generate_print_sheet
    return generate_print_sheet(img, w_mm, h_mm, size, dpi, margin_mm, add_guidelines)

# ── Helpers ─────────────────────────────────────────────────────────

def _decode_image(data: bytes) -> np.ndarray:
    """Decode raw bytes to RGB numpy array."""
    arr = np.frombuffer(data, np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise HTTPException(400, "Invalid image data")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

def _encode_image(img: np.ndarray, fmt: str = ".jpg") -> bytes:
    """Encode numpy array to bytes."""
    if fmt == ".png":
        ok, buf = cv2.imencode(".png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    else:
        ok, buf = cv2.imencode(".jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR),
                               [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    if not ok:
        raise HTTPException(500, "Failed to encode image")
    return buf.tobytes()

def _decode_base64_image(b64: str) -> np.ndarray:
    """Decode base64 string to RGB numpy array."""
    try:
        img_data = base64.b64decode(b64)
    except Exception:
        raise HTTPException(400, "Invalid base64 image data")
    return _decode_image(img_data)

def _save_session(session_id: str, data: dict):
    """Save session to Schema Engine."""
    try:
        requests.post(
            f"{SCHEMA_ENGINE_URL}/api/v1/data/passport_session",
            json={"session_id": session_id, **data},
            timeout=3,
        )
    except Exception as e:
        logger.warning(f"Failed to save session: {e}")

# ═══════════════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════════════

class ProcessPassportRequest(BaseModel):
    image_base64: str
    template_code: str = "us_passport"
    auto_crop: bool = True
    enhance: bool = True
    auto_align: bool = True

class RestoreRequest(BaseModel):
    image_base64: str
    denoise_strength: float = 0.5
    sharpen_strength: float = 0.5
    inpaint_scratches: bool = True
    color_restore: bool = True
    upscale_factor: int = 1
    enhance_face: bool = False

class PrintSheetRequest(BaseModel):
    session_id: str
    print_size: str = "4x6"
    dpi: int = 300
    margin_mm: float = 3.0
    add_guidelines: bool = True

# ═══════════════════════════════════════════════════════════════════
# API Endpoints
# ═══════════════════════════════════════════════════════════════════

@app.get("/api/passport/health")
def health():
    return {
        "status": "ok",
        "service": "passport-module",
        "version": "1.0.0",
        "port": PORT,
    }

# ── Templates ───────────────────────────────────────────────────────

@app.get("/api/passport/templates")
def list_templates():
    """List all passport photo templates."""
    engine = _get_template_engine()
    templates = engine.get_all()
    return {"ok": True, "templates": templates, "count": len(templates)}

@app.get("/api/passport/templates/{code}")
def get_template(code: str):
    """Get a single template by code."""
    engine = _get_template_engine()
    tpl = engine.get(code)
    if not tpl:
        raise HTTPException(404, f"Template '{code}' not found")
    pixels = engine.pixel_dimensions(code)
    return {"ok": True, "template": tpl, "pixels": pixels}

# ── Process Passport Photo (JSON base64) ────────────────────────────

@app.post("/api/passport/process")
async def process_passport(req: ProcessPassportRequest):
    """
    Process passport photo — accepts JSON with base64 image.
    (Uses JSON body instead of multipart to avoid Cloudflare proxy issues)
    """
    session_id = uuid.uuid4().hex[:12]
    logger.info(f"[{session_id}] Process passport: template={req.template_code}")

    img = _decode_base64_image(req.image_base64)
    logger.info(f"  Input: {img.shape[1]}x{img.shape[0]}")

    result = _process_passport(img, req.template_code, req.auto_crop, req.enhance, req.auto_align)
    if not result["ok"]:
        raise HTTPException(400, result.get("error", "Processing failed"))

    output = result["result"]
    out_bytes = _encode_image(output)

    out_path = STORAGE_DIR / f"{session_id}.jpg"
    with open(out_path, "wb") as f:
        f.write(out_bytes)

    _save_session(session_id, {
        "template_code": req.template_code,
        "mode": "passport",
        "status": "processed",
        "result_path": str(out_path),
    })

    return {
        "ok": True,
        "session_id": session_id,
        "download_url": f"/api/passport/download/{session_id}.jpg",
        "template": result["template"],
        "info": result["info"],
    }

# ── Restore Photo ──────────────────────────────────────────────────

@app.post("/api/passport/restore")
async def restore_photo_endpoint(req: RestoreRequest):
    """Restore old/damaged photos."""
    session_id = uuid.uuid4().hex[:12]
    logger.info(f"[{session_id}] Restore photo: denoise={req.denoise_strength} sharpen={req.sharpen_strength}")

    img = _decode_base64_image(req.image_base64)
    logger.info(f"  Input: {img.shape[1]}x{img.shape[0]}")

    result = _restore_photo(
        img,
        denoise=req.denoise_strength,
        sharpen=req.sharpen_strength,
        inpaint=req.inpaint_scratches,
        color=req.color_restore,
        upscale=req.upscale_factor,
        face=req.enhance_face,
    )

    output = result["result"]
    out_bytes = _encode_image(output)

    out_path = STORAGE_DIR / f"{session_id}_restored.jpg"
    with open(out_path, "wb") as f:
        f.write(out_bytes)

    _save_session(session_id, {
        "mode": "restore",
        "status": "processed",
        "result_path": str(out_path),
    })

    return {
        "ok": True,
        "session_id": session_id,
        "download_url": f"/api/passport/download/{session_id}_restored.jpg",
        "info": result["info"],
    }

# ── Print Sheet ────────────────────────────────────────────────────

@app.post("/api/passport/print-sheet")
async def print_sheet(req: PrintSheetRequest):
    """Generate a print sheet from a processed passport photo."""
    src_path = STORAGE_DIR / f"{req.session_id}.jpg"
    if not src_path.exists():
        raise HTTPException(404, f"Session not found: {req.session_id}")

    img_bgr = cv2.imread(str(src_path))
    if img_bgr is None:
        raise HTTPException(500, "Failed to read source image")
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]

    dpi = req.dpi
    mm_w = w / dpi * 25.4
    mm_h = h / dpi * 25.4

    result = _generate_sheet(img_rgb, mm_w, mm_h, req.print_size, dpi, req.margin_mm, req.add_guidelines)
    if not result["ok"]:
        raise HTTPException(400, result.get("error", "Print sheet failed"))

    out_bytes = _encode_image(result["result"])
    out_path = STORAGE_DIR / f"{req.session_id}_print.jpg"
    with open(out_path, "wb") as f:
        f.write(out_bytes)

    return {"ok": True, "session_id": req.session_id, "download_url": f"/api/passport/download/{req.session_id}_print.jpg", "info": result["info"]}

# ── Download ────────────────────────────────────────────────────────

@app.get("/api/passport/download/{filename}")
def download(filename: str):
    """Download processed image by session filename."""
    path = STORAGE_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(str(path), media_type="image/jpeg")

@app.get("/api/passport/download/{session_id}")
def download_by_session(session_id: str):
    """Download the default result for a session."""
    path = STORAGE_DIR / f"{session_id}.jpg"
    if path.exists():
        return FileResponse(str(path), media_type="image/jpeg")
    path2 = STORAGE_DIR / f"{session_id}_restored.jpg"
    if path2.exists():
        return FileResponse(str(path2), media_type="image/jpeg")
    raise HTTPException(404, "Session file not found")

# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info(f"Starting Passport Module on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
