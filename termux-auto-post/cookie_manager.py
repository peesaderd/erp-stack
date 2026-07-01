"""
cookie_manager.py — จัดการ Session Cookie สำหรับแต่ละ Platform

วิธีใช้:
  1. python3 cookie_manager.py --platform tiktok --login
     → เปิด browser/login page ให้คุณ login ผ่านมือถือ
     → บันทึก cookie ไว้ใช้

  2. python3 cookie_manager.py --platform tiktok --refresh
     → ลอง refresh cookie โดยอัตโนมัติ

  3. python3 cookie_manager.py --platform tiktok --show
     → แสดง cookie ปัจจุบัน (ตรวจสอบว่ายังใช้ได้)
"""

import json
import os
import time
import re
import subprocess
from pathlib import Path
from datetime import datetime

COOKIE_DIR = Path(__file__).parent / "cookies"
COOKIE_DIR.mkdir(exist_ok=True)

PLATFORMS = {
    "tiktok": {
        "login_url": "https://www.tiktok.com/login",
        "domain": ".tiktok.com",
        "cookie_name": "sessionid",
        "upload_url": "https://www.tiktok.com/upload/",
    },
    "facebook": {
        "login_url": "https://www.facebook.com",
        "domain": ".facebook.com",
        "cookie_name": "c_user",
        "upload_url": "https://www.facebook.com/upload",
    },
    "instagram": {
        "login_url": "https://www.instagram.com/accounts/login/",
        "domain": ".instagram.com",
        "cookie_name": "sessionid",
        "upload_url": "https://www.instagram.com/create/",
    },
    "twitter_x": {
        "login_url": "https://x.com/login",
        "domain": ".x.com",
        "cookie_name": "auth_token",
        "upload_url": "https://x.com/compose/post",
    },
    "threads": {
        "login_url": "https://www.threads.net/login",
        "domain": ".threads.net",
        "cookie_name": "sessionid",
        "upload_url": "https://www.threads.net/create",
    },
}

def get_cookie_path(platform):
    return COOKIE_DIR / f"{platform}.json"

def save_cookies(platform, cookies):
    """บันทึก cookie ลงไฟล์"""
    path = get_cookie_path(platform)
    data = {
        "platform": platform,
        "cookies": cookies,
        "saved_at": datetime.now().isoformat(),
        "expires_at": datetime.now().isoformat()  # จะอัปเดตเมื่อใช้
    }
    path.write_text(json.dumps(data, indent=2))
    print(f"✅ {platform}: Cookie saved to {path}")

def load_cookies(platform):
    """โหลด cookie จากไฟล์"""
    path = get_cookie_path(platform)
    if not path.exists():
        print(f"❌ {platform}: No cookie file found. Run --login first.")
        return None
    return json.loads(path.read_text())

def get_cookie_header(platform):
    """return dict headers ที่มี cookie สำหรับ curl"""
    data = load_cookies(platform)
    if not data:
        return None
    cookies = data.get("cookies", {})
    # แปลง dict cookie → string format
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    return {"Cookie": cookie_str}

def check_cookie_valid(platform):
    """ตรวจสอบว่า cookie ยังใช้ได้มั้ย โดยลอง GET หน้า profile"""
    headers = get_cookie_header(platform)
    if not headers:
        return False

    import requests

    platform_info = PLATFORMS.get(platform)
    if not platform_info:
        print(f"❌ Unknown platform: {platform}")
        return False

    try:
        url = platform_info["login_url"]
        resp = requests.get(url, headers=headers, timeout=10, allow_redirects=False)
        # ถ้า redirect ไป login แสดงว่า cookie หมดอายุ
        if resp.status_code in (301, 302, 303):
            location = resp.headers.get("Location", "")
            if "login" in location.lower():
                print(f"⚠️ {platform}: Cookie expired. Need re-login.")
                return False
        print(f"✅ {platform}: Cookie is valid")
        return True
    except Exception as e:
        print(f"❌ {platform}: Error checking cookie: {e}")
        return False

def login_interactive(platform):
    """
    เปิด browser ให้คุณ login และเก็บ cookie
    สำหรับ Termux ใช้ termux-open-url
    """
    platform_info = PLATFORMS.get(platform)
    if not platform_info:
        print(f"❌ Unknown platform: {platform}")
        return

    url = platform_info["login_url"]
    print(f"""
╔══════════════════════════════════════════╗
║  🔐 Login: {platform.upper():<12}        ║
╠══════════════════════════════════════════╣
║  Browser จะเปิดขึ้นมา                    ║
║  กรุณา LOGIN ให้เรียบร้อย               ║
║                                          ║
║  หลังจาก login แล้ว                      ║
║  กลับมาใน Termux แล้วพิมพ์: done        ║
╚══════════════════════════════════════════╝
""")

    # ลองเปิด browser บน Termux
    try:
        subprocess.run(["termux-open-url", url], check=False)
    except FileNotFoundError:
        print(f"⚠️ termux-open-url ไม่ได้. เปิดเอง: {url}")

    input("⏳ กด Enter หลังจาก Login เสร็จ...")

    print(f"\n📋 ขั้นตอนถัดไป:")
    print(f"1. เปิด Chrome/Firefox บนมือถือ")
    print(f"2. F12 → Application → Cookies → {platform_info['domain']}")
    print(f"3. Copy Cookies แล้ววางในไฟล์ cookies/{platform}.json")
    print(f"   หรือใช้ --extract เพื่อดึงจากเบราว์เซอร์โดยตรง\n")

def extract_from_chrome(platform):
    """
    ดึง cookie จาก Chrome บน Termux โดยตรง
    ต้องติดตั้ง termux-chrome-cookie หรือ adb ก่อน
    """
    print(f"🔍 กำลังดึง cookie {platform} จาก Chrome...")
    # TODO: implement Chrome cookie extraction via adb
    print("⚠️ ยังไม่พร้อม — ใช้วิธี manual login แทน")
    login_interactive(platform)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cookie Manager สำหรับ Termux Auto Post")
    parser.add_argument("--platform", required=True, choices=list(PLATFORMS.keys()))
    parser.add_argument("--login", action="store_true", help="Login และบันทึก cookie")
    parser.add_argument("--refresh", action="store_true", help="Refresh cookie")
    parser.add_argument("--check", action="store_true", help="ตรวจสอบ cookie ปัจจุบัน")
    parser.add_argument("--show", action="store_true", help="แสดง cookie ปัจจุบัน")
    parser.add_argument("--extract", action="store_true", help="ดึง cookie จาก Chrome")

    args = parser.parse_args()

    if args.login:
        login_interactive(args.platform)
    elif args.refresh:
        print(f"🔄 Refreshing cookie for {args.platform}...")
        login_interactive(args.platform)
    elif args.check:
        check_cookie_valid(args.platform)
    elif args.show:
        data = load_cookies(args.platform)
        if data:
            print(json.dumps(data.get("cookies", {}), indent=2))
    elif args.extract:
        extract_from_chrome(args.platform)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
