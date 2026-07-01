"""
tiktok.py — Auto Post ไปยัง TikTok

วิธี: ใช้ tiktok-uploader library (Scan QR ครั้งเดียว ไม่ต้องยุ่งกับ Cookie)

ติดตั้ง:
  pip install tiktok-uploader

ล็อกอินครั้งแรก:
  python3 -c "from tiktok_uploader.auth import AuthBackend; AuthBackend().login('session.json')"
  
หรือ:
  tiktok-uploader login --session-file session.json

หลังจากนี้ โพสต์ได้เลยโดยไม่ต้องแตะ cookie อีก
"""

import json
import subprocess
import tempfile
import time
from pathlib import Path
from .base import PlatformBase


class TikTok(PlatformBase):
    name = "tiktok"
    method = "tiktok-uploader"

    def __init__(self, config=None):
        super().__init__(config)
        self.session_file = Path(__file__).parent.parent / "session.json"
        self.auth = None
        self._try_load_session()

    def _try_load_session(self):
        """เช็คว่ามี session file แล้วหรือยัง"""
        if self.session_file.exists():
            print(f"✅ TikTok: Session file found ({self.session_file.name})")
            return True
        else:
            print(f"⚠️ TikTok: No session file. Run --login first.")
            return False

    def check_login(self):
        """ตรวจสอบ session ว่ายังใช้ได้"""
        if not self.session_file.exists():
            return False
        # ลองโหลด session
        try:
            data = json.loads(self.session_file.read_text())
            print(f"✅ TikTok: Session OK (expires: {data.get('expires', 'unknown')})")
            return True
        except:
            return False

    def login(self):
        """
        ล็อกอิน TikTok ด้วย QR Scan
        เปิดในเบราว์เซอร์ → Scan QR ด้วยมือถือ → เสร็จ
        """
        print("""
╔══════════════════════════════════════════╗
║  🔐 TikTok Login                       ║
╠══════════════════════════════════════════╣
║  Browser จะเปิดขึ้นมา                    ║
║  แสกน QR Code ด้วยมือถือ                ║
║  แค่นี้! ไม่ต้องกรอกอะไรอีก             ║
╚══════════════════════════════════════════╝
""")
        try:
            # tiktok-uploader มี login built-in
            result = subprocess.run(
                ["tiktok-uploader", "login", "--session-file", str(self.session_file)],
                timeout=120,
            )
            if result.returncode == 0:
                print(f"✅ TikTok: Login สำเร็จ! Session saved to {self.session_file}")
                return True
            else:
                print("❌ TikTok: Login failed")
                return False
        except FileNotFoundError:
            print("❌ ไม่พบ tiktok-uploader — ลงก่อน: pip install tiktok-uploader")
            return False
        except subprocess.TimeoutExpired:
            print("❌ Login timeout")
            return False

    def upload_video(self, video_path, caption=""):
        """โพสต์วิดีโอด้วย tiktok-uploader"""
        if not self.session_file.exists():
            print("❌ TikTok: No session. Run --login first")
            return False

        print(f"📤 TikTok: Uploading {Path(video_path).name}...")
        print(f"📝 Caption: {caption[:60]}...")

        try:
            result = subprocess.run([
                "tiktok-uploader", "upload",
                "--session-file", str(self.session_file),
                video_path,
                "--caption", caption,
            ], timeout=120, capture_output=True, text=True)

            if result.returncode == 0:
                self._log_result(True, f"Uploaded: {Path(video_path).name}")
                print(result.stdout[-200:])
                return True
            else:
                self._log_result(False, result.stderr[:200])
                return False

        except FileNotFoundError:
            print("❌ ไม่พบ tiktok-uploader")
            return False
        except subprocess.TimeoutExpired:
            print("❌ Upload timeout (วิดีโออาจนานเกินไป)")
            return False
        except Exception as e:
            self._log_result(False, str(e))
            return False

    def post_content(self, content):
        """
        โพสต์ content ลง TikTok

        content dict:
        {
            "type": "video" | "image",
            "media": ["path/to/file.mp4"],
            "caption": "ข้อความ + #hashtags"
        }
        """
        if not self.check_login():
            return False

        caption = content.get("caption", "")
        hashtags = content.get("hashtags", "")
        full_caption = f"{caption}\n\n{hashtags}" if hashtags else caption
        media = content.get("media", [])

        if content.get("type") == "video" and media:
            return self.upload_video(media[0], full_caption)
        else:
            print(f"⚠️ TikTok: Video upload required (got type={content.get('type')})")
            return False


# ─── Test ─────────────────────────────────────────────────

if __name__ == "__main__":
    tiktok = TikTok()
    print("🧪 TikTok module (tiktok-uploader)")
    if tiktok.check_login():
        print("✅ Ready to upload")
    else:
        print("⚠️ Run --login first")
