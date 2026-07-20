"""
AitoEarn Connector — Campaign + Affiliate bridge between TikTok UGC and AitoEarn.
Fetches campaigns, affiliate links, reports content back.
"""

import os
import json
import logging
import httpx
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger("aitoearn-connector")

AITOEARN_URL = os.environ.get("AITOEARN_URL", "http://localhost:8123")
STORAGE_DIR = Path(__file__).parent.parent / "storage"
CAMPAIGN_CACHE = STORAGE_DIR / "aitoearn_campaigns.json"
AFFILIATE_CACHE = STORAGE_DIR / "aitoearn_affiliates.json"


class AitoEarnConnector:
    """Bridge between TikTok UGC pipeline and AitoEarn earning system."""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or AITOEARN_URL

    async def _call(self, method: str, path: str, body: dict = None) -> dict:
        """Call AitoEarn API."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                if method == "GET":
                    resp = await client.get(f"{self.base_url}{path}")
                else:
                    resp = await client.post(f"{self.base_url}{path}", json=body or {})
                if resp.status_code >= 400:
                    return {"success": False, "error": f"{resp.status_code}: {resp.text[:200]}"}
                return {"success": True, "data": resp.json()}
        except httpx.ConnectError:
            return {"success": False, "error": "AitoEarn unreachable"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ─── Campaigns ──────────────────────────────────────────────────────

    async def get_active_campaigns(self) -> List[Dict]:
        """Get active campaigns from AitoEarn."""
        result = await self._call("GET", "/api/v1/campaigns/active")
        if result.get("success"):
            campaigns = result.get("data", {}).get("campaigns", [])
            CAMPAIGN_CACHE.write_text(json.dumps(campaigns, indent=2))
            return campaigns
        # Fallback: cached
        if CAMPAIGN_CACHE.exists():
            return json.loads(CAMPAIGN_CACHE.read_text())
        return []

    async def get_campaign(self, campaign_id: str) -> Optional[Dict]:
        """Get single campaign details."""
        result = await self._call("GET", f"/api/v1/campaigns/{campaign_id}")
        return result.get("data") if result.get("success") else None

    async def submit_content_to_campaign(
        self,
        campaign_id: str,
        video_url: str,
        platform: str = "tiktok",
        metadata: dict = None,
    ) -> Dict:
        """Report posted content to a campaign."""
        return await self._call("POST", f"/api/v1/campaigns/{campaign_id}/content", {
            "video_url": video_url,
            "platform": platform,
            "metadata": metadata or {},
        })

    # ─── Affiliate Links ───────────────────────────────────────────────

    async def get_affiliate_links(self, product_name: str = "", product_url: str = "") -> List[Dict]:
        """Get affiliate links for a product."""
        result = await self._call("GET", "/api/v1/affiliate/links", {
            "product_name": product_name,
            "product_url": product_url,
        })
        if result.get("success"):
            links = result.get("data", {}).get("links", [])
            return links
        return []

    async def get_product_affiliate_link(self, product_name: str, platform: str = "tiktok") -> Optional[str]:
        """Get the best affiliate link for a product + platform combo."""
        links = await self.get_affiliate_links(product_name=product_name)
        for link in links:
            if link.get("platform") == platform:
                return link.get("url", link.get("affiliate_url", ""))
        # Any platform
        if links:
            return links[0].get("url", links[0].get("affiliate_url", ""))
        return None

    async def generate_affiliate_link(
        self,
        product_url: str,
        platform: str = "tiktok",
        campaign_id: str = "",
    ) -> Optional[str]:
        """Generate a new affiliate link for a product URL."""
        result = await self._call("POST", "/api/v1/affiliate/generate", {
            "product_url": product_url,
            "platform": platform,
            "campaign_id": campaign_id,
        })
        if result.get("success"):
            return result.get("data", {}).get("affiliate_url", "")
        return None

    # ─── Earnings ──────────────────────────────────────────────────────

    async def get_earnings(self, period: str = "30d") -> Dict:
        """Get earnings summary."""
        result = await self._call("GET", f"/api/v1/earnings?period={period}")
        if result.get("success"):
            return result.get("data", {})
        return {"total": 0, "period": period, "breakdown": []}

    async def get_content_performance(self, content_url: str) -> Optional[Dict]:
        """Get performance metrics for a specific content URL."""
        result = await self._call("GET", "/api/v1/content/performance", {
            "url": content_url,
        })
        return result.get("data") if result.get("success") else None

    # ─── Sync ──────────────────────────────────────────────────────────

    async def sync_with_pipeline(self, pipeline_job: dict) -> Dict:
        """Sync a completed pipeline job with AitoEarn.
        - Report to campaign if affiliated
        - Generate affiliate link if needed
        - Update earnings tracker
        """
        product_name = pipeline_job.get("logs", {}).get("product_title", "")
        video_url = pipeline_job.get("logs", {}).get("video_web_url", "")

        result = {
            "affiliate_link": None,
            "campaign_reported": False,
            "errors": [],
        }

        # 1. Get/generate affiliate link
        if product_name:
            link = await self.get_product_affiliate_link(product_name)
            if not link:
                # Try generating
                product_url = pipeline_job.get("product_url", "")
                link = await self.generate_affiliate_link(product_url or product_name)
            result["affiliate_link"] = link

        # 2. Check for matching campaigns
        campaigns = await self.get_active_campaigns()
        for c in campaigns:
            if c.get("product_category") and product_name.lower().find(c["product_category"].lower()) >= 0:
                if video_url:
                    await self.submit_content_to_campaign(
                        campaign_id=c.get("id", ""),
                        video_url=video_url,
                    )
                result["campaign_reported"] = True
                result["campaign_id"] = c.get("id")

        return result


# Singleton
connector = AitoEarnConnector()
