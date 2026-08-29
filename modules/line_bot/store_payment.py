"""
M2I App Store — Store Payment Gateway (ชำระเงินกลาง App Store)
==============================================================
ให้หน้า App Store (static index.html) ยิง API นี้ผ่าน nginx /line/store/* → 8140
โมดูลจ่ายเงินกลาง reuse จาก modules/payment (qr_promptpay + slipok + payment_flow)
ธุรกรรมทุกอันเขียนลง schema payment_transaction กลาง (schema-engine port 8100)

Flow:
  1. POST /store/checkout   { app_id, amount, app_name, user_token }
       → validate JWT (จาก auth module เดียวกัน จับ user ได้)
       → create_payment_order() ได้ tx_id + QR PromptPay
       → save QR.png ลง qr_static/ + track pending order ใน store_orders.json
       → return { tx_id, qr_url, promptpay_id, amount }
  2. GET  /store/order/{tx_id}   → สถานะออเดอร์ (pending / paid / expired)
  3. POST /store/verify    { tx_id, slip_url | slip_data, amount }
       → verify_and_complete() ตรวจสลิป SlipOK → completed
       → return { success, transaction }

ต้อง login ก่อนจ่าย (validate JWT Secret เดียวกับ auth module /api/auth → 8105)
"""

import os
import json
import time
import base64
import logging
import secrets
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

logger = logging.getLogger("store-payment")

# ── เส้นทางเก็บข้อมูลออเดอร์ store ──────────────────────────────────────────
_STORE_DIR = Path(__file__).parent / "store_data"
_STORE_DIR.mkdir(parents=True, exist_ok=True)
_ORDERS_FILE = _STORE_DIR / "store_orders.json"
QR_STATIC_DIR = Path(__file__).parent / "qr_static"
QR_STATIC_DIR.mkdir(parents=True, exist_ok=True)

# ── โหลด auth base (ใช้ forward token ให้ auth module ตรวจ — เป็น SSOT ของ user) ──
AUTH_BASE = os.environ.get("AUTH_BASE", "http://localhost:8101")

# ── Router ─────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/store", tags=["store-payment"])


# ============================================================
# ตัวช่วย: เก็บ/อ่านออเดอร์ store (json file, thread-safe พอใช้)
# ============================================================
def _load_orders() -> dict:
    if _ORDERS_FILE.exists():
        try:
            return json.loads(_ORDERS_FILE.read_text("utf-8"))
        except Exception:
            return {}
    return {}


def _save_orders(data: dict) -> None:
    _ORDERS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), "utf-8"
    )


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _validate_token(token: str) -> dict:
    """Validates user token by forwarding to auth module (:8101 /api/v1/auth/me).
    Returns user dict {id, email, name, member_tier}. This is the SSOT for identity;
    we do NOT decode JWT locally (auth module holds the secret)."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            resp = await client.get(
                f"{AUTH_BASE}/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ตรวจสอบบัญชีล้มเหลว: {e}")
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Token ไม่ถูกต้องหรือหมดอายุ กรุณาล็อกอินใหม่")
    data = resp.json()
    if not data.get("ok") or not data.get("user"):
        raise HTTPException(status_code=401, detail="ไม่สามารถระบุผู้ใช้ได้")
    return data["user"]


# Lazy import payment module (เพื่อไม่ให้ line_bot main ต้อง import ตรง ๆ ตอนขึ้น)
_flow = None
_pc = None


def _get_payment():
    global _flow, _pc
    if _flow is None:
        try:
            import sys
            _modules_dir = Path(__file__).parent.parent  # modules/
            if str(_modules_dir) not in sys.path:
                sys.path.insert(0, str(_modules_dir))
            from payment import payment_flow, payment_client
            _flow = payment_flow
            _pc = payment_client
        except Exception as e:
            logger.exception(f"payment module import failed: {e}")
            raise HTTPException(status_code=500, detail=f"ระบบจ่ายเงินไม่พร้อม: {e}")
    return _flow, _pc


# ============================================================
# DTO
# ============================================================
class CheckoutReq(BaseModel):
    app_id: str = Field(..., max_length=64)
    amount: float = Field(..., gt=0)
    app_name: str = ""
    user_token: str = ""


class VerifyReq(BaseModel):
    tx_id: str = ""
    order_id: str = ""          # รองรับ lookup ด้วย order id เอง
    slip_url: str = ""          # URL สลิป
    amount: float = 0           # ยอดที่ตั้งเรียกเก็บ (optional, default จาก order)


# ============================================================
# 1) POST /store/checkout
# ============================================================
@router.post("/checkout")
async def store_checkout(req: CheckoutReq):
    """สร้างออเดอร์จ่ายเงิน + คืน QR PromptPay ต้อง login ก่อน (user_token)."""
    if not req.user_token:
        raise HTTPException(status_code=401, detail="ต้องล็อกอินก่อนชำระเงิน")

    user = await _validate_token(req.user_token)
    user_id = user.get("id") or user.get("sub")
    user_email = user.get("email") or ""
    user_name = user.get("name") or ""

    flow, pc = _get_payment()

    # สร้าง payment order + QR (เขียน schema payment_transaction กลาง)
    order_ref = f"store-{req.app_id}-{int(time.time())}"
    try:
        result = flow.create_payment_order(
            amount=req.amount,
            source_app="m2i-store",
            description=f"M2I App Store — {req.app_name or req.app_id}",
            customer_id=user_id,
            customer_name=user_name or user_email or user_id,
            order_ref=order_ref,
            payment_method="promptpay",
            metadata={
                "app_id": req.app_id,
                "app_name": req.app_name or req.app_id,
                "source_web": "m2igen-store",
            },
            with_qr=True,
            provider="slipok",
        )
    except Exception as e:
        logger.exception(f"checkout create_payment_order failed: {e}")
        raise HTTPException(status_code=502, detail=f"สร้างออเดอร์จ่ายเงินล้มเหลว: {e}")

    tx = result["transaction"]
    qr = result.get("qr")
    tx_id = tx.get("tx_id")

    # บันทึก QR เป็นไฟล์เพื่อให้ browser นำไปโชว์ได้ (ผ่าน nginx /line/slip_qr/)
    qr_fname = None
    if qr and qr.get("base64_png"):
        qr_fname = f"store_{tx_id}.png"
        try:
            png_bytes = base64.b64decode(qr["base64_png"])
            (QR_STATIC_DIR / qr_fname).write_bytes(png_bytes)
        except Exception as e:
            logger.warning(f"save QR file failed: {e}")
            qr_fname = None

    # Track pending order ใน store_orders.json
    orders = _load_orders()
    orders[tx_id] = {
        "tx_id": tx_id,
        "record_id": tx.get("_id"),
        "app_id": req.app_id,
        "app_name": req.app_name or req.app_id,
        "amount": req.amount,
        "user_id": user_id,
        "customer_name": user_name or user_email or user_id,
        "order_ref": order_ref,
        "status": "pending",
        "created_at": _utcnow_iso(),
    }
    _save_orders(orders)

    # Public URL ของ QR (nginx /line/ rewrite → 8140 /slip_qr/)
    qr_url = f"/line/slip_qr/{qr_fname}" if qr_fname else None

    return {
        "ok": True,
        "tx_id": tx_id,
        "order_ref": order_ref,
        "amount": req.amount,
        "promptpay_id": qr.get("promptpay_id") if qr else None,
        "payload": qr.get("payload") if qr else None,
        "qr_url": qr_url,
        "expires_in_seconds": 15 * 60,
    }


# ============================================================
# 2) GET /store/order/{tx_id}
# ============================================================
@router.get("/order/{tx_id}")
async def store_status(tx_id: str):
    """ดูสถานะออเดอร์จ่ายเงิน (ตอบจาก store_orders.json + schema กลาง)."""
    orders = _load_orders()
    order = orders.get(tx_id)
    if not order:
        raise HTTPException(status_code=404, detail="ไม่พบออเดอร์")

    return {"ok": True, "order": order}


# ============================================================
# 3) POST /store/verify
# ============================================================
@router.post("/verify")
async def store_verify(req: VerifyReq):
    """ตรวจสลิปด้วย SlipOK แล้ว mark ออเดอร์จ่ายสำเร็จ."""
    flow, pc = _get_payment()

    orders = _load_orders()
    # หา order ด้วย tx_id หรือ record_id
    order = orders.get(req.tx_id)
    if not order and req.order_id:
        for o in orders.values():
            if o.get("order_ref") == req.order_id or str(o.get("record_id")) == req.order_id:
                order = o
                break
    if not order:
        raise HTTPException(status_code=404, detail="ไม่พบออเดอร์")

    record_id = order.get("record_id")
    # ถ้า client ส่ง tx_id มาแต่เราเก็บ record_id -> ใช้ record_id ตรวจ
    tx_id = req.tx_id or order.get("tx_id")

    try:
        result = flow.verify_and_complete(
            record_id=record_id,
            slip_url=req.slip_url or None,
            slip_data=None,
            slip_file=None,
            log=True,
            expected_amount=req.amount or order.get("amount"),
            check_receiver=True,
            force_complete=False,
        )
    except Exception as e:
        logger.warning(f"verify slip failed: {e}")
        raise HTTPException(status_code=400, detail=f"ตรวจสลิปไม่สำเร็จ: {e}")

    # อัปเดต store order
    order["status"] = "paid"
    order["paid_at"] = _utcnow_iso()
    order["trans_ref"] = result.get("slip", {}).get("trans_ref")
    orders[tx_id] = order
    _save_orders(orders)

    return {
        "ok": True,
        "tx_id": tx_id,
        "status": "paid",
        "transaction": result.get("transaction"),
        "slip": result.get("slip"),
    }
