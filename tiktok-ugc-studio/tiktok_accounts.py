"""
TikTok account storage — JSON file persistence.
Extracted from main.py.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger("tiktok-accounts")

ACCOUNTS_FILE = Path(__file__).parent / "storage" / "tiktok_accounts.json"


def _load() -> dict:
    if ACCOUNTS_FILE.exists():
        try:
            return json.loads(ACCOUNTS_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save(accounts: dict):
    ACCOUNTS_FILE.write_text(json.dumps(accounts, indent=2))


def list_accounts() -> list:
    """List all stored TikTok accounts."""
    accounts = _load()
    return [{"id": k, **v} for k, v in accounts.items()]


def get_account(account_id: str) -> dict:
    """Get a single account by ID."""
    accounts = _load()
    return accounts.get(account_id.lstrip("@"), {})


def save_account(account_id: str, data: dict) -> dict:
    """Save or update a TikTok account."""
    accounts = _load()
    accounts[account_id] = data
    _save(accounts)
    return data


def delete_account(account_id: str) -> bool:
    """Delete a TikTok account."""
    accounts = _load()
    if account_id in accounts:
        del accounts[account_id]
        _save(accounts)
        return True
    return False
