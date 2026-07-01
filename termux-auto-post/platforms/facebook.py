"""
facebook.py — Auto Post ไปยัง Facebook

2 วิธี:
  - API (แนะนำ): ใช้ Facebook Graph API — ฟรี
  - Cookie: ใช้ session cookie (fallback)
"""

import requests
import json
import time
from pathlib import Path
from .base import PlatformBase


class Facebook(PlatformBase):
    name = "facebook"
    method = "api"  # default: API (ฟรี!)

    GRAPH_API = "https://graph.facebook.com/v21.0"

    def __init__(self, config=None):
        super().__init__(config)
        self.access_token = self.config.get("access_token", "")
        self.page_id = self.config.get("page_id", "")

    def post_content(self, content):
        """
        โพสต์ content ลง Facebook Page

        content dict:
        {
            "type": "image" | "video" | "text",
            "media": [paths],
            "caption": "ข้อความ",
            "link": "https://affiliate..."
        }
        """
        if self.method == "api" and self.access_token:
            return self._post_via_api(content)
        else:
            return self._post_via_cookie(content)

    def _post_via_api(self, content):
        """โพสต์ผ่าน Graph API (ฟรี, ถาวร)"""
        caption = content.get("caption", "")
        link = content.get("link", "")
        ctype = content.get("type", "text")
        media = content.get("media", [])

        # ถ้ามี link affiliate—ให้เป็น link post
        if link and ctype == "text":
            url = f"{self.GRAPH_API}/{self.page_id}/feed"
            data = {
                "message": caption,
                "link": link,
                "access_token": self.access_token,
            }
        elif ctype == "image" and media:
            url = f"{self.GRAPH_API}/{self.page_id}/photos"
            data = {"caption": caption, "access_token": self.access_token}
            files = {"source": open(media[0], "rb")} if media else {}
        elif ctype == "video" and media:
            url = f"{self.GRAPH_API}/{self.page_id}/videos"
            data = {"description": caption, "access_token": self.access_token}
            files = {"source": open(media[0], "rb")} if media else {}
        else:
            url = f"{self.GRAPH_API}/{self.page_id}/feed"
            data = {"message": caption, "access_token": self.access_token}
            files = {}

        try:
            resp = requests.post(url, data=data, files=files or None, timeout=60)
            result = resp.json()
            if resp.status_code == 200 and result.get("id"):
                self._log_result(True, f"Post ID: {result['id']}")
                return True
            else:
                self._log_result(False, f"API error: {result}")
                return False
        except Exception as e:
            self._log_result(False, str(e))
            return False

    def _post_via_cookie(self, content):
        """Fallback: โพสต์ผ่าน cookie session"""
        headers = self.get_headers({
            "Content-Type": "application/x-www-form-urlencoded",
        })
        caption = content.get("caption", "")

        try:
            resp = requests.post(
                "https://www.facebook.com/upload/",
                headers=headers,
                data={"caption": caption},
                timeout=30,
            )
            self._log_result(resp.ok, f"Cookie post: {resp.status_code}")
            return resp.ok
        except Exception as e:
            self._log_result(False, str(e))
            return False

    def format_for_platform(self, content, product):
        """Facebook Feed — content ควรเป็น text + image"""
        return content


# ─── Test ─────────────────────────────────────────────────

if __name__ == "__main__":
    fb = Facebook({"access_token": "", "page_id": ""})
    print("🧪 Facebook module loaded")
    print(f"Method: {fb.method}")
