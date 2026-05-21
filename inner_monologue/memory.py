"""
Memory — Persistent Memory + Condenser สำหรับ Inner Monologue Agent

ให้ Agent จำประวัติข้ามวัน และสรุปความจำเมื่อบทสนหายาวเกิน
ใช้ LLM จริงในการ Condense (summarize) เพื่อให้ได้สรุปที่มีคุณภาพ
"""

import json
import os
import time
from datetime import datetime
from typing import Optional


class ConversationMemory:
    """บันทึกและโหลดประวัติการสนทนาทั้งหมด พร้อม Condenser แบบ LLM-based"""

    def __init__(self, persistence_dir: str = "./.inner-monologue-memory"):
        self.persistence_dir = persistence_dir
        self.history: list[dict] = []
        self.summary: Optional[str] = None
        self.max_history_length = 30  # จำนวนประวัติสูงสุดก่อนสรุป (ลดลงเพราะ LLM summarize)
        self._llm_condense_fn = None  # จะถูก set โดย Agent
        os.makedirs(self.persistence_dir, exist_ok=True)

    def set_condense_fn(self, fn):
        """ตั้งค่า function สำหรับเรียก LLM เพื่อ summarize"""
        self._llm_condense_fn = fn

    def _history_path(self) -> str:
        return os.path.join(self.persistence_dir, "history.json")

    def _summary_path(self) -> str:
        return os.path.join(self.persistence_dir, "summary.txt")

    def add_entry(self, entry_type: str, content: str, metadata: Optional[dict] = None):
        """เพิ่มบันทึกใหม่ในประวัติ"""
        entry = {
            "type": entry_type,  # "thought", "action", "observation", "user", "agent", "error"
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

    def get_context(self, max_entries: int = 15) -> str:
        """สร้าง context string สำหรับส่งให้ LLM
        - ถ้ามี summary ให้ใส่ก่อน
        - ตามด้วยประวัติล่าสุด
        - รวมข้อผิดพลาดที่เคยเจอ"""
        parts = []

        # ถ้ามี summary ให้ใส่ก่อน
        if self.summary:
            parts.append(f"[สรุปความจำจากรอบก่อน]: {self.summary}\n")

        # เอาประวัติล่าสุด
        recent = self.get_recent(max_entries)
        if recent:
            parts.append("[ประวัติล่าสุด]:")
            for entry in recent:
                icon = {
                    "thought": "🧠",
                    "action": "⚡",
                    "observation": "📊",
                    "user": "👤",
                    "agent": "🤖",
                    "error": "❌",
                }.get(entry["type"], "❓")
                # ตัด content ให้สั้นลง
                content = entry["content"]
                if len(content) > 150:
                    content = content[:150] + "..."
                parts.append(f"  {icon} [{entry['type']}] {content}")

        return "\n".join(parts)

    def condense(self):
        """สรุปประวัติเก่า (Condenser) — ใช้ LLM ถ้ามี ไม่ก็ fallback วิธีเดิม"""
        if not self.history:
            return

        # เก็บประวัติล่าสุด 10 รายการไว้
        keep = self.history[-10:]
        # ส่วนที่เหลือให้สรุป
        to_summarize = self.history[:-10]

        # ถ้ามี LLM condense function ให้ใช้
        if self._llm_condense_fn:
            try:
                self._condense_via_llm(to_summarize)
                self.history = keep
                self._save()
                self._save_summary()
                return
            except Exception:
                pass  # fallback ไปวิธีเดิม

        # Fallback: สรุปแบบง่าย
        key_points = []
        for entry in to_summarize:
            if entry["type"] in ("thought", "observation", "agent", "error"):
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

    def _condense_via_llm(self, to_summarize: list[dict]):
        """ใช้ LLM สรุปประวัติ — พร้อม post-processing ตัด raw output"""
        # สร้างข้อความที่จะให้ summarize
        entries_text = []
        for entry in to_summarize:
            t = entry["type"]
            c = entry["content"]
            if len(c) > 200:
                c = c[:200] + "..."
            entries_text.append(f"[{t}] {c}")

        history_text = "\n".join(entries_text)
        old_summary = self.summary or "ไม่มี"

        prompt = f"""คุณคือ Condenser Agent มีหน้าที่สรุปประวัติการทำงานให้สั้นได้ใจความ

ประวัติเดิม:
{old_summary}

ประวัติใหม่ที่ต้องสรุป:
{history_text}

คำสั่ง:
1. อ่านประวัติใหม่
2. สรุปเฉพาะใจความสำคัญ เป็นภาษาไทย สั้น กระชับ 3-5 บรรทัด
3. รูปแบบ:
   ✅ สิ่งที่ทำไปแล้ว: ...
   ⚠️ ปัญหาที่เจอ: ... (ถ้ามี)
   📋 สิ่งที่ต้องทำต่อ: ...
4. ห้ามใส่ raw log, ห้ามใส่ JSON, ห้ามใส่ code
5. ตอบเฉพาะสรุปเท่านั้น ไม่มีคำนำหรือคำลงท้าย"""

        response = self._llm_condense_fn(prompt)
        if not response:
            raise ValueError("LLM returned empty summary")

        # Post-processing: ตัด raw output ที่อาจปนมา
        cleaned = self._clean_summary(response.strip())
        self.summary = cleaned

    def _clean_summary(self, text: str) -> str:
        """Post-processing: ตัด JSON, code blocks, raw log ที่อาจปนมากับ summary"""
        import re

        # ตัด ``` blocks
        text = re.sub(r'```[\s\S]*?```', '', text)

        # ตัด JSON objects
        text = re.sub(r'\{[^}]*\}', '', text)

        # ตัดบรรทัดที่ขึ้นต้นด้วย [thought], [action], [observation] (raw log)
        text = re.sub(r'(?m)^\s*\[(thought|action|observation|user|agent|error)\].*$', '', text)

        # ตัดบรรทัดที่ขึ้นต้นด้วย {"type": (JSON remnant)
        text = re.sub(r'(?m)^\s*\{".*$', '', text)

        # ลบบรรทัดว่างซ้ำ
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

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
