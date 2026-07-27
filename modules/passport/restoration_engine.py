"""
Photo Restoration Engine v2
============================
ซ่อมแซมภาพถ่ายเก่า — ใช้ AI (GFPGAN) + OpenCV

Features:
- AI Face Restoration (GFPGAN)
- AI Scratch/damage repair
- AI White balance + color restoration
- Super resolution
- Face enhancement
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
    Restore/repair an old/damaged photo using AI + OpenCV.

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

    # ── 0. Downscale if too large (for CPU speed) ───────────────────
    h, w = result.shape[:2]
    MAX_PIXELS = 2000 * 2000
    if h * w > MAX_PIXELS:
        scale = np.sqrt(MAX_PIXELS / (h * w))
        new_w, new_h = int(w * scale), int(h * scale)
        result = cv2.resize(result, (new_w, new_h), interpolation=cv2.INTER_AREA)
        info["resized"] = f"{w}x{h}->{new_w}x{new_h}"

    # ── 1. AI Denoise + Face Restoration ───────────────────────────
    if denoise_strength > 0:
        from .ai_restore import ai_denoise_and_enhance
        result, ai_info = ai_denoise_and_enhance(result, strength=denoise_strength)
        info["denoise"] = round(denoise_strength, 2)
        if ai_info.get("gfpgan"):
            info["ai_face_restored"] = True
            logger.info("✅ AI face restoration (GFPGAN)")

        # Traditional denoise for non-face areas
        if denoise_strength > 0.3:
            d = int(5 + denoise_strength * 15)
            sc = int(30 + denoise_strength * 60)
            trad = cv2.bilateralFilter(result, d, sc, sc)
            result = cv2.addWeighted(result, 0.6, trad, 0.4, 0)

    # ── 2. AI Scratch Inpainting ───────────────────────────────────
    if inpaint_scratches:
        from .ai_restore import ai_inpaint_scratches
        result, inp_info = ai_inpaint_scratches(result)
        info["inpaint"] = inp_info.get("inpainted", False)
        info["scratch_pct"] = inp_info.get("damage_pct", 0)
        if inp_info.get("inpainted"):
            logger.info(f"✅ AI scratch inpainting: {inp_info['damage_pct']:.1f}%")

    # ── 3. AI Color Restoration ────────────────────────────────────
    if color_restore:
        from .ai_restore import ai_white_balance
        result = ai_white_balance(result)
        # Adjusted CLAHE
        lab = cv2.cvtColor(result, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(8, 8))
        l = clahe.apply(l)
        # Subtle saturation boost
        a = cv2.addWeighted(a, 1.0, a - 128, 0.12, 0)
        b = cv2.addWeighted(b, 1.0, b - 128, 0.12, 0)
        result = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)
        info["color_restored"] = True
        logger.info("✅ AI color restoration")

    # ── 4. Sharpen (Unsharp Mask) ──────────────────────────────────
    if sharpen_strength > 0:
        sigma = 1.0 + (1.0 - sharpen_strength) * 2.0
        amount = 0.3 + sharpen_strength * 0.7
        blurred = cv2.GaussianBlur(result, (0, 0), sigma)
        result = cv2.addWeighted(result, 1.0 + amount, blurred, -amount, 0)
        info["sharpened"] = round(sharpen_strength, 2)
        logger.info(f"✅ Unsharp mask: sigma={sigma:.1f}, amount={amount:.2f}")

    # ── 5. Upscale ──────────────────────────────────────────────────
    if upscale_factor > 1:
        new_w = result.shape[1] * upscale_factor
        new_h = result.shape[0] * upscale_factor
        result = cv2.resize(result, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        info["upscaled"] = upscale_factor

    # ── 6. Face enhancement ─────────────────────────────────────────
    if enhance_face:
        from . import face_detector as fd
        face = fd.detect_face(result)
        if face:
            x, y, fw, fh = face["x"], face["y"], face["w"], face["h"]
            mx, my = int(fw * 0.3), int(fh * 0.3)
            x1, y1 = max(0, x - mx), max(0, y - my)
            x2, y2 = min(result.shape[1], x + fw + mx), min(result.shape[0], y + fh + my)
            roi = result[y1:y2, x1:x2].copy()
            # CLAHE on face
            lab2 = cv2.cvtColor(roi, cv2.COLOR_RGB2LAB)
            l2, a2, b2 = cv2.split(lab2)
            clahe2 = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(4, 4))
            l2 = clahe2.apply(l2)
            roi = cv2.cvtColor(cv2.merge([l2, a2, b2]), cv2.COLOR_LAB2RGB)
            result[y1:y2, x1:x2] = roi
            info["face_enhanced"] = True
            logger.info("✅ Face region enhanced")
        else:
            logger.info("No face found for enhancement")

    info["dimensions"] = {"w": result.shape[1], "h": result.shape[0]}
    return {"ok": True, "result": result, "info": info}
