"""
Background removal using Prodia mask-background API.
"""
import os
import json
import logging
from pathlib import Path
import urllib.request
from io import BytesIO
from PIL import Image

logger = logging.getLogger("passport.bg_remover")

# Get Prodia token
_erp_stack = Path(__file__).parent.parent.parent
_env_path = _erp_stack / ".env"

def _get_env(key):
    val = os.environ.get(key)
    if val:
        return val
    if _env_path.exists():
        for line in open(_env_path):
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None

PRODIA_TOKEN = _get_env("PRODIA_TOKEN")
PRODIA_API_URL = "https://inference.prodia.com/v2/job"


def remove_background(image_bytes: bytes) -> tuple:
    """
    Remove background using Prodia mask-background API.
    
    Args:
        image_bytes: Input image bytes (JPEG/PNG)
        
    Returns:
        tuple of (transparent_png_bytes, pil_image)
    """
    if not PRODIA_TOKEN:
        raise RuntimeError("No PRODIA_TOKEN configured")
    
    # Create multipart form data
    boundary = '----ProdiaRembg'
    body = b''
    body += f'--{boundary}\r\n'.encode()
    body += b'Content-Disposition: form-data; name="job"; filename="job.json"\r\n'
    body += b'Content-Type: application/json\r\n\r\n'
    body += json.dumps({'type': 'inference.mask-background.v1', 'config': {}}).encode()
    body += b'\r\n'
    body += f'--{boundary}\r\n'.encode()
    body += b'Content-Disposition: form-data; name="input"; filename="image.jpg"\r\n'
    body += b'Content-Type: image/jpeg\r\n\r\n'
    body += image_bytes
    body += b'\r\n'
    body += f'--{boundary}--\r\n'.encode()
    
    headers = {
        'Authorization': f'Bearer {PRODIA_TOKEN}',
        'Content-Type': f'multipart/form-data; boundary={boundary}',
        'Accept': 'multipart/form-data; image/png'
    }
    
    req = urllib.request.Request(PRODIA_API_URL, data=body, headers=headers, method='POST')
    resp = urllib.request.urlopen(req, timeout=60)
    data = resp.read()
    
    # Parse multipart response
    resp_boundary = data[:50].split(b'--')[1] if b'--' in data[:50] else b''
    parts = data.split(b'--' + resp_boundary)
    
    mask_bytes = None
    for part in parts:
        if b'Content-Disposition' in part:
            header_end = part.find(b'\r\n\r\n')
            if header_end != -1:
                header = part[:header_end]
                body = part[header_end+4:]
                
                if b'job.json' in header:
                    try:
                        job_info = json.loads(body)
                        logger.info(f"Prodia job: {job_info.get('id')} - {job_info.get('state', {}).get('current')}")
                    except:
                        pass
                elif len(body) > 1000:  # Image data
                    mask_bytes = body
    
    if not mask_bytes:
        raise RuntimeError("No mask returned from Prodia")
    
    # Load original and mask
    original = Image.open(BytesIO(image_bytes)).convert('RGBA')
    mask = Image.open(BytesIO(mask_bytes)).convert('L')
    
    # Resize mask to match original if needed
    if mask.size != original.size:
        mask = mask.resize(original.size, Image.LANCZOS)
    
    # Apply mask as alpha channel
    original.putalpha(mask)
    
    # Convert to PNG bytes
    buf = BytesIO()
    original.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()
    
    logger.info(f"Background removed: {len(image_bytes)} -> {len(png_bytes)} bytes")
    return png_bytes, original


def apply_background(pil_image: Image.Image, color: str = "#FFFFFF") -> Image.Image:
    """
    Apply solid OR gradient background to transparent image.

    Args:
        pil_image: RGBA image with transparency
        color: Hex color (e.g. "#FFFFFF", "#C4DCFF") or gradient "HEX1,HEX2" (top->bottom)

    Returns:
        RGB image with background
    """
    w, h = pil_image.size
    if color and "," in color:
        # Gradient: "HEX1,HEX2" vertical top->bottom
        c1, c2 = color.split(",")[:2]
        c1 = c1.strip() or "#FFFFFF"
        c2 = c2.strip() or "#C4DCFF"
        def _hex(c):
            c = c.lstrip("#")
            return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
        r1, g1, b1 = _hex(c1)
        r2, g2, b2 = _hex(c2)
        bg = Image.new("RGB", (w, h))
        px = bg.load()
        for y in range(h):
            t = y / max(1, h - 1)
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            for x in range(w):
                px[x, y] = (r, g, b)
        bg_rgba = bg.convert("RGBA")
        bg_rgba.paste(pil_image, (0, 0), pil_image)
        return bg_rgba.convert("RGB")
    bg = Image.new("RGBA", pil_image.size, color)
    bg.paste(pil_image, (0, 0), pil_image)
    return bg.convert("RGB")


# ── Halo / residual-background cleanup (owner task 2026-08-24 16:06) ──
def clean_mask_halo(rgba, thr: float = 34.0, max_iter: int = 500):
    """
    Clean a BGRA ndarray returned by remove_background():
    1) leftover BACKGROUND baked as OPAQUE pixels (murky band when recoloured)
       -> flood-fill from borders over colour-similar pixels -> alpha=0
    2) gentle feather only on already-partial silhouette edge pixels
    Subject colours far from bg stay untouched (flood cannot cross hard edges).
    """
    import cv2 as _cv
    import numpy as _np

    out = rgba.copy()
    rgb = out[:, :, :3].astype(_np.int16)
    alpha = out[:, :, 3]
    h, w = alpha.shape

    border = ([(0, x) for x in range(w)] + [(h - 1, x) for x in range(w)]
              + [(y, 0) for y in range(h)] + [(y, w - 1) for y in range(h)])
    cols = _np.array([rgb[y, x] for y, x in border], dtype=_np.int16)
    als = _np.array([alpha[y, x] for y, x in border], dtype=_np.uint8)
    opaque = als > 200
    bg = _np.median(cols[opaque], axis=0) if opaque.any() else _np.median(cols, axis=0)

    dist = _np.sqrt(((rgb - bg.reshape(1, 1, 3)) ** 2).sum(axis=2))
    seed = _np.zeros((h, w), dtype=bool)
    bys = _np.array([p[0] for p in border]); bxs = _np.array([p[1] for p in border])
    seed[bys[dist[bys, bxs] < thr * 0.8], bxs[dist[bys, bxs] < thr * 0.8]] = True

    grown = seed.copy()
    allowed = dist < thr
    k = _np.ones((3, 3), _np.uint8)
    for _ in range(max_iter):
        step = (_cv.dilate(grown.astype(_np.uint8), k) > 0) & allowed & (~grown)
        if not step.any():
            break
        grown |= step

    out[:, :, 3] = _np.where(grown, 0, alpha)

    edge = ((alpha > 0) & (alpha < 255)).astype(_np.uint8)
    if edge.any():
        sm = _cv.GaussianBlur(out[:, :, 3], (3, 3), 0.9)
        out[:, :, 3] = _np.where(edge > 0, sm, out[:, :, 3])
    return out
