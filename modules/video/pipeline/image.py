"""Image prompt & generation (Phase C split, move-only)."""
from ._shared import (  # noqa: F401
    os, re, sys, json, time, uuid, logging, random, subprocess, shutil, asyncio,
    Path, Optional, List, Dict, Any, requests,
    PRODIA_TOKEN, GEMINI_API_KEY, logger,
    IMAGE_GEN_URL, PROMPT_BUILDER_URL, STORAGE_DIR, TMP_DIR,
    get_default_style, get_style_config, validate_ugc_style, is_valid_style,
)

# ═══════════════════════════════════════════════════════════════════════════
# STEP 4: Build Image Prompt (Mistral)
# ═══════════════════════════════════════════════════════════════════════════

def build_image_prompt(
    product_name: str,
    product_profile: dict,
    recipe: dict,
) -> str:
    """
    Step 4: Build image prompt via Mistral

    Args:
        product_name: ชื่อสินค้า
        product_profile: ผลจาก analyze_product()
        recipe: ผลจาก load_recipe()

    Returns:
        str: image_prompt
    """
    logger.info(f"Step 4/9: Build image prompt (Mistral)")

    # ใช้ image_prompt ที่ได้จาก analyze_product() (Step 1)
    image_prompt = product_profile.get("_image_prompt", "")

    if image_prompt:
        logger.info(f"  Image prompt: {image_prompt[:60]}...")
        return image_prompt

    # NO hardcoded fallback — image prompt must come from prompt-builder (JSON).
    # Breaking loudly beats silently generating with a generic hardcoded prompt.
    raise ValueError(
        "build_image_prompt: '_image_prompt' missing from product_profile — "
        "prompt-builder (JSON-driven) must supply it; refusing hardcoded fallback"
    )

# ═══════════════════════════════════════════════════════════════════════════
# STEP 5: Generate Image (Prodia Nano Banana)
# ═══════════════════════════════════════════════════════════════════════════

def generate_image(
    prompt: str,
    product_image: str = None,
    aspect_ratio: str = "9:16",
    model: str = "nano-banana",
    placement: str = "hold",
) -> tuple:
    """
    Step 5: Generate image via Prodia.

    Args:
        prompt: image_prompt จาก Step 4
        product_image: URL ของรูปสินค้า (reference)
        aspect_ratio: 9:16 (TikTok portrait — owner direction, always 9:16)
        model: "nano-banana" (default) or "flux-2-klein" (klein 4B img2img)
        placement: "hold" | "place" | "place_and_hold" — hold-vs-place (owner 2026-09-12)

    Returns:
        tuple: (image_url, cost_usd)
    """
    logger.info(f"Step 5/9: Generate image ({model}, {aspect_ratio}, placement={placement})")
    logger.info(f"  Prompt: {prompt[:40]}...")
    logger.info(f"  Reference: {product_image or 'None'}")

    payload = {
        "prompt": prompt,
        "count": 1,
        "upscale": False,
        "aspectRatio": aspect_ratio,
        "model": model,
        "placement": placement,
    }

    if product_image:
        # 8110 (image-module) request schema: inputImage + model + style.
        payload["inputImage"] = product_image
        payload["style"] = "thai_realistic"

    last_exc = None
    for attempt in range(3):
        try:
            resp = requests.post(IMAGE_GEN_URL, json=payload, timeout=300)
            resp.raise_for_status()
            data = resp.json()

            if not (data.get("success") or data.get("ok")) or not data.get("images"):
                raise RuntimeError(f"Image-gen service failed: {data}")

            img_info = data["images"][0]
            url = img_info.get("full_url") or img_info.get("url")

            if not url:
                raise RuntimeError(f"No URL in response: {data}")

            # Extract cost from image service response (real pricing from prodia_pricing)
            cost_data = data.get("cost", {}) or img_info.get("cost", {})
            cost_usd = float(cost_data.get("dollars", 0.039) if isinstance(cost_data, dict) else 0.039)

            logger.info(f"  Image OK: {url[:60]}... | cost=${cost_usd:.4f}")
            return url, cost_usd

        except Exception as e:
            last_exc = e
            logger.warning(f"  Image gen attempt {attempt+1}/3 failed: {e}")
            if attempt < 2:
                logger.info(f"  Retrying image gen...")
                import time
                time.sleep(2)

    logger.error(f"Image generation failed after 3 attempts: {last_exc}")
    raise RuntimeError(f"Image generation failed after 3 attempts: {last_exc}")

# ═══════════════════════════════════════════════════════════════════════════
# STEP 5b: Generate Last (end-scene) image via FLUX.2 [klein] 4B
# Separate pipeline (NOT PassportPhoto). Takes the Nano Banana first-frame as
# input → produces a fresh 9:16 end-scene (Last) image from the SSOT blueprint.
# ═══════════════════════════════════════════════════════════════════════════

def _build_klein_last_prompt(profile: dict, product_name: str) -> str:
    """Build a 9:16 END-scene prompt for FLUX klein — LOCK-SCENE pattern.

    Owner direction (2026-08-24 15:21): the Last frame must stay in the SAME
    scene as the Nano Banana first frame (same woman / clothes / room) and
    change ONLY the pose: product goes from "held toward camera" → "placed
    down on the table, label facing camera" so Wan FL2V interpolates a
    natural put-down motion.
    Per owner-approved klein lesson (2026-08-23): do NOT re-describe
    outfit/scene/camera — klein 4B drifts when over-described. Only
    expression/result_focus still come from the SSOT end_scene blueprint.
    """
    es = (profile or {}).get("_end_scene")
    if not isinstance(es, dict):
        # fallback to a clean pick (binding happens in build_video_prompt normally)
        try:
            from prompt_builder import _pick_end_scene  # type: ignore
            cat = (profile or {}).get("category", "other")
            sub = (profile or {}).get("subcategory", "")
            es = _pick_end_scene(cat, subcategory=sub, profile=profile) or {}
        except Exception:
            es = {}

    gender = "woman" if (profile or {}).get("target_gender") == "female" else "man"
    _expr = es.get("expression") or "a relaxed, content smile"

    return (
        f"Vertical 9:16 portrait. The exact same {gender} as in the input image: keep her "
        f"face, hairstyle, makeup, clothes and the entire room/background EXACTLY identical "
        f"to the input image — do not redesign anything about her or the scene. "
        f"The product from the input image MUST remain clearly visible in this frame "
        f"too — same jar/product, same size and colors as the input image. "
        f"Only a subtle expression change: she continues holding the product steady\n"
        f"toward the camera in the exact same pose, same framing, same hand position —\n"
        f"product facing the camera, crisp and unclipped, label visible. No putting down,\n"
        f"no hand release, no pose change. "
        f"Lighting identical to the input image. Full-frame 9:16, no border, no padding."
    )

def generate_klein_last_image(
    first_frame_local: str,
    profile: dict,
    product_name: str = "",
    aspect_ratio: str = "9:16",
    run_id: str = ""
) -> tuple:
    """Generate the Last (end-scene) image via FLUX.2 [klein] 4B img2img.

    Uses the Nano Banana first-frame as input + the SSOT end-scene prompt.
    Our own klein pipeline (separate from PassportPhoto).

    Returns:
        tuple: (local_path, cost_usd)
    """
    logger.info(f"  ▶ Generate Last image via FLUX.2 klein 4B (from first-frame)")
    prompt = _build_klein_last_prompt(profile, product_name)

    # Send the local first-frame as a self-contained data URL so the image-module
    # can read it without depending on a served URL.
    try:
        import base64 as _b64
        with open(first_frame_local, "rb") as f:
            b64 = _b64.b64encode(f.read()).decode()
        input_ref = f"data:image/png;base64,{b64}"
    except Exception as e:
        logger.warning(f"  ⚠️ ใช้ path ตรงๆ แทน data URL ({e})")
        input_ref = first_frame_local

    img_url, cost_last = generate_image(
        prompt, input_ref, aspect_ratio=aspect_ratio, model="flux-2-klein",
    )
    last_path = TMP_DIR / f"klein_last_{run_id or 'x'}.png"
    download_file(img_url, last_path)
    logger.info(f"  ▶ Klein Last OK: {last_path.name} | cost=${cost_last:.4f}")
    return last_path, cost_last

# ═══════════════════════════════════════════════════════════════════════════
# STEP 6: Build Video Prompts (Mistral)
# ═══════════════════════════════════════════════════════════════════════════

def _clean_product_name_for_video(product_name: str) -> str:
    """Return generic 'product' for video prompts.
    
    Wan 2.7 may interpret product names as instructions.
    The reference image already shows the actual product.
    """
    return "product"

