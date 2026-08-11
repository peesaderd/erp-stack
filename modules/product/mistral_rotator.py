"""
Mistral API Key Rotator — manages 4+ API keys with per-key cooldown,
adaptive backoff, and concurrent-safe access.

Usage:
    rotator = MistralKeyRotator.from_env()
    content = await rotator.call(prompt, max_tokens=500)

Features:
    - Per-key cooldown tracking (resets after cooldown_seconds)
    - Adaptive backoff from Retry-After headers
    - Concurrent-safe with asyncio.Lock
    - Stats tracking per key (success/fail/rate-limit counts)
    - Exponential backoff when all keys exhausted
"""

import asyncio
import os
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger("mistral_rotator")


@dataclass
class KeyStats:
    """Track per-key statistics."""
    success: int = 0
    failed: int = 0
    rate_limited: int = 0
    last_used: float = 0.0
    last_rate_limit: float = 0.0
    total_tokens: int = 0


@dataclass
class KeySlot:
    """One API key with its cooldown state."""
    key: str
    index: int  # 1-based display index
    stats: KeyStats = field(default_factory=KeyStats)
    # Cooldown: timestamp after which this key is available again
    available_after: float = 0.0


class MistralKeyRotator:
    """
    Round-robin key rotator with per-key cooldown.

    When a key returns 429:
        - Mark it as rate-limited for `cooldown_seconds` (default 60s)
        - If Retry-After header present, use that instead
        - Rotate to next available key

    When all keys are exhausted:
        - Wait for the earliest cooldown to expire
        - Retry with exponential backoff
    """

    def __init__(self, keys: list[str], cooldown_seconds: int = 60, max_retries: int = 3):
        self._slots: list[KeySlot] = [
            KeySlot(key=k, index=i + 1) for i, k in enumerate(keys)
        ]
        self._current = 0  # round-robin index
        self._cooldown = cooldown_seconds
        self._max_retries = max_retries
        self._lock = asyncio.Lock()
        self._global_stats = {"total_calls": 0, "total_errors": 0}

        logger.info(f"Initialized MistralKeyRotator with {len(self._slots)} keys, cooldown={cooldown_seconds}s")

    @classmethod
    def from_env(cls, cooldown_seconds: int = 60) -> "MistralKeyRotator":
        """Load keys from MISTRAL_API_KEY, MISTRAL_API_KEY_2, ... MISTRAL_API_KEY_9."""
        keys = []
        seen = set()
        for i in range(1, 10):
            env_name = "MISTRAL_API_KEY" if i == 1 else f"MISTRAL_API_KEY_{i}"
            k = os.environ.get(env_name, "").strip()
            if k and k not in seen:
                seen.add(k)
                keys.append(k)
        if not keys:
            raise ValueError("No MISTRAL_API_KEY found in environment")
        return cls(keys, cooldown_seconds=cooldown_seconds)

    @property
    def available_keys(self) -> int:
        """How many keys are NOT in cooldown right now."""
        now = time.time()
        return sum(1 for s in self._slots if s.available_after <= now)

    def _pick_key(self) -> Optional[KeySlot]:
        """Pick next available key using round-robin. Returns None if all in cooldown."""
        now = time.time()
        n = len(self._slots)
        for _ in range(n):
            slot = self._slots[self._current % n]
            self._current = (self._current + 1) % n
            if slot.available_after <= now:
                return slot
        return None

    def _mark_rate_limited(self, slot: KeySlot, retry_after: Optional[float] = None):
        """Mark a key as rate-limited with cooldown."""
        wait = retry_after if retry_after and retry_after > 0 else self._cooldown
        slot.available_after = time.time() + wait
        slot.stats.rate_limited += 1
        slot.stats.last_rate_limit = time.time()
        logger.info(
            f"Key #{slot.index} rate-limited for {wait:.0f}s "
            f"(stats: ok={slot.stats.success} fail={slot.stats.failed} "
            f"rl={slot.stats.rate_limited})"
        )

    async def call(
        self,
        prompt: str,
        max_tokens: int = 500,
        model: str = "mistral-large-latest",
        temperature: float = 0.3,
    ) -> str:
        """
        Call Mistral API with automatic key rotation.

        Returns the completion text on success, or "" on failure.
        Retries across keys and with backoff on exhaustion.
        """
        self._global_stats["total_calls"] += 1

        for attempt in range(self._max_retries + 1):
            async with self._lock:
                slot = self._pick_key()

            if slot is None:
                # All keys in cooldown — wait for earliest
                earliest = min(s.available_after for s in self._slots)
                wait = max(0.5, earliest - time.time())
                if attempt < self._max_retries:
                    logger.warning(
                        f"All {len(self._slots)} keys in cooldown — "
                        f"waiting {wait:.0f}s (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(wait)
                    continue
                else:
                    logger.error(f"All keys exhausted after {self._max_retries} retries")
                    return ""

            # Make the API call
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        "https://api.mistral.ai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {slot.key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "max_tokens": max_tokens,
                            "temperature": temperature,
                        },
                    )

                if resp.status_code == 200:
                    async with self._lock:
                        slot.stats.success += 1
                        slot.stats.last_used = time.time()
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    return content

                if resp.status_code in (401, 429):
                    # Parse Retry-After header
                    retry_after = None
                    ra = resp.headers.get("Retry-After") or resp.headers.get("retry-after")
                    if ra:
                        try:
                            retry_after = float(ra)
                        except ValueError:
                            pass

                    async with self._lock:
                        self._mark_rate_limited(slot, retry_after)
                    # Immediately try next key (no sleep)
                    continue

                # Other error
                logger.warning(f"Key #{slot.index} HTTP {resp.status_code}: {resp.text[:120]}")
                async with self._lock:
                    slot.stats.failed += 1
                return ""

            except Exception as e:
                msg = str(e).lower()
                if "429" in msg or "rate" in msg or "401" in msg:
                    async with self._lock:
                        self._mark_rate_limited(slot)
                    continue
                async with self._lock:
                    slot.stats.failed += 1
                self._global_stats["total_errors"] += 1
                logger.error(f"Key #{slot.index} error: {e}")
                return ""

        return ""

    def get_stats(self) -> dict:
        """Return rotation stats for monitoring."""
        now = time.time()
        return {
            "total_keys": len(self._slots),
            "available_now": self.available_keys,
            "global": dict(self._global_stats),
            "keys": [
                {
                    "index": s.index,
                    "ok": s.stats.success,
                    "fail": s.stats.failed,
                    "rate_limited": s.stats.rate_limited,
                    "in_cooldown": s.available_after > now,
                    "cooldown_remaining": max(0, round(s.available_after - now)),
                }
                for s in self._slots
            ],
        }

    def reset_all(self):
        """Reset all cooldowns (useful after long pause)."""
        for s in self._slots:
            s.available_after = 0
        logger.info("All key cooldowns reset")


# ─── Global singleton (lazy init) ─────────────────────────────────────────────

_rotator: Optional[MistralKeyRotator] = None


def get_rotator() -> MistralKeyRotator:
    """Get or create the global MistralKeyRotator."""
    global _rotator
    if _rotator is None:
        _rotator = MistralKeyRotator.from_env()
    return _rotator


async def call_mistral(prompt: str, max_tokens: int = 500, model: str = "mistral-large-latest") -> str:
    """Convenience function — call via global rotator."""
    return await get_rotator().call(prompt, max_tokens=max_tokens, model=model)


# ─── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio
    import json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    async def test():
        rotator = MistralKeyRotator.from_env()
        print(f"Keys loaded: {len(rotator._slots)}")

        # Quick test with each key
        for i in range(4):
            result = await rotator.call(f"SReply with just the number {i}", max_tokens=10)
            print(f"Call {i}: {result[:30]!r}")

        print("\nStats:", json.dumps(rotator.get_stats(), indent=2))

    asyncio.run(test())
