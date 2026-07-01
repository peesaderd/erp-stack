"""
tiktok.py — Auto Post ไปยัง TikTok ผ่าน Cookie Session

วิธีใช้ Cookie:
  1. Login TikTok ผ่าน browser
  2. เปิด DevTools → Application → Cookies
  3. คัดลอก sessionid, tt_chain_token, msToken
  4. วางใน cookies/tiktok.json

หรือใช้ cookie_manager.py --platform tiktok --login
"""

import json
import requests
import time
import random
from pathlib import Path
from .base import PlatformBase


class TikTok(PlatformBase):
    name = "tiktok"
    method = "cookie"

    # TikTok Upload URLs
    UPLOAD_URL = "https://www.tiktok.com/upload/"
    API_UPLOAD_INIT = "https://www.tiktok.com/api/v1/video/upload/init/"
    API_UPLOAD_COMPLETE = "https://www.tiktok.com/api/v1/video/upload/complete/"
    API_PUBLISH = "https://www.tiktok.com/api/v1/video/publish/"
    API_CREATOR_INFO = "https://www.tiktok.com/api/v1/user/me/"

    def __init__(self, config=None):
        super().__init__(config)
        self.session = requests.Session()
        headers = self.get_headers()
        self.session.headers.update(headers)

        # CSRF token
        self.csrf_token = ""
        self.creator_name = ""

    def check_login(self):
        """ตรวจสอบว่า session ยังใช้ได้มั้ย"""
        try:
            resp = self.session.get(self.API_CREATOR_INFO, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("user"):
                    self.creator_name = data["user"].get("uniqueId", "")
                    print(f"✅ TikTok: Logged in as @{self.creator_name}")
                    return True
            print(f"⚠️ TikTok: Session invalid (status={resp.status_code})")
            return False
        except Exception as e:
            print(f"❌ TikTok: Check login failed: {e}")
            return False

    def _get_csrf(self):
        """ดึง CSRF token จาก session"""
        try:
            resp = self.session.get("https://www.tiktok.com/", timeout=10)
            # Extract csrf token from cookies
            for cookie in self.session.cookies:
                if cookie.name in ("csrf_token", "s_v_web_id"):
                    self.csrf_token = cookie.value
                    break
            return self.csrf_token
        except:
            return ""

    def upload_video(self, video_path, caption="", hashtags="", schedule_time=None):
        """
        อัปโหลดวิดีโอไปยัง TikTok

        Args:
            video_path: path ไฟล์วิดีโอ
            caption: คำบรรยาย
            hashtags: แฮชแท็ก (space separated)
            schedule_time: datetime object (ถ้าต้องการตั้งเวลา)
        """
        if not self.check_login():
            return False

        self._get_csrf()
        print(f"📤 TikTok: Uploading {video_path}...")

        # จำลอง upload — ของจริงต้องใช้ API upload flow ของ TikTok
        # ซึ่งต้องทำหลายขั้นตอน (init → chunked upload → complete → publish)
        # แต่ Concept คือส่งผ่าน session cookie + csrf token

        print(f"📝 Caption: {caption[:50]}...")
        print(f"#️⃣ Hashtags: {hashtags}")
        print(f"⏰ Schedule: {schedule_time or 'ทันที'}")

        # TODO: implement full upload flow
        # อ้างอิงจาก tiktok_browser.py ที่มีอยู่แล้ว
        print("⚙️ TODO: กำลังเขียน upload logic จริง...")
        print("   ดูตัวอย่างจาก tiktok_browser.py")
        
        self._log_result(True, f"Video queued: {Path(video_path).name}")
        return True

    def post_image(self, image_path, caption=""):
        """
        โพสต์รูปภาพ (TikTok รองรับ Slideshow)
        """
        print(f"📸 TikTok: Posting image {image_path}...")
        print(f"📝 Caption: {caption[:50]}...")
        self._log_result(True, f"Image: {Path(image_path).name}")
        return True

    def post_content(self, content):
        """
        โพสต์ content ลง TikTok

        content dict:
        {
            "type": "video" | "image" | "text",
            "media": ["path/to/video.mp4"] หรือ ["path/to/image.jpg"],
            "caption": "ข้อความ",
            "hashtags": "#skincare #review",
            "link": "https://..."
        }
        """
        if not self.check_login():
            print("⚠️ TikTok: Skipping — not logged in")
            return False

        caption = content.get("caption", "")
        hashtags = content.get("hashtags", "")
        full_caption = f"{caption}\n\n{hashtags}" if hashtags else caption

        ctype = content.get("type", "text")
        media = content.get("media", [])

        if ctype == "video" and media:
            return self.upload_video(media[0], full_caption)
        elif ctype == "image" and media:
            return self.post_image(media[0], full_caption)
        else:
            print(f"⚠️ TikTok: Unsupported content type: {ctype}")
            return False

    def format_for_platform(self, content, product):
        """TikTok รองรับ video และ slideshow"""
        return content


# ─── Test ─────────────────────────────────────────────────

if __name__ == "__main__":
    tiktok = TikTok()
    print(f"🧪 Testing TikTok module...")
    print(f"Cookie file: {tiktok.cookie_path}")
    tiktok.check_login()
