#!/usr/bin/env python3
"""Download REAL product images from Bing Image Search.
Run: cd /home/openhands/erp-stack && python3 download_product_images.py
"""
import sqlite3, json, os, requests, time, re
from pathlib import Path
from urllib.parse import quote

DB = Path(__file__).parent / 'tiktok-ugc-studio' / 'tus_products.db'
IMG_DIR = Path(__file__).parent / 'tiktok-ugc-studio' / 'storage' / 'product_images'
IMG_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7',
}


def has_real_image(pid: str) -> bool:
    """Check if product already has a real (non-generated) image."""
    path = IMG_DIR / f'{pid}.jpg'
    if not path.exists():
        return False
    # Real product images are usually < 500KB
    # Generated images are usually > 500KB
    size = path.stat().st_size
    if size > 500000:  # More than 500KB = probably generated
        return False
    return True


def search_bing_images(query: str) -> list:
    """Search Bing Images for product images."""
    url = f'https://www.bing.com/images/search?q={quote(query)}&form=HDRSC2&first=1'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        # Extract image URLs from murl field
        urls = re.findall(r'murl&quot;:&quot;(https?://[^&]+\.(?:jpg|jpeg|png|webp))', resp.text)
        return urls[:10]
    except Exception as e:
        print(f'    Bing search error: {e}')
        return []


def download_image(url: str, save_path: str) -> bool:
    """Download an image from URL."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, stream=True)
        if resp.status_code == 200:
            content_type = resp.headers.get('content-type', '')
            if 'image' in content_type or url.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                with open(save_path, 'wb') as f:
                    for chunk in resp.iter_content(8192):
                        f.write(chunk)
                # Verify it's a valid image
                size = os.path.getsize(save_path)
                if size > 10000:  # At least 10KB
                    return True
                else:
                    os.remove(save_path)
        return False
    except Exception as e:
        print(f'    Download error: {e}')
        return False


def process_product(pid: str, title: str) -> bool:
    """Try to find and download a real image for a product."""
    if has_real_image(pid):
        print(f'  ✅ Already has image')
        return True
    
    save_path = str(IMG_DIR / f'{pid}.jpg')
    
    # Strategy 1: Search with product name
    print(f'  Searching Bing Images...')
    query = f'{title} product photo'
    urls = search_bing_images(query)
    for url in urls:
        if download_image(url, save_path):
            print(f'  ✅ Downloaded from Bing')
            return True
    
    # Strategy 2: Search with generic terms
    if 'lip' in title.lower() or 'ลิป' in title:
        query = 'lipstick product photo white background'
    elif 'serum' in title.lower() or 'เซรั่ม' in title:
        query = 'serum skincare product photo'
    elif 'brush' in title.lower() or 'แปรง' in title:
        query = 'makeup brush product photo'
    elif 'eyelash' in title.lower() or 'ขนตา' in title:
        query = 'eyelash product photo'
    else:
        query = f'{title.split()[0]} product photo'
    
    urls = search_bing_images(query)
    for url in urls:
        if download_image(url, save_path):
            print(f'  ✅ Downloaded from Bing (generic)')
            return True
    
    print(f'  ❌ Could not find image')
    return False


def main():
    """Main function."""
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    
    # Get products that need images
    rows = conn.execute('SELECT product_id, title FROM tus_products').fetchall()
    
    print(f'Checking {len(rows)} products...')
    need_image = []
    for r in rows:
        if not has_real_image(r['product_id']):
            need_image.append(r)
    
    print(f'Products needing images: {len(need_image)}')
    
    success = 0
    failed = 0
    
    for i, r in enumerate(need_image):
        print(f'\n[{i+1}/{len(need_image)}] {r["title"][:50]}...')
        
        if process_product(r['product_id'], r['title']):
            success += 1
        else:
            failed += 1
        
        time.sleep(2)  # Rate limit
    
    conn.close()
    
    print(f'\n{"="*50}')
    print(f'Results: {success} downloaded, {failed} failed')
    print(f'Total products with images: {len(rows) - failed}/{len(rows)}')


if __name__ == '__main__':
    main()
