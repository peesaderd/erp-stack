"""
Simple head position finder — scan from top down.
Head position = distance from image top to head top.
"""
import cv2
import numpy as np
import sys

try:
    from .ai_passport import detect_face
except ImportError:
    sys.path.insert(0, '/home/openhands/erp-stack')
    from modules.passport.ai_passport import detect_face


def find_head_top(image, bg_sample_rows=15, threshold=30, min_head_width=0.03):
    """สแกนจากบนลงล่าง หาจุดแรกที่สีเปลี่ยนจาก bg → หัว"""
    h, w = image.shape[:2]
    bg_color = image[:bg_sample_rows, :, :].astype(float).mean(axis=(0, 1))

    for y in range(bg_sample_rows, h):
        row = image[y, :, :].astype(float)
        diff = np.sqrt(np.sum((row - bg_color) ** 2, axis=1))
        diff_ratio = (diff > threshold).sum() / w

        if diff_ratio > min_head_width:
            head_pixels = np.where(diff > threshold)[0]
            return {
                "head_top_y": y,
                "head_center_x": int(head_pixels.mean()),
                "headspace_from_top": round(y / h * 100, 1),
            }
    return None


CROP_PRESETS = {
    "standard": {
        "target_head_top_pct": 20,
        "face_width_ratio": 0.70,
        "label": "Standard — head 20% from top",
    },
    "compact": {
        "target_head_top_pct": 15,
        "face_width_ratio": 0.65,
        "label": "Compact — head 15% from top, shows chest",
    },
    "relaxed": {
        "target_head_top_pct": 12,
        "face_width_ratio": 0.60,
        "label": "Relaxed — head 12% from top, more body",
    },
}


# ── ID-photo framing spec (owner 2026-09-12) ───────────────────────────────
# Two owner-approved framing modes. The window "head-top → face-bottom" is
# scaled to a FIXED fraction of the square so the person is identical across
# every render AND we see head + shoulders + upper chest (not half body).
# "ย่อ" = zoom OUT = SMALLER face_frac = MORE chest visible.
ID_FRAME_A = {"face_frac": 0.41, "head_top_frac": 0.115}  # owner pick 14:45 (C: ~half chest)
ID_FRAME_B = {"face_frac": 0.55, "head_top_frac": 0.09}   # tighter (neck/shoulders only)
DEFAULT_FRAME = ID_FRAME_A   # owner picked C (face 41%, ~half chest) 14:45


def normalize_face_size(image, size_px, target_face_frac=None, margin_pct=None,
                        face_frac=None, head_top_frac=None):
    """
    Center the face and scale so the head-to-chin window occupies a FIXED
    fraction of the square frame.

    Owner 2026-09-12: (a) "รูปคน ... มันไม่เท่ากันสักกะรูป" -> face size must be
    identical across renders; (b) "ไม่ใช่ format รูปติดบัตร ... เห็นครึ่งตัว" ->
    must show head + shoulders + upper chest, not half body;
    (c) "ผมขาด ... ตอนแรกมันมี space" -> must NOT clip the hair at the top.

    We measure the DETECTED FACE (Haar) which runs roughly hairline->chin. We
    scale so face-height == face_frac * frame, then anchor the ACTUAL HAIR TOP
    (find_head_top) at head_top_frac * frame so real headroom is preserved.
    Everything below the chin is left visible (chest).

    Back-compat: target_face_frac/margin_pct still accepted.
    No-op when no face is found.
    """
    if face_frac is None:
        face_frac = target_face_frac if target_face_frac is not None else DEFAULT_FRAME["face_frac"]
    if head_top_frac is None:
        head_top_frac = margin_pct if margin_pct is not None else DEFAULT_FRAME["head_top_frac"]

    h, w = image.shape[:2]
    face = detect_face(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    if face is None:
        return image
    fx, fy, fw, fh = [int(v) for v in face]
    if fh <= 0:
        return image

    # ── scale so face height == target fraction of the output square ──
    target_fh = face_frac * size_px
    scale = target_fh / fh
    scale = min(max(scale, 0.4), 2.5)          # sanity clamp

    new_w, new_h = int(round(w * scale)), int(round(h * scale))
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    # face center in the resized image
    fcx = int(round((fx + fw / 2.0) * scale))

    # ── anchor on the ACTUAL hair top, not the Haar face box ──
    # Haar's face box starts BELOW the hairline, so pinning the face top clips
    # the hair above it (owner 2026-09-12: "ผมขาด ... ตอนแรกมันมี space").
    # find_head_top scans the real bg→hair boundary, so we get true headroom.
    head = find_head_top(resized)
    if head is not None:
        hair_top = int(head["head_top_y"])
    else:
        # fallback: estimate hair top above the face box (~35% of face height)
        hair_top = int(round((fy - 0.35 * fh) * scale))

    # place the hair top at head_top_frac of the frame
    want_htop = int(round(size_px * head_top_frac))
    x1 = fcx - size_px // 2
    y1 = hair_top - want_htop

    pad_l = max(0, -x1); pad_t = max(0, -y1)
    pad_r = max(0, (x1 + size_px) - new_w); pad_b = max(0, (y1 + size_px) - new_h)
    if pad_l or pad_t or pad_r or pad_b:
        edge = resized[0, 0].tolist()
        resized = cv2.copyMakeBorder(resized, pad_t, pad_b, pad_l, pad_r,
                                     cv2.BORDER_CONSTANT, value=edge)
        x1 += pad_l; y1 += pad_t
        new_w, new_h = resized.shape[1], resized.shape[0]

    x1 = max(0, min(x1, new_w - size_px))
    y1 = max(0, min(y1, new_h - size_px))
    return resized[y1:y1 + size_px, x1:x1 + size_px]


def crop_passport_auto(image, preset="standard", dpi=300, square=True, size_px=None):
    """
    Auto-crop passport photo.
    square=True (default): keep the square image, only center/trim, do NOT force
    35x45 ratio. size_px: optional exact output size (e.g. 1024). If None, keep
    the largest square that fits (min(w,h)).
    """
    h, w = image.shape[:2]
    target_w_mm, target_h_mm = 35, 45
    crop_ratio = target_w_mm / target_h_mm

    cfg = CROP_PRESETS.get(preset, CROP_PRESETS["standard"])
    target_head_top_pct = cfg["target_head_top_pct"]
    face_width_ratio = cfg["face_width_ratio"]

    if square:
        # ── SQUARE MODE: keep full square, no forced passport ratio ──
        side = size_px if size_px else min(h, w)
        side = min(side, h, w)
        # Normalize face size + center so every outfit render is identical scale.
        cropped = normalize_face_size(image, side)
        # if requested size differs, resize
        if size_px and size_px != cropped.shape[0]:
            cropped = cv2.resize(cropped, (size_px, size_px), interpolation=cv2.INTER_LANCZOS4)
        face = detect_face(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
        head = find_head_top(cropped)
        return {
            "ok": True,
            "result": cropped,
            "headspace_in_crop": (head["headspace_from_top"] if head else "n/a"),
            "crop_region": {"x": 0, "y": 0, "w": side, "h": side},
            "output": f"{cropped.shape[1]}x{cropped.shape[0]}px (square, face-normalized)",
            "square": True,
            "face": [int(v) for v in face] if face is not None else None,
        }
    # ── LEGACY RATIO MODE (unchanged, only used if square=False) ──

    # หาหัว
    head = find_head_top(image)
    if head is None:
        return {"ok": False, "error": "Cannot detect head position"}

    head_top_y = head["head_top_y"]
    head_center_x = head["head_center_x"]

    # ถ้าหัวอยู่สูงเกินไป — เพิ่ม padding ด้านบน
    needed_top_pad = int(h * target_head_top_pct / 100) - head_top_y
    if needed_top_pad > 0:
        pad_color = image[0, w // 2].tolist()
        pad = np.full((needed_top_pad, w, 3), pad_color, dtype=np.uint8)
        image = np.vstack([pad, image])
        h = image.shape[0]
        head_top_y += needed_top_pad
        head_center_x = head["head_center_x"]  # x ไม่เปลี่ยน

    # หา chin
    face = detect_face(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
    if face is not None:
        face_bottom = face[1] + face[3]
    else:
        face_bottom = head_top_y + int(w * 0.25)

    # คำนวณ crop width จาก face
    if face is not None:
        face_w = face[2]
        crop_w = int(face_w / face_width_ratio)
    else:
        crop_w = int(w * 0.6)

    crop_h = int(crop_w / crop_ratio)

    # คำนวณ crop_y1 ให้หัวอยู่ที่ target_head_top_pct% จากบนของ crop
    # head_top_in_crop = head_top_y - crop_y1
    # head_top_in_crop / crop_h = target_head_top_pct / 100
    # crop_y1 = head_top_y - (crop_h * target_head_top_pct / 100)
    desired_crop_y1 = head_top_y - int(crop_h * target_head_top_pct / 100)
    crop_y1 = max(0, desired_crop_y1)

    # ตรวจสอบ chin
    crop_y2 = crop_y1 + crop_h
    if face_bottom > crop_y2 - 30:
        crop_y1 = face_bottom - crop_h + 30
        crop_y1 = max(0, crop_y1)

    crop_x1 = max(0, head_center_x - crop_w // 2)
    crop_x1 = max(0, min(crop_x1, w - crop_w))
    crop_y1 = max(0, min(crop_y1, h - crop_h))

    cropped = image[crop_y1:crop_y1 + crop_h, crop_x1:crop_x1 + crop_w]

    # Resize
    target_w = int(round(target_w_mm / 25.4 * dpi))
    target_h = int(round(target_h_mm / 25.4 * dpi))
    resized = cv2.resize(cropped, (target_w, target_h),
                         interpolation=cv2.INTER_LANCZOS4)

    actual_head_pct = (head_top_y - crop_y1) / crop_h * 100

    return {
        "ok": True,
        "result": resized,
        "headspace_in_crop": f"{actual_head_pct:.1f}%",
        "crop_region": {"x": crop_x1, "y": crop_y1, "w": crop_w, "h": crop_h},
        "output": f"{target_w}x{target_h}px ({target_w_mm}x{target_h_mm}mm @ {dpi}dpi)",
    }


if __name__ == "__main__":
    img_path = sys.argv[1] if len(sys.argv) > 1 else "passport_raw.jpg"
    img = cv2.imread(img_path)
    if img is None:
        print(f"Cannot read: {img_path}"); sys.exit(1)

    print(f"Input: {img.shape[1]}x{img.shape[0]}")
    print()

    for preset_name in ["standard", "compact", "relaxed"]:
        result = crop_passport_auto(img, preset=preset_name, dpi=300)
        if result["ok"]:
            cv2.imwrite(f"passport_crop_{preset_name}.jpg", result["result"])
            print(f"{preset_name.upper()}: {result['headspace_in_crop']} head, saved passport_crop_{preset_name}.jpg")
        else:
            print(f"{preset_name}: Error - {result['error']}")
