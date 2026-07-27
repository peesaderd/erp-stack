"""
Schema Engine Client — CRUD wrapper for reward-related schemas

Schema Engine stores records as:
  { id, schema, data: { field1: val1, ... }, created_at, updated_at }

POST/PUT: send fields flat in the request body (NOT wrapped in {fields: ...})
GET response: fields are in record["data"], not record["fields"]
"""

import json
import urllib.request
import urllib.error
import logging
from typing import Optional

from reward.config import SCHEMA_ENGINE_URL, SCHEMA_MEMBER, SCHEMA_REWARD_LEDGER, SCHEMA_REWARDS

logger = logging.getLogger("reward.schema_client")


def _api(method: str, path: str, data: Optional[dict] = None) -> Optional[dict]:
    """Call Schema Engine API."""
    url = f"{SCHEMA_ENGINE_URL}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        logger.error(f"Schema API {method} {path} -> {e.code}: {err_body[:300]}")
        return None
    except Exception as e:
        logger.error(f"Schema API {method} {path} -> {e}")
        return None


def _get_fields(record: Optional[dict]) -> dict:
    """Extract field data from a record (works whether it's under 'data' or top-level)."""
    if not record:
        return {}
    if isinstance(record, dict):
        if "data" in record and isinstance(record["data"], dict):
            return record["data"]
        # Direct field dict
        return record
    return {}


# ── Member ──────────────────────────────────────────────────────────

def find_member_by_line(line_user_id: str) -> Optional[dict]:
    """Find a member record by LINE User ID (field filter)."""
    result = _api("GET", f"/api/v1/data/{SCHEMA_MEMBER}?line_user_id={line_user_id}&limit=1")
    if result and result.get("success") and result.get("data"):
        records = result["data"]
        return records[0] if records else None
    return None


def get_member(member_id: str) -> Optional[dict]:
    """Get a single member by record ID."""
    result = _api("GET", f"/api/v1/data/{SCHEMA_MEMBER}/{member_id}")
    if result and result.get("success"):
        return result.get("data")
    return None


def create_member(field_data: dict) -> Optional[dict]:
    """Create a new member record (fields sent flat)."""
    result = _api("POST", f"/api/v1/data/{SCHEMA_MEMBER}", field_data)
    if result and result.get("success"):
        return result.get("record")
    return None


def update_member(member_id: str, field_data: dict) -> Optional[dict]:
    """Update member fields (points, tier, etc.)."""
    result = _api("PUT", f"/api/v1/data/{SCHEMA_MEMBER}/{member_id}", field_data)
    if result and result.get("success"):
        return result.get("record")
    return None


def list_members(search: str = "", limit: int = 50) -> list:
    """List all members, optionally filtered."""
    params = f"?limit={limit}"
    if search:
        params = f"?search={search}"
    result = _api("GET", f"/api/v1/data/{SCHEMA_MEMBER}{params}")
    if result and result.get("success"):
        return result.get("data", [])
    return []


# ── Reward Ledger ───────────────────────────────────────────────────

def create_ledger_entry(field_data: dict) -> Optional[dict]:
    """Record a ledger transaction (fields sent flat)."""
    result = _api("POST", f"/api/v1/data/{SCHEMA_REWARD_LEDGER}", field_data)
    if result and result.get("success"):
        return result.get("record")
    return None


def get_ledger_for_member(member_id: str, limit: int = 20) -> list:
    """Get recent ledger entries for a member using field-specific filter."""
    result = _api("GET", f"/api/v1/data/{SCHEMA_REWARD_LEDGER}?member_id={member_id}&limit={limit}")
    if result and result.get("success"):
        return result.get("data", [])
    return []


# ── Rewards Catalog ────────────────────────────────────────────────

def list_active_rewards() -> list:
    """Get all active redeemable rewards."""
    result = _api("GET", f"/api/v1/data/{SCHEMA_REWARDS}?limit=100")
    if result and result.get("success"):
        entries = result.get("data", [])
        return [e for e in entries if _get_fields(e).get("is_active", False)]
    return []


def get_reward(reward_id: str) -> Optional[dict]:
    """Get a single reward item."""
    result = _api("GET", f"/api/v1/data/{SCHEMA_REWARDS}/{reward_id}")
    if result and result.get("success"):
        return result.get("data")
    return None
