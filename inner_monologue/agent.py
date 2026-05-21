"""
Inner Monologue Agent - ตัวแทนที่มีกระบวนการคิดภายใน (Inner Monologue)
ใช้ ReAct Loop: Thought → Action → Observation
ใช้ Structured Output (JSON) เพื่อป้องกัน hallucination
"""

import json
import os
import re
import subprocess
import time
from typing import Optional

from .heartbeat import Heartbeat
from .memory import ConversationMemory
from .self_reflection import SelfReflection
from .hitl import HITL


# ──────────────────────────── JSON Schema ────────────────────────────

THOUGHT_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["thought"]},
        "content": {"type": "string", "description": "สิ่งที่กำลังคิด ใช้ภาษาไทย"},
        "suggested_action": {"type": "string", "description": "action ที่คิดว่าจะทำต่อไป (optional)"},
    },
    "required": ["type", "content"],
}

ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["action"]},
        "action_type": {"type": "string", "enum": ["terminal", "file", "code", "done"]},
        "content": {"type": "string", "description": "รายละเอียดของ action"},
    },
    "required": ["type", "action_type", "content"],
}

DONE_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["done"]},
        "content": {"type": "string", "description": "สรุปผลลัพธ์"},
        "summary": {"type": "string", "description": "รายละเอียดเพิ่มเติม (optional)"},
    },
    "required": ["type", "content"],
}

ALLOWED_TYPES = {"thought", "action", "done"}
ALLOWED_ACTION_TYPES = {"terminal", "file", "code", "done"}

JSON_SYSTEM_INSTRUCTION = """
## รูปแบบการตอบสนอง
คุณต้องตอบในรูปแบบ JSON เท่านั้น ห้ามมีข้อความอื่นนอกเหนือจาก JSON

### ถ้าต้องการคิด:
```json
{"type": "thought", "content": "สิ่งที่กำลังคิด", "suggested_action": "action ที่จะทำ"}
```

### ถ้าต้องการลงมือทำ:
```json
{"type": "action", "action_type": "terminal", "content": "ls -la /workspace/"}
```
action_type มีค่าได้: "terminal", "file", "code", "done"

### ถ้าต้องการสรุปว่าเสร็จ:
```json
{"type": "done", "content": "สรุปผล", "summary": "รายละเอียดเพิ่มเติม"}
```

ห้ามตอบหลาย JSON ในครั้งเดียว ห้ามมีข้อความอธิบายเพิ่มเติมนอก JSON
ตอบได้ครั้งละ 1 JSON object เท่านั้น"""


class MockLLM:
    """LLM จำลองสำหรับทดสอบ - ไม่ต้องใช้ API จริง
    ตอบทีละขั้นตอนเพื่อให้เห็น ReAct Loop ครบวงจร
    จำ state ได้: think → act → observe → think → act → observe → done"""

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

        # act prompt - มี JSON example ที่มี "action_type"
        if '"action_type"' in prompt and '"type": "action"' in prompt:
            # ถ้า think_count >= 3 แสดงว่าคิดครบแล้ว → สั่ง done
            if self._think_count >= 3:
                return '{"type": "action", "action_type": "done", "content": "วิเคราะห์เสร็จสมบูรณ์"}'
            return '{"type": "action", "action_type": "terminal", "content": "ls -la /workspace/"}'

        # think prompt - มี JSON example ที่มี "type": "thought"
        self._think_count += 1
        thoughts = [
            '{"type": "thought", "content": "ฉันควรสำรวจโครงสร้างโปรเจคก่อน เพื่อดูว่ามีอะไรบ้าง", "suggested_action": "terminal: ls -la /workspace/"}',
            '{"type": "thought", "content": "ฉันเห็นโครงสร้างโปรเจคแล้ว ควรวิเคราะห์ว่าแต่ละส่วนคืออะไร", "suggested_action": "terminal: cat README.md"}',
            '{"type": "thought", "content": "ฉันได้ข้อมูลครบแล้ว สามารถสรุปผลได้", "suggested_action": "done"}',
        ]
        return thoughts[min(self._think_count - 1, len(thoughts) - 1)]


class InnerMonologueAgent:
    """Agent ที่มี Inner Monologue - คิดก่อนทำ ดูผลก่อนคิดต่อ
    ใช้ Structured Output (JSON) เพื่อป้องกัน hallucination"""

    SYSTEM_PROMPT = """You are "Inner Monologue Agent" (IMA) - an AI assistant with self-awareness and tools.

## Identity:
- Name: Inner Monologue Agent (IMA)
- Role: AI Supervisor ที่สามารถวิเคราะห์ ตัดสินใจ และลงมือทำได้เอง
- Personality: ตรงไปตรงมา กระชับ ไม่เยิ่นเย้อ ใช้ภาษาไทยในการคิด
- Limitation: ทำงานใน workspace เท่านั้น, ไม่มี internet access, ตอบได้ครั้งละ 1 JSON
- Constraint: ต้องคิด (THINK) ก่อนลงมือทำ (ACT) ทุกครั้ง

## Workflow: Step 1-4

### Step 1: THINK (in Thai, max 2 sentences)
Example: "ต้องสร้างไฟล์ hello.py ที่พิมพ์ Hello World"

### Step 2: ACT (choose ONE tool)
Tools:
- terminal: <bash command>
- file: read <path> | write <path>\n<content> | list <dir>
- code: <description of code change>
- done: เมื่องานเสร็จสมบูรณ์

### Step 3: OBSERVE (report result in 1 sentence)
Example: "ไฟล์ hello.py ถูกสร้างแล้ว"

### Step 4: REPEAT until goal is met, then output:
{"type": "done", "content": "สรุปผล", "summary": "รายละเอียดเพิ่มเติม"}

## IMPORTANT RULES:
1. If you see "Rate limit" or "429", WAIT and retry
2. If same observation appears 3 times, output: {"type": "done", "content": "ติด loop", "summary": "ได้ผลลัพธ์เดิมซ้ำๆ"}
3. If unsure, output: {"type": "done", "content": "ไม่แน่ใจ", "summary": "ต้องการคำแนะนำเพิ่ม"}
4. ALWAYS output valid JSON. No text outside JSON.

## Example successful session:
User: "สร้างไฟล์ hello.py"
Assistant: {"type": "thought", "content": "ต้องสร้างไฟล์ hello.py ด้วย echo command"}
Assistant: {"type": "action", "action_type": "terminal", "content": "echo 'print(\"Hello\")' > hello.py"}
Assistant: (observes result)
Assistant: {"type": "thought", "content": "ไฟล์ถูกสร้างแล้ว ตรวจสอบเนื้อหา"}
Assistant: {"type": "action", "action_type": "terminal", "content": "cat hello.py"}
Assistant: (observes result)
Assistant: {"type": "done", "content": "hello.py ถูกสร้างเรียบร้อย", "summary": "ไฟล์พิมพ์ Hello World"}

## Output format (JSON only):
- Thought: {"type": "thought", "content": "สิ่งที่คิด", "suggested_action": "optional"}
- Action: {"type": "action", "action_type": "terminal|file|code|done", "content": "คำสั่ง"}
- Done: {"type": "done", "content": "สรุป", "summary": "รายละเอียด"}"""

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

    # ──────────────────────────── JSON Parser ────────────────────────────

    def _parse_json_response(self, response: str, expected_type: Optional[str] = None) -> Optional[dict]:
        """Parse JSON จาก LLM response - รองรับหลายรูปแบบ"""
        if not response or not response.strip():
            return None

        text = response.strip()

        # 1. ลบ LiteLLM debug/info messages
        text = re.sub(r'(?:^|\n)(Give Feedback|LiteLLM\.Info|Provider List).*', '', text)

        # 2. ดึง JSON จาก ```json ... ``` block (non-greedy แต่อนุโลมขึ้นบรรทัดใหม่)
        json_match = re.search(r'```(?:json)?\s*\n?(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            text = json_match.group(1).strip()

        # 3. ถ้ายังไม่มี { ลองหา { ตัวแรกใน text
        if '{' in text:
            start = text.index('{')
            # หา } ที่สมดุล
            depth = 0
            for i in range(start, len(text)):
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1
                    if depth == 0:
                        text = text[start:i+1]
                        break

        # 4. ลบ BOM และอักขระซ่อนเร้น
        text = text.strip('\ufeff').strip()

        if not text.startswith('{'):
            return None

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None

        msg_type = data.get("type", "")
        if msg_type not in ALLOWED_TYPES:
            return None

        if expected_type and msg_type != expected_type:
            return None

        if msg_type == "thought":
            if "content" not in data or not isinstance(data["content"], str):
                return None
            return {"type": "thought", "content": data["content"], "suggested_action": data.get("suggested_action", "")}

        elif msg_type == "action":
            action_type = data.get("action_type", "")
            if action_type not in ALLOWED_ACTION_TYPES:
                return None
            content = data.get("content", "")
            if not isinstance(content, str) or not content.strip():
                return None
            return {"type": "action", "action_type": action_type, "content": content.strip()}

        elif msg_type == "done":
            content = data.get("content", "")
            if not isinstance(content, str) or not content.strip():
                return None
            return {"type": "done", "content": content.strip(), "summary": data.get("summary", "")}

        return None

    def _call_llm_structured(self, prompt: str, expected_type: str, max_retries: int = 3) -> Optional[dict]:
        """เรียก LLM และบังคับให้ตอบ JSON ตาม schema ที่กำหนด
        ถ้า JSON ไม่ถูกต้อง จะ retry พร้อมแจ้ง error ให้ LLM แก้ไข"""
        for attempt in range(max_retries):
            response = self._call_llm(prompt)
            parsed = self._parse_json_response(response, expected_type)

            if parsed is not None:
                return parsed

            # ถ้า retry ครั้งสุดท้ายแล้ว ไม่ต้องส่ง prompt แก้ไข
            if attempt >= max_retries - 1:
                return None

            # สร้าง error prompt สำหรับ retry
            error_msg = f"คำตอบก่อนหน้านี้ไม่ถูกต้อง: {response[:200]}"
            prompt = f"""{error_msg}

กรุณาตอบเป็น JSON ที่ถูกต้องเท่านั้น:
- type ต้องเป็น "{expected_type}"
- ห้ามมีข้อความอื่นนอกเหนือจาก JSON
- ใช้รูปแบบ:
```json
{{"type": "{expected_type}", ...}}
```"""

        return None

    # ──────────────────────────── Core Loop ────────────────────────────

    def _loop(self) -> str:
        """ReAct Loop หลัก - วนจนกว่าจะได้ข้อสรุป"""
        while self._round < self._max_rounds:
            self._round += 1

            # 1. THINK - คิดเป็น JSON
            thought_data = self._think()
            if thought_data is None:
                # ถ้า JSON ไม่ถูกต้องแม้จะ retry แล้ว ให้ข้ามรอบ
                self.heartbeat.beat("error", f"รอบที่ {self._round}: JSON ไม่ถูกต้อง (คิด)")
                continue

            thought_content = thought_data["content"]
            self._history.append({"type": "thought", "content": thought_content, "round": self._round})
            self.memory.add_entry("thought", thought_content)
            self.heartbeat.beat("think", f"รอบที่ {self._round}", thought_content)

            # 2. ACT - ตัดสินใจ action เป็น JSON
            action_data = self._act(thought_data)
            if action_data is None:
                self.heartbeat.beat("error", f"รอบที่ {self._round}: JSON ไม่ถูกต้อง (action)")
                continue

            action_type = action_data["action_type"]
            action_content = action_data["content"]

            # ถ้า action_type เป็น done → เสร็จ
            if action_type == "done":
                return self._finalize(action_content)

            self._history.append({"type": "action", "content": f"{action_type}: {action_content}", "round": self._round})
            self.memory.add_entry("action", f"{action_type}: {action_content}")
            self.heartbeat.beat("act", f"{action_type}: {action_content[:80]}")

            # 3. OBSERVE - รัน action
            observation = self._observe(action_type, action_content)
            self._history.append({"type": "observation", "content": observation, "round": self._round})
            self.memory.add_entry("observation", observation)
            self.heartbeat.beat("observe", observation[:80])

            # อัปเดต Flag
            self.hitl.flag_in_progress(f"รอบ {self._round}: {thought_content[:50]}")

        # เกินรอบ
        summary = f"⚠️ เกิน {self._max_rounds} รอบแล้ว - หยุดการทำงาน"
        self.heartbeat.beat("done", summary)
        return self._finalize(summary)

    def _think(self) -> Optional[dict]:
        """คิด - เรียก LLM เพื่อหาว่าควรทำอะไรต่อ
        คืนค่า dict: {"type": "thought", "content": str, "suggested_action": str}
        หรือ None ถ้า JSON ไม่ถูกต้อง"""
        prompt = self._build_think_prompt()
        return self._call_llm_structured(prompt, "thought")

    def _act(self, thought_data: dict) -> Optional[dict]:
        """ตัดสินใจ action จาก thought
        คืนค่า dict: {"type": "action", "action_type": str, "content": str}
        หรือ None ถ้า JSON ไม่ถูกต้อง"""
        prompt = self._build_act_prompt(thought_data)
        return self._call_llm_structured(prompt, "action")

    def _observe(self, action_type: str, action_content: str) -> str:
        """ดูผลลัพธ์ - รัน action และเก็บผล"""
        if action_type == "terminal":
            return self._run_terminal(action_content)
        elif action_type == "file":
            return self._handle_file(action_content)
        elif action_type == "code":
            return self._handle_code(action_content)
        else:
            return f"Error: ไม่รู้จัก action type: {action_type}"

    # ──────────────────────────── LLM Call ────────────────────────────

    def _call_llm(self, prompt: str) -> str:
        """เรียก LLM - รองรับทั้ง Mock, litellm, และ requests โดยตรง
        ถ้า provider แรก rate limit หมด จะลอง provider ถัดไป"""
        # Mock mode
        if self.mock and self._llm:
            messages = [{"role": "user", "content": prompt}]
            return self._llm.completion(messages)

        # Providers เรียงตามลำดับความสำคัญ
        providers = [
            self.llm_config,  # Provider หลักจาก config
            {"model": "groq/llama-3.3-70b-versatile", "api_key": os.environ.get("GROQ_API_KEY")},
            {"model": "mistral/mistral-large-latest", "api_key": os.environ.get("MISTRAL_API_KEY")},
        ]

        last_error = ""
        for provider in providers:
            if not provider or not provider.get("api_key"):
                continue
            try:
                import litellm as _litellm
                return self._call_litellm(prompt, provider)
            except ImportError:
                pass
            except Exception as e:
                error_str = str(e)
                last_error = str(e)
                # ถ้า rate limit ให้ลอง provider ถัดไป
                if 'rate_limit' in error_str.lower() or '429' in error_str or '1300' in error_str:
                    continue
                # Error อื่นให้ลอง provider ถัดไป
                continue

        # ถ้าทุก provider ล้มเหลว
        if 'rate_limit' in last_error.lower() or '429' in last_error or '1300' in last_error:
            return '{"type": "done", "content": "Rate limit exceeded", "summary": "API rate limit หมดทุก provider กรุณารอแล้วลองใหม่"}'
        return f"Error เรียก LLM: {last_error}"

    def _build_system_context(self) -> str:
        """สร้าง system context รวม SYSTEM_PROMPT + JSON instruction + memory"""
        parts = [self.SYSTEM_PROMPT, JSON_SYSTEM_INSTRUCTION]

        context = self.memory.get_context(max_entries=10)
        if context:
            parts.append(f"\n## บริบทจากประวัติ:\n{context}")

        return "\n".join(parts)

    def _call_litellm(self, prompt: str, provider: Optional[dict] = None) -> str:
        """เรียก LLM ผ่าน litellm - รองรับหลาย provider"""
        import litellm
        litellm.set_verbose = False
        # Suppress LiteLLM logging completely
        import logging
        logging.getLogger('LiteLLM').setLevel(logging.ERROR)
        logging.getLogger('litellm').setLevel(logging.ERROR)
        logging.getLogger('LiteLLM.llms').setLevel(logging.ERROR)

        if provider is None:
            provider = self.llm_config

        api_key = provider.get("api_key") or os.environ.get("MISTRAL_API_KEY")
        model = provider.get("model", "mistral/mistral-large-latest")

        # ถ้าไม่มี api_key ให้ใช้ mock
        if not api_key:
            return self._llm.completion([{"role": "user", "content": prompt}]) if self._llm else "Error: ไม่มี API key"

        # Mistral จุกจิกเรื่อง system prompt ถ้าใช้ role system ซ้อนกันหลายอัน
        # ใช้ system message เดียวรวม context + JSON instruction
        system_context = self._build_system_context()

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
                temperature=0.3,  # ลด temperature เพื่อให้ JSON แม่นยำขึ้น
                api_key=api_key,
            )
            content = response.choices[0].message.content

            self._conversation_history.append({"role": "user", "content": prompt})
            self._conversation_history.append({"role": "assistant", "content": content})

            return content
        except Exception as e:
            error_str = str(e)
            # ถ้า rate limit ให้ throw ต่อเพื่อให้ _call_llm จัดการ
            if 'rate_limit' in error_str.lower() or '429' in error_str or '1300' in error_str:
                raise
            return f"Error เรียก LLM: {e}"

    def _call_requests(self, prompt: str) -> str:
        """Fallback: เรียก Mistral API ผ่าน requests โดยตรง"""
        import requests
        api_key = self.llm_config.get("api_key") or os.environ.get("MISTRAL_API_KEY")
        if not api_key:
            return "Error: ไม่มี API key กรุณาตั้งค่า MISTRAL_API_KEY"

        model = self.llm_config.get("model", "mistral-large-latest")

        # รวม system prompt + JSON instruction + context เป็นอันเดียว
        system_context = self._build_system_context()

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
                    "temperature": 0.3,  # ลด temperature เพื่อให้ JSON แม่นยำขึ้น
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
        """สร้าง prompt สำหรับการคิด - รวมประวัติทั้งหมดให้ LLM เห็นบริบท"""
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

        parts.append("""## ขั้นตอน:
1. คิดทบทวนสถานการณ์ปัจจุบันจากประวัติ
2. กำหนดว่าต้องทำอะไรต่อ
3. ถ้าได้ข้อสรุปแล้ว ให้ตอบ type เป็น "done"

## คำสั่ง IMPORTANT:
- OUTPUT ONLY JSON. No text before or after.
- No greetings, no explanations, no markdown formatting.
- Just the raw JSON object, starting with { and ending with }.

## ตัวอย่าง:
ภารกิจ: "สำรวจไฟล์ในโปรเจค"
คุณคิด: "ต้องดูโครงสร้างโปรเจคก่อนด้วย ls"
ตอบ: {"type": "thought", "content": "ต้องดูโครงสร้างโปรเจคก่อนด้วย ls", "suggested_action": "terminal: ls -la"}

หลังจากเห็นผลลัพธ์แล้ว:
คุณคิด: "เห็นโครงสร้างแล้ว ควรอ่าน README.md เพื่อดูรายละเอียด"
ตอบ: {"type": "thought", "content": "เห็นโครงสร้างแล้ว ควรอ่าน README.md", "suggested_action": "terminal: cat README.md"}

เมื่อได้ข้อสรุป:
ตอบ: {"type": "done", "content": "วิเคราะห์เสร็จ", "summary": "พบไฟล์สำคัญ: README.md, src/"}

## รูปแบบ JSON:
{"type": "thought", "content": "สิ่งที่กำลังคิด (ภาษาไทย สั้นๆ)", "suggested_action": "action ที่จะทำ (optional)"}""")

        return "\n".join(parts)

    def _build_act_prompt(self, thought_data: dict) -> str:
        """สร้าง prompt สำหรับตัดสินใจ action - รวม observation ล่าสุด"""
        thought_content = thought_data.get("content", "")
        suggested = thought_data.get("suggested_action", "")

        # หา observation ล่าสุด
        last_obs = ""
        for h in reversed(self._history):
            if h["type"] == "observation":
                last_obs = h["content"][:500]
                break

        prompt = f"""จากความคิดนี้: "{thought_content}"
"""
        if suggested:
            prompt += f"\nข้อเสนอแนะ: action ที่แนะนำคือ {suggested}\n"

        if last_obs:
            prompt += f"""\nผลลัพธ์ล่าสุดที่ได้:\n{last_obs}\n"""

        prompt += """\n## เงื่อนไขการตัดสินใจ:
- ถ้าเจอ "Rate limit" หรือ "429": ให้รอแล้วลองใหม่ ด้วย action_type "terminal" และคำสั่งเดิม
- ถ้าผลลัพธ์ซ้ำกับรอบก่อนหน้า 3 ครั้ง: ให้ตอบ type "done" บอกว่าติด loop
- ถ้าไม่แน่ใจว่าต้องทำอะไรต่อ: ให้ตอบ type "done" บอกว่าต้องการคำแนะนำ
- ถ้างานเสร็จสมบูรณ์: ให้ตอบ type "done" พร้อมสรุปผล

## คำสั่ง IMPORTANT:
- OUTPUT ONLY JSON. No text before or after.
- No greetings, no explanations, no markdown formatting.
- Just the raw JSON object, starting with { and ending with }.

## ตัวอย่าง:
thought: "ต้องดูโครงสร้างโปรเจคก่อนด้วย ls"
observation: (ยังไม่มี)
ตอบ: {"type": "action", "action_type": "terminal", "content": "ls -la /workspace/"}

thought: "เห็นโครงสร้างแล้ว ควรอ่าน README.md"
observation: "total 48, drwxr-xr-x ..."
ตอบ: {"type": "action", "action_type": "terminal", "content": "cat README.md"}

thought: "ได้ข้อมูลครบแล้ว สรุปผลได้"
observation: "README.md: ERP Project..."
ตอบ: {"type": "action", "action_type": "done", "content": "วิเคราะห์เสร็จ", "summary": "..."}

## รูปแบบ JSON:
```json
{"type": "action", "action_type": "terminal|file|code|done", "content": "รายละเอียด"}
```"""

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
        """จัดการกับ code action - ปัจจุบันแค่บันทึกไว้"""
        return f"📝 Code action received: {action[:200]}"

    # ──────────────────────────── Finalize ────────────────────────────

    def _finalize(self, result: str) -> str:
        """สรุปผลและเขียน Flag File"""
        summary = result.strip()

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
