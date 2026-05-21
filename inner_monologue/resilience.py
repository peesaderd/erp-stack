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
