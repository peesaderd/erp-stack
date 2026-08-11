"""
TUS Product DB Guard — Prevents direct writes to tus_products.db.

tus_products.db is a READ-ONLY cache synced from PostgreSQL.
The ONLY way to update it is through pipeline_service.sync_all_to_tus().

This module:
1. Logs any direct INSERT/UPDATE/DELETE attempts
2. Provides audit trail for debugging
3. Pipeline service uses check_write_allowed() before writing
"""
import logging
import traceback
from typing import Optional, Set

logger = logging.getLogger("tus_guard")

# ── Guard state ──────────────────────────────────────────────────────────────
_guard_enabled = True
_violations: list = []

# ── Paths that are ALLOWED to write to tus_products.db ──────────────────────
ALLOWED_WRITERS: Set[str] = {
    "pipeline_service.py",
    "sync_tus_products.py",
}


class GuardViolation(Exception):
    """Raised when a direct write to tus_products.db is attempted."""
    pass


def check_write_allowed(file_path: str, caller_info: str = "") -> bool:
    """
    Check if a write to tus_products.db is allowed.
    Returns True if allowed, raises GuardViolation if blocked.
    """
    if not _guard_enabled:
        return True

    # Check if caller is in allowed list
    if caller_info:
        for allowed in ALLOWED_WRITERS:
            if allowed in caller_info:
                return True

    # Block the write
    violation = {
        "file": file_path,
        "caller": caller_info[:200],
    }
    _violations.append(violation)

    logger.warning(f"TUS GUARD: Blocked direct write to {file_path}")
    logger.warning(f"  Caller: {caller_info[:200]}")
    logger.warning(f"  Use pipeline_service.sync_all_to_tus() instead")

    raise GuardViolation(
        f"Direct write to tus_products.db is blocked. "
        f"Use POST /api/v1/pipeline/sync instead."
    )


def log_write_attempt(file_path: str, caller_info: str = "") -> bool:
    """
    Log a write attempt without blocking (for auditing).
    Returns True if allowed, False if blocked.
    """
    if not _guard_enabled:
        return True

    if caller_info:
        for allowed in ALLOWED_WRITERS:
            if allowed in caller_info:
                return True

    violation = {
        "file": file_path,
        "caller": caller_info[:200],
    }
    _violations.append(violation)
    logger.warning(f"TUS GUARD: Write attempt blocked: {file_path}")
    return False


def get_violations() -> list:
    """Get all guard violations for debugging."""
    return _violations[-50:]


def set_guard_enabled(enabled: bool):
    """Enable/disable the guard (for debugging only)."""
    global _guard_enabled
    _guard_enabled = enabled
    logger.info(f"TUS Guard: {'ENABLED' if enabled else 'DISABLED'}")


def is_guard_enabled() -> bool:
    return _guard_enabled
