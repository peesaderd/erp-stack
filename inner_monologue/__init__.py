"""
Inner Monologue — ระบบให้ AI Agent มีกระบวนการคิดภายใน (Inner Monologue)

Components:
- agent.py: Agent หลักที่มี ReAct Loop
- heartbeat.py: แสดงสถานะการทำงาน
- memory.py: Persistent Memory + Condenser
- self_reflection.py: Self-Reflection / Tom Agent
- hitl.py: Human-in-the-Loop แบบง่าย
- main.py: ตัวรันหลัก
"""

from .agent import InnerMonologueAgent
from .heartbeat import Heartbeat
from .memory import ConversationMemory
from .self_reflection import SelfReflection
from .hitl import HITL

__all__ = [
    "InnerMonologueAgent",
    "Heartbeat",
    "ConversationMemory",
    "SelfReflection",
    "HITL",
]
