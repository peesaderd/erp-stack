"""
TikTok Poster — Strategy: AitoEarn REST API → Cookie-based Playwright fallback.
Uses AitoEarnClient for all API operations.
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("tiktok-poster")

STORAGE_DIR = Path(__file__).parent.parent / "storage"
COOKIE_FILE = STORAGE_DIR / "tiktok_cookies.json"

# Account ID for TikTok (from AitoEarn)
TIKTOK_ACCOUNT_ID = os.getenv("TIKTOK_AITOEARN_ACCOUNT_ID", "")


class TikTokPoster:
    """Post videos to TikTok: AitoEarn first, cookie fallback."""

    def __init__(self, account_id: str = None):
        self.account_id = account_id or TIKTOK_ACCOUNT_ID
        self._cookies = None
        self._client = None  # Lazy AitoEarnClient

    @property
    def aitoearn(self):
        """Lazy-load AitoEarnClient."""
        if self._client is None:
            from connect.aitoearn_client import client as _client
            self._client = _client
        return self._client

    # ─── Cookie management ───────────────────────────────────────────

    def load_cookies(self) -> Optional[dict]:
        if COOKIE_FILE.exists():
            try:
                self._cookies = json.loads(COOKIE_FILE.read_text())
                return self._cookies
            except Exception:
                return None
        return None

    def save_cookies(self, cookies: dict):
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        COOKIE_FILE.write_text(json.dumps(cookies, indent=2))
        self._cookies = cookies

    def has_cookies(self) -> bool:
        return self._cookies is not None or COOKIE_FILE.exists()

    # ─── AitoEarn API (primary) ──────────────────────────────────────

    async def post_via_aitoearn(
        self,
        video_path: str,
        caption: str,
        hashtags: list = None,
        schedule_at: str = None,
    ) -> Dict[str, Any]:
        """Post via AitoEarn REST API. Uses the central client."""
        if not self.aitoearn.configured:
            return {"success": False, "error": "AITOEARN_API_KEY not configured", "method": "aitoearn"}
        if not self.account_id:
            return {"success": False, "error": "TIKTOK_AITOEARN_ACCOUNT_ID not configured", "method": "aitoearn"}

        result = await self.aitoearn.publish_video(
            video_path=video_path,
            caption=caption,
            hashtags=hashtags,
            account_id=self.account_id,
            schedule_at=schedule_at,
            publish_immediately=True,
        )

        if result.get("success"):
            result["method"] = "aitoearn"
        else:
            result["method"] = "aitoearn"
        return result

    # ─── Cookie-based fallback ──────────────────────────────────────

    async def post_via_cookie(
        self,
        video_path: str,
        caption: str,
        hashtags: list = None,
    ) -> Dict[str, Any]:
        """Post via Playwright browser with TikTok cookies."""
        if not self.has_cookies() and not self.load_cookies():
            return {"success": False, "error": "No TikTok cookies available", "method": "cookie"}

        try:
            cookies = self._cookies or self.load_cookies()
            if not cookies:
                return {"success": False, "error": "Cookies empty", "method": "cookie"}

            from tiktok_uploader import upload_video
            from tiktok_uploader.types import Cookie

            cookie_list = []
            if isinstance(cookies, list):
                for c in cookies:
                    cookie_list.append(Cookie(
                        name=c.get("name", ""), value=c.get("value", ""),
                        domain=c.get("domain", ".tiktok.com"), path=c.get("path", "/"),
                    ))
            elif isinstance(cookies, dict):
                for name, value in cookies.items():
                    if isinstance(value, str):
                        cookie_list.append(Cookie(name=name, value=value, domain=".tiktok.com", path="/"))

            # Build full caption with hashtags
            full_caption = caption
            if hashtags:
                tags = " ".join(f"#{t.strip('#')}" for t in hashtags)
                full_caption = f"{caption} {tags}"

            results = await asyncio.to_thread(
                upload_video,
                str(video_path),
                description=full_caption,
                cookies_list=cookie_list,
                headless=True,
                browser="chromium",
            )

            if len(results) == 0:
                return {"success": True, "method": "cookie", "message": "Video posted to TikTok"}

            failed_paths = [v.get("path", "?") for v in results]
            return {"success": False, "error": f"Upload failed: {failed_paths}", "method": "cookie"}

        except ImportError as e:
            return {"success": False, "error": f"tiktok_uploader not installed: {e}", "method": "cookie"}
        except Exception as e:
            return {"success": False, "error": str(e), "method": "cookie"}

    # ─── Main ───────────────────────────────────────────────────────

    async def post(
        self,
        video_path: str,
        caption: str,
        hashtags: list = None,
        schedule_at: str = None,
    ) -> Dict[str, Any]:
        """Post to TikTok: AitoEarn first, cookie fallback."""
        logger.info(f"📤 Posting: {Path(video_path).name} — {caption[:60]}...")

        # 1. Try AitoEarn (primary)
        if self.aitoearn.configured and self.account_id:
            result = await self.post_via_aitoearn(video_path, caption, hashtags, schedule_at)
            if result.get("success"):
                return result
            logger.info(f"AitoEarn failed: {result.get('error')}, trying cookie...")
        else:
            logger.info("AitoEarn not configured, skipping to cookie")

        # 2. Cookie fallback
        if self.has_cookies():
            result = await self.post_via_cookie(video_path, caption, hashtags)
            if result.get("success"):
                return result

        return {"success": False, "error": "All methods failed", "method": "all_failed"}


# Singleton
poster = TikTokPoster()
