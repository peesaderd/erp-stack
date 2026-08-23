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
    from templates import engine
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
    from print_sheet import generate_print_sheet
    return generate_print_sheet(img, w_mm, h_mm, size, dpi, gap_mm, True, border, gap_mm, blade_mode, photo_count)


# ═══════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════

class GenerateRequest(BaseModel):
    image_base64: Optional[str] = None     # direct base64 (backward compat)
    session_id: Optional[str] = None       # upload session (preferred)
    template_code: str = "thai_passport"
    gender: str = "auto"           # "male" | "female" | "auto"
    clothing: str = "auto"         # clothing key, "auto", or "random"
    background: str = "light_blue" # "light_blue" | "white" | "light_gray" | "custom"
    background_color: Optional[str] = None   # custom hex color
    background_gradient: Optional[str] = None # CSS gradient string
    strength: float = 0.45         # FLUX i2i strength
    crop_preset: str = "standard"  # "standard" | "compact" | "relaxed"
    print_size: str = "4x6"        # "4x6" | "5x7" | "a6" | "a4"
    custom_clothing_base64: Optional[str] = None  # user's own outfit photo
    photo_count: int = 6           # total photos on print sheet (multi-sheet if > max)
    border: str = "frame"          # "none" | "guidelines" | "frame"
    blade_mode: bool = False
    gap_mm: float = 2.0
    border_color: str = "#FFFFFF"
    border_width_mm: float = 3.0

class BulkGenerateRequest(BaseModel):
    images: Optional[list] = None  # list of base64 strings (backward compat)
    bulk_sessions: Optional[list] = None  # list of session_ids (preferred)
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
    photo_size: str = "passport"  # "passport" | "25x35" | "30x40" | "50x50" | "50x70"
    photo_count: int = 6           # 0 = auto, >0 = how many photos total. If > max per sheet, multi-sheet concat.
    border: str = "none"           # "none" | "guidelines" | "frame" | "white"
    gap_mm: float = 2.0
    blade_mode: bool = False
    dpi: int = 300
    border_color: str = "#FFFFFF"
    border_width_mm: float = 3.0   # default 3mm frame


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

@app.get("/api/passport/options")
def get_all_options():
    """All options in one call: countries, clothing (both genders), backgrounds."""
    from clothing import list_clothing as _list_clothing, list_backgrounds as _list_bg
    engine = _get_template_engine()
    return {
        "ok": True,
        "templates": engine.get_all(),
        "clothing": {
            "male": _list_clothing("male"),
            "female": _list_clothing("female"),
        },
        "backgrounds": _list_bg(),
    }


@app.get("/api/passport/clothing")
def list_clothing(gender: str = "male"):
    from clothing import list_clothing as _list
    return {"ok": True, "gender": gender, "options": _list(gender)}

@app.get("/api/passport/backgrounds")
def list_backgrounds():
    from clothing import list_backgrounds as _list
    return {"ok": True, "options": _list()}


@app.post("/api/passport/upload")
async def upload_photo(file: UploadFile = File(...)):
    """Upload photo, save as session, detect gender. Returns session_id."""
    session_id = uuid.uuid4().hex[:12]
    img_bytes = await file.read()

    # Save original
    orig_path = STORAGE_DIR / f"{session_id}_original.jpg"
    with open(orig_path, "wb") as f:
        f.write(img_bytes)

    # Also save as passport.jpg (used by other endpoints)
    passport_path = STORAGE_DIR / f"{session_id}_passport.jpg"
    with open(passport_path, "wb") as f:
        f.write(img_bytes)

    # Gender detection
    try:
        from gender_detector import detect_gender as _detect
        result = _detect(img_bytes)
        gender = result.get("gender", "male")
    except Exception:
        gender = "male"

    logger.info(f"[{session_id}] Uploaded: {file.filename}, gender: {gender}")
    return {
        "ok": True,
        "session_id": session_id,
        "gender": gender,
        "filename": file.filename,
    }


@app.post("/api/passport/preview")
async def preview_photo(req: GenerateRequest):
    """Fast preview: client-side bg simulation is used for instant feedback; this endpoint
    validates the image + returns face/screenshot check WITHOUT burning a FLUX credit.
    Returns pass/fail + metadata so the UI can show a live preview badge."""
    from ai_passport import is_ui_screenshot
    import io as _io
    try:
        img_bytes = base64.b64decode(req.image_base64)
    except Exception:
        raise HTTPException(400, "Invalid base64")
    arr = np.frombuffer(img_bytes, np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        raise HTTPException(400, "Cannot decode image")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    is_ss, reason = is_ui_screenshot(rgb)
    try:
        from ai_passport import detect_face
        face = detect_face(rgb)
        face_info = None
        if face is not None:
            x, y, w, h = face
            face_info = {
                "x": int(x), "y": int(y), "w": int(w), "h": int(h),
                "headspace_pct": round(y / rgb.shape[0] * 100, 1),
            }
    except Exception:
        face_info = None
    return {
        "ok": True,
        "is_screenshot": is_ss,
        "screenshot_reason": reason if is_ss else None,
        "face": face_info,
        "size": {"w": rgb.shape[1], "h": rgb.shape[0]},
    }


# ── Gender Detection ──────────────────────────────────

@app.post("/api/passport/detect-gender")
async def detect_gender(image_base64: str = Form(...)):
    from gender_detector import detect_gender as _detect
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
    from ai_passport import generate_passport
    from gender_detector import detect_gender as _detect_gender
    from clothing import get_clothing, get_background

    session_id = uuid.uuid4().hex[:12]
    t0 = time.time()
    logger.info(f"[{session_id}] V2 Generate: template={req.template_code}, gender={req.gender}, clothing={req.clothing}")

    # Get template
    engine = _get_template_engine()
    template_info = engine.get(req.template_code)
    if not template_info:
        raise HTTPException(404, f"Template '{req.template_code}' not found")

    # Decode image — support both session_id (file) and image_base64
    if req.session_id:
        src_path = STORAGE_DIR / f"{req.session_id}_original.jpg"
        if not src_path.exists():
            src_path = STORAGE_DIR / f"{req.session_id}_passport.jpg"
        if not src_path.exists():
            raise HTTPException(404, f"Session not found: {req.session_id}")
        with open(src_path, "rb") as f:
            img_bytes = f.read()
        session_id = req.session_id  # reuse existing session
    elif req.image_base64:
        try:
            img_bytes = base64.b64decode(req.image_base64)
        except Exception:
            raise HTTPException(400, "Invalid base64")
    else:
        raise HTTPException(400, "Provide session_id or image_base64")

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

    # Decode custom clothing if provided
    custom_clothing_bytes = None
    if req.custom_clothing_base64:
        try:
            custom_clothing_bytes = base64.b64decode(req.custom_clothing_base64)
        except Exception:
            logger.warning("Invalid custom_clothing_base64, ignoring")

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
        custom_clothing_bytes=custom_clothing_bytes,
    )

    if not result["ok"]:
        raise HTTPException(500, result.get("error", "Generation failed"))

    # Save raw FLUX output (large, uncropped)
    out_img = result["result"]
    out_bytes = _encode_image(out_img)
    out_path = STORAGE_DIR / f"{session_id}_passport.jpg"
    with open(out_path, "wb") as f:
        f.write(out_bytes)

    # Auto-crop with preset — SQUARE mode (no forced passport ratio, no chin cut)
    crop_preset = req.crop_preset if req.crop_preset in ("standard", "compact", "relaxed") else "standard"
    try:
        from head_finder import crop_passport_auto
        crop_result = crop_passport_auto(out_img, preset=crop_preset, dpi=300, square=True)
        if crop_result["ok"]:
            cropped = crop_result["result"]
            crop_bytes = _encode_image(cropped)
            crop_path = STORAGE_DIR / f"{session_id}_cropped.jpg"
            with open(crop_path, "wb") as f:
                f.write(crop_bytes)
            crop_info = {
                "preset": crop_preset,
                "headspace": crop_result["headspace_in_crop"],
                "output": crop_result["output"],
            }
        else:
            crop_info = {"error": crop_result.get("error")}
    except Exception as e:
        logger.warning(f"Crop error: {e}")
        crop_info = {"error": str(e)}

    # Generate print sheet from cropped image
    print_info = None
    try:
        if crop_result and crop_result.get("ok"):
            from print_sheet import generate_print_sheet
            cropped = crop_result["result"]
            ch, cw = cropped.shape[:2]
            # Convert px to mm (assuming 300 DPI)
            mm_w = cw / 300 * 25.4
            mm_h = ch / 300 * 25.4

            # Probe max per sheet
            gap_mm = req.gap_mm if req.gap_mm else 2.0
            if req.blade_mode:
                gap_mm = max(gap_mm, 5.0)
            probe = generate_print_sheet(
                cropped, mm_w, mm_h, req.print_size, 300, gap_mm, True,
                req.border, gap_mm, req.blade_mode, 0,
                req.border_color, req.border_width_mm,
            )
            if probe.get("ok"):
                max_per_sheet = probe["info"]["max_count"]
                requested = req.photo_count if req.photo_count and req.photo_count > 0 else max_per_sheet
                if requested > max_per_sheet:
                    sheets = []
                    remaining = requested
                    while remaining > 0:
                        this_count = min(remaining, max_per_sheet)
                        r = generate_print_sheet(
                            cropped, mm_w, mm_h, req.print_size, 300, gap_mm, True,
                            req.border, gap_mm, req.blade_mode, this_count,
                            req.border_color, req.border_width_mm,
                        )
                        if r.get("ok"):
                            sheets.append(r["result"])
                        remaining -= this_count
                    gap = 20
                    total_h = sum(s.shape[0] for s in sheets) + gap * (len(sheets) - 1)
                    total_w = max(s.shape[1] for s in sheets)
                    combined = np.full((total_h, total_w, 3), 255, dtype=np.uint8)
                    y = 0
                    for s in sheets:
                        combined[y:y + s.shape[0], :s.shape[1]] = s
                        y += s.shape[0] + gap
                    sheet_bytes = _encode_image(combined)
                    probe["info"]["count"] = requested
                    probe["info"]["max_count"] = max_per_sheet
                    probe["info"]["sheets"] = len(sheets)
                    probe["info"]["multi_sheet"] = True
                else:
                    sheet = generate_print_sheet(
                        cropped, mm_w, mm_h, req.print_size, 300, gap_mm, True,
                        req.border, gap_mm, req.blade_mode, requested,
                        req.border_color, req.border_width_mm,
                    )
                    if sheet.get("ok"):
                        sheet_bytes = _encode_image(sheet["result"])
                        probe["info"]["multi_sheet"] = False
                with open(STORAGE_DIR / f"{session_id}_print.jpg", "wb") as f:
                    f.write(sheet_bytes)
                print_info = probe["info"]
    except Exception as e:
        logger.warning(f"Print sheet error: {e}")

    elapsed = round(time.time() - t0, 1)
    logger.info(f"[{session_id}] Done in {elapsed}s")

    return {
        "ok": True,
        "session_id": session_id,
        "download_passport": f"/api/passport/download/{session_id}_passport.jpg",
        "download_cropped": f"/api/passport/download/{session_id}_cropped.jpg",
        "download_print": f"/api/passport/download/{session_id}_print.jpg",
        "gender": gender,
        "gender_info": gender_info,
        "clothing": clothing["name"],
        "custom_clothing": custom_clothing_bytes is not None,
        "background": bg["name"],
        "print_info": print_info,
        "crop_info": crop_info,
        "dimensions_px": result["dimensions_px"],
        "face_info": result["info"].get("face_in_output"),
        "time_seconds": elapsed,
    }


# ── Remove Background ────────────────────────────────

class RemoveBgRequest(BaseModel):
    session_id: str
    background_color: str = "#C4DCFF"  # hex color

class ApplyBgRequest(BaseModel):
    session_id: str
    background_color: str = "#C4DCFF"

@app.post("/api/passport/remove-bg")
async def remove_bg(req: RemoveBgRequest):
    """Remove background and apply selected color.
    If transparent PNG already exists, skip Prodia (free color swap)."""
    transparent_path = STORAGE_DIR / f"{req.session_id}_transparent.png"
    from bg_remover import remove_background, apply_background
    
    if transparent_path.exists():
        # Already have transparent PNG — skip Prodia (FREE)
        logger.info(f"Reusing existing transparent PNG for {req.session_id}")
        pil_image = Image.open(transparent_path).convert('RGBA')
    else:
        # First time — call Prodia ($0.0025)
        # Prefer _passport.jpg (square, uncropped) — NOT _cropped.jpg (may have cut chin)
        src_path = STORAGE_DIR / f"{req.session_id}_passport.jpg"
        if not src_path.exists():
            src_path = STORAGE_DIR / f"{req.session_id}_cropped.jpg"
        if not src_path.exists():
            raise HTTPException(404, f"Session not found: {req.session_id}")
        with open(src_path, "rb") as f:
            img_bytes = f.read()
        try:
            transparent_png, pil_image = remove_background(img_bytes)
            with open(transparent_path, "wb") as f:
                f.write(transparent_png)
        except Exception as e:
            logger.error(f"Remove BG error: {e}")
            raise HTTPException(500, f"Background removal failed: {str(e)}")
    
    # Apply background color (PIL local = FREE)
    result_img = apply_background(pil_image, req.background_color)
    result_path = STORAGE_DIR / f"{req.session_id}_bg.jpg"
    result_img.save(result_path, "JPEG", quality=95)
    
    return {
        "ok": True,
        "session_id": req.session_id,
        "download_transparent": f"/api/passport/download/{req.session_id}_transparent.png",
        "download_bg": f"/api/passport/download/{req.session_id}_bg.jpg",
        "background_color": req.background_color,
    }

@app.post("/api/passport/apply-bg")
async def apply_bg(req: ApplyBgRequest):
    """Apply background color to existing transparent PNG (FREE, no Prodia)."""
    transparent_path = STORAGE_DIR / f"{req.session_id}_transparent.png"
    if not transparent_path.exists():
        raise HTTPException(404, "No transparent image. Run remove-bg first.")
    
    from bg_remover import apply_background
    pil_image = Image.open(transparent_path).convert('RGBA')
    result_img = apply_background(pil_image, req.background_color)
    result_path = STORAGE_DIR / f"{req.session_id}_bg.jpg"
    result_img.save(result_path, "JPEG", quality=95)
    
    return {
        "ok": True,
        "session_id": req.session_id,
        "download_bg": f"/api/passport/download/{req.session_id}_bg.jpg",
        "background_color": req.background_color,
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
    
    # Photo sizes in mm
    PHOTO_SIZES = {
        'passport': {'w': 35, 'h': 45},
        '25x35': {'w': 25, 'h': 35},
        '30x40': {'w': 30, 'h': 40},
        '50x50': {'w': 50, 'h': 50},
        '50x70': {'w': 50, 'h': 70},
    }
    
    # Get target photo size
    photo_size = PHOTO_SIZES.get(req.photo_size, PHOTO_SIZES['passport'])
    target_w_mm = photo_size['w']
    target_h_mm = photo_size['h']
    
    # Resize image to target size if needed
    current_w_mm = w / dpi * 25.4
    current_h_mm = h / dpi * 25.4
    
    if abs(current_w_mm - target_w_mm) > 1 or abs(current_h_mm - target_h_mm) > 1:
        # Resize to target size
        target_w_px = int(round(target_w_mm / 25.4 * dpi))
        target_h_px = int(round(target_h_mm / 25.4 * dpi))
        img_rgb = cv2.resize(img_rgb, (target_w_px, target_h_px), interpolation=cv2.INTER_LANCZOS4)
        mm_w = target_w_mm
        mm_h = target_h_mm
    else:
        mm_w = current_w_mm
        mm_h = current_h_mm

    from print_sheet import generate_print_sheet

    # First call to learn max_count per sheet
    probe = generate_print_sheet(
        img_rgb, mm_w, mm_h, req.print_size, dpi, req.gap_mm, True,
        req.border, req.gap_mm, req.blade_mode, 0,  # 0 = auto-fill one sheet
        req.border_color, req.border_width_mm,
    )
    if not probe["ok"]:
        raise HTTPException(400, probe.get("error", "Print sheet failed"))
    max_per_sheet = probe["info"]["max_count"]

    requested = req.photo_count if req.photo_count and req.photo_count > 0 else max_per_sheet
    if requested > max_per_sheet:
        # Multi-sheet: concat vertically
        sheets = []
        remaining = requested
        while remaining > 0:
            this_count = min(remaining, max_per_sheet)
            r = generate_print_sheet(
                img_rgb, mm_w, mm_h, req.print_size, dpi, req.gap_mm, True,
                req.border, req.gap_mm, req.blade_mode, this_count,
                req.border_color, req.border_width_mm,
            )
            if not r["ok"]:
                raise HTTPException(400, r.get("error", "Print sheet failed"))
            sheets.append(r["result"])
            remaining -= this_count
        # Concat vertically with small gap
        gap = 20
        total_h = sum(s.shape[0] for s in sheets) + gap * (len(sheets) - 1)
        total_w = max(s.shape[1] for s in sheets)
        combined = np.full((total_h, total_w, 3), 255, dtype=np.uint8)
        y = 0
        for s in sheets:
            combined[y:y + s.shape[0], :s.shape[1]] = s
            y += s.shape[0] + gap
        result_img = combined
        info = {
            **probe["info"],
            "count": requested,
            "max_count": max_per_sheet,
            "sheets": len(sheets),
            "multi_sheet": True,
        }
    else:
        # Single sheet
        result = generate_print_sheet(
            img_rgb, mm_w, mm_h, req.print_size, dpi, req.gap_mm, True,
            req.border, req.gap_mm, req.blade_mode, requested,
            req.border_color, req.border_width_mm,
        )
        if not result["ok"]:
            raise HTTPException(400, result.get("error", "Print sheet failed"))
        result_img = result["result"]
        info = result["info"]
        info["multi_sheet"] = False

    out_bytes = _encode_image(result_img)
    out_path = STORAGE_DIR / f"{req.session_id}_print.jpg"
    with open(out_path, "wb") as f:
        f.write(out_bytes)

    return {
        "ok": True,
        "session_id": req.session_id,
        "download_url": f"/api/passport/download/{req.session_id}_print.jpg",
        "info": info,
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
    from print_sheet import generate_multi_print_sheet
    
    if not req.session_ids:
        raise HTTPException(400, "No photos selected")
    if len(req.session_ids) > 20:
        raise HTTPException(400, "Max 20 photos")
    
    # Load all images — prefer cropped (35x45mm Thai passport), fall back to passport.jpg
    images = []
    dims = []
    for sid in req.session_ids:
        path = STORAGE_DIR / f"{sid}_cropped.jpg"
        if not path.exists():
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
    from ai_passport import generate_passport
    from gender_detector import detect_gender as _detect_gender
    from clothing import get_clothing, get_background
    from print_sheet import generate_print_sheet

    if not req.images and not req.bulk_sessions:
        raise HTTPException(400, "No images provided")
    if req.images and len(req.images) > 20:
        raise HTTPException(400, "Max 20 images per batch")
    if req.bulk_sessions and len(req.bulk_sessions) > 20:
        raise HTTPException(400, "Max 20 images per batch")

    engine = _get_template_engine()
    template_info = engine.get(req.template_code)
    if not template_info:
        raise HTTPException(404, f"Template '{req.template_code}' not found")

    bg = get_background(req.background)
    results = []
    total_t0 = time.time()

    # Build image list: from bulk_sessions or images
    image_list = []
    if req.bulk_sessions:
        for sid in req.bulk_sessions:
            src_path = STORAGE_DIR / f"{sid}_original.jpg"
            if not src_path.exists():
                src_path = STORAGE_DIR / f"{sid}_passport.jpg"
            if src_path.exists():
                with open(src_path, "rb") as f:
                    image_list.append((sid, f.read()))
            else:
                image_list.append((sid, None))
    elif req.images:
        for i, img_b64 in enumerate(req.images):
            try:
                image_list.append((uuid.uuid4().hex[:12], base64.b64decode(img_b64)))
            except Exception:
                image_list.append((uuid.uuid4().hex[:12], None))

    for idx, (sid, img_bytes) in enumerate(image_list):
        if img_bytes is None:
            results.append({"ok": False, "index": idx, "error": "Image not found"})
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
            results.append({"ok": False, "index": idx, "error": result.get("error", "Failed")})
            continue

        # Save raw FLUX output (large, uncropped)
        out_img = result["result"]
        out_bytes = _encode_image(out_img)
        out_path = STORAGE_DIR / f"{sid}_passport.jpg"
        with open(out_path, "wb") as f:
            f.write(out_bytes)

        # No auto print sheet — raw image needs cropping first
        print_url = None

        elapsed = round(time.time() - t0, 1)
        results.append({
            "ok": True,
            "index": idx,
            "session_id": sid,
            "download_passport": f"/api/passport/download/{sid}_passport.jpg",
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
        transparent_file = STORAGE_DIR / f"{sid}_transparent.png"
        bg_file = STORAGE_DIR / f"{sid}_bg.jpg"
        cropped_file = STORAGE_DIR / f"{sid}_cropped.jpg"
        files.append({
            "session_id": sid,
            "filename": f.name,
            "url": f"/api/passport/download/{f.name}",
            "print_url": f"/api/passport/download/{sid}_print.jpg" if print_file.exists() else None,
            "flux_raw_url": f"/api/passport/download/{sid}_flux_raw.jpg" if flux_raw_file.exists() else None,
            "transparent_url": f"/api/passport/download/{sid}_transparent.png" if transparent_file.exists() else None,
            "bg_url": f"/api/passport/download/{sid}_bg.jpg" if bg_file.exists() else None,
            "cropped_url": f"/api/passport/download/{sid}_cropped.jpg" if cropped_file.exists() else None,
            "has_transparent": transparent_file.exists(),
            "has_bg": bg_file.exists(),
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
    transparent_file = STORAGE_DIR / f"{session_id}_transparent.png"
    bg_file = STORAGE_DIR / f"{session_id}_bg.jpg"
    cropped_file = STORAGE_DIR / f"{session_id}_cropped.jpg"
    return {
        "ok": True,
        "session_id": session_id,
        "url": f"/api/passport/download/{session_id}_passport.jpg",
        "print_url": f"/api/passport/download/{session_id}_print.jpg" if print_file.exists() else None,
        "transparent_url": f"/api/passport/download/{session_id}_transparent.png" if transparent_file.exists() else None,
        "bg_url": f"/api/passport/download/{session_id}_bg.jpg" if bg_file.exists() else None,
        "cropped_url": f"/api/passport/download/{session_id}_cropped.jpg" if cropped_file.exists() else None,
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
    from ai_passport import crop_to_template
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
