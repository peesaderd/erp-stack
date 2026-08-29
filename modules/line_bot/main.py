"""
LINE Bot Service — FastAPI Application
======================================
LINE Messaging API integration for ERP Stack
Features:
  - Webhook handler for LINE events
  - POS ordering (menu, cart, checkout)
  - Rich Menu management
  - Integration with ERP Modular

Webhook URL: POST /webhook
Health:      GET /health
"""

import os
import json
import hashlib
import hmac
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from line_client import line_client, CHANNEL_SECRET, CHANNEL_ACCESS_TOKEN
from handlers import handle_webhook
from line_richmenu import setup_rich_menus
from store_payment import router as store_payment_router

logger = logging.getLogger("line-bot")

# ── โหลด .env จาก root ของ erp-stack (SlipOK / PromptPay / ฯลฯ) ─────────────
# pm2 `env_file` อาจไม่อ่าน env เข้า child process เสมอไป (โดยเฉพาะหลัง restart) →
# โหลดตรง ๆ เพื่อให้ process มี SLIPOK_BRANCH_ID / SLIPOK_API_KEY / PROMPTPAY_ID เสมอ
_env_path = Path(__file__).resolve().parents[2] / ".env"  # /home/openhands/erp-stack/.env
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path, override=False)
        logger.info(f"Loaded env file: {_env_path}")
    except Exception as _e:  # pragma: no cover
        logger.warning(f"dotenv load failed ({_e}); relying on process env")
else:
    logger.warning(f".env not found at {_env_path}; using process env only")

# Static dir สำหรับเก็บ QR PromptPay ชั่วคราว (เสิร์ฟผ่าน /slip_qr/*)
QR_STATIC_DIR = Path(__file__).parent / "qr_static"
QR_STATIC_DIR.mkdir(parents=True, exist_ok=True)

# ── Lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown."""
    logger.info("LINE Bot Service starting...")

    # Verify LINE token
    if CHANNEL_ACCESS_TOKEN:
        verify = await line_client.verify()
        logger.info(f"LINE API verified: {verify.get('client_id', 'unknown')}")
    else:
        logger.warning("LINE_CHANNEL_ACCESS_TOKEN not set — bot won't work!")

    # Try setting up rich menu
    try:
        await setup_rich_menus(force=False)
    except Exception as e:
        logger.warning(f"Rich menu setup skipped: {e}")

    yield

    # Shutdown
    await line_client.close()
    logger.info("LINE Bot Service stopped")


app = FastAPI(
    title="LINE Bot Service",
    description="LINE Messaging API Bot — Order food, view menu, manage cart",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── M2I App Store — ชำระเงินกลาง (ต้อง login ก่อนจ่าย) ─────────────────────
app.include_router(store_payment_router)


# ── LINE Signature Verification ───────────────────────────────────────────

def _verify_signature(body: bytes, signature: str) -> bool:
    """Verify LINE webhook signature using channel secret."""
    if not CHANNEL_SECRET:
        logger.warning("CHANNEL_SECRET not set — skipping signature verification")
        return True
    if not signature:
        logger.warning("No signature in request")
        return False
    expected = hmac.new(
        CHANNEL_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


# ── Routes ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "ok": True,
        "module": "line-bot",
        "version": "1.0.0",
        "line_configured": bool(CHANNEL_ACCESS_TOKEN),
    }


@app.get("/webhook")
async def webhook_get():
    """LINE webhook verification (GET is for verification only)."""
    return PlainTextResponse(content="LINE Bot Webhook is active")


@app.post("/webhook")
async def webhook_post(request: Request):
    """
    Main webhook endpoint for LINE Messaging API.
    LINE sends events here.
    """
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    # Verify signature
    if not _verify_signature(body, signature):
        logger.warning(f"Invalid signature received (sig={signature[:20]}...)")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Parse events
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Invalid JSON body")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Handle events (async, non-blocking)
    await handle_webhook(data, signature)

    # LINE requires 200 OK response within 5 seconds
    return JSONResponse(content={"ok": True})


# ── GPS Queue Webhook ──────────────────────────────────────────────────────

# In-memory mapping: customer_name → user_id (populated on check-in)
_customer_user_map: dict[str, str] = {}

@app.post("/webhook/queue/checkin")
async def webhook_queue_checkin(request: Request):
    """Called by GPS Queue when a LINE user checks in — stores name→user_id mapping."""
    body = await request.json()
    customer_name = body.get("customer_name", "")
    user_id = body.get("user_id", "")
    if customer_name and user_id:
        _customer_user_map[customer_name] = user_id
        logger.info(f"Mapped customer '{customer_name}' → LINE {user_id[:8]}...")
        return {"ok": True}
    return JSONResponse(status_code=400, content={"error": "customer_name and user_id required"})

@app.post("/webhook/queue/notify")
async def webhook_queue_notify(request: Request):
    """Called by GPS Queue when a ticket is called — pushes notification to LINE user."""
    body = await request.json()
    customer_name = body.get("customer_name", "")
    ticket = body.get("ticket", "")
    message = body.get("message", "")
    notify_type = body.get("type", "called")  # called, completed, cancelled

    # Look up user_id from mapping
    user_id = _customer_user_map.get(customer_name, "")
    if not user_id:
        # Try partial match
        for name, uid in _customer_user_map.items():
            if customer_name in name or name in customer_name:
                user_id = uid
                break

    if not user_id:
        logger.warning(f"No LINE user found for customer '{customer_name}'")
        return {"ok": False, "error": "user not mapped"}

    # Build notification message
    if not message:
        if notify_type == "called":
            message = f"📢 **คิวของคุณถูกเรียกแล้ว!**\n\n🎫 หมายเลข: {ticket}\n\nกรุณาไปที่เคาน์เตอร์ครับ"
        elif notify_type == "completed":
            message = f"✅ **คิว {ticket} เสร็จสิ้นแล้ว**\n\nขอบคุณที่มาใช้บริการครับ!"
        elif notify_type == "cancelled":
            message = f"❌ **คิว {ticket} ถูกยกเลิก**"
        else:
            message = f"🔔 แจ้งเตือน: {ticket} — {notify_type}"

    # Push notification
    from line_client import line_client
    status, _ = await line_client.push(user_id, [line_client.text(message)])
    logger.info(f"Pushed {notify_type} notification to {customer_name} (LINE {user_id[:8]}...): {status}")
    return {"ok": status == 200}


# ── Admin Routes ──────────────────────────────────────────────────────────

@app.post("/admin/richmenu/setup")
async def admin_setup_richmenu():
    """Force recreate rich menu."""
    menu_id = await setup_rich_menus(force=True)
    return {"ok": True, "richMenuId": menu_id}


@app.get("/admin/richmenu/list")
async def admin_list_richmenu():
    """List all rich menus."""
    from line_richmenu import list_and_cleanup
    menus = await list_and_cleanup()
    return {"ok": True, "richmenus": menus}


@app.post("/admin/richmenu/unlink/{user_id}")
async def admin_unlink_richmenu(user_id: str):
    """Unlink rich menu from a user."""
    await line_client.unlink_rich_menu(user_id)
    return {"ok": True, "message": f"Unlinked rich menu from {user_id}"}


@app.post("/admin/push")
async def admin_push(user_id: str, message: str):
    """Push a message to a user."""
    status, _ = await line_client.push(user_id, [line_client.text(message)])
    return {"ok": status == 200}


@app.get("/admin/profile/{user_id}")
async def admin_profile(user_id: str):
    """Get LINE profile."""
    profile = await line_client.get_profile(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"ok": True, "profile": {
        "display_name": profile.display_name,
        "picture_url": profile.picture_url,
        "status_message": profile.status_message,
    }}


# ── PromptPay QR static serving ────────────────────────────────────────────────
@app.get("/slip_qr/{fname}")
async def serve_slip_qr(fname: str):
    """Serve a stored PromptPay QR PNG by filename (used as LINE image URL).
    Access via https://m2igen.com/line/slip_qr/<fname>.png (nginx /line/ → 8140)."""
    if not fname.endswith(".png"):
        raise HTTPException(status_code=400, detail="Only .png allowed")
    # ป้องกัน path traversal
    safe = Path(fname).name
    path = QR_STATIC_DIR / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail="QR not found")
    return FileResponse(str(path), media_type="image/png")
