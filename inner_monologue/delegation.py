"""
Multi-Agent Delegation System — Sub-Agent Manager + Delegate Protocol

ให้ Agent หลักสามารถสร้าง Sub-Agent เพื่อทำงานเฉพาะทาง และรวบรวมผลลัพธ์กลับมา

## Protocol

### Task Spec (JSON):
{
    "id": "uuid",
    "type": "file | search | code | analyze | custom",
    "task": "คำอธิบายงาน",
    "context": {"optional": "context"},
    "timeout": 60,
    "priority": "high | normal | low"
}

### Result Spec (JSON):
{
    "id": "uuid",
    "status": "done | error | timeout | stuck",
    "result": "ผลลัพธ์",
    "summary": "สรุปสั้น",
    "rounds": 5,
    "error": "optional error message"
}
"""

import json
import os
import time
import uuid
import threading
from datetime import datetime
from typing import Optional, Callable

from .heartbeat import Heartbeat
from .memory import ConversationMemory
from .resilience import StuckDetector


# ─── Sub-Agent Types ────────────────────────────────────────────────────

SUB_AGENT_TYPES = {
    "file": {
        "name": "FileAgent",
        "description": "จัดการไฟล์ — อ่าน, เขียน, แก้ไข, ค้นหา",
        "capabilities": ["read", "write", "edit", "search", "list"],
    },
    "search": {
        "name": "SearchAgent",
        "description": "ค้นหาข้อมูลใน codebase — grep, find, วิเคราะห์โครงสร้าง",
        "capabilities": ["grep", "find", "analyze", "stats"],
    },
    "code": {
        "name": "CodeAgent",
        "description": "เขียนและแก้ไขโค้ด — สร้างไฟล์, refactor, lint",
        "capabilities": ["generate", "refactor", "lint", "format"],
    },
    "analyze": {
        "name": "AnalyzeAgent",
        "description": "วิเคราะห์และวางแผน — เปรียบเทียบ, หาจุดอ่อน, เสนอแนะ",
        "capabilities": ["compare", "audit", "plan", "recommend"],
    },
    "test": {
        "name": "TestAgent",
        "description": "รันทดสอบ — pytest, ตรวจสอบ coverage, debug",
        "capabilities": ["run", "coverage", "debug", "assert"],
    },
}


# ─── Sub-Agent Result ───────────────────────────────────────────────────

class SubAgentResult:
    """ผลลัพธ์จาก Sub-Agent"""

    def __init__(
        self,
        task_id: str,
        agent_type: str,
        status: str = "pending",
        result: str = "",
        summary: str = "",
        rounds: int = 0,
        error: str = "",
    ):
        self.task_id = task_id
        self.agent_type = agent_type
        self.status = status  # pending | running | done | error | timeout | stuck
        self.result = result
        self.summary = summary
        self.rounds = rounds
        self.error = error
        self.created_at = datetime.now().isoformat()
        self.completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "agent_type": self.agent_type,
            "status": self.status,
            "result": self.result,
            "summary": self.summary,
            "rounds": self.rounds,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SubAgentResult":
        r = cls(
            task_id=data["task_id"],
            agent_type=data["agent_type"],
            status=data.get("status", "done"),
            result=data.get("result", ""),
            summary=data.get("summary", ""),
            rounds=data.get("rounds", 0),
            error=data.get("error", ""),
        )
        r.created_at = data.get("created_at", r.created_at)
        r.completed_at = data.get("completed_at")
        return r


# ─── Sub-Agent Base ─────────────────────────────────────────────────────

class SubAgent:
    """Base class สำหรับ Sub-Agent — มี ReAct Loop เบาๆ ของตัวเอง
    พร้อม Condenser + Self-Reflection ในตัว"""

    def __init__(
        self,
        agent_type: str,
        llm_call_fn: Callable,
        workspace: str = "/workspace",
        heartbeat: Optional[Heartbeat] = None,
        memory: Optional[ConversationMemory] = None,
    ):
        self.agent_type = agent_type
        self.llm_call_fn = llm_call_fn  # function สำหรับเรียก LLM
        self.workspace = workspace
        self.heartbeat = heartbeat or Heartbeat(verbose=False)
        self.memory = memory or ConversationMemory(
            persistence_dir=f"./.sub-agent-memory/{agent_type}"
        )
        # ให้ Sub-Agent มี Self-Reflection ของตัวเอง
        from .self_reflection import SelfReflection
        self.self_reflection = SelfReflection(
            persistence_dir=f"./.sub-agent-memory/{agent_type}"
        )
        # เชื่อม LLM ให้ Self-Reflection
        self.self_reflection.set_llm_fn(llm_call_fn)
        self.stuck_detector = StuckDetector(
            same_action_threshold=3,
            same_thought_threshold=3,
            no_progress_rounds=6,
            max_consecutive_errors=4,
        )
        self._history: list[dict] = []
        # โหลดประวัติเก่า
        self.memory.load()

    def run(self, task: str, context: Optional[dict] = None) -> SubAgentResult:
        """รัน Sub-Agent ตาม task ที่ได้รับ — คืนค่า SubAgentResult
        พร้อมบันทึก memory + self-reflection"""
        task_id = str(uuid.uuid4())
        result = SubAgentResult(
            task_id=task_id,
            agent_type=self.agent_type,
            status="running",
        )

        self.heartbeat.start(f"[{self.agent_type}] {task[:80]}")
        self.stuck_detector.reset()
        self._history = []

        # บันทึก task ใน memory
        self.memory.add_entry("user", f"[{self.agent_type}] {task}")

        try:
            # Simple ReAct loop — ไม่เกิน 15 รอบ (Sub-Agent ไม่ต้องคิดลึก)
            max_rounds = 15
            for round_num in range(1, max_rounds + 1):
                # Think
                thought = self._think(task, context)
                if not thought:
                    continue

                self._history.append({"type": "thought", "content": thought, "round": round_num})
                self.memory.add_entry("thought", thought)
                self.heartbeat.beat("think", f"รอบ {round_num}", thought)

                # Act
                action = self._act(thought)
                if not action:
                    continue

                action_type = action.get("action_type", "")
                action_content = action.get("content", "")

                if action_type == "done":
                    result.status = "done"
                    result.result = action_content
                    result.summary = action.get("summary", action_content[:200])
                    result.rounds = round_num
                    self.memory.add_entry("agent", f"✅ เสร็จ: {result.summary}")
                    break

                self.memory.add_entry("action", f"{action_type}: {action_content[:100]}")

                # Stuck detection
                stuck = self.stuck_detector.check(
                    round_num, thought, action_type, action_content, is_error=False
                )
                if stuck:
                    result.status = "stuck"
                    result.result = f"ติดลูป: {stuck['reason']}"
                    result.summary = result.result
                    result.rounds = round_num
                    self.memory.add_entry("error", f"ติดลูป: {stuck['reason']}")
                    break

                # Observe
                observation = self._observe(action_type, action_content)
                self._history.append({"type": "observation", "content": observation, "round": round_num})
                self.memory.add_entry("observation", observation[:200])
                self.heartbeat.beat("observe", observation[:80])

            else:
                # เกิน max_rounds
                result.status = "timeout"
                result.result = f"เกิน {max_rounds} รอบ"
                result.summary = result.result
                self.memory.add_entry("error", f"timeout: เกิน {max_rounds} รอบ")

        except Exception as e:
            result.status = "error"
            result.error = str(e)
            result.result = f"Error: {e}"
            self.memory.add_entry("error", str(e))
            self.heartbeat.error(str(e))

        # Self-reflection หลังจากทำงานเสร็จ
        self.self_reflection.reflect(self._history)
        memory_context = self.memory.get_context(max_entries=5)
        if memory_context:
            self.self_reflection.deep_reflect(memory_context)

        # บันทึก memory
        self.memory.save()

        result.completed_at = datetime.now().isoformat()
        self.heartbeat.done(result.summary)
        return result

    def _think(self, task: str, context: Optional[dict] = None) -> Optional[str]:
        """คิด — คืนค่า thought content หรือ None ถ้า LLM ตอบ done (จบงาน)"""
        prompt = self._build_think_prompt(task, context)
        try:
            response = self.llm_call_fn(prompt)
            data = self._parse_simple_json(response)
            if data:
                if data.get("type") == "thought":
                    return data.get("content", "")
                if data.get("type") == "done":
                    # LLM ตอบ done ในรอบคิด — ให้ act จัดการ
                    return "__DONE__:" + data.get("content", "เสร็จ")
            return response[:200]
        except Exception:
            return None

    def _act(self, thought: str) -> Optional[dict]:
        """ตัดสินใจ action — คืนค่า action dict หรือ done dict"""
        # ถ้า _think ส่งสัญญาณ done มา
        if thought.startswith("__DONE__:"):
            content = thought[len("__DONE__:"):]
            return {"type": "done", "action_type": "done", "content": content, "summary": content}

        prompt = self._build_act_prompt(thought)
        try:
            response = self.llm_call_fn(prompt)
            data = self._parse_simple_json(response)
            if data:
                if data.get("type") == "action":
                    return data
                if data.get("type") == "done":
                    return {"type": "done", "action_type": "done", **{k: v for k, v in data.items() if k != "type"}}
            return None
        except Exception:
            return None

    def _observe(self, action_type: str, action_content: str) -> str:
        """execute action — ใช้ tools พื้นฐาน"""
        import subprocess

        if action_type == "terminal":
            try:
                result = subprocess.run(
                    action_content,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=self.workspace,
                )
                output = ""
                if result.stdout:
                    output += result.stdout[:1500]
                if result.stderr:
                    output += f"\n[STDERR]: {result.stderr[:300]}"
                if result.returncode != 0:
                    output += f"\n[Exit code: {result.returncode}]"
                return output.strip() or "(ไม่มี output)"
            except subprocess.TimeoutExpired:
                return "Error: คำสั่งใช้เวลาเกิน 30 วินาที"
            except Exception as e:
                return f"Error: {e}"

        elif action_type == "file":
            return self._handle_file(action_content)

        return f"Action type '{action_type}' ไม่รองรับใน Sub-Agent"

    def _handle_file(self, action: str) -> str:
        """จัดการ file action"""
        action = action.strip()
        if action.startswith("read:") or action.startswith("read "):
            prefix = "read:" if action.startswith("read:") else "read "
            path = action[len(prefix):].strip()
            full_path = os.path.join(self.workspace, path) if not path.startswith("/") else path
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    return f.read()[:2000]
            except FileNotFoundError:
                return f"Error: ไม่พบไฟล์ {path}"
            except Exception as e:
                return f"Error: {e}"

        elif action.startswith("list:") or action.startswith("list "):
            prefix = "list:" if action.startswith("list:") else "list "
            path = action[len(prefix):].strip()
            full_path = os.path.join(self.workspace, path) if not path.startswith("/") else path
            try:
                items = os.listdir(full_path)
                return "\n".join(sorted(items)[:50])
            except Exception as e:
                return f"Error: {e}"

        return f"ไม่รู้จัก file action: {action}"

    def _build_system_context(self) -> str:
        """สร้าง system context รวม memory + self-reflection insights"""
        parts = []

        # ความจำจากรอบก่อน
        memory_context = self.memory.get_context(max_entries=5)
        if memory_context:
            parts.append(f"## ความจำ:\n{memory_context}")

        # Insights จาก self-reflection
        insights = self.self_reflection.get_insights()
        if insights:
            parts.append(f"## สิ่งที่รู้:\n{insights}")

        return "\n\n".join(parts)

    def _build_think_prompt(self, task: str, context: Optional[dict] = None) -> str:
        """สร้าง prompt สำหรับคิด — override ใน Sub-Agent เฉพาะทาง"""
        ctx = ""
        if context:
            ctx = f"\n## Context:\n{json.dumps(context, indent=2, ensure_ascii=False)}\n"

        system = self._build_system_context()
        system_section = f"\n{system}\n" if system else ""

        return f"""คุณคือ {SUB_AGENT_TYPES.get(self.agent_type, {}).get('name', 'Sub-Agent')} — ผู้เชี่ยวชาญด้าน {SUB_AGENT_TYPES.get(self.agent_type, {}).get('description', 'ทั่วไป')}
{system_section}
## ภารกิจ:
{task}
{ctx}
## คำสั่ง:
- คิดสั้นๆ 1-2 ประโยค ภาษาไทย
- ตอบเป็น JSON: {{"type": "thought", "content": "..."}}
- OUTPUT ONLY JSON"""

    def _build_act_prompt(self, thought: str) -> str:
        """สร้าง prompt สำหรับ action"""
        return f"""จากความคิด: "{thought}"

เลือก action ที่เหมาะสม:
- terminal: คำสั่ง bash
- file: read: path หรือ list: path
- done: งานเสร็จแล้ว พร้อมสรุป

## เงื่อนไข:
- ถ้าได้ข้อมูลครบแล้ว → done ทันที
- ถ้าสำรวจไป 2-3 รอบแล้ว → done สรุปผล
- งานง่าย (list, read) → done หลังจาก execute รอบเดียว

ตอบเป็น JSON:
{{"type": "action", "action_type": "terminal|file|done", "content": "..."}}
หรือ
{{"type": "done", "content": "สรุป", "summary": "รายละเอียด"}}

OUTPUT ONLY JSON"""

    def _parse_simple_json(self, text: str) -> Optional[dict]:
        """parse JSON อย่างง่าย"""
        import re
        if not text:
            return None
        # ลองหา ```json ... ```
        m = re.search(r'```(?:json)?\s*\n?(\{.*?\})\s*```', text, re.DOTALL)
        if m:
            text = m.group(1)
        # ลองหา { ... }
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            text = m.group(0)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None


# ─── Sub-Agent Registry ─────────────────────────────────────────────────

class SubAgentRegistry:
    """ลงทะเบียนและสร้าง Sub-Agent ตามประเภท"""

    def __init__(self):
        self._agents: dict[str, type] = {}

    def register(self, agent_type: str, agent_class: type):
        """ลงทะเบียน Sub-Agent type"""
        self._agents[agent_type] = agent_class

    def create(
        self,
        agent_type: str,
        llm_call_fn: Callable,
        workspace: str = "/workspace",
    ) -> Optional[SubAgent]:
        """สร้าง Sub-Agent ตามประเภท"""
        agent_class = self._agents.get(agent_type)
        if not agent_class:
            return None
        return agent_class(
            agent_type=agent_type,
            llm_call_fn=llm_call_fn,
            workspace=workspace,
        )

    def list_types(self) -> list[dict]:
        """รายการ Sub-Agent ที่ลงทะเบียน"""
        return [
            {"type": t, **SUB_AGENT_TYPES.get(t, {})}
            for t in self._agents
        ]


# ─── SubAgentManager ────────────────────────────────────────────────────

class SubAgentManager:
    """จัดการ Sub-Agent ทั้งหมด — สร้าง, รัน, ติดตามผล"""

    def __init__(
        self,
        llm_call_fn: Callable,
        workspace: str = "/workspace",
        max_concurrent: int = 3,
    ):
        self.registry = SubAgentRegistry()
        self.llm_call_fn = llm_call_fn
        self.workspace = workspace
        self.max_concurrent = max_concurrent
        self._results: dict[str, SubAgentResult] = {}
        self._running: dict[str, threading.Thread] = {}

        # ลงทะเบียน Sub-Agent พื้นฐาน
        self._register_defaults()

    def _register_defaults(self):
        """ลงทะเบียน Sub-Agent ชนิดต่างๆ"""
        # ใช้ SubAgent เป็น default สำหรับทุก type
        # เฉพาะทางสามารถสร้าง subclass แล้ว register ทับได้
        for agent_type in SUB_AGENT_TYPES:
            self.registry.register(agent_type, SubAgent)

    def register_agent(self, agent_type: str, agent_class: type):
        """ลงทะเบียน Sub-Agent เพิ่มเติม"""
        self.registry.register(agent_type, agent_class)

    def delegate(
        self,
        agent_type: str,
        task: str,
        context: Optional[dict] = None,
        timeout: int = 120,
        wait: bool = True,
    ) -> SubAgentResult:
        """มอบหมายงานให้ Sub-Agent

        Args:
            agent_type: ประเภท Sub-Agent (file, search, code, analyze, test)
            task: งานที่ต้องการให้ทำ
            context: ข้อมูลเพิ่มเติม
            timeout: เวลาสูงสุด (วินาที)
            wait: True = รอผล, False = ส่งไปแล้วคืนทันที

        Returns:
            SubAgentResult
        """
        agent = self.registry.create(agent_type, self.llm_call_fn, self.workspace)
        if not agent:
            return SubAgentResult(
                task_id=str(uuid.uuid4()),
                agent_type=agent_type,
                status="error",
                error=f"ไม่รู้จัก Sub-Agent type: {agent_type}",
                result=f"ไม่มี Sub-Agent สำหรับ {agent_type}",
            )

        if wait:
            # รอผล
            result = agent.run(task, context)
            self._results[result.task_id] = result
            return result
        else:
            # ส่งไป background
            task_id = str(uuid.uuid4())
            result = SubAgentResult(
                task_id=task_id,
                agent_type=agent_type,
                status="running",
            )
            self._results[task_id] = result

            def _run():
                try:
                    r = agent.run(task, context)
                    self._results[task_id] = r
                except Exception as e:
                    self._results[task_id] = SubAgentResult(
                        task_id=task_id,
                        agent_type=agent_type,
                        status="error",
                        error=str(e),
                    )

            t = threading.Thread(target=_run, daemon=True)
            self._running[task_id] = t
            t.start()
            return result

    def get_result(self, task_id: str) -> Optional[SubAgentResult]:
        """ตรวจสอบผลลัพธ์ของ task"""
        return self._results.get(task_id)

    def wait_for_result(self, task_id: str, timeout: float = 60.0) -> Optional[SubAgentResult]:
        """รอผลลัพธ์ของ task (ใช้กับ async)"""
        thread = self._running.get(task_id)
        if thread:
            thread.join(timeout=timeout)
        return self._results.get(task_id)

    def get_all_results(self, status: Optional[str] = None) -> list[SubAgentResult]:
        """รายการผลลัพธ์ทั้งหมด"""
        results = list(self._results.values())
        if status:
            results = [r for r in results if r.status == status]
        return results

    def list_agents(self) -> list[dict]:
        """รายการ Sub-Agent ที่พร้อมใช้งาน"""
        return self.registry.list_types()

    def clear_results(self):
        """ล้างผลลัพธ์เก่า"""
        self._results.clear()
        self._running.clear()


# ─── DelegateTool — สำหรับใช้ใน Agent Loop ──────────────────────────────

DELEGATE_SYSTEM_INSTRUCTION = """
## Delegation Tool — มอบหมายงานให้ Sub-Agent

คุณสามารถมอบหมายงานเฉพาะทางให้ Sub-Agent ได้ โดยใช้ action type "delegate"

รูปแบบ:
{
    "type": "action",
    "action_type": "delegate",
    "content": "ประเภท Sub-Agent | งานที่ต้องการให้ทำ"
}

ประเภท Sub-Agent ที่มี:
- file: จัดการไฟล์ — อ่าน, เขียน, แก้ไข, ค้นหา
- search: ค้นหาข้อมูลใน codebase — grep, find, วิเคราะห์โครงสร้าง
- code: เขียนและแก้ไขโค้ด — สร้างไฟล์, refactor
- analyze: วิเคราะห์และวางแผน — เปรียบเทียบ, หาจุดอ่อน
- test: รันทดสอบ — pytest, ตรวจสอบ coverage

ตัวอย่าง:
{
    "type": "action",
    "action_type": "delegate",
    "content": "search | หาไฟล์ทั้งหมดที่เกี่ยวกับ 'payment' ใน erp-modular/"
}

{
    "type": "action",
    "action_type": "delegate",
    "content": "analyze | วิเคราะห์โครงสร้าง API ใน erp-modular/api/ และแนะนำการปรับปรุง"
}

เมื่อ Sub-Agent ทำงานเสร็จ ผลลัพธ์จะกลับมาให้คุณดำเนินการต่อ
"""


def setup_delegation(agent, llm_call_fn: Callable, workspace: str = "/workspace"):
    """ตั้งค่า Delegation system ให้ Agent — เพิ่ม SubAgentManager และ delegate handler

    Args:
        agent: InnerMonologueAgent instance
        llm_call_fn: function สำหรับเรียก LLM (ใช้ _call_llm_for_condense หรือ _call_llm)
        workspace: working directory
    """
    manager = SubAgentManager(
        llm_call_fn=llm_call_fn,
        workspace=workspace,
    )
    agent.sub_agent_manager = manager

    # เพิ่ม delegate action ใน _observe
    original_observe = agent._observe

    def observe_with_delegate(action_type: str, action_content: str) -> str:
        if action_type == "delegate":
            return _handle_delegate(manager, action_content)
        return original_observe(action_type, action_content)

    agent._observe = observe_with_delegate

    # เพิ่ม delegate instruction ใน system prompt
    original_build = agent._build_system_context

    def build_with_delegate():
        return original_build() + DELEGATE_SYSTEM_INSTRUCTION

    agent._build_system_context = build_with_delegate

    return manager


def _handle_delegate(manager: SubAgentManager, content: str) -> str:
    """จัดการ delegate action — รูปแบบ: "type | task description" """
    content = content.strip()

    if "|" not in content:
        return "Error: รูปแบบไม่ถูกต้อง ใช้: delegate: type | task description"

    parts = content.split("|", 1)
    agent_type = parts[0].strip()
    task = parts[1].strip()

    if not agent_type or not task:
        return "Error: ต้องระบุทั้งประเภท Sub-Agent และงาน"

    # รัน Sub-Agent (รอผล)
    result = manager.delegate(agent_type, task, wait=True)

    # สร้างรายงาน
    report = f"""📋 Sub-Agent [{agent_type}] ผลลัพธ์:
  สถานะ: {result.status}
  สรุป: {result.summary}
  จำนวนรอบ: {result.rounds}
"""
    if result.status == "done":
        report += f"\n{result.result[:1000]}"
    if result.error:
        report += f"\n  ❌ Error: {result.error}"

    return report
