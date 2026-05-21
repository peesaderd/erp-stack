"""
Self-Reflection (Tom Agent) — ให้ Agent เข้าใจพฤติกรรมผู้ใช้และพัฒนาตัวเอง

เรียนรู้จากประวัติการสนทนา:
- ความชอบของผู้ใช้ (เช่น ชอบสั้น ชอบละเอียด)
- รูปแบบการทำงานที่เคยทำ
- ข้อผิดพลาดที่เคยเกิดขึ้น
- ปรับปรุงตัวเองจากผลลัพธ์ที่ผ่านมา
"""

import json
import os
import re
from datetime import datetime
from typing import Optional, Callable


class UserProfile:
    """โปรไฟล์ผู้ใช้ — เรียนรู้จากประวัติการสนทนา"""

    def __init__(self):
        self.preferences: dict[str, str] = {}  # ความชอบ
        self.patterns: list[str] = []  # รูปแบบที่สังเกตได้
        self.past_mistakes: list[str] = []  # ข้อผิดพลาดที่เคยเกิด
        self.known_topics: dict[str, str] = {}  # หัวข้อที่คุยแล้ว
        self.interaction_count: int = 0
        self.work_style: str = ""  # รูปแบบการทำงานที่ชอบ
        self.communication_style: str = ""  # รูปแบบการสื่อสาร
        self.avoid_topics: list[str] = []  # หัวข้อที่ควรหลีกเลี่ยง
        self.successful_patterns: list[str] = []  # รูปแบบที่เคยสำเร็จ

    def learn_from_history(self, history: list[dict]):
        """เรียนรู้จากประวัติการสนทนา"""
        self.interaction_count += 1

        for entry in history:
            content = entry.get("content", "")
            entry_type = entry.get("type", "")

            # เรียนรู้ความชอบจากคำพูดผู้ใช้
            if entry_type == "user":
                self._analyze_user_message(content)

            # เรียนรู้จากข้อผิดพลาด
            if entry_type == "error" or "error" in content.lower():
                self.past_mistakes.append(content[:100])

            # เรียนรู้จากความสำเร็จ (done + สรุป)
            if entry_type == "agent" and "✅" in content:
                self.successful_patterns.append(content[:150])

    def _analyze_user_message(self, message: str):
        """วิเคราะห์ข้อความผู้ใช้เพื่อหาความชอบ"""
        msg_lower = message.lower()

        # ความยาว
        if len(message) < 50:
            self.preferences["response_length"] = "short"
        elif len(message) > 500:
            self.preferences["response_length"] = "long"

        # รูปแบบ
        if "สั้น" in msg_lower or "สรุป" in msg_lower:
            self.preferences["style"] = "concise"
        if "ละเอียด" in msg_lower or "รายละเอียด" in msg_lower:
            self.preferences["style"] = "detailed"
        if "ตัวอย่าง" in msg_lower:
            self.preferences["include_examples"] = "true"

        # ภาษา
        if "ไทย" in message or "ภาษาไทย" in message:
            self.preferences["language"] = "thai"
        if "english" in msg_lower or "อังกฤษ" in msg_lower:
            self.preferences["language"] = "english"

        # รูปแบบการทำงาน
        if "deploy" in msg_lower or "รัน" in msg_lower or "ขึ้น" in msg_lower:
            self.work_style = "action-oriented"
        if "วางแผน" in msg_lower or "plan" in msg_lower or "roadmap" in msg_lower:
            self.work_style = "planning-oriented"
        if "ทดสอบ" in msg_lower or "test" in msg_lower:
            self.preferences["testing_first"] = "true"

        # หัวข้อที่คุย
        topics = [
            "erp", "odoo", "api", "database", "deploy", "docker",
            "frontend", "backend", "agent", "ai", "plugin", "gateway",
            "auth", "migration", "server", "voip", "appsheet",
        ]
        for topic in topics:
            if topic in msg_lower:
                self.known_topics[topic] = datetime.now().isoformat()

    def analyze_with_llm(self, history_summary: str, llm_fn: Optional[Callable] = None):
        """ใช้ LLM วิเคราะห์พฤติกรรมผู้ใช้เชิงลึก"""
        if not llm_fn:
            return

        prompt = f"""คุณคือ Tom Agent (Theory of Mind) — วิเคราะห์ผู้ใช้จากประวัติการสนทนา

ประวัติ:
{history_summary}

กรุณาตอบเป็น JSON เท่านั้น:
{{
  "work_style": "action-oriented | planning-oriented | mixed",
  "communication_style": " concise | detailed | mixed",
  "preferred_language": "thai | english | mixed",
  "avoid_topics": ["หัวข้อที่ควรหลีกเลี่ยง"],
  "key_insights": ["ข้อมูลเชิงลึกที่สำคัญ"],
  "suggested_approach": "วิธีเข้าหาผู้ใช้คนนี้"
}}

วิเคราะห์:
- ผู้ใช้คนนี้ชอบทำงานแบบไหน?
- อะไรที่ทำให้ผู้ใช้พอใจ?
- อะไรที่ควรระวัง?"""

        try:
            response = llm_fn(prompt)
            if response:
                # Extract JSON from response
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    if data.get("work_style"):
                        self.work_style = data["work_style"]
                    if data.get("communication_style"):
                        self.communication_style = data["communication_style"]
                    if data.get("avoid_topics"):
                        self.avoid_topics = data["avoid_topics"]
        except Exception:
            pass  # fallback ไปใช้ rule-based

    def get_system_prompt_extra(self) -> str:
        """สร้างส่วนเพิ่มของ system prompt จากสิ่งที่เรียนรู้"""
        parts = []

        if self.work_style:
            parts.append(f"รูปแบบการทำงาน: {self.work_style}")
        if self.communication_style:
            parts.append(f"รูปแบบการสื่อสาร: {self.communication_style}")

        if self.preferences:
            prefs = []
            for key, val in self.preferences.items():
                prefs.append(f"{key}={val}")
            parts.append(f"ความชอบ: {', '.join(prefs)}")

        if self.past_mistakes:
            recent = self.past_mistakes[-3:]
            parts.append(f"ข้อผิดพลาดที่เคยเกิด: {'; '.join(recent)}")

        if self.avoid_topics:
            parts.append(f"ควรหลีกเลี่ยง: {', '.join(self.avoid_topics)}")

        if self.known_topics:
            topics = list(self.known_topics.keys())
            parts.append(f"หัวข้อที่คุยแล้ว: {', '.join(topics)}")

        if self.successful_patterns:
            parts.append(f"รูปแบบที่เคยสำเร็จ: {self.successful_patterns[-1][:100]}")

        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "preferences": self.preferences,
            "patterns": self.patterns,
            "past_mistakes": self.past_mistakes,
            "known_topics": self.known_topics,
            "interaction_count": self.interaction_count,
            "work_style": self.work_style,
            "communication_style": self.communication_style,
            "avoid_topics": self.avoid_topics,
            "successful_patterns": self.successful_patterns,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        profile = cls()
        profile.preferences = data.get("preferences", {})
        profile.patterns = data.get("patterns", [])
        profile.past_mistakes = data.get("past_mistakes", [])
        profile.known_topics = data.get("known_topics", {})
        profile.interaction_count = data.get("interaction_count", 0)
        profile.work_style = data.get("work_style", "")
        profile.communication_style = data.get("communication_style", "")
        profile.avoid_topics = data.get("avoid_topics", [])
        profile.successful_patterns = data.get("successful_patterns", [])
        return profile


class SelfReflection:
    """ระบบ Self-Reflection — ให้ Agent พัฒนาตัวเองจากประวัติ"""

    def __init__(self, persistence_dir: str = "./.inner-monologue-memory"):
        self.persistence_dir = persistence_dir
        self.user_profile = UserProfile()
        self._llm_fn: Optional[Callable] = None
        self._load()

    def set_llm_fn(self, fn: Callable):
        """ตั้งค่า LLM function สำหรับวิเคราะห์เชิงลึก"""
        self._llm_fn = fn

    def reflect(self, history: list[dict]):
        """สะท้อนผลจากประวัติ และเรียนรู้"""
        self.user_profile.learn_from_history(history)
        self._save()

    def deep_reflect(self, history_summary: str):
        """วิเคราะห์เชิงลึกด้วย LLM"""
        if self._llm_fn:
            self.user_profile.analyze_with_llm(history_summary, self._llm_fn)
            self._save()

    def get_insights(self) -> str:
        """ดึงข้อมูลเชิงลึกที่ Agent ควรรู้"""
        return self.user_profile.get_system_prompt_extra()

    def _profile_path(self) -> str:
        return os.path.join(self.persistence_dir, "user_profile.json")

    def _save(self):
        path = self._profile_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.user_profile.to_dict(), f, ensure_ascii=False, indent=2)

    def _load(self):
        path = self._profile_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.user_profile = UserProfile.from_dict(data)
