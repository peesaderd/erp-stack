"""
Remote Auth Final — Opens real Chrome on xvfb, monitors cookies, captures session.
"""
import asyncio, json, os, sys, time, signal, base64, subprocess
from pathlib import Path
from playwright.async_api import async_playwright

CHROME_PATH = "/home/openhands/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome"
USER_DATA_DIR = "/tmp/tiktok_remote_chrome"
STATUS_FILE = "/tmp/remote_auth_status.json"
SESSIONS_DIR = Path(__file__).parent / "sessions" / "remote"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

async def main():
    account_id = sys.argv[1] if len(sys.argv) > 1 else "unknown"
    session_id = sys.argv[2] if len(sys.argv) > 2 else f"ra{int(time.time())%100000:05d}"
    
    print(f"[{session_id}] Starting remote auth for @{account_id}")
    
    # Poll cookies by watching Chrome's user data directory
    async def poll_cookies(context):
        for i in range(150):
            try:
                cookies = await context.cookies()
                for c in cookies:
                    if "sessionid" in c["name"].lower() and c["value"]:
                        token = base64.b64encode(json.dumps(cookies).encode()).decode()
                        result = {
                            "status": "success",
                            "token": token,
                            "account_id": account_id,
                            "session_id": session_id,
                            "cookies_snapshot": {c2["name"]: c2["value"][:20] for c2 in cookies 
                                               if "session" in c2["name"].lower() or "sid" in c2["name"].lower()}
                        }
                        with open(STATUS_FILE, "w") as f:
                            json.dump(result, f)
                        with open(SESSIONS_DIR / f"{session_id}_result.json", "w") as f:
                            json.dump(result, f)
                        print(f"[{session_id}] ✅ LOGIN SUCCESS! Session captured!")
                        return True
            except Exception as e:
                pass
            if i % 15 == 0:
                print(f"[{session_id}] Waiting... ({i*2}s)")
            await asyncio.sleep(2)
        return False
    
    # Launch browser on display :99 using Playwright
    os.environ["DISPLAY"] = ":99"
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            executable_path=CHROME_PATH,
            args=[
                "--no-sandbox", "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--window-size=1280,720",
                "--disable-blink-features=AutomationControlled",
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
        
        await page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        print(f"[{session_id}] ✅ Browser ready on virtual display!")
        print(f"[{session_id}] 📱 Opening VNC...")
        print(f"VNC_URL:https://openhands.m2igen.com/vnc/vnc.html"
              f"?host=openhands.m2igen.com&port=443&path=vnc/websockify&password=tkremote"
              f"&title=TikTok+Login&autoconnect=true")
        print(f"[{session_id}] ⏳ Waiting 5 min for login...")
        
        # Save initial status
        with open(STATUS_FILE, "w") as f:
            json.dump({"status": "waiting", "session_id": session_id, "account_id": account_id}, f)
        
        success = await poll_cookies(context)
        
        if not success:
            print(f"[{session_id}] ⏰ Timeout")
            with open(STATUS_FILE, "w") as f:
                json.dump({"status": "timeout", "session_id": session_id, "account_id": account_id}, f)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
