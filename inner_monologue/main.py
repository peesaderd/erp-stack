"""
Main — ตัวรัน Inner Monologue Agent

วิธีใช้:
  python -m inner_monologue.main "วิเคราะห์ ERP เราเทียบ Odoo"
  python -m inner_monologue.main --task "ช่วยเขียน Docs" --model mistral-large-2411
"""

import argparse
import os
import sys

from .agent import InnerMonologueAgent
from .heartbeat import Heartbeat
from .memory import ConversationMemory
from .self_reflection import SelfReflection
from .hitl import HITL


def main():
    parser = argparse.ArgumentParser(description="Inner Monologue Agent")
    parser.add_argument("task", nargs="?", default="", help="ภารกิจที่ให้ Agent ทำ")
    parser.add_argument("--model", default="mistral/mistral-large-2411", help="Model name (ใช้ litellm format)")
    parser.add_argument("--workspace", default="/workspace", help="Working directory")
    parser.add_argument("--memory-dir", default="./.inner-monologue-memory", help="ที่เก็บประวัติ")
    parser.add_argument("--verbose", action="store_true", default=True, help="แสดงผลละเอียด")
    parser.add_argument("--quiet", action="store_true", help="แสดงผลน้อยลง")
    parser.add_argument("--mock", action="store_true", help="ใช้ Mock LLM (ไม่ต้องใช้ API)")
    parser.add_argument("--list-history", action="store_true", help="ดูประวัติที่มีอยู่")
    parser.add_argument("--clear-memory", action="store_true", help="ล้างประวัติทั้งหมด")

    args = parser.parse_args()

    # API key — ไม่บังคับถ้าใช้ mock
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key and not args.mock:
        print("❌ กรุณาตั้งค่า MISTRAL_API_KEY ใน environment variable")
        print("   export MISTRAL_API_KEY='your-key-here'")
        print("   หรือใช้ --mock เพื่อทดสอบโดยไม่ต้องใช้ API")
        sys.exit(1)

    # สร้าง components
    memory = ConversationMemory(persistence_dir=args.memory_dir)
    heartbeat = Heartbeat(verbose=not args.quiet)
    self_reflection = SelfReflection(persistence_dir=args.memory_dir)
    hitl = HITL(workspace=args.workspace)

    # ดูประวัติ
    if args.list_history:
        memory.load()
        history = memory.get_full_history()
        print(f"\n📚 ประวัติทั้งหมด ({len(history)} รายการ):\n")
        for i, entry in enumerate(history[-20:], 1):
            icon = {
                "thought": "🧠",
                "action": "⚡",
                "observation": "📊",
                "user": "👤",
                "agent": "🤖",
                "error": "❌",
            }.get(entry["type"], "❓")
            content = entry["content"][:100]
            print(f"  {i}. {icon} [{entry['type']}] {content}")
        if memory.summary:
            print(f"\n📝 สรุปความจำ:\n{memory.summary}")
        return

    # ล้างประวัติ
    if args.clear_memory:
        memory.clear()
        print("✅ ล้างประวัติเรียบร้อย")
        return

    # ตรวจสอบว่ามี task หรือไม่
    if not args.task:
        parser.print_help()
        print("\n❌ ระบุ task ด้วย เช่น:")
        print('   python -m inner_monologue.main "วิเคราะห์ ERP"')
        sys.exit(1)

    # สร้าง Agent และรัน
    agent = InnerMonologueAgent(
        llm_config={
            "api_key": api_key,
            "model": args.model,
        },
        memory=memory,
        heartbeat=heartbeat,
        self_reflection=self_reflection,
        hitl=hitl,
        workspace=args.workspace,
        mock=args.mock,
    )

    try:
        result = agent.run(args.task)
        print(f"\n📋 ผลลัพธ์:\n{result}\n")
    except KeyboardInterrupt:
        print("\n\n⏹ หยุดการทำงานโดยผู้ใช้")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ เกิดข้อผิดพลาด: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
