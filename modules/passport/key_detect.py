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


def _subject_brightness(image: np.ndarray):
    """Mean luminance of the SUBJECT only (background excluded).

    OWNER LESSON (2026-09-12): a blown-out WHITE background fools the key detector.
    Real case: a subject was lit from the front but standing in front of a pure-white
    wall (43% of the frame clipped to white). The frame mean read ~150 and the FACE-box
    mean read ~159 because the face box (detect_face + 25% pad) included tons of the
    surrounding white wall. The detector called it HIGH-key and skipped the brightening
    pass -> the face came out under-lit AND FLUX created a new face (identity drift).

    Approach: we do NOT trust a padded box, and we do NOT trust a global threshold
    (a mid-grey wall breaks the bright/dark branching). Instead we:
      1. detect the face box,
      2. shrink it to the CENTRAL FACE CORE (drop ~30% on each side) so walls/hair/
         background edges are excluded and only skin+eyes+nose stay,
      3. take the MEDIAN of that core (robust to a few blown specular highlights).
    Falls back to the plain centre crop when no face is detected.

    Returns (subject_mean, bg_mean, core_ratio).
    """
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

    try:
        from ai_passport import detect_face
        face = detect_face(image)
    except Exception:
        face = None

    if face is not None:
        x, y, fw, fh = [int(v) for v in face]
        # shrink to the face CORE: central 60% width x 70% height (skin + features)
        cx0 = x + int(fw * 0.20)
        cy0 = y + int(fh * 0.12)
        cx1 = min(w, x + int(fw * 0.80))
        cy1 = min(h, y + int(fh * 0.85))
        if cx1 - cx0 >= 8 and cy1 - cy0 >= 8:
            core = gray[cy0:cy1, cx0:cx1]
            subject_mean = float(np.median(core))
            rr = 0.6
        else:
            subject_mean = None
            rr = 0.0
    else:
        # fallback: central 40% box (typical head-and-shoulders framing)
        cy, cx = h // 2, w // 2
        core = gray[max(0, cy - int(h * 0.20)):cy + int(h * 0.20),
                    max(0, cx - int(w * 0.20)):cx + int(w * 0.20)]
        subject_mean = float(np.median(core)) if core.size else None
        rr = 0.4

    # background reference: the border ring median (for logging / hints only)
    ring = np.concatenate([
        gray[0:max(1, h // 20), :].ravel(),
        gray[-max(1, h // 20):, :].ravel(),
        gray[:, 0:max(1, w // 20)].ravel(),
        gray[:, -max(1, w // 20):].ravel(),
    ])
    bg_mean = float(np.median(ring))
    return subject_mean, bg_mean, rr


def classify_key(image: np.ndarray) -> dict:
    """
    Classify exposure key of a portrait image (RGB or BGR; only luminance matters).

    IMPORTANT (owner 2026-09-11): a face-only mean is NOT enough — a subject can sit in
    front of a bright wall so the FRAME is already near high-key even though the face
    reads "normal", and a 0.30 lift then blows the whole image (>50% clipped). So we
    measure BOTH the face region AND the whole frame and decide on the BRIGHTER signal.

    IMPORTANT (owner 2026-09-12): BUT a blown-out white WALL next to a dark subject makes
    BOTH the frame mean and the padded face-box mean read bright, so the earlier logic
    wrongly said "high-key" for a subject who was actually under-lit and needed brightening.
    We now ALSO measure the SUBJECT-ONLY brightness (background excluded) and let it drive
    the LOW-key decision: a dark subject wins over a bright background.

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

    # Owner 2026-09-12: measure the SUBJECT-only brightness (BACKGROUND EXCLUDED) so a
    # blown-out white wall cannot masquerade as "high-key" over an under-lit person.
    # subj_mean = median of the FACE CORE (padded box shrunk to skin+features).
    subj_mean, bg_mean, core_ratio = _subject_brightness(image)
    # The padded face-box mean is unreliable: it eats dark hair/background. For the LOW
    # side prefer the SUBJECT-core median when we have it, else fall back to face_mean.
    face_signal = subj_mean if subj_mean is not None else face_mean
    dark_subject = subj_mean is not None and subj_mean < 118.0

    # High-key side = brighter of face/frame BUT a genuinely dark subject core outranks
    # a bright background (dark person in front of a white wall still needs a lift).
    if dark_subject:
        bright_signal = face_signal
    else:
        bright_signal = max(face_signal, frame_mean)

    # Ambiguity score (for the A hybrid gate): how CLOSE each signal sits to its
    # decision boundary. Near a boundary = borderline = let Mimo vision confirm.
    LOW_EDGE = 124.0
    HIGH_EDGE = 178.0
    d_low = abs(face_signal - LOW_EDGE)
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
    #   dark portraits  -> subject core < ~124, p90 < 185, some crushed lows
    #   normal          -> subject core ~135-175 AND frame not already bright
    #   bright ones     -> face/frame > ~178, or already blown highlights
    # NOTE: the LOW side now uses face_signal (subject-core median when available),
    # NOT the padded face-box mean which is dragged down by dark hair/background.
    if dark_subject or face_signal < 124.0 or (p90 < 185 and clipped_low > 4.0 and face_signal < 135.0):
        key = "low"
        strength = 0.42          # stronger lift to open up shadows
        step2_scale = 1.0        # dark photos can take full clothing i2i
        prompt = ("brighten and lift the shadows, evenly lit face, soft fill light, "
                  "clear bright even illumination across the whole face, "
                  "same person same clothes same background, natural skin tones")
        if dark_subject:
            reason = (f"subject_core={subj_mean:.0f} dark (bg={bg_mean:.0f}) "
                      f"-> brighten subject, not fooled by bright bg")
        else:
            reason = f"face_signal={face_signal:.0f} dark -> stronger lift"
    elif bright_signal > 178 or clipped_high > 6.0 or frame_clip_high > 8.0:
        key = "high"
        strength = 0.14          # very gentle — already bright, avoid blowing highlights
        step2_scale = 0.55       # already-bright photos wash out fast -> lighter Step 2
        prompt = ("even out the lighting, tame the highlights, balanced exposure, "
                  "soft even illumination, same person same clothes same background, "
                  "natural skin tones, no blown-out areas, keep midtones from washing out")
        reason = (f"face_signal={face_signal:.0f}/frame={frame_mean:.0f} already bright "
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
        "subject_mean": round(subj_mean, 1) if subj_mean is not None else None,
        "bg_mean": round(bg_mean, 1) if bg_mean is not None else None,
        "core_ratio": round(core_ratio, 3),
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
