"""
AitoEarn Client — Central REST API client for all AitoEarn operations.
Handles auth, account listing, asset upload, publish flow, campaigns, affiliate.

Replaces the old scattered connector + poster duplication.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

import httpx

logger = logging.getLogger("aitoearn-client")

# ─── Config from env ─────────────────────────────────────────────────
AITOEARN_BASE = os.environ.get("AITOEARN_URL", "https://aitoearn.ai").rstrip("/")
AITOEARN_API_KEY = os.environ.get("AITOEARN_API_KEY", "")


class AitoEarnClient:
    """Central AitoEarn REST API client.
    
    Usage:
        client = AitoEarnClient()
        accounts = await client.list_accounts("tiktok")
        asset_url = await client.upload_asset("/path/to/video.mp4")
        flow = await client.create_publish_flow(content, items)
    """

    def __init__(self, base_url: str = None, api_key: str = None):
        self.base_url = (base_url or AITOEARN_BASE).rstrip("/")
        self.api_key = api_key or AITOEARN_API_KEY
        self._account_cache: Optional[List[Dict]] = None
        self._cache_ts: float = 0

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    # ─── Low-level HTTP ──────────────────────────────────────────────

    async def _call(
        self,
        method: str,
        path: str,
        body: dict = None,
        timeout: float = 120.0,
    ) -> Dict[str, Any]:
        """Call AitoEarn REST API. Returns {"ok": True, "data": ...} or {"ok": False, "error": ...}."""
        if not self.api_key:
            return {"ok": False, "error": "AITOEARN_API_KEY not configured"}
        
        headers = {"X-Api-Key": self.api_key}
        url = f"{self.base_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                elif method == "POST":
                    resp = await client.post(url, json=body or {}, headers=headers)
                elif method == "PUT":
                    resp = await client.put(url, content=body.get("_raw") if body else None, headers=headers)
                else:
                    return {"ok": False, "error": f"Unsupported method: {method}"}

                status = resp.status_code
                data = resp.json() if resp.text else {}
                
                # Log non-200 responses for debugging
                if status >= 400:
                    logger.warning(f"AitoEarn {method} {path} → HTTP {status}: {resp.text[:500] if resp.text else '(empty)'}")

                # AitoEarn wraps all responses: {code, message, data}
                if data.get("code") == 0:
                    result_data = data.get("data", data)
                    # Empty data for uploadSign means something went wrong
                    if isinstance(result_data, dict) and not result_data and "uploadSign" in path:
                        logger.warning(f"uploadSign returned empty data — API may have changed. Full response: {data}")
                    return {"ok": True, "data": result_data}
                
                return {
                    "ok": False,
                    "error": f"{data.get('message', 'Unknown error')} (HTTP {status}, code={data.get('code')})",
                    "raw": data,
                }

        except httpx.ConnectError:
            return {"ok": False, "error": "AitoEarn unreachable"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ─── Account Management ──────────────────────────────────────────

    async def list_accounts(self, platform: str = None, use_cache: bool = True) -> List[Dict]:
        """List connected channel accounts. Optionally filter by platform.
        
        Returns list of accounts with keys: id, type, uid, account, nickname, 
        avatar, fansCount, status, loginTime, workCount
        """
        # Use cache if fresh (< 5 min)
        import time
        if use_cache and self._account_cache and (time.time() - self._cache_ts) < 300:
            if platform:
                return [a for a in self._account_cache if a.get("type") == platform]
            return self._account_cache

        # Fetch all pages
        all_accounts = []
        params = []
        if platform:
            params.append(f"types[]={platform}")

        query = "&".join(params)
        path = f"/api/v2/channels/accounts?{query}" if query else "/api/v2/channels/accounts"

        result = await self._call("GET", path)
        if result["ok"]:
            data = result["data"]
            all_accounts = data.get("list", [])
            total = data.get("total", 0)
            logger.info(f"AitoEarn: {len(all_accounts)}/{total} connected accounts")

        self._account_cache = all_accounts
        self._cache_ts = time.time()
        return all_accounts

    async def get_account(self, account_id: str) -> Optional[Dict]:
        """Get single account detail."""
        result = await self._call("GET", f"/api/v2/channels/accounts/{account_id}")
        return result["data"] if result["ok"] else None

    async def get_connected_platforms(self) -> List[Dict]:
        """Get summary of connected platforms (grouped by type).
        
        Returns [{platform, count, accounts: [{id, nickname, avatar, fans, status}]}]
        """
        accounts = await self.list_accounts()
        
        platforms = {}
        for a in accounts:
            ptype = a.get("type", "unknown")
            if ptype not in platforms:
                platforms[ptype] = {"platform": ptype, "count": 0, "accounts": []}
            platforms[ptype]["count"] += 1
            platforms[ptype]["accounts"].append({
                "id": a.get("id"),
                "nickname": a.get("nickname", a.get("account", "")),
                "avatar": a.get("avatar", ""),
                "fans": a.get("fansCount", 0),
                "status": "active" if a.get("status") == 1 else "inactive",
                "works": a.get("workCount", 0),
                "last_login": a.get("loginTime"),
            })

        return sorted(platforms.values(), key=lambda p: p["count"], reverse=True)

    def get_account_for_platform(self, platform: str) -> Optional[Dict]:
        """Get the first active account for a platform from cache."""
        if not self._account_cache:
            return None
        for a in self._account_cache:
            if a.get("type") == platform and a.get("status") == 1:
                return a
        return None

    # ─── Asset Upload ────────────────────────────────────────────────

    async def upload_asset(self, file_path: str, asset_type: str = "publishMedia", public_url: str = "") -> Optional[str]:
        """Upload a local file to AitoEarn asset storage (R2).
        
        3-step flow: getUploadSign → PUT to R2 → confirm
        Falls back to public_url if uploadSign fails or returns empty.
        
        Returns public asset URL, or the public_url fallback, or None on total failure.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        filename = file_path.name
        file_size = file_path.stat().st_size

        try:
            # Step 1: Get upload signature (API uses lowercase 'filename')
            sign = await self._call("POST", "/api/assets/uploadSign", {"filename": filename, "type": asset_type, "size": file_size})

            # Fallback: if uploadSign fails, try public URL
            if not sign or not sign.get("ok") or not isinstance(sign.get("data"), dict) or not sign["data"].get("uploadUrl"):
                if public_url:
                    logger.warning(f"uploadSign failed — falling back to public URL: {public_url}")
                    return public_url
                logger.error(f"uploadSign failed and no public_url fallback: {sign.get('error') if sign else 'no response'}")
                return None
            if not sign["ok"]:
                logger.error(f"Upload sign failed: {sign['error']}")
                return None

            sign_data = sign["data"]
            asset_url = sign_data["url"]
            upload_url = sign_data["uploadUrl"]
            asset_id = sign_data["id"]

            # Step 2: Upload to R2 (raw PUT, no JSON wrapper)
            async with httpx.AsyncClient(timeout=300.0) as client:
                with open(file_path, "rb") as f:
                    raw_resp = await client.put(
                        upload_url,
                        content=f.read(),
                        headers={"Content-Length": str(file_size)},
                    )
                if raw_resp.status_code != 200:
                    logger.error(f"R2 upload failed: HTTP {raw_resp.status_code}")
                    return None

            # Step 3: Confirm
            confirm = await self._call("POST", f"/api/assets/{asset_id}/confirm")
            if not confirm["ok"]:
                logger.error(f"Asset confirm failed: {confirm['error']}")
                return None

            logger.info(f"✅ Asset uploaded: {asset_url}")
            return asset_url

        except Exception as e:
            logger.error(f"Asset upload error: {e}")
            return None

    # ─── Publish Flow ────────────────────────────────────────────────

    async def create_publish_flow(
        self,
        content: Dict,
        items: List[Dict],
        publish_at: str = None,
        flow_id: str = None,
    ) -> Dict:
        """Create a publish flow. publishAt is REQUIRED — defaults to now.
        
        content: {title?, body, media: [{url}], cover?: {url}}
        items: [{platform, accountId, option?}]
        
        Returns {ok, data: {flowId, tasks: [{id, platform, accountId, status}]}}
        """
        if not publish_at:
            from datetime import datetime, timezone
            publish_at = datetime.now(timezone.utc).isoformat()

        payload = {
            "content": content,
            "items": items,
            "publishAt": publish_at,
        }
        if flow_id:
            payload["flowId"] = flow_id

        return await self._call("POST", "/api/v2/channels/publish/flows", payload)

    async def publish_now(self, task_id: str) -> Dict:
        """Publish a queued task immediately."""
        return await self._call("POST", f"/api/v2/channels/publish/tasks/{task_id}/publishNow")

    async def get_flow(self, flow_id: str) -> Dict:
        """Get publish flow detail with task statuses."""
        return await self._call("GET", f"/api/v2/channels/publish/flows/{flow_id}")

    async def list_publish_records(self, status: str = None) -> List[Dict]:
        """List publish records (published/queued)."""
        path = "/api/v2/channels/publish-records"
        if status:
            path += f"?status={status}"
        result = await self._call("GET", path)
        return result.get("data", {}).get("list", []) if result["ok"] else []

    # ─── Publish: High-level one-shot ────────────────────────────────

    async def publish_video(
        self,
        video_path: str,
        caption: str,
        items: List[Dict] = None,
        hashtags: List[str] = None,
        schedule_at: str = None,
        publish_immediately: bool = True,
        title: str = "",
        description: str = "",
    ) -> Dict[str, Any]:
        """One-shot: upload video + create flow + optionally publish now.
        
        Supports multi-platform via items=[{platform, accountId}, ...]
        Falls back to legacy single platform (tiktok) if items is None.
        Returns {success, flow_id, tasks, platforms, error}
        """
        # 0. Resolve items from platforms/accounts
        if items is None:
            # Legacy: resolve from single platform
            platform = "tiktok"
            acct = self.get_account_for_platform(platform)
            if not acct:
                await self.list_accounts(use_cache=False)
                acct = self.get_account_for_platform(platform)
            if acct:
                items = [{"platform": platform, "accountId": acct.get("id", "")}]
            else:
                return {"success": False, "error": f"No active {platform} account connected"}
        else:
            # Multi-platform: resolve any missing accountIds
            for item in items:
                if not item.get("accountId"):
                    plat = item.get("platform", "tiktok")
                    acct = self.get_account_for_platform(plat)
                    if not acct:
                        await self.list_accounts(use_cache=False)
                        acct = self.get_account_for_platform(plat)
                    if acct:
                        item["accountId"] = acct.get("id", "")
                        logger.info(f"Auto-resolved {plat} account: {item['accountId']}")
                    else:
                        logger.warning(f"No active {plat} account — skipping")

        # Filter valid items only
        items = [i for i in items if i.get("accountId")]
        if not items:
            return {"success": False, "error": "No valid platform accounts for publishing"}

        logger.info(f"Publishing to: {[i['platform'] for i in items]}")

        # 1. Upload to AitoEarn asset storage (local file only)
        video_url = video_path
        if not video_path.startswith("http"):
            uploaded = await self.upload_asset(video_path)
            if not uploaded:
                return {"success": False, "error": "Asset upload failed — m2igen.com URLs not allowed by AitoEarn"}
            video_url = uploaded

        # 2. Build caption with hashtags
        full_title = (title or caption or description)[:100]
        full_body = (description or caption or full_title)[:2200]
        if hashtags:
            tags = " ".join(f"#{t.strip('#')}" for t in hashtags)
            full_body = f"{full_body} {tags}"

        # 3. Create publish flow (multi-platform via items[])
        flow = await self.create_publish_flow(
            content={
                "title": full_title,
                "body": full_body[:2200],
                "media": [{"url": video_url}],
            },
            items=items,
            publish_at=schedule_at,
        )

        if not flow["ok"]:
            return {"success": False, "error": f"Publish flow: {flow['error']}"}

        flow_data = flow["data"]
        tasks = flow_data.get("tasks", [])

        result = {
            "success": True,
            "flow_id": flow_data.get("flowId", ""),
            "tasks": tasks,
            "platforms": [t.get("platform") for t in tasks],
        }

        # 4. Publish immediately if requested (all tasks)
        if publish_immediately:
            for task in tasks:
                task_id = task.get("id", "")
                if task_id:
                    pub = await self.publish_now(task_id)
                    if pub["ok"]:
                        logger.info(f"Published {task.get('platform')} ({task_id})")
                    else:
                        logger.warning(f"publishNow {task.get('platform')} failed: {pub['error']}")
            result["published_now"] = True

        return result

    # ─── Campaigns ───────────────────────────────────────────────────

    async def get_active_campaigns(self) -> List[Dict]:
        """Get active campaigns from AitoEarn."""
        result = await self._call("GET", "/api/v1/campaigns/active")
        if result["ok"]:
            return result.get("data", {}).get("campaigns", [])
        return []

    async def submit_to_campaign(self, campaign_id: str, video_url: str, platform: str = "tiktok") -> Dict:
        """Report content to a campaign."""
        return await self._call("POST", f"/api/v1/campaigns/{campaign_id}/content", {
            "video_url": video_url,
            "platform": platform,
        })

    # ─── Affiliate ───────────────────────────────────────────────────

    async def get_affiliate_link(self, product_name: str = "", product_url: str = "") -> Optional[str]:
        """Get an affiliate link for a product."""
        result = await self._call("GET", "/api/v1/affiliate/links", {
            "product_name": product_name,
            "product_url": product_url,
        })
        if result["ok"]:
            links = result.get("data", {}).get("links", [])
            if links:
                return links[0].get("url", links[0].get("affiliate_url", ""))
        return None

    # ─── Earnings ────────────────────────────────────────────────────

    async def get_earnings(self, period: str = "30d") -> Dict:
        """Get earnings summary."""
        result = await self._call("GET", f"/api/v1/earnings?period={period}")
        return result.get("data", {}) if result["ok"] else {"total": 0, "period": period}

    # ─── Pipeline Sync ─────────────────────────────────────────────

    async def sync_with_pipeline(self, pipeline_job: dict) -> Dict:
        """Sync a completed pipeline job with AitoEarn."""
        try:
            product_name = pipeline_job.get("product_title", "") or pipeline_job.get("product_url", "")
            result = {"affiliate_link": None, "synced": True}
            if product_name:
                link = await self.get_affiliate_link(product_name)
                if link:
                    result["affiliate_link"] = link
            logger.info(f"Pipeline sync complete for {str(product_name)[:40] if product_name else 'unknown'}")
            return result
        except Exception as e:
            logger.warning(f"Pipeline sync skipped: {e}")
            return {"synced": False, "error": str(e)}

    # ─── OAuth / Platform Connect ───────────────────────────────────

    async def start_oauth(self, platform: str, redirect_uri: str = "", callback_url: str = "") -> Dict:
        """Initiate platform OAuth. Returns {url, sessionId, expiresAt}."""
        params = {}
        if redirect_uri:
            params["redirectUri"] = redirect_uri
        if callback_url:
            params["callbackUrl"] = callback_url
        result = await self._call("GET", f"/api/v2/channels/accounts/auth/{platform}", params)
        if result["ok"]:
            return {"success": True, "data": result.get("data", {})}
        return {"success": False, "error": result.get("message", "OAuth failed")}

    async def check_oauth_status(self, platform: str, session_id: str) -> Dict:
        """Poll OAuth session status."""
        result = await self._call("GET", f"/api/v2/channels/accounts/auth/{platform}/status/{session_id}")
        if result["ok"]:
            data = result.get("data", {})
            return {
                "success": True,
                "status": data.get("status", "pending"),
                "account_id": data.get("accountId"),
                "data": data,
            }
        return {"success": False, "error": result.get("message", "Status check failed")}


# Singleton
client = AitoEarnClient()
