"""
Passport Photo Module V2 — FastAPI
===================================
Port: 8122

New in V2:
- Gender detection (Gemini Vision)
- Clothing selection (male/female presets + random)
- Prodia FLUX i2i pipeline
- Print sheet: border/no-border, cutting blade, photo count
"""

import os
import sys
import json
import uuid
import io
import time
import logging
import base64
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel
from typing import Optional
import uvicorn
import requests

_erp_stack = Path(__file__).parent.parent.parent
if str(_erp_stack) not in sys.path:
    sys.path.insert(0, str(_erp_stack))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("passport")

# ── App Setup ─────────────────────────────────────────
app = FastAPI(title="Passport Photo Module V2", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    errors = [{"loc": e.get("loc"), "msg": str(e.get("msg")), "type": e.get("type")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})

@app.exception_handler(StarletteHTTPException)
async def http_exc_handler(request: Request, exc: StarletteHTTPException):
    detail = str(exc.detail)[:500] if exc.detail else "Unknown error"
    if isinstance(detail, bytes): detail = detail.decode("utf-8", errors="replace")
    return JSONResponse(status_code=exc.status_code, content={"detail": detail})

@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception):
    msg = str(exc)[:500] if str(exc) else "Internal server error"
    if isinstance(msg, bytes): msg = msg.decode("utf-8", errors="replace")
    return JSONResponse(status_code=500, content={"detail": f"Internal server error: {msg}"})

PORT = int(os.environ.get("PORT", 8122))
STORAGE_DIR = Path(__file__).parent / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
SCHEMA_ENGINE_URL = "http://localhost:8100"


# ── Helpers ───────────────────────────────────────────

def _get_template_engine():
    from .templates import engine
    engine.load()
    return engine

def _encode_image(img: np.ndarray, fmt: str = ".jpg") -> bytes:
    if fmt == ".png":
        ok, buf = cv2.imencode(".png", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    else:
        ok, buf = cv2.imencode(".jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR),
                               [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    if not ok:
        raise HTTPException(500, "Failed to encode image")
    return buf.tobytes()

def _generate_sheet(img, w_mm, h_mm, size="4x6", dpi=300, gap_mm=3.0, border="guidelines", blade_mode=False, photo_count=0):
    from .print_sheet import generate_print_sheet
    return generate_print_sheet(img, w_mm, h_mm, size, dpi, gap_mm, True, border, gap_mm, blade_mode, photo_count)


# ═══════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════

class GenerateRequest(BaseModel):
    image_base64: str
    template_code: str = "thai_passport"
    gender: str = "auto"           # "male" | "female" | "auto"
    clothing: str = "auto"         # clothing key, "auto", or "random"
    background: str = "light_blue" # "light_blue" | "white" | "light_gray" | "custom"
    background_color: Optional[str] = None   # custom hex color
    background_gradient: Optional[str] = None # CSS gradient string
    strength: float = 0.45         # FLUX i2i strength

class BulkGenerateRequest(BaseModel):
    images: list  # list of base64 strings
    template_code: str = "thai_passport"
    gender: str = "auto"
    clothing: str = "auto"
    background: str = "light_blue"
    background_color: Optional[str] = None
    background_gradient: Optional[str] = None
    strength: float = 0.45
    print_size: str = "4x6"
    photo_count: int = 6
    border: str = "none"
    blade_mode: bool = False
    gap_mm: float = 2.0
    border_color: str = "#FFFFFF"
    border_width_mm: float = 0.0

class PrintSheetRequest(BaseModel):
    session_id: str
    print_size: str = "4x6"
    photo_count: int = 6           # 0 = auto
    border: str = "none"           # "none" | "frame"
    gap_mm: float = 2.0
    blade_mode: bool = False
    dpi: int = 300
    border_color: str = "#FFFFFF"
    border_width_mm: float = 0.0


# ═══════════════════════════════════════════════════════════
# API Endpoints
# ═══════════════════════════════════════════════════════════

@app.get("/api/passport/health")
def health():
    return {"status": "ok", "service": "passport-module-v2", "version": "2.0.0", "port": PORT}


# ── Templates ─────────────────────────────────────────

@app.get("/api/passport/templates")
def list_templates():
    engine = _get_template_engine()
    return {"ok": True, "templates": engine.get_all(), "count": len(engine.get_all())}

@app.get("/api/passport/templates/{code}")
def get_template(code: str):
    engine = _get_template_engine()
    tpl = engine.get(code)
    if not tpl: raise HTTPException(404, f"Template '{code}' not found")
    return {"ok": True, "template": tpl, "pixels": engine.pixel_dimensions(code)}


# ── Clothing ──────────────────────────────────────────

@app.get("/api/passport/clothing")
def list_clothing(gender: str = "male"):
    from .clothing import list_clothing as _list
    return {"ok": True, "gender": gender, "options": _list(gender)}

@app.get("/api/passport/backgrounds")
def list_backgrounds():
    from .clothing import list_backgrounds as _list
    return {"ok": True, "options": _list()}


# ── Gender Detection ──────────────────────────────────

@app.post("/api/passport/detect-gender")
async def detect_gender(image_base64: str = Form(...)):
    from .gender_detector import detect_gender as _detect
    try:
        img_bytes = base64.b64decode(image_base64)
    except Exception:
        raise HTTPException(400, "Invalid base64")
    result = _detect(img_bytes)
    return {"ok": True, **result}


# ── Main Generate (V2) ────────────────────────────────

@app.post("/api/passport/generate")
async def generate_passport_v2(req: GenerateRequest):
    """V2: Gender detection + clothing selection + FLUX i2i + print sheet."""
    from .ai_passport import generate_passport
    from .gender_detector import detect_gender as _detect_gender
    from .clothing import get_clothing, get_background

    session_id = uuid.uuid4().hex[:12]
    t0 = time.time()
    logger.info(f"[{session_id}] V2 Generate: template={req.template_code}, gender={req.gender}, clothing={req.clothing}")

    # Get template
    engine = _get_template_engine()
    template_info = engine.get(req.template_code)
    if not template_info:
        raise HTTPException(404, f"Template '{req.template_code}' not found")

    # Decode image
    try:
        img_bytes = base64.b64decode(req.image_base64)
    except Exception:
        raise HTTPException(400, "Invalid base64")

    # Gender detection
    gender = req.gender
    gender_info = {"gender": gender, "confidence": 1.0, "description": "user specified"}
    if gender == "auto":
        gender_info = _detect_gender(img_bytes)
        gender = gender_info["gender"]
        logger.info(f"[{session_id}] Detected gender: {gender} ({gender_info['confidence']:.0%})")

    # Clothing selection
    clothing = get_clothing(gender, req.clothing)
    bg = get_background(req.background)

    # Background color/gradient override
    bg_color = req.background_color
    bg_gradient = req.background_gradient
    if bg_gradient:
        bg_prompt = f"gradient background {bg_gradient}"
    elif bg_color:
        bg_prompt = f"solid {bg_color} background"
    else:
        bg_prompt = bg["prompt"]

    # Generate passport photo
    result = generate_passport(
        img_bytes,
        template_info=template_info,
        clothing_prompt=clothing["prompt"],
        bg_prompt=bg_prompt,
        strength=req.strength,
        session_id=session_id,
    )

    if not result["ok"]:
        raise HTTPException(500, result.get("error", "Generation failed"))

    # Save raw FLUX output (large, uncropped)
    out_img = result["result"]
    out_bytes = _encode_image(out_img)
    out_path = STORAGE_DIR / f"{session_id}_passport.jpg"
    with open(out_path, "wb") as f:
        f.write(out_bytes)

    # No auto print sheet — raw image needs cropping first
    print_info = None

    elapsed = round(time.time() - t0, 1)
    logger.info(f"[{session_id}] Done in {elapsed}s")

    return {
        "ok": True,
        "session_id": session_id,
        "download_passport": f"/api/passport/download/{session_id}_passport.jpg",
        "download_print": f"/api/passport/download/{session_id}_print.jpg",
        "gender": gender,
        "gender_info": gender_info,
        "clothing": clothing["name"],
        "background": bg["name"],
        "print_info": print_info,
        "dimensions_px": result["dimensions_px"],
        "face_info": result["info"].get("face_in_output"),
        "time_seconds": elapsed,
    }


# ── Print Sheet (V2) ──────────────────────────────────

@app.post("/api/passport/print-sheet")
async def print_sheet_v2(req: PrintSheetRequest):
    """Generate print sheet with V2 options (border, blade, count)."""
    src_path = STORAGE_DIR / f"{req.session_id}_passport.jpg"
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

    from .print_sheet import generate_print_sheet
    result = generate_print_sheet(
        img_rgb, mm_w, mm_h, req.print_size, dpi, req.gap_mm, True,
        req.border, req.gap_mm, req.blade_mode, req.photo_count
    )
    if not result["ok"]:
        raise HTTPException(400, result.get("error", "Print sheet failed"))

    out_bytes = _encode_image(result["result"])
    out_path = STORAGE_DIR / f"{req.session_id}_print.jpg"
    with open(out_path, "wb") as f:
        f.write(out_bytes)

    return {
        "ok": True,
        "session_id": req.session_id,
        "download_url": f"/api/passport/download/{req.session_id}_print.jpg",
        "info": result["info"],
    }


# ── Multi-Photo Print Sheet ────────────────────────

class MultiPrintRequest(BaseModel):
    session_ids: list  # list of session_id strings
    copies: int = 1    # copies per photo
    print_size: str = "4x6"
    border: str = "none"
    blade_mode: bool = False
    gap_mm: float = 2.0
    dpi: int = 300
    border_color: str = "#FFFFFF"
    border_width_mm: float = 0.0


@app.post("/api/passport/multi-print")
async def multi_print(req: MultiPrintRequest):
    """Generate print sheet with multiple different photos."""
    from .print_sheet import generate_multi_print_sheet
    
    if not req.session_ids:
        raise HTTPException(400, "No photos selected")
    if len(req.session_ids) > 20:
        raise HTTPException(400, "Max 20 photos")
    
    # Load all images
    images = []
    dims = []
    for sid in req.session_ids:
        path = STORAGE_DIR / f"{sid}_passport.jpg"
        if not path.exists():
            raise HTTPException(404, f"Photo not found: {sid}")
        img = cv2.imread(str(path))
        if img is None:
            raise HTTPException(500, f"Failed to read: {sid}")
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = img_rgb.shape[:2]
        images.append(img_rgb)
        dims.append((w / req.dpi * 25.4, h / req.dpi * 25.4))
    
    # Generate multi-photo sheet
    result = generate_multi_print_sheet(
        images, dims, req.copies, req.print_size, req.dpi,
        req.gap_mm, req.border, req.blade_mode
    )
    
    if not result["ok"]:
        raise HTTPException(500, result.get("error", "Failed"))
    
    # Save with unique ID
    batch_id = f"batch_{uuid.uuid4().hex[:8]}"
    out_bytes = _encode_image(result["result"])
    out_path = STORAGE_DIR / f"{batch_id}_print.jpg"
    with open(out_path, "wb") as f:
        f.write(out_bytes)
    
    return {
        "ok": True,
        "batch_id": batch_id,
        "download_url": f"/api/passport/download/{batch_id}_print.jpg",
        "info": result["info"],
    }


# ── Download ──────────────────────────────────────────

@app.get("/api/passport/download/{filename}")
def download(filename: str):
    path = STORAGE_DIR / filename
    if not path.exists():
        raise HTTPException(404, "File not found")
    return FileResponse(str(path), media_type="image/jpeg")


# ── Bulk Generate ─────────────────────────────────────

@app.post("/api/passport/bulk-generate")
async def bulk_generate(req: BulkGenerateRequest):
    """Generate multiple passport photos in one request."""
    from .ai_passport import generate_passport
    from .gender_detector import detect_gender as _detect_gender
    from .clothing import get_clothing, get_background
    from .print_sheet import generate_print_sheet

    if not req.images:
        raise HTTPException(400, "No images provided")
    if len(req.images) > 20:
        raise HTTPException(400, "Max 20 images per batch")

    engine = _get_template_engine()
    template_info = engine.get(req.template_code)
    if not template_info:
        raise HTTPException(404, f"Template '{req.template_code}' not found")

    bg = get_background(req.background)
    results = []
    total_t0 = time.time()

    for i, img_b64 in enumerate(req.images):
        batch_id = uuid.uuid4().hex[:12]
        t0 = time.time()
        logger.info(f"[BULK {i+1}/{len(req.images)}] Processing...")

        try:
            img_bytes = base64.b64decode(img_b64)
        except Exception:
            results.append({"ok": False, "index": i, "error": "Invalid base64"})
            continue

        # Gender detection
        gender = req.gender
        gender_info = {"gender": gender, "confidence": 1.0}
        if gender == "auto":
            gender_info = _detect_gender(img_bytes)
            gender = gender_info["gender"]

        clothing = get_clothing(gender, req.clothing)

        # Generate passport photo
        result = generate_passport(
            img_bytes,
            template_info=template_info,
            clothing_prompt=clothing["prompt"],
            bg_prompt=bg["prompt"],
            strength=req.strength,
        )

        if not result["ok"]:
            results.append({"ok": False, "index": i, "error": result.get("error", "Failed")})
            continue

        # Save raw FLUX output (large, uncropped)
        out_img = result["result"]
        out_bytes = _encode_image(out_img)
        out_path = STORAGE_DIR / f"{batch_id}_passport.jpg"
        with open(out_path, "wb") as f:
            f.write(out_bytes)

        # No auto print sheet — raw image needs cropping first
        print_url = None

        elapsed = round(time.time() - t0, 1)
        results.append({
            "ok": True,
            "index": i,
            "session_id": batch_id,
            "download_passport": f"/api/passport/download/{batch_id}_passport.jpg",
            "download_print": print_url,
            "gender": gender,
            "clothing": clothing["name"],
            "time_seconds": elapsed,
        })
        logger.info(f"[BULK {i+1}/{len(req.images)}] Done in {elapsed}s — gender={gender}")

    total_elapsed = round(time.time() - total_t0, 1)
    success = sum(1 for r in results if r["ok"])
    logger.info(f"[BULK] Complete: {success}/{len(req.images)} in {total_elapsed}s")

    return {
        "ok": True,
        "total": len(req.images),
        "success": success,
        "failed": len(req.images) - success,
        "time_seconds": total_elapsed,
        "results": results,
    }


# ═══════════════════════════════════════════════════════════
# Gallery API
# ═══════════════════════════════════════════════════════════

@app.get("/api/passport/gallery")
def list_gallery(limit: int = 50, offset: int = 0):
    """List all passport photos in storage."""
    files = []
    for f in sorted(STORAGE_DIR.glob("*_passport.jpg"), key=lambda x: x.stat().st_mtime, reverse=True):
        sid = f.stem.replace("_passport", "")
        stat = f.stat()
        print_file = STORAGE_DIR / f"{sid}_print.jpg"
        flux_raw_file = STORAGE_DIR / f"{sid}_flux_raw.jpg"
        files.append({
            "session_id": sid,
            "filename": f.name,
            "url": f"/api/passport/download/{f.name}",
            "print_url": f"/api/passport/download/{sid}_print.jpg" if print_file.exists() else None,
            "flux_raw_url": f"/api/passport/download/{sid}_flux_raw.jpg" if flux_raw_file.exists() else None,
            "size_kb": round(stat.st_size / 1024, 1),
            "created": stat.st_mtime,
        })
    total = len(files)
    return {"ok": True, "total": total, "photos": files[offset:offset+limit]}


@app.get("/api/passport/gallery/{session_id}")
def get_gallery_photo(session_id: str):
    """Get one passport photo details."""
    passport = STORAGE_DIR / f"{session_id}_passport.jpg"
    if not passport.exists():
        raise HTTPException(404, "Photo not found")
    stat = passport.stat()
    print_file = STORAGE_DIR / f"{session_id}_print.jpg"
    return {
        "ok": True,
        "session_id": session_id,
        "url": f"/api/passport/download/{session_id}_passport.jpg",
        "print_url": f"/api/passport/download/{session_id}_print.jpg" if print_file.exists() else None,
        "size_kb": round(stat.st_size / 1024, 1),
        "created": stat.st_mtime,
    }


@app.delete("/api/passport/gallery/{session_id}")
def delete_gallery_photo(session_id: str):
    """Delete a passport photo."""
    deleted = []
    for suffix in ["_passport.jpg", "_print.jpg"]:
        p = STORAGE_DIR / f"{session_id}{suffix}"
        if p.exists():
            p.unlink()
            deleted.append(p.name)
    if not deleted:
        raise HTTPException(404, "Photo not found")
    return {"ok": True, "deleted": deleted}


@app.post("/api/passport/cleanup")
def cleanup_old_photos(days: int = 7):
    """Delete photos older than N days."""
    cutoff = time.time() - (days * 86400)
    deleted = []
    for f in STORAGE_DIR.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            f.unlink()
            deleted.append(f.name)
    logger.info(f"Cleanup: deleted {len(deleted)} files older than {days} days")
    return {"ok": True, "deleted_count": len(deleted), "files": deleted}


@app.post("/api/passport/recrop")
def recrop_photo(req: dict):
    """
    Re-crop a FLUX raw output with new crop parameters.
    Does NOT regenerate via FLUX — just re-crops the saved intermediate.
    
    Request: { "session_id": "...", "crop_y_pct": 0.08, "crop_x_pct": 0.17, ... }
    """
    session_id = req.get("session_id")
    if not session_id:
        raise HTTPException(400, "session_id required")
    
    storage = STORAGE_DIR
    flux_raw_path = storage / f"{session_id}_flux_raw.jpg"
    if not flux_raw_path.exists():
        raise HTTPException(404, f"FLUX raw output not found for {session_id}. Generate a photo first.")
    
    # Load FLUX raw output
    img = cv2.imread(str(flux_raw_path))
    if img is None:
        raise HTTPException(500, "Failed to read FLUX raw image")
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Build template with new crop params
    template = {
        "width_mm": req.get("width_mm", 35),
        "height_mm": req.get("height_mm", 45),
        "dpi": req.get("dpi", 300),
        "crop_x_pct": req.get("crop_x_pct", 0.17),
        "crop_y_pct": req.get("crop_y_pct", 0.08),
        "crop_w_pct": req.get("crop_w_pct", 0.66),
        "crop_h_pct": req.get("crop_h_pct", 0.65),
    }
    
    # Re-crop
    from .ai_passport import crop_to_template
    final = crop_to_template(img_rgb, template, template["dpi"])
    
    # Save new result
    out_bytes = _encode_image(final)
    out_path = STORAGE_DIR / f"{session_id}_passport.jpg"
    with open(out_path, "wb") as f:
        f.write(out_bytes)
    
    # Check headspace
    gray = cv2.cvtColor(final, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
    headspace_pct = 0
    if len(faces) > 0:
        headspace_pct = round(faces[0][1] / final.shape[0] * 100, 1)
    
    return {
        "ok": True,
        "session_id": session_id,
        "download_url": f"/api/passport/download/{session_id}_passport.jpg",
        "headspace_pct": headspace_pct,
        "size": f"{final.shape[1]}x{final.shape[0]}",
    }


# ═══════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info(f"Starting Passport Module V2 on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
