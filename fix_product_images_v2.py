#!/usr/bin/env python3
"""
Fix product images v2:
1. Download real images from TikTok Shop for ALL products
2. Convert WebP to proper JPG
3. Verify no duplicate images
4. Update DB to use local paths
"""
import sqlite3
import httpx
import json
import os
import re
import hashlib
import time
from pathlib import Path
from PIL import Image
import io

DB_PATH = Path("/home/openhands/erp-stack/tiktok-ugc-studio/tus_products.db")
IMG_DIR = Path("/home/openhands/erp-stack/tiktok-ugc-studio/storage/product_images")
IMG_DIR.mkdir(parents=True, exist_ok=True)

def get_tiktok_shop_image_url(product_id: str) -> list[str]:
    """Try to get product images from TikTok Shop API"""
    # Method 1: Try the CDN pattern from scraper
    urls = []
    
    # Try direct TikTok product page to extract images
    try:
        client = httpx.Client(
            follow_redirects=True,
            timeout=15.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept-Language": "th-TH,th;q=0.9,en;q=0.8",
            }
        )
        
        # Try TikTok Shop product URL
        resp = client.get(f"https://www.tiktok.com/@product/{product_id}")
        if resp.status_code == 200:
            # Extract og:image from HTML
            og_match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', resp.text)
            if og_match:
                img_url = og_match.group(1)
                urls.append(img_url)
        
        client.close()
    except Exception as e:
        print(f"  TikTok page error: {e}")
    
    return urls

def download_and_convert(url: str, output_path: Path) -> bool:
    """Download image and convert to proper JPG"""
    try:
        client = httpx.Client(
            follow_redirects=True,
            timeout=20.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                "Referer": "https://www.tiktok.com/",
            }
        )
        
        resp = client.get(url)
        if resp.status_code != 200:
            print(f"    HTTP {resp.status_code}")
            client.close()
            return False
        
        content_type = resp.headers.get("content-type", "")
        content = resp.content
        
        # Convert to proper JPG using PIL
        try:
            img = Image.open(io.BytesIO(content))
            if img.mode in ('RGBA', 'P', 'LA'):
                img = img.convert('RGB')
            
            # Save as proper JPEG
            img.save(str(output_path), 'JPEG', quality=90, optimize=True)
            
            # Verify file
            file_size = output_path.stat().st_size
            if file_size < 1000:
                print(f"    File too small ({file_size} bytes)")
                return False
            
            print(f"    OK: {file_size:,} bytes, {img.size[0]}x{img.size[1]}")
            client.close()
            return True
        except Exception as e:
            print(f"    PIL error: {e}")
            client.close()
            return False
            
    except Exception as e:
        print(f"    Download error: {e}")
        return False

def main():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Get all products
    cur.execute("SELECT product_id, title, images FROM tus_products ORDER BY product_id")
    products = cur.fetchall()
    
    print(f"Total products: {len(products)}")
    
    # Track which images we've seen (by content hash)
    seen_hashes = {}
    
    downloaded = 0
    skipped = 0
    failed = 0
    
    for p in products:
        pid = p["product_id"]
        title = p["title"][:50]
        images_json = p["images"]
        
        try:
            images = json.loads(images_json) if images_json else []
        except:
            images = []
        
        img_path = IMG_DIR / f"{pid}.jpg"
        
        # Check if file exists and is a real JPEG (not WebP saved as .jpg)
        if img_path.exists():
            with open(img_path, 'rb') as f:
                header = f.read(3)
            if header == b'\xff\xd8\xff':  # Real JPEG
                # Check for duplicates
                content_hash = hashlib.md5(img_path.read_bytes()).hexdigest()
                if content_hash in seen_hashes:
                    print(f"DUPLICATE: {pid} ({title}) is same as {seen_hashes[content_hash]}")
                    # Need to re-download
                else:
                    seen_hashes[content_hash] = pid
                    skipped += 1
                    continue
            else:
                print(f"BAD FORMAT: {pid} ({title}) - not a real JPEG ({header[:4]})")
        
        # Try to download
        print(f"\nDownloading: {pid} - {title}")
        
        # First try the CDN URL from DB (if it's a CDN URL)
        if images and 'cdn-image.hdnet.workers.dev' in images[0]:
            success = download_and_convert(images[0], img_path)
            if success:
                content_hash = hashlib.md5(img_path.read_bytes()).hexdigest()
                seen_hashes[content_hash] = pid
                downloaded += 1
                time.sleep(1)
                continue
        
        # Try TikTok page
        tiktok_urls = get_tiktok_shop_image_url(pid)
        if tiktok_urls:
            success = download_and_convert(tiktok_urls[0], img_path)
            if success:
                content_hash = hashlib.md5(img_path.read_bytes()).hexdigest()
                seen_hashes[content_hash] = pid
                downloaded += 1
                time.sleep(1)
                continue
        
        print(f"  FAILED: Could not download image")
        failed += 1
        time.sleep(0.5)
    
    # Now update DB: all products should use local paths
    print("\n--- Updating DB ---")
    cur.execute("SELECT product_id FROM tus_products")
    all_pids = [r[0] for r in cur.fetchall()]
    
    for pid in all_pids:
        img_path = IMG_DIR / f"{pid}.jpg"
        if img_path.exists() and img_path.stat().st_size > 1000:
            new_images = json.dumps([f"/ugc/static/product_images/{pid}.jpg"])
            cur.execute("UPDATE tus_products SET images = ? WHERE product_id = ?", (new_images, pid))
    
    conn.commit()
    conn.close()
    
    print(f"\n=== SUMMARY ===")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped (good): {skipped}")
    print(f"Failed: {failed}")
    print(f"Total: {len(products)}")

if __name__ == "__main__":
    main()
