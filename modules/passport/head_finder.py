"""
Simple head position finder — scan from top down.
Head position = distance from image top to head top.
"""
import cv2
import numpy as np
import sys

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


def crop_passport_auto(image, preset="standard", dpi=300):
    """
    Auto-crop passport photo.
    เลือก preset: standard, compact, relaxed
    """
    h, w = image.shape[:2]
    target_w_mm, target_h_mm = 35, 45
    crop_ratio = target_w_mm / target_h_mm

    cfg = CROP_PRESETS.get(preset, CROP_PRESETS["standard"])
    target_head_top_pct = cfg["target_head_top_pct"]
    face_width_ratio = cfg["face_width_ratio"]

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
