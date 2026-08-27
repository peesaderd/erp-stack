"""
Payment Flow Orchestrator — ระบบจ่ายเงิน M2I Gen แบบครบวงจร

รวมทุกอย่างใน modules/payment เป็น flow เดียว:
  1. create_payment_order()  → สร้าง payment_transaction (pending) + สร้าง QR PromptPay
  2. verify_and_complete()   → ตรวจสลิปด้วย SlipOK + อัปเดต transactions เป็น completed
  3. release_access()        → hook ปล่อยสิทธิ์/สินค้าหลังชำระสำเร็จ (ให้แต่ละโปรเจกต์ override)

สถาปัตยกรรม (ตามที่พี่ตกลง):
  - QR PromptPay ใช้ของเราเอง (qr_promptpay.py, PROMPTPAY_ID จาก env, default 0993946144)
  - ตรวจยอด/สลิปจริงด้วย SlipOK (slipok_client.py; env SLIPOK_BRANCH_ID + SLIPOK_API_KEY)
  - บัตรเครดิตใช้ Stripe (ยังอยู่ภายนอก flow นี้ ผ่าน create_checkout-session ของ calm-noether)
  - ทุกธุรกรรมเขียนลง schema payment_transaction กลาง (payment_client.py)

โหมด SLIPOK_MODE:
  - "real"  : ตรวจสลิปจริงกับ SlipOK (default เมื่อตั้ง SLIPOK_BRANCH_ID + SLIPOK_API_KEY)
  - "mock"  : จำลองตรวจสำเร็จ (ใช้ตอนพัฒนา/ทดสอบ flow โดยไม่มีคีย์จริง) — NEVER ใช้ใน production
อ่านจาก env เดียวกับที่ slipok_client ใช้ (SLIPOK_BRANCH_ID มีค่า = real)
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

from payment import payment_client as pc
from payment import qr_promptpay
from payment import slipok_client

logger = logging.getLogger("payment.flow")


class PaymentFlowError(Exception):
    pass


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _slipok_ready() -> bool:
    return bool(os.environ.get("SLIPOK_BRANCH_ID") and os.environ.get("SLIPOK_API_KEY"))


# ---------------------------------------------------------------------------
# 1) สร้าง order + QR
# ---------------------------------------------------------------------------

def create_payment_order(
    amount: float,
    source_app: str,
    description: str = "",
    customer_name: str = "",
    customer_id: str = "",
    order_ref: str = "",
    currency: str = "THB",
    payment_method: str = "promptpay",
    metadata: dict = None,
    with_qr: bool = True,
    provider: str = "slipok",   # "slipok" | "stripe"
) -> dict:
    """Create a pending payment transaction (+ optional QR PromptPay PNG).

    Returns: {
      'transaction': {<fields>, _id},       # pending payment_transaction
      'qr': {payload, base64_png, amount, promptpay_id} | None,
    }
    """
    tx = pc.create_pending(
        amount=amount,
        payment_method=payment_method,
        source_app=source_app,
        description=description,
        customer_name=customer_name,
        customer_id=customer_id,
        order_ref=order_ref,
        currency=currency,
        metadata={
            **(metadata or {}),
            "provider": provider,
        },
    )
    if payment_method == "promptpay" and with_qr:
        qr = qr_promptpay.build_qr(amount=amount)
    else:
        qr = None
    return {"transaction": tx, "qr": qr}


# ---------------------------------------------------------------------------
# 2) Verify slip + complete
# ---------------------------------------------------------------------------

def verify_and_complete(
    record_id: str,
    slip_data: Optional[str] = None,
    slip_file=None,
    slip_url: Optional[str] = None,
    log: bool = True,
    expected_amount: Optional[float] = None,
    request_amount: Optional[float] = None,
    check_receiver: bool = True,
    force_complete: bool = False,
) -> dict:
    """Verify a slip via SlipOK, then mark the transaction completed.

    Args:
      record_id: _id (uuid) ของ payment_transaction ที่ pending อยู่
      slip_data / slip_file / slip_url: แหล่งของสลิป (อย่างใดอย่างหนึ่ง)
      request_amount: ยอดที่ตั้งเรียกเก็บใน transaction (ใช้เช็คกับสลิป)
      force_complete: ถ้า True จะ complete โดยไม่ผ่าน SlipOK (ใช้ตอน mock/บายพาส)

    Returns: { transaction, slip }
    Raises: PaymentFlowError (slip ตรวจไม่ผ่าน / ไม่ตรงยอด / ไม่ตรงบัญชี / not found)
    """
    tx = pc.get_transaction(record_id)
    if not tx:
        raise PaymentFlowError(f"Transaction not found: {record_id}")
    if tx.get("status") == "completed":
        logger.warning("Transaction %s already completed", record_id)
        return {"transaction": tx, "slip": {}}

    if force_complete:
        amount = request_amount if request_amount is not None else tx.get("amount")
        slip = {"verified": True, "amount": amount, "trans_ref": "MOCK-" + record_id[:8]}
    elif not _slipok_ready():
        raise PaymentFlowError(
            "SlipOK not configured (SLIPOK_BRANCH_ID / SLIPOK_API_KEY). "
            "Set them or pass force_complete=True in dev only."
        )
    else:
        expected_amount = expected_amount if expected_amount is not None else request_amount
        expected_receiver_account = qr_promptpay.promptpay_id() if check_receiver else None
        slip = slipok_client.verify_slip(
            payment_data=slip_data,
            file_upload=slip_file,
            url=slip_url,
            log=log,
            amount=expected_amount,
            expected_receiver_account=expected_receiver_account,
        )

    # อัปเดต refs + metadata + status completed ในครั้งเดียว (ไม่ทับ metadata)
    existing_meta = {}
    try:
        existing_meta = json.loads(tx.get("metadata_json") or "{}")
    except Exception:
        existing_meta = {}
    existing_meta.setdefault("slip", {})
    existing_meta["slip"].update({
        "trans_ref": slip.get("trans_ref"),
        "amount": slip.get("amount"),
        "verify_message": slip.get("message"),
        "provider": "slipok",
    })
    updated = pc.update_transaction(record_id, {
        "status": "completed",
        "completed_at": _now(),
        "payment_ref": slip.get("trans_ref"),
        "metadata_json": json.dumps(existing_meta, ensure_ascii=False),
    })
    return {"transaction": updated, "slip": slip}


# ---------------------------------------------------------------------------
# 3) Release access (hook)
# ---------------------------------------------------------------------------

def release_access(transaction: dict) -> None:
    """Hook: after payment completed, release product/access.
    Default no-op — แต่ละโปรเจกต์ override (eg. unlock bot license, deliver file)."""
    logger.info("release_access called for tx %s (override in your app)", transaction.get("tx_id"))
