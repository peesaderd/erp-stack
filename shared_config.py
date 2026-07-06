"""
Shared Config — Centralized key/secret loader
==============================================
Priority:
  1. os.environ (set by pm2/systemd)
  2. .env files in known locations
  3. Clear error if missing

Usage:
  from shared_config import PRODIA_TOKEN, GEMINI_API_KEY

Do NOT copy/redefine key env vars in individual modules anymore.
"""

import os
import logging

logger = logging.getLogger("shared_config")

# ─── Config search paths ─────────────────────────────────────────────
# .env file locations in priority order (first match wins per key)
ENV_FILE_PATHS = [
    "/home/openhands/.openclaw/workspace/business-os/services/image-gen/.env",
    "/home/openhands/erp-stack/tiktok-ugc-studio/.env",
    "/home/openhands/erp-stack/.env",
]


def _load_env_files():
    """Load all .env files into a flat dict (first file wins per key)."""
    merged = {}
    for fpath in ENV_FILE_PATHS:
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key not in merged:  # first wins
                        merged[key] = val
        except Exception as e:
            logger.debug(f"Could not read {fpath}: {e}")
    return merged


_env_dict = _load_env_files()


def _get_key(name: str) -> str:
    """Get key: os.environ → .env files → ValueError"""
    val = os.environ.get(name)
    if val:
        return val
    val = _env_dict.get(name)
    if val:
        return val
    raise ValueError(
        f"{name} not found in os.environ or any .env file. "
        f"Checked paths: {[p for p in ENV_FILE_PATHS if os.path.isfile(p)]}"
    )


# ─── Exported Keys (lazy, only raise on access) ──────────────────────

def _lazy(name):
    def _get():
        return _get_key(name)
    return _get


PRODIA_TOKEN = _lazy("PRODIA_TOKEN")
GEMINI_API_KEY = _lazy("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", _env_dict.get("GEMINI_MODEL", "gemini-2.5-flash"))
PFM_API_KEY = _lazy("PFM_API_KEY")
FACEBOOK_ACCESS_TOKEN = _lazy("FACEBOOK_ACCESS_TOKEN")
