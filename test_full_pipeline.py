"""
Test full pipeline: FLUX i2i with adjusted settings
- strength: 0.45 (from 0.65) — preserve face more
- Prompt: explicit "preserve beard, mustache, facial hair"
"""
import sys, os, json, time
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

# Convert to bytes (as pipeline expects)
_, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
img_bytes = buf.tobytes()

# ══════════════════════════════════════════════════════════
# Run full pipeline via API (strength=0.45)
# ══════════════════════════════════════════════════════════
import base64
img_b64 = base64.b64encode(img_bytes).decode()

payload = json.dumps({
    "image_base64": img_b64,
    "template_code": "thai_passport",
    "gender": "auto",
    "clothing": "auto",
    "background": "auto",
    "strength": 0.45
}).encode()

import urllib.request
req = urllib.request.Request(
    "http://localhost:8122/api/passport/generate",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)

print("Calling FLUX i2i pipeline (strength=0.45)...")
t0 = time.time()
resp = urllib.request.urlopen(req, timeout=120)
result = json.loads(resp.read())
elapsed = round(time.time() - t0, 1)

if result.get("ok"):
    print(f"✅ Done in {elapsed}s")
    print(f"Info: {json.dumps(result.get('info', {}), indent=2)}")
    
    # Download the result
    dl_url = result.get("download_passport", "")
    if dl_url:
        dl_req = urllib.request.Request(f"http://localhost:8122{dl_url}")
        dl_resp = urllib.request.urlopen(dl_req)
        dl_bytes = dl_resp.read()
        with open('test_result_flux.jpg', 'wb') as f:
            f.write(dl_bytes)
        print(f"Saved: test_result_flux.jpg ({len(dl_bytes)} bytes)")
else:
    print(f"❌ Error: {result.get('error', 'unknown')}")
