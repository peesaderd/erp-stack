"""
HITL (Human-in-the-Loop) — Confirmation Mode + Flag Files + Callbacks

ให้ Agent:
1. แจ้งสถานะตลอดการทำงาน (IN_PROGRESS, READY_FOR_REVIEW)
2. รอการอนุมัติก่อนทำ destructive actions (WAITING_FOR_APPROVAL)
3. ผู้ใช้ตอบกลับผ่านไฟล์ (APPROVED.txt / REJECTED.txt)
4. ส่ง callback แจ้งเตือนเมื่อรออนุมัติ
"""

import os
import time
import json
from datetime import datetime
from typing import Optional, Callable


# ─── Confirmation Levels ────────────────────────────────────────────────

CONFIRMATION_LEVELS = {
    "none": {
        "description": "ไม่ต้องยืนยัน — ทำได้เลย",
        "actions": [],
    },
    "destructive": {
        "description": "ยืนยันเฉพาะ action ที่อาจเสียหาย",
        "actions": [
            "deploy",
            "delete_file",
            "overwrite_file",
            "git_push",
            "git_force_push",
            "db_drop",
            "db_migrate",
            "restart_service",
            "stop_service",
            "format_disk",
            "chmod_critical",
            "rm_critical",
        ],
    },
    "all": {
        "description": "ยืนยันทุก action",
        "actions": ["*"],  # wildcard = ทุก action
    },
}

# Action types ที่ถือว่า destructive (ต้องยืนยัน)
DESTRUCTIVE_ACTIONS = {
    "deploy": "deploy ขึ้น production",
    "delete_file": "ลบไฟล์",
    "overwrite_file": "เขียนทับไฟล์ที่มีอยู่",
    "git_push": "git push (อาจกระทบ remote)",
    "git_force_push": "git push --force (อันตราย)",
    "db_drop": "ลบ table/database",
    "db_migrate": "รัน database migration",
    "restart_service": "restart service",
    "stop_service": "stop service",
    "rm_critical": "rm -rf หรือลบ path สำคัญ",
}


class HITL:
    """Human-in-the-Loop — แจ้งและรอการยืนยันจากผู้ใช้
    รองรับ Confirmation Mode และ Callback"""

    def __init__(
        self,
        workspace: str = "/workspace",
        confirmation_level: str = "destructive",
        callback: Optional[Callable] = None,
    ):
        self.workspace = workspace
        self.flag_dir = os.path.join(workspace, ".hitl-flags")
        self.callback = callback
        os.makedirs(self.flag_dir, exist_ok=True)

        # ตั้งค่า confirmation level
        self.confirmation_level = confirmation_level
        self._pending_actions: dict[str, str] = {}  # action_id -> description

    # ─── Public API ───────────────────────────────────────────────────

    def set_confirmation_level(self, level: str):
        """เปลี่ยนระดับการยืนยัน: none | destructive | all"""
        if level in CONFIRMATION_LEVELS:
            self.confirmation_level = level

    def needs_confirmation(self, action_type: str, action_detail: str = "") -> bool:
        """ตรวจสอบว่า action นี้ต้องยืนยันหรือไม่
        ตรวจสอบทั้ง action_type และ action_detail (ตัวคำสั่งจริง)
        """
        level_config = CONFIRMATION_LEVELS.get(self.confirmation_level, CONFIRMATION_LEVELS["destructive"])

        if "*" in level_config["actions"]:
            return True  # all mode

        action_lower = action_type.lower()
        detail_lower = action_detail.lower()

        # ตรวจสอบว่า action นี้ตรงกับ destructive list หรือไม่
        for destructive_key in level_config["actions"]:
            if destructive_key in action_lower or destructive_key in detail_lower:
                return True

        # ตรวจสอบ destructive patterns เพิ่มเติมสำหรับ terminal commands
        destructive_patterns = [
            "rm -rf", "rm -r", "rm -f", "rm --recursive",
            "dd ", "mkfs", "format", "fdisk",
            "git push --force", "git push -f",
            "drop table", "drop database", "truncate",
            "kill -9", "pkill",
            "chmod 777", "chmod -R",
            "shutdown", "reboot", "poweroff",
            "> /dev/", "> /dev/sd",
            "docker rm", "docker rmi", "docker system prune",
            "pip uninstall", "apt remove", "apt purge",
            "npm uninstall", "npm cache clean",
            "mv /", "cp -r /",
        ]
        for pattern in destructive_patterns:
            if pattern in detail_lower:
                return True

        return False

    def request_confirmation(self, action_type: str, action_detail: str, timeout: int = 300) -> bool:
        """ขออนุมัติจากผู้ใช้ — คืนค่า True ถ้าอนุมัติ, False ถ้าปฏิเสธ

        Args:
            action_type: ประเภท action (deploy, delete_file, ฯลฯ)
            action_detail: รายละเอียดของ action
            timeout: เวลารอสูงสุด (วินาที) — default 5 นาที

        Returns:
            bool: True = อนุมัติ, False = ปฏิเสธ หรือ timeout
        """
        action_id = f"{action_type}_{int(time.time())}"
        self._pending_actions[action_id] = action_detail

        # สร้าง flag WAITING_FOR_APPROVAL
        self.flag_waiting_for_approval(action_type, action_detail, action_id)

        # ส่ง callback ถ้ามี
        if self.callback:
            try:
                self.callback("waiting_for_approval", {
                    "action_id": action_id,
                    "action": action_type,
                    "detail": action_detail,
                    "timeout": timeout,
                })
            except Exception:
                pass

        # รอการตอบกลับ (polling)
        start_time = time.time()
        while time.time() - start_time < timeout:
            approval = self.check_approval(action_id)
            if approval is True:
                self._cleanup_approval(action_id)
                return True
            elif approval is False:
                self._cleanup_approval(action_id)
                return False
            time.sleep(2)  # poll ทุก 2 วินาที

        # timeout
        self._cleanup_approval(action_id)
        return False

    def check_approval(self, action_id: str = "") -> Optional[bool]:
        """ตรวจสอบว่าผู้ใช้อนุมัติหรือยัง

        Args:
            action_id: ถ้าระบุ จะตรวจสอบเฉพาะ action นั้น

        Returns:
            True = อนุมัติ, False = ปฏิเสธ, None = ยังไม่ตอบ
        """
        # ถ้ามี action_id ให้ดูไฟล์เฉพาะ
        if action_id:
            approved_path = os.path.join(self.flag_dir, f"APPROVED_{action_id}.txt")
            rejected_path = os.path.join(self.flag_dir, f"REJECTED_{action_id}.txt")
            if os.path.exists(approved_path):
                return True
            if os.path.exists(rejected_path):
                return False
            return None

        # ถ้าไม่มี action_id ดูไฟล์ทั่วไป
        approved_path = os.path.join(self.flag_dir, "APPROVED.txt")
        rejected_path = os.path.join(self.flag_dir, "REJECTED.txt")
        if os.path.exists(approved_path):
            return True
        if os.path.exists(rejected_path):
            return False
        return None

    # ─── Flag Files ───────────────────────────────────────────────────

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

        if self.callback:
            try:
                self.callback("ready_for_review", {"summary": summary})
            except Exception:
                pass

    def flag_waiting_for_approval(self, action: str, reason: str = "", action_id: str = ""):
        """สร้าง Flag File แจ้งว่ารอการอนุมัติ"""
        aid = action_id or f"{action}_{int(time.time())}"
        content = f"""STATUS: WAITING_FOR_APPROVAL
TIMESTAMP: {datetime.now().isoformat()}
ACTION_ID: {aid}
ACTION: {action}
REASON: {reason}

หมายถึง: Agent ต้องการการยืนยันก่อนดำเนินการต่อ

วิธีตอบ:
- อนุมัติ: สร้างไฟล์ APPROVED_{aid}.txt ใน {self.flag_dir}/
- ปฏิเสธ: สร้างไฟล์ REJECTED_{aid}.txt ใน {self.flag_dir}/
"""
        path = os.path.join(self.flag_dir, f"WAITING_FOR_APPROVAL_{aid}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n  ⏳ รออนุมัติ: {action}")
        if reason:
            print(f"     เหตุผล: {reason}")
        print(f"     Action ID: {aid}")
        print(f"     ดูได้ที่: {path}")
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
            try:
                os.remove(os.path.join(self.flag_dir, f))
            except Exception:
                pass

    # ─── Internal ─────────────────────────────────────────────────────

    def _cleanup_approval(self, action_id: str):
        """ลบไฟล์ที่เกี่ยวข้องกับ action_id"""
        self._pending_actions.pop(action_id, None)
        for prefix in ["WAITING_FOR_APPROVAL_", "APPROVED_", "REJECTED_"]:
            path = os.path.join(self.flag_dir, f"{prefix}{action_id}.txt")
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

    def get_pending_actions(self) -> dict:
        """รายการ action ที่รออนุมัติ"""
        return dict(self._pending_actions)
