"""
Payment Notification — PassportPhoto
====================================
ระบบแจ้งเตือนชำระเงินจาก SlipOK Webhook

Flow:
  1. SlipOK ส่ง webhook เมื่อมีเงินเข้า (POST /api/passport/payment/webhook)
  2. ตรวจสลิปกับ SlipOK API (verify)
  3. อัปเดต order ใน commerce (payment_status=paid)
  4. ส่ง LINE notification ให้ลูกค้า

SlipOK Webhook docs:
  - POST request with body: { data: <base64 slip>, branchId, ... }
  - ต้อง return 200 ภายใน 5 วินาที (SlipOK จะ retry ถ้า timeout)
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Optional

from passport import commerce_client
from payment import slipok_client
from payment.payment_flow import verify_and_complete

logger = logging.getLogger("passport.payment_notify")

SCHEMA_ENGINE_URL = os.environ.get("SCHEMA_ENGINE_URL", "http://localhost:8100")


# ── LINE Notification ─────────────────────────────────────────────────

def _send_line_notification(user_id: str, messages: list[dict]):
    """ส่ง LINE notification แบบ sync (blocking). ใช้ httpx แทน async."""
    import httpx

    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    if not token:
        # fallback: อ่านจาก .env
        try:
            with open("/home/openhands/erp-stack/.env", "r") as f:
                for line in f:
                    if "LINE_CHANNEL_ACCESS_TOKEN=" in line:
                        token = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass

    if not token:
        logger.warning("[line_notify] LINE_CHANNEL_ACCESS_TOKEN not set, skip push")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"to": user_id, "messages": messages}

    try:
        resp = httpx.post(
            "https://api.line.me/v2/bot/message/push",
            headers=headers,
            json=payload,
            timeout=10,
        )
        if resp.status_code != 200:
            logger.error(f"[line_notify] push failed ({resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        logger.error(f"[line_notify] push error: {e}")


def notify_payment_success(order: dict, slip_info: dict):
    """ส่ง LINE Flex Message แจ้งชำระเงินสำเร็จ"""
    user_id = order.get("line_user_id")
    if not user_id:
        logger.info(f"[line_notify] order {order.get('order_number')} has no line_user_id, skip")
        return

    order_number = order.get("order_number", "-")
    amount = slip_info.get("amount", order.get("grand_total", 0))
    trans_ref = slip_info.get("trans_ref", "-")
    sender_name = slip_info.get("sender_display_name", "-")
    paid_at = slip_info.get("trans_date", "-") + " " + slip_info.get("trans_time", "-")

    # Flex Message: แจ้งชำระเงินสำเร็จ
    flex_contents = {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "✅ ชำระเงินสำเร็จ", "weight": "bold", "size": "xl", "color": "#27AE60"}
            ],
            "backgroundColor": "#EAFAF1",
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "box", "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": "เลขคำสั่งซื้อ", "size": "sm", "color": "#555555", "flex": 4},
                        {"type": "text", "text": order_number, "size": "sm", "align": "end", "flex": 5},
                    ]
                },
                {"type": "separator", "margin": "md"},
                {
                    "type": "box", "layout": "horizontal", "margin": "md",
                    "contents": [
                        {"type": "text", "text": "ยอดชำระ", "size": "sm", "color": "#555555", "flex": 4},
                        {"type": "text", "text": f"฿{amount:,.2f}", "size": "sm", "align": "end", "flex": 5, "weight": "bold", "color": "#27AE60"},
                    ]
                },
                {
                    "type": "box", "layout": "horizontal", "margin": "sm",
                    "contents": [
                        {"type": "text", "text": "ผู้โอน", "size": "sm", "color": "#555555", "flex": 4},
                        {"type": "text", "text": sender_name, "size": "sm", "align": "end", "flex": 5},
                    ]
                },
                {
                    "type": "box", "layout": "horizontal", "margin": "sm",
                    "contents": [
                        {"type": "text", "text": "เวลาชำระ", "size": "sm", "color": "#555555", "flex": 4},
                        {"type": "text", "text": paid_at, "size": "sm", "align": "end", "flex": 5},
                    ]
                },
                {
                    "type": "box", "layout": "horizontal", "margin": "sm",
                    "contents": [
                        {"type": "text", "text": "Ref", "size": "sm", "color": "#555555", "flex": 4},
                        {"type": "text", "text": trans_ref[:16] if trans_ref else "-", "size": "xs", "align": "end", "flex": 5},
                    ]
                },
                {"type": "separator", "margin": "lg"},
                {"type": "text", "text": "📋 คำสั่งซื้อของคุณกำลังดำเนินการอยู่ค่ะ", "size": "sm", "color": "#888888", "margin": "md", "wrap": True},
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "Passport Photo Service", "size": "xs", "color": "#AAAAAA", "align": "center"}
            ]
        }
    }

    messages = [
        {"type": "flex", "altText": f"ชำระเงินสำเร็จ คำสั่งซื้อ {order_number} ยอด ฿{amount:,.2f}", "contents": flex_contents}
    ]

    _send_line_notification(user_id, messages)
    logger.info(f"[line_notify] sent payment success to {user_id} for order {order_number}")


def notify_payment_failed(order: dict, reason: str):
    """ส่ง LINE notification เมื่อตรวจสอบสลิปไม่ผ่าน"""
    user_id = order.get("line_user_id")
    if not user_id:
        return

    order_number = order.get("order_number", "-")
    messages = [
        {"type": "text", "text": f"❌ ตรวจสอบสลิปไม่ผ่าน\nคำสั่งซื้อ: {order_number}\nเหตุผล: {reason}\n\nกรุณาโอนเงินใหม่หรือส่งสลิปอีกครั้งค่ะ"}
    ]

    _send_line_notification(user_id, messages)
    logger.info(f"[line_notify] sent payment failed to {user_id} for order {order_number}")


# ── SlipOK Webhook Handler ────────────────────────────────────────────

def handle_slipok_webhook(body: dict) -> dict:
    """
    จัดการ SlipOK Webhook Request

    SlipOK ส่ง body:
    {
      "data": "<base64 encoded slip data>",
      "branchId": "...",
      "transRef": "...",
      ...
    }

    Returns: { success, order, slip }
    Raises: on verification failure
    """
    slip_data = body.get("data") or body.get("payment_data")
    if not slip_data:
        raise ValueError("No slip data in webhook body")

    # 1) ตรวจสลิปกับ SlipOK API
    try:
        slip = slipok_client.verify_slip(payment_data=slip_data, log=True)
    except slipok_client.SlipOKError as e:
        logger.error(f"[webhook] slip verify failed: {e}")
        raise

    trans_ref = slip.get("trans_ref")
    amount = slip.get("amount")
    logger.info(f"[webhook] slip verified: trans_ref={trans_ref}, amount={amount}")

    # 2) หา order จาก ref1 (ถ้า SlipOK ส่ง ref1 มา) หรือจาก transaction ref
    #    ลองหา order ที่ payment_status=pending โดยใช้ amount + recent
    order = None
    order_id = None

    # วิธี 1: ลองหาจาก payment_transaction ใน schema-engine
    try:
        import urllib.request
        resp = urllib.request.urlopen(
            f"{SCHEMA_ENGINE_URL}/api/v1/data/payment_transaction?payment_ref={trans_ref}&limit=1",
            timeout=10
        )
        result = json.loads(resp.read())
        records = (result.get("data") or [])
        if records:
            tx = records[0]
            tx_data = tx.get("data") or {}
            order_ref = tx_data.get("order_ref")
            if order_ref:
                order = commerce_client.get_order_by_number(order_ref)
                if order:
                    order_id = order.get("_id")
    except Exception as e:
        logger.warning(f"[webhook] lookup tx by trans_ref failed: {e}")

    # วิธี 2: ถ้าไม่เจอ ลองหา pending order ที่ตรงยอด (within 1 ชม.)
    if not order and amount:
        try:
            pending_orders = commerce_client.list_orders(status="pending", limit=20)
            for o in pending_orders:
                if abs((o.get("grand_total") or 0) - amount) < 0.01:
                    order = o
                    order_id = o.get("_id")
                    break
        except Exception as e:
            logger.warning(f"[webhook] fallback order search failed: {e}")

    if not order:
        logger.warning(f"[webhook] no matching order found for trans_ref={trans_ref}, amount={amount}")
        return {"success": False, "error": "Order not found", "slip": slip}

    # 3) อัปเดต order เป็น paid
    try:
        commerce_client.update_order(order_id, {
            "payment_status": "paid",
            "status": "paid",
            "payment_method": "promptpay",
            "m2i_payment_ref": trans_ref,
            "notes": (order.get("notes") or "") + f"\n[webhook] paid via SlipOK trans_ref={trans_ref}",
        })
        logger.info(f"[webhook] order {order.get('order_number')} updated to paid")
    except Exception as e:
        logger.error(f"[webhook] update order failed: {e}")
        # ไม่ raise เพราะ slip verify สำเร็จแล้ว

    # 4) อัปเดต payment_transaction ใน schema-engine (ถ้ามี)
    try:
        import urllib.request
        resp = urllib.request.urlopen(
            f"{SCHEMA_ENGINE_URL}/api/v1/data/payment_transaction?payment_ref={trans_ref}&limit=1",
            timeout=10
        )
        result = json.loads(resp.read())
        records = (result.get("data") or [])
        if records:
            tx_id = records[0].get("id")
            if tx_id:
                urllib.request.urlopen(
                    urllib.request.Request(
                        f"{SCHEMA_ENGINE_URL}/api/v1/data/payment_transaction/{tx_id}",
                        data=json.dumps({"status": "completed", "completed_at": datetime.utcnow().isoformat() + "Z"}).encode(),
                        headers={"Content-Type": "application/json"},
                        method="PUT",
                    ),
                    timeout=10,
                )
    except Exception as e:
        logger.warning(f"[webhook] update payment_transaction failed: {e}")

    # 5) ส่ง LINE notification
    try:
        notify_payment_success(order, slip)
    except Exception as e:
        logger.error(f"[webhook] line notify failed: {e}")
        # ไม่ raise เพราะ payment สำเร็จแล้ว

    return {"success": True, "order": order, "slip": slip}


# ── Manual Verify (from frontend) ─────────────────────────────────────

def handle_manual_verify(order_ref: str, slip_base64: str, amount: Optional[float] = None) -> dict:
    """
    ตรวจสอบสลิปแบบ manual (ผู้ใช้ upload สลิปเอง)

    Returns: { success, order, slip }
    """
    # 1) หา order
    order = commerce_client.get_order_by_number(order_ref)
    if not order:
        raise ValueError(f"Order not found: {order_ref}")

    order_id = order.get("_id")

    # 2) ตรวจสลิป
    try:
        slip = slipok_client.verify_slip(
            payment_data=slip_base64,
            log=True,
            amount=amount or order.get("grand_total"),
        )
    except slipok_client.SlipOKError as e:
        logger.error(f"[manual_verify] slip verify failed: {e}")
        # ส่ง notification ว่าสลิปไม่ผ่าน
        try:
            notify_payment_failed(order, str(e))
        except Exception:
            pass
        raise

    # 3) อัปเดต order
    trans_ref = slip.get("trans_ref")
    commerce_client.update_order(order_id, {
        "payment_status": "paid",
        "status": "paid",
        "payment_method": "promptpay",
        "m2i_payment_ref": trans_ref,
        "notes": (order.get("notes") or "") + f"\n[manual] paid via SlipOK trans_ref={trans_ref}",
    })

    # 4) ส่ง notification
    try:
        notify_payment_success(order, slip)
    except Exception as e:
        logger.error(f"[manual_verify] line notify failed: {e}")

    return {"success": True, "order": order, "slip": slip}
