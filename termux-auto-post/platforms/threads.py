"""
threads.py — Auto Post ไปยัง Threads (Meta)

วิธี:
  - API (แนะนำ): Threads API — ฟรี! (ผ่าน Facebook Graph API)
  - Cookie: fallback ใช้ cookie session
"""

import requests
import json
from pathlib import Path
from .base import PlatformBase


class Threads(PlatformBase):
    name = "threads"
    method = "api"

    GRAPH_API = "https://graph.facebook.com/v21.0"

    def __init__(self, config=None):
        super().__init__(config)
        self.access_token = self.config.get("access_token", "")
        self.user_id = self.config.get("user_id", "")

    def post_content(self, content):
        if self.method == "api" and self.access_token:
            return self._post_via_api(content)
        else:
            return self._post_via_cookie(content)

    def _post_via_api(self, content):
        """
        Threads API — คล้าย IG
        Step 1: Create media container
        Step 2: Publish
        """
        caption = content.get("caption", "")
        ctype = content.get("type", "text")
        link = content.get("link", "")

        # Threads API ใช้ IG user_id (เหมือนกัน)
        if not self.user_id:
            self._log_result(False, "No user_id configured")
            return False

        # Threads รองรับ text + image + video
        text = caption
        if link:
            text += f"\n{link}"

        try:
            create_data = {
                "media_type": "TEXT",
                "text": text,
                "access_token": self.access_token,
            }

            if ctype == "image" and content.get("media"):
                create_data["media_type"] = "IMAGE"
                create_data["image_url"] = content["media"][0]
            elif ctype == "video" and content.get("media"):
                create_data["media_type"] = "VIDEO"
                create_data["video_url"] = content["media"][0]

            # Step 1
            resp = requests.post(
                f"{self.GRAPH_API}/{self.user_id}/threads",
                data=create_data,
                timeout=30,
            )
            result = resp.json()
            container_id = result.get("id")

            if not container_id:
                self._log_result(False, f"Container failed: {result}")
                return False

            import time
            time.sleep(3)

            # Step 2
            pub_resp = requests.post(
                f"{self.GRAPH_API}/{self.user_id}/threads_publish",
                data={
                    "creation_id": container_id,
                    "access_token": self.access_token,
                },
                timeout=30,
            )
            pub_result = pub_resp.json()

            if pub_result.get("id"):
                self._log_result(True, f"Threads ID: {pub_result['id']}")
                return True
            else:
                self._log_result(False, f"Publish failed: {pub_result}")
                return False

        except Exception as e:
            self._log_result(False, str(e))
            return False

    def _post_via_cookie(self, content):
        """Fallback: ใช้ cookie session"""
        headers = self.get_headers()
        try:
            resp = requests.post(
                "https://www.threads.net/create/",
                headers=headers,
                data=content,
                timeout=30,
            )
            self._log_result(resp.ok, f"Cookie post: {resp.status_code}")
            return resp.ok
        except Exception as e:
            self._log_result(False, str(e))
            return False

    def format_for_platform(self, content, product):
        """Threads — content คล้าย X แต่ยาวกว่า"""
        return content


if __name__ == "__main__":
    t = Threads({"access_token": "", "user_id": ""})
    print("🧪 Threads module loaded")
