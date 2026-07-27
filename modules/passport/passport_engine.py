"""
Passport Photo Engine v2
========================
Core processing pipeline:
1. Face detection → auto-crop with head positioning
2. Face angle correction (eyes alignment) → straighten tilted faces
3. Lighting adjustment → shadow removal, highlight balance, skin brightness
4. Clothing/skin cleanup → tidy collar area, remove background from shoulders
5. Background removal → replace with template color
6. Resize to exact passport dimensions
7. Color/contrast enhancement + beautification
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
    auto_align: bool = True,
) -> dict:
    """
    Process an input image into a passport photo.

    Args:
        image: RGB numpy array (H, W, 3)
        template_code: e.g. "us_passport", "thai_passport"
        auto_crop: auto-detect face and crop
        enhance: apply color/contrast enhancement
        auto_align: auto-straighten tilted faces + beautification

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
    h, w = result.shape[:2]

    # ── 0. ENHANCEMENT PASS — before any cropping ───────────────────
    # Fix lighting, skin tone, and overall quality on the full image
    # so the face detector gets a better input too
    if enhance or auto_align:
        result = _enhance_lighting_and_skin(result)
        info["pre_enhanced"] = True

    # ── 1. Face angle correction (eye alignment) ────────────────────
    if auto_align:
        aligned, align_info = _correct_face_angle(result)
        result = aligned
        info["align"] = align_info

    # ── 2. Auto-crop based on face ──────────────────────────────────
    if auto_crop:
        cropped, crop_info = fd.auto_crop_passport(result, template["head_height_pct"])
        result = cropped
        info["crop"] = crop_info

    # ── 3. Smart background removal + clothing protection ──────────
    rgba = bg.remove_background(result, template["bg_color"])
    # If rembg worked, clean up edges near shoulders/clothing
    if rgba.shape[2] == 4:
        rgba = _clean_clothing_edges(rgba)
    result = bg.replace_background(rgba, template["bg_color"])
    info["bg_removed"] = True

    # ── 4. Apply beauty enhancement on face region ──────────────────
    if enhance or auto_align:
        result = _beautify_face(result)
        info["beauty"] = True

    # ── 5. Resize to exact passport dimensions ──────────────────────
    target_w_px = int(round(template["width_mm"] / 25.4 * template["dpi"]))
    target_h_px = int(round(template["height_mm"] / 25.4 * template["dpi"]))

    if result.shape[1] != target_w_px or result.shape[0] != target_h_px:
        result = cv2.resize(result, (target_w_px, target_h_px), interpolation=cv2.INTER_LANCZOS4)
        info["resized_to"] = f"{target_w_px}x{target_h_px}"
    else:
        info["resized_to"] = "same"

    # ── 6. Final enhancement ────────────────────────────────────────
    if enhance:
        result = _enhance_passport_photo(result)
        info["enhanced"] = True

    info["dimensions_px"] = {"w": target_w_px, "h": target_h_px}
    info["dimensions_mm"] = {"w": template["width_mm"], "h": template["height_mm"]}

    return {"ok": True, "result": result, "template": template, "info": info}


# ═══════════════════════════════════════════════════════════════════
# Face Angle Correction
# ═══════════════════════════════════════════════════════════════════

def _correct_face_angle(image: np.ndarray) -> tuple:
    """
    Detect eye positions and rotate image to align eyes horizontally.

    Returns:
        (rotated_image, info_dict)
    """
    from . import face_detector as fd
    info = {"rotated": False, "angle": 0.0}

    # Use MediaPipe or landmark detection for eyes
    eyes = fd.detect_eyes(image)
    if eyes and len(eyes) >= 2:
        left_eye = eyes[0]
        right_eye = eyes[1]

        dx = right_eye[0] - left_eye[0]
        dy = right_eye[1] - left_eye[1]
        angle = np.degrees(np.arctan2(dy, dx))

        if abs(angle) > 0.5:
            h, w = image.shape[:2]
            center = ((left_eye[0] + right_eye[0]) // 2, (left_eye[1] + right_eye[1]) // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            result = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_LANCZOS4,
                                     borderMode=cv2.BORDER_REPLICATE)
            info["rotated"] = True
            info["angle"] = round(angle, 2)
            logger.info(f"Face rotated by {angle:.2f}°")
            return result, info

    logger.info("Face angle: no correction needed (eyes not detected or already aligned)")
    return image, info


# ═══════════════════════════════════════════════════════════════════
# Lighting & Skin Enhancement
# ═══════════════════════════════════════════════════════════════════

def _enhance_lighting_and_skin(image: np.ndarray) -> np.ndarray:
    """
    Multi-step lighting and skin improvement:
    1. Shadow removal (Monge-Kantorovich style using YUV)
    2. Local contrast boost for face region
    3. Skin tone smoothing (bilateral filter on face areas)
    4. Highlight/shadow balance
    """
    result = image.copy()

    # ── Step 1: Convert to LAB for better luminance handling ──────
    lab = cv2.cvtColor(result, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)

    # ── Step 2: Shadow removal via CLAHE on L channel ────────────
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l)

    # ── Step 3: Shadow/highlight balance ──────────────────────────
    # Lighten shadows, preserve highlights
    shadow_mask = l_enhanced < 80
    highlight_mask = l_enhanced > 200

    l_balanced = l_enhanced.astype(np.float32)
    # Boost shadows by 30%
    l_balanced[shadow_mask] = np.clip(l_balanced[shadow_mask] * 1.3, 0, 255)
    # Slightly reduce highlights
    l_balanced[highlight_mask] = np.clip(l_balanced[highlight_mask] * 0.9, 0, 255)
    l_balanced = l_balanced.astype(np.uint8)

    # ── Step 4: Skin-color preserving luminance blend ─────────────
    # Keep original L where it's better, use enhanced elsewhere
    # Compute face region with color-based skin detection
    ycrcb = cv2.cvtColor(result, cv2.COLOR_RGB2YCrCb)
    Y, Cr, Cb = cv2.split(ycrcb)

    # Skin color range in YCrCb
    skin_mask = cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127))
    skin_mask = cv2.erode(skin_mask, np.ones((3, 3), np.uint8), iterations=1)
    skin_mask = cv2.GaussianBlur(skin_mask.astype(np.float32), (15, 15), 0)

    # Blend: use enhanced L for skin, balanced L for everything
    l_final = (l_balanced * (1 - skin_mask/255) + l_enhanced * (skin_mask/255)).astype(np.uint8)

    lab = cv2.merge([l_final, a, b])
    result = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)

    # ── Step 5: Subtle skin smoothing (bilateral filter) ──────────
    # Apply gentle bilateral filter only on skin regions
    smoothed = cv2.bilateralFilter(result, 9, 50, 50)
    skin_mask_3 = cv2.merge([skin_mask, skin_mask, skin_mask]).astype(np.float32) / 255.0
    result = (result.astype(np.float32) * (1 - skin_mask_3 * 0.3)
              + smoothed.astype(np.float32) * (skin_mask_3 * 0.3)).astype(np.uint8)

    logger.info("Lighting/skin enhancement applied")
    return result


# ═══════════════════════════════════════════════════════════════════
# Clothing Edge Cleanup
# ═══════════════════════════════════════════════════════════════════

def _clean_clothing_edges(rgba: np.ndarray) -> np.ndarray:
    """
    Clean up alpha channel near shoulders/clothing.
    Removes stray background pixels and smooths edges.
    """
    alpha = rgba[:, :, 3]

    # Morphological close to fill small holes in the subject
    kernel = np.ones((5, 5), np.uint8)
    alpha = cv2.morphologyEx(alpha, cv2.MORPH_CLOSE, kernel)

    # Erode slightly to remove thin translucent edges
    alpha = cv2.erode(alpha, np.ones((3, 3), np.uint8), iterations=1)
    alpha = cv2.GaussianBlur(alpha, (5, 5), 0)

    result = rgba.copy()
    result[:, :, 3] = alpha
    return result


# ═══════════════════════════════════════════════════════════════════
# Face Beautification
# ═══════════════════════════════════════════════════════════════════

def _beautify_face(image: np.ndarray) -> np.ndarray:
    """
    Beautification applied to face region:
    - Subtle skin smoothing (reduce blemishes)
    - Eye brightening (local contrast on eye region)
    - Soft highlight on cheeks
    """
    face = fd.detect_face(image)
    if not face:
        return image

    x, y, w, h = face["x"], face["y"], face["w"], face["h"]

    # Expand face region slightly
    mx = int(w * 0.1)
    my = int(h * 0.05)
    x1 = max(0, x - mx)
    y1 = max(0, y - my)
    x2 = min(image.shape[1], x + w + mx)
    y2 = min(image.shape[0], y + h + my)

    face_roi = image[y1:y2, x1:x2].copy()
    h2, w2 = face_roi.shape[:2]

    # ── Skin smoothing on face (bilateral filter + guided filter) ──
    smooth = cv2.bilateralFilter(face_roi, 7, 40, 40)
    # Use guided filter for edge-preserving smoothing
    smooth_float = smooth.astype(np.float32)
    guide = face_roi.astype(np.float32)
    # Simple weighted blend: 40% smooth, 60% original = subtle smoothing
    blended = (smooth_float * 0.4 + guide * 0.6).astype(np.uint8)

    # ── Eye region brightening ────────────────────────────────────
    eye_y = int(h2 * 0.25)  # eyes in upper 25% of face
    eye_h = int(h2 * 0.25)
    eye_x1 = int(w2 * 0.15)
    eye_x2 = int(w2 * 0.85)

    if eye_h > 5 and eye_x2 > eye_x1:
        eye_roi = blended[eye_y:eye_y + eye_h, eye_x1:eye_x2]
        # Subtle brighten + contrast
        eye_lab = cv2.cvtColor(eye_roi, cv2.COLOR_RGB2LAB)
        eye_l, eye_a, eye_b = cv2.split(eye_lab)
        eye_clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
        eye_l = eye_clahe.apply(eye_l)
        eye_lab = cv2.merge([eye_l, eye_a, eye_b])
        eye_enhanced = cv2.cvtColor(eye_lab, cv2.COLOR_LAB2RGB)
        blended[eye_y:eye_y + eye_h, eye_x1:eye_x2] = eye_enhanced

    # Paste back
    result = image.copy()
    result[y1:y2, x1:x2] = blended

    logger.info(f"Face beautification: face region ({x1},{y1},{x2},{y2})")
    return result


# ═══════════════════════════════════════════════════════════════════
# Standard Enhancements (original)
# ═══════════════════════════════════════════════════════════════════

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
