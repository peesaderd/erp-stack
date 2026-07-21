"""
Background Remover
==================
Uses rembg (U²-Net) to remove image backgrounds.
Falls back to OpenCV-based chroma-key if rembg fails.
"""

import logging
import numpy as np
import cv2
from PIL import Image
import io

logger = logging.getLogger("passport.bg_remover")


def remove_background(image: np.ndarray, fallback_color: str = "#FFFFFF") -> np.ndarray:
    """
    Remove background from image using rembg U²-Net.
    Falls back to OpenCV edge-based extraction if rembg fails.

    Args:
        image: RGB image as numpy array (H, W, 3)
        fallback_color: hex color for background in case of fallback

    Returns:
        RGBA image with transparent background, or RGB if fallback used
    """
    try:
        import rembg

        # Convert numpy -> PIL -> bytes for rembg
        pil_img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_RGB2RGBA))
        input_bytes = io.BytesIO()
        pil_img.save(input_bytes, format="PNG")
        input_bytes.seek(0)

        output_bytes = rembg.remove(input_bytes.read())
        output_pil = Image.open(io.BytesIO(output_bytes))
        output_arr = np.array(output_pil)  # RGBA

        logger.info("Background removed via rembg")
        return output_arr  # (H, W, 4) RGBA

    except Exception as e:
        logger.warning(f"rembg failed, using OpenCV fallback: {e}")
        return _fallback_remove_bg(image, fallback_color)


def _fallback_remove_bg(image: np.ndarray, bg_hex: str = "#FFFFFF") -> np.ndarray:
    """
    OpenCV-based fallback: edge detection + contour extraction.
    Less accurate than rembg but works for simple backgrounds.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Edge detection
    edges = cv2.Canny(blurred, 30, 100)
    kernel = np.ones((5, 5), np.uint8)
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    dilated = cv2.dilate(closed, kernel, iterations=2)

    # Find largest contour (assumed to be person)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        logger.warning("No contours found, returning original")
        # Return original with full opacity
        return cv2.cvtColor(image, cv2.COLOR_RGB2RGBA)

    largest = max(contours, key=cv2.contourArea)
    mask = np.zeros(gray.shape, dtype=np.uint8)
    cv2.drawContours(mask, [largest], -1, 255, -1)

    # Smooth mask edges
    mask = cv2.GaussianBlur(mask, (15, 15), 0)

    # Apply mask
    rgba = cv2.cvtColor(image, cv2.COLOR_RGB2RGBA)
    rgba[:, :, 3] = mask

    logger.info("Background removed via OpenCV fallback")
    return rgba


def replace_background(rgba: np.ndarray, bg_hex: str = "#FFFFFF") -> np.ndarray:
    """
    Composite RGBA image onto a solid background color.

    Args:
        rgba: (H, W, 4) image
        bg_hex: background color (e.g. "#FFFFFF")

    Returns:
        RGB image (H, W, 3) with solid background
    """
    if rgba.shape[2] == 3:
        return rgba

    bg_hex = bg_hex.lstrip("#")
    bg_rgb = tuple(int(bg_hex[i : i + 2], 16) for i in (0, 2, 4))

    h, w = rgba.shape[:2]
    bg = np.full((h, w, 3), bg_rgb, dtype=np.uint8)

    alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
    fg = rgba[:, :, :3].astype(np.float32)

    result = (fg * alpha + bg * (1 - alpha)).astype(np.uint8)
    return result
