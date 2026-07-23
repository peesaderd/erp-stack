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

def _fal_img2img(image_bytes: bytes, prompt: str, strength: float = 0.4) -> bytes | None:
    """
    Call fal.ai Flux dev image-to-image.
    Low strength (~0.4) preserves face identity while changing background/clothing.
    """
    if not FAL_KEY:
        logger.error("No FAL_KEY")
        return None

    try:
        # Upload image to get a URL that fal can use
        # fal accepts base64 directly in newer API versions
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

def _composite_background(img: Image.Image, bg_color: str = "#FFFFFF") -> Image.Image:
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, bg_color)
        bg.paste(img, mask=img.split()[3])
        return bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    return img


def _resize_to_template(img: Image.Image, w_mm: float, h_mm: float, dpi: int = 300) -> Image.Image:
    target_w = int(round(w_mm / 25.4 * dpi))
    target_h = int(round(h_mm / 25.4 * dpi))
    target_ratio = target_w / target_h
    orig_w, orig_h = img.size
    orig_ratio = orig_w / orig_h

    if abs(orig_ratio - target_ratio) > 0.01:
        if orig_ratio > target_ratio:
            new_w = int(orig_h * target_ratio)
            x = (orig_w - new_w) // 2
            img = img.crop((x, 0, x + new_w, orig_h))
        else:
            new_h = int(orig_w / target_ratio)
            y = (orig_h - new_h) // 2
            img = img.crop((0, y, orig_w, y + new_h))

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

    # ── Step 3: Generate with fal.ai img2img ──
    logger.info("[AI v2] Generating with fal.ai Flux img2img...")
    
    # Try with progressive strength
    strengths = [0.35, 0.45, 0.55]
    result_bytes = None
    
    for strength in strengths:
        logger.info(f"  Trying strength={strength}...")
        result_bytes = _fal_img2img(image_bytes, prompt, strength)
        if result_bytes:
            break
    
    if not result_bytes:
        return {"ok": False, "error": "AI image generation failed"}

    # ── Step 4: Decode + post-process ──
    try:
        img = Image.open(io.BytesIO(result_bytes))
    except Exception as e:
        return {"ok": False, "error": f"Failed to decode: {e}"}

    img = _composite_background(img, bg_hex)
    original_size = img.size

    dpi = template_info.get("dpi", 300) if template_info else 300
    w_mm = template_info.get("width_mm", 35) if template_info else 35
    h_mm = template_info.get("height_mm", 45) if template_info else 45
    img = _resize_to_template(img, w_mm, h_mm, dpi)

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
