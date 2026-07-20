"""Rate Limiting — Token Bucket Algorithm สำหรับ ERP Modular API Gateway

รองรับ:
- Per-client rate limiting (ใช้ client_id หรือ API key)
- Configurable limits ต่อ endpoint
- In-memory (เริ่มต้น) → สามารถเปลี่ยนเป็น Redis ได้

โครงสร้าง:
    RateLimiter: class หลักที่จัดการ token buckets
    rate_limit(): FastAPI middleware/dependency สำหรับ protect endpoints
"""

import time
import threading
from typing import Dict, Optional, Callable
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


# ─── Token Bucket ───────────────────────────────────────────────────────────

class TokenBucket:
    """Token Bucket Algorithm — ควบคุมอัตราการเรียกใช้ API

    ทำงาน:
        - bucket มี tokens เต็มที่ capacity
        - ทุกครั้งที่มี request ใช้ 1 token
        - tokens เติมกลับในอัตรา refill_rate ต่อวินาที
        - ถ้าไม่มี tokens → reject request
    """

    __slots__ = ("capacity", "refill_rate", "_tokens", "_last_refill", "_lock")

    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens ต่อวินาที
        self._tokens = float(capacity)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self):
        """เติม tokens ตามเวลาที่ผ่านไป"""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
        self._last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """ใช้ tokens — คืน True ถ้ามีพอ, False ถ้าไม่"""
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    @property
    def available(self) -> float:
        """จำนวน tokens ที่เหลืออยู่"""
        with self._lock:
            self._refill()
            return self._tokens


# ─── Rate Limiter ───────────────────────────────────────────────────────────

class RateLimiter:
    """Rate Limiter หลัก — จัดการ token buckets สำหรับหลาย clients

    ใช้งาน:
        limiter = RateLimiter()
        limiter.add_rule("/api/v1/*", capacity=60, refill_rate=1.0)  # 60 req/min

        # ใน middleware
        if not limiter.check("client-123", "/api/v1/modules"):
            raise HTTPException(429, "Too Many Requests")
    """

    def __init__(self, default_capacity: int = 60, default_refill_rate: float = 1.0):
        self.default_capacity = default_capacity
        self.default_refill_rate = default_refill_rate
        self._buckets: Dict[str, TokenBucket] = {}
        self._rules: list[tuple[str, int, float]] = []  # (pattern, capacity, refill_rate)
        self._lock = threading.Lock()

    def add_rule(self, path_pattern: str, capacity: int, refill_rate: float):
        """เพิ่ม rate limit rule สำหรับ path pattern

        Args:
            path_pattern: รูปแบบ path (รองรับ * ท้าย) เช่น "/api/v1/*"
            capacity: จำนวน tokens สูงสุด
            refill_rate: อัตราเติม tokens ต่อวินาที
        """
        with self._lock:
            self._rules.append((path_pattern, capacity, refill_rate))

    def _match_rule(self, path: str) -> tuple[int, float]:
        """หา rule ที่ตรงกับ path — คืน (capacity, refill_rate)"""
        for pattern, capacity, refill_rate in self._rules:
            if pattern.endswith("*"):
                if path.startswith(pattern[:-1]):
                    return capacity, refill_rate
            elif pattern == path:
                return capacity, refill_rate
        return self.default_capacity, self.default_refill_rate

    def _get_bucket_key(self, client_id: str, path: str) -> str:
        """สร้าง key สำหรับ bucket — client + path"""
        return f"{client_id}:{path}"

    def check(self, client_id: str, path: str) -> bool:
        """ตรวจสอบว่า request นี้ผ่าน rate limit หรือไม่

        Returns:
            True ถ้าผ่าน, False ถ้าโดน limit
        """
        capacity, refill_rate = self._match_rule(path)
        bucket_key = self._get_bucket_key(client_id, path)

        with self._lock:
            if bucket_key not in self._buckets:
                self._buckets[bucket_key] = TokenBucket(capacity, refill_rate)

        return self._buckets[bucket_key].consume()

    def get_remaining(self, client_id: str, path: str) -> float:
        """จำนวน tokens ที่เหลือ"""
        bucket_key = self._get_bucket_key(client_id, path)
        bucket = self._buckets.get(bucket_key)
        return bucket.available if bucket else self.default_capacity

    def cleanup(self, max_age_seconds: int = 3600):
        """ลบ buckets ที่ไม่ได้ใช้งานแล้ว — เรียกเป็นระยะ"""
        now = time.monotonic()
        with self._lock:
            expired = [
                k for k, v in self._buckets.items()
                if now - v._last_refill > max_age_seconds
            ]
            for k in expired:
                del self._buckets[k]


# ─── Global Instance ────────────────────────────────────────────────────────

_rate_limiter: Optional[RateLimiter] = None
_rate_limiter_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    """Singleton: ได้ instance ของ RateLimiter"""
    global _rate_limiter
    if _rate_limiter is None:
        with _rate_limiter_lock:
            if _rate_limiter is None:
                _rate_limiter = RateLimiter()
                # Default rules
                _rate_limiter.add_rule("/health", capacity=120, refill_rate=2.0)  # 120 req/min
                _rate_limiter.add_rule("/api/v1/*", capacity=60, refill_rate=1.0)  # 60 req/min
                _rate_limiter.add_rule("/api/v1/modules/*", capacity=120, refill_rate=2.0)
                _rate_limiter.add_rule("/api/v1/templates/render", capacity=30, refill_rate=0.5)  # 30 req/min
    return _rate_limiter


# ─── FastAPI Middleware ─────────────────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware สำหรับ rate limiting

    ใช้งาน:
        app.add_middleware(RateLimitMiddleware)
    """

    async def dispatch(self, request: Request, call_next):
        limiter = get_rate_limiter()

        # ดึง client_id จาก request
        client_id = self._get_client_id(request)

        # ตรวจสอบ rate limit
        if not limiter.check(client_id, request.url.path):
            remaining = limiter.get_remaining(client_id, request.url.path)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "เรียก API บ่อยเกินไป กรุณารอสักครู่",
                    "retry_after_seconds": 1.0,
                },
                headers={
                    "X-RateLimit-Limit": "60",
                    "X-RateLimit-Remaining": str(int(remaining)),
                    "Retry-After": "1",
                },
            )

        # ดำเนินการต่อ
        response = await call_next(request)

        # เพิ่ม headers rate limit
        remaining = limiter.get_remaining(client_id, request.url.path)
        response.headers["X-RateLimit-Limit"] = "60"
        response.headers["X-RateLimit-Remaining"] = str(int(remaining))

        return response

    @staticmethod
    def _get_client_id(request: Request) -> str:
        """ดึง client identifier จาก request"""
        # 1. ลองจาก Authorization header
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:][:20]  # ใช้ token prefix

        # 2. ลองจาก X-API-Key header
        api_key = request.headers.get("X-API-Key", "")
        if api_key:
            return f"apikey:{api_key[:8]}"

        # 3. fallback: IP address
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        return f"ip:{request.client.host}" if request.client else "unknown"
