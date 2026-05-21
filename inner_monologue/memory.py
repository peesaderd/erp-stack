"""
Memory — Persistent Memory + Condenser สำหรับ Inner Monologue Agent

ให้ Agent จำประวัติข้ามวัน และสรุปความจำเมื่อบทสนหายาวเกิน
"""

import json
import os
from datetime import datetime
from typing import Optional


class ConversationMemory:
    """บันทึกและโหลดประวัติการสนทนาทั้งหมด พร้อม Condenser"""

    def __init__(self, persistence_dir: str = "./.inner-monologue-memory"):
        self.persistence_dir = persistence_dir
        self.history: list[dict] = []
        self.summary: Optional[str] = None
        self.max_history_length = 50  # จำนวนประวัติสูงสุดก่อนสรุป
        os.makedirs(self.persistence_dir, exist_ok=True)

    def _history_path(self) -> str:
        return os.path.join(self.persistence_dir, "history.json")

    def _summary_path(self) -> str:
        return os.path.join(self.persistence_dir, "summary.txt")

    def add_entry(self, entry_type: str, content: str, metadata: Optional[dict] = None):
        """เพิ่มบันทึกใหม่ในประวัติ"""
        entry = {
            "type": entry_type,  # "thought", "action", "observation", "user", "agent"
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        self.history.append(entry)
        self._save()

        # ถ้าประวัติยาวเกิน → ทำ Condense
        if len(self.history) >= self.max_history_length:
            self.condense()

    def get_recent(self, n: int = 10) -> list[dict]:
        """ดึงประวัติล่าสุด n รายการ"""
        return self.history[-n:]

    def get_full_history(self) -> list[dict]:
        """ดึงประวัติทั้งหมด"""
        return self.history

    def get_context(self, max_entries: int = 20) -> str:
        """สร้าง context string สำหรับส่งให้ LLM"""
        parts = []

        # ถ้ามี summary ให้ใส่ก่อน
        if self.summary:
            parts.append(f"[สรุปความจำ]: {self.summary}\n")

        # เอาประวัติล่าสุด
        recent = self.get_recent(max_entries)
        for entry in recent:
            icon = {
                "thought": "🧠",
                "action": "⚡",
                "observation": "📊",
                "user": "👤",
                "agent": "🤖",
            }.get(entry["type"], "❓")
            parts.append(f"{icon} {entry['content']}")

        return "\n".join(parts)

    def condense(self):
        """สรุปประวัติเก่า (Condenser) — เก็บเฉพาะส่วนสำคัญ"""
        if not self.history:
            return

        # เก็บประวัติล่าสุด 10 รายการไว้
        keep = self.history[-10:]
        # ส่วนที่เหลือให้สรุป
        to_summarize = self.history[:-10]

        # สรุปแบบง่าย: ดึงเฉพาะ thought และ observation ที่สำคัญ
        key_points = []
        for entry in to_summarize:
            if entry["type"] in ("thought", "observation", "agent"):
                content = entry["content"]
                if len(content) > 50:
                    key_points.append(content[:80])

        old_summary = self.summary or ""
        new_summary = f"{old_summary}\n[รอบที่ผ่านมา]: {' | '.join(key_points[-10:])}"
        self.summary = new_summary.strip()

        # เก็บเฉพาะประวัติล่าสุด
        self.history = keep
        self._save()
        self._save_summary()

    def save(self):
        """บันทึกประวัติทั้งหมดลง disk"""
        self._save()
        if self.summary:
            self._save_summary()

    def _save(self):
        """บันทึกประวัติลงไฟล์"""
        path = self._history_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "history": self.history,
                    "summary": self.summary,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _save_summary(self):
        """บันทึก summary ลงไฟล์"""
        if self.summary:
            path = self._summary_path()
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.summary)

    def load(self):
        """โหลดประวัติจาก disk"""
        path = self._history_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.history = data.get("history", [])
                self.summary = data.get("summary")

        summary_path = self._summary_path()
        if os.path.exists(summary_path):
            with open(summary_path, "r", encoding="utf-8") as f:
                self.summary = f.read().strip()

    def clear(self):
        """ล้างประวัติทั้งหมด"""
        self.history = []
        self.summary = None
        if os.path.exists(self._history_path()):
            os.remove(self._history_path())
        if os.path.exists(self._summary_path()):
            os.remove(self._summary_path())

    @property
    def entry_count(self) -> int:
        return len(self.history)
