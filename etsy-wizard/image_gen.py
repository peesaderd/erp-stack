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
    position: str = "center_bottom",
) -> PILImage.Image:
    """
    Composite a real product image over an AI-generated scene.

    The AI should have generated a hand holding a blank/placeholder container.
    This function replaces that blank container with the real product image.

    Args:
        scene_image: PIL Image from AI generation (hand + blank placeholder)
        product_image_url: URL to the real product PNG (with transparent bg)
        product_id: Optional product ID for logging
        position: Where to place the product ("center_bottom" default)

    Returns:
        PIL Image with product composited in
    """
    import requests
    import io
    import math

    product_id_str = product_id or "unknown"

    # Download product image
    try:
        resp = requests.get(product_image_url, timeout=15)
        resp.raise_for_status()
        product_img = PILImage.open(io.BytesIO(resp.content)).convert("RGBA")
        logger.info(f"Downloaded product image: {product_image_url} ({product_img.size})")
    except Exception as e:
        logger.warning(f"Failed to download product image {product_image_url}: {e}")
        return scene_image  # Return original scene as fallback

    scene = scene_image.convert("RGBA")
    sw, sh = scene.size

    # Calculate product size: fill roughly 30-40% of scene height
    target_height = int(sh * 0.45)
    pw, ph = product_img.size
    if ph == 0:
        return scene

    # Resize maintaining aspect ratio
    ratio = target_height / ph
    new_w = int(pw * ratio)
    new_h = target_height
    product_resized = product_img.resize((new_w, new_h), PILImage.LANCZOS)

    # Position: center-bottom (where hand is holding)
    x = (sw - new_w) // 2
    y = sh - new_h - int(sh * 0.08)  # 8% from bottom

    # Composite with alpha
    composite = scene.copy()
    composite.paste(product_resized, (x, y), product_resized)

    logger.info(f"Composite done: product at ({x},{y}), size {new_w}x{new_h} on scene {sw}x{sh}")
    return composite


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
