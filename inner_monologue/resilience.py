"""
Resilience — Retry Strategy + Fallback Provider + Circuit Breaker + JSON Schema Validation

ให้ Agent ทนทานต่อ:
- Rate limit (429) → retry แบบ exponential backoff
- Provider ล้ม → fallback ไป provider อื่น
- JSON ไม่ถูกต้อง → retry พร้อม schema validation
- ติดลูป → stuck detection + circuit breaker
"""

import json
import re
import time
import random
from typing import Optional, Callable, Any


# ═══════════════════════════════════════════════════════════════════════════
# Retry Strategy
# ═══════════════════════════════════════════════════════════════════════════

class RetryStrategy:
    """Retry แบบ Exponential Backoff + Jitter"""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: bool = True,
        retryable_exceptions: tuple = (Exception,),
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions

    def execute(self, fn: Callable, *args, **kwargs) -> Any:
        """เรียก fn พร้อม retry ถ้าเกิด exception"""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except self.retryable_exceptions as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = self._get_delay(attempt)
                    print(f"  ⚠️ Retry {attempt + 1}/{self.max_retries} หลังจาก {delay:.1f}s: {e}")
                    time.sleep(delay)

        raise last_exception

    def _get_delay(self, attempt: int) -> float:
        """คำนวณ delay = exponential backoff + optional jitter"""
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        if self.jitter:
            delay = delay * (0.5 + random.random() * 0.5)  # ±50%
        return delay


# ═══════════════════════════════════════════════════════════════════════════
# Fallback Provider Chain
# ═══════════════════════════════════════════════════════════════════════════

class FallbackProvider:
    """Provider Chain — ลอง provider ทีละตัว ถ้าตัวแรก fail ก็ลองตัวถัดไป"""

    def __init__(self, providers: list[dict]):
        """
        providers: list of dicts
            [{"name": "deepseek", "model": "deepseek/deepseek-chat", "api_key": "..."},
             {"name": "groq", "model": "groq/llama-3.3-70b-versatile", "api_key": "..."}]
        """
        self.providers = providers
        self._last_failures: dict[str, float] = {}  # provider_name -> timestamp
        self._cooldown_period = 30.0  # 30 seconds before retrying a failed provider

    def execute(self, call_fn: Callable, prompt: str, provider_override: Optional[dict] = None) -> str:
        """ลองเรียก provider เรียงตามลำดับ ถ้าตัวแรก fail ก็ลองตัวถัดไป"""
        providers_to_try = [provider_override] if provider_override else self.providers

        errors = []
        for provider in providers_to_try:
            name = provider.get("name", "unknown")

            # Check cooldown
            if name in self._last_failures:
                elapsed = time.time() - self._last_failures[name]
                if elapsed < self._cooldown_period:
                    continue  # ข้าม provider ที่เพิ่ง fail

            try:
                result = call_fn(prompt, provider)
                # Success — reset failure count
                self._last_failures.pop(name, None)
                return result
            except Exception as e:
                self._last_failures[name] = time.time()
                errors.append(f"{name}: {e}")
                print(f"  ⚠️ Provider '{name}' ล้ม: {e}")
                continue

        # All providers failed
        raise RuntimeError(
            f"Providers ทั้งหมดล้ม:\n" + "\n".join(errors)
        )


# ═══════════════════════════════════════════════════════════════════════════
# Circuit Breaker
# ═══════════════════════════════════════════════════════════════════════════

class CircuitBreaker:
    """Circuit Breaker — ป้องกันการเรียกซ้ำเมื่อ provider มีปัญหา"""

    STATE_CLOSED = "closed"       # ปกติ เรียกได้
    STATE_OPEN = "open"           # ปิด ไม่ให้เรียก
    STATE_HALF_OPEN = "half_open" # ทดสอบเรียกดู

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = self.STATE_CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0

    def call(self, fn: Callable, *args, **kwargs) -> Any:
        """เรียก fn ผ่าน Circuit Breaker"""
        if self.state == self.STATE_OPEN:
            # เช็คว่าถึงเวลา recovery หรือยัง
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                print("  🔄 Circuit Breaker: half-open — ทดสอบเรียก")
                self.state = self.STATE_HALF_OPEN
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN (failures: {self.failure_count})"
                )

        try:
            result = fn(*args, **kwargs)
            # Success — reset
            if self.state == self.STATE_HALF_OPEN:
                print("  ✅ Circuit Breaker: closed — เรียกสำเร็จ")
            self.state = self.STATE_CLOSED
            self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = self.STATE_OPEN
                print(f"  🔴 Circuit Breaker: open — ปิดการเรียก ({self.failure_count} failures)")

            raise


class CircuitBreakerOpenError(Exception):
    """Circuit breaker is open — ไม่ให้เรียก"""
    pass


# ═══════════════════════════════════════════════════════════════════════════
# Stuck Detection
# ═══════════════════════════════════════════════════════════════════════════

class StuckDetector:
    """ตรวจจับว่า Agent วนลูปหรือติดอยู่ — พร้อม auto-recovery"""

    def __init__(
        self,
        same_action_threshold: int = 3,    # action ซ้ำกันกี่รอบถึงถือว่าติด
        same_thought_threshold: int = 3,   # thought ซ้ำกันกี่รอบถึงถือว่าติด
        no_progress_rounds: int = 6,       # กี่รอบแล้วไม่มีความคืบหน้า
        max_consecutive_errors: int = 4,   # error ติดกันกี่รอบถึงถือว่าติด
    ):
        self.same_action_threshold = same_action_threshold
        self.same_thought_threshold = same_thought_threshold
        self.no_progress_rounds = no_progress_rounds
        self.max_consecutive_errors = max_consecutive_errors

        # State
        self._last_action: str = ""
        self._same_action_count = 0
        self._last_thought: str = ""
        self._same_thought_count = 0
        self._consecutive_errors = 0
        self._rounds_since_progress = 0
        self._last_unique_action: str = ""
        self._recovery_attempted = False

    def check(
        self,
        round_num: int,
        thought: str,
        action_type: str,
        action_content: str,
        is_error: bool = False,
    ) -> Optional[dict]:
        """ตรวจสอบว่า Agent ติดหรือไม่
        คืนค่า None ถ้าปกติ, คืนค่า dict ถ้าติด:
            {"stuck": True, "reason": str, "recovery": str}
        """
        action_key = f"{action_type}:{action_content.strip()[:50]}" if action_type else ""
        thought_key = thought.strip()[:50] if thought else ""

        # ─── 1. Consecutive errors ───
        if is_error:
            self._consecutive_errors += 1
            if self._consecutive_errors >= self.max_consecutive_errors:
                return {
                    "stuck": True,
                    "reason": f"error ติดกัน {self._consecutive_errors} รอบ",
                    "recovery": "simplify_task",
                }
            # ยังไม่ถึง threshold — แค่ increment แล้ว return None
            # ไม่เช็ค action/thought ซ้ำ เพราะเป็น error
            return None

        # ไม่ใช่ error — reset error count
        self._consecutive_errors = 0

        # ─── 2. Same action detection ───
        if action_key and action_key == self._last_action:
            self._same_action_count += 1
        else:
            self._same_action_count = 0
            self._last_unique_action = action_key
        self._last_action = action_key

        if self._same_action_count >= self.same_action_threshold:
            return {
                "stuck": True,
                "reason": f"action ซ้ำ {self._same_action_count} รอบ: {action_key}",
                "recovery": "try_different_approach",
            }

        # ─── 3. Same thought detection ───
        if thought_key and thought_key == self._last_thought:
            self._same_thought_count += 1
        else:
            self._same_thought_count = 0
        self._last_thought = thought_key

        if self._same_thought_count >= self.same_thought_threshold:
            return {
                "stuck": True,
                "reason": f"thought ซ้ำ {self._same_thought_count} รอบ: {thought_key}",
                "recovery": "try_different_approach",
            }

        # ─── 4. No progress detection ───
        if action_type in ("terminal", "file", "read"):
            if action_key == self._last_unique_action:
                self._rounds_since_progress += 1
            else:
                self._rounds_since_progress = 0
        else:
            self._rounds_since_progress = 0

        if self._rounds_since_progress >= self.no_progress_rounds:
            return {
                "stuck": True,
                "reason": f"ไม่มีความคืบหน้า {self._rounds_since_progress} รอบ (แค่ explore อย่างเดียว)",
                "recovery": "force_conclusion",
            }

        return None

    def get_recovery_prompt(self, stuck_info: dict) -> str:
        """สร้าง prompt สำหรับ auto-recovery เมื่อ Agent ติด"""
        reason = stuck_info.get("reason", "ไม่ทราบสาเหตุ")
        recovery = stuck_info.get("recovery", "try_different_approach")

        prompts = {
            "try_different_approach": (
                "คุณกำลังทำงานซ้ำๆ โดยไม่ได้ผลลัพธ์ใหม่\n"
                "ให้เปลี่ยนวิธีการ:\n"
                "- ถ้าสำรวจไปหลายรอบแล้ว → สรุปผลเลย\n"
                "- ถ้ารันคำสั่งเดิมซ้ำ → ลองคำสั่งอื่น\n"
                "- ถ้าอ่านไฟล์เดิมซ้ำ → ใช้ข้อมูลที่มีสรุปเลย"
            ),
            "simplify_task": (
                "คุณเจอข้อผิดพลาดหลายครั้งติดต่อกัน\n"
                "ให้:\n"
                "- ลดความซับซ้อนของงาน\n"
                "- ถ้า error ไม่หาย → สรุปว่าทำไม่ได้และแนะนำวิธีแก้\n"
                "- อย่าพยายามซ้ำในสิ่งเดิม"
            ),
            "force_conclusion": (
                "คุณสำรวจมานานแล้ว但没有ได้ข้อสรุป\n"
                "ให้:\n"
                "- ใช้ข้อมูลที่มีอยู่ตอนนี้สรุปผล\n"
                "- ถ้าข้อมูลไม่พอ → สรุปว่าขาดอะไรและแนะนำแนวทาง\n"
                "- อย่าสำรวจเพิ่ม"
            ),
        }

        recovery_msg = prompts.get(recovery, prompts["force_conclusion"])
        return f"""⚠️ ตรวจพบว่าคุณติดลูป: {reason}

{recovery_msg}

ให้ตอบ type="done" พร้อม summary ทันที"""

    def reset(self):
        """รีเซ็ตสถานะทั้งหมด"""
        self._last_action = ""
        self._same_action_count = 0
        self._last_thought = ""
        self._same_thought_count = 0
        self._consecutive_errors = 0
        self._rounds_since_progress = 0
        self._last_unique_action = ""
        self._recovery_attempted = False


# ═══════════════════════════════════════════════════════════════════════════
# JSON Schema Validation
# ═══════════════════════════════════════════════════════════════════════════

# Schema definitions สำหรับแต่ละ action type
ACTION_SCHEMAS = {
    "thought": {
        "type": "object",
        "required": ["type", "content"],
        "properties": {
            "type": {"type": "string", "pattern": "^thought$"},
            "content": {"type": "string", "minLength": 1},
        },
    },
    "action": {
        "type": "object",
        "required": ["type", "action_type", "content"],
        "properties": {
            "type": {"type": "string", "pattern": "^action$"},
            "action_type": {
                "type": "string",
                "enum": ["terminal", "file", "read", "done", "think", "error"],
            },
            "content": {"type": "string", "minLength": 1},
        },
    },
    "done": {
        "type": "object",
        "required": ["type", "content", "summary"],
        "properties": {
            "type": {"type": "string", "pattern": "^done$"},
            "content": {"type": "string"},
            "summary": {"type": "string"},
        },
    },
}


def validate_json_schema(data: dict, schema: dict) -> tuple[bool, str]:
    """ตรวจสอบ JSON ตาม schema — คืนค่า (valid, error_message)"""
    if not isinstance(data, dict):
        return False, "response ไม่ใช่ JSON object"

    # Check required fields
    required = schema.get("required", [])
    for field in required:
        if field not in data:
            return False, f"ไม่พบ field ที่จำเป็น: '{field}'"

    # Check property types
    props = schema.get("properties", {})
    for field, value in data.items():
        if field not in props:
            continue
        prop_schema = props[field]

        # type check
        expected_type = prop_schema.get("type")
        if expected_type == "string" and not isinstance(value, str):
            return False, f"field '{field}' ต้องเป็น string"
        if expected_type == "integer" and not isinstance(value, int):
            return False, f"field '{field}' ต้องเป็น integer"

        # pattern check (string)
        pattern = prop_schema.get("pattern")
        if pattern and isinstance(value, str) and not re.match(pattern, value):
            return False, f"field '{field}' ไม่ตรง pattern: {pattern}"

        # enum check
        enum_values = prop_schema.get("enum")
        if enum_values and value not in enum_values:
            return False, f"field '{field}' ต้องเป็นหนึ่งใน: {enum_values}"

        # minLength check
        min_len = prop_schema.get("minLength")
        if min_len and isinstance(value, str) and len(value) < min_len:
            return False, f"field '{field}' สั้นเกินไป (ขั้นต่ำ {min_len} ตัวอักษร)"

    return True, ""


def extract_json(text: str) -> Optional[dict]:
    """Extract JSON จาก text — รองรับทั้ง ```json ... ``` และ JSON ล้วน"""
    if not text:
        return None

    # ลองแบบ ```json ... ```
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # ลองแบบ JSON ล้วน
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # ลองหา {...} แรกที่เจอ
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def parse_structured_response(
    response: str,
    expected_type: str,
    max_retries: int = 2,
) -> Optional[dict]:
    """Parse JSON response และ validate ตาม schema — พร้อม retry"""
    schema = ACTION_SCHEMAS.get(expected_type)
    if not schema:
        return None

    data = extract_json(response)
    if not data:
        return None

    valid, error = validate_json_schema(data, schema)
    if not valid:
        return None

    return data
