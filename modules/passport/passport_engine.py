"""
Passport Photo Engine
=====================
Core processing pipeline:
1. Face detection → auto crop
2. Background removal → replace with template color
3. Resize to exact passport dimensions
4. Color/contrast normalization
"""

import logging
import cv2
import numpy as np
from PIL import Image

from . import background_remover as bg
from . import face_detector as fd
from .templates import engine as template_engine

logger = logging.getLogger("passport.engine")


def process_passport_photo(
    image: np.ndarray,
    template_code: str,
    auto_crop: bool = True,
    enhance: bool = True,
) -> dict:
    """
    Process an input image into a passport photo.

    Args:
        image: RGB numpy array (H, W, 3)
        template_code: e.g. "us_passport", "thai_passport"
        auto_crop: auto-detect face and crop
        enhance: apply color/contrast enhancement

    Returns:
        dict with:
            - ok: bool
            - result: processed RGB image (H, W, 3)
            - template: template dict used
            - info: processing metadata
    """
    template = template_engine.get(template_code)
    if not template:
        logger.error(f"Unknown template: {template_code}")
        return {"ok": False, "error": f"Unknown template: {template_code}"}

    info = {"template_code": template_code}
    result = image.copy()

    # ── 1. Auto-crop based on face ──────────────────────────────────
    if auto_crop:
        cropped, crop_info = fd.auto_crop_passport(result, template["head_height_pct"])
        result = cropped
        info["crop"] = crop_info

    # ── 2. Remove background → replace with template color ──────────
    rgba = bg.remove_background(result, template["bg_color"])
    result = bg.replace_background(rgba, template["bg_color"])
    info["bg_removed"] = True

    # ── 3. Resize to exact passport dimensions ──────────────────────
    target_w_px = int(round(template["width_mm"] / 25.4 * template["dpi"]))
    target_h_px = int(round(template["height_mm"] / 25.4 * template["dpi"]))

    if result.shape[1] != target_w_px or result.shape[0] != target_h_px:
        result = cv2.resize(result, (target_w_px, target_h_px), interpolation=cv2.INTER_LANCZOS4)
        info["resized_to"] = f"{target_w_px}x{target_h_px}"
    else:
        info["resized_to"] = "same"

    # ── 4. Enhance colors/contrast ──────────────────────────────────
    if enhance:
        result = _enhance_passport_photo(result)
        info["enhanced"] = True

    info["dimensions_px"] = {"w": target_w_px, "h": target_h_px}
    info["dimensions_mm"] = {"w": template["width_mm"], "h": template["height_mm"]}

    return {"ok": True, "result": result, "template": template, "info": info}


def _enhance_passport_photo(image: np.ndarray) -> np.ndarray:
    """Apply standard enhancements for passport photos."""
    # Convert to LAB for brightness/contrast adjustment
    lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)

    # CLAHE on L channel (local contrast)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l = clahe.apply(l)

    lab = cv2.merge([l, a, b])
    result = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

    # Subtle sharpening
    kernel = np.array([[-0.5, -0.5, -0.5],
                       [-0.5,  5.0, -0.5],
                       [-0.5, -0.5, -0.5]]) / 2.0
    result = cv2.filter2D(result, -1, kernel)

    return result
