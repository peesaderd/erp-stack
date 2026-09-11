"""
key_detect.py — Classify photo exposure key (low / normal / high)
=================================================================
Owner request (2026-09-11):
    "บางรูป low key, high key, normal key ต่างกัน ถ้าใช้ step เดียวรูปเพี้ยนอีก"
    Some photos are low-key (dark), high-key (bright), or normal.
    If we run ONE lighting strength for all, dark photos get blown out and
    bright photos get crushed -> distortion. So we detect the key first and
    pick the right lighting strength / direction for each.

The classification uses the FACE region brightness (not the whole frame,
because background dominates the mean) plus clipping ratios:

    low_key    -> dark/underexposed. Needs a stronger + brighter lift.
    normal_key -> well exposed. Needs only a gentle touch.
    high_key   -> bright/overexposed. Needs little to no lift (or slight pull-down).

Output feeds ai_passport.generate_passport() so the FLUX lighting step
(step 1.5) uses a key-appropriate strength + prompt instead of a fixed 0.30.
"""

import logging

import cv2
import numpy as np

logger = logging.getLogger("passport.key")


def _face_region(img: np.ndarray):
    """Return the face crop if a face is found, else the central region."""
    h, w = img.shape[:2]
    try:
        from ai_passport import detect_face
        face = detect_face(img)
    except Exception:
        face = None
    if face is not None:
        x, y, fw, fh = face
        # Expand a little to include forehead + cheeks
        pad_x = int(fw * 0.25)
        pad_y = int(fh * 0.20)
        x0 = max(0, x - pad_x)
        y0 = max(0, y - pad_y)
        x1 = min(w, x + fw + pad_x)
        y1 = min(h, y + fh + pad_y)
        return img[y0:y1, x0:x1]
    # fallback: centre 60%
    cy, cx = h // 2, w // 2
    return img[max(0, cy - h // 3):cy + h // 3, max(0, cx - w // 3):cx + w // 3]


def classify_key(image: np.ndarray) -> dict:
    """
    Classify exposure key of a portrait image (RGB or BGR; only luminance matters).

    IMPORTANT (owner 2026-09-11): a face-only mean is NOT enough — a subject can sit in
    front of a bright wall so the FRAME is already near high-key even though the face
    reads "normal", and a 0.30 lift then blows the whole image (>50% clipped). So we
    measure BOTH the face region AND the whole frame and decide on the BRIGHTER signal.

    Returns dict:
        key: "low" | "normal" | "high"
        face_mean, frame_mean: mean luminance (0-255)
        p10, p50, p90: percentiles of face luminance
        clipped_low_pct, clipped_high_pct: % of FACE pixels crushed/blown
        lighting_strength: suggested FLUX strength for the lighting step
        lighting_prompt: suggested prompt for the lighting step
        reason: short human-readable reason
    """
    region = _face_region(image)
    if region is None or region.size == 0:
        region = image
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY) if region.ndim == 3 else region
    frame_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

    face_mean = float(gray.mean())
    frame_mean = float(frame_gray.mean())
    frame_p50 = float(np.percentile(frame_gray, 50))
    frame_clip_high = float((frame_gray > 240).mean() * 100.0)
    p10 = float(np.percentile(gray, 10))
    p50 = float(np.percentile(gray, 50))
    p90 = float(np.percentile(gray, 90))
    clipped_low = float((gray < 15).mean() * 100.0)
    clipped_high = float((gray > 240).mean() * 100.0)

    # Use the brighter of face/frame to decide the high-key side (avatar sitting on
    # a bright wall = frame-driven high-key). Use face for the low-key side.
    bright_signal = max(face_mean, frame_mean)

    # Ambiguity score (for the A hybrid gate): how CLOSE each signal sits to its
    # decision boundary. Near a boundary = borderline = let Mimo vision confirm.
    LOW_EDGE = 132.0
    HIGH_EDGE = 178.0
    d_low = abs(face_mean - LOW_EDGE)
    d_high = abs(bright_signal - HIGH_EDGE)
    nearest = min(d_low, d_high)
    if nearest >= 18:
        confidence = 0.95          # clearly on one side
    elif nearest >= 10:
        confidence = 0.8
    elif nearest >= 5:
        confidence = 0.6           # borderline -> Mimo should confirm
    else:
        confidence = 0.45          # right on the line -> definitely ask Mimo
    ambiguous = confidence < 0.62

    # Decision thresholds (validated against real sessions in storage/):
    #   dark portraits  -> face_mean ~60-130, p90 < 180, some crushed lows
    #   normal          -> face_mean ~135-188 AND frame not already bright
    #   bright ones     -> face/frame > ~188, or already blown highlights
    if face_mean < 132 or (p90 < 185 and clipped_low > 4.0):
        key = "low"
        strength = 0.42          # stronger lift to open up shadows
        step2_scale = 1.0        # dark photos can take full clothing i2i
        prompt = ("brighten and lift the shadows, evenly lit face, soft fill light, "
                  "clear bright even illumination across the whole face, "
                  "same person same clothes same background, natural skin tones")
        reason = f"face_mean={face_mean:.0f} dark -> stronger lift"
    elif bright_signal > 178 or clipped_high > 6.0 or frame_clip_high > 8.0:
        key = "high"
        strength = 0.14          # very gentle — already bright, avoid blowing highlights
        step2_scale = 0.55       # already-bright photos wash out fast -> lighter Step 2
        prompt = ("even out the lighting, tame the highlights, balanced exposure, "
                  "soft even illumination, same person same clothes same background, "
                  "natural skin tones, no blown-out areas, keep midtones from washing out")
        reason = (f"face_mean={face_mean:.0f}/frame_mean={frame_mean:.0f} already bright "
                  f"-> gentle, tame highlights")
    else:
        key = "normal"
        strength = 0.22          # gentle default (was 0.30 which over-brightened bright frames)
        step2_scale = 0.85       # slightly lighter Step 2 to protect midtones
        prompt = ("even out the lighting, softly balance exposure across the photo, well-lit face, "
                  "uniform illumination, smooth soft light, natural skin tones, "
                  "same person same clothes same background")
        reason = f"face_mean={face_mean:.0f}/frame_mean={frame_mean:.0f} well exposed"

    result = {
        "key": key,
        "face_mean": round(face_mean, 1),
        "frame_mean": round(frame_mean, 1),
        "p10": round(p10, 1),
        "p50": round(p50, 1),
        "p90": round(p90, 1),
        "clipped_low_pct": round(clipped_low, 2),
        "clipped_high_pct": round(clipped_high, 2),
        "lighting_strength": strength,
        "step2_scale": step2_scale,
        "lighting_prompt": prompt,
        "reason": reason,
        "confidence": confidence,
        "ambiguous": ambiguous,
    }
    logger.info(f"key_detect: {key} ({reason}), strength={strength}, conf={confidence}")
    return result
