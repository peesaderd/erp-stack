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
import math

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
        color: Hex color (e.g. "#FFFFFF") OR CSS-style gradient string:
            - "linear-gradient(180deg,#aaa,#bbb)"  (0deg=to-top, 90deg=to-right, 180deg=to-bottom)
            - "radial-gradient(circle,#center,#edge)"
            - "HEX1,HEX2" (legacy = vertical top->bottom gradient)

    Returns:
        RGB image with background
    """
    w, h = pil_image.size
    if color and "linear-gradient" in color:
        bg = _grad_bg(w, h, color, radial=False)
        bg.paste(pil_image, (0, 0), pil_image)
        return bg.convert("RGB")
    if color and "radial-gradient" in color:
        bg = _grad_bg(w, h, color, radial=True)
        bg.paste(pil_image, (0, 0), pil_image)
        return bg.convert("RGB")
    if color and "," in color:
        # Legacy / simple vertical gradient: "HEX1,HEX2"
        c1, c2 = color.split(",")[:2]
        rad = "linear-gradient(180deg,{},{})".format((c1 or "#FFFFFF").strip(), (c2 or "#C4DCFF").strip())
        bg = _grad_bg(w, h, rad, radial=False)
        bg.paste(pil_image, (0, 0), pil_image)
        return bg.convert("RGB")
    bg = Image.new("RGBA", pil_image.size, color)
    bg.paste(pil_image, (0, 0), pil_image)
    return bg.convert("RGB")


def _hex_rgb(hexstr):
    """Parse #RGB / #RRGGBB / #RRGGBBAA (alpha ignored) -> (r,g,b)."""
    c = hexstr.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) >= 6:
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return (255, 255, 255)


def _lerp(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def _split_css_colors(s):
    """Split a comma list returning only hex-looking color tokens (up to 2)."""
    if not s:
        return []
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return [p for p in parts if "#" in p][:2]


def _grad_bg(w, h, css, radial=False):
    """Build RGB gradient background from a CSS-style gradient string using pure PIL."""
    start = css.find("(")
    end = css.rfind(")")
    body = css[start + 1:end] if start != -1 and end != -1 and end > start else css

    if radial:
        # radial-gradient(circle,#center,#edge)
        colors = _split_css_colors(body.split("circle", 1)[-1] if "circle" in body else body)
        c_center = _hex_rgb(colors[0]) if colors else (255, 255, 255)
        c_edge = _hex_rgb(colors[1]) if len(colors) > 1 else c_center
        cx, cy = w / 2.0, h / 2.0
        max_r = (cx ** 2 + cy ** 2) ** 0.5
        bg = Image.new("RGB", (w, h))
        px = bg.load()
        for y in range(h):
            for x in range(w):
                d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                t = min(1.0, d / max(1, max_r))
                px[x, y] = _lerp(c_center, c_edge, t)
        return bg

    # linear-gradient([<angle>deg,] c1[,c2])
    first = body.split(",", 1)[0].strip()
    angle = 180
    if "deg" in first:
        try:
            angle = int(first.replace("deg", "").strip()) % 360
        except ValueError:
            angle = 180
        rest = body.split(",", 1)[1] if "," in body else ""
    else:
        rest = body
    colors = _split_css_colors(rest)
    c1 = _hex_rgb(colors[0]) if colors else (255, 255, 255)
    c2 = _hex_rgb(colors[1]) if len(colors) > 1 else c1

    rad = math.radians(angle)
    dx = math.sin(rad)
    dy = -math.cos(rad)
    proj_len = abs(dx) * w + abs(dy) * h
    if proj_len <= 0:
        proj_len = 1
    cx, cy = w / 2.0, h / 2.0
    bg = Image.new("RGB", (w, h))
    px = bg.load()
    for y in range(h):
        for x in range(w):
            t = ((x - cx) * dx + (y - cy) * dy) / proj_len + 0.5
            t = max(0.0, min(1.0, t))
            px[x, y] = _lerp(c1, c2, t)
    return bg


