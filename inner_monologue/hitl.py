"""
HITL (Human-in-the-Loop) แบบง่าย

ให้ Agent แจ้งสถานะและรอการยืนยันจากผู้ใช้เมื่อถึงจุดสำคัญ
"""

import os
from datetime import datetime
from typing import Optional


class HITL:
    """Human-in-the-Loop — แจ้งและรอการยืนยันจากผู้ใช้"""

    def __init__(self, workspace: str = "/workspace"):
        self.workspace = workspace
        self.flag_dir = os.path.join(workspace, ".hitl-flags")
        os.makedirs(self.flag_dir, exist_ok=True)

    def flag_ready_for_review(self, summary: str = ""):
        """สร้าง Flag File แจ้งว่างานเสร็จ พร้อมให้ตรวจสอบ"""
        content = f"""STATUS: READY_FOR_REVIEW
TIMESTAMP: {datetime.now().isoformat()}
SUMMARY: {summary}

หมายถึง: Agent ทำงานเสร็จแล้ว กรุณาตรวจสอบผลลัพธ์
"""
        path = os.path.join(self.flag_dir, "READY_FOR_REVIEW.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n  📋 สร้าง Flag: {path}")
        print(f"  {summary}\n")

    def flag_waiting_for_approval(self, action: str, reason: str = ""):
        """สร้าง Flag File แจ้งว่ารอการอนุมัติ"""
        content = f"""STATUS: WAITING_FOR_APPROVAL
TIMESTAMP: {datetime.now().isoformat()}
ACTION: {action}
REASON: {reason}

หมายถึง: Agent ต้องการการยืนยันก่อนดำเนินการต่อ
"""
        path = os.path.join(self.flag_dir, "WAITING_FOR_APPROVAL.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n  ⏳ รออนุมัติ: {action}")
        if reason:
            print(f"     เหตุผล: {reason}")
        print()

    def flag_in_progress(self, current_step: str):
        """สร้าง Flag File แจ้งว่ากำลังทำงาน"""
        content = f"""STATUS: IN_PROGRESS
TIMESTAMP: {datetime.now().isoformat()}
CURRENT_STEP: {current_step}
"""
        path = os.path.join(self.flag_dir, "STATUS.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def clear_flags(self):
        """ลบ Flag Files ทั้งหมด"""
        for f in os.listdir(self.flag_dir):
            os.remove(os.path.join(self.flag_dir, f))

    def check_approval(self) -> Optional[bool]:
        """ตรวจสอบว่าผู้ใช้อนุมัติหรือยัง (ดูจากไฟล์)"""
        approved_path = os.path.join(self.flag_dir, "APPROVED.txt")
        rejected_path = os.path.join(self.flag_dir, "REJECTED.txt")

        if os.path.exists(approved_path):
            return True
        if os.path.exists(rejected_path):
            return False
        return None  # ยังไม่ตอบ
