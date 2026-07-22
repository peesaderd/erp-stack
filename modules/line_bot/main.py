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

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware

from .line_client import line_client, CHANNEL_SECRET, CHANNEL_ACCESS_TOKEN
from .handlers import handle_webhook
from .line_richmenu import setup_rich_menus

logger = logging.getLogger("line-bot")

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


# ── Admin Routes ──────────────────────────────────────────────────────────

@app.post("/admin/richmenu/setup")
async def admin_setup_richmenu():
    """Force recreate rich menu."""
    menu_id = await setup_rich_menus(force=True)
    return {"ok": True, "richMenuId": menu_id}


@app.get("/admin/richmenu/list")
async def admin_list_richmenu():
    """List all rich menus."""
    from .line_richmenu import list_and_cleanup
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
