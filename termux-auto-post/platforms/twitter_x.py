"""
twitter_x.py — Auto Post ไปยัง X (Twitter)

2 วิธี:
  - API: X API v2 Basic ($100/เดือน) หรือ Free Tier (1,500 post/เดือน)
  - Cookie: ใช้ session cookie (แนะนำเพราะฟรี)
"""

import requests
import json
from pathlib import Path
from .base import PlatformBase


class TwitterX(PlatformBase):
    name = "twitter_x"
    method = "cookie"  # default: cookie (ฟรี!)

    API_V2 = "https://api.twitter.com/2"
    UPLOAD_MEDIA = "https://upload.twitter.com/1.1/media/upload.json"

    def __init__(self, config=None):
        super().__init__(config)
        self.bearer_token = self.config.get("bearer_token", "")

    def post_content(self, content):
        if self.method == "api" and self.bearer_token:
            return self._post_via_api(content)
        else:
            return self._post_via_cookie(content)

    def _post_via_api(self, content):
        """X API v2"""
        caption = content.get("caption", "")
        # รองรับแค่ 280 ตัวอักษร (หรือ 4000 ถ้ามี X Premium)
        if len(caption) > 280:
            caption = caption[:277] + "..."

        headers = {
            "Authorization": f"Bearer {self.bearer_token}",
            "Content-Type": "application/json",
        }

        data = {"text": caption}
        if content.get("link"):
            data["text"] += f"\n\n{content['link']}"

        try:
            resp = requests.post(
                f"{self.API_V2}/tweets",
                headers=headers,
                json=data,
                timeout=30,
            )
            result = resp.json()
            if resp.status_code == 201 and result.get("data", {}).get("id"):
                self._log_result(True, f"Tweet ID: {result['data']['id']}")
                return True
            else:
                self._log_result(False, f"API error: {result}")
                return False
        except Exception as e:
            self._log_result(False, str(e))
            return False

    def _post_via_cookie(self, content):
        """
        X — โพสต์ผ่าน Cookie Session

        ใช้ auth_token cookie จาก x.com
        """
        headers = self.get_headers({
            "Content-Type": "application/json",
            "X-CSRF-Token": self._get_csrf(),
            "Authorization": "Bearer " + self._get_bearer_from_cookie(),
            "Origin": "https://x.com",
            "Referer": "https://x.com/compose/post",
        })

        caption = content.get("caption", "")
        if len(caption) > 280:
            caption = caption[:277] + "..."

        data = {
            "variables": {
                "tweet_text": caption,
                "dark_request": False,
                "media": {},
                "semantic_annotation_ids": [],
            },
            "features": {
                "tweet_text_limit": 280,
            },
            "queryId": self._get_query_id(),
        }

        try:
            url = "https://x.com/i/api/graphql/CreateTweet"
            resp = requests.post(url, headers=headers, json=data, timeout=30)
            if resp.status_code == 200:
                self._log_result(True, "Tweet posted via cookie")
                return True
            else:
                self._log_result(False, f"Cookie post failed: {resp.status_code}")
                return False
        except Exception as e:
            self._log_result(False, str(e))
            return False

    def _get_csrf(self):
        """ดึง CSRF token จาก cookie"""
        cookies = self.load_cookies() or {}
        return cookies.get("ct0", "")

    def _get_bearer_from_cookie(self):
        """Bearer token สำหรับ X internal API"""
        return "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"

    def _get_query_id(self):
        """GraphQL query ID สำหรับ X CreateTweet"""
        return "bDEfVAMGfyVpzWGEBzOYA"  # อาจเปลี่ยนตาม version

    def format_for_platform(self, content, product):
        """X — ข้อความสั้น, รูปภาพ, link"""
        # ตัดข้อความให้สั้น
        existing = content.get("caption", "")
        content["caption"] = existing[:277] if len(existing) > 280 else existing
        return content


if __name__ == "__main__":
    x = TwitterX()
    print("🧪 X/Twitter module loaded")
