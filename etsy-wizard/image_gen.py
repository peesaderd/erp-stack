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
    AI-powered product compositing with perspective matching + position detection.

    Pipeline:
    1. Download product image with Cache-first strategy
    2. rembg auto background removal
    3. Use OpenCV to detect the "blank container" region in the scene
    4. Warp product to match perspective/angle of the detected region
    5. Generate realistic drop shadow with matching angle
    6. Edge feathering + light blending
    7. QC validation

    Instead of static paste, this detects WHERE in the scene the product
    should go (by detecting the placeholder region), then WARPS the product
    to match the perspective and angle of the hand.

    Falls back to center-bottom if detection fails.
    """
    import io
    import cv2
    import numpy as np
    import os, hashlib, time

    product_id_str = product_id or "unknown"
    sw, sh = scene_image.size

    # ── Step 1: Download product image (with Cache) ──
    CACHE_DIR = "/tmp/product_image_cache"
    os.makedirs(CACHE_DIR, exist_ok=True)

    # Cache key based on URL
    cache_key = hashlib.md5(product_image_url.encode()).hexdigest()
    cache_path = os.path.join(CACHE_DIR, f"{cache_key}.png")

    if os.path.exists(cache_path) and (time.time() - os.path.getmtime(cache_path)) < 86400:
        # Cache hit (within 24h)
        product_img = PILImage.open(cache_path).convert("RGBA")
        logger.info(f"Cache HIT [{product_id_str}]: {cache_path}")
    else:
        # Cache miss — download + rembg + save to cache
        try:
            resp = requests.get(product_image_url, timeout=15)
            resp.raise_for_status()
            raw_product = PILImage.open(io.BytesIO(resp.content))
            logger.info(f"Downloaded [{product_id_str}]: {raw_product.size} mode={raw_product.mode}")
        except Exception as e:
            logger.warning(f"Download failed {product_image_url}: {e}")
            return scene_image

        # rembg if no alpha
        if raw_product.mode != "RGBA":
            try:
                from rembg import remove as rembg_remove
                buf = io.BytesIO()
                raw_product.save(buf, format="PNG")
                buf.seek(0)
                result_bytes = rembg_remove(buf.read())
                product_img = PILImage.open(io.BytesIO(result_bytes)).convert("RGBA")
                logger.info(f"rembg OK [{product_id_str}]")
            except Exception as e:
                logger.warning(f"rembg failed ({e}), using raw")
                product_img = raw_product.convert("RGBA")
        else:
            product_img = raw_product.convert("RGBA")

        # Save to cache
        try:
            product_img.save(cache_path, "PNG")
            logger.info(f"Cached [{product_id_str}]: {cache_path}")
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")

    pw, ph = product_img.size
    if ph == 0:
        return scene_image

    scene_arr = np.array(scene_image.convert("RGB"))
    scene_gray = cv2.cvtColor(scene_arr, cv2.COLOR_RGB2GRAY)

    # ── Step 2: Detect placeholder region in scene ──
    # Strategy: find a blank/featureless region in the center-bottom area
    # where the hand is holding the product. The hand is typically in the
    # lower-center third of the image.
    
    detect_x_start = int(sw * 0.15)
    detect_x_end = int(sw * 0.85)
    detect_y_start = int(sh * 0.30)
    detect_y_end = int(sh * 0.90)

    # Look for the most homogeneous (low-texture) region = the blank placeholder
    roi = scene_gray[detect_y_start:detect_y_end, detect_x_start:detect_x_end]
    
    # Compute local variance map to find the blank area
    blur = cv2.GaussianBlur(roi, (15, 15), 0)
    variance = cv2.Laplacian(blur, cv2.CV_64F).var()
    
    # Try contour detection to find the blank container shape
    edges = cv2.Canny(blur, 30, 100)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    detected_rect = None
    detected_angle = 0
    # All product placement variables with defaults
    x = (sw - int(pw * (sh * 0.42) / ph)) // 2
    y = sh - int(sh * 0.42) - int(sh * 0.10)
    new_w = int(pw * (sh * 0.42) / ph)
    new_h = int(sh * 0.42)
    
    if contours:
        # Filter contours: find the one that's roughly in the right position/size
        valid = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < (sw * sh * 0.01):  # too small
                continue
            if area > (sw * sh * 0.35):  # too big (might be background)
                continue
            x_c, y_c, w_c, h_c = cv2.boundingRect(cnt)
            # Must be in the lower half roughly
            cy = detect_y_start + y_c + h_c // 2
            if cy < sh * 0.35:
                continue
            aspect = w_c / max(h_c, 1)
            # Product containers are typically 0.3-0.7 aspect ratio (taller than wide)
            valid.append((cnt, area, (x_c, y_c, w_c, h_c)))
        
        if valid:
            # Pick the largest valid contour
            best = max(valid, key=lambda v: v[1])
            _, _, (bx, by, bw, bh) = best
            detected_x = detect_x_start + bx
            detected_y = detect_y_start + by
            detected_w = bw
            detected_h = bh
            
            # Get angle via min area rectangle
            rect = cv2.minAreaRect(best[0])
            detected_angle = rect[2]
            # Normalize angle (OpenCV gives weird ranges)
            if detected_angle < -45:
                detected_angle = 90 + detected_angle
                
            logger.info(f"Detected placeholder: pos=({detected_x},{detected_y}) "
                        f"size={detected_w}x{detected_h} angle={detected_angle:.1f}°")
            
            # Size product to match detected region
            new_w = int(detected_w * 0.85)  # slightly smaller than detected area
            new_h = int(detected_h * 0.85)
            x = detected_x + (detected_w - new_w) // 2
            y = detected_y + (detected_h - new_h) // 2
        else:
            logger.info("No valid placeholder contour found, using default position")
    else:
        logger.info(f"No contours detected (variance={variance:.1f}), using default position")

    # ── Step 3: Resize product ──
    product_resized = product_img.resize((new_w, new_h), PILImage.LANCZOS)

    # ── Step 4: Perspective warp ──
    # If we detected an angle, warp the product to match
    scene_rgba = scene_image.convert("RGBA")
    
    if abs(detected_angle) > 3.0:
        # Warp product to match detected angle
        prod_np = np.array(product_resized.convert("RGBA"))
        h_p, w_p = prod_np.shape[:2]
        center = (w_p // 2, h_p // 2)
        M = cv2.getRotationMatrix2D(center, detected_angle, 1.0)
        
        # Compute new bounds after rotation
        cos = abs(M[0, 0])
        sin = abs(M[0, 1])
        new_w_warp = int((h_p * sin) + (w_p * cos))
        new_h_warp = int((h_p * cos) + (w_p * sin))
        M[0, 2] += (new_w_warp / 2) - center[0]
        M[1, 2] += (new_h_warp / 2) - center[1]
        
        warped = cv2.warpAffine(prod_np, M, (new_w_warp, new_h_warp), 
                                 flags=cv2.INTER_LANCZOS4,
                                 borderMode=cv2.BORDER_CONSTANT,
                                 borderValue=(0, 0, 0, 0))
        product_resized = PILImage.fromarray(warped, "RGBA")
        # Adjust position to center the warped product
        x -= (new_w_warp - new_w) // 2
        y -= (new_h_warp - new_h) // 2
        new_w, new_h = new_w_warp, new_h_warp
        logger.info(f"Perspective warp applied: angle={detected_angle:.1f}°")

    # ── Step 5: Generate drop shadow (angle-aware) ──
    try:
        shadow = PILImage.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
        product_alpha = product_resized.split()[3]
        shadow.paste((0, 0, 0, 160), (0, 0), product_alpha)
        # Shadow offset matches the detected angle
        rad = math.radians(detected_angle)
        sox = int(new_w * (0.03 * math.cos(rad) + 0.02))
        soy = int(new_h * (0.04 * math.sin(rad) + 0.03))
        sox = max(1, sox)
        soy = max(1, soy)
        shadow_blurred = shadow.filter(
            PILImageFilter.GaussianBlur(radius=max(5, new_w // 30))
        )
        scene_rgba.paste(shadow_blurred, (x + sox, y + soy), shadow_blurred)
    except Exception as e:
        logger.warning(f"Shadow failed: {e}")

    # ── Step 6: Edge feathering ──
    try:
        feather_px = max(3, min(new_w, new_h) // 60)
        if feather_px > 0:
            edge_mask = PILImage.new("L", (new_w, new_h), 255)
            draw = PILImageDraw.Draw(edge_mask)
            for i in range(feather_px):
                a = int(255 * (i / feather_px))
                draw.rectangle([0, i, new_w, i + 1], fill=a)
                draw.rectangle([0, new_h - i - 1, new_w, new_h - i], fill=a)
                draw.rectangle([i, 0, i + 1, new_h], fill=a)
                draw.rectangle([new_w - i - 1, 0, new_w - i, new_h], fill=a)
            pa = product_resized.split()[3]
            ba = PILImage.composite(
                PILImage.new("L", (new_w, new_h), 0), pa, edge_mask
            )
            product_resized.putalpha(ba)
    except Exception as e:
        logger.warning(f"Feathering failed: {e}")

    # ── Step 7: Ambient lighting blend ──
    try:
        sx, sy = max(0, x - 30), max(0, y - 60)
        ex, ey = min(sw, x + new_w + 30), max(0, y - 5)
        if ex > sx and ey > sy:
            sample = scene_rgba.crop((sx, sy, ex, ey))
            sample_arr = np.array(sample.convert("RGB"))
            scene_bright = np.mean(sample_arr)
            prod_arr = np.array(product_resized.convert("RGB"))
            pa_np = np.array(product_resized.split()[3])
            mask = pa_np > 10
            if mask.any():
                prod_bright = np.mean(prod_arr[mask])
                bright_ratio = scene_bright / max(prod_bright, 1)
                bright_ratio = max(0.7, min(1.35, bright_ratio))
                if abs(bright_ratio - 1.0) > 0.05:
                    adj = (prod_arr.astype(np.float32) * bright_ratio)
                    adj = np.clip(adj, 0, 255).astype(np.uint8)
                    product_resized = PILImage.fromarray(
                        np.dstack([adj, pa_np]), "RGBA"
                    )
                    logger.info(f"Ambient blend: ratio={bright_ratio:.2f}")
    except Exception as e:
        logger.warning(f"Ambient blend skipped: {e}")

    # ── Step 8: Composite ──
    scene_rgba.paste(product_resized, (x, y), product_resized)

    # ── Step 9: QC ──
    try:
        final_arr = np.array(scene_rgba.convert("RGB"))
        pa = final_arr[y:y+new_h, x:x+new_w]
        logger.info(f"QC [{product_id_str}]: brightness={np.mean(pa):.0f}, "
                    f"contrast={np.std(pa):.0f}, "
                    f"angle={detected_angle:.1f}°, "
                    f"pos=({x},{y})")
    except Exception as e:
        logger.warning(f"QC failed: {e}")

    logger.info(f"Composite OK [{product_id_str}]: ({x},{y}) {new_w}x{new_h}")
    return scene_rgba



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
