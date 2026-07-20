"""
schedule.py — Scheduler สำหรับ Termux Auto Post

รันวนลูป 24/7:
- TikTok → ทุก 6 ชม.
- Facebook → ทุก 12 ชม.
- Instagram → ทุก 12 ชม.
- X → ทุก 8 ชม.
- Threads → ทุก 12 ชม.
- Shopee → ทุก 24 ชม. (สร้าง link)

ใช้ termux-wake-lock ป้องกัน Android ฆ่ากระบวนการ
"""

import time
import random
import json
from datetime import datetime
from pathlib import Path


class Scheduler:
    def __init__(self, config):
        self.config = config
        self.last_run = {}  # platform → timestamp
        self.schedule = self._build_schedule()
        self.stats_file = Path(__file__).parent / "scheduler_stats.json"
        self.stats = self._load_stats()

    def _build_schedule(self):
        """สร้างตารางเวลาจาก config"""
        schedule = {}
        for name, pconfig in self.config.get("platforms", {}).items():
            if pconfig.get("enabled", False):
                hours = pconfig.get("schedule_hours", 12)
                # แปลงเป็นวินาที + random jitter
                base_seconds = hours * 3600
                jitter = random.uniform(0.8, 1.2)  # ±20%
                interval = int(base_seconds * jitter)
                schedule[name] = interval
                print(f"  📅 {name}: ทุก {hours} ชม. ({interval/3600:.1f} actual)")

        return schedule

    def _load_stats(self):
        if self.stats_file.exists():
            return json.loads(self.stats_file.read_text())
        return {"runs": 0, "posts": {}, "started": datetime.now().isoformat()}

    def _save_stats(self):
        self.stats_file.write_text(json.dumps(self.stats, indent=2, ensure_ascii=False))

    def is_due(self, platform):
        """เช็คว่าถึงเวลาโพสต์รึยัง"""
        if platform not in self.last_run:
            return True
        interval = self.schedule.get(platform, 3600)
        elapsed = time.time() - self.last_run[platform]
        return elapsed >= interval

    def run_forever(self):
        """รันวน loop ตรวจสอบและโพสต์"""
        print(f"""
╔══════════════════════════════════════════╗
║  📱 Termux Auto Post — Scheduler        ║
║  🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}       ║
║                                          ║
║  เริ่มวน loop ตรวจสอบทุก 10 นาที         ║
║  ใช้ termux-wake-lock เพื่อให้ไม่หลับ    ║
╚══════════════════════════════════════════╝
        """)

        print("📋 ตารางเวลา:")
        for name, interval in self.schedule.items():
            h = interval / 3600
            print(f"  {name:15s} → ทุก {h:5.1f} ชม.")

        print(f"\n{'='*50}")
        print(f"⏳ รอคอย... (ตรวจสอบทุก 600 วิ / 10 นาที)")
        print(f"{'='*50}\n")

        try:
            while True:
                now = datetime.now()
                to_post = []

                # ตรวจว่า platform ไหนถึงเวลา
                for name in self.schedule:
                    if self.is_due(name):
                        to_post.append(name)

                if to_post:
                    print(f"\n{'='*50}")
                    print(f"🚀 [{now.strftime('%H:%M:%S')}] ถึงเวลาโพสต์: {', '.join(to_post)}")
                    
                    # import ตรงนี้เพื่อ avoid circular import
                    from termux_main import do_post_all
                    
                    # รันโพสต์เฉพาะ platform ที่ถึงเวลา
                    for platform in to_post:
                        try:
                            print(f"\n--- {platform} ---")
                            do_post_all(self.config, specific_platform=platform)
                            self.last_run[platform] = time.time()
                            self.stats["runs"] += 1
                            self.stats["posts"][platform] = self.stats["posts"].get(platform, 0) + 1
                            self._save_stats()
                        except Exception as e:
                            print(f"❌ {platform}: Error — {e}")

                        # หน่วงระหว่าง platform
                        delay = random.randint(30, 120)
                        print(f"⏳ พัก {delay} วิ...")
                        time.sleep(delay)

                    # แจ้ง stat
                    total = sum(self.stats["posts"].values())
                    print(f"\n📊 สถิติ: {self.stats['runs']} runs | {total} posts ทั้งหมด")
                    print(f"{'='*50}\n")

                # รอ 10 นาทีแล้วค่อยตรวจใหม่
                time.sleep(600)

        except KeyboardInterrupt:
            print(f"\n\n⏹️ หยุด Scheduler")
            self._save_stats()
            print(f"📊 สถิติการทำงาน:")
            print(f"  Runs: {self.stats['runs']}")
            print(f"  Posts: {sum(self.stats['posts'].values())}")
            for name, count in self.stats['posts'].items():
                print(f"    {name}: {count}")
            print(f"  Started: {self.stats.get('started', '?')}")


# ─── ฟังก์ชันสำหรับ Termux cron ─────────────────────────

def setup_termux_cron(config):
    """
    ตั้งค่า cron ผ่าน termux-job-scheduler
    (ไม่ต้องรัน --schedule ตลอด — ให้ Android OS เรียกแทน)
    """
    import subprocess
    main_script = Path(__file__).parent / "termux_main.py"

    for name, pconfig in config.get("platforms", {}).items():
        if not pconfig.get("enabled", False):
            continue

        hours = pconfig.get("schedule_hours", 12)
        period_sec = hours * 3600

        cmd = [
            "termux-job-scheduler",
            "--script", str(main_script),
            "--script-args", f"--post --platform {name}",
            "--period-sec", str(period_sec),
        ]

        try:
            subprocess.run(cmd, check=True)
            print(f"✅ {name}: cron ตั้งแล้ว (ทุก {hours} ชม.)")
        except FileNotFoundError:
            print(f"⚠️ ไม่พบ termux-job-scheduler — ใช้ --schedule แทน")
            return False
        except Exception as e:
            print(f"❌ {name}: {e}")
            return False

    return True


if __name__ == "__main__":
    print("🧪 Scheduler Test")
    print("เรียกผ่าน termux_main.py --schedule")
