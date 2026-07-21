"""
Photo Restoration Engine
========================
ซ่อมแซมภาพถ่ายเก่า — แบบครบวงจร

Features:
- Denoise (Bilateral, Non-local Means)
- Scratch/damage repair (Inpainting)
- Color restoration (White balance, histogram equalization)
- Super resolution (LANCZOS upscale)
- Face enhancement (local contrast + sharpen)
- Unsharp mask for overall sharpness
"""

import logging
import cv2
import numpy as np

logger = logging.getLogger("passport.restoration")


def restore_photo(
    image: np.ndarray,
    denoise_strength: float = 0.5,
    sharpen_strength: float = 0.5,
    inpaint_scratches: bool = True,
    color_restore: bool = True,
    upscale_factor: int = 1,
    enhance_face: bool = False,
) -> dict:
    """
    Restore/repair an old/damaged photo.

    Args:
        image: RGB numpy array (H, W, 3)
        denoise_strength: 0.0 (none) to 1.0 (max)
        sharpen_strength: 0.0 (none) to 1.0 (max)
        inpaint_scratches: detect and repair scratches
        color_restore: white balance + histogram equalization
        upscale_factor: 1 = no upscale, 2 = 2x, 4 = 4x
        enhance_face: apply local enhancement to face region

    Returns:
        dict with:
            - ok: bool
            - result: restored RGB image
            - info: processing metadata
    """
    result = image.copy()
    info = {}

    # ── 1. Denoise ──────────────────────────────────────────────────
    if denoise_strength > 0:
        result = _apply_denoise(result, denoise_strength)
        info["denoise"] = denoise_strength

    # ── 2. Scratch/damage inpainting ────────────────────────────────
    if inpaint_scratches:
        result = _inpaint_damage(result)
        info["inpaint"] = True

    # ── 3. Color restoration ────────────────────────────────────────
    if color_restore:
        result = _restore_color(result)
        info["color_restored"] = True

    # ── 4. Sharpen (Unsharp Mask) ──────────────────────────────────
    if sharpen_strength > 0:
        result = _apply_unsharp_mask(result, sharpen_strength)
        info["sharpened"] = sharpen_strength

    # ── 5. Upscale ──────────────────────────────────────────────────
    if upscale_factor > 1:
        new_w = result.shape[1] * upscale_factor
        new_h = result.shape[0] * upscale_factor
        result = cv2.resize(result, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        info["upscaled"] = upscale_factor

    # ── 6. Face enhancement ─────────────────────────────────────────
    if enhance_face:
        result = _enhance_face_region(result)
        info["face_enhanced"] = True

    info["dimensions"] = {"w": result.shape[1], "h": result.shape[0]}
    return {"ok": True, "result": result, "info": info}


# ── Denoise ──────────────────────────────────────────────────────────

def _apply_denoise(image: np.ndarray, strength: float) -> np.ndarray:
    """
    Multi-method denoising.

    strength 0.0-1.0 maps to:
      - 0.0-0.3: light bilateral filter only
      - 0.3-0.7: bilateral + mild NL-means
      - 0.7-1.0: aggressive bilateral + stronger NL-means
    """
    result = image.copy()

    d = int(5 + strength * 15)  # diameter 5-20
    sigma_color = int(30 + strength * 60)  # 30-90
    sigma_space = int(30 + strength * 60)

    result = cv2.bilateralFilter(result, d, sigma_color, sigma_space)
    info_log = f"bilateral(d={d}, sc={sigma_color}, ss={sigma_space})"

    if strength > 0.3:
        # Non-local Means Denoising
        h = int(3 + strength * 10)  # 3-13
        result = cv2.fastNlMeansDenoisingColored(result, None, h, h, 7, 21)
        info_log += f" + NL-means(h={h})"

    logger.info(f"Denoising: {info_log}")
    return result


# ── Scratch/Damage Inpainting ────────────────────────────────────────

def _detect_scratches(gray: np.ndarray) -> np.ndarray:
    """
    Detect scratches/damage in grayscale image using adaptive thresholding.
    Returns binary mask of detected damage.
    """
    # Detect dark scratches (dark lines on lighter bg)
    dark_mask = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 31, 10
    )

    # Detect bright scratches (white lines)
    bright_mask = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 10
    )
    bright_mask = cv2.bitwise_not(bright_mask)

    # Combine
    mask = cv2.bitwise_or(dark_mask, bright_mask)

    # Remove small noise (keep only line-like features)
    kernel = np.ones((2, 2), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # Dilate to cover scratch edges
    mask = cv2.dilate(mask, kernel, iterations=1)

    return mask


def _inpaint_damage(image: np.ndarray) -> np.ndarray:
    """
    Detect scratches/damage and repair using Telea inpainting.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    mask = _detect_scratches(gray)

    # Count damaged pixels
    damage_count = cv2.countNonZero(mask)
    total_pixels = mask.shape[0] * mask.shape[1]
    damage_pct = damage_count / total_pixels * 100
    logger.info(f"Detected damage: {damage_count}px ({damage_pct:.2f}%)")

    if damage_pct < 0.01:
        # Negligible damage, skip
        return image

    # Telea inpainting
    inpainted = cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)

    # Also apply NS inpainting and blend for better results on larger damage
    if damage_pct > 1.0:
        inpainted_ns = cv2.inpaint(image, mask, 5, cv2.INPAINT_NS)
        inpainted = cv2.addWeighted(inpainted, 0.6, inpainted_ns, 0.4, 0)

    logger.info(f"Inpainting: Telea{' + NS' if damage_pct > 1.0 else ''}")
    return inpainted


# ── Color Restoration ────────────────────────────────────────────────

def _restore_color(image: np.ndarray) -> np.ndarray:
    """White balance + contrast + saturation enhancement."""
    result = image.copy()

    # 1. Simple white balance (Gray World assumption)
    avg_r = np.mean(result[:, :, 0])
    avg_g = np.mean(result[:, :, 1])
    avg_b = np.mean(result[:, :, 2])
    avg_all = (avg_r + avg_g + avg_b) / 3.0

    if avg_r > 0:
        result[:, :, 0] = np.clip(result[:, :, 0] * (avg_all / avg_r), 0, 255).astype(np.uint8)
    if avg_g > 0:
        result[:, :, 1] = np.clip(result[:, :, 1] * (avg_all / avg_g), 0, 255).astype(np.uint8)
    if avg_b > 0:
        result[:, :, 2] = np.clip(result[:, :, 2] * (avg_all / avg_b), 0, 255).astype(np.uint8)

    # 2. Convert to HSV, enhance saturation
    hsv = cv2.cvtColor(result, cv2.COLOR_RGB2HSV)
    h, s, v = cv2.split(hsv)

    # Boost saturation by 20%
    s = np.clip(s * 1.2, 0, 255).astype(np.uint8)

    # CLAHE on Value channel (local contrast)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    v = clahe.apply(v)

    hsv = cv2.merge([h, s, v])
    result = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)

    logger.info("Color restoration: white balance + saturation boost + CLAHE")
    return result


# ── Unsharp Mask ─────────────────────────────────────────────────────

def _apply_unsharp_mask(image: np.ndarray, strength: float) -> np.ndarray:
    """Apply unsharp masking for sharpness enhancement."""
    sigma = 1.0 + (1.0 - strength) * 2.0  # sigma 1-3
    amount = 0.3 + strength * 0.7  # amount 0.3-1.0

    blurred = cv2.GaussianBlur(image, (0, 0), sigma)
    sharpened = cv2.addWeighted(image, 1.0 + amount, blurred, -amount, 0)

    logger.info(f"Unsharp mask: sigma={sigma:.1f}, amount={amount:.2f}")
    return sharpened


# ── Face Enhancement ────────────────────────────────────────────────

def _enhance_face_region(image: np.ndarray) -> np.ndarray:
    """Detect face and apply local enhancement."""
    from . import face_detector as fd

    face = fd.detect_face(image)
    if not face:
        logger.info("No face detected for enhancement")
        return image

    x, y, w, h = face["x"], face["y"], face["w"], face["h"]
    # Expand region slightly
    margin_x = int(w * 0.3)
    margin_y = int(h * 0.3)
    x1 = max(0, x - margin_x)
    y1 = max(0, y - margin_y)
    x2 = min(image.shape[1], x + w + margin_x)
    y2 = min(image.shape[0], y + h + margin_y)

    face_region = image[y1:y2, x1:x2].copy()

    # CLAHE on LAB L channel
    lab = cv2.cvtColor(face_region, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(4, 4))
    l = clahe.apply(l)
    lab = cv2.merge([l, a, b])
    enhanced_face = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

    # Light sharpen
    kernel = np.array([[-1, -1, -1],
                       [-1,  9, -1],
                       [-1, -1, -1]]) / 5.0
    enhanced_face = cv2.filter2D(enhanced_face, -1, kernel)

    # Blend back
    result = image.copy()
    result[y1:y2, x1:x2] = enhanced_face

    logger.info(f"Face region enhanced: ({x1},{y1})-({x2},{y2})")
    return result
