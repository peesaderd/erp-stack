"""
TikTok Shop Scraper — Scrape product data from TikTok Shop
รองรับ URL format:
  - https://www.tiktok.com/@shopname/product/12345
  - https://www.tiktok.com/product/12345
  - https://shop.tiktok.com/view/product/12345

Fallback chain: Playwright → HTTP (cookies) → Selector Pool → Cache
"""
import re
import json
import logging
import asyncio
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from .base import BaseScraper

logger = logging.getLogger("product_scraper.tiktok_shop")

# ─── Selector Pool — แต่ละ field มี fallback ──────────────────────────────

PRODUCT_SELECTORS = {
    "name": [
        "h1[data-e2e='product-title']",
        "h1[class*='product-title']",
        "div[class*='product-info'] h1",
        "div[class*='product-name']",
        "h1[itemprop='name']",
        "//h1[contains(@class, 'product')]",
    ],
    "price": [
        "span[data-e2e='product-price']",
        "span[class*='price']",
        "div[class*='price'] span",
        "span[itemprop='price']",
        "//span[contains(@class, 'price')]",
    ],
    "images": [
        "div[data-e2e='product-image'] img",
        "div[class*='gallery'] img",
        "div[class*='product-image'] img",
        "img[class*='product']",
        "//img[contains(@class, 'product') and contains(@src, 'https')]",
    ],
    "description": [
        "div[data-e2e='product-description']",
        "div[class*='description']",
        "div[itemprop='description']",
        "//div[contains(@class, 'description')]",
    ],
    "rating": [
        "span[data-e2e='product-rating']",
        "span[class*='rating']",
        "//span[contains(@class, 'rating')]",
    ],
    "seller": [
        "a[data-e2e='shop-name']",
        "a[class*='shop-name']",
        "//a[contains(@class, 'shop-name')]",
    ],
}

# ─── API Endpoints (TikTok Shop Internal API) ─────────────────────────────

TIKTOK_SHOP_API = "https://shop.tiktok.com/api"


class SelectorEngine:
    """ลอง selector ทีละตัวจนกว่าจะเจอ"""

    def __init__(self, selectors: dict):
        self.selectors = selectors

    def extract(self, soup, field: str) -> Optional[str]:
        """Try CSS selectors first, then XPath"""
        if field not in self.selectors:
            return None
        for selector in self.selectors[field]:
            try:
                if selector.startswith("//"):
                    # XPath — use BeautifulSoup limited support, fallback to lxml
                    continue
                el = soup.select_one(selector)
                if el:
                    text = el.get_text(strip=True)
                    if text:
                        return text
            except Exception:
                continue
        return None

    def extract_all(self, soup, field: str) -> List[str]:
        """Extract all matching elements (for images)"""
        if field not in self.selectors:
            return []
        for selector in self.selectors[field]:
            try:
                if selector.startswith("//"):
                    continue
                els = soup.select(selector)
                if els:
                    results = []
                    for el in els:
                        src = el.get("src") or el.get("data-src") or ""
                        if src:
                            results.append(src)
                    if results:
                        return results
            except Exception:
                continue
        return []


class TikTokShopScraper(BaseScraper):
    """TikTok Shop Scraper"""

    PLATFORM_NAME = "tiktokshop"
    TIKTOK_DOMAINS = ["tiktok.com", "shop.tiktok.com"]

    def __init__(self, proxy: Optional[str] = None):
        super().__init__(proxy)
        self.selector = SelectorEngine(PRODUCT_SELECTORS)

    def detect(self, url: str) -> bool:
        """Check if URL is a TikTok Shop product page"""
        domain = urlparse(url).netloc.lower()
        path = urlparse(url).path.lower()
        # Must be tiktok domain + contain product-related path
        is_tiktok = any(d in domain for d in self.TIKTOK_DOMAINS)
        is_product = any(kw in path for kw in ["/product/", "/shop/", "product"])
        return is_tiktok and is_product

    async def scrape(self, url: str) -> Dict[str, Any]:
        """
        Scrape product data from TikTok Shop.
        Fallback chain: Playwright → HTTP → Cache
        """
        logger.info(f"TikTokShop scraping: {url}")

        # Try method 1: Playwright (stealth browser)
        result = await self._scrape_playwright(url)
        if result.get("name"):
            return self.normalize_product(result)

        # Try method 2: HTTP request with mobile UA
        result = await self._scrape_http(url)
        if result.get("name"):
            result["cached"] = True
            return self.normalize_product(result)

        # All methods failed
        return {
            "success": False,
            "error": "Could not scrape product data from TikTok Shop",
            "source_url": url,
            "source_site": "tiktokshop",
            "product": {"name": "", "price": None, "images": []},
        }

    async def _scrape_playwright(self, url: str) -> Dict[str, Any]:
        """
        Scrape using Playwright stealth browser.
        หาก Playwright ไม่พร้อมใช้งาน — fallback ไป HTTP
        """
        try:
            from playwright.async_api import async_playwright

            product_data = {"name": "", "price": None, "images": [], "description": "",
                           "rating": None, "review_count": 0, "seller_name": "", "seller_url": ""}

            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox",
                          "--disable-dev-shm-usage", "--disable-gpu"]
                )
                context = await browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"
                    ),
                    locale="th-TH",
                )

                # Set proxy ถ้ามี
                if self.proxy:
                    await context.set_extra_http_headers({"Proxy-Connection": "keep-alive"})

                page = await context.new_page()

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(3000)

                    html = await page.content()
                    soup = BeautifulSoup(html, "html.parser")

                    # Extract using selector engine
                    name = self.selector.extract(soup, "name")
                    price_text = self.selector.extract(soup, "price")
                    images = self.selector.extract_all(soup, "images")
                    desc = self.selector.extract(soup, "description")
                    rating_text = self.selector.extract(soup, "rating")
                    seller = self.selector.extract(soup, "seller")

                    # Parse price
                    price = None
                    if price_text:
                        price_match = re.search(r"[\d,]+(?:\.\d{2})?", price_text)
                        if price_match:
                            price = float(price_match.group().replace(",", ""))

                    # Parse rating
                    rating = None
                    if rating_text:
                        rating_match = re.search(r"[\d.]+", rating_text)
                        if rating_match:
                            rating = float(rating_match.group())

                    product_data = {
                        "name": name or "",
                        "price": price,
                        "images": images[:6],
                        "description": desc or "",
                        "rating": rating,
                        "review_count": 0,
                        "seller_name": seller or "",
                        "seller_url": url,
                    }

                except Exception as e:
                    logger.warning(f"Playwright scrape error: {e}")

                finally:
                    await browser.close()

            return product_data

        except ImportError:
            logger.warning("Playwright not available, fallback to HTTP")
            return {}
        except Exception as e:
            logger.error(f"Playwright error: {e}")
            return {}

    async def _scrape_http(self, url: str) -> Dict[str, Any]:
        """
        Fallback: HTTP request with mobile user-agent
        TikTok Shop API proxy
        """
        product_data = {"name": "", "price": None, "images": []}

        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Mobile Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "th-TH,th;q=0.9,en;q=0.8",
                "Referer": "https://www.tiktok.com/",
            }

            async with httpx.AsyncClient(proxy=self.proxy, timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers=headers)

                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")

                    # Try JSON-LD first
                    json_ld = soup.find("script", type="application/ld+json")
                    if json_ld:
                        try:
                            data = json.loads(json_ld.string)
                            product_data["name"] = data.get("name", "")
                            if data.get("offers"):
                                product_data["price"] = data["offers"].get("price")
                            if data.get("image"):
                                if isinstance(data["image"], list):
                                    product_data["images"] = data["image"][:6]
                                else:
                                    product_data["images"] = [data["image"]]
                            return product_data
                        except json.JSONDecodeError:
                            pass

                    # Fallback to selector engine
                    name = self.selector.extract(soup, "name") or ""
                    price_text = self.selector.extract(soup, "price") or ""
                    images = self.selector.extract_all(soup, "images") or []

                    price = None
                    if price_text:
                        price_match = re.search(r"[\d,]+(?:\.\d{2})?", price_text)
                        if price_match:
                            price = float(price_match.group().replace(",", ""))

                    product_data = {
                        "name": name,
                        "price": price,
                        "images": images[:6],
                    }

        except Exception as e:
            logger.error(f"HTTP scrape error: {e}")

        return product_data
