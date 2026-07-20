"""
BaseScraper — Abstract class สำหรับ platform scrapers ทั้งหมด
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger("product_scraper.base")


class BaseScraper(ABC):
    """Base scraper ที่ platform scrapers ต้อง implement"""

    PLATFORM_NAME = "base"

    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.logger = logger

    @abstractmethod
    async def scrape(self, url: str) -> Dict[str, Any]:
        """Main scrape method — ต้อง implement ใน subclass"""
        pass

    @abstractmethod
    def detect(self, url: str) -> bool:
        """Check if this scraper can handle the URL"""
        pass

    def normalize_product(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize ให้ output format เดียวกัน"""
        import datetime
        return {
            "success": True,
            "method": "platform_scraper",
            "source_site": self.PLATFORM_NAME,
            "product": {
                "name": raw.get("name", ""),
                "price": raw.get("price"),
                "currency": "THB",
                "images": raw.get("images", []),
                "video_url": raw.get("video_url", ""),
                "rating": raw.get("rating"),
                "review_count": raw.get("review_count", 0),
                "description": raw.get("description", ""),
                "features": raw.get("features", []),
                "seller_name": raw.get("seller_name", ""),
                "seller_url": raw.get("seller_url", ""),
            },
            "scraped_at": datetime.datetime.now().isoformat(),
            "cached": raw.get("cached", False),
        }
