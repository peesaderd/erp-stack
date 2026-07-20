"""
Remote Auth Service — lets users login to TikTok from their phone via VNC/NoVNC.

Flow:
1. User clicks "Remote Login" on phone web UI
2. Server starts xvfb (virtual display) + x11vnc + websockify + Playwright
3. Playwright opens TikTok login on the virtual display
4. User receives a noVNC URL → opens on phone → sees TikTok page
5. User logs in manually (password / phone + SMS / Google / etc.)
6. Background script detects session cookie → saves session
7. VNC shuts down, token stored, user notified
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path


SESSIONS_DIR = Path(__file__).parent / "remote_sessions"
SESSIONS_DIR.mkdir(exist_ok=True)

XVFB_DISPLAY = ":99"
VNC_BASE_PORT = 15900
WS_PORT = 6081
VNC_ROOT = "/usr/share/novnc"


async def run_playwright(session_id: str, display: str, done_file: str):
    """Open TikTok login on the virtual display and monitor for session cookies."""
    import asyncio
    from playwright.async_api import async_playwright

    os.environ["DISPLAY"] = display

    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(
                headless=False,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    f"--window-size=1280,720",
                ],
            )

            page = await browser.new_page(
                viewport={"width": 1280, "height": 720},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

            # Navigate to TikTok login
            await page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # Poll for session cookies
            max_wait = 300  # 5 minutes max
            cookie_names = {"sessionid", "sid_tt", "session"}
            for i in range(max_wait):
                try:
                    cookies = await page.context.cookies()
                    found = {}
                    for c in cookies:
                        cname = c["name"].lower()
                        for target in cookie_names:
                            if target in cname:
                                found[c["name"]] = c["value"]
                                break
                        # Also look for tt_chain_token which indicates authenticated state
                        if "tt_chain_token" in cname:
                            found[c["name"]] = c["value"]
                    
                    # Check if we have sessionid (main TikTok auth cookie)
                    if any("sessionid" in k.lower() for k in found):
                        # We're logged in!
                        with open(done_file, "w") as f:
                            json.dump({
                                "status": "success",
                                "session_id": session_id,
                                "cookies": cookies,
                                "token": found,
                                "timestamp": time.time(),
                            }, f)
                        print(f"[{session_id}] ✅ Session detected! Token saved.")
                        await browser.close()
                        return
                    
                except Exception as e:
                    print(f"[{session_id}] Poll error: {e}")

                await asyncio.sleep(2)

            # Timeout
            with open(done_file, "w") as f:
                json.dump({"status": "timeout", "session_id": session_id}, f)
            print(f"[{session_id}] ⏰ Timeout - no login detected")
            await browser.close()

        except Exception as e:
            with open(done_file, "w") as f:
                json.dump({"status": "error", "error": str(e), "session_id": session_id}, f)
            print(f"[{session_id}] ❌ Error: {e}")


def start_session():
    """Start a VNC auth session and return the session info."""
    session_id = uuid.uuid4().hex[:8]
    vnc_port = VNC_BASE_PORT + (hash(session_id) % 100)
    vnc_password = session_id
    done_file = str(SESSIONS_DIR / f"{session_id}.json")

    # Start xvfb if not running
    xvfb_proc = subprocess.Popen(
        ["Xvfb", XVFB_DISPLAY, "-screen", "0", "1280x720x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for xvfb to be ready
    time.sleep(1)

    # Start x11vnc
    x11vnc_proc = subprocess.Popen(
        ["x11vnc", "-display", XVFB_DISPLAY, "-forever",
         "-rfbport", str(vnc_port), "-passwd", vnc_password, "-quiet"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Start websockify (reuse port 6081 for all sessions)
    ws_proc = subprocess.Popen(
        ["websockify", "--web=" + VNC_ROOT, str(WS_PORT), f"localhost:{vnc_port}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    vnc_url = (
        f"https://openhands.m2igen.com/vnc/vnc.html"
        f"?host=openhands.m2igen.com&port=443&path=vnc/websockify&password={vnc_password}"
        f"&title=TikTok+Login&autoconnect=true&reconnect=true"
    )

    # Store process info
    session_info = {
        "session_id": session_id,
        "status": "starting",
        "vnc_url": vnc_url,
        "vnc_port": vnc_port,
        "display": XVFB_DISPLAY,
        "vnc_password": vnc_password,
        "created_at": time.time(),
        "done_file": done_file,
        "xvfb_pid": xvfb_proc.pid,
        "x11vnc_pid": x11vnc_proc.pid,
        "ws_pid": ws_proc.pid,
    }

    # Save session info
    with open(SESSIONS_DIR / f"{session_id}_info.json", "w") as f:
        json.dump(session_info, f)

    print(f"[{session_id}] ✅ VNC session started")
    print(f"[{session_id}] URL: {vnc_url}")
    print(f"[{session_id}] VNC pass: {vnc_password}")

    # Launch Playwright in background
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_playwright(session_id, XVFB_DISPLAY, done_file))
    loop.close()

    # Cleanup after playwright finishes
    xvfb_proc.terminate()
    x11vnc_proc.terminate()
    ws_proc.terminate()

    return session_id


if __name__ == "__main__":
    sid = start_session()
    print(f"\nDONE session_id={sid}")
