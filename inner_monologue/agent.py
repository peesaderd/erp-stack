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


class RateLimitError(Exception):
    """Rate limit exceeded"""
    pass


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
ALLOWED_ACTION_TYPES = {"terminal", "file", "code", "test", "git", "done"}

JSON_SYSTEM_INSTRUCTION = """
ตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่น

คิด: {"type": "thought", "content": "..."}
ทำ: {"type": "action", "action_type": "terminal|file|code|test|git|done", "content": "..."}
เสร็จ: {"type": "done", "content": "สรุป", "summary": "..."}

ห้ามตอบหลาย JSON ในครั้งเดียว"""


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
            if self._think_count >= 5:
                return '{"type": "action", "action_type": "done", "content": "วิเคราะห์เสร็จสมบูรณ์ วางแผนเรียบร้อย"}'
            actions = [
                '{"type": "action", "action_type": "terminal", "content": "ls -la"}',
                '{"type": "action", "action_type": "terminal", "content": "pwd"}',
                '{"type": "action", "action_type": "file", "content": "list: ."}',
                '{"type": "action", "action_type": "terminal", "content": "ls -la .."}',
            ]
            return actions[min(self._think_count - 1, len(actions) - 1)]

        # think prompt - มี JSON example ที่มี "type": "thought"
        self._think_count += 1
        thoughts = [
            '{"type": "thought", "content": "ฉันควรสำรวจโครงสร้างโปรเจคก่อน เพื่อดูว่ามีไฟล์อะไรอยู่แล้วบ้าง", "suggested_action": "terminal: ls -la"}',
            '{"type": "thought", "content": "โปรเจคมีโครงสร้างเป็นระเบียบ ต้องวางแผนการทำงานเป็น Phase", "suggested_action": "terminal: pwd"}',
            '{"type": "thought", "content": "Core Data Model และ API Layer ควรมาก่อน เพราะทุกอย่างต่อยอดจากโครงสร้างข้อมูล", "suggested_action": "file: list: ."}',
            '{"type": "thought", "content": "Plugin System และ API Gateway ต้องมาต่อ เพราะ Mini App ต้องมี Gateway เป็นทางเข้าออกเดียว", "suggested_action": "terminal: ls -la .."}',
            '{"type": "thought", "content": "Integrations และ AI Agent มาทีหลัง เพราะต้องมี Core + Gateway + Plugin พร้อมก่อน", "suggested_action": "done"}',
        ]
        return thoughts[min(self._think_count - 1, len(thoughts) - 1)]


class InnerMonologueAgent:
    """Agent ที่มี Inner Monologue - คิดก่อนทำ ดูผลก่อนคิดต่อ
    ใช้ Structured Output (JSON) เพื่อป้องกัน hallucination"""

    SYSTEM_PROMPT = """You are "Inner Monologue Agent" (IMA) - an AI assistant with self-awareness and tools.

## Identity:
- Role: AI Supervisor ที่วิเคราะห์ ตัดสินใจ และลงมือทำได้เอง
- Personality: ตรงไปตรงมา กระชับ ใช้ภาษาไทย
- Constraint: ต้องคิดก่อนลงมือทำทุกครั้ง

## Workflow:
1. THINK (ไทย สั้นๆ 1-2 ประโยค)
2. ACT (terminal | file | code | done)
3. OBSERVE (รายงานผลสั้นๆ)
4. REPEAT จนกว่างานเสร็จ → {"type": "done", "content": "สรุป", "summary": "รายละเอียด"}

## Rules:
1. Rate limit → retry
2. ผลซ้ำ 3 รอบ → done บอกติด loop
3. ไม่แน่ใจ → done บอกต้องการคำแนะนำ
4. OUTPUT ONLY JSON. No text outside JSON.
5. งานง่าย (date/time) → done หลังได้ข้อมูล

## Available Tools:

### File Operations:
- read: path/to/file — อ่านไฟล์
- write: path/to/file\\nเนื้อหา — เขียนไฟล์ใหม่ (มี HITL ถ้าไฟล์มีอยู่แล้ว)
- edit: path/to/file\\nSEARCH\\nข้อความเดิม\\nSEARCH\\nข้อความใหม่ — แก้ไขเฉพาะส่วน (search-and-replace)
- list: path/to/dir — ดูรายการใน directory

### Terminal:
- terminal: คำสั่ง bash ใดๆ — รันคำสั่ง shell

### Test:
- test: path/to/test_file.py — รัน pytest
- test: path/to/test_file.py::test_func — รัน pytest เฉพาะฟังก์ชัน

### Git:
- git: status, git: add ., git: commit -m "msg", git: push, etc.

### Code:
- code: คำอธิบาย — บันทึกแนวคิดการเขียนโค้ด (ยังไม่ execute)

## Micro-agents (ความรู้เฉพาะทาง):

### Python/SQLModel:
- SQLModel table=True class: ห้ามใช้ Dict, List, Optional[Dict], Optional[List] ใช้ str แทนแล้ว JSON.stringify ตอนใช้งาน
- ก่อน import ให้ pip install dependencies ก่อนเสมอ
- ถ้า import ล้มเหลว ให้ตรวจสอบว่า dependencies ครบหรือยัง
- ใช้ .venv/bin/activate (ไม่ใช่ source เพราะ shell เป็น /bin/sh)

### Shell:
- shell นี้เป็น /bin/sh ไม่ใช่ bash — ใช้ . venv/bin/activate แทน source
- ใช้ python3 (ไม่ใช่ python)
- ถ้าคำสั่งใช้เวลาเกิน 30 วิ จะ timeout"""

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
        hitl_callback: Optional[callable] = None,
    ):
        self.llm_config = llm_config or {}
        self.memory = memory or ConversationMemory()
        self.heartbeat = heartbeat or Heartbeat()
        self.self_reflection = self_reflection or SelfReflection()
        self.hitl = hitl or HITL(workspace=workspace)
        self.workspace = workspace
        self.mock = mock
        self.hitl_callback = hitl_callback

        self._llm = MockLLM(responses=mock_responses) if mock else None
        self._done = False
        self._history: list[dict] = []
        self._current_task = ""
        self._max_rounds = 40  # เพิ่มจาก 20 เป็น 40
        self._round = 0
        self._conversation_history: list[dict] = []  # สำหรับส่งให้ LLM
        self._response_cache: dict[str, str] = {}  # cache: prompt hash → response

        # Rate limiter — ป้องกัน 429
        self._last_request_time = 0.0
        self._min_request_interval = 1.1  # 1.1 วินาทีระหว่าง request (Mistral ~55 RPM)

        # โหลดประวัติเก่า
        self.memory.load()

        # เชื่อม Condenser function — ให้ memory ใช้ LLM ของ Agent ในการ summarize
        self.memory.set_condense_fn(self._call_llm_for_condense)

        # เชื่อม Self-Reflection กับ LLM
        self.self_reflection.set_llm_fn(self._call_llm_for_condense)

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

    def _call_llm_structured(self, prompt: str, expected_type: str, max_retries: int = 1) -> Optional[dict]:
        """เรียก LLM และบังคับให้ตอบ JSON ตาม schema ที่กำหนด
        ถ้า JSON ไม่ถูกต้อง จะ retry พร้อมแจ้ง error ให้ LLM แก้ไข"""
        for attempt in range(max_retries):
            response = self._call_llm(prompt)
            parsed = self._parse_json_response(response, expected_type)

            if parsed is not None:
                return parsed

            # ถ้า LLM ตอบ "done" แทน "thought" หรือ "action" ให้ยอมรับ
            done_parsed = self._parse_json_response(response, "done")
            if done_parsed is not None and expected_type in ("thought", "action"):
                return {"type": "action", "action_type": "done", "content": done_parsed["content"], "summary": done_parsed.get("summary", "")}

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
        elif action_type == "test":
            return self._run_test(action_content)
        elif action_type == "git":
            return self._run_git(action_content)
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
            {"model": "deepseek/deepseek-chat", "api_key": os.environ.get("DEEPSEEK_API_KEY")},
            {"model": "groq/llama-3.3-70b-versatile", "api_key": os.environ.get("GROQ_API_KEY")},
            {"model": "mistral/mistral-large-latest", "api_key": os.environ.get("MISTRAL_API_KEY")},
        ]

        last_error = ""
        for provider in providers:
            if not provider or not provider.get("api_key"):
                continue
            try:
                return self._call_via_requests(prompt, provider)
            except Exception as e:
                error_str = str(e)
                last_error = str(e)
                # ถ้า rate limit ให้ลอง provider ถัดไป
                if 'rate limit' in error_str.lower() or '429' in error_str or '1300' in error_str:
                    continue
                # Error อื่นให้ลอง provider ถัดไป
                continue

        # ถ้าทุก provider ล้มเหลว
        if 'rate limit' in last_error.lower() or '429' in last_error or '1300' in last_error:
            return '{"type": "done", "content": "Rate limit exceeded", "summary": "API rate limit หมดทุก provider กรุณารอแล้วลองใหม่"}'
        return f"Error เรียก LLM: {last_error}"

    def _call_llm_for_condense(self, prompt: str) -> str:
        """เรียก LLM สำหรับ Condense โดยเฉพาะ — ไม่มี JSON parsing, ไม่มี cache
        คืนค่า plain text response"""
        if self.mock and self._llm:
            messages = [{"role": "user", "content": prompt}]
            return self._llm.completion(messages)

        providers = [
            self.llm_config,
            {"model": "deepseek/deepseek-chat", "api_key": os.environ.get("DEEPSEEK_API_KEY")},
            {"model": "groq/llama-3.3-70b-versatile", "api_key": os.environ.get("GROQ_API_KEY")},
            {"model": "mistral/mistral-large-latest", "api_key": os.environ.get("MISTRAL_API_KEY")},
        ]

        for provider in providers:
            if not provider or not provider.get("api_key"):
                continue
            try:
                return self._call_via_requests_raw(prompt, provider)
            except Exception:
                continue

        return "สรุป: ไม่สามารถเชื่อมต่อ LLM เพื่อสรุปความจำได้"

    def _call_via_requests_raw(self, prompt: str, provider: dict) -> str:
        """เรียก LLM ผ่าน requests POST — คืนค่า plain text (ไม่ใช่ JSON)"""
        import requests

        api_key = provider.get("api_key")
        model = provider.get("model", "mistral/mistral-large-latest")

        if not api_key:
            raise ValueError("No API key")

        if "groq" in model:
            url = "https://api.groq.com/openai/v1/chat/completions"
            api_model = model.split("/", 1)[-1]
        elif "mistral" in model:
            url = "https://api.mistral.ai/v1/chat/completions"
            api_model = model.split("/", 1)[-1]
        elif "deepseek" in model:
            url = "https://api.deepseek.com/v1/chat/completions"
            api_model = model.split("/", 1)[-1]
        else:
            raise ValueError(f"Unknown provider in model: {model}")

        messages = [{"role": "user", "content": prompt}]

        # Rate limiter
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": api_model,
                "messages": messages,
                "max_tokens": 1024,
                "temperature": 0.3,
            },
            timeout=30,
        )

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 5))
            time.sleep(retry_after)
            raise RateLimitError(f"Rate limit exceeded, retry after {retry_after}s")

        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    def _build_system_context(self) -> str:
        """สร้าง system context รวม SYSTEM_PROMPT + JSON instruction + memory"""
        parts = [self.SYSTEM_PROMPT, JSON_SYSTEM_INSTRUCTION]

        # บอก workspace path ให้ LLM รู้
        parts.append(f"\n## Workspace:\n{self.workspace}")

        context = self.memory.get_context(max_entries=10)
        if context:
            parts.append(f"\n## บริบทจากประวัติ:\n{context}")

        return "\n".join(parts)

    def _call_via_requests(self, prompt: str, provider: dict) -> str:
        """เรียก LLM ผ่าน requests POST โดยตรง - ไม่มี debug messages"""
        import requests

        api_key = provider.get("api_key")
        model = provider.get("model", "mistral/mistral-large-latest")

        if not api_key:
            raise ValueError("No API key")

        # Map model to API endpoint
        if "groq" in model:
            url = "https://api.groq.com/openai/v1/chat/completions"
            api_model = model.split("/", 1)[-1]
        elif "mistral" in model:
            url = "https://api.mistral.ai/v1/chat/completions"
            api_model = model.split("/", 1)[-1]
        elif "deepseek" in model:
            url = "https://api.deepseek.com/v1/chat/completions"
            api_model = model.split("/", 1)[-1]
        else:
            raise ValueError(f"Unknown provider in model: {model}")

        # รวม system prompt + JSON instruction + context เป็นอันเดียว
        system_context = self._build_system_context()

        messages = [{"role": "system", "content": system_context}]
        for msg in self._conversation_history[-2:]:
            messages.append(msg)
        messages.append({"role": "user", "content": prompt})

        # cache key = hash ของ messages ทั้งหมด
        cache_key = str(hash(str(messages)))
        if cache_key in self._response_cache:
            cached = self._response_cache[cache_key]
            self._conversation_history.append({"role": "user", "content": prompt})
            self._conversation_history.append({"role": "assistant", "content": cached})
            return cached

        # Rate limiter — รอให้ถึง interval ก่อนส่ง request
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            wait = self._min_request_interval - elapsed
            time.sleep(wait)
        self._last_request_time = time.time()

        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": api_model,
                "messages": messages,
                "max_tokens": 2048,
                "temperature": 0.3,
            },
            timeout=30,
        )

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 5))
            time.sleep(retry_after)
            raise RateLimitError(f"Rate limit exceeded, retry after {retry_after}s")

        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        self._response_cache[cache_key] = content
        self._conversation_history.append({"role": "user", "content": prompt})
        self._conversation_history.append({"role": "assistant", "content": content})

        return content

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
            for h in self._history[-2:]:  # 2 รอบล่าสุด
                t = h["type"]
                c = h["content"][:200]
                r = h["round"]
                history_lines.append(f"[รอบ {r}] {t.upper()}: {c}")
            parts.append("## ประวัติการทำงาน:\n" + "\n".join(history_lines) + "\n")

        # Planning Step — ถ้ายังไม่มี history ให้สำรวจก่อน
        if not self._history:
            parts.append("""## ขั้นตอน (Planning Step):
นี่คือรอบแรก — ยังไม่ได้ลงมือทำอะไรเลย

### ต้องทำ 3 ขั้นตอนก่อนลงมือ:
1. **EXPLORE**: สำรวจโครงสร้างโปรเจคก่อน (list: workspace, read ไฟล์สำคัญ)
2. **PLAN**: วางแผนว่าต้องทำอะไรบ้าง ลำดับก่อนหลัง
3. **EXECUTE**: ลงมือทำตามแผน

### คำถามที่ต้องตอบให้ได้ก่อนลงมือ:
- workspace มีไฟล์อะไรอยู่แล้วบ้าง?
- dependencies มีอะไร? ติดตั้งแล้วหรือยัง?
- โครงสร้างโปรเจคเป็นยังไง?
- อะไรต้องทำก่อน? อะไรทำทีหลัง?

### คำสั่ง:
- OUTPUT ONLY JSON. No text before or after.
- รูปแบบ: {"type": "thought", "content": "สิ่งที่คิด (ไทย สั้นๆ)", "suggested_action": "optional"}""")
        else:
            parts.append("""## ขั้นตอน:
1. คิดทบทวนสถานการณ์ปัจจุบันจากประวัติ
2. กำหนดว่าต้องทำอะไรต่อ
3. ถ้าได้ข้อสรุปแล้ว ให้ตอบ type เป็น "done"

## คำสั่ง:
- OUTPUT ONLY JSON. No text before or after.
- รูปแบบ: {"type": "thought", "content": "สิ่งที่คิด (ไทย สั้นๆ)", "suggested_action": "optional"}""")

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

        prompt += """\n## เงื่อนไข:
- Rate limit → retry ด้วยคำสั่งเดิม
- ผลซ้ำ 3 รอบ → done บอกติด loop
- ไม่แน่ใจ → done บอกต้องการคำแนะนำ
- งานเสร็จ → done พร้อมสรุปผล

## คำสั่ง:
- OUTPUT ONLY JSON. No text before or after.
- รูปแบบ: {"type": "action", "action_type": "terminal|file|code|test|git|done", "content": "..."}

## รูปแบบ action:
- อ่านไฟล์: {"type": "action", "action_type": "file", "content": "read: path/to/file.py"}
- เขียนไฟล์: {"type": "action", "action_type": "file", "content": "write: path/to/file.py\\nเนื้อหาไฟล์..."}
- แก้ไขไฟล์: {"type": "action", "action_type": "file", "content": "edit: path/to/file.py\\nSEARCH\\nข้อความเดิม\\nSEARCH\\nข้อความใหม่"}
- ดูรายการ: {"type": "action", "action_type": "file", "content": "list: path/to/dir"}
- รัน pytest: {"type": "action", "action_type": "test", "content": "tests/test_file.py::test_func"}
- รัน git: {"type": "action", "action_type": "git", "content": "status"}"""

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
        """จัดการกับ file action — มี HITL ก่อนเขียนทับไฟล์ที่มีอยู่"""
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
                return f"Error อ่านไฟล์: {e}"
        elif action.startswith("edit:") or action.startswith("edit "):
            # edit: path/to/file.py\nSEARCH\nold code\nSEARCH\nnew code
            prefix = "edit:" if action.startswith("edit:") else "edit "
            rest = action[len(prefix):].strip()
            if "\n" not in rest:
                return "Error: รูปแบบไม่ถูกต้อง ใช้: edit: path/to/file.py\\nSEARCH\\nข้อความเดิม\\nSEARCH\\nข้อความใหม่"
            path, rest2 = rest.split("\n", 1)
            path = path.strip()
            if "SEARCH" not in rest2:
                return "Error: รูปแบบไม่ถูกต้อง ต้องมี SEARCH คั่นระหว่างข้อความเดิมและข้อความใหม่"
            parts = rest2.split("SEARCH")
            if len(parts) != 3:
                return "Error: รูปแบบไม่ถูกต้อง ใช้: edit: path\\nSEARCH\\nold\\nSEARCH\\nnew"
            old_str = parts[1].strip("\n").strip()
            new_str = parts[2].strip("\n").strip()
            if not old_str:
                return "Error: ข้อความเดิม (SEARCH) ห้ามว่าง"
            full_path = os.path.join(self.workspace, path) if not path.startswith("/") else path
            if not os.path.exists(full_path):
                return f"Error: ไม่พบไฟล์ {path}"
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if old_str not in content:
                    return f"Error: ไม่พบข้อความที่ต้องการแก้ไขใน {path}"
                new_content = content.replace(old_str, new_str, 1)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                return f"แก้ไขไฟล์ {path} สำเร็จ (แทนที่ {len(old_str)} → {len(new_str)} ตัวอักษร)"
            except Exception as e:
                return f"Error แก้ไขไฟล์: {e}"
        elif action.startswith("write:") or action.startswith("write "):
            # write: path\ncontent  หรือ write path\ncontent
            prefix = "write:" if action.startswith("write:") else "write "
            rest = action[len(prefix):].strip()
            if "\n" in rest:
                path, content = rest.split("\n", 1)
                path = path.strip()
                full_path = os.path.join(self.workspace, path) if not path.startswith("/") else path

                # HITL: ถ้าไฟล์มีอยู่แล้ว ให้ถามผู้ใช้ก่อน
                if os.path.exists(full_path):
                    # อ่านไฟล์เดิมเพื่อเปรียบเทียบ
                    try:
                        with open(full_path, "r", encoding="utf-8") as f:
                            old_content = f.read()
                    except Exception:
                        old_content = ""

                    # สร้าง flag รออนุมัติ
                    self.hitl.flag_waiting_for_approval(
                        f"เขียนทับไฟล์ {path}",
                        f"ไฟล์นี้มีอยู่แล้ว ({len(old_content)} ตัวอักษร) ต้องการเขียนทับหรือไม่?"
                    )

                    # ถ้ามี HITL callback ให้เรียก
                    if self.hitl_callback:
                        self.hitl_callback("waiting_for_approval", {
                            "action": f"เขียนทับไฟล์ {path}",
                            "reason": f"ไฟล์นี้มีอยู่แล้ว ({len(old_content)} ตัวอักษร)",
                            "old_content_preview": old_content[:500],
                            "new_content_preview": content[:500],
                        })

                    return f"⏳ HITL: รออนุมัติก่อนเขียนทับไฟล์ {path} — ไฟล์นี้มีอยู่แล้ว ({len(old_content)} ตัวอักษร) กรุณาตรวจสอบ flag ใน .hitl-flags/WAITING_FOR_APPROVAL.txt"

                try:
                    os.makedirs(os.path.dirname(full_path), exist_ok=True)
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    return f"เขียนไฟล์ {path} สำเร็จ ({len(content)} ตัวอักษร)"
                except Exception as e:
                    return f"Error เขียนไฟล์: {e}"
            return "Error: รูปแบบไม่ถูกต้อง ใช้: write: path/to/file\\nเนื้อหาไฟล์..."
        elif action.startswith("list:") or action.startswith("list "):
            prefix = "list:" if action.startswith("list:") else "list "
            path = action[len(prefix):].strip()
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

    def _run_test(self, action: str) -> str:
        """รัน pytest และคืนค่าผลลัพธ์"""
        action = action.strip()
        # รองรับ: test: path/to/test_file.py หรือ test: path/to/test_file.py::test_func
        try:
            result = subprocess.run(
                f"python3 -m pytest {action} -v --tb=short 2>&1 | tail -40",
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.workspace,
            )
            output = result.stdout or ""
            if result.stderr:
                output += f"\n[STDERR]: {result.stderr[:500]}"
            if result.returncode != 0:
                output += f"\n[Exit code: {result.returncode}]"
            return output.strip() or "(ไม่มี output)"
        except subprocess.TimeoutExpired:
            return "Error: pytest ใช้เวลาเกิน 60 วินาที"
        except Exception as e:
            return f"Error รัน pytest: {e}"

    def _run_git(self, action: str) -> str:
        """รัน git command และคืนค่าผลลัพธ์"""
        action = action.strip()
        # รองรับ: git: status, git: add . , git: commit -m "msg", git: push, etc.
        try:
            result = subprocess.run(
                f"git {action}",
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
            return "Error: git ใช้เวลาเกิน 30 วินาที"
        except Exception as e:
            return f"Error รัน git: {e}"

    # ──────────────────────────── Finalize ────────────────────────────

    def _finalize(self, result: str) -> str:
        """สรุปผลและเขียน Flag File + ส่ง Log ไป ERP Modular"""
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

        # Self-reflection (rule-based)
        self.self_reflection.reflect(self._history)

        # Deep reflection (LLM-based) — ใช้ summary จาก memory
        memory_context = self.memory.get_context(max_entries=5)
        if memory_context:
            self.self_reflection.deep_reflect(memory_context)

        # ส่ง Log ไป ERP Modular API (ถ้าใช้งานได้)
        self._send_agent_log(summary)

        return summary

    def _send_agent_log(self, summary: str):
        """ส่ง Log การทำงานไปยัง ERP Modular API"""
        try:
            import urllib.request
            import json

            data = json.dumps({
                "activity": self._current_task[:100],
                "detail": f"Rounds: {self._round} | Summary: {summary[:300]}",
                "status": "done",
            }).encode("utf-8")

            req = urllib.request.Request(
                "http://localhost:54520/agent/logs",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=3)
        except Exception:
            pass  # ERP Modular อาจยังไม่พร้อม — ไม่เป็นไร
