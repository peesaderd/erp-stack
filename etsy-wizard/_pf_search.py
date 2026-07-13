"""Search Printful products for wall art / canvas / photo frame"""
import json, os, sys
from urllib.request import Request, urlopen

api_key = os.environ.get('PRINTFUL_API_KEY', '')
if not api_key:
    # Read from .env
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    for line in open(env_path).readlines():
        line = line.strip()
        if line.startswith('PRINTFUL_API_KEY='):
            api_key = line.split('=', 1)[1]

if not api_key:
    print("No PRINTFUL_API_KEY found")
    sys.exit(1)

req = Request('https://api.printful.com/products')
req.add_header('Authorization', f'Bearer {api_key}')
req.add_header('User-Agent', 'EtsyWizard/1.0')

resp = urlopen(req, timeout=15)
data = json.loads(resp.read().decode())
result = data.get('result', [])

print(f"Total products: {len(result)}\n")

keywords = ['canvas', 'wall', 'frame', 'photo', 'poster', 'print', 'panel']
for r in result:
    p = r.get('product', {})
    title = (p.get('title') or '') + ' ' + (p.get('type') or '')
    title_lower = title.lower()
    if any(k in title_lower for k in keywords):
        pf_id = p.get('id') or 0
        t = (p.get('title') or '?')
        brand = p.get('brand') or ''
        print(f'  ID={pf_id:>3d} | {t:<55s} | brand={brand}')
