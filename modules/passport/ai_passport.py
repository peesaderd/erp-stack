"""
AI Passport Photo Generator v4 — Face Compositing
===================================================
Strategy:
  1. Send original image + editing prompt to Flux 2 klein 4B (multipart)
     → generates new person with correct clothing/background/framing
     (but the face is wrong — the AI imagines someone else)
  2. Extract ORIGINAL face from user's photo (center region where face is)
  3. Composite original face onto generated image with feather blending
  4. Resize to template dimensions

This guarantees the face is the ORIGINAL person while clothes/background change.
"""

import os
import sys
import json
import io
import logging
import base64
import time
import re
import uuid
from pathlib import Path

import requests
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

logger = logging.getLogger("passport.ai")

# ── Configuration ─────────────────────────────────────────
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

CF_TOKEN = os.environ.get("CF_WORKERS_AI_TOKEN", "") or _get_env("CLOUDFLARE_AI_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "") or _get_env("GOOGLE_API_KEY")
CF_ACCOUNT = "c4c9b706dc3b71a3a6304531834a23db"
CF_BASE = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run"

# ── Gemini Vision Analysis ────────────────────────────────

def _gemini_analyze(image_bytes: bytes) -> str:
    """Get detailed face description for prompting the AI."""
    if not GEMINI_KEY:
        logger.warning("No Gemini key")
        return ""
    try:
        import google.genai as genai
        client = genai.Client(api_key=GEMINI_KEY)
        prompt_text = (
            "Describe this person's appearance for an ID photo. "
            "Focus on FACE: shape, eyes, nose, lips, skin tone (hex-level), "
            "hair (color, length, style), facial hair. "
            "Also note: what clothing they're wearing now. "
            "Keep it concise (2-3 sentences max)."
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt_text, Image.open(io.BytesIO(image_bytes))],
        )
        desc = response.text.strip() if response.text else ""
        logger.info(f"Gemini analysis: {len(desc)} chars")
        return desc
    except Exception as e:
        logger.warning(f"Gemini failed: {e}")
        return ""

def _gemini_clothing(image_bytes: bytes) -> str:
    if not GEMINI_KEY:
        return ""
    try:
        import google.genai as genai
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                "Describe this clothing in extreme detail: style, exact color, collar type, neckline, fabric, formality, patterns.",
                Image.open(io.BytesIO(image_bytes)),
            ],
        )
        return response.text.strip()[:200] if response.text else ""
    except:
        return ""


# ── Cloudflare Flux txt2img ───────────────────────────────

def _flux_txt2img(prompt: str) -> bytes | None:
    """Generate image from text using Cloudflare Flux schnell."""
    if not CF_TOKEN:
        logger.warning("No Cloudflare token")
        return None
    try:
        if len(prompt) > 2040:
            prompt = prompt[:2040]
        r = requests.post(
            f"{CF_BASE}/@cf/black-forest-labs/flux-1-schnell",
            headers={"Authorization": f"Bearer {CF_TOKEN}"},
            json={"prompt": prompt},
            timeout=60,
        )
        if r.status_code != 200:
            err = r.json().get("errors", [{}])[0].get("message", "?")[:200]
            logger.error(f"Flux error {r.status_code}: {err}")
            return None
        try:
            jd = r.json()
            if "result" in jd and "image" in jd["result"]:
                raw = base64.b64decode(jd["result"]["image"])
                logger.info(f"Flux txt2img: {len(raw)} bytes")
                return raw
        except:
            pass
        ct = r.headers.get("content-type", "")
        if "image" in ct:
            return r.content
        logger.error(f"Flux: unexpected: {r.text[:200]}")
        return None
    except Exception as e:
        logger.error(f"Flux failed: {e}")
        return None


# ── Cloudflare Flux 2 klein 4B (editing mode) ─────────────

def _flux_edit(image_bytes: bytes, prompt: str) -> bytes | None:
    """Send image + prompt to Flux 2 klein via multipart."""
    if not CF_TOKEN:
        return None
    try:
        boundary = "----" + uuid.uuid4().hex
        body = b""
        body += f"--{boundary}\r\n".encode()
        body += b'Content-Disposition: form-data; name="prompt"\r\n'
        body += b"Content-Type: text/plain\r\n\r\n"
        body += prompt.encode()
        body += f"\r\n--{boundary}\r\n".encode()
        body += b'Content-Disposition: form-data; name="image"; filename="input.jpg"\r\n'
        body += b"Content-Type: image/jpeg\r\n\r\n"
        body += image_bytes
        body += f"\r\n--{boundary}--\r\n".encode()

        r = requests.post(
            f"{CF_BASE}/@cf/black-forest-labs/flux-2-klein-4b",
            headers={
                "Authorization": f"Bearer {CF_TOKEN}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
            data=body,
            timeout=120,
        )
        if r.status_code != 200:
            try:
                err = r.json().get("errors", [{}])[0].get("message", "?")[:300]
            except:
                err = r.text[:300]
            logger.error(f"Flux edit error {r.status_code}: {err}")
            return None
        try:
            jd = r.json()
            if "result" in jd and "image" in jd["result"]:
                raw = base64.b64decode(jd["result"]["image"])
                logger.info(f"Flux edit: {len(raw)} bytes")
                return raw
        except:
            pass
        ct = r.headers.get("content-type", "")
        if "image" in ct:
            return r.content
        return None
    except Exception as e:
        logger.error(f"Flux edit failed: {e}")
        return None


# ── Face Extraction & Compositing ─────────────────────────

def _extract_face_region(img: Image.Image) -> tuple:
    """
    Estimate the face region in a portrait photo.
    Returns (x, y, w, h) as pixel coordinates.
    Assumes photo is a headshot/selfie — face centered in upper portion.
    """
    w, h = img.size
    # Portrait: face occupies roughly center 40% width, top 50% height
    face_x = int(w * 0.3)
    face_y = int(h * 0.1)
    face_w = int(w * 0.4)
    face_h = int(h * 0.5)
    return (face_x, face_y, face_w, face_h)

def _create_feather_mask(size: tuple, face_box: tuple, feather_radius: int = 30) -> Image.Image:
    """
    Create a soft feathered mask for compositing the face.
    White = fully original face, Black = use generated image.
    Feather creates smooth transition at the boundary.
    """
    mask = Image.new("L", size, 0)  # black background
    draw = ImageDraw.Draw(mask)
    x, y, fw, fh = face_box
    
    # Draw white ellipse for face region
    draw.ellipse([x, y, x + fw, y + fh], fill=255)
    
    # Apply Gaussian blur for feathering
    if feather_radius > 0:
        mask = mask.filter(ImageFilter.GaussianBlur(radius=feather_radius))
    
    return mask

def _composite_face(original: Image.Image, generated: Image.Image) -> Image.Image:
    """
    Overlay the ORIGINAL face onto the AI-generated image.
    Uses feathered mask for smooth transition.
    Face is extracted from upper-center of original and composited.
    """
    # Both images should be same size
    gen = generated.copy()
    orig = original.copy()
    
    if gen.size != orig.size:
        orig = orig.resize(gen.size, Image.LANCZOS)
    
    # Extract face region bounds
    face_box = _extract_face_region(gen)
    
    # Create feathered mask
    mask = _create_feather_mask(gen.size, face_box, feather_radius=40)
    
    # Composite: original face on top of generated body
    result = Image.composite(orig, gen, mask)
    
    return result


# ── Post-processing ───────────────────────────────────────

def _resize_to_template(img: Image.Image, w_mm: float, h_mm: float, dpi: int = 300) -> Image.Image:
    """Scale image to fill template dimensions, center-crop if needed."""
    target_w = int(round(w_mm / 25.4 * dpi))
    target_h = int(round(h_mm / 25.4 * dpi))
    target_ratio = target_w / target_h
    
    orig_w, orig_h = img.size
    orig_ratio = orig_w / orig_h
    
    if orig_ratio > target_ratio:
        new_h = target_h
        new_w = int(target_h * orig_ratio)
    else:
        new_w = target_w
        new_h = int(target_w / orig_ratio)
    
    img = img.resize((new_w, new_h), Image.LANCZOS)
    x = (new_w - target_w) // 2
    y = (new_h - target_h) // 2
    img = img.crop((x, y, x + target_w, y + target_h))
    return img


# ═══════════════════════════════════════════════════════════
# Main Generation Function
# ═══════════════════════════════════════════════════════════

def generate_ai_passport(
    image_bytes: bytes,
    template_code: str = "thai_passport",
    template_info: dict = None,
    user_prompt: str = "",
    reference_image_bytes: bytes | None = None,
) -> dict:
    t0 = time.time()
    info = {"template_code": template_code}

    # ── Step 1: Template info ──
    bg_hex = "#FFFFFF"
    tpl_name = "passport"
    w_mm = 35
    h_mm = 45
    dpi = 300
    
    if template_info:
        bg_hex = template_info.get("bg_color", "#FFFFFF")
        tpl_name = template_info.get("name", "passport")
        w_mm = template_info.get("width_mm", 35)
        h_mm = template_info.get("height_mm", 45)
        dpi = template_info.get("dpi", 300)
    
    orientation = "landscape" if w_mm >= h_mm else "portrait"
    logger.info(f"  Template: {w_mm}x{h_mm}mm ({orientation}), DPI={dpi}")

    # ── Step 2: Analyze original face with Gemini ──
    logger.info("[AI v4] Analyzing original face with Gemini...")
    face_description = _gemini_analyze(image_bytes)
    info["gemini_chars"] = len(face_description)
    
    clothing_desc = ""
    if reference_image_bytes:
        clothing_desc = _gemini_clothing(reference_image_bytes)
        info["clothing_ref"] = clothing_desc[:100]
    
    # Load original image
    orig_img = Image.open(io.BytesIO(image_bytes))

    # ── Step 3: Clothing preset ──
    clothes = user_prompt if user_prompt else (clothing_desc[:150] if clothing_desc else "a formal white dress shirt with collar")

    # ── Step 4: Generate body/clothes/background with Flux ──
    # Strategy A: Use Flux 2 klein editing (sends original image as reference)
    # If it preserves the face → great. If not → face composite fallback (Strategy B).
    
    edit_prompt = (
        f"Edit this image into a passport photo. "
        f"Change clothing to {clothes}. "
        f"White background. Front view. Professional, high quality."
    )
    
    logger.info(f"[AI v4] Generating body with Flux editing...")
    result_bytes = _flux_edit(image_bytes, edit_prompt)

    if not result_bytes:
        # Fallback: use txt2img with face description
        logger.info("  Fallback: Flux txt2img with face description")
        txt_prompt = (
            f"Passport photo. {face_description[:300]} "
            f"Wearing {clothes}. White background, front view."
        )
        result_bytes = _flux_txt2img(txt_prompt)

    if not result_bytes:
        return {"ok": False, "error": "AI generation failed"}

    # ── Step 5: Decode AI output ──
    try:
        gen_img = Image.open(io.BytesIO(result_bytes)).convert("RGB")
    except Exception as e:
        return {"ok": False, "error": f"Failed to decode Flux output: {e}"}

    info["generated_size"] = gen_img.size

    # ── Step 6: Face compositing ──
    # Take the ORIGINAL face and overlay on the AI-generated body
    # This ensures the face is ALWAYS the original person
    logger.info("  Compositing original face onto generated body...")
    final = _composite_face(orig_img, gen_img)
    info["face_composite"] = True

    # ── Step 7: Resize to template ──
    final = _resize_to_template(final, w_mm, h_mm, dpi)

    # Fix colors
    if final.mode != "RGB":
        final = final.convert("RGB")

    info["final_size"] = final.size
    info["time_seconds"] = round(time.time() - t0, 1)
    info["orientation"] = orientation
    info["method"] = "flux_edit_face_composite"

    logger.info(f"[AI v4] Done in {info['time_seconds']}s — {final.size}")

    return {
        "ok": True,
        "result": final,
        "info": info,
        "dimensions_mm": {"w": w_mm, "h": h_mm},
        "dimensions_px": {"w": final.size[0], "h": final.size[1]},
    }
