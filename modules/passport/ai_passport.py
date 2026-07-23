"""
AI Passport Photo Generator v2
================================
Pure AI-powered passport photo generation.
Uses Gemini vision + fal.ai Flux image-to-image (img2img).
รักษาหน้าตาตัวจริงของผู้ใช้ไว้ได้ 

Flow:
  1. Gemini vision → analyze uploaded photo
  2. Gemini vision → analyze reference clothing photo (optional)
  3. Merge with user prompt
  4. fal.ai Flux img2img → transform photo (keep face, change bg/clothes)
  5. Resize/crop to template dimensions
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

FAL_KEY = _get_env("FAL_KEY")
GEMINI_KEY = _get_env("GEMINI_API_KEY") or _get_env("GOOGLE_API_KEY")

FAL_BASE = "https://fal.run"

# ── Gemini Vision Analysis ────────────────────────────────

def _gemini_analyze(image_bytes: bytes, user_prompt: str = "") -> str:
    """Analyze photo with Gemini and return detailed description."""
    if not GEMINI_KEY:
        logger.warning("No Gemini key")
        return _default_description(user_prompt)

    try:
        import google.genai as genai
        client = genai.Client(api_key=GEMINI_KEY)

        prompt_text = (
            "Describe this person in DETAIL for a passport photo. "
            "Include: gender, approximate age, hair color and exact style, "
            "skin tone, face shape, eye color, distinctive features, "
            "current clothing. Be specific. Keep response under 500 chars."
        )
        if user_prompt:
            prompt_text += f"\nUser wants: {user_prompt}\n"

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt_text, Image.open(io.BytesIO(image_bytes))],
        )
        desc = response.text.strip()
        logger.info(f"Gemini: {len(desc)} chars")
        return desc
    except Exception as e:
        logger.warning(f"Gemini failed: {e}")
        return _default_description(user_prompt)


def _gemini_analyze_clothing(image_bytes: bytes) -> str:
    """Analyze reference clothing photo."""
    if not GEMINI_KEY:
        return ""
    try:
        import google.genai as genai
        client = genai.Client(api_key=GEMINI_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                "Describe this clothing in detail: style, color, collar, formality. Be specific, keep under 200 chars.",
                Image.open(io.BytesIO(image_bytes)),
            ],
        )
        return response.text.strip() if response.text else ""
    except:
        return ""


def _default_description(user_prompt: str = "") -> str:
    if user_prompt:
        return f"a person, {user_prompt}"
    return "a person, front-facing portrait"


# ── fal.ai Flux Image-to-Image ────────────────────────────

def _fal_img2img(image_bytes: bytes, prompt: str, strength: float = 0.4, image_size: str = None) -> bytes | None:
    """
    Call fal.ai Flux dev image-to-image.
    Low strength (~0.4) preserves face identity while changing background/clothing.
    image_size: 'square_hd'|'square'|'portrait_4_3'|'portrait_16_9'|'landscape_4_3'|'landscape_16_9'
    """
    if not FAL_KEY:
        logger.error("No FAL_KEY")
        return None

    try:
        img_b64 = base64.b64encode(image_bytes).decode()

        url = f"{FAL_BASE}/fal-ai/flux/dev/image-to-image"
        
        payload = {
            "image_url": f"data:image/jpeg;base64,{img_b64}",
            "prompt": prompt,
            "strength": strength,
            "guidance_scale": 7.5,
            "num_inference_steps": 28,
            "seed": 42,
            "enable_safety_checker": False,
            "output_format": "jpeg",
        }
        
        if image_size:
            payload["image_size"] = image_size

        logger.info(f"fal.ai img2img: strength={strength}, prompt={prompt[:100]}...")
        
        r = requests.post(
            url,
            headers={
                "Authorization": f"Key {FAL_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )

        if r.status_code != 200:
            logger.error(f"fal.ai error {r.status_code}: {r.text[:300]}")
            return None

        result = r.json()
        
        # Response contains image URL
        img_url = result.get("image", {}).get("url") or result.get("images", [{}])[0].get("url")
        if not img_url:
            logger.error(f"fal.ai: no image URL in response: {json.dumps(result)[:300]}")
            return None

        # Download the result
        img_r = requests.get(img_url, timeout=30)
        if img_r.status_code != 200:
            logger.error(f"Failed to download fal result: {img_r.status_code}")
            return None

        logger.info(f"fal.ai done: {len(img_r.content)} bytes")
        return img_r.content

    except Exception as e:
        logger.error(f"fal.ai failed: {e}")
        return None


# ── Post-processing ───────────────────────────────────────

def _parse_hex_color(hex_str: str) -> tuple:
    """Parse '#FFFFFF' to (255, 255, 255)."""
    h = hex_str.lstrip("#")
    try:
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except:
        return (255, 255, 255)


def _composite_background(img: Image.Image, bg_color: str = "#FFFFFF") -> Image.Image:
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, bg_color)
        bg.paste(img, mask=img.split()[3])
        return bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    return img


def _pad_to_aspect(img: Image.Image, target_w_mm: float, target_h_mm: float, bg_color: str = "#FFFFFF") -> Image.Image:
    """
    Pad image to match template aspect ratio before AI generation.
    This way fal.ai generates at the correct aspect ratio.
    """
    target_ratio = target_w_mm / target_h_mm
    w, h = img.size
    current_ratio = w / h
    
    if abs(current_ratio - target_ratio) < 0.01:
        return img
    
    bg_rgb = _parse_hex_color(bg_color)
    
    if current_ratio > target_ratio:
        # Image is too wide → pad top/bottom
        new_h = int(w / target_ratio)
        canvas = Image.new("RGB", (w, new_h), bg_rgb)
        y = (new_h - h) // 2
        canvas.paste(img, (0, y))
    else:
        # Image is too tall → pad left/right
        new_w = int(h * target_ratio)
        canvas = Image.new("RGB", (new_w, h), bg_rgb)
        x = (new_w - w) // 2
        canvas.paste(img, (x, 0))
    
    return canvas


def _fit_to_template(img: Image.Image, w_mm: float, h_mm: float, dpi: int = 300, bg_color: str = "#FFFFFF") -> Image.Image:
    """
    Scale to exact template pixel dimensions (assumes img already has correct ratio).
    """
    target_w = int(round(w_mm / 25.4 * dpi))
    target_h = int(round(h_mm / 25.4 * dpi))
    img = img.resize((target_w, target_h), Image.LANCZOS)
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

    # ── Step 1: Analyze ──
    logger.info("[AI v2] Analyzing photo...")
    description = _gemini_analyze(image_bytes, user_prompt)
    info["description"] = description[:200]

    # Analyze reference clothing
    clothing_desc = ""
    if reference_image_bytes:
        clothing_desc = _gemini_analyze_clothing(reference_image_bytes)
        info["clothing_ref"] = clothing_desc[:100]

    # ── Step 2: Build prompt ──
    bg_hex = template_info.get("bg_color", "#FFFFFF") if template_info else "#FFFFFF"
    bg_name = {"#FFFFFF": "white", "#F0F0F0": "light gray", "#0000FF": "blue",
               "#FF0000": "red", "#ADD8E6": "light blue"}.get(bg_hex.upper(), "white")
    template_name = template_info.get("name", "passport") if template_info else "passport"

    # Base clothing description
    if not clothing_desc:
        if "wearing" not in description.lower() and user_prompt:
            clothing_desc = f", {user_prompt}"
        elif "wearing" not in description.lower():
            clothing_desc = ", wearing formal business attire, collared shirt"

    prompt = (
        f"Professional passport photo. EXACTLY the same person, keep face IDENTICAL. "
        f"{bg_name} background, studio lighting, front-facing, centered, neutral expression. "
        f"High quality, realistic photo, sharp focus. NO BEAUTIFICATION, no makeup changes. "
        f"Keep original skin texture, wrinkles, and facial features. "
    )
    
    if user_prompt:
        prompt += f"User request: {user_prompt}. "
    if clothing_desc:
        prompt += f"Clothing: {clothing_desc}."

    # ── Step 3: Get template dimensions and pad input to match ──
    w_mm = template_info.get("width_mm", 35) if template_info else 35
    h_mm = template_info.get("height_mm", 45) if template_info else 45
    dpi = template_info.get("dpi", 300) if template_info else 300
    logger.info(f"  Template {w_mm}x{h_mm}mm @ {dpi}dpi")

    # Pad input image to template aspect ratio before AI gen
    input_img = Image.open(io.BytesIO(image_bytes))
    padded = _pad_to_aspect(input_img, w_mm, h_mm, bg_hex)
    logger.info(f"  Padded input: {input_img.size} → {padded.size}")
    
    # Re-encode padded image for fal.ai
    pad_buf = io.BytesIO()
    padded.save(pad_buf, format="JPEG", quality=95)
    padded_bytes = pad_buf.getvalue()

    # ── Step 4: Generate with fal.ai img2img ──
    logger.info("[AI v2] Generating with fal.ai Flux img2img...")
    
    strengths = [0.35, 0.45, 0.55]
    result_bytes = None
    
    for strength in strengths:
        logger.info(f"  Trying strength={strength}...")
        result_bytes = _fal_img2img(padded_bytes, prompt, strength)
        if result_bytes:
            break
    
    if not result_bytes:
        return {"ok": False, "error": "AI image generation failed"}

    # ── Step 5: Decode + resize to exact template ──
    try:
        img = Image.open(io.BytesIO(result_bytes))
    except Exception as e:
        return {"ok": False, "error": f"Failed to decode: {e}"}

    img = _composite_background(img, bg_hex)
    original_size = img.size

    img = _fit_to_template(img, w_mm, h_mm, dpi, bg_hex)

    info["prompt"] = prompt[:200]
    info["generated_size"] = original_size
    info["final_size"] = img.size
    info["time_seconds"] = round(time.time() - t0, 1)

    logger.info(f"[AI v2] Done in {info['time_seconds']}s — {img.size}")

    return {
        "ok": True,
        "result": img,
        "info": info,
        "dimensions_mm": {"w": w_mm, "h": h_mm},
        "dimensions_px": {"w": img.size[0], "h": img.size[1]},
    }
