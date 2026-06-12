"""
Remote Auth VNC Server - FastAPI service for remote TikTok auth via VNC.
"""
import asyncio
import json
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

BASE_DIR = Path(__file__).parent
SESSIONS_DIR = BASE_DIR / "sessions" / "remote"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

XVFB_DISPLAY = ":99"
VNC_PORT = 15900
WS_PORT = 6081

app = FastAPI()

# Track active sessions in memory
active_sessions: dict = {}
running_processes = {}


class StartRequest(BaseModel):
    account_id: str


@app.get("/health")
def health():
    return {"status": "ok", "display": XVFB_DISPLAY, "vnc": VNC_PORT, "active": len(active_sessions)}


@app.post("/start")
def start_session(req: StartRequest):
    """Start a VNC auth session for the given account."""
    account_id = req.account_id.lstrip("@")
    
    # Check for existing active session
    for sid, sess in active_sessions.items():
        if sess.get("account_id") == account_id and sess["status"] in ("starting", "waiting"):
            return {"session_id": sid, "vnc_url": sess["vnc_url"], "status": sess["status"]}
    
    session_id = uuid.uuid4().hex[:8]
    vnc_password = session_id
    
    # Ensure xvfb is running
    if not running_processes.get("xvfb") or running_processes["xvfb"].poll() is not None:
        xvfb = subprocess.Popen(
            ["Xvfb", XVFB_DISPLAY, "-screen", "0", "1280x720x24"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        running_processes["xvfb"] = xvfb
        time.sleep(1)
    
    # Ensure x11vnc is running
    if not running_processes.get("x11vnc") or running_processes["x11vnc"].poll() is not None:
        x11vnc = subprocess.Popen(
            ["x11vnc", "-display", XVFB_DISPLAY, "-forever",
             "-rfbport", str(VNC_PORT), "-passwd", "tkremote", "-quiet"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        running_processes["x11vnc"] = x11vnc
        time.sleep(1)
    
    # Ensure websockify is running
    if not running_processes.get("ws") or running_processes["ws"].poll() is not None:
        ws = subprocess.Popen(
            ["websockify", "--web=/usr/share/novnc", str(WS_PORT), f"localhost:{VNC_PORT}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        running_processes["ws"] = ws
        time.sleep(1)
    
    vnc_url = (
        f"https://openhands.m2igen.com/vnc/vnc.html"
        f"?host=openhands.m2igen.com&port=443&path=vnc/websockify&password={vnc_password}"
        f"&title=TikTok+Login&autoconnect=true&reconnect=true"
    )
    
    # Store session info
    session_info = {
        "session_id": session_id,
        "account_id": account_id,
        "status": "waiting",
        "vnc_url": vnc_url,
        "vnc_password": vnc_password,
        "created_at": time.time(),
        "expires_at": time.time() + 300,
        "token": None,
    }
    active_sessions[session_id] = session_info
    
    # Save to file
    with open(SESSIONS_DIR / f"{session_id}.json", "w") as f:
        json.dump(session_info, f)
    
    # Launch Playwright on the virtual display
    asyncio.create_task(launch_auth_browser(session_id, account_id))
    
    return {"session_id": session_id, "vnc_url": vnc_url, "status": "starting"}


@app.get("/status/{session_id}")
def get_status(session_id: str):
    """Check if the session has completed login."""
    session = active_sessions.get(session_id)
    if not session:
        # Try loading from file
        fp = SESSIONS_DIR / f"{session_id}.json"
        if fp.exists():
            with open(fp) as f:
                session = json.load(f)
    if not session:
        raise HTTPException(404, "Session not found")
    
    return {
        "session_id": session["session_id"],
        "account_id": session.get("account_id", ""),
        "status": session["status"],
        "has_token": session.get("token") is not None,
        "vnc_url": session.get("vnc_url", ""),
    }


async def launch_auth_browser(session_id: str, account_id: str):
    """Launch Playwright browser on the virtual display for TikTok login."""
    from playwright.async_api import async_playwright
    
    os.environ["DISPLAY"] = XVFB_DISPLAY
    session = active_sessions.get(session_id)
    if not session:
        return
    
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=False,
                args=[
                    "--no-sandbox", "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage", "--window-size=1280,720",
                ],
            )
            
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            page = await context.new_page()
            
            await page.goto("https://www.tiktok.com/login", wait_until="networkidle")
            session["status"] = "waiting"
            
            # Poll for session cookie
            for i in range(150):  # 5 min max
                try:
                    cookies = await context.cookies()
                    for c in cookies:
                        if "sessionid" in c["name"].lower() and c["value"]:
                            # Login detected!
                            token = base64.b64encode(
                                json.dumps(cookies).encode()
                            ).decode()
                            session["token"] = token
                            session["status"] = "success"
                            
                            # Write result
                            result = {
                                "status": "success",
                                "token": token,
                                "account_id": account_id,
                                "cookies": cookies,
                            }
                            with open(SESSIONS_DIR / f"{session_id}_result.json", "w") as f:
                                json.dump(result, f)
                            
                            await browser.close()
                            return
                except Exception:
                    pass
                
                await asyncio.sleep(2)
            
            session["status"] = "timeout"
            await browser.close()
            
    except Exception as e:
        if session_id in active_sessions:
            active_sessions[session_id]["status"] = "error"
            active_sessions[session_id]["error"] = str(e)
        print(f"[{session_id}] Error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8106)
