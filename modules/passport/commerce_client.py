"""
Commerce Client — Schema Engine CRUD wrapper สำหรับระบบสั่งซื้อ + จัดส่ง

ผูกกับ schema-engine (PostgreSQL) เป็น SSOT กลาง:
- customer_profile : ลูกค้า (SSOT)
- commerce_order   : ใบสั่งซื้อออนไลน์
- delivery         : การจัดส่ง

Pattern เดียวกับ modules/reward/schema_client.py
POST/PUT: ส่ง fields flat ใน request body
GET: fields อยู่ใน record["data"]

Response shape ของ schema-engine (create/get):
  { "success": true, "record": { "id", "schema_id", "data": {...}, "created_at", ... } }
  List: { "success": true, "data": [ { "id", "data": {...} }, ... ] }
"""

import json
import urllib.request
import urllib.error
import logging
from typing import Optional

_SCHEMA_ENGINE_URL = "http://localhost:8100"

SCHEMA_CUSTOMER = "customer_profile"
SCHEMA_ORDER = "commerce_order"
SCHEMA_DELIVERY = "delivery"

logger = logging.getLogger("passport.commerce")

# HTTP status codes
_HTTP_CONFLICT = 409


class CommerceError(Exception):
    """Base error for commerce client."""
    pass


class DuplicateError(CommerceError):
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
        return None
    except Exception as e:
        logger.error("Schema API %s %s -> %s", method, path, e)
        raise CommerceError(str(e))


def _get_fields(record: Optional[dict]) -> dict:
    """Extract field data from a record (handles 'data' wrapper or flat dict)."""
    if not record:
        return {}
    if isinstance(record, dict) and "data" in record and isinstance(record["data"], dict):
        return record["data"]
    return record if isinstance(record, dict) else {}


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


# ── Customer (SSOT) ──────────────────────────────────────────────────

def find_customer_by_phone(phone: str) -> Optional[dict]:
    """Find customer by phone (SSOT). Returns fields dict or None."""
    result = _api("GET", f"/api/v1/data/{SCHEMA_CUSTOMER}?phone={phone}&limit=1")
    records = _extract_records(result)
    return records[0] if records else None


def find_customer_by_line(line_user_id: str) -> Optional[dict]:
    """Find customer by LINE User ID. Returns fields dict or None."""
    result = _api("GET", f"/api/v1/data/{SCHEMA_CUSTOMER}?line_user_id={line_user_id}&limit=1")
    records = _extract_records(result)
    return records[0] if records else None


def get_customer(customer_id: str) -> Optional[dict]:
    """Get one customer by record id."""
    result = _api("GET", f"/api/v1/data/{SCHEMA_CUSTOMER}/{customer_id}")
    if result and result.get("success"):
        return _extract_record(result.get("record") or result.get("data"))
    return None


def create_customer(field_data: dict) -> Optional[dict]:
    """Create a customer record."""
    result = _api("POST", f"/api/v1/data/{SCHEMA_CUSTOMER}", field_data)
    if result and result.get("success"):
        return _extract_record(result.get("record") or result.get("data"))
    return None


def upsert_customer(field_data: dict) -> dict:
    """Find customer by phone; create if missing. Returns customer fields dict with _id."""
    existing = None
    phone = field_data.get("phone")
    if phone:
        existing = find_customer_by_phone(phone)
    if existing and existing.get("_id"):
        return existing
    created = create_customer(field_data)
    if not created:
        raise CommerceError("Create customer failed")
    return created


# ── Commerce Order ───────────────────────────────────────────────────

def create_order(field_data: dict) -> dict:
    """Create a commerce_order record."""
    result = _api("POST", f"/api/v1/data/{SCHEMA_ORDER}", field_data)
    if not result or not result.get("success"):
        raise CommerceError("Create order failed")
    return _extract_record(result.get("record") or result.get("data"))


def get_order(order_id: str) -> Optional[dict]:
    """Get one order by record id."""
    result = _api("GET", f"/api/v1/data/{SCHEMA_ORDER}/{order_id}")
    if result and result.get("success"):
        return _extract_record(result.get("record") or result.get("data"))
    return None


def get_order_by_number(order_number: str) -> Optional[dict]:
    """Get order by order_number."""
    result = _api("GET", f"/api/v1/data/{SCHEMA_ORDER}?order_number={order_number}&limit=1")
    records = _extract_records(result)
    return records[0] if records else None


def list_orders(limit: int = 50, offset: int = 0, status: str = "", line_user_id: str = "") -> list:
    """List orders with optional filters (status, line_user_id)."""
    params = f"?limit={limit}&offset={offset}"
    if status:
        params += f"&status={status}"
    if line_user_id:
        params += f"&line_user_id={line_user_id}"
    result = _api("GET", f"/api/v1/data/{SCHEMA_ORDER}{params}")
    return _extract_records(result)


def update_order(order_id: str, field_data: dict) -> Optional[dict]:
    """Update order fields (status, payment_status, etc.)."""
    result = _api("PUT", f"/api/v1/data/{SCHEMA_ORDER}/{order_id}", field_data)
    if result and result.get("success"):
        return _extract_record(result.get("record") or result.get("data"))
    return None


# ── Delivery ─────────────────────────────────────────────────────────

def create_delivery(field_data: dict) -> dict:
    """Create a delivery record (linked to order_id)."""
    result = _api("POST", f"/api/v1/data/{SCHEMA_DELIVERY}", field_data)
    if not result or not result.get("success"):
        raise CommerceError("Create delivery failed")
    return _extract_record(result.get("record") or result.get("data"))


def get_delivery(delivery_id: str) -> Optional[dict]:
    """Get one delivery by record id."""
    result = _api("GET", f"/api/v1/data/{SCHEMA_DELIVERY}/{delivery_id}")
    if result and result.get("success"):
        return _extract_record(result.get("record") or result.get("data"))
    return None


def get_delivery_by_order(order_id: str) -> Optional[dict]:
    """Get delivery for a given order (field filter)."""
    result = _api("GET", f"/api/v1/data/{SCHEMA_DELIVERY}?order_id={order_id}&limit=1")
    records = _extract_records(result)
    return records[0] if records else None


def update_delivery(delivery_id: str, field_data: dict) -> Optional[dict]:
    """Update delivery fields (status, tracking_number, etc.)."""
    result = _api("PUT", f"/api/v1/data/{SCHEMA_DELIVERY}/{delivery_id}", field_data)
    if result and result.get("success"):
        return _extract_record(result.get("record") or result.get("data"))
    return None
