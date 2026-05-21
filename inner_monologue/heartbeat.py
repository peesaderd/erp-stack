"""
Heartbeat — แสดงสถานะของ Agent ทุกรอบ
"""

from datetime import datetime
from typing import Optional


class Heartbeat:
    """แสดงสถานะการทำงานของ Agent แบบ Real-time"""

    ICONS = {
        "think": "🧠",
        "act": "⚡",
        "observe": "📊",
        "done": "✅",
        "error": "❌",
        "waiting": "⏳",
        "info": "ℹ️",
    }

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.round = 0
        self.start_time: Optional[datetime] = None

    def start(self, task: str):
        """เริ่มนับเวลาและแสดง Task ที่ได้รับ"""
        self.start_time = datetime.now()
        self.round = 0
        print(f"\n{'='*60}")
        print(f"  🧠 INNER MONOLOGUE AGENT")
        print(f"  Task: {task}")
        print(f"  Started: {self.start_time.strftime('%H:%M:%S')}")
        print(f"{'='*60}\n")

    def beat(self, status: str, message: str, detail: str = ""):
        """ส่งสัญญาณ heartbeat หนึ่งครั้ง"""
        self.round += 1
        icon = self.ICONS.get(status, "❓")
        elapsed = ""
        if self.start_time:
            delta = datetime.now() - self.start_time
            elapsed = f" [+{delta.seconds}s]"

        if self.verbose:
            print(f"  [{icon}] รอบที่ {self.round}{elapsed}")
            print(f"       {message}")
            if detail:
                # แสดงรายละเอียดเฉพาะบรรทัดแรก ถ้ายาวเกิน
                first_line = detail.strip().split("\n")[0]
                if len(first_line) > 100:
                    first_line = first_line[:100] + "..."
                print(f"       {first_line}")
            print()
        else:
            # โหมดสั้น: แสดงเฉพาะไอคอน + ข้อความสั้น
            short_msg = message[:60] + "..." if len(message) > 60 else message
            print(f"  {icon} [{self.round}] {short_msg}")

    def done(self, summary: str = ""):
        """แสดงว่า Agent ทำงานเสร็จ"""
        elapsed = ""
        if self.start_time:
            delta = datetime.now() - self.start_time
            elapsed = f" (ใช้เวลา {delta.seconds} วินาที)"

        print(f"\n{'='*60}")
        print(f"  ✅ งานเสร็จ{elapsed}")
        if summary:
            print(f"  {summary}")
        print(f"{'='*60}\n")

    def error(self, err_msg: str):
        """แสดง Error"""
        print(f"\n  ❌ ERROR: {err_msg}\n")
