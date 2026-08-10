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
    """Build FLUX i2i prompt from clothing + background."""
    return (
        f"keep the person's face exactly as it is, do not change facial features, "
        f"{clothing_prompt}, "
        f"{bg_prompt}, "
        f"bright even studio lighting, "
        f"remove acne and blemishes from skin, "
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


def flux_i2i(input_image: np.ndarray, prompt: str, strength: float = 0.65) -> np.ndarray:
    """
    Run FLUX i2i via Prodia API.
    
    Args:
        input_image: RGB numpy array
        prompt: text prompt
        strength: 0.0-1.0 (0.65 = preserve face, change clothing/bg)
    
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


def crop_passport(image: np.ndarray) -> np.ndarray:
    """Crop image to passport 35:45 ratio, centered on face."""
    face = detect_face(image)
    h, w = image.shape[:2]

    if face is None:
        # No face detected, center crop
        target_ratio = 35.0 / 45.0
        crop_h = int(h * 0.8)
        crop_w = int(crop_h * target_ratio)
        x1 = max(0, (w - crop_w) // 2)
        y1 = max(0, (h - crop_h) // 3)
        return cv2.resize(image[y1:y1 + crop_h, x1:x1 + crop_w], (354, 450), interpolation=cv2.INTER_LANCZOS4)

    x, y, fw, fh = face
    target_ratio = 35.0 / 45.0
    face_center_x = x + fw // 2
    face_center_y = y + fh // 2

    crop_h = int(fh / 0.40)
    crop_w = int(crop_h * target_ratio)

    crop_x1 = max(0, face_center_x - crop_w // 2)
    crop_y1 = max(0, int(face_center_y - crop_h * 0.30))

    if crop_x1 + crop_w > w: crop_x1 = w - crop_w
    if crop_y1 + crop_h > h: crop_y1 = h - crop_h
    crop_x1 = max(0, crop_x1)
    crop_y1 = max(0, crop_y1)

    cropped = image[crop_y1:crop_y1 + crop_h, crop_x1:crop_x1 + crop_w]
    return cv2.resize(cropped, (354, 450), interpolation=cv2.INTER_LANCZOS4)


# ── Resize to Template ─────────────────────────────────

def resize_to_template(img: np.ndarray, w_mm: float, h_mm: float, dpi: int = 300) -> np.ndarray:
    """Scale image to fill template dimensions, center-crop if needed."""
    target_w = int(round(w_mm / 25.4 * dpi))
    target_h = int(round(h_mm / 25.4 * dpi))
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
    x = (new_w - target_w) // 2
    y = (new_h - target_h) // 2
    return img[y:y + target_h, x:x + target_w]


# ═══════════════════════════════════════════════════════════
# Main Generation Function
# ═══════════════════════════════════════════════════════════

def generate_passport(
    image_bytes: bytes,
    template_info: dict = None,
    clothing_prompt: str = "white formal dress shirt",
    bg_prompt: str = "soft light blue background",
    strength: float = 0.65,
) -> dict:
    """
    Generate passport photo using Prodia FLUX i2i.
    
    Args:
        image_bytes: original photo as bytes
        template_info: template dict with width_mm, height_mm, dpi
        clothing_prompt: FLUX prompt for clothing
        bg_prompt: FLUX prompt for background
        strength: FLUX i2i strength (0.65 default)
    
    Returns:
        dict with ok, result (numpy), info, dimensions_mm, dimensions_px
    """
    t0 = time.time()
    info = {}

    # Template defaults
    w_mm = 35
    h_mm = 45
    dpi = 300
    if template_info:
        w_mm = template_info.get("width_mm", 35)
        h_mm = template_info.get("height_mm", 45)
        dpi = template_info.get("dpi", 300)

    # Load image
    arr = np.frombuffer(image_bytes, np.uint8)
    bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if bgr is None:
        return {"ok": False, "error": "Invalid image"}
    original = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    # Step 1: Crop to passport ratio
    logger.info("Step 1: Crop to passport ratio...")
    cropped = crop_passport(original)
    info["crop_size"] = [cropped.shape[1], cropped.shape[0]]

    # Step 2: FLUX i2i
    logger.info("Step 2: FLUX i2i...")
    prompt = build_prompt(clothing_prompt, bg_prompt)
    generated = flux_i2i(cropped, prompt, strength)
    info["flux_size"] = [generated.shape[1], generated.shape[0]]

    # Step 3: Resize to template
    logger.info("Step 3: Resize to template...")
    final = resize_to_template(generated, w_mm, h_mm, dpi)

    info["final_size"] = [final.shape[1], final.shape[0]]
    info["time_seconds"] = round(time.time() - t0, 1)
    info["strength"] = strength
    info["prompt"] = prompt

    logger.info(f"Done in {info['time_seconds']}s — {final.shape[1]}x{final.shape[0]}px")

    return {
        "ok": True,
        "result": final,
        "info": info,
        "dimensions_mm": {"w": w_mm, "h": h_mm},
        "dimensions_px": {"w": final.shape[1], "h": final.shape[0]},
    }
