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
    "6x4": {"width_mm": 152.4, "height_mm": 101.6},
    "5x7": {"width_mm": 127.0, "height_mm": 177.8},
    "7x5": {"width_mm": 177.8, "height_mm": 127.0},
    "a4": {"width_mm": 210.0, "height_mm": 297.0},
    "a4_l": {"width_mm": 297.0, "height_mm": 210.0},
    "a6": {"width_mm": 105.0, "height_mm": 148.0},
    "a6_l": {"width_mm": 148.0, "height_mm": 105.0},
}


def generate_print_sheet(
    passport_image: np.ndarray,
    template_w_mm: float,
    template_h_mm: float,
    print_size: str = "4x6",
    dpi: int = 300,
    margin_mm: float = 3.0,
    add_guidelines: bool = True,
    border: str = "none",
    gap_mm: float = 0.0,
    blade_mode: bool = False,
    photo_count: int = 0,
    border_color: str = "#FFFFFF",
    border_width_mm: float = 0.0,
    hairline: bool = False,
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
        add_guidelines: unused (kept for backward compat)
        border: "none" | "white" | "frame" (frame = border_color + border_width_mm)
        gap_mm: gap between photos in mm
        blade_mode: if True, add extra gap for cutting blade
        photo_count: 0 = auto-fill, >0 = limit photo count
        border_color: hex color for frame border (default #FFFFFF)
        border_width_mm: border width in mm (default 0 = no border)

    Returns:
        dict with ok, result, info
    """
    ps = PRINT_SIZES.get(print_size)
    if not ps:
        return {"ok": False, "error": f"Unknown print size: {print_size}"}

    # Calculate print sheet pixel dimensions
    sheet_w = int(round(ps["width_mm"] / 25.4 * dpi))
    sheet_h = int(round(ps["height_mm"] / 25.4 * dpi))

    # Border adds to each photo's outer dimensions
    border_px = int(round(border_width_mm / 25.4 * dpi)) if border_width_mm > 0 else 0
    photo_w = int(round(template_w_mm / 25.4 * dpi)) + border_px * 2
    photo_h = int(round(template_h_mm / 25.4 * dpi)) + border_px * 2

    # Use gap_mm for padding (supports cutting blade)
    padding_px = int(round(gap_mm / 25.4 * dpi))
    if blade_mode:
        padding_px = int(round(max(gap_mm, 5.0) / 25.4 * dpi))

    # Ensure passport_image matches expected passport dimensions (without border)
    passport_w = int(round(template_w_mm / 25.4 * dpi))
    passport_h = int(round(template_h_mm / 25.4 * dpi))
    if passport_image.shape[1] != passport_w or passport_image.shape[0] != passport_h:
        passport_image = cv2.resize(passport_image, (passport_w, passport_h), interpolation=cv2.INTER_LANCZOS4)

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

    # Parse border color
    bc = (255, 255, 255)  # default white
    if border_color and border_color.startswith("#"):
        try:
            h = border_color.lstrip("#")
            bc = (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))  # BGR for OpenCV
        except Exception:
            bc = (255, 255, 255)

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
                # Draw border first (if any)
                if border_px > 0:
                    sheet[y:y2, x:x2] = bc
                    # Place passport photo centered inside border
                    inner_x = x + border_px
                    inner_y = y + border_px
                    inner_x2 = inner_x + passport_w
                    inner_y2 = inner_y + passport_h
                    # Clamp to sheet bounds
                    if inner_x2 <= sheet_w and inner_y2 <= sheet_h:
                        sheet[inner_y:inner_y2, inner_x:inner_x2] = passport_image
                else:
                    sheet[y:y2, x:x2] = passport_image
                positions.append({"x": x, "y": y, "w": pw, "h": ph})
                placed += 1
        if placed >= count:
            break

    info = {
        "print_size": print_size,
        "dpi": dpi,
        "cols": cols,
        "rows": rows,
        "count": placed,
        "max_count": max_count,
        "border": border,
        "border_color": border_color,
        "border_width_mm": border_width_mm,
        "gap_mm": gap_mm,
        "blade_mode": blade_mode,
        "sheet_pixels": {"w": sheet_w, "h": sheet_h},
        "sheet_mm": {"w": ps["width_mm"], "h": ps["height_mm"]},
        "photo_mm": {"w": template_w_mm, "h": template_h_mm},
    }

    if hairline:
        sheet = _add_hairline(sheet, positions)
    logger.info(f"Print sheet: {cols}x{rows}={placed}/{max_count} photos on {print_size} (border={border}, border_width={border_width_mm}mm)")
    return {"ok": True, "result": sheet, "info": info}


def _add_hairline(sheet: np.ndarray, positions: list, margin: int = 0) -> np.ndarray:
    """Owner spec v3: cut guide at FULL darkness but HALF thickness.
    True 0.5px: dashed lines drawn on a 2x supersampled mask (thickness 1),
    downscaled with INTER_AREA -> crisp ~0.5px core, same tone as before."""
    h, w = sheet.shape[:2]
    SC = 2
    mask2 = np.zeros((h * SC, w * SC), np.uint8)
    color = 205          # same darkness as approved v2
    strength = 0.25      # same ink level as approved v2
    dl, gp = 16, 10      # dash pattern scaled 2x
    for pos in positions:
        x = max(pos["x"] - margin, 0); y = max(pos["y"] - margin, 0)
        x2 = min(pos["x"] + pos["w"] + margin, w - 1); y2 = min(pos["y"] + pos["h"] + margin, h - 1)
        X, Y, X2, Y2 = x * SC, y * SC, x2 * SC, y2 * SC
        pw, ph = X2 - X, Y2 - Y
        for dx in range(0, pw, dl + gp):
            cv2.line(mask2, (X + dx, Y), (min(X + dx + dl, X2), Y), 255, 1)
            cv2.line(mask2, (X + dx, Y2), (min(X + dx + dl, X2), Y2), 255, 1)
        for dy in range(0, ph, dl + gp):
            cv2.line(mask2, (X, Y + dy), (X, min(Y + dy + dl, Y2)), 255, 1)
            cv2.line(mask2, (X2, Y + dy), (X2, min(Y + dy + dl, Y2)), 255, 1)
    mask = cv2.resize(mask2, (w, h), interpolation=cv2.INTER_AREA)
    a = (mask.astype(np.float32) / 255.0) * strength
    sel = a > 0.02
    base = sheet[sel].astype(np.float32)
    alpha = a[sel][:, None]
    sheet[sel] = (base * (1 - alpha) + color * alpha).astype(np.uint8)
    return sheet


def _add_guidelines(sheet: np.ndarray, positions: list) -> np.ndarray:
    """Add ultra-thin dashed cut lines using 4x supersampling for ~0.25px lines."""
    result = sheet.copy()
    scale = 4
    sh, sw = result.shape[:2]
    mask = np.full((sh * scale, sw * scale, 3), 255, dtype=np.uint8)
    dash_len = 8 * scale
    gap_len = 4 * scale
    color = (180, 180, 180)

    for pos in positions:
        x, y, pw, ph = pos["x"], pos["y"], pos["w"], pos["h"]
        # Top & bottom
        for dx in range(0, pw, dash_len + gap_len):
            x1 = x * scale + dx
            x2 = min(x1 + dash_len, (x + pw) * scale)
            cv2.line(mask, (x1, y * scale), (x2, y * scale), color, 1)
            cv2.line(mask, (x1, (y + ph) * scale), (x2, (y + ph) * scale), color, 1)
        # Left & right
        for dy in range(0, ph, dash_len + gap_len):
            y1 = y * scale + dy
            y2 = min(y1 + dash_len, (y + ph) * scale)
            cv2.line(mask, (x * scale, y1), (x * scale, y2), color, 1)
            cv2.line(mask, ((x + pw) * scale, y1), ((x + pw) * scale, y2), color, 1)

    # Downscale with INTER_AREA for anti-aliased thin lines
    thin = cv2.resize(mask, (sw, sh), interpolation=cv2.INTER_AREA)
    # Blend: white background + thin gray lines
    result = cv2.addWeighted(thin, 0.3, result, 0.7, 0)
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
    border_width_mm: float = 0.0,
    border_color: str = "#FFFFFF",
    hairline: bool = False,
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
    border_px = int(round(border_width_mm / 25.4 * dpi)) if (border == "frame" and border_width_mm > 0) else 0
    try:
        hcl = border_color.lstrip("#")
        bc = (int(hcl[4:6], 16), int(hcl[2:4], 16), int(hcl[0:2], 16))  # BGR
    except Exception:
        bc = (255, 255, 255)
    
    # Build list of photos to place (with copies), NORMALIZED to one size.
    # Fix 2026-08-24 13:11: old code resized each photo to ITS OWN mm dims,
    # a no-op for freshly generated squares -> mixing an un-recropped 1024x1024
    # with recropped portraits crashed broadcasting on paste.
    # Owner rule: TOP-CENTER scale-cover into the FIRST photo's cell size.
    def _fit_cover(img, tw, th):
        ih, iw = img.shape[:2]
        scale = max(tw / iw, th / ih)
        nw = max(tw, int(round(iw * scale)))
        nh = max(th, int(round(ih * scale)))
        out = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
        x0 = (nw - tw) // 2
        y0 = 0                                    # anchor TOP (head safe)
        return out[y0:y0 + th, x0:x0 + tw]

    raw_list = []
    for _img in images:
        for _c in range(copies):
            raw_list.append(_img)
    if not raw_list:
        return {"ok": False, "error": "No photos to place"}

    # Cell basis = SMALLEST-area photo: uniform pools unchanged, mixed pools
    # keep a usable passport-sized grid instead of one giant tile.
    _i0 = min(range(len(raw_list)),
              key=lambda k: raw_list[k].shape[0] * raw_list[k].shape[1])
    ref_h, ref_w = raw_list[_i0].shape[:2]
    photo_list = [_fit_cover(im, ref_w, ref_h) for im in raw_list]
    cell_w = ref_w + border_px * 2   # owner: real white RING around each photo
    cell_h = ref_h + border_px * 2
    
    cols = (sheet_w + padding_px) // (cell_w + padding_px)
    rows = (sheet_h + padding_px) // (cell_h + padding_px)
    if cols < 1: cols = 1
    if rows < 1: rows = 1
    
    max_count = cols * rows
    count = min(len(photo_list), max_count)
    
    # Center the grid
    total_w = cols * cell_w + (cols - 1) * padding_px
    total_h = rows * cell_h + (rows - 1) * padding_px
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
            x = offset_x + col * (cell_w + padding_px)
            y = offset_y + row * (cell_h + padding_px)
            x2 = min(x + cell_w, sheet_w)
            y2 = min(y + cell_h, sheet_h)
            cw_ = x2 - x
            ch_ = y2 - y
            if cw_ > 0 and ch_ > 0:
                if border_px > 0:
                    sheet[y:y2, x:x2] = bc          # white ring
                    ix, iy = x + border_px, y + border_px
                    sheet[iy:iy + ref_h, ix:ix + ref_w] = photo_list[placed]
                else:
                    sheet[y:y2, x:x2] = photo_list[placed]
                positions.append({"x": x, "y": y, "w": cw_, "h": ch_})
                placed += 1
        if placed >= count:
            break
    
    # Add border/guidelines
    if border == "frame":
        if border_px == 0:
            sheet = _add_frame(sheet, positions)   # legacy thin stroke when no ring width given
    elif border == "guidelines":
        sheet = _add_guidelines(sheet, positions)
    if hairline:
        sheet = _add_hairline(sheet, positions)    # owner: cut line OUTSIDE borders
    
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
        "border_width_mm": border_width_mm,
        "hairline": hairline,
        "gap_mm": gap_mm,
        "blade_mode": blade_mode,
        "sheet_pixels": {"w": sheet_w, "h": sheet_h},
        "sheet_mm": {"w": sheet_w / dpi * 25.4, "h": sheet_h / dpi * 25.4},
        "photo_mm": {"w": dims_mm[0][0] if dims_mm else 0, "h": dims_mm[0][1] if dims_mm else 0},
    }
    
    logger.info(f"Multi-print: {cols}x{rows}={placed}/{max_count} photos ({len(images)} unique x {copies} copies) on {print_size}")
    return {"ok": True, "result": sheet, "info": info}
