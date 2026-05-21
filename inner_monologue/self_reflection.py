"""
Self-Reflection (Tom Agent) — ให้ Agent เข้าใจพฤติกรรมผู้ใช้และพัฒนาตัวเอง

เรียนรู้จากประวัติการสนทนา:
- ความชอบของผู้ใช้ (เช่น ชอบสั้น ชอบละเอียด)
- รูปแบบการทำงานที่เคยทำ
- ข้อผิดพลาดที่เคยเกิดขึ้น
"""

import json
import os
from datetime import datetime
from typing import Optional


class UserProfile:
    """โปรไฟล์ผู้ใช้ — เรียนรู้จากประวัติการสนทนา"""

    def __init__(self):
        self.preferences: dict[str, str] = {}  # ความชอบ
        self.patterns: list[str] = []  # รูปแบบที่สังเกตได้
        self.past_mistakes: list[str] = []  # ข้อผิดพลาดที่เคยเกิด
        self.known_topics: dict[str, str] = {}  # หัวข้อที่คุยแล้ว
        self.interaction_count: int = 0

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

        # หัวข้อที่คุย
        topics = ["erp", "odoo", "api", "database", "deploy", "docker", "frontend", "backend"]
        for topic in topics:
            if topic in msg_lower:
                self.known_topics[topic] = datetime.now().isoformat()

    def get_system_prompt_extra(self) -> str:
        """สร้างส่วนเพิ่มของ system prompt จากสิ่งที่เรียนรู้"""
        parts = []

        if self.preferences:
            prefs = []
            for key, val in self.preferences.items():
                prefs.append(f"{key}={val}")
            parts.append(f"ผู้ใช้มีความชอบ: {', '.join(prefs)}")

        if self.past_mistakes:
            recent = self.past_mistakes[-3:]
            parts.append(f"ข้อผิดพลาดที่เคยเกิด: {'; '.join(recent)}")

        if self.known_topics:
            topics = list(self.known_topics.keys())
            parts.append(f"หัวข้อที่คุยแล้ว: {', '.join(topics)}")

        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "preferences": self.preferences,
            "patterns": self.patterns,
            "past_mistakes": self.past_mistakes,
            "known_topics": self.known_topics,
            "interaction_count": self.interaction_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        profile = cls()
        profile.preferences = data.get("preferences", {})
        profile.patterns = data.get("patterns", [])
        profile.past_mistakes = data.get("past_mistakes", [])
        profile.known_topics = data.get("known_topics", {})
        profile.interaction_count = data.get("interaction_count", 0)
        return profile


class SelfReflection:
    """ระบบ Self-Reflection — ให้ Agent พัฒนาตัวเองจากประวัติ"""

    def __init__(self, persistence_dir: str = "./.inner-monologue-memory"):
        self.persistence_dir = persistence_dir
        self.user_profile = UserProfile()
        self._load()

    def reflect(self, history: list[dict]):
        """สะท้อนผลจากประวัติ และเรียนรู้"""
        self.user_profile.learn_from_history(history)
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
