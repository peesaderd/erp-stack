"""Simple remote auth - opens browser on virtual display, waits for login, captures session."""
import asyncio, json, os, sys, time, base64
from playwright.async_api import async_playwright

async def main():
    os.environ["DISPLAY"] = ":99"
    
    async with async_playwright() as pw:
        print("🚀 Launching browser...", flush=True)
        browser = await pw.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox", "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
            ],
        )
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        print("🌐 Navigating to TikTok login...", flush=True)
        await page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded")
        await asyncio.sleep(3)
        
        print("\n✅ Browser ready!", flush=True)
        print("📱 Open this URL on your phone:", flush=True)
        print("   https://openhands.m2igen.com/vnc/vnc.html?host=openhands.m2igen.com&port=443&path=vnc/websockify&password=tkremote", flush=True)
        print("\n⏳ Waiting for login (checking cookies every 2s, 5min timeout)...", flush=True)
        print("   (Log in to TikTok using phone/email/Google/Facebook)", flush=True)
        sys.stdout.flush()
        
        # Save status to a file
        status_file = "/tmp/remote_auth_status.json"
        with open(status_file, "w") as f:
            json.dump({"status": "waiting"}, f)
        
        # Poll for session cookies
        for i in range(150):
            try:
                cookies = await context.cookies()
                for c in cookies:
                    if "sessionid" in c["name"].lower() and c["value"]:
                        # LOGIN SUCCESS!
                        token = base64.b64encode(json.dumps(cookies).encode()).decode()
                        with open(status_file, "w") as f:
                            json.dump({
                                "status": "success",
                                "token": token,
                                "cookies": {c2["name"]: c2["value"] for c2 in cookies 
                                           if "session" in c2["name"].lower() or "sid" in c2["name"].lower()}
                            }, f)
                        print(f"\n✅ LOGIN SUCCESS! Session captured!", flush=True)
                        await asyncio.sleep(3)
                        await browser.close()
                        return
            except Exception:
                pass
            
            if i % 15 == 0:
                print(f"   Still waiting... ({i*2}s elapsed)", flush=True)
            await asyncio.sleep(2)
        
        print("\n⏰ Timeout - no login detected in 5 minutes", flush=True)
        with open(status_file, "w") as f:
            json.dump({"status": "timeout"}, f)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
