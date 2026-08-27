"""
Payment Client — Payment Module กลาง (SSOT บน Schema Engine)

ผูกกับ schema-engine (PostgreSQL) เป็น SSOT กลางของธุรกรรมการเงิน
schema: payment_transaction (สร้างไว้ 2026-08-27)

ให้ทุกโปรเจกต์ reuse ได้ (calm-noether / M2I gen, passport, POS ฯลฯ):
- calm-noether ใช้จ่าย Stripe (card + QR PromptPay)
- passport ใช้ผูกกับ commerce_order ผ่าน order_ref / m2i_payment_ref

Pattern เดียวกับ modules/passport/commerce_client.py และ modules/reward/schema_client.py
POST/PUT: ส่ง fields flat ใน request body
GET: fields อยู่ใน record["data"]

Response shape ของ schema-engine (create/get):
  { "success": true, "record": { "id", "schema_id", "data": {...}, "created_at", ... } }
  List: { "success": true, "data": [ { "id", "data": {...} }, ... ] }

⚠️ สิ่งสำคัญ: schema-engine ใช้ record id แบบ uuid สำหรับ GET/PUT
   ทุกฟังก์ชันคืน field dict พร้อม `_id` (record id) แนบมาให้ใช้ต่อตอน update
   อย่าใช้ tx_id (เช่น "TX-AB12") กับ path GET/PUT เพราะเป็นแค่ field ไม่ใช่ record id
"""

import json
import uuid

import urllib.request
import urllib.error
import logging
from typing import Optional

_SCHEMA_ENGINE_URL = "http://localhost:8100"

SCHEMA_PAYMENT = "payment_transaction"

logger = logging.getLogger("payment.client")

# HTTP status codes
_HTTP_CONFLICT = 409


class PaymentError(Exception):
    """Base error for payment client."""
    pass


class DuplicateError(PaymentError):
    """Record already exists (409 conflict)."""
    pass


def _api(method: str, path: str, data: Optional[dict] = None) -> Optional[dict]:
    """Call Schema Engine API. Raises on transport errors."""
    url = f"{_SCHEMA_ENGINE_URL}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method=method
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        logger.error("Schema API %s %s -> %s: %s", method, path, e.code, err_body[:300])
        if e.code == _HTTP_CONFLICT:
            raise DuplicateError(f"Conflict: {err_body[:200]}")
        raise PaymentError(f"{method} {path} failed: {e.code} {err_body[:300]}")
    except (urllib.error.URLError, ConnectionError) as e:
        logger.error("Schema API %s %s transport error: %s", method, path, e)
        raise PaymentError(f"{method} {path} unreachable: {e}")


def _get_fields(record: Optional[dict]) -> dict:
    """Normalize: fields may be top-level or under record['data']."""
    if not record:
        return {}
    return record.get("data") or record


def _extract_record(record: Optional[dict]) -> dict:
    """Normalize a single record (from create/get) into fields dict with _id attached."""
    fields = _get_fields(record)
    if isinstance(record, dict) and record.get("id"):
        fields["_id"] = record["id"]
    return fields


def _extract_records(result: Optional[dict]) -> list:
    """Normalize GET list result into a list of field dicts (each with _id)."""
    if not result or not result.get("success"):
        return []
    data = result.get("data", [])
    if isinstance(data, list):
        out = []
        for item in data:
            rec = _get_fields(item)
            rec["_id"] = item.get("id") if isinstance(item, dict) else None
            out.append(rec)
        return out
    return [_extract_record(data)] if data else []


def _create(schema: str, field_data: dict) -> dict:
    """Create a record and return normalized field dict with _id."""
    result = _api("POST", f"/api/v1/data/{schema}", field_data)
    if not result or not result.get("success"):
        raise PaymentError("Create failed")
    return _extract_record(result.get("record") or result.get("data"))


def _update(schema: str, record_id: str, field_data: dict) -> Optional[dict]:
    """Update a record by its record id (uuid); return normalized dict with _id."""
    result = _api("PUT", f"/api/v1/data/{schema}/{record_id}", field_data)
    if result and result.get("success"):
        return _extract_record(result.get("record") or result.get("data"))
    return None


def _get(schema: str, record_id: str) -> Optional[dict]:
    """Get one record by its record id (uuid)."""
    result = _api("GET", f"/api/v1/data/{schema}/{record_id}")
    if result and result.get("success"):
        return _extract_record(result.get("record") or result.get("data"))
    return None


# ---------------------------------------------------------------------------
# Transaction (payment_transaction) — SSOT ของธุรกรรมการเงิน
# ---------------------------------------------------------------------------

def gen_tx_id() -> str:
    """Generate a unique transaction id, e.g. TX-<uuid8>."""
    return "TX-" + uuid.uuid4().hex[:8].upper()


def create_transaction(field_data: dict) -> dict:
    """Create a pending payment transaction. Returns field dict with _id."""
    data = dict(field_data)
    if not data.get("tx_id"):
        data["tx_id"] = gen_tx_id()
    return _create(SCHEMA_PAYMENT, data)


def get_transaction(record_id: str) -> Optional[dict]:
    """Get one transaction by its record id (uuid)."""
    return _get(SCHEMA_PAYMENT, record_id)


def find_by_tx_id(tx_id: str) -> Optional[dict]:
    """Find transaction by its tx_id field (unique). Returns field dict with _id or None."""
    result = _api("GET", f"/api/v1/data/{SCHEMA_PAYMENT}?search={tx_id}&limit=1")
    records = _extract_records(result)
    for r in records:
        if r.get("tx_id") == tx_id:
            return r
    return None


def list_transactions(limit: int = 50, offset: int = 0, status: str = "",
                      source_app: str = "", payment_method: str = "",
                      search: str = "") -> list:
    """List transactions with optional filters. Returns field dicts each with _id."""
    params = f"?limit={limit}&offset={offset}"
    if status:
        params += f"&status={status}"
    if source_app:
        params += f"&source_app={source_app}"
    if payment_method:
        params += f"&payment_method={payment_method}"
    if search:
        params += f"&search={search}"
    result = _api("GET", f"/api/v1/data/{SCHEMA_PAYMENT}{params}")
    return _extract_records(result)


def update_transaction(record_id: str, field_data: dict) -> Optional[dict]:
    """Update a transaction by its record id (uuid)."""
    return _update(SCHEMA_PAYMENT, record_id, field_data)


def complete_transaction(record_id: str, stripe_session_id: str = "",
                         stripe_payment_intent: str = "",
                         stripe_event_id: str = "",
                         completed_at: str = None) -> Optional[dict]:
    """Mark a transaction (by record id) as completed + store stripe references."""
    from datetime import datetime
    data = {
        "status": "completed",
        "stripe_session_id": stripe_session_id or None,
        "stripe_payment_intent": stripe_payment_intent or None,
        "stripe_event_id": stripe_event_id or None,
        "completed_at": completed_at or datetime.utcnow().isoformat() + "Z",
    }
    return update_transaction(record_id, data)


def create_pending(amount: float, payment_method: str, source_app: str,
                   description: str = "", customer_name: str = "",
                   customer_id: str = "", order_ref: str = "",
                   currency: str = "THB", metadata: dict = None) -> dict:
    """Convenience helper: create a pending transaction in one call.
    Returns field dict with _id (ใช้ _id ต่อตอน complete/update)."""
    data = {
        "tx_id": gen_tx_id(),
        "amount": amount,
        "currency": currency,
        "payment_method": payment_method,
        "status": "pending",
        "source_app": source_app,
        "description": description,
        "customer_name": customer_name,
        "customer_id": customer_id,
        "order_ref": order_ref,
        "metadata_json": json.dumps(metadata, ensure_ascii=False) if metadata else None,
    }
    return create_transaction(data)
