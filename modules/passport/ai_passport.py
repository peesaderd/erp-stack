"""
AI Passport Photo Generator V2 — Prodia FLUX i2i
=================================================
Uses Prodia FLUX.2 Klein 4B img2i for passport photo generation.
Pipeline: Crop → FLUX i2i → Resize to template

Cost: $0.004/photo
"""

import os
import io
import json
import re
import time
import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
import urllib.request

logger = logging.getLogger("passport.ai")

# ── Config ─────────────────────────────────────────────
_erp_stack = Path(__file__).parent.parent.parent
_env_path = _erp_stack / ".env"

def _get_env(key):
    val = os.environ.get(key)
    if val:
        return val
    if _env_path.exists():
        for line in open(_env_path):
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None

PRODIA_TOKEN = _get_env("PRODIA_TOKEN")
PRODIA_API_URL = "https://inference.prodia.com/v2/job"

# ── FLUX i2i Prompt Template ──────────────────────────

def build_prompt(clothing_prompt: str, bg_prompt: str) -> str:
    """Build FLUX i2i prompt — v4 style, simple."""
    return (
        f"keep the person's face and appearance exactly as it is, "
        f"{clothing_prompt}, "
        f"{bg_prompt}, "
        f"bright even studio lighting, "
        f"straighten posture slightly, "
        f"show full head and shoulders, face not too large in frame, "
        f"passport ID photo style, government photo"
    )


# ── FLUX i2i Core ─────────────────────────────────────

def _parse_multipart_response(resp_data: bytes, ct: str):
    """Parse multipart response, return (json_job, image_bytes)."""
    job_info = None
    image_bytes = None

    boundary_match = re.search(r'boundary=([^\s;]+)', ct)
    if not boundary_match:
        if resp_data[:2] == b"\xff\xd8" or resp_data[:4] == b"\x89PNG":
            return None, resp_data
        return None, None

    boundary = boundary_match.group(1)
    parts = resp_data.split(f"--{boundary}".encode())

    for part in parts:
        if len(part) < 10:
            continue
        if part[:2] == b"\r\n":
            part = part[2:]
        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            continue
        headers_str = part[:header_end].decode("utf-8", errors="replace")
        body_bytes = part[header_end + 4:]
        if body_bytes.endswith(b"\r\n"):
            body_bytes = body_bytes[:-2]

        if "application/json" in headers_str:
            try:
                job_info = json.loads(body_bytes)
            except:
                pass
        elif body_bytes[:2] == b"\xff\xd8" or body_bytes[:4] == b"\x89PNG":
            image_bytes = body_bytes

    return job_info, image_bytes


def _compose_with_clothing(person: np.ndarray, clothing: np.ndarray) -> np.ndarray:
    """Side-by-side composite: person on left, clothing reference on right.
    Returns image with max dimension <= 1024 (FLUX input limit)."""
    person_h, person_w = person.shape[:2]
    cloth_h, cloth_w = clothing.shape[:2]
    scale = person_h / cloth_h
    cw2 = max(1, int(cloth_w * scale))
    cloth_w2 = min(cw2, int(person_w * 0.6))  # keep clothing panel smaller than person
    clothing_r = cv2.resize(clothing, (cloth_w2, person_h), interpolation=cv2.INTER_LANCZOS4)
    canvas = np.full((person_h, person_w + cloth_w2 + 8, 3), 240, dtype=np.uint8)
    canvas[:, :person_w] = person
    canvas[:, person_w + 8:] = clothing_r
    # Downscale to fit FLUX 1024 limit
    h, w = canvas.shape[:2]
    if max(h, w) > 1024:
        s = 1024 / max(h, w)
        canvas = cv2.resize(canvas, (int(w * s), int(h * s)), interpolation=cv2.INTER_LANCZOS4)
    return canvas


def flux_i2i(input_image: np.ndarray, prompt: str, strength: float = 0.30) -> np.ndarray:
    """
    Run FLUX i2i via Prodia API.
    
    Args:
        input_image: RGB numpy array
        prompt: text prompt
        strength: 0.0-1.0 (lower = more freedom to change composition/face size)
    
    Returns:
        RGB numpy array (output image)
    """
    if not PRODIA_TOKEN:
        raise RuntimeError("No PRODIA_TOKEN configured")

    # Encode input to JPEG bytes
    _, buf = cv2.imencode(".jpg", cv2.cvtColor(input_image, cv2.COLOR_RGB2BGR),
                          [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    input_bytes = buf.tobytes()

    BOUNDARY = "----ProdiaPassportV2"
    job_json = json.dumps({
        "type": "inference.flux-2.klein.4b.img2img.v1",
        "config": {
            "prompt": prompt,
            "steps": 4,
            "strength": strength,
        }
    })

    body = b""
    body += f"--{BOUNDARY}\r\n".encode()
    body += b'Content-Disposition: form-data; name="job"; filename="job.json"\r\n'
    body += b"Content-Type: application/json\r\n\r\n"
    body += job_json.encode()
    body += b"\r\n"
    body += f"--{BOUNDARY}\r\n".encode()
    body += b'Content-Disposition: form-data; name="input"; filename="image.jpg"\r\n'
    body += b"Content-Type: image/jpeg\r\n\r\n"
    body += input_bytes
    body += b"\r\n"
    body += f"--{BOUNDARY}--\r\n".encode()

    headers = {
        "Authorization": f"Bearer {PRODIA_TOKEN}",
        "Content-Type": f"multipart/form-data; boundary={BOUNDARY}",
        "Accept": "multipart/form-data",
    }

    req = urllib.request.Request(
        f"{PRODIA_API_URL}?price=true", data=body, headers=headers, method="POST"
    )
    resp = urllib.request.urlopen(req, timeout=120)
    resp_data = resp.read()
    ct = resp.headers.get("Content-Type", "")

    job_info, image_bytes = _parse_multipart_response(resp_data, ct)

    if job_info:
        state = job_info.get("state", {}).get("current", "unknown")
        price = job_info.get("price", {}).get("dollars", "N/A")
        logger.info(f"FLUX i2i: state={state}, price=${price}")

    if image_bytes:
        arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    raise RuntimeError("FLUX i2i returned no image")


# ── Face Detection ─────────────────────────────────────

def detect_face(image: np.ndarray) -> tuple:
    """Detect face, return (x, y, w, h) or None."""
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(80, 80))
    if len(faces) == 0:
        return None
    return max(faces, key=lambda f: f[2] * f[3])


def prepare_for_flux(image: np.ndarray) -> np.ndarray:
    """
    Prepare image for FLUX i2i: detect face, add generous padding.
    No ratio constraint — output largest possible with headroom.
    """
    face = detect_face(image)
    h, w = image.shape[:2]

    if face is None:
        # No face — just resize to max FLUX input (1024px)
        scale = 1024 / max(h, w)
        return cv2.resize(image, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LANCZOS4)

    x, y, fw, fh = face
    face_cx = x + fw // 2
    face_cy = y + fh // 2

    # Calculate padding: generous headroom + sides
    # Face should be ~20% of final height, centered horizontally
    # Add 3x face height above, 2x below, 2x on each side
    pad_top = int(fh * 5.0)
    pad_bottom = int(fh * 2.0)
    pad_side = int(fw * 2.0)

    # Expand canvas
    new_h = h + pad_top + pad_bottom
    new_w = w + pad_side * 2
    canvas = np.full((new_h, new_w, 3), (200, 200, 200), dtype=np.uint8)  # gray bg
    canvas[pad_top:pad_top + h, pad_side:pad_side + w] = image

    # Adjust face coordinates
    new_face_cx = face_cx + pad_side
    new_face_cy = face_cy + pad_top

    # Crop to square-ish with face centered, max 1024px
    crop_size = max(new_w, new_h)
    crop_size = min(crop_size, 1024)

    cx1 = max(0, new_face_cx - crop_size // 2)
    cy1 = max(0, new_face_cy - int(crop_size * 0.45))  # face at ~45% from top
    cx1 = min(cx1, new_w - crop_size)
    cy1 = min(cy1, new_h - crop_size)
    cx1 = max(0, cx1)
    cy1 = max(0, cy1)

    result = canvas[cy1:cy1 + crop_size, cx1:cx1 + crop_size]
    logger.info(f"prepare_for_flux: {result.shape[1]}x{result.shape[0]}, face centered with headroom")
    return result


# ── Resize to Template ─────────────────────────────────

def resize_to_template(img: np.ndarray, w_mm: float, h_mm: float, dpi: int = 300, generate_scale: float = 1.5) -> np.ndarray:
    """Scale image to fill template dimensions * generate_scale, ensure 20% headspace."""
    target_w = int(round(w_mm / 25.4 * dpi * generate_scale))
    target_h = int(round(h_mm / 25.4 * dpi * generate_scale))
    target_ratio = target_w / target_h

    h, w = img.shape[:2]
    orig_ratio = w / h

    if orig_ratio > target_ratio:
        new_h = target_h
        new_w = int(target_h * orig_ratio)
    else:
        new_w = target_w
        new_h = int(target_w / orig_ratio)

    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    # Detect face and ensure 20% headspace in the scaled image
    face = detect_face(img)
    if face is not None:
        fx, fy, fw, fh = face[0], face[1], face[2], face[3]
        # In final output (target_h / generate_scale), face top should be ≥20%
        # So in scaled image, face top should be ≥ 0.20 * target_h
        min_face_top_scaled = int(target_h * 0.20)
        if fy < min_face_top_scaled:
            # Face is too high — pad top with edge color to push face down
            pad = min_face_top_scaled - fy
            # Sample top edge for padding color
            pad_color = img[0, w // 2].tolist()
            pad_img = np.full((pad, new_w, 3), pad_color, dtype=np.uint8)
            img = np.vstack([pad_img, img])
            new_h += pad

    # Center crop to target size
    x = (new_w - target_w) // 2
    y = max(0, (new_h - target_h) // 2)
    return img[y:y + target_h, x:x + target_w]


def crop_to_template(img: np.ndarray, template: dict, dpi: int = 300) -> np.ndarray:
    """
    Crop the generated image to exact passport size.
    Guarantees ≥20% headspace (face top at ≥20% from top of final image).
    """
    target_w = int(round(template["width_mm"] / 25.4 * dpi))
    target_h = int(round(template["height_mm"] / 25.4 * dpi))
    
    h, w = img.shape[:2]
    
    # If already correct size, return as-is
    if w == target_w and h == target_h:
        return img
    
    face = detect_face(img)
    
    if face is not None:
        fx, fy, fw, fh = face[0], face[1], face[2], face[3]
        face_top = fy
        
        # Guarantee: face top must be at ≥20% from top of final crop
        min_head_y = int(target_h * 0.20)
        
        if face_top <= min_head_y:
            # Face is already high enough — crop from top, face will be ≥20%
            y_offset = 0
        else:
            # Face is too low — push crop down so face lands at 20%
            y_offset = face_top - min_head_y
        
        # Ensure we don't crop past image bottom
        y_offset = min(y_offset, h - target_h)
        y_offset = max(0, y_offset)
        
        face_center_x = fx + fw // 2
        x_offset = max(0, min(face_center_x - target_w // 2, w - target_w))
    else:
        x_offset = (w - target_w) // 2
        y_offset = int(target_h * 0.20)  # 20% headspace fallback
        y_offset = min(y_offset, h - target_h)
        y_offset = max(0, y_offset)
    
    x_offset = max(0, min(x_offset, w - target_w))
    
    cropped = img[y_offset:y_offset + target_h, x_offset:x_offset + target_w]
    
    # Verify headspace
    face_check = detect_face(cropped)
    if face_check is not None:
        actual_headspace = face_check[1] / target_h * 100
        logger.info(f"Crop: ({x_offset},{y_offset}) -> {target_w}x{target_h}, headspace={actual_headspace:.1f}%")
    else:
        logger.info(f"Crop: ({x_offset},{y_offset}) -> {target_w}x{target_h}, no face detected in crop")
    return cropped


# ═══════════════════════════════════════════════════════════
# Main Generation Function
# ═══════════════════════════════════════════════════════════

def is_ui_screenshot(image: np.ndarray) -> tuple:
    """
    Detect if image is a UI screenshot instead of a portrait photo.
    Returns (is_screenshot: bool, reason: str)
    """
    h, w = image.shape[:2]
    
    # Check 1: Landscape orientation (portrait photos are usually portrait)
    is_landscape = w > h * 1.2
    
    # Check 2: Horizontal sharp transitions (UI menus, toolbars)
    gray = image.mean(axis=2) if len(image.shape) == 3 else image.astype(float)
    row_means = gray.mean(axis=1)
    h_trans = sum(1 for i in range(1, len(row_means)) if abs(row_means[i] - row_means[i-1]) > 20)
    h_trans_pct = h_trans / h
    
    # Check 3: Uniform gray areas (UI panels)
    gray_pixels = 0
    total = h * w
    for y in range(0, h, max(1, h//50)):
        for x in range(0, w, max(1, w//50)):
            r, g, b = image[y, x]
            if 180 < r < 240 and abs(int(r) - int(g)) < 15 and abs(int(g) - int(b)) < 15:
                gray_pixels += 1
    gray_pct = gray_pixels / (min(h, 50) * min(w, 50))
    
    # Check 4: Face detection fails (no face = likely not a portrait)
    face = detect_face(image)
    has_face = face is not None
    
    # Decision
    if is_landscape and h_trans_pct > 0.08:
        return True, "Landscape image with UI-like horizontal patterns"
    if gray_pct > 0.65 and not has_face:
        return True, "Large uniform gray areas with no face detected"
    if is_landscape and not has_face and gray_pct > 0.4:
        return True, "Landscape image with no face and gray UI panels"
    
    return False, "OK"


def generate_passport(
    image_bytes: bytes,
    template_info: dict = None,
    clothing_prompt: str = "white formal dress shirt",
    bg_prompt: str = "soft light blue background",
    strength: float = 0.45,
    session_id: str = None,
    custom_clothing_bytes: bytes = None,
) -> dict:
    """
    Generate passport photo source using Prodia FLUX i2i.
    Output: large image with headroom, NO crop. Crop is a separate step.
    
    custom_clothing_bytes: optional photo of the outfit the person should wear.
    """
    t0 = time.time()
    info = {}

    # Load image
    arr = np.frombuffer(image_bytes, np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return {"ok": False, "error": "Invalid image"}
    original = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    # Screenshot validation
    is_ss, ss_reason = is_ui_screenshot(original)
    if is_ss:
        logger.warning(f"Input rejected: {ss_reason}")
        return {"ok": False, "error": f"This image appears to be a screenshot ({ss_reason}). Please upload a clear portrait photo of a person.", "is_screenshot": True}

    # Step 1: Prepare for FLUX (face detect + padding, no ratio constraint)
    logger.info("Step 1: Prepare for FLUX...")
    prepared = prepare_for_flux(original)
    info["prepared_size"] = [prepared.shape[1], prepared.shape[0]]

    # Step 1.5: Optional custom clothing — composite side-by-side with person
    custom_clothing = None
    if custom_clothing_bytes:
        try:
            arr_c = np.frombuffer(custom_clothing_bytes, np.uint8)
            bgr_c = cv2.imdecode(arr_c, cv2.IMREAD_COLOR)
            if bgr_c is not None:
                clothing_rgb = cv2.cvtColor(bgr_c, cv2.COLOR_BGR2RGB)
                prepared = _compose_with_clothing(prepared, clothing_rgb)
                info["custom_clothing"] = True
                logger.info("Custom clothing reference composited side-by-side")
        except Exception as e:
            logger.warning(f"Custom clothing composite failed: {e}")

    # Step 2: FLUX i2i (generate at full size)
    logger.info("Step 2: FLUX i2i...")
    if custom_clothing:
        prompt = build_prompt(
            "the person is wearing the exact outfit shown in the reference image on the right side, "
            "match the clothing style, colors and details precisely, "
            "the reference panel itself must not appear in the final photo",
            bg_prompt,
        )
    else:
        prompt = build_prompt(clothing_prompt, bg_prompt)
    generated = flux_i2i(prepared, prompt, strength)
    info["flux_size"] = [generated.shape[1], generated.shape[0]]

    # Detect face in output for later cropping reference
    face = detect_face(generated)
    if face is not None:
        fx, fy, fw, fh = face
        info["face_in_output"] = {
            "x": int(fx), "y": int(fy),
            "w": int(fw), "h": int(fh),
            "headspace_pct": round(fy / generated.shape[0] * 100, 1),
            "face_width_pct": round(fw / generated.shape[1] * 100, 1),
        }
        logger.info(f"Face in output: {fw}x{fh} at ({fx},{fy}), headspace={fy/generated.shape[0]*100:.0f}%")

    # Save raw FLUX output
    if session_id:
        storage = Path(__file__).parent / "storage"
        storage.mkdir(exist_ok=True)
        flux_raw_path = storage / f"{session_id}_flux_raw.jpg"
        try:
            cv2.imwrite(str(flux_raw_path), cv2.cvtColor(generated, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 95])
            info["flux_raw_saved"] = True
        except Exception as e:
            logger.warning(f"Failed to save FLUX raw: {e}")

    info["time_seconds"] = round(time.time() - t0, 1)
    info["strength"] = strength
    info["prompt"] = prompt

    logger.info(f"Done in {info['time_seconds']}s — {generated.shape[1]}x{generated.shape[0]}px (raw, no crop)")

    return {
        "ok": True,
        "result": generated,
        "info": info,
        "dimensions_px": {"w": generated.shape[1], "h": generated.shape[0]},
    }
