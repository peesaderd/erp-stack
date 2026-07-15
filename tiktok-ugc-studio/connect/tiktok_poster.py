"""
TikTok Poster — Abstract posting layer.
Strategy: AitoEarn API bypass → Cookie-based fallback → Error.
"""

import os
import json
import logging
import httpx
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("tiktok-poster")

STORAGE_DIR = Path(__file__).parent.parent / "storage"
COOKIE_FILE = STORAGE_DIR / "tiktok_cookies.json"


class TikTokPoster:
    """Post videos to TikTok via AitoEarn proxy or cookie."""

    def __init__(self, aitoearn_url: str = "http://localhost:8123"):
        self.aitoearn_url = aitoearn_url
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

    # ─── AitoEarn bypass ──────────────────────────────────────────────

    async def post_via_aitoearn(
        self,
        video_path: str,
        caption: str,
        hashtags: list = None,
        schedule_at: str = None,
    ) -> Dict[str, Any]:
        """
        Post video via AitoEarn TikTok API proxy.
        Returns {success, post_id, post_url, error}
        """
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                payload = {
                    "video_path": video_path,
                    "caption": caption,
                    "hashtags": hashtags or [],
                }
                if schedule_at:
                    payload["schedule_at"] = schedule_at

                resp = await client.post(
                    f"{self.aitoearn_url}/api/v1/tiktok/post",
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "success": True,
                        "post_id": data.get("post_id", ""),
                        "post_url": data.get("post_url", ""),
                        "method": "aitoearn",
                    }
                # AitoEarn returned error — try parsing
                return {
                    "success": False,
                    "error": f"AitoEarn: {resp.status_code} {resp.text[:200]}",
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

            # Use tiktok_uploader package
            from tiktok_uploader.upload import upload_video
            from tiktok_uploader.auth import AuthBackend

            # Write temp cookie file for tiktok_uploader
            cookie_path = STORAGE_DIR / "tiktok_session.txt"
            cookie_path.write_text(cookies.get("sessionid", ""))

            result = upload_video(
                video_path,
                caption,
                cookies=cookies,
            )

            if result and getattr(result, "id", None):
                return {
                    "success": True,
                    "post_id": str(result.id),
                    "method": "cookie",
                }
            return {
                "success": False,
                "error": f"Upload returned no ID: {result}",
                "method": "cookie",
            }
        except ImportError:
            return {"success": False, "error": "tiktok_uploader package not available", "method": "cookie"}
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
