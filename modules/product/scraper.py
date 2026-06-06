# Patchright-based product scraper with stealth techniques.
"""Playwright-based product scraper with stealth techniques.
Supports Shopee, Lazada, Boots, Watsons, and generic e-commerce sites."""
import asyncio, re, json, logging, os
from typing import Optional, Dict, List, Any
from urllib.parse import urlparse
from datetime import datetime

logger = logging.getLogger("product_scraper")

SITE_PATTERNS = {
    "shopee": ["shopee.co.th", "shopee.com"],
    "lazada": ["lazada.co.th", "lazada.com"],
    "boots": ["boots.co.th", "boots.com"],
    "watsons": ["watsons.co.th", "watsons.com"],
    "central": ["central.co.th"],
}

async def _launch_browser(storage_state: Optional[str] = None):
    from patchright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
        ]
    )
    ctx = await browser.new_context(
        storage_state=storage_state,
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        viewport={"width": 1366, "height": 768},
        locale="th-TH",
        timezone_id="Asia/Bangkok",
    )
    # Stealth: override webdriver detection
    await ctx.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        window.chrome = { runtime: {} };
    """)
    page = await ctx.new_page()
    return pw, browser, ctx, page

async def _save_session(ctx, domain: str) -> None:
    """Save browser context state to disk for session persistence."""
    session_dir = "/home/openhands/erp-stack/modules/product/sessions"
    os.makedirs(session_dir, exist_ok=True)
    session_path = os.path.join(session_dir, f"{domain}.json")

    try:
        state = await ctx.storage_state()
        with open(session_path, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.warning(f"Failed to save session for {domain}: {e}")


async def _try_http_extract(url: str) -> Optional[Dict[str, Any]]:
    """Try to extract product data using HTTP requests and regex only."""
    import httpx

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return None
            html = resp.text

        data = {"name": None, "price": None, "images": [], "description": None, "sku": None}

        # Extract OG tags
        og_title = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html)
        if og_title:
            data["name"] = og_title.group(1)

        og_image = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
        if og_image:
            data["images"] = [og_image.group(1)]

        og_desc = re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html)
        if og_desc:
                data["description"] = og_desc.group(1)

        # Extract JSON-LD
        ld_match = re.search(r'<script\s+type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        if ld_match:
            try:
                ld = json.loads(ld_match.group(1))
                if isinstance(ld, dict):
                    if ld.get("@type") in ("Product", "ItemPage"):
                        if ld.get("name") and not data["name"]:
                            data["name"] = ld["name"]
                        if ld.get("offers"):
                            off = ld["offers"]
                            if isinstance(off, dict) and off.get("price"):
                                data["price"] = _parse_price(off["price"])
                            elif isinstance(off, list) and off[0].get("price"):
                                data["price"] = _parse_price(off[0]["price"])
                        if ld.get("image"):
                            img = ld["image"]
                            if isinstance(img, str):
                                data["images"] = [img]
                            elif isinstance(img, list):
                                data["images"] = img[:5]
                        if ld.get("sku"):
                            data["sku"] = ld["sku"]
                        if ld.get("description") and not data["description"]:
                            data["description"] = ld["description"]
            except json.JSONDecodeError:
                pass

        # Fallback to title tag
        if not data["name"]:
            title_match = re.search(r'<title>(.*?)</title>', html)
            if title_match:
                data["name"] = title_match.group(1)

        return data if (data["name"] or data["price"]) else None

    except Exception as e:
        logger.warning(f"HTTP extraction failed: {e}")
        return None

def _detect_site(url: str) -> str:
    domain = urlparse(url).netloc.lower()
    for site, domains in SITE_PATTERNS.items():
        if any(d in domain for d in domains):
            return site
    return "generic"

async def _extract_boots(page) -> Dict:
    """Boots.co.th uses Nuxt.js with __NUXT__ state"""
    data = {"name": None, "price": None, "images": [], "description": None, "sku": None}
    
    try:
        # Wait for Nuxt state
        await page.wait_for_function("() => window.__NUXT__", timeout=8000)
        nuxt = await page.evaluate("() => window.__NUXT__")
        
        # Navigate the Nuxt state to find product data
        # Typical Boots Nuxt state structure
        raw = json.dumps(nuxt, ensure_ascii=False)
        
        # Try to find product info via meta tags
        name = await page.evaluate("""() => {
            const m = document.querySelector('meta[property="og:title"]');
            return m ? m.content : null;
        }""")
        data["name"] = name
        
        price = await page.evaluate("""() => {
            const m = document.querySelector('[itemprop="price"], .product-price, [data-testid="price"]');
            return m ? m.textContent.trim() : null;
        }""")
        data["price"] = _parse_price(price) if price else None
        
        images = await page.evaluate("""() => {
            const imgs = document.querySelectorAll('.product-gallery img, .product-image img, [data-testid="product-image"] img');
            return Array.from(imgs).slice(0, 5).map(i => i.src || i.getAttribute('data-src')).filter(Boolean);
        }""")
        data["images"] = images or []
        
        desc = await page.evaluate("""() => {
            const d = document.querySelector('[itemprop="description"], .product-description, .product-details');
            return d ? d.textContent.trim().slice(0, 2000) : null;
        }""")
        data["description"] = desc
        
        # Try to find JSON-LD
        ld = await page.evaluate("""() => {
            const s = document.querySelector('script[type="application/ld+json"]');
            if (!s) return null;
            try { return JSON.parse(s.textContent); } catch { return null; }
        }""")
        if ld and isinstance(ld, dict):
            if "name" in ld and not data["name"]:
                data["name"] = ld["name"]
            if "offers" in ld and not data["price"]:
                data["price"] = _parse_price(ld["offers"].get("price"))
            if "sku" in ld:
                data["sku"] = ld["sku"]
            if "image" in ld:
                img = ld["image"]
                if isinstance(img, list):
                    data["images"] = img[:5]
                else:
                    data["images"] = [img]
        
    except Exception as e:
        logger.warning(f"Boots extraction failed: {e}")
    
    return data

async def _extract_generic(page) -> Dict:
    """Generic e-commerce product extraction"""
    data = {"name": None, "price": None, "images": [], "description": None, "sku": None}
    
    try:
        await page.wait_for_timeout(3000)
        
        # Try different selectors
        name = await page.evaluate("""() => {
            const selectors = [
                'h1[data-testid="product-name"]', 'h1.product-title',
                '[itemprop="name"]', '.product-name', '.product__title',
                'h1', 'meta[property="og:title"]'
            ];
            for (const s of selectors) {
                const el = document.querySelector(s);
                if (el) {
                    if (s.startsWith('meta')) return el.content;
                    return el.textContent.trim();
                }
            }
            return null;
        }""")
        data["name"] = name
        
        price = await page.evaluate("""() => {
            const selectors = [
                '[itemprop="price"]', '[data-testid="price"]',
                '.product-price', '.price', '.product__price',
                '.sale-price', '.current-price'
            ];
            for (const s of selectors) {
                const el = document.querySelector(s);
                if (el) return el.textContent.trim();
            }
            return null;
        }""")
        data["price"] = _parse_price(price) if price else None
        
        images = await page.evaluate("""() => {
            const selectors = [
                '.product-gallery img', '.product-image img',
                '[data-testid="product-image"] img',
                '.gallery img', '.carousel img',
                'img[src*="product"]', 'img[src*="shop"]',
                'meta[property="og:image"]'
            ];
            const urls = new Set();
            for (const s of selectors) {
                const els = document.querySelectorAll(s);
                for (const el of els) {
                    const src = el.src || el.content || el.getAttribute('data-src');
                    if (src && src.startsWith('http')) urls.add(src);
                }
            }
            return Array.from(urls).slice(0, 5);
        }""")
        data["images"] = images or []
        
        # Try JSON-LD
        ld = await page.evaluate("""() => {
            const s = document.querySelector('script[type="application/ld+json"]');
            if (!s) return null;
            try { return JSON.parse(s.textContent); } catch { return null; }
        }""")
        if ld and isinstance(ld, dict):
            for item in ([ld] + (ld.get("@graph", []) if isinstance(ld.get("@graph"), list) else [])):
                if item.get("@type") in ("Product", "ItemPage"):
                    if item.get("name") and not data["name"]:
                        data["name"] = item["name"]
                    if item.get("offers"):
                        off = item["offers"]
                        if isinstance(off, dict) and off.get("price"):
                            data["price"] = _parse_price(off["price"])
                        elif isinstance(off, list) and off[0].get("price"):
                            data["price"] = _parse_price(off[0]["price"])
                    if item.get("image"):
                        img = item["image"]
                        data["images"] = [img] if isinstance(img, str) else img[:5]
                    if item.get("sku"):
                        data["sku"] = item["sku"]
                    if item.get("description") and not data["description"]:
                        data["description"] = item["description"]
                    if item.get("brand") and isinstance(item["brand"], dict):
                        data["brand"] = item["brand"].get("name")
                    break
        
        # Description fallback
        if not data["description"]:
            desc = await page.evaluate("""() => {
                const selectors = [
                    '[itemprop="description"]', '.product-description',
                    '.product-details', '#description', '.description',
                    'meta[property="og:description"]', 'meta[name="description"]'
                ];
                for (const s of selectors) {
                    const el = document.querySelector(s);
                    if (el) {
                        if (s.startsWith('meta')) return el.content;
                        return el.textContent.trim().slice(0, 2000);
                    }
                }
                return null;
            }""")
            data["description"] = desc
        
    except Exception as e:
        logger.warning(f"Generic extraction error: {e}")
    
    return data

def _parse_price(text: str) -> Optional[float]:
    if not text:
        return None
    # Remove currency symbols, commas, spaces
    cleaned = re.sub(r'[฿$€£¥,.\s]', '', text.strip())
    # Handle Thai numbering
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None

async def scrape_url(url: str) -> dict:
    """Main entry point: scrape a product URL and return structured data."""
    site = _detect_site(url)
    domain = urlparse(url).netloc
    logger.info(f"Scraping {site}: {url}")
    
    # Try HTTP extraction first
    http_data = await _try_http_extract(url)
    if http_data:
        result = {
            "name": http_data.get("name"),
            "price": http_data.get("price"),
            "currency": "THB",
            "images": http_data.get("images", []),
            "description": http_data.get("description"),
            "sku": http_data.get("sku"),
            "source_url": url,
            "source_site": site,
        }
        return {"success": True, "method": "http", "product": result}

    pr = browser = ctx = page = None
    try:
        session_path = f"/home/openhands/erp-stack/modules/product/sessions/{domain}.json"
        storage_state = None
        if os.path.exists(session_path):
            with open(session_path, "r") as f:
                storage_state = json.load(f)

        pr, browser, ctx, page = await _launch_browser(storage_state=storage_state)
        
        # Load page
        await page.goto(url, timeout=15000, wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)
        
        # Detect and handle blocked pages
        title = await page.title()
        if "captcha" in title.lower() or "verify" in title.lower() or "blocked" in title.lower():
            logger.warning(f"Anti-bot detected on {site}")
            return {"success": False, "method": "blocked", "error": f"Anti-bot detection on {site}"}
        
        # Extract based on site
        if site == "boots":
            data = await _extract_boots(page)
        else:
            data = await _extract_generic(page)
        

        await _save_session(ctx, domain)

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
        
        # Success if we got at least name or price
        if result["name"] or result["price"]:
            return {"success": True, "method": "playwright", "product": result}
        else:
            return {"success": False, "method": "playwright", "error": "Could not extract product data", "product": result}
    
    except Exception as e:
        logger.error(f"Scrape error: {e}")
        return {"success": False, "method": "failed", "error": str(e)}
    
    finally:
        if ctx: await ctx.close()
        if browser: await browser.close()
        if pw: await pw.stop()
