"""
Print Sheet Generator
====================
สร้างแผ่นรวมรูป passport photo สำหรับพิมพ์จริง

Layouts:
- 4x6" print: 6-up (2 columns × 3 rows)
- 5x7" print: 4-up (2 columns × 2 rows)
- A4 print: multi-configurable

Options:
- border: "none" | "guidelines" | "frame"
- gap_mm: cutting blade gap (default 3mm)
- blade_mode: True/False for cutting blade support
"""

import logging
import cv2
import numpy as np

logger = logging.getLogger("passport.print_sheet")

# Standard print sizes in mm
PRINT_SIZES = {
    "4x6": {"width_mm": 101.6, "height_mm": 152.4},
    "5x7": {"width_mm": 127.0, "height_mm": 177.8},
    "a4": {"width_mm": 210.0, "height_mm": 297.0},
    "a6": {"width_mm": 105.0, "height_mm": 148.0},
}


def generate_print_sheet(
    passport_image: np.ndarray,
    template_w_mm: float,
    template_h_mm: float,
    print_size: str = "4x6",
    dpi: int = 300,
    margin_mm: float = 3.0,
    add_guidelines: bool = True,
    border: str = "guidelines",
    gap_mm: float = 3.0,
    blade_mode: bool = False,
    photo_count: int = 0,
) -> dict:
    """
    Generate a print-ready sheet with multiple passport photos.

    Args:
        passport_image: RGB passport photo (already at correct dimensions)
        template_w_mm: template width in mm
        template_h_mm: template height in mm
        print_size: "4x6" | "5x7" | "a4" | "a6"
        dpi: target print DPI
        margin_mm: margin between photos in mm (legacy, use gap_mm)
        add_guidelines: add cut lines (legacy, use border param)
        border: "none" | "guidelines" | "frame"
        gap_mm: gap between photos in mm (for cutting blade)
        blade_mode: if True, add extra gap for cutting blade
        photo_count: 0 = auto-fill, >0 = limit photo count

    Returns:
        dict with ok, result, info
    """
    ps = PRINT_SIZES.get(print_size)
    if not ps:
        return {"ok": False, "error": f"Unknown print size: {print_size}"}

    # Calculate print sheet pixel dimensions
    sheet_w = int(round(ps["width_mm"] / 25.4 * dpi))
    sheet_h = int(round(ps["height_mm"] / 25.4 * dpi))

    photo_w = int(round(template_w_mm / 25.4 * dpi))
    photo_h = int(round(template_h_mm / 25.4 * dpi))

    # Use gap_mm for padding (supports cutting blade)
    padding_px = int(round(gap_mm / 25.4 * dpi))
    if blade_mode:
        padding_px = int(round(max(gap_mm, 5.0) / 25.4 * dpi))

    # Ensure passport_image matches expected dimensions
    if passport_image.shape[1] != photo_w or passport_image.shape[0] != photo_h:
        passport_image = cv2.resize(passport_image, (photo_w, photo_h), interpolation=cv2.INTER_LANCZOS4)

    # Calculate grid layout
    cols = (sheet_w + padding_px) // (photo_w + padding_px)
    rows = (sheet_h + padding_px) // (photo_h + padding_px)
    if cols < 1: cols = 1
    if rows < 1: rows = 1

    max_count = cols * rows
    count = photo_count if 0 < photo_count <= max_count else max_count

    # Center the grid
    total_w = cols * photo_w + (cols - 1) * padding_px
    total_h = rows * photo_h + (rows - 1) * padding_px
    offset_x = (sheet_w - total_w) // 2
    offset_y = (sheet_h - total_h) // 2

    # Create white sheet
    sheet = np.full((sheet_h, sheet_w, 3), 255, dtype=np.uint8)

    # Place photos (respect photo_count limit)
    positions = []
    placed = 0
    for row in range(rows):
        for col in range(cols):
            if placed >= count:
                break
            x = offset_x + col * (photo_w + padding_px)
            y = offset_y + row * (photo_h + padding_px)
            x2 = min(x + photo_w, sheet_w)
            y2 = min(y + photo_h, sheet_h)
            pw = x2 - x
            ph = y2 - y
            if pw > 0 and ph > 0:
                sheet[y:y2, x:x2] = passport_image[:ph, :pw]
                positions.append({"x": x, "y": y, "w": pw, "h": ph})
                placed += 1
        if placed >= count:
            break

    # Add border/guidelines
    if border == "frame":
        sheet = _add_frame(sheet, positions)
    elif border == "guidelines" or add_guidelines:
        sheet = _add_guidelines(sheet, positions)

    info = {
        "print_size": print_size,
        "dpi": dpi,
        "cols": cols,
        "rows": rows,
        "count": placed,
        "max_count": max_count,
        "border": border,
        "gap_mm": gap_mm,
        "blade_mode": blade_mode,
        "sheet_pixels": {"w": sheet_w, "h": sheet_h},
        "sheet_mm": {"w": ps["width_mm"], "h": ps["height_mm"]},
        "photo_mm": {"w": template_w_mm, "h": template_h_mm},
    }

    logger.info(f"Print sheet: {cols}x{rows}={placed}/{max_count} photos on {print_size} (border={border})")
    return {"ok": True, "result": sheet, "info": info}


def _add_guidelines(sheet: np.ndarray, positions: list) -> np.ndarray:
    """Add thin dashed cut lines around each photo."""
    result = sheet.copy()
    dash_len = 8
    gap_len = 4
    color = (180, 180, 180)
    thickness = 1

    for pos in positions:
        x, y, pw, ph = pos["x"], pos["y"], pos["w"], pos["h"]
        # Top & bottom
        for dx in range(0, pw, dash_len + gap_len):
            x1 = x + dx
            x2 = min(x1 + dash_len, x + pw)
            cv2.line(result, (x1, y), (x2, y), color, thickness)
            cv2.line(result, (x1, y + ph), (x2, y + ph), color, thickness)
        # Left & right
        for dy in range(0, ph, dash_len + gap_len):
            y1 = y + dy
            y2 = min(y1 + dash_len, y + ph)
            cv2.line(result, (x, y1), (x, y2), color, thickness)
            cv2.line(result, (x + pw, y1), (x + pw, y2), color, thickness)

    return result


def _add_frame(sheet: np.ndarray, positions: list) -> np.ndarray:
    """Add solid white frame border around each photo."""
    result = sheet.copy()
    color = (255, 255, 255)
    thickness = 3

    for pos in positions:
        x, y, pw, ph = pos["x"], pos["y"], pos["w"], pos["h"]
        cv2.rectangle(result, (x - 1, y - 1), (x + pw + 1, y + ph + 1), color, thickness)

    return result


def generate_multi_print_sheet(
    images: list,
    dims_mm: list,
    copies: int = 1,
    print_size: str = "4x6",
    dpi: int = 300,
    gap_mm: float = 3.0,
    border: str = "guidelines",
    blade_mode: bool = False,
) -> dict:
    """
    Generate a print sheet with multiple different photos.
    Each photo appears `copies` times.
    
    Args:
        images: list of RGB numpy arrays
        dims_mm: list of (width_mm, height_mm) tuples
        copies: number of times each photo appears
        print_size: "4x6" | "5x7" | "a4" | "a6"
        dpi: target DPI
        gap_mm: gap between photos
        border: "none" | "guidelines" | "frame"
        blade_mode: extra gap for cutting blade
    
    Returns:
        dict with ok, result, info
    """
    ps = PRINT_SIZES.get(print_size)
    if not ps:
        return {"ok": False, "error": f"Unknown print size: {print_size}"}
    
    sheet_w = int(round(ps["width_mm"] / 25.4 * dpi))
    sheet_h = int(round(ps["height_mm"] / 25.4 * dpi))
    
    padding_px = int(round(gap_mm / 25.4 * dpi))
    if blade_mode:
        padding_px = int(round(max(gap_mm, 5.0) / 25.4 * dpi))
    
    # Build list of photos to place (with copies)
    photo_list = []
    for i, (img, (w_mm, h_mm)) in enumerate(zip(images, dims_mm)):
        pw = int(round(w_mm / 25.4 * dpi))
        ph = int(round(h_mm / 25.4 * dpi))
        resized = cv2.resize(img, (pw, ph), interpolation=cv2.INTER_LANCZOS4)
        for c in range(copies):
            photo_list.append(resized)
    
    if not photo_list:
        return {"ok": False, "error": "No photos to place"}
    
    # Use first photo dimensions for grid calculation (assume same passport size)
    ref_h, ref_w = photo_list[0].shape[:2]
    
    cols = (sheet_w + padding_px) // (ref_w + padding_px)
    rows = (sheet_h + padding_px) // (ref_h + padding_px)
    if cols < 1: cols = 1
    if rows < 1: rows = 1
    
    max_count = cols * rows
    count = min(len(photo_list), max_count)
    
    # Center the grid
    total_w = cols * ref_w + (cols - 1) * padding_px
    total_h = rows * ref_h + (rows - 1) * padding_px
    offset_x = (sheet_w - total_w) // 2
    offset_y = (sheet_h - total_h) // 2
    
    # Create white sheet
    sheet = np.full((sheet_h, sheet_w, 3), 255, dtype=np.uint8)
    
    # Place photos
    positions = []
    placed = 0
    for row in range(rows):
        for col in range(cols):
            if placed >= count:
                break
            x = offset_x + col * (ref_w + padding_px)
            y = offset_y + row * (ref_h + padding_px)
            x2 = min(x + ref_w, sheet_w)
            y2 = min(y + ref_h, sheet_h)
            pw = x2 - x
            ph = y2 - y
            if pw > 0 and ph > 0:
                sheet[y:y2, x:x2] = photo_list[placed][:ph, :pw]
                positions.append({"x": x, "y": y, "w": pw, "h": ph})
                placed += 1
        if placed >= count:
            break
    
    # Add border/guidelines
    if border == "frame":
        sheet = _add_frame(sheet, positions)
    elif border == "guidelines":
        sheet = _add_guidelines(sheet, positions)
    
    info = {
        "print_size": print_size,
        "dpi": dpi,
        "cols": cols,
        "rows": rows,
        "count": placed,
        "max_count": max_count,
        "total_photos": len(photo_list),
        "unique_photos": len(images),
        "copies_per_photo": copies,
        "border": border,
        "gap_mm": gap_mm,
        "blade_mode": blade_mode,
    }
    
    logger.info(f"Multi-print: {cols}x{rows}={placed}/{max_count} photos ({len(images)} unique x {copies} copies) on {print_size}")
    return {"ok": True, "result": sheet, "info": info}
