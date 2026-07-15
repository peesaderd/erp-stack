"""
TikTok Poster — Abstract posting layer.
Strategy: AitoEarn REST API → Cookie-based Playwright fallback → Error.

AitoEarn REST API docs: https://docs.aitoearn.ai/en/api
"""

import os
import json
import asyncio
import logging
import httpx
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("tiktok-poster")

STORAGE_DIR = Path(__file__).parent.parent / "storage"
COOKIE_FILE = STORAGE_DIR / "tiktok_cookies.json"

# AitoEarn REST API config
AITOEARN_BASE = os.getenv("AITOEARN_URL", "https://aitoearn.ai")
AITOEARN_API_KEY = os.getenv("AITOEARN_API_KEY", "")
TIKTOK_ACCOUNT_ID = os.getenv("TIKTOK_AITOEARN_ACCOUNT_ID", "")


class TikTokPoster:
    """Post videos to TikTok via AitoEarn REST API or cookie."""

    def __init__(
        self,
        aitoearn_url: str = None,
        api_key: str = None,
        tiktok_account_id: str = None,
    ):
        self.aitoearn_url = (aitoearn_url or AITOEARN_BASE).rstrip("/")
        self.api_key = api_key or AITOEARN_API_KEY
        self.tiktok_account_id = tiktok_account_id or TIKTOK_ACCOUNT_ID
        self._cookies = None

    # ─── Cookie management ─────────────────────────────────────────────

    def load_cookies(self) -> Optional[dict]:
        """Load TikTok cookies from disk."""
        if COOKIE_FILE.exists():
            try:
                self._cookies = json.loads(COOKIE_FILE.read_text())
                return self._cookies
            except Exception:
                return None
        return None

    def save_cookies(self, cookies: dict):
        """Save TikTok cookies to disk."""
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        COOKIE_FILE.write_text(json.dumps(cookies, indent=2))
        self._cookies = cookies
        logger.info("TikTok cookies saved")

    def has_cookies(self) -> bool:
        return self._cookies is not None or COOKIE_FILE.exists()

    # ─── AitoEarn Asset Upload ───────────────────────────────────────

    async def _upload_asset(self, file_path: str) -> Optional[str]:
        """
        Upload a local file to AitoEarn asset storage (R2).
        Returns public asset URL, or None on failure.
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return None

            file_size = file_path.stat().st_size
            filename = file_path.name

            async with httpx.AsyncClient(timeout=300.0) as client:
                # Step 1: Get upload signature
                sign_resp = await client.post(
                    f"{self.aitoearn_url}/api/assets/uploadSign",
                    json={"filename": filename, "type": "publishMedia", "size": file_size},
                    headers={"X-Api-Key": self.api_key},
                )
                sign_data = sign_resp.json()
                if sign_data.get("code") != 0:
                    logger.error(f"Upload sign failed: {sign_data.get('message')}")
                    return None

                sign = sign_data["data"]
                asset_url = sign["url"]
                upload_url = sign["uploadUrl"]
                asset_id = sign["id"]

                # Step 2: Upload to R2
                with open(file_path, "rb") as f:
                    upload_resp = await client.put(
                        upload_url,
                        content=f.read(),
                        headers={"Content-Length": str(file_size)},
                    )
                if upload_resp.status_code != 200:
                    logger.error(f"R2 upload failed: HTTP {upload_resp.status_code}")
                    return None

                # Step 3: Confirm upload
                confirm_resp = await client.post(
                    f"{self.aitoearn_url}/api/assets/{asset_id}/confirm",
                    headers={"X-Api-Key": self.api_key},
                )
                if confirm_resp.json().get("code") != 0:
                    logger.error(f"Asset confirm failed")
                    return None

                logger.info(f"Asset uploaded: {asset_url}")
                return asset_url

        except Exception as e:
            logger.error(f"Asset upload error: {e}")
            return None

    # ─── AitoEarn REST API ───────────────────────────────────────────

    async def post_via_aitoearn(
        self,
        video_path: str,
        caption: str,
        hashtags: list = None,
        schedule_at: str = None,
    ) -> Dict[str, Any]:
        """
        Post video via AitoEarn REST API (channels publish flow).
        Flow: upload asset → confirm → create publish flow → publish now.
        Endpoint: POST /api/v2/channels/publish/flows
        
        NOTE: publishAt is REQUIRED. If schedule_at is None, publishes now.
        Returns {success, flow_id, tasks, method, error}
        """
        if not self.api_key:
            return {"success": False, "error": "No AITOEARN_API_KEY configured", "method": "aitoearn"}
        if not self.tiktok_account_id:
            return {"success": False, "error": "No TIKTOK_AITOEARN_ACCOUNT_ID configured", "method": "aitoearn"}

        try:
            # Determine video URL: upload local files, use URLs directly
            video_url = video_path
            if not video_path.startswith("http"):
                # Check if there's a public URL equivalent
                public_url = f"https://m2igen.com/tiktok/storage/videos/{Path(video_path).name}"
                # Try uploading via AitoEarn asset system (more reliable)
                asset_url = await self._upload_asset(video_path)
                video_url = asset_url or public_url
                logger.info(f"Video URL for publish: {video_url}")

            # Build caption with hashtags
            full_caption = caption
            if hashtags:
                tags = " ".join(f"#{t.strip('#')}" for t in hashtags)
                full_caption = f"{caption} {tags}"

            # publishAt is REQUIRED by AitoEarn API
            from datetime import datetime, timezone
            if not schedule_at:
                schedule_at = datetime.now(timezone.utc).isoformat()

            payload = {
                "content": {
                    "title": caption[:100],
                    "body": full_caption[:2200],  # TikTok char limit
                    "media": [{"url": video_url}],
                },
                "publishAt": schedule_at,
                "items": [
                    {
                        "platform": "tiktok",
                        "accountId": self.tiktok_account_id,
                    }
                ],
            }

            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.aitoearn_url}/api/v2/channels/publish/flows",
                    json=payload,
                    headers={"X-Api-Key": self.api_key},
                )
                data = resp.json()

                if data.get("code") == 0:
                    flow = data.get("data", {})
                    tasks = flow.get("tasks", [])
                    return {
                        "success": True,
                        "flow_id": flow.get("flowId", ""),
                        "tasks": tasks,
                        "method": "aitoearn",
                    }
                return {
                    "success": False,
                    "error": f"AitoEarn: {data.get('message', 'Unknown error')}",
                    "method": "aitoearn",
                }
        except httpx.ConnectError:
            logger.warning("AitoEarn not reachable, falling back to cookie")
            return {"success": False, "error": "AitoEarn unreachable", "method": "aitoearn"}
        except Exception as e:
            return {"success": False, "error": str(e), "method": "aitoearn"}

    # ─── Cookie-based fallback ────────────────────────────────────────

    async def post_via_cookie(
        self,
        video_path: str,
        caption: str,
        hashtags: list = None,
    ) -> Dict[str, Any]:
        """
        Post video using tiktok_uploader package (cookie-based).
        Returns {success, post_id, post_url, error}
        """
        if not self.has_cookies() and not self.load_cookies():
            return {"success": False, "error": "No TikTok cookies available", "method": "cookie"}

        try:
            cookies = self._cookies or self.load_cookies()
            if not cookies:
                return {"success": False, "error": "Cookies empty", "method": "cookie"}

            # Use tiktok_uploader package (v1.2.0+)
            from tiktok_uploader import upload_video
            from tiktok_uploader.types import Cookie

            # Convert saved cookies to Cookie objects
            cookie_list = []
            if isinstance(cookies, list):
                for c in cookies:
                    cookie_list.append(Cookie(
                        name=c.get("name", ""),
                        value=c.get("value", ""),
                        domain=c.get("domain", ".tiktok.com"),
                        path=c.get("path", "/"),
                    ))
            elif isinstance(cookies, dict):
                # Single cookie object
                for name, value in cookies.items():
                    if isinstance(value, str):
                        cookie_list.append(Cookie(name=name, value=value, domain=".tiktok.com", path="/"))

            # Post via headless browser (sync, run in thread)
            results = await asyncio.to_thread(
                upload_video,
                str(video_path),
                description=caption,
                cookies_list=cookie_list,
                headless=True,
                browser="chromium",
            )

            if len(results) == 0:
                # Empty failed list = ALL SUCCESS
                return {
                    "success": True,
                    "method": "cookie",
                    "message": "Video posted to TikTok"
                }
            # Check if any failed
            failed_paths = [v.get("path", "?") for v in results]
            return {
                "success": False,
                "error": f"Upload failed for videos: {failed_paths}",
                "method": "cookie",
            }
        except ImportError as e:
            return {"success": False, "error": f"tiktok_uploader: {e}", "method": "cookie"}
        except Exception as e:
            return {"success": False, "error": str(e), "method": "cookie"}

    # ─── Main: try AitoEarn → fallback cookie ─────────────────────────

    async def post(
        self,
        video_path: str,
        caption: str,
        hashtags: list = None,
        schedule_at: str = None,
    ) -> Dict[str, Any]:
        """
        Post to TikTok: AitoEarn first, cookie fallback.
        """
        logger.info(f"Posting to TikTok: {video_path} — caption: {caption[:60]}...")

        # 1. Try AitoEarn
        result = await self.post_via_aitoearn(video_path, caption, hashtags, schedule_at)
        if result.get("success"):
            return result

        logger.info(f"AitoEarn failed: {result.get('error')}, trying cookie...")

        # 2. Fallback: cookie
        if self.has_cookies():
            result = await self.post_via_cookie(video_path, caption, hashtags)
            if result.get("success"):
                return result

        return {
            "success": False,
            "error": f"All methods failed. AitoEarn: {result.get('error', 'N/A')}",
            "method": "all_failed",
        }


# Singleton
poster = TikTokPoster()
