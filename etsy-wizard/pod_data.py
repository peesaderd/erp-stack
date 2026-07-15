"""
POD (Print on Demand) Data Provider
====================================
แหล่งข้อมูลสินค้า POD — รองรับทั้ง static reference + Printful API (cache)
"""

import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.request import urlopen, Request
from urllib.error import HTTPError

from pod_sizes import POD_PRODUCTS as ARTWORK_SPECS

logger = logging.getLogger("pod-data")

# ─── Cache ─────────────────────────────────────────────────────────────────
CACHE_DIR = Path(__file__).parent / ".pod_cache"
CACHE_TTL = timedelta(hours=12)  # refresh every 12h

PRINTFUL_API = "https://api.printful.com"

# ─── Static Provider Reference ──────────────────────────────────────────────
# Printful product IDs for our core products (known IDs from API)
# These are the standard Printful catalog items
PRINTFUL_PRODUCT_IDS = {
    "tshirt_standard": 71,        # Bella+Canvas 3001 Unisex Jersey Tee
    "hoodie_standard": None,      # TODO: find ID
    "tank_top": None,             # TODO: find ID
    "leggings": None,             # TODO: find ID (all-over print = 189)
    "mug_11oz": None,             # TODO: find ID
    "mug_15oz": None,             # TODO: find ID
    "water_bottle": None,         # TODO: find ID
    "canvas_print": 3,            # Canvas (in) — แคนวาส 8x10
    "framed_canvas": 614,         # Framed Canvas (in)
    "poster_18x24": 1,            # Enhanced Matte Paper Poster (in)
    "framed_poster": 2,           # Enhanced Matte Paper Framed Poster (in)
    "metal_print": 588,           # Glossy Metal Print (in)
    "wall_tapestry": 973,         # Indoor Wall Tapestry
    "pillow_square": 83,          # All-Over Print Basic Pillow
    "tote_bag": 84,               # All-Over Tote
    "phone_case_iphone": None,    # TODO: find ID
    "notebook": None,             # TODO: find ID
}

# Providers
PROVIDERS = [
    {
        "id": "printful",
        "name": "Printful",
        "description": "POD fulfillment ทั่วโลก มีทั้ง DTG, Sublimation, Embroidery",
        "website": "https://www.printful.com",
        "has_api": True,
        "shipping_regions": ["US", "EU", "UK", "CA"],
        "avg_delivery_days": "3-7",
    },
    {
        "id": "printify",
        "name": "Printify",
        "description": "Marketplace POD มี provider หลายเจ้าให้เลือก",
        "website": "https://printify.com",
        "has_api": False,
        "shipping_regions": ["US", "EU", "UK", "CA", "AU"],
        "avg_delivery_days": "5-10",
    },
    {
        "id": "gelato",
        "name": "Gelato",
        "description": "POD แบบ distributed print — พิมพ์ใกล้ลูกค้า",
        "website": "https://www.gelato.com",
        "has_api": False,
        "shipping_regions": ["US", "EU", "UK", "CA", "AU", "JP"],
        "avg_delivery_days": "2-5",
    },
]


# ─── Printful API Client ────────────────────────────────────────────────────

class PrintfulAPI:
    """Lightweight Printful API wrapper with caching"""
    
    def __init__(self):
        self._cache = {}
        self._ensure_cache_dir()
    
    def _ensure_cache_dir(self):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    def _cache_path(self, key: str) -> Path:
        return CACHE_DIR / f"{key}.json"
    
    def _load_cache(self, key: str) -> Optional[dict]:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
            if datetime.now() - cached_at > CACHE_TTL:
                return None  # expired
            return data.get("data")
        except (json.JSONDecodeError, KeyError, ValueError):
            return None
    
    def _save_cache(self, key: str, data: dict):
        path = self._cache_path(key)
        payload = {
            "_cached_at": datetime.now().isoformat(),
            "data": data,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False))
    
    def _load_printful_key(self) -> str:
        """Load Printful API key from env or .env file"""
        key = os.environ.get('PRINTFUL_API_KEY', '')
        if key:
            return key
        # Try reading from our .env file
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            for line in env_path.read_text().split('\n'):
                line = line.strip()
                if line.startswith('PRINTFUL_API_KEY='):
                    key = line.split('=', 1)[1]
                    os.environ['PRINTFUL_API_KEY'] = key
                    return key
        return ''
    
    def fetch_product(self, pf_id: int) -> Optional[dict]:
        """Fetch product detail + variants from Printful API"""
        cache_key = f"product_{pf_id}"
        cached = self._load_cache(cache_key)
        if cached:
            logger.info(f"  [PF API] Cache hit: product {pf_id}")
            return cached
        
        api_key = self._load_printful_key()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "EtsyWizard/1.0",
        }
        
        try:
            req = Request(f"{PRINTFUL_API}/products/{pf_id}", headers=headers)
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            
            if data.get("code") != 200:
                logger.warning(f"  [PF API] Error {data.get('code')} for product {pf_id}")
                return None
            
            result = data.get("result", {})
            self._save_cache(cache_key, result)
            logger.info(f"  [PF API] Fetched product {pf_id}: {result.get('product',{}).get('title','?')}")
            return result
        except Exception as e:
            logger.warning(f"  [PF API] Failed to fetch product {pf_id}: {e}")
            return None


# Singleton
_pf_api = None
def get_printful_api() -> PrintfulAPI:
    global _pf_api
    if _pf_api is None:
        _pf_api = PrintfulAPI()
    return _pf_api


# ─── POD Data Provider ──────────────────────────────────────────────────────

def get_providers() -> list:
    """รายการ POD providers ที่รองรับ"""
    return PROVIDERS


def get_product_catalog(provider_id: str = "printful", category: str = None) -> list:
    """
    รายการสินค้า POD ทั้งหมด (รวม artwork spec + ข้อมูลจาก API ถ้ามี)
    
    Returns list of dicts with merged data:
      - product_id, name, category
      - artwork_spec (from pod_sizes.py)
      - pf_product_id (Printful API ID ถ้ามี)
      - variants (จาก API ถ้ามี)
      - pricing (จาก API ถ้ามี)
    """
    products = []
    
    for spec in ARTWORK_SPECS:
        pid = spec["id"]
        pf_id = PRINTFUL_PRODUCT_IDS.get(pid)
        
        product = {
            "product_id": pid,
            "name": spec["name"],
            "category": spec["category"],
            "artwork_spec": {
                "print_area": spec["print_area"],
                "width_inch": spec["width_inch"],
                "height_inch": spec["height_inch"],
                "width_px": spec["width_px_300"],
                "height_px": spec["height_px_300"],
                "dpi_min": spec["dpi_min"],
                "dpi_recommended": spec["dpi_recommended"],
                "aspect_ratio": spec["aspect_ratio"],
                "orientation": spec["orientation"],
                "file_type": spec["file_type"],
                "max_file_size_mb": spec["max_file_size_mb"],
                "notes": spec["notes"],
                "print_technique": spec["print_technique"],
            },
            "providers": spec["providers"],
            "pf_product_id": pf_id,
            "pf_data_available": pf_id is not None,
        }
        
        # Try to get Printful data (cached)
        if pf_id:
            api = get_printful_api()
            pf_data = api.fetch_product(pf_id)
            if pf_data:
                pf_product = pf_data.get("product", {})
                variants = pf_data.get("variants", [])
                
                product["pf_title"] = pf_product.get("title")
                product["pf_brand"] = pf_product.get("brand")
                product["pf_model"] = pf_product.get("model")
                product["pf_image"] = pf_product.get("image")
                product["pf_techniques"] = pf_product.get("techniques", [])
                product["pf_files"] = pf_product.get("files", [])
                product["pf_options"] = pf_product.get("options", [])
                
                # Extract unique colors and sizes from variants
                colors = {}
                sizes = set()
                pricing = {"min": None, "max": None, "variants_count": len(variants)}
                
                for v in variants:
                    color = v.get("color")
                    size = v.get("size")
                    price = float(v.get("price", 0))
                    
                    if color:
                        code = v.get("color_code")
                        if color not in colors:
                            colors[color] = {"name": color, "code": code, "image": v.get("image")}
                    if size:
                        sizes.add(size)
                    if pricing["min"] is None or price < pricing["min"]:
                        pricing["min"] = price
                    if pricing["max"] is None or price > pricing["max"]:
                        pricing["max"] = price
                
                product["pf_colors"] = list(colors.values())
                product["pf_sizes"] = sorted(sizes, key=lambda s: ["XS","S","M","L","XL","2XL","3XL","4XL","5XL"].index(s) if s in ["XS","S","M","L","XL","2XL","3XL","4XL","5XL"] else 99)
                product["pf_pricing"] = pricing
        
        # Category filter
        if category and product["category"] != category:
            continue
        
        products.append(product)
    
    return products


def get_product_detail(product_id: str, provider_id: str = "printful") -> Optional[dict]:
    """รายละเอียดสินค้าแบบเต็ม"""
    catalog = get_product_catalog(provider_id)
    for p in catalog:
        if p["product_id"] == product_id:
            return p
    return None


def get_categories() -> list:
    """รายการหมวดหมู่ POD"""
    cats = set()
    for spec in ARTWORK_SPECS:
        cats.add(spec["category"])
    return sorted(cats)


# ─── Shipping Cost Estimates (Static) ────────────────────────────────────────
# Based on Printful public pricing (approximate)
SHIPPING_ESTIMATES = {
    "tshirt_standard": {"US": 3.99, "EU": 4.99, "UK": 4.99, "CA": 5.99},
    "hoodie_standard": {"US": 4.99, "EU": 5.99, "UK": 5.99, "CA": 6.99},
    "tank_top":       {"US": 3.99, "EU": 4.99, "UK": 4.99, "CA": 5.99},
    "leggings":       {"US": 5.99, "EU": 6.99, "UK": 6.99, "CA": 7.99},
    "mug_11oz":       {"US": 4.99, "EU": 5.99, "UK": 5.99, "CA": 6.99},
    "mug_15oz":       {"US": 5.49, "EU": 6.49, "UK": 6.49, "CA": 7.49},
    "poster_18x24":   {"US": 3.99, "EU": 4.99, "UK": 4.99, "CA": 5.99},
    "canvas_print":   {"US": 5.99, "EU": 6.99, "UK": 6.99, "CA": 7.99},
    "tote_bag":       {"US": 3.99, "EU": 4.99, "UK": 4.99, "CA": 5.99},
}


def get_shipping_estimate(product_id: str, region: str = "US") -> Optional[float]:
    """ค่าส่งประมาณการ — ใช้ Printful public rates"""
    estimates = SHIPPING_ESTIMATES.get(product_id)
    if estimates:
        return estimates.get(region)
    return None


def get_profit_calculation(product_id: str, selling_price: float, region: str = "US") -> dict:
    """
    คำนวณกำไรเบื้องต้น
    """
    product = get_product_detail(product_id)
    if not product:
        return {"error": f"ไม่พบสินค้า: {product_id}"}
    
    pricing = product.get("pf_pricing", {})
    base_cost = pricing.get("min") if pricing else None
    
    if not base_cost:
        # Fallback estimates
        cost_estimates = {
            "tshirt_standard": 11.95,
            "hoodie_standard": 24.95,
            "tank_top": 9.95,
            "leggings": 19.95,
            "mug_11oz": 8.95,
            "mug_15oz": 10.95,
            "poster_18x24": 14.95,
            "canvas_print": 19.95,
            "pillow_square": 16.95,
            "tote_bag": 12.95,
            "phone_case_iphone": 11.95,
            "notebook": 12.95,
            "water_bottle": 14.95,
        }
        base_cost = cost_estimates.get(product_id, 10.00)
    
    shipping = get_shipping_estimate(product_id, region) or 4.99
    
    platform_fee = selling_price * 0.065  # Etsy ≈ 6.5%
    transaction_fee = (selling_price * 0.03) + 0.30  # Payment processing ≈ 3% + $0.30
    
    total_cost = base_cost + shipping + platform_fee + transaction_fee
    profit = selling_price - total_cost
    margin_pct = (profit / selling_price) * 100 if selling_price > 0 else 0
    
    return {
        "product_id": product_id,
        "product_name": product.get("name"),
        "selling_price": round(selling_price, 2),
        "base_cost": round(base_cost, 2),
        "shipping": round(shipping, 2),
        "platform_fee": round(platform_fee, 2),
        "transaction_fee": round(transaction_fee, 2),
        "total_cost": round(total_cost, 2),
        "profit": round(profit, 2),
        "margin_percent": round(margin_pct, 1),
        "break_even_price": round(total_cost, 2),
        "region": region,
        "note": "ค่าส่งเป็นประมาณการ ขึ้นอยู่กับ provider และ destination จริง",
    }


# ─── Printful Mockup Generator API ──────────────────────────────────────────

def get_printful_printfiles(product_id: int) -> Optional[dict]:
    """
    ดึง print file specs จาก Printful Mockup Generator API
    
    GET /mockup-generator/printfiles/{product_id}
    
    คืนค่าข้อมูล placement (front/back/sleeve), printfile dimensions, variant mapping
    """
    api = get_printful_api()
    api_key = api._load_printful_key()
    if not api_key:
        logger.warning("Printful API key not configured")
        return None
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "EtsyWizard/1.0",
    }
    
    try:
        req = Request(f"{PRINTFUL_API}/mockup-generator/printfiles/{product_id}", headers=headers)
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if data.get("code") != 200:
            logger.warning(f"Printful printfiles error: {data.get('code')}")
            return None
        return data.get("result")
    except Exception as e:
        logger.warning(f"Failed to fetch printfiles for product {product_id}: {e}")
        return None


def get_printful_mockup_templates(product_id: int) -> Optional[dict]:
    """
    ดึง mockup templates สำหรับ product
    
    GET /mockup-generator/templates?id={product_id}
    
    คืนค่า variant_mapping + templates (print_area coords, image_url, background_url)
    """
    api = get_printful_api()
    api_key = api._load_printful_key()
    if not api_key:
        logger.warning("Printful API key not configured")
        return None
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "EtsyWizard/1.0",
    }
    
    try:
        req = Request(f"{PRINTFUL_API}/mockup-generator/templates?id={product_id}", headers=headers)
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        if data.get("code") != 200:
            logger.warning(f"Printful templates error: {data.get('code')}")
            return None
        return data.get("result")
    except Exception as e:
        logger.warning(f"Failed to fetch templates for product {product_id}: {e}")
        return None


def create_printful_mockup(
    product_id: int,
    variant_ids: list,
    files: list,
    format: str = "png",
) -> Optional[dict]:
    """
    สร้าง mockup task ผ่าน Printful Mockup Generator API
    
    POST /mockup-generator/create-task/{product_id}
    
    files = [
        {
            "placement": "front",          # placement จาก printfiles
            "image_url": "https://...",    # URL ของ artwork ที่ gen แล้ว
            "position": {
                "area_width": 3000,        # printfile width
                "area_height": 3000,       # printfile height
                "width": 1800,             # artwork display width
                "height": 2400,            # artwork display height
                "top": 0,                  # offset from top
                "left": 0                  # offset from left
            },
            "printfile_id": 1,             # printfile_id จาก printfiles
        }
    ]
    """
    api = get_printful_api()
    api_key = api._load_printful_key()
    if not api_key:
        logger.warning("Printful API key not configured")
        return None
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "EtsyWizard/1.0",
    }
    
    payload = {
        "variant_ids": variant_ids,
        "format": format,
        "files": files,
    }
    
    try:
        import http.client
        body = json.dumps(payload).encode()
        logger.info(f"Printful mockup payload: {json.dumps(payload)[:500]}")
        req = Request(
            f"{PRINTFUL_API}/mockup-generator/create-task/{product_id}",
            data=body,
            headers=headers,
        )
        with urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        if data.get("code") not in (200, 201):
            logger.warning(f"Printful create-task error ({data.get('code')}): {json.dumps(data.get('result',{}))[:500]}")
            return None
        return data.get("result")
    except Exception as e:
        logger.warning(f"Failed to create mockup for product {product_id}: {e}")
        # Try to read response body for more detail
        if hasattr(e, 'read'):
            try:
                err_body = e.read().decode() if callable(e.read) else e.read()
                logger.warning(f"Printful error body: {err_body[:500]}")
            except:
                pass
        return None


def check_mockup_task(task_key: str) -> Optional[dict]:
    """
    ตรวจสอบสถานะ mockup task
    
    GET /mockup-generator/task?task_key={task_key}
    
    Returns {
        "status": "completed" | "failed" | "pending",
        "mockups": [{ "placement": "front", "variant_ids": [9575], "mockup_url": "...", "extra": [...] }],
        ...
    }
    """
    api = get_printful_api()
    api_key = api._load_printful_key()
    if not api_key:
        logger.warning("Printful API key not configured")
        return None
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "EtsyWizard/1.0",
    }
    
    try:
        req = Request(f"{PRINTFUL_API}/mockup-generator/task?task_key={task_key}", headers=headers)
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        if data.get("code") != 200:
            logger.warning(f"Printful task status error: {data.get('code')}")
            return None
        return data.get("result")
    except Exception as e:
        logger.warning(f"Failed to check mockup task {task_key}: {e}")
        return None


if __name__ == "__main__":
    # Test
    logging.basicConfig(level=logging.INFO)
    
    print("=== Product Catalog ===")
    cats = get_categories()
    print(f"Categories: {cats}")
    
    products = get_product_catalog()
    for p in products:
        pf_status = "✅" if p.get("pf_data_available") else "❌"
        pf_price = p.get("pf_pricing", {})
        price_str = f"${pf_price.get('min','?')}-${pf_price.get('max','?')}" if pf_price.get('min') else "N/A"
        print(f"  {pf_status} {p['product_id']:25s} {p['name'][:35]:35s} {price_str}")
    
    print("\n=== Profit Calculation (T-Shirt, sell $29.99) ===")
    calc = get_profit_calculation("tshirt_standard", 29.99)
    for k, v in calc.items():
        print(f"  {k}: {v}")
