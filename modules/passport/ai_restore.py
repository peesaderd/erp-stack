"""
AI Face Restoration Module
==========================
Uses GFPGAN for face restoration + OpenCV enhancements.
Run on CPU (CUDA not available).
"""

import os
import logging
import time
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger("passport.ai_restore")

# Lazy-loaded GFPGAN
_restorer = None

GFPGAN_MODEL_PATH = os.path.expanduser("~/.cache/gfpgan/GFPGANv1.4.pth")


def _init_restorer():
    global _restorer
    if _restorer is not None:
        return True

    if not os.path.exists(GFPGAN_MODEL_PATH):
        logger.warning(f"GFPGAN model not found at {GFPGAN_MODEL_PATH}")
        return False

    try:
        logger.info("Loading GFPGAN (this may take 30-60s on CPU)...")
        t0 = time.time()
        # Fix: ensure stdlib 'profile' module is found before erp-stack's 'profile' package
        import sys, importlib
        if 'profile' in sys.modules:
            del sys.modules['profile']
        # Remove erp-stack modules from path when importing gfpgan
        _erp_stack = str(Path(__file__).parent.parent.parent)
        _saved_paths = [p for p in sys.path if _erp_stack in p]
        for p in _saved_paths:
            if p in sys.path:
                sys.path.remove(p)
        try:
            from gfpgan import GFPGANer
        finally:
            # Restore paths
            sys.path = _saved_paths + sys.path
            _erp_stack = None
        _restorer = GFPGANer(
            model_path=GFPGAN_MODEL_PATH,
            upscale=1,
            arch='clean',
            channel_multiplier=2,
            bg_upsampler=None,
        )
        logger.info(f"GFPGAN loaded in {time.time()-t0:.1f}s")
        return True
    except Exception as e:
        logger.error(f"Failed to load GFPGAN: {e}")
        return False


def ai_denoise_and_enhance(image: np.ndarray, strength: float = 0.7) -> np.ndarray:
    """
    Apply GFPGAN face restoration + OpenCV denoising to the entire image.
    """
    result = image.copy()
    info = {}

    # Step 1: Try GFPGAN face restoration
    gfpgan_ok = _init_restorer()
    if gfpgan_ok:
        try:
            t0 = time.time()
            _, _, enhanced = _restorer.enhance(
                result, has_aligned=False, only_center_face=False, paste_back=True
            )
            if enhanced is not None and enhanced.shape == result.shape:
                # Blend with original based on strength
                result = cv2.addWeighted(enhanced, strength, result, 1 - strength, 0)
                info["gfpgan"] = True
                logger.info(f"GFPGAN enhancement done ({time.time()-t0:.1f}s)")
            else:
                logger.warning(f"GFPGAN returned mismatched shape: {enhanced.shape if enhanced is not None else 'None'}")
        except Exception as e:
            logger.warning(f"GFPGAN error (non-fatal): {e}")

    return result, info


def ai_inpaint_scratches(image: np.ndarray, strength: float = 0.5) -> np.ndarray:
    """
    Detect damage (scratches, spots, tears) via local variance analysis,
    then inpaint using OpenCV's NS method.
    
    Uses AI-like adaptive thresholding rather than fixed thresholds.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape

    # Compute local variance to detect anomalies
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    diff = cv2.absdiff(gray.astype(np.float32), blurred.astype(np.float32))

    # Adaptive threshold: Otsu on the diff map
    diff_norm = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, scratch_mask = cv2.threshold(diff_norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Also detect very dark spots and very bright spots
    dark_mask = cv2.inRange(gray, 0, 30)
    bright_mask = cv2.inRange(gray, 225, 255)

    # Combine masks
    mask = cv2.bitwise_or(scratch_mask, dark_mask)
    mask = cv2.bitwise_or(mask, bright_mask)

    # Morphological cleanup
    kernel = np.ones((2, 2), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    mask = cv2.erode(mask, np.ones((1, 1), np.uint8), iterations=1)

    # Only inpaint if significant damage detected
    damage_pct = np.sum(mask > 0) / (h * w) * 100
    info = {"damage_pct": round(damage_pct, 2)}

    if damage_pct > 0.5:
        result = cv2.inpaint(image, mask, inpaintRadius=3, flags=cv2.INPAINT_NS)
        info["inpainted"] = True
        logger.info(f"Scratch inpainting: {damage_pct:.1f}% damage")
    else:
        result = image.copy()
        info["inpainted"] = False

    return result, info


def ai_white_balance(image: np.ndarray) -> np.ndarray:
    """
    Smart white balance using gray world + white patch with saturation control.
    """
    result = image.copy().astype(np.float32)

    # Gray world assumption
    avg_r = np.mean(result[:, :, 0])
    avg_g = np.mean(result[:, :, 1])
    avg_b = np.mean(result[:, :, 2])
    avg_gray = (avg_r + avg_g + avg_b) / 3

    gains = np.array([avg_gray / avg_r, avg_gray / avg_g, avg_gray / avg_b])
    gains = np.clip(gains, 0.8, 1.5)  # Prevent over-correction

    for c in range(3):
        result[:, :, c] *= gains[c]

    result = np.clip(result, 0, 255).astype(np.uint8)
    return result
