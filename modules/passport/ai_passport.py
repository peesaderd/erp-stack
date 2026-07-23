"""
AI Passport Photo Generator v3
================================
Pure AI-powered passport photo generation.
Uses Gemini vision + Cloudflare Flux text-to-image (txt2img).

Flow:
  1. Gemini vision → detailed face/clothing description
  2. Build prompt: face description + user clothing + template spec
  3. Cloudflare Flux txt2img → generate full passport photo (from scratch)
  4. Resize to template dimensions (no crop needed)
"""

import os
import sys
import json
import io
import logging
import base64
import time
import re
from pathlib import Path

import requests
import numpy as np
from PIL import Image

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

CF_TOKEN = _get_env("CF_WORKERS_AI_TOKEN") or _get_env("CLOUDFLARE_AI_TOKEN")
GEMINI_KEY = _get_env("GEMINI_API_KEY") or _get_env("GOOGLE_API_KEY")
CF_BASE = "https://api.cloudflare.com/client/v4/accounts/c4c9b706dc3b71a3a6304531834a23db/ai/run"

# ── Gemini Vision Analysis ────────────────────────────────

def _gemini_analyze(image_bytes: bytes, user_prompt: str = "") -> str:
    if not GEMINI_KEY:
        logger.warning("No Gemini key")
        return ""
    try:
        import google.genai as genai
        client = genai.Client(api_key=GEMINI_KEY)
        prompt_text = (
            "Describe this person's face in EXTREME DETAIL for an AI to recreate a passport photo. "
            "Include ALL of: face shape (oval/round/square/heart), forehead height/brow shape, "
            "eye color EXACT shade, eye shape/size, eyelid type, eyebrow shape and thickness, "
            "nose shape (wide/narrow/pointed/button), nose bridge height, "
            "lip shape (full/thin/wide), lip color tone, "
            "chin shape (pointed/rounded/square), jawline definition, "
            "cheekbone prominence, skin tone exact shade (warm/cool/olive/fair/medium/dark with hex-level precision), "
            "hair color EXACT shade, hair length, hair texture (straight/wavy/curly), hairstyle (parted/swept/combed), "
            "scalp/hairline, facial hair if any, "
            "distinguishing features (moles, freckles, scars, wrinkles, dimples), "
            "and current clothing style/shirt. "
            "Be extremely specific. VITAL for face recreation accuracy."
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
        return response.text.strip()[:300] if response.text else ""
    except:
        return ""

# ── Cloudflare Flux txt2img ────────────────────────────────

FLUX_MAX_PROMPT = 2040  # Cloudflare limit

def _flux_txt2img(prompt: str) -> bytes | None:
    if not CF_TOKEN:
        logger.error("No Cloudflare token")
        return None
    try:
        # Truncate to limit
        if len(prompt) > FLUX_MAX_PROMPT:
            prompt = prompt[:FLUX_MAX_PROMPT]
            logger.warning(f"Prompt truncated to {FLUX_MAX_PROMPT} chars")

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
        
        ct = r.headers.get("content-type", "")
        if "image" not in ct:
            logger.error(f"Flux returned non-image: {ct[:50]}")
            # Try parsing JSON anyway
            try:
                jd = r.json()
                if "result" in jd and "image" in jd["result"]:
                    import base64 as b64
                    return b64.b64decode(jd["result"]["image"])
            except:
                pass
            logger.error(f"Response: {r.text[:200]}")
            return None

        logger.info(f"Flux txt2img: {len(r.content)} bytes")
        return r.content

    except Exception as e:
        logger.error(f"Flux failed: {e}")
        return None

# ── Post-processing ───────────────────────────────────────

def _composite_background(img: Image.Image, bg_color: str = "#FFFFFF") -> Image.Image:
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, bg_color)
        bg.paste(img, mask=img.split()[3])
        return bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    return img

def _resize_to_template(img: Image.Image, w_mm: float, h_mm: float, dpi: int = 300, bg_color: str = "#FFFFFF") -> Image.Image:
    """Scale image to fill template dimensions, center-crop if needed."""
    target_w = int(round(w_mm / 25.4 * dpi))
    target_h = int(round(h_mm / 25.4 * dpi))
    target_ratio = target_w / target_h
    
    # First scale so the image covers the target (fill, not fit)
    orig_w, orig_h = img.size
    orig_ratio = orig_w / orig_h
    
    if orig_ratio > target_ratio:
        # Image is wider → scale to match height
        new_h = target_h
        new_w = int(target_h * orig_ratio)
    else:
        # Image is taller → scale to match width
        new_w = target_w
        new_h = int(target_w / orig_ratio)
    
    img = img.resize((new_w, new_h), Image.LANCZOS)
    
    # Center crop to exact target
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

    # ── Step 1: Gemini analyze face ──
    logger.info("[AI v3] Analyzing photo with Gemini...")
    description = _gemini_analyze(image_bytes, user_prompt)
    
    # Get clothing reference
    clothing_desc = ""
    if reference_image_bytes:
        clothing_desc = _gemini_clothing(reference_image_bytes)
        info["clothing_ref"] = clothing_desc[:100]

    # ── Step 2: Get template info ──
    bg_hex = template_info.get("bg_color", "#FFFFFF") if template_info else "#FFFFFF"
    tpl_name = template_info.get("name", "passport") if template_info else "passport"
    w_mm = template_info.get("width_mm", 35) if template_info else 35
    h_mm = template_info.get("height_mm", 45) if template_info else 45
    dpi = template_info.get("dpi", 300) if template_info else 300
    
    # Determine orientation
    if w_mm >= h_mm:
        orientation = "landscape"
    else:
        orientation = "portrait"
    
    logger.info(f"  Template: {w_mm}x{h_mm}mm ({orientation}), DPI={dpi}")

    # ── Step 3: Build prompt for Flux ──
    # Use SHORT face summary (Cloudflare Flux rejects long/verbose prompts)
    
    face_summary = ""
    if description:
        # Take first part only - key visual features, keep short
        face_summary = description[:200].split(".")[0] + "."
        # Remove any problematic words
        for bad in ["mole", "freckle", "scar", "wrinkle", "dimple"]:
            if bad in face_summary.lower():
                # Replace with neutral term
                face_summary = face_summary.replace(bad, "feature")
    
    # Short, clean prompt (under 500 chars)
    if user_prompt:
        clothes = user_prompt
    elif clothing_desc:
        clothes = clothing_desc[:100]
    else:
        clothes = "formal white shirt with collar"
    
    prompt = (
        f"Passport photo. {face_summary} "
        f"Wearing {clothes}. "
        f"White background, front view, centered, high quality."
    )
    
    logger.info(f"  Prompt ({len(prompt)} chars)")

    # ── Step 4: Generate with Flux txt2img ──
    logger.info("[AI v3] Generating with Cloudflare Flux txt2img...")
    result_bytes = _flux_txt2img(prompt)
    
    if not result_bytes:
        # Try with ultra-short prompt (skip face description)
        logger.info("  Retrying with ultra-short prompt...")
        clothes = user_prompt if user_prompt else "formal white shirt"
        short_prompt = f"Passport photo. A person wearing {clothes}. White background, front view."
        result_bytes = _flux_txt2img(short_prompt)
    
    if not result_bytes:
        return {"ok": False, "error": "AI generation failed after retry"}

    # ── Step 5: Decode + post-process ──
    try:
        img = Image.open(io.BytesIO(result_bytes))
    except Exception as e:
        return {"ok": False, "error": f"Failed to decode Flux output: {e}"}

    img = _composite_background(img, bg_hex)
    original_size = img.size
    
    # Resize to template
    img = _resize_to_template(img, w_mm, h_mm, dpi)

    info["prompt"] = prompt[:200]
    info["generated_size"] = original_size
    info["final_size"] = img.size
    info["time_seconds"] = round(time.time() - t0, 1)
    info["orientation"] = orientation
    info["method"] = "flux_txt2img"

    logger.info(f"[AI v3] Done in {info['time_seconds']}s — {img.size}")

    return {
        "ok": True,
        "result": img,
        "info": info,
        "dimensions_mm": {"w": w_mm, "h": h_mm},
        "dimensions_px": {"w": img.size[0], "h": img.size[1]},
    }
