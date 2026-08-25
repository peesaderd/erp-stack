#!/usr/bin/env python3
"""Order Alarm — poll POS for pending orders, push LINE flex card, re-ring until accepted.

Ring policy:
- New pending order  -> immediate card push (count=1)
- Still 'pending'    -> re-push every REPEAT_SEC seconds, up to MAX_REPEATS times
- Status != pending  -> stop ringing immediately (accepted/cancelled/completed)
"""
import json
import logging
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pos_mcp_server import _load_line_token, _order_flex  # reuse flex builder + token loader

API = os.environ.get("POS_API_URL", "https://pos.m2igen.com/api").rstrip("/")
DEFAULT_TO = "U59a6080f40e4ac45f07b1ae17d41875f"
STATE_FILE = Path("/home/openhands/erp-stack/data/order_alarm_state.json")

POLL_SEC = int(os.environ.get("ALARM_POLL_SEC", "30"))
REPEAT_SEC = int(os.environ.get("ALARM_REPEAT_SEC", "60"))
MAX_REPEATS = int(os.environ.get("ALARM_MAX_REPEATS", "20"))
# never ring orders older than this (restart must not replay ancient pendings)
MAX_AGE_SEC = int(os.environ.get("ALARM_MAX_AGE_SEC", "7200"))

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("order-alarm")


def api_get(path: str):
    req = urllib.request.Request(f"{API}{path}", headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def _env_token() -> str | None:
    """Token from env or erp-stack/.env (pm2 runs as openhands; openclaw.json is root-only)."""
    tok = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
    if tok:
        return tok
    try:
        for line in Path("/home/openhands/erp-stack/.env").read_text().splitlines():
            if line.startswith("LINE_CHANNEL_ACCESS_TOKEN="):
                return line.split("=", 1)[1].strip() or None
    except Exception:
        pass
    return None


def _targets() -> list[str]:
    """Push destinations: LINE_PUSH_TO env/.env may hold comma-separated user/group ids."""
    raw = os.environ.get("LINE_PUSH_TO", "")
    if not raw:
        for line in Path("/home/openhands/erp-stack/.env").read_text().splitlines():
            if line.startswith("LINE_PUSH_TO="):
                raw = line.split("=", 1)[1].strip()
                break
    ids = [t.strip().removeprefix("line:") for t in raw.split(",") if t.strip()]
    return ids or [DEFAULT_TO.removeprefix("line:")]


def push_line(order: dict, count: int) -> None:
    token = _env_token() or _load_line_token()
    if not token:
        log.warning("no LINE token; skip")
        return
    to_list = _targets()
    oid = order.get("order_id", "")
    alt = (f"\U0001f514 \u0e2d\u0e2d\u0e40\u0e14\u0e2d\u0e23\u0e4c\u0e43\u0e2b\u0e21\u0e48 {oid}!"
           if count == 1 else
           f"\u23f0 \u0e22\u0e31\u0e07\u0e44\u0e21\u0e48\u0e23\u0e31\u0e1a\u0e2d\u0e2d\u0e40\u0e14\u0e2d\u0e23\u0e4c {oid} (\u0e04\u0e23\u0e31\u0e49\u0e07\u0e17\u0e35\u0e48 {count})")
    messages = [{"type": "flex", "altText": alt, "contents": _order_flex(order)}]
    ok = 0
    for to in to_list:
        payload = {"to": to, "messages": messages}
        req = urllib.request.Request(
            "https://api.line.me/v2/bot/message/push",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                ok += 1 if r.status == 200 else 0
                log.info("pushed %s to %s (ring #%s, http %s)", oid, to[:8] + "…", count, r.status)
        except Exception as e:  # noqa: BLE001
            log.warning("push failed for %s: %s", to[:8] + "…", e)
    return ok


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False))
    tmp.replace(STATE_FILE)


def _age_sec(o: dict):
    """Seconds since created_at; None if unparseable (treat as too-old, never ring)."""
    try:
        from datetime import datetime
        return time.time() - datetime.fromisoformat(str(o.get("created_at", ""))).timestamp()
    except Exception:
        return None


def main() -> None:
    log.info("order-alarm started: poll=%ss repeat=%ss max=%s target=%s",
             POLL_SEC, REPEAT_SEC, MAX_REPEATS,
             os.environ.get("LINE_PUSH_TO", DEFAULT_TO))
    state = load_state()
    while True:
        try:
            orders = api_get("/pos/orders?limit=50")
            by_id = {o["order_id"]: o for o in orders if isinstance(o, dict)}
            pending = []
            for o in orders:
                if not isinstance(o, dict) or o.get("status") != "pending":
                    continue
                age = _age_sec(o)
                if age is not None and age <= MAX_AGE_SEC:
                    pending.append(o)
            now = time.time()

            for o in pending:
                oid = o["order_id"]
                ent = state.get(oid)
                if not ent:
                    push_line(o, 1)
                    state[oid] = {"count": 1, "last": now}
                elif (now - ent["last"] >= REPEAT_SEC
                      and ent["count"] < MAX_REPEATS):
                    push_line(o, ent["count"] + 1)
                    ent["count"] += 1
                    ent["last"] = now

            # anything no longer pending (or vanished from list) stops ringing
            for oid in list(state.keys()):
                if by_id.get(oid, {}).get("status") != "pending":
                    if oid in state:
                        del state[oid]
                        log.info("cleared %s (no longer pending)", oid)

            save_state(state)
        except Exception as e:  # noqa: BLE001
            log.error("cycle failed: %s", e)
        time.sleep(POLL_SEC)


if __name__ == "__main__":
    main()
