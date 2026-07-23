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

# ── Pydantic models for new endpoints ────────────────────────────────

class AiGeneratePassportRequest(BaseModel):
    image_base64: str
    template_code: str = "thai_passport"
    prompt: str = ""
    reference_image_base64: str = ""  # Optional reference clothing photo

# ── AI Generate — Pure AI Passport Photo ──────────────────────────

@app.post("/api/passport/ai-generate")
async def ai_generate_passport(req: AiGeneratePassportRequest):
    """
    AI-powered passport photo generation.
    Uses Gemini vision + Cloudflare Flux — no traditional CV processing.
    """
    import time
    from .ai_passport import generate_ai_passport
    
    session_id = uuid.uuid4().hex[:12]
    logger.info(f"[{session_id}] AI Generate: {req.template_code}")
    
    # Get template info
    engine = _get_template_engine()
    template_info = engine.get(req.template_code)
    if not template_info:
        raise HTTPException(404, f"Template '{req.template_code}' not found")
    
    # Decode images
    img_bytes = None
    ref_bytes = None
    try:
        img_bytes = base64.b64decode(req.image_base64)
        if req.reference_image_base64:
            ref_bytes = base64.b64decode(req.reference_image_base64)
    except Exception:
        raise HTTPException(400, "Invalid base64")
    
    result = generate_ai_passport(
        img_bytes,
        template_code=req.template_code,
        template_info=template_info,
        user_prompt=req.prompt,
        reference_image_bytes=ref_bytes,
    )
    
    if not result["ok"]:
        raise HTTPException(500, result.get("error", "Generation failed"))
    
    # Save
    out_img = result["result"]
    out_bytes = _encode_image(np.array(out_img))
    out_path = STORAGE_DIR / f"{session_id}_passport.jpg"
    with open(out_path, "wb") as f:
        f.write(out_bytes)
    
    # Generate print sheet
    try:
        ph, pw = out_img.size[1], out_img.size[0]
        mm_w = result["dimensions_mm"]["w"]
        mm_h = result["dimensions_mm"]["h"]
        sheet = _generate_sheet(np.array(out_img), mm_w, mm_h, "4x6", 300, 3.0, True)
        if sheet.get("ok"):
            sheet_bytes = _encode_image(sheet["result"])
            with open(STORAGE_DIR / f"{session_id}_print.jpg", "wb") as f:
                f.write(sheet_bytes)
    except Exception as e:
        logger.warning(f"Print sheet error: {e}")
    
    logger.info(f"[{session_id}] AI Done")
    
    return {
        "ok": True,
        "session_id": session_id,
        "download_passport": f"/api/passport/download/{session_id}_passport.jpg",
        "download_print": f"/api/passport/download/{session_id}_print.jpg",
        "info": result["info"],
        "dimensions": result["dimensions_mm"],
    }


