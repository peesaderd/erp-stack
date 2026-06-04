"""
Etsy Wizard — AI Image Generation Pipeline
Supports multiple providers: Fal.ai, OpenAI, DeepInfra
Configurable via environment variables
"""

import os
import io
import base64
import json
import time
import logging
from typing import Optional
from enum import Enum

import requests
from PIL import Image as PILImage
import PIL.ImageDraw as PILImageDraw
import PIL.ImageFilter as PILImageFilter

logger = logging.getLogger("etsy-wizard.image_gen")

# ─── Provider Configuration ────────────────────────────────────────────

class ImageProvider(str, Enum):
    FAL = "fal"
    OPENAI = "openai"
    DEEPINFRA = "deepinfra"

PROVIDER_CONFIG = {
    ImageProvider.FAL: {
        "key": os.environ.get("FAL_KEY", "d0c3dc45-54ff-4363-ab83-bdc32e10af5b:ed8039106b88025957e3bbde7e72b4c8"),
        "models": {
            "fast": {"endpoint": "fal-ai/flux/schnell", "cost_per_image": 0.003},
            "quality": {"endpoint": "fal-ai/flux/dev", "cost_per_image": 0.025},
            "pro": {"endpoint": "fal-ai/flux-pro/v1.1", "cost_per_image": 0.05},
        },
        "default_model": "fast",
        "base_url": "https://fal.run",
    },
    ImageProvider.DEEPINFRA: {
        "key": os.environ.get("DEEPINFRA_API_KEY", ""),
        "models": {
            "fast": {"endpoint": "black-forest-labs/FLUX-1-schnell", "cost_per_image": 0.003},
            "quality": {"endpoint": "black-forest-labs/FLUX-1-dev", "cost_per_image": 0.025},
        },
        "default_model": "fast",
        "base_url": "https://api.deepinfra.com/v1/inference",
    },
}

UPSCALE_MODELS = {
    "clarity": {"endpoint": "fal-ai/clarity-upscaler", "cost": 0.01},
    "esrgan": {"endpoint": "fal-ai/esrgan", "cost": 0.003},
    "seedvr": {"endpoint": "fal-ai/seedvr/upscale/image", "cost": 0.02},
}

# Etsy requirements
ETSY_MIN_SIZE = 2000  # px minimum for main image
ETSY_RECOMMENDED_SIZE = 3000  # px recommended
ETSY_ASPECT_RATIO = 1.0  # 1:1 square
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

# Thai model base prompt
THAI_BASE_PROMPT = "Thai model, young Southeast Asian woman or man, soft natural lighting, authentic Thai lifestyle setting, warm skin tones"
VALID_ASPECT_RATIOS = {
    "1:1": "square_hd",
    "9:16": "portrait_16_9",
    "16:9": "landscape_16_9",
    "4:5": "portrait_4_3",
    "3:2": "landscape_4_3",
}

# ─── Fal.ai Client ─────────────────────────────────────────────────────

def fal_generate(
    prompt: str,
    model_tier: str = "fast",
    image_size: str = "square_hd",
    num_images: int = 1,
    timeout: int = 60,
    aspect_ratio: str = None,
) -> dict:
    """Generate images via Fal.ai"""
    provider = ImageProvider.FAL
    config = PROVIDER_CONFIG[provider]
    api_key = config["key"]

    if not api_key:
        raise ValueError("FAL_KEY not configured")

    model = config["models"].get(model_tier, config["models"][config["default_model"]])
    endpoint = f"{config['base_url']}/{model['endpoint']}"

    negative_prompt_default = "text, watermark, logo, signature, low quality, blurry, distorted, deformed, ugly, bad anatomy, bad proportions, extra limbs, cloned face, disfigured, gross proportions, malformed limbs, missing arms, missing legs, extra arms, extra legs, fused fingers, too many fingers, long neck, username, artist name, bad art, poorly drawn, mutation, deformed, boring, sketch, lacklutter, wrong colors, bad lighting, overexposed, underexposed"

    payload = {
        "prompt": prompt,
        "image_size": VALID_ASPECT_RATIOS.get(aspect_ratio, image_size),
        "num_images": num_images,
        "negative_prompt": negative_prompt_default,
    }

    # Extra params for quality/dev models
    if model_tier in ("quality", "pro"):
        payload["guidance_scale"] = 7.5
        payload["num_inference_steps"] = 28

    logger.info(f"Fal.ai generate: {model['endpoint']} | size={image_size} | n={num_images}")

    resp = requests.post(
        endpoint,
        headers={
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )

    if resp.status_code != 200:
        try:
            err = resp.json()
        except Exception:
            err = resp.text[:500]
        raise RuntimeError(f"Fal.ai error ({resp.status_code}): {err}")

    data = resp.json()
    images = data.get("images", [])
    if not images:
        raise RuntimeError("Fal.ai returned no images")

    result = {
        "provider": "fal",
        "model": model["endpoint"],
        "images": [],
        "seed": data.get("seed"),
        "cost": model["cost_per_image"] * num_images,
    }

    for img in images:
        result["images"].append({
            "url": img.get("url"),
            "width": img.get("width", 1024),
            "height": img.get("height", 1024),
            "content_type": img.get("content_type", "image/jpeg"),
        })

    return result


def fal_upscale(
    image_url: str,
    model_tier: str = "esrgan",
    scale_factor: Optional[int] = None,
    target_size: Optional[int] = ETSY_MIN_SIZE,
    timeout: int = 120,
) -> dict:
    """Upscale an image using Fal.ai upscale models"""
    config = UPSCALE_MODELS.get(model_tier, UPSCALE_MODELS["esrgan"])
    api_key = PROVIDER_CONFIG[ImageProvider.FAL]["key"]
    endpoint = f"https://fal.run/{config['endpoint']}"

    payload = {"image_url": image_url}
    if scale_factor:
        payload["scale"] = scale_factor

    logger.info(f"Fal.ai upscale: {config['endpoint']} | target={target_size}px")

    resp = requests.post(
        endpoint,
        headers={
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )

    if resp.status_code != 200:
        try:
            err = resp.json()
        except Exception:
            err = resp.text[:500]
        raise RuntimeError(f"Upscale error ({resp.status_code}): {err}")

    data = resp.json()
    # Some upscale models (esrgan, clarity) return {"image": {...}} instead of {"images": [...]}
    images = data.get("images", [])
    single = data.get("image")
    if not images and single:
        images = [single]

    if not images:
        raise RuntimeError(f"Upscale returned no images: {json.dumps(data)[:200]}")

    result = {
        "provider": "fal",
        "model": config["endpoint"],
        "cost": config["cost"],
        "images": [],
    }

    for img in images:
        result["images"].append({
            "url": img.get("url") or img.get("image_url", ""),
            "width": img.get("width", 0),
            "height": img.get("height", 0),
            "content_type": img.get("content_type", "image/jpeg"),
        })

    return result


def download_image(image_url: str, timeout: int = 30) -> bytes:
    """Download image from URL"""
    resp = requests.get(image_url, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def validate_etsy_image(image_bytes: bytes) -> dict:
    """
    Validate image against Etsy listing requirements
    Returns: {"valid": bool, "issues": [str], "width": int, "height": int}
    """
    issues = []
    img = PILImage.open(io.BytesIO(image_bytes))
    w, h = img.size

    result = {
        "valid": True,
        "width": w,
        "height": h,
        "format": img.format,
        "file_size_bytes": len(image_bytes),
        "issues": [],
    }

    # Size check (≥2000px for main image)
    if w < ETSY_MIN_SIZE or h < ETSY_MIN_SIZE:
        result["valid"] = False
        issues.append(f"Image too small: {w}x{h}, minimum {ETSY_MIN_SIZE}x{ETSY_MIN_SIZE}")

    # Aspect ratio check (should be square-ish for main listing)
    ratio = w / h if h > 0 else 0
    if ratio < 0.8 or ratio > 1.25:
        result["valid"] = False
        issues.append(f"Non-square aspect ratio: {w}x{h} ({ratio:.2f}), recommended 1:1")

    # File size check
    if len(image_bytes) > MAX_FILE_SIZE:
        issues.append(f"File too large: {len(image_bytes)/(1024*1024):.1f}MB, max 20MB")

    result["issues"] = issues
    result["valid"] = len(issues) == 0

    return result



def composite_product_into_scene(
    scene_image: PILImage.Image,
    product_image_url: str,
    product_id: str = None,
    position: str = "auto",
) -> PILImage.Image:
    """
    Professional product compositing — Gemini-reviewed, silent bugs fixed.

    Pipeline:
    1. Download product (24h cache) → rembg
    2. Position: Gemini bbox JSON (preferred) | OpenCV contour (fallback)
    3. Rotation warp (angle preserved, position NOT overwritten)
    4. Angle-aware drop shadow
    5. Mask-clipped per-channel RGB ambient blend (no edge glow)
    6. Edge feathering
    7. Compositing (single return path — NO variable confusion)
    8. QC validation
    """
    import io, json, os, hashlib, time, math
    import cv2
    import numpy as np

    product_id_str = product_id or "unknown"
    sw, sh = scene_image.size

    # ── Parse position (JSON bbox from Gemini) ──
    bbox = None
    if isinstance(position, str) and position.startswith("{"):
        try: bbox = json.loads(position)
        except: pass
    elif isinstance(position, dict):
        bbox = position

    # ── Step 1: Download product (cache-first, 24h TTL) ──
    CACHE_DIR = "/tmp/product_image_cache"
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_key = hashlib.md5(product_image_url.encode()).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.png")

    if os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path)) < 86400:
        product_img = PILImage.open(cache_path).convert("RGBA")
        logger.info(f"Cache HIT [{product_id_str}]")
    else:
        try:
            resp = requests.get(product_image_url, timeout=15)
            resp.raise_for_status()
            raw_product = PILImage.open(io.BytesIO(resp.content))
        except Exception as e:
            logger.warning(f"Download failed {product_image_url}: {e}")
            return scene_image
        if raw_product.mode != "RGBA":
            try:
                from rembg import remove as rembg_remove
                buf = io.BytesIO()
                raw_product.save(buf, format="PNG"); buf.seek(0)
                product_img = PILImage.open(io.BytesIO(rembg_remove(buf.read()))).convert("RGBA")
            except Exception as e:
                logger.warning(f"rembg failed ({e}), using raw")
                product_img = raw_product.convert("RGBA")
        else:
            product_img = raw_product.convert("RGBA")
        try: product_img.save(cache_path, "PNG")
        except: pass

    pw, ph = product_img.size
    if ph == 0:
        return scene_image

    # ── Step 2: Determine placement ──
    angle = 0.0
    if bbox:
        # Gemini-provided bounding box (preferred)
        bbox_x = bbox.get("x", (sw - int(pw * 0.4)) // 2)
        bbox_y = bbox.get("y", sh - int(sh * 0.5))
        bbox_w = bbox.get("width", int(pw * 0.4))
        bbox_h = bbox.get("height", int(ph * 0.4))
        angle = float(bbox.get("angle", 0))
        logger.info(f"Gemini bbox: ({bbox_x},{bbox_y}) {bbox_w}x{bbox_h} angle={angle}")
    else:
        # OpenCV fallback
        scene_arr = np.array(scene_image.convert("RGB"))
        scene_gray = cv2.cvtColor(scene_arr, cv2.COLOR_RGB2GRAY)
        dx = int(sw * 0.15)
        dy1 = int(sh * 0.30); dy2 = int(sh * 0.90)
        roi = scene_gray[dy1:dy2, dx:sw-dx]
        target_h = int(sh * 0.42)
        bbox_w = int(pw * target_h / ph)
        bbox_h = target_h
        bbox_x = (sw - bbox_w) // 2
        bbox_y = sh - bbox_h - int(sh * 0.10)
        blur = cv2.GaussianBlur(roi, (15, 15), 0)
        edges = cv2.Canny(blur, 30, 100)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            valid = [(c, cv2.contourArea(c), cv2.boundingRect(c)) for c in contours]
            valid = [(c, a, r) for c, a, r in valid if (sw*sh*0.01) < a < (sw*sh*0.3)
                     and (dy1 + r[1] + r[3]//2) > sh * 0.35
                     and 0.2 < r[2]/max(r[3],1) < 1.5]
            if valid:
                best = max(valid, key=lambda v: v[1])
                _, _, (bx, by, bw, bh) = best
                bbox_x = dx + bx; bbox_y = dy1 + by
                rect = cv2.minAreaRect(best[0])
                a = rect[2]
                angle = a if a >= -45 else 90 + a
                bbox_w = int(bw * 0.85); bbox_h = int(bh * 0.85)
                bbox_x += (bw - bbox_w) // 2; bbox_y += (bh - bbox_h) // 2
                logger.info(f"OpenCV fallback: ({bbox_x},{bbox_y}) angle={angle:.1f}")

    # ── Step 3: Resize + rotation warp ──
    # FIX #2: Use ORIGINAL bbox coordinates, accumulate offset, NEVER overwrite
    resize_w = max(bbox_w, 10)
    resize_h = max(bbox_h, 10)
    product_resized = product_img.resize((resize_w, resize_h), PILImage.LANCZOS)

    final_x = bbox_x
    final_y = bbox_y
    final_w = resize_w
    final_h = resize_h

    if abs(angle) > 3.0:
        prod_np = np.array(product_resized.convert("RGBA"))
        hp, wp = prod_np.shape[:2]
        center = (wp // 2, hp // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        cos_a = abs(M[0, 0]); sin_a = abs(M[0, 1])
        nw = int((hp * sin_a) + (wp * cos_a))
        nh = int((hp * cos_a) + (wp * sin_a))
        M[0, 2] += (nw / 2) - center[0]
        M[1, 2] += (nh / 2) - center[1]
        warped = cv2.warpAffine(prod_np, M, (nw, nh),
                                flags=cv2.INTER_LANCZOS4,
                                borderMode=cv2.BORDER_CONSTANT,
                                borderValue=(0, 0, 0, 0))
        product_resized = PILImage.fromarray(warped, "RGBA")
        # FIX #2: offset from original bbox, NOT overwrite
        offset_x = (nw - resize_w) // 2
        offset_y = (nh - resize_h) // 2
        final_x = bbox_x - offset_x
        final_y = bbox_y - offset_y
        final_w = nw; final_h = nh
        logger.info(f"Rotation {angle:.1f}°: offset=({offset_x},{offset_y})")

    # ── Step 4: Drop shadow ──
    scene_out = scene_image.convert("RGBA")
    try:
        shadow = PILImage.new("RGBA", (final_w, final_h), (0, 0, 0, 0))
        pa = product_resized.split()[3]
        shadow.paste((0, 0, 0, 140), (0, 0), pa)
        rad = math.radians(angle)
        sox = max(1, int(final_w * (0.03 * math.cos(rad) + 0.02)))
        soy = max(1, int(final_h * (0.04 * math.sin(rad) + 0.03)))
        shadow_blurred = shadow.filter(PILImageFilter.GaussianBlur(radius=max(5, final_w // 35)))
        scene_out.paste(shadow_blurred, (final_x + sox, final_y + soy), shadow_blurred)
    except Exception as e:
        logger.warning(f"Shadow failed: {e}")

    # ── Step 5: Mask-clipped per-channel RGB ambient blend ──
    # FIX #3: Only blend pixels within product mask, NOT the whole array
    try:
        sx = max(0, final_x - 30); sy = max(0, final_y - 60)
        ex = min(sw, final_x + final_w + 30); ey = max(0, final_y - 5)
        if ex > sx and ey > sy:
            sample = scene_out.crop((sx, sy, ex, ey))
            sample_arr = np.array(sample.convert("RGB")).astype(np.float32)
            mean_r = np.mean(sample_arr[:,:,0])
            mean_g = np.mean(sample_arr[:,:,1])
            mean_b = np.mean(sample_arr[:,:,2])

            prod_arr = np.array(product_resized.convert("RGB")).astype(np.float32)
            pa_np = np.array(product_resized.split()[3])
            mask = pa_np > 15  # FIX #3: higher threshold to exclude near-transparent edge pixels

            if mask.any():
                pr_r = np.mean(prod_arr[:,:,0][mask])
                pr_g = np.mean(prod_arr[:,:,1][mask])
                pr_b = np.mean(prod_arr[:,:,2][mask])

                ratio_r = max(0.7, min(1.35, mean_r / max(pr_r, 1)))
                ratio_g = max(0.7, min(1.35, mean_g / max(pr_g, 1)))
                ratio_b = max(0.7, min(1.35, mean_b / max(pr_b, 1)))

                # FIX #3: Blend ONLY masked pixels, copy unmasked as-is
                adj_r = np.where(mask, np.clip(prod_arr[:,:,0] * ratio_r, 0, 255), prod_arr[:,:,0]).astype(np.uint8)
                adj_g = np.where(mask, np.clip(prod_arr[:,:,1] * ratio_g, 0, 255), prod_arr[:,:,1]).astype(np.uint8)
                adj_b = np.where(mask, np.clip(prod_arr[:,:,2] * ratio_b, 0, 255), prod_arr[:,:,2]).astype(np.uint8)
                product_resized = PILImage.fromarray(
                    np.dstack([adj_r, adj_g, adj_b, pa_np]), "RGBA"
                )
                logger.info(f"Per-channel: R={ratio_r:.2f} G={ratio_g:.2f} B={ratio_b:.2f}")
    except Exception as e:
        logger.warning(f"Ambient blend skipped: {e}")

    # ── Step 6: Edge feathering ──
    try:
        feather = max(3, min(final_w, final_h) // 60)
        if feather > 0:
            edge_mask = PILImage.new("L", (final_w, final_h), 255)
            draw = PILImageDraw.Draw(edge_mask)
            for i in range(feather):
                a = int(255 * (i / feather))
                draw.rectangle([0, i, final_w, i + 1], fill=a)
                draw.rectangle([0, final_h - i - 1, final_w, final_h - i], fill=a)
                draw.rectangle([i, 0, i + 1, final_h], fill=a)
                draw.rectangle([final_w - i - 1, 0, final_w - i, final_h], fill=a)
            pa2 = product_resized.split()[3]
            ba = PILImage.composite(PILImage.new("L", (final_w, final_h), 0), pa2, edge_mask)
            product_resized.putalpha(ba)
    except Exception as e:
        logger.warning(f"Feathering failed: {e}")

    # ── Step 7: Composite (SINGLE paste, ONE return path) ──
    # FIX #1: One consistent variable — scene_out, no "composite" confusion
    scene_out.paste(product_resized, (final_x, final_y), product_resized)

    # ── Step 8: QC ──
    try:
        final_arr = np.array(scene_out.convert("RGB"))
        pa_qc = final_arr[final_y:final_y+final_h, final_x:final_x+final_w]
        logger.info(f"QC [{product_id_str}]: avg={np.mean(pa_qc):.0f} "
                    f"std={np.std(pa_qc):.0f} angle={angle:.1f} pos=({final_x},{final_y})")
    except Exception as e:
        logger.warning(f"QC failed: {e}")

    logger.info(f"Composite OK [{product_id_str}]: ({final_x},{final_y}) {final_w}x{final_h}")
    # FIX #1: Always return scene_out (the one true composited result)
    return scene_out



def generate_product_image(
    prompt: str,
    model_tier: str = "quality",
    upscale: bool = True,
    aspect_ratio: str = None,
    product_image_url: str = None,
    product_id: str = None,
) -> dict:
    """
    Full pipeline: generate → upscale → validate → composite
    If product_image_url is provided, composites real product over the generated scene.
    Returns finalized image info + validation
    """
    # Step 1: Generate
    gen_result = fal_generate(prompt, model_tier=model_tier, aspect_ratio=aspect_ratio)
    image_url = gen_result["images"][0]["url"]
    total_cost = gen_result["cost"]

    # Step 2: Download
    image_bytes = download_image(image_url)
    img = PILImage.open(io.BytesIO(image_bytes))
    w, h = img.size

    # Step 3: Upscale if needed
    if upscale and (w < ETSY_MIN_SIZE or h < ETSY_MIN_SIZE):
        upscaled = fal_upscale(image_url, model_tier="esrgan")
        upscaled_url = upscaled["images"][0]["url"]
        total_cost += upscaled["cost"]
        image_bytes = download_image(upscaled_url)
        image_url = upscaled_url

    # Step 4: Composite real product over AI-generated placeholder
    if product_image_url:
        img = PILImage.open(io.BytesIO(image_bytes))
        img = composite_product_into_scene(img, product_image_url, product_id=product_id)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()

    # Step 5: Validate
    validation = validate_etsy_image(image_bytes)

    return {
        "image_url": image_url,
        "image_bytes_base64": base64.b64encode(image_bytes).decode(),
        "width": validation["width"],
        "height": validation["height"],
        "validation": validation,
        "cost": total_cost,
        "provider": "fal",
    }


def make_etsy_compliant_prompt(product_name: str, description: str, style: str = "product", thai_model: bool = True) -> str:
    """
    Generate an Etsy-optimized image prompt
    Ensures: no watermark, no text, white/clean background, high quality
    """
    model_context = f", {THAI_BASE_PROMPT}" if thai_model else ""
    base = (
        f"{product_name}, {description}, "
        "e-commerce product photography, "
        "pure white background, clean studio lighting, "
        "no watermark, no text overlay, no logo, "
        "high detail, sharp focus, professional quality"
        f"{model_context}"
    )

    if style and style != "product":
        base += f", {style}"

    return base


# ─── DeepInfra Client (fallback) ───────────────────────────────────────

def deepinfra_generate(
    prompt: str,
    model_tier: str = "fast",
    num_images: int = 1,
    timeout: int = 60,
) -> dict:
    """Generate images via DeepInfra"""
    api_key = PROVIDER_CONFIG[ImageProvider.DEEPINFRA]["key"]
    if not api_key:
        raise ValueError("DEEPINFRA_API_KEY not configured")

    model = PROVIDER_CONFIG[ImageProvider.DEEPINFRA]["models"].get(
        model_tier,
        PROVIDER_CONFIG[ImageProvider.DEEPINFRA]["models"]["fast"]
    )
    endpoint = f"{PROVIDER_CONFIG[ImageProvider.DEEPINFRA]['base_url']}/{model['endpoint']}"

    payload = {
        "input": {"prompt": prompt},
    }

    if num_images > 1:
        payload["input"]["num_images"] = num_images

    logger.info(f"DeepInfra generate: {model['endpoint']}")

    resp = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )

    if resp.status_code != 200:
        try:
            err = resp.json()
        except Exception:
            err = resp.text[:500]
        raise RuntimeError(f"DeepInfra error ({resp.status_code}): {err}")

    data = resp.json()
    images = data.get("images", [])
    if not images:
        raise RuntimeError("DeepInfra returned no images")

    result = {
        "provider": "deepinfra",
        "model": model["endpoint"],
        "images": [],
        "cost": model["cost_per_image"] * num_images,
    }

    for img in images:
        result["images"].append({
            "url": img if isinstance(img, str) else img.get("url", ""),
            "width": 1024,
            "height": 1024,
            "content_type": "image/jpeg",
        })

    return result
