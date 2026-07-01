"""
instagram.py — Auto Post ไปยัง Instagram

2 วิธี:
  - API (แนะนำ): Instagram Graph API — ฟรี
  - Cookie: ใช้ session cookie (fallback)
"""

import requests
import json
from pathlib import Path
from .base import PlatformBase


class Instagram(PlatformBase):
    name = "instagram"
    method = "api"

    GRAPH_API = "https://graph.facebook.com/v21.0"

    def __init__(self, config=None):
        super().__init__(config)
        self.access_token = self.config.get("access_token", "")
        self.business_id = self.config.get("business_id", "")

    def post_content(self, content):
        if self.method == "api" and self.access_token:
            return self._post_via_api(content)
        else:
            return self._post_via_cookie(content)

    def _post_via_api(self, content):
        """
        Instagram Graph API — container-based upload
        Step 1: Create media container
        Step 2: Publish container
        """
        caption = content.get("caption", "")
        ctype = content.get("type", "image")
        media = content.get("media", [])
        media_url = media[0] if media else ""
        media_path = media[0] if media else ""

        try:
            if ctype == "image":
                # สร้าง Image Container
                create_url = f"{self.GRAPH_API}/{self.business_id}/media"
                create_data = {
                    "image_url": media_url,
                    "caption": caption,
                    "access_token": self.access_token,
                }
            elif ctype == "video":
                create_url = f"{self.GRAPH_API}/{self.business_id}/media"
                create_data = {
                    "media_type": "VIDEO",
                    "video_url": media_url,
                    "caption": caption,
                    "access_token": self.access_token,
                }
            elif ctype == "carousel" and len(media) > 1:
                children_ids = []
                for m in media:
                    child = requests.post(
                        f"{self.GRAPH_API}/{self.business_id}/media",
                        data={"image_url": m, "is_carousel_item": True, "access_token": self.access_token},
                    ).json()
                    if child.get("id"):
                        children_ids.append(child["id"])
                
                create_url = f"{self.GRAPH_API}/{self.business_id}/media"
                create_data = {
                    "media_type": "CAROUSEL",
                    "children": ",".join(children_ids),
                    "caption": caption,
                    "access_token": self.access_token,
                }
            else:
                self._log_result(False, f"Unsupported type for IG: {ctype}")
                return False

            # Step 1
            resp = requests.post(create_url, data=create_data, timeout=30)
            result = resp.json()
            container_id = result.get("id")
            if not container_id:
                self._log_result(False, f"Container creation failed: {result}")
                return False

            # Wait for media processing
            import time
            time.sleep(5)

            # Step 2
            publish_url = f"{self.GRAPH_API}/{self.business_id}/media_publish"
            publish_data = {
                "creation_id": container_id,
                "access_token": self.access_token,
            }
            pub_resp = requests.post(publish_url, data=publish_data, timeout=30)
            pub_result = pub_resp.json()

            if pub_result.get("id"):
                self._log_result(True, f"Post ID: {pub_result['id']}")
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
                "https://www.instagram.com/create/",
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
        """IG — เน้นรูปภาพสวยๆ"""
        return content


if __name__ == "__main__":
    ig = Instagram({"access_token": "", "business_id": ""})
    print("🧪 Instagram module loaded")
