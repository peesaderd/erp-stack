"""
Etsy Wizard — AI Image Generation Service
==========================================
Generate artwork for POD products via Prodia Nano Banana (port 8110)
Future: switch to Fal.ai when FAL_KEY available
"""

import logging
import requests
from typing import Optional

logger = logging.getLogger("etsy-wizard.image_service")

PRODIA_SERVICE_URL = "http://localhost:8110/api/v1/image/generate"


def generate_artwork(
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    input_image: Optional[str] = None,
    aspect_ratio: str = "1:1",
    timeout: int = 120,
) -> Optional[dict]:
    """
    Generate artwork/design via Prodia Nano Banana (img2img)
    
    Args:
        prompt: คำอธิบาย artwork
        width/height: ขนาด artwork (px) — ควรตรง print area
        input_image: URL รูป reference (optional, สำหรับ img2img)
        aspect_ratio: "1:1" | "9:16" | "16:9"
    
    Returns:
        {"image_url": "...", "width": ..., "height": ..., "cost": ...}
    """
    try:
        payload = {
            "prompt": prompt,
            "aspectRatio": aspect_ratio,
            "width": width,
            "height": height,
        }
        if input_image:
            payload["inputImage"] = input_image

        logger.info(f"Generating artwork via Prodia: {prompt[:60]}... @ {width}x{height}")
        resp = requests.post(
            PRODIA_SERVICE_URL,
            json=payload,
            timeout=timeout,
        )
        if resp.status_code != 200:
            logger.error(f"Prodia error ({resp.status_code}): {resp.text[:200]}")
            return None

        data = resp.json()
        images = data.get("images", [])
        if not images:
            logger.error("Prodia returned no images")
            return None

        img_url = images[0].get("url", "") if isinstance(images[0], dict) else images[0]

        return {
            "image_url": img_url,
            "width": width,
            "height": height,
            "provider": "prodia",
            "cost": data.get("cost", {}).get("dollars", 0),
            "prompt_used": prompt,
        }
    except requests.Timeout:
        logger.error(f"Prodia timeout ({timeout}s)")
        return None
    except Exception as e:
        logger.error(f"Artwork generation failed: {e}")
        return None


def generate_etsy_artwork(
    product_id: str,
    product_name: str,
    description: str,
    print_area_width: int,
    print_area_height: int,
    style: str = "minimal",
) -> Optional[dict]:
    """
    Generate artwork sized for the product's print area
    
    สร้าง prompt ที่เหมาะสม + gen รูปขนาด print area
    """
    # Map sizes to aspect ratio
    ratio = print_area_width / print_area_height if print_area_height > 0 else 1.0
    if abs(ratio - 1.0) < 0.1:
        aspect = "1:1"
    elif ratio > 1.0:
        aspect = "16:9"
    else:
        aspect = "9:16"

    prompt = (
        f"Create a beautiful {style} print design for a {product_name}, "
        f"theme: {description}, "
        "high quality vector art style, clean lines, "
        "centered composition, transparent background, "
        "no mockup, no product, design only, "
        "print-ready artwork with 0.5 inch bleed"
    )

    # ใช้ print area dimensions (แต่ clamp เพื่อไม่ให้ Prodia reject)
    gen_width = min(print_area_width, 2048)
    gen_height = min(print_area_height, 2048)

    return generate_artwork(
        prompt=prompt,
        width=gen_width,
        height=gen_height,
        aspect_ratio=aspect,
    )
