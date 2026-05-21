"""
Main — ตัวรัน Inner Monologue Agent

วิธีใช้:
  python -m inner_monologue.main "วิเคราะห์ ERP เราเทียบ Odoo"
  python -m inner_monologue.main --task "ช่วยเขียน Docs" --model mistral-large-2411
"""

import argparse
import json
import os
import sys
import time

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
    parser.add_argument("--wait", action="store_true", help="รันแบบ daemon รอรับ task จาก .agent-tasks/")
    parser.add_argument("--task-dir", default="./.agent-tasks", help="directory ที่ใช้รับ task (ใช้กับ --wait)")

    args = parser.parse_args()

    # API key — ตรวจสอบตาม model ที่เลือก
    model = args.model
    if "deepseek" in model:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key and not args.mock:
            print("❌ กรุณาตั้งค่า DEEPSEEK_API_KEY ใน environment variable")
            print("   export DEEPSEEK_API_KEY='your-key-here'")
            sys.exit(1)
    elif "groq" in model:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key and not args.mock:
            print("❌ กรุณาตั้งค่า GROQ_API_KEY ใน environment variable")
            print("   export GROQ_API_KEY='your-key-here'")
            sys.exit(1)
    else:
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

    # HITL callback — แจ้งผู้ใช้เมื่อรออนุมัติ
    def _on_hitl(event: str, data: dict):
        """เมื่อ Agent รอการอนุมัติ ให้แจ้งผู้ใช้"""
        if event == "waiting_for_approval":
            action = data.get("action", "")
            reason = data.get("reason", "")
            print(f"\n  ⏳ HITL: {action}")
            print(f"     เหตุผล: {reason}")
            print(f"     ตรวจสอบได้ที่: {os.path.join(args.workspace, '.hitl-flags', 'WAITING_FOR_APPROVAL.txt')}")
            print()

    # สร้าง Agent
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
        hitl_callback=_on_hitl,
    )

    # ──── --wait mode: daemon รอรับ task ────
    if args.wait:
        task_dir = os.path.abspath(args.task_dir)
        result_dir = os.path.join(task_dir, "..", ".agent-results")
        os.makedirs(task_dir, exist_ok=True)
        os.makedirs(result_dir, exist_ok=True)
        print(f"\n  🧠 Agent Daemon เริ่มทำงานแล้ว")
        print(f"  📥 รอรับ task ที่: {task_dir}/")
        print(f"  📤 ผลลัพธ์จะอยู่ที่: {result_dir}/")
        print(f"  ⏹ กด Ctrl+C เพื่อหยุด\n")

        processed = set()
        while True:
            try:
                # หาไฟล์ task ใหม่ (เฉพาะ .json ที่ยังไม่เคยประมวลผล)
                tasks = [f for f in os.listdir(task_dir) if f.endswith(".json")]
                new_tasks = [f for f in tasks if f not in processed]

                for task_file in new_tasks:
                    task_path = os.path.join(task_dir, task_file)
                    try:
                        with open(task_path, "r", encoding="utf-8") as f:
                            task_data = json.load(f)
                        task_content = task_data.get("task", "")
                        task_id = task_data.get("id", task_file.replace(".json", ""))

                        print(f"\n  📥 ได้รับ task: {task_id}")
                        print(f"     {task_content[:100]}")

                        # รัน Agent
                        result = agent.run(task_content)

                        # เขียนผลลัพธ์
                        result_path = os.path.join(result_dir, f"{task_id}.json")
                        with open(result_path, "w", encoding="utf-8") as f:
                            json.dump({
                                "id": task_id,
                                "task": task_content,
                                "result": result,
                                "status": "done",
                                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                            }, f, ensure_ascii=False, indent=2)

                        print(f"  📤 ผลลัพธ์: {result_path}")
                    except json.JSONDecodeError:
                        print(f"  ❌ task {task_file} JSON ไม่ถูกต้อง")
                    except Exception as e:
                        print(f"  ❌ task {task_file} error: {e}")
                    finally:
                        # ลบ task file ทิ้ง
                        try:
                            os.remove(task_path)
                        except Exception:
                            pass
                        processed.add(task_file)

                # เก็บเฉพาะ 100 ล่าสุด (ไม่ให้ memory ล้น)
                if len(processed) > 100:
                    processed = set(list(processed)[-50:])

                time.sleep(1)
            except KeyboardInterrupt:
                print("\n\n  ⏹ หยุด Agent Daemon")
                sys.exit(0)

    # ──── ปกติ: รัน task เดียวแล้วจบ ────
    if not args.task:
        parser.print_help()
        print("\n❌ ระบุ task ด้วย เช่น:")
        print('   python -m inner_monologue.main "วิเคราะห์ ERP"')
        print('   หรือใช้ --wait เพื่อรันแบบ daemon')
        sys.exit(1)

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
