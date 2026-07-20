"""
Shopee Thailand Scraper — Scrape product data from Shopee.co.th
Fallback chain: Playwright → JSON-LD → Selector Pool → HTTP
"""
import re
import json
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .base import BaseScraper

logger = logging.getLogger("product_scraper.shopee")

# ─── Selector Pool ─────────────────────────────────────────────────────────

PRODUCT_SELECTORS = {
    "name": [
        "h1[class*='product-title']",
        "div[class*='product-title']",
        "[data-product-name]",
        "h1[itemprop='name']",
        "div[class*='_44qnta']",          # Shopee React class
        "//h1[contains(@class, 'title')]",
    ],
    "price": [
        "div[class*='product-price']",
        "span[class*='price']",
        "div[itemprop='price']",
        "[data-product-price]",
        "//div[contains(@class, 'price')]",
    ],
    "images": [
        "img[class*='product-image']",
        "div[class*='image-viewer'] img",
        "div[class*='gallery'] img",
        "//img[contains(@class, 'product')]",
    ],
    "description": [
        "div[class*='product-description']",
        "div[itemprop='description']",
        "div[class*='description']",
    ],
    "rating": [
        "div[class*='product-rating']",
        "span[class*='rating']",
        "//*[contains(@class, 'rating')]",
    ],
    "seller": [
        "a[class*='shop-name']",
        "div[class*='shop-name']",
        "//a[contains(@class, 'shop')]",
    ],
}


class ShopeeScraper(BaseScraper):
    PLATFORM_NAME = "shopee"
    DOMAINS = ["shopee.co.th", "shopee.com", "shopee.sg", "shopee.com.my"]

    def detect(self, url: str) -> bool:
        domain = urlparse(url).netloc.lower()
        return any(d in domain for d in self.DOMAINS)

    async def scrape(self, url: str) -> Dict[str, Any]:
        logger.info(f"Shopee scraping: {url}")

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
            "error": "Could not scrape product data from Shopee",
            "source_url": url,
            "source_site": "shopee",
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

                    # ถ้ายังไม่ได้ — try window.__INITIAL_STATE__
                    if not result.get("name"):
                        try:
                            state = await page.evaluate("window.__INITIAL_STATE__")
                            if state:
                                result = self._extract_from_state(state, url)
                        except:
                            pass

                except Exception as e:
                    logger.warning(f"Shopee Playwright error: {e}")
                    result = {}
                finally:
                    await browser.close()
                return result
        except ImportError:
            logger.warning("Playwright not available")
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
            logger.error(f"Shopee HTTP error: {e}")
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
                        try:
                            product["price"] = float(p)
                        except: pass
                    img = data.get("image", [])
                    if isinstance(img, list):
                        product["images"] = img[:6]
                    elif img:
                        product["images"] = [img]
            except: pass

        # Selector engine (ถ้า JSON-LD ไม่ได้)
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

        # Seller
        if not product["seller_name"]:
            for sel in PRODUCT_SELECTORS["seller"]:
                if sel.startswith("//"):
                    continue
                el = soup.select_one(sel)
                if el:
                    product["seller_name"] = el.get_text(strip=True)
                    product["seller_url"] = el.get("href", "")
                    break

        return product

    def _extract_from_state(self, state: dict, url: str) -> Dict[str, Any]:
        """Extract from window.__INITIAL_STATE__"""
        product = {}
        try:
            if "productDetail" in state:
                p = state["productDetail"]
                product["name"] = p.get("name", "")
                product["price"] = p.get("price", p.get("price_min", 0))
                product["images"] = [img.get("url", "") for img in p.get("images", [])][:6]
                product["description"] = p.get("description", "")
                product["rating"] = p.get("rating_star", 0)
                product["review_count"] = p.get("cmt_count", 0)
                product["seller_name"] = p.get("shop_name", "")
        except Exception as e:
            logger.warning(f"State extract error: {e}")
        return product
