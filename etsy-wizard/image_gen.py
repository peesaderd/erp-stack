"""
Etsy Wizard — AI Image Prompt Helpers
Prodia Nano Banana img2img via modules/image service (port 8110)
"""

import logging
from PIL import Image as PILImage

logger = logging.getLogger("etsy-wizard.image_gen")

# ─── Etsy Requirements ─────────────────────────────────────────────────

ETSY_MIN_SIZE = 2000       # px minimum for main image
ETSY_RECOMMENDED_SIZE = 3000
ETSY_ASPECT_RATIO = 1.0    # 1:1 square
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

THAI_BASE_PROMPT = (
    "Thai model, young Southeast Asian woman or man, "
    "soft natural lighting, authentic Thai lifestyle setting, warm skin tones"
)

VALID_ASPECT_RATIOS = {
    "1:1": "square_hd",
    "9:16": "portrait_16_9",
    "16:9": "landscape_16_9",
    "4:5": "portrait_4_3",
    "3:2": "landscape_4_3",
}

# Export empty dict for backward compat with main.py import
UPSCALE_MODELS = {}
PROVIDER_CONFIG = {}


def make_etsy_compliant_prompt(
    product_name: str,
    description: str,
    style: str = "product",
    thai_model: bool = True,
) -> str:
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
