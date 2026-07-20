"""
base.py — Base class สำหรับทุก Platform
"""

import json
import requests
import time
import random
from pathlib import Path
from datetime import datetime


class PlatformBase:
    """Base class ที่ Platform ทุกตัวต้อง implement"""

    name = ""  # เช่น "tiktok", "facebook"
    method = "cookie"  # หรือ "api"

    def __init__(self, config=None):
        self.config = config or {}
        self.cookie_path = Path(__file__).parent.parent / "cookies" / f"{self.name}.json"
        self.stats = {
            "posted": 0,
            "failed": 0,
            "last_post": None,
        }

    def load_cookies(self):
        """โหลด cookie จากไฟล์"""
        if not self.cookie_path.exists():
            print(f"⚠️ {self.name}: No cookie file at {self.cookie_path}")
            return None
        data = json.loads(self.cookie_path.read_text())
        return data.get("cookies", {})

    def get_cookie_header(self):
        """return header dict สำหรับ curl"""
        cookies = self.load_cookies()
        if not cookies:
            return None
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        return {"Cookie": cookie_str}

    def get_headers(self, extra=None):
        """headers พื้นฐาน"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36",
            "Accept": "*/*",
            "Accept-Language": "th-TH,th;q=0.9,en;q=0.8",
        }
        cookie_header = self.get_cookie_header()
        if cookie_header:
            headers.update(cookie_header)
        if extra:
            headers.update(extra)
        return headers

    def post_content(self, content):
        """
        โพสต์ content ลง platform นี้
        content: dict {
            type: "image" | "video" | "text"
            media: [paths],
            caption: str,
            link: str (affiliate)
        }
        return: bool
        """
        raise NotImplementedError("subclass must implement post_content()")

    def format_for_platform(self, content, product):
        """
        แปลง content ให้เหมาะกับ platform
        เช่น บาง platform รองรับแค่รูป ไม่รองรับวิดีโอ
        """
        return content

    def _log_result(self, success, detail=""):
        """บันทึกผลการโพสต์"""
        if success:
            self.stats["posted"] += 1
        else:
            self.stats["failed"] += 1
        self.stats["last_post"] = datetime.now().isoformat()
        status = "✅" if success else "❌"
        print(f"{status} {self.name}: {detail or ('Posted' if success else 'Failed')}")

    def _random_delay(self, min_s=2, max_s=8):
        """หน่วงเวลาแบบสุ่ม — ไม่ให้ดูเหมือน bot"""
        delay = random.uniform(min_s, max_s)
        time.sleep(delay)
