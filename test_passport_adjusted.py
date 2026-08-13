"""
Test passport photo with ADJUSTED settings:
- GFPGAN strength: 0.2 (from 0.7) — preserve beard/facial features
- Skin smoothing: 10% (from 30%) — keep natural skin texture
- Skip inpaint_scratches — avoid removing facial hair as "damage"
"""
import sys, os
sys.path.insert(0, '/home/openhands/erp-stack')
os.chdir('/home/openhands/erp-stack')

import cv2
import numpy as np
from pathlib import Path

# Load test image
img = cv2.imread('test_input.jpg')
if img is None:
    print("ERROR: Cannot read test_input.jpg")
    sys.exit(1)

print(f"Input: {img.shape[1]}x{img.shape[0]}")

# Convert to RGB for processing
img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

# ══════════════════════════════════════════════════════════
# STEP 1: Face detection + crop (same as original)
# ══════════════════════════════════════════════════════════
from modules.passport.face_detector import detect_face
face = detect_face(img_rgb)
if face is None:
    print("WARNING: No face detected, using center crop")
    h, w = img_rgb.shape[:2]
    cx, cy = w // 2, h // 3
    face = {"bbox": (cx - 100, cy - 120, 200, 280)}

print(f"Face: {face}")

# Crop to passport aspect ratio (35x45mm = 7:9)
fx, fy = face["x"], face["y"]
fw, fh = face["w"], face["h"]
src_h, src_w = img_rgb.shape[:2]

# Calculate crop with headspace
target_ratio = 45 / 35  # height/width
face_top = fy

# Head at ~12% from top
headspace_target = int(src_h * 0.12)
y_offset = max(0, face_top - headspace_target)
new_h = int(src_w * target_ratio)
if y_offset + new_h > src_h:
    new_h = src_h - y_offset
new_w = int(new_h / target_ratio)

# Center horizontally on face
x_offset = max(0, min(fx + fw // 2 - new_w // 2, src_w - new_w))

cropped = img_rgb[y_offset:y_offset + new_h, x_offset:x_offset + new_w]
print(f"Cropped: {cropped.shape[1]}x{cropped.shape[0]}")

# ══════════════════════════════════════════════════════════
# STEP 2: Background removal (rembg — gentle settings)
# ══════════════════════════════════════════════════════════
from rembg import remove as rembg_remove
from PIL import Image

pil_img = Image.fromarray(cropped)
nobg = rembg_remove(
    pil_img,
    alpha_matting=True,
    alpha_matting_foreground_threshold=200,
    alpha_matting_background_threshold=10,
    alpha_matting_erode_size=0,  # No erosion — preserves beard
)
print("Background removed")

# Replace with white background
bg = Image.new("RGBA", nobg.size, (255, 255, 255, 255))
bg.paste(nobg, (0, 0), nobg)
result_rgb = np.array(bg.convert("RGB"))

# ══════════════════════════════════════════════════════════
# STEP 3: GFPGAN — ADJUSTED (strength 0.2 instead of 0.7)
# ══════════════════════════════════════════════════════════
gfpgan_strength = 0.2  # Was 0.7 — much gentler now

GFPGAN_MODEL = os.path.expanduser("~/.cache/gfpgan/GFPGANv1.4.pth")
if os.path.exists(GFPGAN_MODEL):
    try:
        import sys as _sys
        # Fix path conflicts
        _erp_stack = str(Path('/home/openhands/erp-stack'))
        _saved = [p for p in _sys.path if _erp_stack in p]
        for p in _saved:
            _sys.path.remove(p)
        try:
            from gfpgan import GFPGANer
        finally:
            _sys.path = _saved + _sys.path

        restorer = GFPGANer(
            model_path=GFPGAN_MODEL,
            upscale=1, arch='clean', channel_multiplier=2,
            bg_upsampler=None,
        )
        _, _, enhanced = restorer.enhance(
            result_rgb, has_aligned=False, only_center_face=False, paste_back=True
        )
        if enhanced is not None and enhanced.shape == result_rgb.shape:
            result_rgb = cv2.addWeighted(enhanced, gfpgan_strength, result_rgb, 1 - gfpgan_strength, 0)
            print(f"GFPGAN applied (strength={gfpgan_strength})")
        else:
            print("GFPGAN: shape mismatch, skipped")
    except Exception as e:
        print(f"GFPGAN error: {e}")
else:
    print("GFPGAN model not found, skipped")

# ══════════════════════════════════════════════════════════
# STEP 4: Skin smoothing — ADJUSTED (10% instead of 30%)
# ══════════════════════════════════════════════════════════
smooth_strength = 0.10  # Was 0.30 — keep natural skin

# Detect skin region
hsv = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2HSV)
skin_lower = np.array([0, 20, 70])
skin_upper = np.array([25, 150, 255])
skin_mask = cv2.inRange(hsv, skin_lower, skin_upper)
skin_mask = cv2.GaussianBlur(skin_mask, (5, 5), 0)

# Gentle bilateral filter
smoothed = cv2.bilateralFilter(result_rgb, 5, 30, 30)

# Blend: only smooth skin regions, very subtle
skin_mask_3 = np.stack([skin_mask] * 3, axis=-1).astype(np.float32) / 255.0
result_rgb = (result_rgb.astype(np.float32) * (1 - skin_mask_3 * smooth_strength) +
              smoothed.astype(np.float32) * (skin_mask_3 * smooth_strength)).astype(np.uint8)
print(f"Skin smoothing applied (strength={smooth_strength})")

# ══════════════════════════════════════════════════════════
# STEP 5: Final color/contrast — SUBTLE
# ══════════════════════════════════════════════════════════
# Very gentle CLAHE on luminance only
lab = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2LAB)
l, a, b = cv2.split(lab)
clahe = cv2.createCLAHE(clipLimit=1.0, tileGridSize=(4, 4))
l = clahe.apply(l)
lab = cv2.merge([l, a, b])
result_rgb = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
print("Color/contrast adjusted (subtle)")

# ══════════════════════════════════════════════════════════
# STEP 6: Resize to passport dimensions (35x45mm @ 300dpi)
# ══════════════════════════════════════════════════════════
passport_w = 413  # 35mm @ 300dpi
passport_h = 531  # 45mm @ 300dpi
final = cv2.resize(result_rgb, (passport_w, passport_h), interpolation=cv2.INTER_LANCZOS4)

# Save results
cv2.imwrite('test_result_adjusted.jpg', cv2.cvtColor(final, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 95])
print(f"Saved: test_result_adjusted.jpg ({passport_w}x{passport_h})")

# Also save a comparison: original cropped vs adjusted
cv2.imwrite('test_comparison_input.jpg', cv2.cvtColor(cropped, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 95])
print("Saved: test_comparison_input.jpg (original cropped)")
