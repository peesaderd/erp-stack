"""
Bridge Server — ERP Stack Integration Layer

Receives webhooks from Plane, Planka, BookStack, OpenObserve
and syncs data between systems. All activity is logged to OpenObserve.
"""
import asyncio
import httpx
from fastapi import FastAPI, Request, HTTPException, Header

from config import settings

app = FastAPI(title="ERP Bridge Server", version="1.0.0")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def verify_secret(request: Request):
    """Verify X-Bridge-Secret header matches configured secret."""
    secret = request.headers.get("X-Bridge-Secret", "")
    if settings.secret_token and secret != settings.secret_token:
        raise HTTPException(status_code=403, detail="Invalid secret")


_openobserve_token: str | None = None


async def _get_openobserve_token() -> str | None:
    """Obtain OpenObserve auth token via login."""
    global _openobserve_token
    if _openobserve_token:
        return _openobserve_token
    if not settings.openobserve_login:
        return None
    url = f"{settings.openobserve_base_url}/api/{settings.openobserve_org}/auth/login"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(url, json={
                "login": settings.openobserve_login,
                "password": settings.openobserve_password,
            })
            if resp.status_code == 200:
                data = resp.json()
                _openobserve_token = data.get("token", {}).get("access_token", "")
                return _openobserve_token
    except Exception as exc:
        print(f"[Bridge] OpenObserve login failed: {exc}")
    return None


async def log_to_openobserve(level: str, source: str, event: str, data: dict):
    """Send a log entry to OpenObserve."""
    token = await _get_openobserve_token()
    if not token:
        return
    url = f"{settings.openobserve_base_url}/api/{settings.openobserve_org}/{settings.openobserve_stream}/_json"
    headers = {"Authorization": f"Bearer {token}"}
    payload = [{"level": level, "source": source, "event": event, "data": data}]
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, headers=headers, json=payload)
    except Exception as exc:
        print(f"[Bridge] Failed to log to OpenObserve: {exc}")


# ---------------------------------------------------------------------------
# Plane session auto-refresh
# ---------------------------------------------------------------------------

_plane_session_key: str | None = None


def _parse_session_cookie(cookie_str: str) -> str | None:
    """Extract session-id value from 'session-id=xxx' format."""
    if not cookie_str:
        return None
    for part in cookie_str.split(";"):
        part = part.strip()
        if part.startswith("session-id="):
            return part[len("session-id="):]
    if cookie_str.startswith("session-id="):
        return cookie_str[len("session-id="):]
    return cookie_str if cookie_str else None


async def refresh_plane_session():
    """Login to Plane and update the session cookie in settings."""
    global _plane_session_key
    csrf_url = f"{settings.plane_base_url}/auth/get-csrf-token/"
    login_url = f"{settings.plane_base_url}/auth/sign-in/"
    async with httpx.AsyncClient(timeout=10) as client:
        # Step 1: get CSRF token
        resp = await client.get(csrf_url)
        csrf_token = resp.json().get("csrf_token", "")
        csrfcookie = resp.cookies.get("csrftoken", "")
        # Step 2: login with form data
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": csrf_token,
            "Referer": settings.plane_base_url,
        }
        if csrfcookie:
            client.cookies.set("csrftoken", csrfcookie)
        login_resp = await client.post(
            login_url,
            data={"email": settings.plane_email, "password": settings.plane_password},
            headers=headers,
            follow_redirects=False,
        )
        session_key = login_resp.cookies.get("session-id")
        if session_key:
            _plane_session_key = session_key
            settings.plane_cookie = f"session-id={session_key}"
            print(f"[Bridge] Plane session refreshed: {session_key[:16]}...")
            return True
        print(f"[Bridge] Plane session refresh failed (status={login_resp.status_code})")
        return False


def get_plane_session_cookie() -> str:
    """Return the current Plane session cookie value."""
    if _plane_session_key:
        return f"session-id={_plane_session_key}"
    return settings.plane_cookie


# ---------------------------------------------------------------------------
# Webhook: Plane
# ---------------------------------------------------------------------------

@app.post("/webhooks/plane")
async def webhook_plane(request: Request):
    await verify_secret(request)
    body = await request.json()
    event = body.get("event", "unknown")
    payload = body.get("payload", body)

    print(f"[Plane Webhook] event={event}")

    # Log to OpenObserve
    await log_to_openobserve("info", "plane", event, payload)

    # --- Sync logic ---
    if event in ("issue_created", "issue_updated"):
        # Forward to Planka as a card
        await _sync_plane_issue_to_planka(payload)
        # Forward to BookStack as a doc page
        await _sync_plane_issue_to_bookstack(payload)

    return {"status": "ok", "event": event}


async def _sync_plane_issue_to_planka(issue: dict):
    """Create/update a Planka card from a Plane issue."""
    if not settings.planka_api_token:
        return
    name = issue.get("name", issue.get("title", "Untitled"))
    # Map Plane state to Planka list
    state = (issue.get("state", {}) or {}).get("name", "Backlog")
    list_map = {
        "Backlog": "1778282670761968654",      # 📋 รอทำ
        "Todo": "1778282670761968654",
        "In Progress": "1778282670317372429",   # 🔄 กำลังทำ
        "Done": "1778282669436568588",          # ✅ เสร็จแล้ว
        "Cancelled": "1778282669436568588",
    }
    list_id = list_map.get(state, "1778282670761968654")
    url = f"{settings.planka_base_url}/api/lists/{list_id}/cards"
    headers = {
        "X-API-Key": settings.planka_api_token,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            await client.post(url, headers=headers, json={
                "name": f"[Plane] {name}",
                "type": "project",
                "position": 1,
            })
        except Exception as exc:
            print(f"[Bridge] Planka sync failed: {exc}")


async def _sync_plane_issue_to_bookstack(issue: dict):
    """Create/update a BookStack page from a Plane issue."""
    if not settings.bookstack_token_id:
        return
    name = issue.get("name", issue.get("title", "Untitled"))
    description = issue.get("description", "") or ""
    url = f"{settings.bookstack_base_url}/api/pages"
    headers = {
        "Authorization": f"Token {settings.bookstack_token_id}:{settings.bookstack_token_secret}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            await client.post(url, headers=headers, json={
                "name": f"[Plane] {name}",
                "html": f"<p>{description}</p><p><em>Auto-synced from Plane</em></p>",
                "book_id": 1,
            })
        except Exception as exc:
            print(f"[Bridge] BookStack sync failed: {exc}")


# ---------------------------------------------------------------------------
# Webhook: Planka
# ---------------------------------------------------------------------------

@app.post("/webhooks/planka")
async def webhook_planka(request: Request):
    await verify_secret(request)
    body = await request.json()
    event = body.get("event", body.get("action", "unknown"))
    payload = body.get("data", body)

    print(f"[Planka Webhook] event={event}")
    await log_to_openobserve("info", "planka", event, payload)

    if event in ("cardCreate", "cardUpdate"):
        card_name = payload.get("name", "Untitled")
        await log_to_openobserve("info", "planka", "card_synced", {
            "name": card_name, "event": event,
        })

    return {"status": "ok", "event": event}


# ---------------------------------------------------------------------------
# Webhook: BookStack
# ---------------------------------------------------------------------------

@app.post("/webhooks/bookstack")
async def webhook_bookstack(request: Request):
    await verify_secret(request)
    body = await request.json()
    event = body.get("event", body.get("action", "unknown"))
    payload = body.get("data", body)

    print(f"[BookStack Webhook] event={event}")
    await log_to_openobserve("info", "bookstack", event, payload)

    return {"status": "ok", "event": event}


# ---------------------------------------------------------------------------
# Webhook: OpenObserve Alert
# ---------------------------------------------------------------------------

@app.post("/webhooks/openobserve")
async def webhook_openobserve(request: Request):
    await verify_secret(request)
    body = await request.json()
    print(f"[OpenObserve Alert] {body}")
    await log_to_openobserve("warn", "openobserve", "alert", body)
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Health & Status
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "service": "bridge-server"}


@app.get("/api/status")
async def status():
    """Show which services are configured."""
    return {
        "plane": bool(settings.plane_cookie),
        "planka": bool(settings.planka_api_token),
        "bookstack": bool(settings.bookstack_token_id and settings.bookstack_token_secret),
        "openobserve": bool(settings.openobserve_login),
    }


@app.post("/api/plane/refresh-session")
async def manual_refresh_plane_session():
    """Manually trigger a Plane session refresh."""
    ok = await refresh_plane_session()
    return {"status": "ok" if ok else "error"}


# ---------------------------------------------------------------------------
# Startup: refresh Plane session on boot
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_refresh():
    """Refresh Plane session on startup if credentials are configured."""
    if settings.plane_password:
        await refresh_plane_session()


# ---------------------------------------------------------------------------
# Manual sync endpoints (for testing / one-off use)
# ---------------------------------------------------------------------------

@app.post("/api/sync/plane-to-planka")
async def manual_sync_plane_to_planka(issue_name: str = "Test Issue"):
    """Manually trigger a Plane → Planka sync."""
    await _sync_plane_issue_to_planka({"name": issue_name, "state": {"name": "Backlog"}})
    return {"status": "ok", "message": f"Synced '{issue_name}' to Planka"}


@app.post("/api/sync/plane-to-bookstack")
async def manual_sync_plane_to_bookstack(issue_name: str = "Test Issue"):
    """Manually trigger a Plane → BookStack sync."""
    await _sync_plane_issue_to_bookstack({"name": issue_name, "description": "Manual sync"})
    return {"status": "ok", "message": f"Synced '{issue_name}' to BookStack"}
