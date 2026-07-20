"""
Lazada Thailand Scraper — Scrape product data from Lazada.co.th
Fallback chain: Playwright → JSON-LD → Selector Pool (with data-attributes)
"""
import re
import json
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .base import BaseScraper

logger = logging.getLogger("product_scraper.lazada")

# ─── Selector Pool ─────────────────────────────────────────────────────────

PRODUCT_SELECTORS = {
    "name": [
        "h1[class*='pdp-product-title']",
        "h1[class*='product-title']",
        "[data-spm='pdp-product-title'] h1",
        "div[class*='product-title'] h1",
        "//h1[contains(@class, 'product')]",
    ],
    "price": [
        "span[class*='pdp-price']",
        "span[class*='price']",
        "div[class*='pdp-product-price'] span",
        "[data-spm='pdp-price'] span",
        "//span[contains(@class, 'price') and contains(text(), '฿')]",
    ],
    "images": [
        "div[class*='gallery-preview'] img",
        "div[class*='image-gallery'] img",
        "div[class*='pdp-image'] img",
        "img[class*='pdp']",
        "//img[contains(@class, 'gallery')]",
    ],
    "description": [
        "div[class*='product-description']",
        "div[class*='pdp-product-desc']",
        "//div[contains(@class, 'desc')]",
    ],
    "rating": [
        "span[class*='rating']",
        "div[class*='rating'] span",
        "//span[contains(@class, 'rating')]",
    ],
    "seller": [
        "a[class*='seller-name']",
        "div[class*='seller'] a",
        "//a[contains(@class, 'seller')]",
    ],
}

# Lazada data attribute patterns
DATA_PATTERNS = {
    "name": ["data-product-name", "data-title", "data-name"],
    "price": ["data-price", "data-product-price"],
    "sku": ["data-sku", "data-product-sku", "data-item-id"],
}


class LazadaScraper(BaseScraper):
    PLATFORM_NAME = "lazada"
    DOMAINS = ["lazada.co.th", "lazada.com", "lazada.sg", "lazada.com.my"]

    def detect(self, url: str) -> bool:
        domain = urlparse(url).netloc.lower()
        return any(d in domain for d in self.DOMAINS)

    async def scrape(self, url: str) -> Dict[str, Any]:
        logger.info(f"Lazada scraping: {url}")

        # Method 1: Playwright
        result = await self._scrape_playwright(url)
        if result.get("name"):
            return self.normalize_product(result)

        # Method 2: HTTP + DOM extract
        result = await self._scrape_http(url)
        if result.get("name"):
            return self.normalize_product(result)

        return {
            "success": False,
            "error": "Could not scrape product data from Lazada",
            "source_url": url,
            "source_site": "lazada",
            "product": {"name": "", "price": None, "images": []},
        }

    async def _scrape_playwright(self, url: str) -> Dict[str, Any]:
        try:
            from playwright.async_api import async_playwright

            proxy_cfg = {"server": self.proxy.replace("http://", "")} if self.proxy else None

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
                context = await browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/126.0.0.0 Safari/537.36"),
                    locale="th-TH",
                    proxy=proxy_cfg,
                )
                page = await context.new_page()
                try:
                    await page.goto(url, timeout=25000, wait_until="domcontentloaded")
                    await page.wait_for_timeout(3000)
                    content = await page.content()
                    result = self._extract_from_html(content, url)

                    # Try window.pageData (Lazada stores data here)
                    if not result.get("name"):
                        try:
                            state = await page.evaluate("window.pageData")
                            if state:
                                result = self._extract_from_state(state, url)
                        except:
                            pass

                except Exception as e:
                    logger.warning(f"Lazada Playwright error: {e}")
                    result = {}
                finally:
                    await browser.close()
                return result
        except ImportError:
            return {}

    async def _scrape_http(self, url: str) -> Dict[str, Any]:
        try:
            import httpx
            headers = {
                "User-Agent": ("Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/126.0.0.0 Mobile Safari/537.36"),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "th-TH,th;q=0.9",
            }
            async with httpx.AsyncClient(proxy=self.proxy, timeout=15, follow_redirects=True) as client:
                r = await client.get(url, headers=headers)
                return self._extract_from_html(r.text, url)
        except Exception as e:
            logger.error(f"Lazada HTTP error: {e}")
            return {}

    def _extract_from_html(self, html: str, url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        product = {"name": "", "price": None, "images": [], "description": "",
                   "rating": None, "review_count": 0, "seller_name": "", "seller_url": url}

        # JSON-LD
        json_ld = soup.find("script", type="application/ld+json")
        if json_ld:
            try:
                data = json.loads(json_ld.string)
                if isinstance(data, dict):
                    product["name"] = data.get("name", "") or product["name"]
                    if data.get("offers"):
                        p = data["offers"].get("price", "")
                        try: product["price"] = float(p)
                        except: pass
                    img = data.get("image", [])
                    if isinstance(img, list):
                        product["images"] = img[:6]
                    elif img:
                        product["images"] = [img]
            except: pass

        # Data attributes (Lazada-specific)
        if not product["name"]:
            for attr in DATA_PATTERNS["name"]:
                el = soup.select_one(f"[{attr}]")
                if el:
                    product["name"] = el.get(attr, "") or el.get_text(strip=True)
                    if product["name"]:
                        break

        # Selector engine
        if not product["name"]:
            for sel in PRODUCT_SELECTORS["name"]:
                if sel.startswith("//"):
                    continue
                el = soup.select_one(sel)
                if el:
                    text = el.get_text(strip=True)
                    if text:
                        product["name"] = text
                        break

        # Price
        if not product["price"]:
            for sel in PRODUCT_SELECTORS["price"]:
                if sel.startswith("//"):
                    continue
                el = soup.select_one(sel)
                if el:
                    text = el.get_text(strip=True)
                    m = re.search(r"[\d,]+(?:\.\d{2})?", text)
                    if m:
                        try:
                            product["price"] = float(m.group().replace(",", ""))
                            break
                        except: pass

        # Images
        if not product["images"]:
            for sel in PRODUCT_SELECTORS["images"]:
                if sel.startswith("//"):
                    continue
                els = soup.select(sel)
                if els:
                    for el in els:
                        src = el.get("src") or el.get("data-src") or ""
                        if src and "data:image" not in src:
                            product["images"].append(src)
                    if product["images"]:
                        product["images"] = product["images"][:6]
                        break

        return product

    def _extract_from_state(self, state: dict, url: str) -> Dict[str, Any]:
        """Extract from window.pageData"""
        product = {}
        try:
            if isinstance(state, dict):
                p = state.get("product", state)
                product["name"] = p.get("name", "")
                product["price"] = p.get("price", p.get("originalPrice", 0))
                product["images"] = [img.get("src", "") for img in p.get("images", [])][:6]
                product["description"] = p.get("description", "")
                product["rating"] = p.get("rating", None)
                product["seller_name"] = p.get("sellerName", "")
        except Exception as e:
            logger.warning(f"Lazada state error: {e}")
        return product
