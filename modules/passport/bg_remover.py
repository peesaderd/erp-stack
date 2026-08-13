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
    Apply solid color background to transparent image.
    
    Args:
        pil_image: RGBA image with transparency
        color: Hex color (e.g. "#FFFFFF", "#C4DCFF")
        
    Returns:
        RGB image with background
    """
    bg = Image.new("RGBA", pil_image.size, color)
    bg.paste(pil_image, (0, 0), pil_image)
    return bg.convert("RGB")
