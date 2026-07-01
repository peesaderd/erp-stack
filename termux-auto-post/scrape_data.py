"""
scrape_data.py — ดึงข้อมูลสินค้าจาก Platform โดยตรง
ใช้บน Termux ผ่าน requests + cookies

Sources:
  - TikTok Shop (affiliate product feed)
  - Shopee (product feed)
  - Google Sheets (optional)

Output:
  - list[dict] — ข้อมูลสินค้าพร้อมรูป + description
"""

import json
import time
import random
import requests
from datetime import datetime
from pathlib import Path

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# ─── TikTok Shop Scrape ───────────────────────────────────

def scrape_tiktok_shop(session_cookies=None, limit=10):
    """
    ดึงสินค้าจาก TikTok Shop Feed
    ใช้ cookie session ของ TikTok
    """
    print("🔍 Scraping TikTok Shop products...")

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.tiktok.com",
        "Referer": "https://www.tiktok.com/",
    }

    if session_cookies:
        cookie_str = "; ".join([f"{k}={v}" for k, v in session_cookies.items()])
        headers["Cookie"] = cookie_str

    products = []

    # Fallback: ใช้ mock data สำหรับ development
    # ใน production จะเรียก TikTok API endpoint จริง
    products = _mock_scrape("tiktok_shop", limit)

    print(f"✅ TikTok Shop: ได้ {len(products)} สินค้า")
    return products


# ─── Shopee Scrape ────────────────────────────────────────

def scrape_shopee(limit=10):
    """
    ดึงสินค้าจาก Shopee
    """
    print("🔍 Scraping Shopee products...")

    products = _mock_scrape("shopee", limit)

    print(f"✅ Shopee: ได้ {len(products)} สินค้า")
    return products


# ─── Google Sheets (optional) ─────────────────────────────

def scrape_google_sheets(sheet_id=None):
    """
    ดึง content calendar จาก Google Sheets
    """
    print("🔍 Scraping Google Sheets...")
    return []


# ─── Mock / Dev Data ──────────────────────────────────────

def _mock_scrape(source, limit=5):
    """
    ใช้ตอนพัฒนา — ตอนใช้งานจริงให้เปลี่ยนเป็น scrape จริง
    """
    mock_products = {
        "tiktok_shop": [
            {
                "source": "tiktok_shop",
                "product_name": "เซรั่มบำรุงผิวหน้า Vitamin C",
                "price": 299,
                "currency": "THB",
                "description": "เซรั่มวิตามินซีเข้มข้น ลดจุดด่างดำ กระจ่างใสใน 7 วัน",
                "images": ["https://via.placeholder.com/400"],
                "affiliate_link": "https://vt.toktok.com/xxxxx",
                "category": "skincare",
                "rating": 4.5,
                "sold_count": 15200,
            },
            {
                "source": "tiktok_shop",
                "product_name": "ลิปสติกเนื้อแมทติดทน 12HR",
                "price": 199,
                "currency": "THB",
                "description": "ลิปเนื้อแมท สีชัด ปากไม่แห้ง ติดทนทั้งวัน",
                "images": ["https://via.placeholder.com/400"],
                "affiliate_link": "https://vt.toktok.com/xxxxx",
                "category": "beauty",
                "rating": 4.3,
                "sold_count": 8900,
            },
            {
                "source": "tiktok_shop",
                "product_name": "ที่ชาร์จไร้สาย Fast Charge 15W",
                "price": 459,
                "currency": "THB",
                "description": "ที่ชาร์จไร้สาย รองรับ Fast Charge 15W ใช้กับ iOS/Android ได้",
                "images": ["https://via.placeholder.com/400"],
                "affiliate_link": "https://vt.toktok.com/xxxxx",
                "category": "gadget",
                "rating": 4.7,
                "sold_count": 32100,
            },
        ],
        "shopee": [
            {
                "source": "shopee",
                "product_name": "กระบอกน้ำ Stainless สุดเท่ 750ml",
                "price": 350,
                "currency": "THB",
                "description": "กระบอกน้ำสแตนเลส เก็บร้อน 24hr เก็บเย็น 48hr",
                "images": ["https://via.placeholder.com/400"],
                "affiliate_link": "https://shopee.co.th/xxxxx",
                "category": "lifestyle",
                "rating": 4.8,
                "sold_count": 55000,
            },
            {
                "source": "shopee",
                "product_name": "หูฟัง Bluetooth 5.3 กันน้ำ IPX7",
                "price": 790,
                "currency": "THB",
                "description": "หูฟังไร้สาย Bluetooth 5.3 เสียงคมชัด กันน้ำ ใส่ลุยฝนได้",
                "images": ["https://via.placeholder.com/400"],
                "affiliate_link": "https://shopee.co.th/xxxxx",
                "category": "gadget",
                "rating": 4.6,
                "sold_count": 28700,
            },
        ],
    }

    return mock_products.get(source, [])[:limit]


# ─── Content Filter ───────────────────────────────────────

def filter_products(products, min_rating=4.0, max_price=None, category=None):
    """กรองสินค้าตามเงื่อนไข"""
    filtered = products[:]

    if min_rating:
        filtered = [p for p in filtered if p.get("rating", 0) >= min_rating]
    if max_price:
        filtered = [p for p in filtered if p.get("price", 999999) <= max_price]
    if category:
        filtered = [p for p in filtered if p.get("category") == category]

    return filtered


def get_random_product(products):
    """สุ่มสินค้าหนึ่งชิ้น"""
    return random.choice(products) if products else None


# ─── Main ─────────────────────────────────────────────────

def main():
    """ทดสอบ scrape"""
    print("🧪 Scrape Data Test\n")

    tiktok_items = scrape_tiktok_shop(limit=3)
    shopee_items = scrape_shopee(limit=3)

    all_items = tiktok_items + shopee_items

    print(f"\n{'='*50}")
    print(f"รวมทั้งสิ้น: {len(all_items)} สินค้า")
    print(f"{'='*50}")

    for i, item in enumerate(all_items, 1):
        print(f"\n{i}. [{item['source']}] {item['product_name']}")
        print(f"   💰 {item['price']} {item['currency']}")
        print(f"   ⭐ {item.get('rating', 'N/A')}")
        print(f"   🔗 {item.get('affiliate_link', 'N/A')}")

    # บันทึกลง cache
    cache_path = CACHE_DIR / f"products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    cache_path.write_text(json.dumps(all_items, indent=2, ensure_ascii=False))
    print(f"\n💾 บันทึก cache: {cache_path}")


if __name__ == "__main__":
    main()
