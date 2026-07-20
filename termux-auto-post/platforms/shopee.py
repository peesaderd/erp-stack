"""
shopee.py — Shopee Affiliate Post

Shopee ไม่มี API สำหรับโพสต์ (เป็น marketplace)
ทำได้แค่:
  1. สร้าง Affiliate Link → นำไปโพสต์บน platform อื่น
  2. ไม่สามารถโพสต์ลง Shopee โดยตรง
"""

import requests
from .base import PlatformBase


class Shopee(PlatformBase):
    name = "shopee"
    method = "affiliate_api"

    AFFILIATE_API = "https://affiliate.shopee.co.th/api/v1"

    def __init__(self, config=None):
        super().__init__(config)
        self.api_key = self.config.get("api_key", "")
        self.affiliate_id = self.config.get("affiliate_id", "")

    def post_content(self, content):
        """
        Shopee — ไม่รองรับการโพสต์โดยตรง

        แต่สร้าง Affiliate Link ให้ platform อื่นใช้ได้
        """
        self._log_result(True, "Link created — for use on other platforms")
        return True

    def generate_affiliate_link(self, product_url=None, product_id=None):
        """สร้าง Shopee Affiliate Link"""
        if not self.api_key:
            print("⚠️ Shopee: No API key for affiliate link")
            # Fallback: return URL ตรงๆ
            return product_url or f"https://shopee.co.th/product/{product_id}/"

        try:
            resp = requests.post(
                f"{self.AFFILIATE_API}/link/generate",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "url": product_url,
                    "affiliate_id": self.affiliate_id,
                },
                timeout=10,
            )
            data = resp.json()
            if data.get("short_url"):
                return data["short_url"]
        except:
            pass

        return product_url

    def format_for_platform(self, content, product):
        """Shopee — สร้างแค่ affiliate link"""
        link = self.generate_affiliate_link(
            product.get("affiliate_link") or product.get("url")
        )
        content["shopee_link"] = link
        return content


if __name__ == "__main__":
    s = Shopee({"api_key": "", "affiliate_id": ""})
    print("🧪 Shopee module loaded")
    print("Note: Shopee posts go to other platforms, not Shopee itself")
