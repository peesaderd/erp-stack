"""Ultra-stealth product scraper with multi-layer extraction.
Supports: Shopee, Lazada, Boots, Watsons, Central, and all generic e-commerce.
Fallback chain: HTTP → Playwright Stealth → JSON-LD → Vision AI
"""
import asyncio, re, json, logging, os, random
from typing import Optional, Dict, List, Any
from urllib.parse import urlparse
from datetime import datetime

logger = logging.getLogger("product_scraper")

# ─── Proxy Config ──────────────────────────────────────────────────────────
# Read from env: PROXY_LIST=http://user:pass@ip:port,http://user2:pass2@ip2:port
# Each call rotates to the next proxy automatically.
_proxy_list = os.environ.get("PROXY_LIST", "").strip()
PROXY_LIST = [p.strip() for p in _proxy_list.split(",") if p.strip()]
_proxy_index = 0
_proxy_lock = asyncio.Lock()

async def _get_next_proxy() -> Optional[str]:
    """Round-robin proxy selection."""
    global _proxy_index
    if not PROXY_LIST:
        return None
    async with _proxy_lock:
        idx = _proxy_index % len(PROXY_LIST)
        _proxy_index += 1
        return PROXY_LIST[idx]

# ─── Config ────────────────────────────────────────────────────────────────

SITE_PATTERNS = {
    "tiktok":  ["tiktok.com/shop", "tiktok.com/@"],
    "shopee":  ["shopee.co.th", "shopee.com.my", "shopee.sg", "shopee.com"],
    "lazada":  ["lazada.co.th", "lazada.com"],
    "boots":   ["boots.co.th", "boots.com", "store.boots.co.th"],
    "watsons": ["watsons.co.th", "watsons.com"],
    "central": ["central.co.th"],
    "amazon":  ["amazon.com", "amazon.co.th"],
    "advice":  ["advice.co.th"],
    "jib":     ["jib.co.th"],
    "powerbuy":["powerbuy.co.th"],
    "tiktok": {
        "name":    ['h1[data-e2e="product-title"]', '.product-title'],
        "price":   ['span[data-e2e="product-price"]', '.product-price'],
        "images":  ['.product-image-list img', '[data-e2e="product-image"] img'],
    },
    "tiktokshop":["tiktok.com"],
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

VIEWPORTS = [
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1920, "height": 1080},
    {"width": 1536, "height": 864},
    {"width": 1280, "height": 720},
]

STEALTH_SCRIPT = """
// Override navigator.webdriver
Object.defineProperty(navigator, 'webdriver', { get: () => false });

// Chrome runtime
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: { isInstalled: false, InstallState: {}, RunningState: {} },
};

// Permissions
const origQuery = navigator.permissions.query;
navigator.permissions.query = (params) => (
    params.name === 'notifications' ? Promise.resolve({ state: 'denied' }) : origQuery(params)
);

// Plugins array (length > 0 = real browser)
Object.defineProperty(navigator, 'plugins', {
    get: () => [
        { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
        { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
        { name: 'Native Client', filename: 'internal-nacl-plugin' },
    ],
});

// Languages
Object.defineProperty(navigator, 'languages', { get: () => ['th-TH', 'th', 'en-US', 'en'] });
Object.defineProperty(navigator, 'language', { get: () => 'th-TH' });

// Hardware concurrency (real CPUs)
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });

// Device memory
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

// WebGL vendor/renderer spoof
const getParameterProxyHandler = {
    apply: function(target, thisArg, args) {
        const param = args[0];
        if (param === 37445) return 'Google Inc.';      // UNMASKED_VENDOR_WEBGL
        if (param === 37446) return 'ANGLE (Intel, Intel(R) UHD Graphics (0x0000A7A0) Direct3D11 vs_5_0 ps_5_0)';
        return Reflect.apply(target, thisArg, args);
    }
};
try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl');
    if (gl) {
        const origGetParameter = gl.getParameter.bind(gl);
        gl.getParameter = new Proxy(origGetParameter, getParameterProxyHandler);
    }
} catch(e) {}

// Hide Playwright/Puppeteer traces
if (document.querySelector('[__playwright_target__]')) {
    document.querySelectorAll('[__playwright_target__]').forEach(el => el.removeAttribute('__playwright_target__'));
}
"""


# ═══════════════════════════════════════════════════════════════════════════
# HTTP Extraction (Layer 1) — fastest, works for simple SSR sites
# ═══════════════════════════════════════════════════════════════════════════

async def _try_http_extract(url: str, proxy_url: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Extract product data via HTTP + regex (no browser)."""
    import httpx
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, proxy=proxy_url) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code >= 400:
                return None
            html = resp.text

        data = {"name": None, "price": None, "images": [], "description": None, "sku": None}

        # OG tags
        og = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html, re.I)
        if og: data["name"] = og.group(1)
        og_img = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html, re.I)
        if og_img: data["images"] = [og_img.group(1)]
        og_desc = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html, re.I)
        if og_desc: data["description"] = og_desc.group(1)

        # JSON-LD (handles @graph with multiple items)
        for match in re.finditer(r'<script\s+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
            try:
                obj = json.loads(match.group(1))
                items = [obj]
                if isinstance(obj.get("@graph"), list):
                    items.extend(obj["@graph"])
                for item in items:
                    if not isinstance(item, dict) or item.get("@type") not in ("Product", "ItemPage"):
                        continue
                    if item.get("name") and not data["name"]: data["name"] = item["name"]
                    offers = item.get("offers")
                    if offers:
                        if isinstance(offers, dict):
                            p = offers.get("price") or offers.get("lowPrice")
                        elif isinstance(offers, list) and offers:
                            p = offers[0].get("price")
                        else:
                            p = None
                        if p and not data["price"]: data["price"] = _parse_price(str(p))
                    img = item.get("image")
                    if img and not data["images"]:
                        data["images"] = [img] if isinstance(img, str) else (img[:5] if isinstance(img, list) else [])
                    if item.get("sku") and not data["sku"]: data["sku"] = item["sku"]
                    if item.get("description") and not data["description"]: data["description"] = item["description"]
                    brand = item.get("brand")
                    if isinstance(brand, dict) and brand.get("name"):
                        data["brand"] = brand["name"]
                    break
            except json.JSONDecodeError:
                pass

        # Title fallback
        if not data["name"]:
            t = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
            if t: data["name"] = t.group(1).split("|")[0].split("-")[0].strip()

        # Price regex fallback (THB)
        if not data["price"]:
            pr = re.search(r'["\']?price["\']?\s*[:\=]\s*["\']?(\d+(?:[.,]\d+)?)', html, re.I)
            if pr: data["price"] = _parse_price(pr.group(1))

        # Image fallback
        if not data["images"]:
            imgs = re.findall(r'(https?://[^\s"\'<>]+(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>]*)?)', html, re.I)
            large = [i for i in imgs if any(x in i.lower() for x in ["product", "large", "zoom"])]
            data["images"] = (large[:5] if large else imgs[:3])

        return data if (data["name"] or data["price"] is not None) else None

    except Exception as e:
        logger.warning(f"HTTP extraction failed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Playwright Stealth Engine (Layer 2)
# ═══════════════════════════════════════════════════════════════════════════

PRODUCT_SELECTORS = {
    "name": [
        'h1[data-testid="product-name"]', 'h1.product-title', 'h1.product-name',
        '[itemprop="name"]', '.product-name', '.product__title',
        '.pdp-product-name', '.product-header__title',
        '[data-auto="product-title"]', '[data-comp="ProductTitle"]',
        'h1',
    ],
    "price": [
        '[itemprop="price"]', '[data-testid="price"]',
        '.product-price', '.price', '.product__price',
        '.sale-price', '.current-price', '.pdp-price',
        '[data-testid="product-price"]', '.a-price-whole',
        '[data-comp="Price"]',
    ],
    "images": [
        '.product-gallery img', '.product-image img',
        '[data-testid="product-image"] img',
        '.gallery img', '.carousel img', '.pdp-gallery img',
        'img[src*="product"]', 'img[src*="shop"]',
        'meta[property="og:image"]', 'link[rel="preload"][as="image"]',
    ],
    "description": [
        '[itemprop="description"]', '.product-description',
        '.product-details', '#description', '.description',
        '.pdp-description', '.product-info__description',
        'meta[property="og:description"]', 'meta[name="description"]',
    ],
    "sku": [
        '[itemprop="sku"]', '.sku', '.product-sku',
        '[data-testid="sku"]', '.product-code',
    ],
    "brand": [
        '[itemprop="brand"]', '.brand', '.product-brand',
        '[data-testid="brand"]',
    ],
}

# Thai e-commerce specific patterns
SITE_SPECIFIC = {
    "shopee": {
        "name":    ['div[data-sqe="name"]', '.shopee-product-info__header', 'div[data-sqe="name"] span'],
        "price":   ['.shopee-product-info__header__price', '[data-sqe="price"]'],
        "images":  ['.shopee-image-content img', '.shopee-product-image img'],
    },
    "lazada": {
        "name":    ['h1.pdp-product-title', '[data-spm="pdp-product-title"]'],
        "price":   ['.pdp-price', '[data-spm="pdp-price"]'],
        "images":  ['.gallery-preview-panel img', '.pdp-gallery img'],
    },
}


def _detect_site(url: str) -> str:
    domain = urlparse(url).netloc.lower()
    for site, domains in SITE_PATTERNS.items():
        if any(d in domain for d in domains):
            return site
    return "generic"


async def _launch_browser(storage_state: Optional[str] = None, proxy_url: Optional[str] = None):
    """Launch undetectable Chromium via Patchright with optional proxy."""
    from patchright.async_api import async_playwright
    pw = await async_playwright().start()

    ua = random.choice(USER_AGENTS)
    vp = random.choice(VIEWPORTS)

    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-web-security",
            "--disable-features=BlockInsecurePrivateNetworkRequests",
            "--window-size=%d,%d" % (vp["width"], vp["height"]),
        ]
    )
    proxy_cfg = {"server": proxy_url} if proxy_url else None
    ctx = await browser.new_context(
        storage_state=storage_state,
        user_agent=ua,
        viewport=vp,
        proxy=proxy_cfg,
        device_scale_factor=1,
        is_mobile=False,
        has_touch=False,
        locale="th-TH",
        timezone_id="Asia/Bangkok",
        color_scheme="light",
        reduced_motion="no-preference",
        forced_colors="none",
        extra_http_headers={
            "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
            "DNT": "1",
        },
    )
    await ctx.add_init_script(STEALTH_SCRIPT)
    page = await ctx.new_page()
    return pw, browser, ctx, page


async def _random_delay(page, min_ms=200, max_ms=1200):
    """Simulate human-like random delay."""
    await page.wait_for_timeout(random.randint(min_ms, max_ms))


async def _human_scroll(page):
    """Simulate human scroll behavior."""
    await page.evaluate("""async () => {
        const total = document.body.scrollHeight || 1000;
        const steps = 3 + Math.floor(Math.random() * 4);
        for (let i = 1; i <= steps; i++) {
            window.scrollTo({ top: (total / steps) * i, behavior: 'smooth' });
            await new Promise(r => setTimeout(r, 200 + Math.random() * 400));
        }
    }""")


async def _evaluate_selectors(page, field: str, site_selectors: list = None) -> Any:
    """Try all selectors for a field, returns first match."""
    field_selectors = PRODUCT_SELECTORS.get(field, [])
    if site_selectors:
        field_selectors = site_selectors + field_selectors

    code = f"""
    (() => {{
        const selectors = {json.dumps(field_selectors)};
        for (const s of selectors) {{
            try {{
                const el = document.querySelector(s);
                if (el) {{
                    if (s.startsWith('meta')) return el.content;
                    if (s.startsWith('link')) return el.href;
                    const txt = el.textContent.trim();
                    if (txt) {{ return txt; }}
                }}
            }} catch(e) {{ continue; }}
        }}
        return null;
    }})()
    """
    return await page.evaluate(code)


async def _extract_jsonld(page) -> Dict:
    """Extract product data from JSON-LD (any site)."""
    ld = await page.evaluate("""() => {
        const scripts = document.querySelectorAll('script[type="application/ld+json"]');
        for (const s of scripts) {
            try {
                const data = JSON.parse(s.textContent);
                const items = [data].concat(data['@graph'] || []);
                for (const item of items) {
                    if (item['@type'] === 'Product' || item['@type'] === 'ItemPage') return item;
                }
            } catch(e) { continue; }
        }
        return null;
    }""")
    return ld or {}


async def _extract_nuxt_state(page) -> Dict:
    """Extract product data from Nuxt.js __NUXT__ state."""
    nuxt = await page.evaluate("""() => {
        try { return window.__NUXT__; } catch(e) { return null; }
    }""")
    if not nuxt:
        return {}

    raw = json.dumps(nuxt, default=str)
    found = {}

    # Try common Nuxt state paths for product data
    for key in ["product", "item", "data", "pageData", "productData"]:
        val = _deep_get(nuxt, key)
        if isinstance(val, dict):
            for k in ["name", "price", "description", "sku"]:
                if val.get(k):
                    found[k] = val[k]
    if not found:
        # Search by keywords
        for kw in ["name", "price", "description", "image", "sku"]:
            pattern = r'["\']' + kw + r'["\']\s*:\s*["\']([^"\']+)["\']'
            m = re.search(pattern, raw)
            if m:
                found[kw] = m.group(1)
    return found


def _deep_get(obj, key):
    """Recursively search for a key in nested dicts."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                return v
            if isinstance(v, (dict, list)):
                result = _deep_get(v, key)
                if result is not None:
                    return result
    elif isinstance(obj, list):
        for item in obj:
            result = _deep_get(item, key)
            if result is not None:
                return result
    return None


async def _extract_all(page) -> Dict:
    """Main extraction: tries every method and merges results."""
    data = {"name": None, "price": None, "images": [], "description": None, "sku": None, "brand": None}

    # 1. JSON-LD (most reliable)
    ld = await _extract_jsonld(page)
    if ld:
        offers = ld.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if ld.get("name"): data["name"] = ld["name"]
        if offers.get("price") or offers.get("lowPrice"):
            data["price"] = _parse_price(str(offers.get("price") or offers.get("lowPrice")))
        if ld.get("description"): data["description"] = ld["description"]
        if ld.get("sku"): data["sku"] = ld.get("sku")
        brand = ld.get("brand")
        if isinstance(brand, dict) and brand.get("name"):
            data["brand"] = brand["name"]
        img = ld.get("image")
        if img:
            data["images"] = [img] if isinstance(img, str) else (img[:5] if isinstance(img, list) else [img])

    # 2. Nuxt state (for Boots etc.)
    if not data["name"]:
        nd = await _extract_nuxt_state(page)
        for k, v in nd.items():
            if k in data and not data.get(k):
                data[k] = v

    # 3. DOM selectors
    site_name = _detect_site(page.url)
    site_sels = SITE_SPECIFIC.get(site_name, {})
    for field in ["name", "price", "description", "sku", "brand", "images"]:
        if not data.get(field):
            result = await _evaluate_selectors(page, field, site_sels.get(field))
            if result:
                if field == "images":
                    # images from meta returns content attr
                    data["images"] = await _extract_images(page)
                elif field == "price":
                    data["price"] = _parse_price(result)
                else:
                    data[field] = result

    # 4. Images
    if not data["images"]:
        data["images"] = await _extract_images(page)

    # 5. Brute-force text scan (last resort)
    if not data["name"] or data["price"] is None:
        text = await page.evaluate("() => document.body?.innerText || ''")
        # Try find price pattern anywhere
        if data["price"] is None:
            import re as _re
            patterns = [
                _re.search(r'[\u0e3f฿]\s*([\d,]+(?:\.\d{2})?)', text),
                _re.search(r'\$(\s*[\d,]+(?:\.\d{2})?)', text),
                _re.search(r'(?:price|ราคา|เพียง)\s*:?\s*[\u0e3f฿$]?\s*([\d,]+(?:\.\d{2})?)', text, _re.I),
                _re.search(r'([\d,]+(?:\.\d{2})?)\s*(?:บาท|฿)', text),
            ]
            for m in patterns:
                if m:
                    data["price"] = _parse_price(m.group(1))
                    break
        # Try find name from title if missing
        if not data["name"]:
            title = await page.evaluate("() => document.title")
            if title:
                # Strip site name suffixes
                for sep in [" | ", " - ", " : ", " | ", " — "]:
                    parts = title.split(sep)
                    if len(parts) > 1:
                        data["name"] = parts[0].strip()
                        break
                if not data["name"]:
                    data["name"] = title.strip()

    return data


async def _extract_images(page) -> List[str]:
    """Extract product images from page."""
    urls = await page.evaluate("""() => {
        const seen = new Set();
        const results = [];

        // Check meta og:image
        const meta = document.querySelector('meta[property="og:image"]');
        if (meta && meta.content) { seen.add(meta.content); results.push(meta.content); }

        // Check link preload
        const links = document.querySelectorAll('link[rel="preload"][as="image"]');
        links.forEach(l => { if (l.href && !seen.has(l.href)) { seen.add(l.href); results.push(l.href); } });

        // Gallery images
        const selectors = [
            '.product-gallery img', '[data-testid="product-image"] img',
            '.gallery img', '.carousel img',
            'img[src*="product"]', 'img[src*="shop"]',
            'img[src*="upload"]', 'img[src*="image"]',
        ];
        for (const sel of selectors) {
            document.querySelectorAll(sel).forEach(img => {
                const src = img.src || img.getAttribute('data-src') || img.getAttribute('data-lazy');
                if (src && !seen.has(src) && src.startsWith('http')) {
                    seen.add(src);
                    if (results.length < 5) results.push(src);
                }
            });
        }
        return results.slice(0, 5);
    }""")
    return urls


def _parse_price(text) -> Optional[float]:
    if not text:
        return None
    cleaned = re.sub(r'[^\d.,]', '', str(text).strip())
    # Handle thousands separator
    if cleaned.count(",") == 1 and cleaned.count(".") == 0:
        cleaned = cleaned.replace(",", "")
    elif cleaned.count(",") > 0 and cleaned.count(".") <= 1:
        cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


async def _save_session(ctx, domain: str) -> None:
    """Save browser session (cookies + localStorage) to disk."""
    session_dir = "/home/openhands/erp-stack/modules/product/sessions"
    os.makedirs(session_dir, exist_ok=True)
    path = os.path.join(session_dir, f"{domain}.json")
    try:
        state = await ctx.storage_state()
        with open(path, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.warning(f"Session save failed for {domain}: {e}")


async def _load_session(domain: str) -> Optional[Dict]:
    path = f"/home/openhands/erp-stack/modules/product/sessions/{domain}.json"
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            pass
    return None


# ═══════════════════════════════════════════════════════════════════════════
# SPA API Intercept Engine (Shopee, Lazada, TikTok)
# ═══════════════════════════════════════════════════════════════════════════

API_PATTERNS = {
    "shopee": [
        "/api/v4/product/get_baseinfo",
        "/api/v4/product/get_shop_detail",
        "/api/v2/product/get_one_item",
    ],
    "lazada": [
        "/api/product/detail",
        "/graphql",
        "/rest/product",
    ],
    "tiktokshop": [
        "/api/v1/product/detail",
        "/api/product/detail",
        "/api/v2/product",
    ],
}

async def _intercept_api_data(page, site: str, timeout: int = 12) -> Optional[Dict]:
    """Wait for and intercept API responses from Shopee/Lazada/TikTok."""
    patterns = API_PATTERNS.get(site, [])
    if not patterns:
        return None

    api_future = asyncio.get_event_loop().create_future()
    collected_responses = {}

    async def _handle_response(response):
        url_path = response.url.split("?")[0]
        if any(p in url_path for p in patterns):
            try:
                body = await response.json()
                collected_responses[url_path] = body
                if not api_future.done():
                    api_future.set_result(True)
            except Exception:
                pass

    page.on("response", _handle_response)
    try:
        await asyncio.wait_for(api_future, timeout=timeout)
    except asyncio.TimeoutError:
        pass
    finally:
        try:
            page.remove_listener("response", _handle_response)
        except Exception:
            pass

    if not collected_responses:
        return None

    # Parse based on site
    if site == "shopee":
        return _parse_shopee_api(collected_responses)
    elif site == "lazada":
        return _parse_lazada_api(collected_responses)
    elif site == "tiktokshop":
        return _parse_tiktok_api(collected_responses)
    return None


def _parse_shopee_api(responses: Dict) -> Optional[Dict]:
    """Parse Shopee API response into product data."""
    for path, data in responses.items():
        # /api/v4/product/get_baseinfo
        if "get_baseinfo" in path:
            prod = data.get("data", {})
            name = prod.get("name")
            images_raw = prod.get("images", [])
            price = prod.get("price") or prod.get("price_min") or prod.get("price_max")
            if price:
                # Shopee returns price in cents/100
                try:
                    price = float(price) / 100000
                except (ValueError, TypeError):
                    price = None
            description = prod.get("description")
            ctime = prod.get("ctime")
            
            if name or price:
                return {
                    "name": name,
                    "price": price,
                    "currency": "THB",
                    "images": [f"https://down-th.img.susercontent.com/file/{img}" for img in (images_raw or [])[:8]],
                    "description": description,
                    "sku": str(prod.get("itemid", "")),
                    "brand": prod.get("brand"),
                }
        
        # /api/v4/product/get_shop_detail
        if "get_shop_detail" in path:
            shop = data.get("data", {})
            return {
                "shop_name": shop.get("name"),
                "shop_rating": shop.get("rating_star"),
            }
    return None


def _parse_lazada_api(responses: Dict) -> Optional[Dict]:
    """Parse Lazada API response into product data."""
    for path, data in responses.items():
        # Try graphql data
        if "graphql" in path:
            result = _deep_get(data, "data.product")
            if result:
                return {
                    "name": result.get("name"),
                    "price": result.get("price"),
                    "currency": "THB",
                    "images": [result.get("image")] if result.get("image") else [],
                    "description": result.get("shortDescription"),
                    "sku": result.get("sku"),
                    "brand": result.get("brand"),
                }
        # Direct REST
        if "product" in path.lower():
            result = data.get("data") or data.get("result")
            if isinstance(result, dict):
                return {
                    "name": result.get("name"),
                    "price": result.get("price"),
                    "currency": "THB",
                    "images": result.get("images", [])[:8] if isinstance(result.get("images"), list) else [],
                    "description": result.get("description"),
                    "sku": result.get("sku"),
                    "brand": result.get("brand"),
                }
    return None


def _parse_tiktok_api(responses: Dict) -> Optional[Dict]:
    """Parse TikTok Shop API response into product data."""
    for path, data in responses.items():
        result = data.get("data") or data
        if isinstance(result, dict):
            prod = result.get("product") or result.get("item") or result
            name = prod.get("title") or prod.get("product_name") or prod.get("name")
            price = prod.get("price") or prod.get("min_price")
            images_raw = prod.get("images") or prod.get("product_images") or []
            if isinstance(images_raw, list) and images_raw:
                images = [img.get("url", img) if isinstance(img, dict) else img for img in images_raw[:8]]
            else:
                images = []
            if name or price:
                return {
                    "name": name,
                    "price": price,
                    "currency": "USD",
                    "images": images,
                    "description": prod.get("description"),
                    "sku": prod.get("sku") or str(prod.get("id", "")),
                    "brand": prod.get("brand_name") or prod.get("brand"),
                }
    return None


async def _scrape_with_api_intercept(page, site: str, url: str, proxy_url: Optional[str] = None) -> Optional[Dict]:
    """Navigate to URL and intercept API data."""
    # Set up API intercept BEFORE navigation
    patterns = API_PATTERNS.get(site, [])
    api_data = []
    api_ready = asyncio.Event()

    async def _capture_api(response):
        url_path = response.url.split("?")[0]
        if any(p in url_path for p in patterns):
            try:
                body = await response.json()
                api_data.append(body)
                api_ready.set()
            except Exception:
                pass

    page.on("response", _capture_api)
    
    try:
        response = await page.goto(url, timeout=25000, wait_until="domcontentloaded")
        if not response:
            return None
        if response.status in (403, 429):
            logger.warning(f"Blocked ({response.status}) on {site}, trying API intercept anyway")
            # Still wait in case API calls were made before block

        # Wait for API responses (short timeout)
        try:
            await asyncio.wait_for(api_ready.wait(), timeout=15)
        except asyncio.TimeoutError:
            pass

        # Also wait more for JS-heavy sites
        if api_data:
            await _random_delay(page, 1000, 2000)

    finally:
        try:
            page.remove_listener("response", _capture_api)
        except Exception:
            pass

    if not api_data:
        return None

    # Parse based on site
    merged = {}
    if site == "shopee":
        for d in api_data:
            parsed = _parse_shopee_api({"intercepted": d})
            if parsed:
                merged.update(parsed)
    elif site == "lazada":
        for d in api_data:
            parsed = _parse_lazada_api({"intercepted": d})
            if parsed:
                merged.update(parsed)
    elif site == "tiktokshop":
        for d in api_data:
            parsed = _parse_tiktok_api({"intercepted": d})
            if parsed:
                merged.update(parsed)

    # Add source info
    if merged.get("name") or merged.get("price") is not None:
        merged["source_url"] = url
        merged["source_site"] = site
        return merged
    
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Main Entry
# ═══════════════════════════════════════════════════════════════════════════

async def scrape_url(url: str, proxy_url: Optional[str] = None, rotate_proxy: bool = True) -> dict:
    """Scrape product URL — 3-layer fallback: HTTP → Playwright → Vision AI.
    
    Args:
        url: Product URL to scrape
        proxy_url: Specific proxy to use (None = auto-rotate if PROXY_LIST set)
        rotate_proxy: If True and no proxy_url given, auto-rotate from PROXY_LIST
    """
    site = _detect_site(url)
    domain = urlparse(url).netloc
    logger.info(f"Scraping [{site}]: {url}")

    # Pick proxy (auto-rotate or explicit)
    if not proxy_url and rotate_proxy:
        proxy_url = await _get_next_proxy()
    if proxy_url:
        sanitized = proxy_url.split("@")[-1] if "@" in proxy_url else proxy_url
        logger.info(f"Using proxy: {sanitized}")

    # ─── Layer 1: HTTP Extract (fast, zero overhead) ───────────────
    http_data = await _try_http_extract(url, proxy_url=proxy_url)
    if http_data and (http_data.get("name") or http_data.get("price") is not None):
        logger.info(f"HTTP success for {url}")
        return {
            "success": True,
            "method": "http",
            "product": {
                "name": http_data.get("name"),
                "price": http_data.get("price"),
                "currency": "THB",
                "images": http_data.get("images", []),
                "description": http_data.get("description"),
                "sku": http_data.get("sku"),
                "brand": http_data.get("brand"),
                "source_url": url,
                "source_site": site,
            }
        }

    # ─── Layer 1.5: SPA API Intercept (Shopee/Lazada/TikTok) ──────
    if site in ("shopee", "lazada", "tiktokshop", "tiktok"):
        # Only if HTTP failed, try browser + API intercept
        if not http_data or (not http_data.get("name") and http_data.get("price") is None):
            try:
                pr2, browser2, ctx2, page2 = await _launch_browser(proxy_url=proxy_url)
                api_result = await _scrape_with_api_intercept(page2, site, url, proxy_url=proxy_url)
                if page2:
                    try: await page2.close()
                    except: pass
                if ctx2:
                    try: await ctx2.close()
                    except: pass
                if browser2:
                    try: await browser2.close()
                    except: pass
                if pr2:
                    try: await pr2.stop()
                    except: pass
                if api_result and (api_result.get("name") or api_result.get("price") is not None):
                    logger.info(f"API Intercept success for [{site}]: {url}")
                    return {"success": True, "method": "api_intercept", "product": {
                        "name": api_result.get("name"),
                        "price": api_result.get("price"),
                        "currency": api_result.get("currency", "THB"),
                        "images": api_result.get("images", []),
                        "description": api_result.get("description"),
                        "sku": api_result.get("sku"),
                        "brand": api_result.get("brand"),
                        "source_url": url,
                        "source_site": site,
                    }}
            except Exception as e:
                logger.warning(f"API Intercept failed for [{site}]: {e}")
                # Continue to fallback to full Playwright extraction

    # ─── Layer 2: Playwright Stealth ───────────────────────────────
    pr = browser = ctx = page = None
    try:
        storage_state = await _load_session(domain)
        pr, browser, ctx, page = await _launch_browser(storage_state=storage_state, proxy_url=proxy_url)

        # Navigate with human-like behavior
        response = await page.goto(url, timeout=25000, wait_until="domcontentloaded")
        if not response:
            return {"success": False, "method": "failed", "error": "No response from page"}

        status = response.status
        if status in (403, 429, 503):
            logger.warning(f"Blocked ({status}) on {site}")
            return {"success": False, "method": "blocked", "error": f"HTTP {status} from {site}"}

        # Wait for content to stabilize
        await _random_delay(page, 1500, 3000)

        # Wait for a signal that page has meaningful content
        try:
            await page.wait_for_function(
                """() => {
                    const h1 = document.querySelector('h1');
                    const scripts = document.querySelectorAll('script[type="application/ld+json"]');
                    const nuxt = window.__NUXT__;
                    return h1 || scripts.length > 0 || nuxt;
                }""",
                timeout=8000
            )
        except Exception:
            # Timeout but navigate anyway
            pass

        # Check for anti-bot
        title = await page.title()
        body_text = await page.evaluate("() => document.body?.innerText?.toLowerCase()?.slice(0, 500) || ''")
        bot_signals = ["captcha", "verify you are human", "please confirm you are human",
                       "access denied", "automated access", "blocked"]
        if any(s in title.lower() or s in body_text for s in bot_signals):
            logger.warning(f"Anti-bot detected on {site}")
            return {"success": False, "method": "blocked", "error": f"Anti-bot detected on {site}"}

        # Scroll like a human
        await _human_scroll(page)
        await _random_delay(page, 500, 1000)

        # Extract data
        data = await _extract_all(page)

        # Save session for future use
        await _save_session(ctx, domain)

        # Build result
        result = {
            "name": data.get("name"),
            "price": data.get("price"),
            "currency": "THB",
            "images": data.get("images", []),
            "description": data.get("description"),
            "sku": data.get("sku"),
            "brand": data.get("brand"),
            "source_url": url,
            "source_site": site,
        }

        if result["name"] or result["price"] is not None:
            logger.info(f"Playwright success for {url}: name={result['name']}, price={result['price']}")
            return {"success": True, "method": "playwright", "product": result}
        else:
            logger.warning(f"Playwright could not extract data from {url}")
            return {"success": False, "method": "playwright", "error": "Could not extract product data", "product": result}

    except Exception as e:
        logger.error(f"Scrape error: {e}")
        return {"success": False, "method": "failed", "error": str(e)}

    finally:
        # Cleanup
        if page:
            try: await page.close()
            except Exception: pass
        if ctx:
            try: await ctx.close()
            except Exception: pass
        if browser:
            try: await browser.close()
            except Exception: pass
        if pr:
            try: await pr.stop()
            except Exception: pass
