"""
Inner Monologue Agent — ตัวแทนที่มีกระบวนการคิดภายใน (Inner Monologue)
ใช้ ReAct Loop: Thought → Action → Observation
"""

import json
import os
import subprocess
import time
from typing import Optional

from .heartbeat import Heartbeat
from .memory import ConversationMemory
from .self_reflection import SelfReflection
from .hitl import HITL


class MockLLM:
    """LLM จำลองสำหรับทดสอบ — ไม่ต้องใช้ API จริง
    ตอบทีละขั้นตอนเพื่อให้เห็น ReAct Loop ครบวงจร
    จำ state ได้: รอบ 1 = think, รอบ 2 = act, รอบ 3 = done"""

    def __init__(self, responses: Optional[list[str]] = None):
        self.responses = responses or []
        self._idx = 0
        self._think_count = 0

    def completion(self, messages: list[dict], **kwargs) -> str:
        if self.responses:
            resp = self.responses[self._idx % len(self.responses)]
            self._idx += 1
            return resp

        prompt = messages[-1]["content"] if messages else ""

        # act prompt — ตอบ action
        if "terminal:" in prompt or "action ที่จะทำ" in prompt:
            return "⚡ ACTION: terminal: ls -la /workspace/"

        # done — คิดครบ 3 รอบแล้ว
        if self._think_count >= 3:
            return "✅ DONE: วิเคราะห์เสร็จสมบูรณ์"

        # think prompt
        self._think_count += 1
        thoughts = [
            "🧠 THOUGHT: ฉันควรสำรวจโครงสร้างโปรเจคก่อน เพื่อดูว่ามีอะไรบ้าง",
            "🧠 THOUGHT: ฉันเห็นโครงสร้างโปรเจคแล้ว ควรวิเคราะห์ว่าแต่ละส่วนคืออะไร",
            "🧠 THOUGHT: ฉันได้ข้อมูลครบแล้ว สามารถสรุปผลได้",
        ]
        return thoughts[min(self._think_count - 1, len(thoughts) - 1)]


class InnerMonologueAgent:
    """Agent ที่มี Inner Monologue — คิดก่อนทำ ดูผลก่อนคิดต่อ"""

    SYSTEM_PROMPT = """คุณคือ Inner Monologue Agent ที่มีกระบวนการคิดภายใน (Inner Monologue)

กฎการทำงาน:
1. คิดทบทวนก่อนลงมือทำทุกครั้ง
2. ใช้ขั้นตอน: คิด -> ทำ -> ดูผล -> คิดต่อ
3. เมื่อได้ข้อสรุปแล้ว ให้เขียน READY_FOR_REVIEW.txt
4. ถ้าต้องการข้อมูลเพิ่ม ให้ใช้ tools ที่มี

เครื่องมือที่มี:
- terminal: รันคำสั่ง bash
- file: อ่าน/เขียนไฟล์
- code: แก้ไขโค้ด

รูปแบบการตอบ:
🧠 THOUGHT: สิ่งที่กำลังคิด (ใช้ภาษาไทย)
⚡ ACTION: terminal: <คำสั่ง bash>
📊 OBSERVATION: ผลลัพธ์ที่ได้
✅ DONE: เมื่อเสร็จแล้ว

ข้อควรปฏิบัติ:
- คิดทีละขั้นตอน อย่าด่วนสรุป
- ตรวจสอบผลลัพธ์ทุกครั้งก่อนตัดสินใจ
- ถ้าผลลัพธ์ไม่ชัดเจน ให้รันคำสั่งเพิ่ม
- ใช้ภาษาไทยในการคิดและสรุป"""

    def __init__(
        self,
        llm_config: Optional[dict] = None,
        memory: Optional[ConversationMemory] = None,
        heartbeat: Optional[Heartbeat] = None,
        self_reflection: Optional[SelfReflection] = None,
        hitl: Optional[HITL] = None,
        workspace: str = "/workspace",
        mock: bool = False,
        mock_responses: Optional[list[str]] = None,
    ):
        self.llm_config = llm_config or {}
        self.memory = memory or ConversationMemory()
        self.heartbeat = heartbeat or Heartbeat()
        self.self_reflection = self_reflection or SelfReflection()
        self.hitl = hitl or HITL(workspace=workspace)
        self.workspace = workspace
        self.mock = mock

        self._llm = MockLLM(responses=mock_responses) if mock else None
        self._done = False
        self._history: list[dict] = []
        self._current_task = ""
        self._max_rounds = 50
        self._round = 0
        self._conversation_history: list[dict] = []  # สำหรับส่งให้ LLM

        # โหลดประวัติเก่า
        self.memory.load()

    # ──────────────────────────── Public API ────────────────────────────

    def run(self, task: str) -> str:
        """รัน Agent ตาม task ที่ได้รับ"""
        self._current_task = task
        self._done = False
        self._round = 0
        self._conversation_history = []

        self.heartbeat.start(task)
        self.hitl.clear_flags()
        self.hitl.flag_in_progress(f"เริ่มทำงาน: {task[:50]}")

        # เพิ่ม task ใน memory
        self.memory.add_entry("user", task)

        try:
            result = self._loop()
            self._done = True
            self.heartbeat.done(result)
            self.hitl.flag_ready_for_review(result)
            self.memory.add_entry("agent", f"✅ เสร็จ: {result}")
            self.memory.save()
            return result
        except Exception as e:
            self.heartbeat.error(str(e))
            self.memory.add_entry("error", str(e))
            self.memory.save()
            raise

    @property
    def is_done(self) -> bool:
        return self._done

    @property
    def get_history(self) -> list[dict]:
        return self._history

    # ──────────────────────────── Core Loop ────────────────────────────

    def _loop(self) -> str:
        """ReAct Loop หลัก — วนจนกว่าจะได้ข้อสรุป"""
        while self._round < self._max_rounds:
            self._round += 1

            # 1. THINK
            thought = self._think()
            self._history.append({"type": "thought", "content": thought, "round": self._round})
            self.memory.add_entry("thought", thought)
            self.heartbeat.beat("think", f"รอบที่ {self._round}", thought)

            # เช็คว่าคิดว่าเสร็จหรือยัง
            if "[DONE]" in thought or "✅" in thought or "READY_FOR_REVIEW" in thought:
                return self._finalize(thought)

            # 2. ACT
            action = self._act(thought)
            self._history.append({"type": "action", "content": action, "round": self._round})
            self.memory.add_entry("action", action)
            self.heartbeat.beat("act", action[:80])

            # 3. OBSERVE
            observation = self._observe(action)
            self._history.append({"type": "observation", "content": observation, "round": self._round})
            self.memory.add_entry("observation", observation)
            self.heartbeat.beat("observe", observation[:80])

            # อัปเดต Flag
            self.hitl.flag_in_progress(f"รอบ {self._round}: {thought[:50]}")

        # เกินรอบ
        summary = f"⚠️ เกิน {self._max_rounds} รอบแล้ว — หยุดการทำงาน"
        self.heartbeat.beat("done", summary)
        return self._finalize(summary)

    def _think(self) -> str:
        """คิด — เรียก LLM เพื่อหาว่าควรทำอะไรต่อ"""
        prompt = self._build_think_prompt()
        response = self._call_llm(prompt)
        return response.strip()

    def _act(self, thought: str) -> str:
        """ตัดสินใจ action จาก thought — ดึง action ที่จะทำออกมา"""
        prompt = self._build_act_prompt(thought)
        response = self._call_llm(prompt)
        # ตัด emoji prefix เฉพาะสำหรับ action (ไม่ตัด done)
        cleaned = self._clean_action(response)
        return cleaned or response.strip()

    def _clean_action(self, action: str) -> str:
        """ลบ emoji prefix และ label ต่างๆ ออกจาก action string"""
        import re
        # ลบ emoji + label เช่น "⚡ ACTION: ", "🧠 THOUGHT: ", "✅ DONE: "
        cleaned = re.sub(r'^[^\w\s]*\s*(?:ACTION|THOUGHT|DONE|OBSERVATION)?\s*:\s*', '', action.strip())
        # ถ้า cleaned ว่าง ให้ใช้ original
        return cleaned.strip() or action.strip()

    def _observe(self, action: str) -> str:
        """ดูผลลัพธ์ — รัน action และเก็บผล"""
        action = action.strip()
        cleaned = self._clean_action(action)

        # ตรวจสอบว่าเป็น action ประเภทไหน (ลองทั้ง original และ cleaned)
        for candidate in [cleaned, action]:
            if candidate.startswith("terminal:"):
                cmd = candidate[9:].strip()
                return self._run_terminal(cmd)
            elif candidate.startswith("file:"):
                file_action = candidate[5:].strip()
                return self._handle_file(file_action)
            elif candidate.startswith("code:"):
                code_action = candidate[5:].strip()
                return self._handle_code(code_action)
            elif candidate.startswith("done:") or candidate.startswith("[DONE]"):
                return candidate

        # ถ้าไม่ระบุ action type ให้ถือว่าเป็น terminal
        return self._run_terminal(cleaned)

    # ──────────────────────────── LLM Call ────────────────────────────

    def _call_llm(self, prompt: str) -> str:
        """เรียก LLM — รองรับทั้ง Mock, litellm, และ requests โดยตรง"""
        # Mock mode
        if self.mock and self._llm:
            messages = [{"role": "user", "content": prompt}]
            return self._llm.completion(messages)

        # litellm mode (แนะนำ)
        try:
            import litellm as _litellm
            return self._call_litellm(prompt)
        except ImportError:
            pass

        # Fallback: requests โดยตรง
        return self._call_requests(prompt)

    def _call_litellm(self, prompt: str) -> str:
        """เรียก LLM ผ่าน litellm — รองรับหลาย provider"""
        import litellm
        api_key = self.llm_config.get("api_key") or os.environ.get("MISTRAL_API_KEY")
        model = self.llm_config.get("model", "mistral/mistral-large-latest")

        # ถ้าไม่มี api_key ให้ใช้ mock
        if not api_key:
            return self._llm.completion([{"role": "user", "content": prompt}]) if self._llm else "Error: ไม่มี API key"

        # Mistral จุกจิกเรื่อง system prompt ถ้าใช้ role system ซ้อนกันหลายอัน
        # ใช้ system message เดียวรวม context
        system_context = self.SYSTEM_PROMPT
        context = self.memory.get_context(max_entries=10)
        if context:
            system_context += f"\n\n## บริบทจากประวัติ:\n{context}"

        messages = [{"role": "system", "content": system_context}]

        # เพิ่มประวัติล่าสุด
        for msg in self._conversation_history[-6:]:
            messages.append(msg)

        messages.append({"role": "user", "content": prompt})

        try:
            response = litellm.completion(
                model=model,
                messages=messages,
                max_tokens=2048,
                temperature=0.7,
                api_key=api_key,
            )
            content = response.choices[0].message.content

            self._conversation_history.append({"role": "user", "content": prompt})
            self._conversation_history.append({"role": "assistant", "content": content})

            return content
        except Exception as e:
            return f"Error เรียก LLM: {e}"

    def _call_requests(self, prompt: str) -> str:
        """Fallback: เรียก Mistral API ผ่าน requests โดยตรง"""
        import requests
        api_key = self.llm_config.get("api_key") or os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            return "Error: ไม่มี API key กรุณาตั้งค่า MISTRAL_API_KEY"

        model = self.llm_config.get("model", "mistral-large-latest")

        # รวม system prompt + context เป็นอันเดียว (Mistral จุกจิกเรื่อง system ซ้อน)
        system_context = self.SYSTEM_PROMPT
        context = self.memory.get_context(max_entries=10)
        if context:
            system_context += f"\n\n## บริบทจากประวัติ:\n{context}"

        messages = [{"role": "system", "content": system_context}]
        for msg in self._conversation_history[-6:]:
            messages.append(msg)
        messages.append({"role": "user", "content": prompt})

        try:
            resp = requests.post(
                "https://api.mistral.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": 2048,
                    "temperature": 0.7,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]

            self._conversation_history.append({"role": "user", "content": prompt})
            self._conversation_history.append({"role": "assistant", "content": content})

            return content
        except Exception as e:
            return f"Error เรียก API: {e}"

    # ──────────────────────────── Prompt Builder ────────────────────────────

    def _build_think_prompt(self) -> str:
        """สร้าง prompt สำหรับการคิด — รวมประวัติทั้งหมดให้ LLM เห็นบริบท"""
        parts = [f"## ภารกิจ: {self._current_task}\n"]

        # เพิ่ม insights จาก self-reflection
        insights = self.self_reflection.get_insights()
        if insights:
            parts.append(f"## สิ่งที่รู้เกี่ยวกับผู้ใช้:\n{insights}\n")

        # เพิ่มประวัติการทำงาน (history) เพื่อให้ LLM เห็นบริบท
        if self._history:
            history_lines = []
            for h in self._history[-6:]:  # 6 รอบล่าสุด
                t = h["type"]
                c = h["content"][:300]
                r = h["round"]
                history_lines.append(f"[รอบ {r}] {t.upper()}: {c}")
            parts.append("## ประวัติการทำงาน:\n" + "\n".join(history_lines) + "\n")

        parts.append("## ขั้นตอน:\n1. คิดทบทวนสถานการณ์ปัจจุบันจากประวัติ\n2. กำหนดว่าต้องทำอะไรต่อ\n3. ถ้าได้ข้อสรุปแล้ว ให้ขึ้นต้นด้วย [DONE]")

        return "\n".join(parts)

    def _build_act_prompt(self, thought: str) -> str:
        """สร้าง prompt สำหรับตัดสินใจ action — รวม observation ล่าสุด"""
        # หา observation ล่าสุด
        last_obs = ""
        for h in reversed(self._history):
            if h["type"] == "observation":
                last_obs = h["content"][:500]
                break

        prompt = f"""จากความคิดนี้: "{thought}"
"""
        if last_obs:
            prompt += f"""\nผลลัพธ์ล่าสุดที่ได้:\n{last_obs}\n"""

        prompt += """\nจงเลือก action ที่จะทำ โดยตอบในรูปแบบใดรูปแบบหนึ่งต่อไปนี้:
- terminal: <คำสั่ง bash>
- file: read <path> | write <path> | list <dir>
- code: <คำอธิบายการแก้ไขโค้ด>
- done: <สรุปผล>

ตัวอย่าง:
- terminal: ls -la /workspace/
- file: read /workspace/file.txt
- done: วิเคราะห์เสร็จแล้ว พบว่า..."""

        return prompt

    # ──────────────────────────── Tool Execution ────────────────────────────

    def _run_terminal(self, cmd: str) -> str:
        """รันคำสั่ง bash"""
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.workspace,
            )
            output = ""
            if result.stdout:
                output += result.stdout[:2000]
            if result.stderr:
                output += f"\n[STDERR]: {result.stderr[:500]}"
            if result.returncode != 0:
                output += f"\n[Exit code: {result.returncode}]"
            return output.strip() or "(ไม่มี output)"
        except subprocess.TimeoutExpired:
            return "Error: คำสั่งใช้เวลาเกิน 30 วินาที"
        except Exception as e:
            return f"Error รันคำสั่ง: {e}"

    def _handle_file(self, action: str) -> str:
        """จัดการกับ file action"""
        action = action.strip()
        if action.startswith("read "):
            path = action[5:].strip()
            full_path = os.path.join(self.workspace, path) if not path.startswith("/") else path
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    return f.read()[:2000]
            except FileNotFoundError:
                return f"Error: ไม่พบไฟล์ {path}"
            except Exception as e:
                return f"Error อ่านไฟล์: {e}"
        elif action.startswith("write "):
            # write: path\ncontent
            rest = action[6:].strip()
            if "\n" in rest:
                path, content = rest.split("\n", 1)
                path = path.strip()
                full_path = os.path.join(self.workspace, path) if not path.startswith("/") else path
                try:
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    return f"เขียนไฟล์ {path} สำเร็จ"
                except Exception as e:
                    return f"Error เขียนไฟล์: {e}"
            return "Error: รูปแบบไม่ถูกต้อง ใช้: write: path\\ncontent"
        elif action.startswith("list "):
            path = action[5:].strip()
            full_path = os.path.join(self.workspace, path) if not path.startswith("/") else path
            try:
                items = os.listdir(full_path)
                return "\n".join(sorted(items)[:50])
            except FileNotFoundError:
                return f"Error: ไม่พบ {path}"
            except Exception as e:
                return f"Error: {e}"
        return f"Error: ไม่รู้จัก file action: {action}"

    def _handle_code(self, action: str) -> str:
        """จัดการกับ code action — ปัจจุบันแค่บันทึกไว้"""
        return f"📝 Code action received: {action[:200]}"

    # ──────────────────────────── Finalize ────────────────────────────

    def _finalize(self, result: str) -> str:
        """สรุปผลและเขียน Flag File"""
        summary = result.replace("[DONE]", "").replace("✅", "").strip()

        # เขียน READY_FOR_REVIEW.txt
        ready_path = os.path.join(self.workspace, "READY_FOR_REVIEW.txt")
        try:
            with open(ready_path, "w", encoding="utf-8") as f:
                f.write(f"""STATUS: READY_FOR_REVIEW
TIMESTAMP: {time.strftime('%Y-%m-%d %H:%M:%S')}
TASK: {self._current_task}
SUMMARY: {summary}
ROUNDS: {self._round}
""")
        except Exception as e:
            pass

        # Self-reflection
        self.self_reflection.reflect(self._history)

        return summary
