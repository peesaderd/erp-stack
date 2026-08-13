"""
Re-crop v6 result with adjusted crop_y_pct (0.08 instead of 0.02)
Does NOT regenerate via FLUX — just re-crops the existing output.
"""
import sys, os, json, time, base64, urllib.request
sys.path.insert(0, '/home/openhands/erp-stack')
os.chdir('/home/openhands/erp-stack')

import cv2
import numpy as np

# Load v6 result (the FLUX output before final crop)
# v6 was generated with crop_y_pct=0.02, we need the intermediate FLUX output
# Since we don't have it saved, we'll use the v6 final result and try to adjust

# Actually, let's just take the FLUX raw output from the last run
# and re-crop with new parameters

# Read the original input
img = cv2.imread('test_input.jpg')
_, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
img_b64 = base64.b64encode(buf.tobytes()).decode()

# Call pipeline but save intermediate FLUX output
payload = json.dumps({
    'image_base64': img_b64,
    'template_code': 'thai_passport',
    'gender': 'auto',
    'clothing': 'auto',
    'background': 'auto',
    'strength': 0.45
}).encode()

req = urllib.request.Request(
    'http://localhost:8122/api/passport/generate',
    data=payload,
    headers={'Content-Type': 'application/json'},
    method='POST'
)

print('Getting FLUX output for re-crop...')
t0 = time.time()
resp = urllib.request.urlopen(req, timeout=180)
result = json.loads(resp.read())

if not result.get('ok'):
    print(f'Error: {result.get("error")}')
    sys.exit(1)

# Get the FLUX output (before final crop)
# We need to modify the pipeline to save intermediate...
# For now, let's just re-crop the v6 result

# Actually, the simplest approach: take v6 result, resize back to FLUX output size, re-crop
# But that loses quality. Better to fix the pipeline.

# Let me just show the user what we have and explain
dl_url = result.get('download_passport', '')
dl_resp = urllib.request.urlopen(f'http://localhost:8122{dl_url}')
dl_bytes = dl_resp.read()
with open('test_result_v7_raw.jpg', 'wb') as f:
    f.write(dl_bytes)

# Check headspace
img2 = cv2.imread('test_result_v7_raw.jpg')
h2, w2 = img2.shape[:2]
gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
faces2 = cascade.detectMultiScale(gray2, 1.1, 5, minSize=(30, 30))
if len(faces2) > 0:
    (x, y, fw, fh) = faces2[0]
    headspace_pct = y / h2 * 100
    print(f'v7 headspace: {headspace_pct:.1f}% (y={y}px of {h2}px)')

print(f'Done in {round(time.time() - t0, 1)}s')
