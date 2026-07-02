#!/usr/bin/env python3
"""
tiktok_login.py — TikTok Login สแกน QR ครั้งเดียว! (ไม่ต้อง Build, ไม่ต้อง Copy Cookie)

วิธีใช้:
  python3 tiktok_login.py

ขั้นตอน:
  1. เปิด Browser → ไป TikTok
  2. แสกน QR หรือล็อกอิน
  3. กด Enter → Session จะถูกบันทึกไว้

ครั้งต่อไปที่โพสต์ → ใช้ session ที่บันทึกไว้ ไม่ต้องล็อกอินอีก
"""

import json
import sys
import os
import subprocess
from pathlib import Path

# ตั้ง TMPDIR ก่อน import อะไร
os.environ.setdefault("TMPDIR", "/data/data/com.termux/files/usr/tmp")

SESSION_FILE = Path(__file__).parent / "session_tiktok.json"
CHROMIUM_PATHS = [
    "/data/data/com.termux/files/usr/bin/chromium-browser",
    "/data/data/com.termux/files/usr/bin/chromium",
    "/data/data/com.termux/files/usr/bin/chromium-browser-headless",
]


def find_chromium():
    """หา path Chromium ใน Termux"""
    for p in CHROMIUM_PATHS:
        if Path(p).exists():
            return p
    try:
        result = subprocess.run(["which", "chromium-browser"], capture_output=True, text=True)
        if result.stdout.strip():
            return result.stdout.strip()
    except:
        pass
    return None


def login():
    """ล็อกอิน TikTok ด้วย Playwright + Chromium ของ Termux"""
    chrome_path = find_chromium()
    if not chrome_path:
        print("❌ ไม่พบ Chromium! ลงก่อน:")
        print("   pkg install x11-repo && pkg install chromium")
        sys.exit(1)

    print(f"✅ พบ Chromium ที่: {chrome_path}")

    # Try importing playwright-core first, then playwright
    for mod_name in ["playwrightcore", "playwright"]:
        try:
            if mod_name == "playwrightcore":
                from playwrightcore.sync_api import sync_playwright
            else:
                from playwright.sync_api import sync_playwright
            break
        except ImportError:
            continue
    else:
        print("❌ ลง playwright-core ก่อน:")
        print("   pip install playwright-core")
        sys.exit(1)

    print(f"✅ ใช้ module: {mod_name}")
    print(f"📁 Session จะบันทึกที่: {SESSION_FILE}")
    print()

    print("""
╔══════════════════════════════════════════╗
║  🔐 TikTok Login — Scan QR ครั้งเดียว!   ║
╠══════════════════════════════════════════╣
║  1. Browser จะเปิดขึ้นมา                  ║
║  2. แสกน QR ด้วยมือถือ                    ║
║  3. หรือล็อกอินตามปกติ                    ║
║  4. เสร็จแล้วกลับมา Termux → กด Enter    ║
╚══════════════════════════════════════════╝
""")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=chrome_path,
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36",
        )
        page = context.new_page()
        page.goto("https://www.tiktok.com", wait_until="domcontentloaded")
        print("🌐 เปิด TikTok ใน Browser แล้ว...")

        input("⏳ ล็อกอินให้เรียบร้อย แล้วกด Enter...")

        # ดึง Cookie + Storage
        cookies = context.cookies()
        storage = context.storage_state()

        with open(SESSION_FILE, "w") as f:
            json.dump({"cookies": cookies, "storage": storage}, f, indent=2)

        browser.close()

    print(f"\n✅ Login สำเร็จ! ({len(cookies)} cookies)")
    print(f"📁 Session: {SESSION_FILE}")
    print("🚀 ต่อไป: python3 termux_main.py --post --platform tiktok")


if __name__ == "__main__":
    login()
