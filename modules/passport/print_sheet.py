"""
Print Sheet Generator
=====================
สร้างแผ่นรวมรูป passport photo สำหรับพิมพ์จริง

Layouts:
- 4x6" print: 6-up (2 columns × 3 rows)
- 5x7" print: 4-up (2 columns × 2 rows)
- A4 print: multi-configurable

Guidelines are added as thin dashed lines for easy cutting.
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
) -> dict:
    """
    Generate a print-ready sheet with multiple passport photos.

    Args:
        passport_image: RGB passport photo (already at correct dimensions)
        template_w_mm: template width in mm
        template_h_mm: template height in mm
        print_size: "4x6" | "5x7" | "a4" | "a6"
        dpi: target print DPI
        margin_mm: margin between photos in mm
        add_guidelines: add cut lines

    Returns:
        dict with:
            - ok: bool
            - result: RGB print sheet image
            - info: metadata (cols, rows, count, etc.)
    """
    ps = PRINT_SIZES.get(print_size)
    if not ps:
        return {"ok": False, "error": f"Unknown print size: {print_size}"}

    # Calculate print sheet pixel dimensions
    sheet_w = int(round(ps["width_mm"] / 25.4 * dpi))
    sheet_h = int(round(ps["height_mm"] / 25.4 * dpi))

    photo_w = int(round(template_w_mm / 25.4 * dpi))
    photo_h = int(round(template_h_mm / 25.4 * dpi))

    margin_px = int(round(margin_mm / 25.4 * dpi))
    padding_px = max(margin_px, 10)  # at least 10px

    # Ensure passport_image matches expected dimensions
    if passport_image.shape[1] != photo_w or passport_image.shape[0] != photo_h:
        passport_image = cv2.resize(passport_image, (photo_w, photo_h), interpolation=cv2.INTER_LANCZOS4)

    # Calculate grid layout
    cols = (sheet_w + padding_px) // (photo_w + padding_px)
    rows = (sheet_h + padding_px) // (photo_h + padding_px)

    if cols < 1:
        cols = 1
    if rows < 1:
        rows = 1

    # Maximum count
    count = cols * rows

    # If too many, center the grid
    total_w = cols * photo_w + (cols - 1) * padding_px
    total_h = rows * photo_h + (rows - 1) * padding_px
    offset_x = (sheet_w - total_w) // 2
    offset_y = (sheet_h - total_h) // 2

    # Create white sheet
    sheet = np.full((sheet_h, sheet_w, 3), 255, dtype=np.uint8)

    # Place photos
    positions = []
    for row in range(rows):
        for col in range(cols):
            x = offset_x + col * (photo_w + padding_px)
            y = offset_y + row * (photo_h + padding_px)

            x2 = min(x + photo_w, sheet_w)
            y2 = min(y + photo_h, sheet_h)
            pw = x2 - x
            ph = y2 - y

            if pw > 0 and ph > 0:
                paste = passport_image[:ph, :pw]
                sheet[y:y2, x:x2] = paste
                positions.append({"x": x, "y": y, "w": pw, "h": ph})

    # Add cut guidelines
    if add_guidelines:
        sheet = _add_guidelines(sheet, positions)

    # Save info
    info = {
        "print_size": print_size,
        "dpi": dpi,
        "cols": cols,
        "rows": rows,
        "count": count,
        "sheet_pixels": {"w": sheet_w, "h": sheet_h},
        "sheet_mm": {"w": ps["width_mm"], "h": ps["height_mm"]},
        "photo_mm": {"w": template_w_mm, "h": template_h_mm},
    }

    logger.info(f"Print sheet: {cols}x{rows}={count} photos on {print_size} ({sheet_w}x{sheet_h}px)")
    return {"ok": True, "result": sheet, "info": info}


def _add_guidelines(sheet: np.ndarray, positions: list) -> np.ndarray:
    """Add thin dashed cut lines around each photo."""
    result = sheet.copy()
    h, w = result.shape[:2]

    for pos in positions:
        x, y, pw, ph = pos["x"], pos["y"], pos["w"], pos["h"]

        # Draw dashed rectangle (thin gray lines)
        dash_len = 8
        gap_len = 4
        color = (180, 180, 180)
        thickness = 1

        # Top edge
        for dx in range(0, pw, dash_len + gap_len):
            x1 = x + dx
            x2 = min(x1 + dash_len, x + pw)
            cv2.line(result, (x1, y), (x2, y), color, thickness)

        # Bottom edge
        for dx in range(0, pw, dash_len + gap_len):
            x1 = x + dx
            x2 = min(x1 + dash_len, x + pw)
            cv2.line(result, (x1, y + ph), (x2, y + ph), color, thickness)

        # Left edge
        for dy in range(0, ph, dash_len + gap_len):
            y1 = y + dy
            y2 = min(y1 + dash_len, y + ph)
            cv2.line(result, (x, y1), (x, y2), color, thickness)

        # Right edge
        for dy in range(0, ph, dash_len + gap_len):
            y1 = y + dy
            y2 = min(y1 + dash_len, y + ph)
            cv2.line(result, (x + pw, y1), (x + pw, y2), color, thickness)

    return result
