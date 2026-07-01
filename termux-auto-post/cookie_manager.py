"""
cookie_manager.py — จัดการ Session Cookie สำหรับแต่ละ Platform

--login:     เปิด browser → login → ดึง cookie อัตโนมัติ (ไม่ต้อง copy!)
--auto-fetch: ดึง cookie จาก Chrome ที่ login อยู่แล้ว
--check:     ตรวจสอบ cookie ว่ายังใช้ได้มั้ย
--show:      แสดง cookie ปัจจุบัน
"""

import json
import os
import re
import subprocess
import time
import requests
from pathlib import Path
from datetime import datetime

COOKIE_DIR = Path(__file__).parent / "cookies"
COOKIE_DIR.mkdir(exist_ok=True)

PLATFORMS = {
    "tiktok": {
        "login_url": "https://www.tiktok.com/login",
        "domain": ".tiktok.com",
        "cookie_name": "sessionid",
        "check_url": "https://www.tiktok.com/",
    },
    "facebook": {
        "login_url": "https://m.facebook.com/login",
        "domain": ".facebook.com",
        "cookie_name": "c_user",
        "check_url": "https://m.facebook.com/",
    },
    "instagram": {
        "login_url": "https://www.instagram.com/accounts/login/",
        "domain": ".instagram.com",
        "cookie_name": "sessionid",
        "check_url": "https://www.instagram.com/",
    },
    "twitter_x": {
        "login_url": "https://x.com/login",
        "domain": ".x.com",
        "cookie_name": "auth_token",
        "check_url": "https://x.com/",
    },
    "threads": {
        "login_url": "https://www.threads.net/login",
        "domain": ".threads.net",
        "cookie_name": "sessionid",
        "check_url": "https://www.threads.net/",
    },
}


def get_cookie_path(platform):
    return COOKIE_DIR / f"{platform}.json"


def save_cookies(platform, cookies):
    path = get_cookie_path(platform)
    data = {
        "platform": platform,
        "cookies": cookies,
        "saved_at": datetime.now().isoformat(),
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"✅ {platform}: Cookie saved to {path}")
    return True


def load_cookies(platform):
    path = get_cookie_path(platform)
    if not path.exists():
        return None
    return json.loads(path.read_text())


def get_cookie_header(platform):
    data = load_cookies(platform)
    if not data:
        return None
    cookies = data.get("cookies", {})
    cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
    return {"Cookie": cookie_str}


def check_cookie_valid(platform):
    """ตรวจสอบ cookie โดยลองเรียกหน้าแรกของ platform"""
    headers = get_cookie_header(platform)
    if not headers:
        print(f"⚠️ {platform}: No cookie loaded")
        return False

    info = PLATFORMS.get(platform, {})
    try:
        resp = requests.get(
            info.get("check_url", info.get("login_url", "")),
            headers=headers,
            timeout=10,
            allow_redirects=False,
        )
        # ถ้า redirect ไป login → cookie หมดอายุ
        if resp.status_code in (301, 302, 303):
            loc = resp.headers.get("Location", "")
            if "login" in loc.lower():
                print(f"⚠️ {platform}: Cookie expired")
                return False
        print(f"✅ {platform}: Cookie valid")
        return True
    except Exception as e:
        print(f"❌ {platform}: Error: {e}")
        return False


# ═══════════════════════════════════════════════
#  AUTO-FETCH: ดึง Cookie จาก Chrome/Kiwi โดยตรง
# ═══════════════════════════════════════════════

def try_termux_chrome_cookie(platform):
    """
    วิธีที่ 1: ใช้ termux-chrome-cookie tool
    """
    try:
        result = subprocess.run(
            ["termux-chrome-cookie", platform],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            # คาดว่าผลลัพท์เป็น JSON
            try:
                cookies = json.loads(result.stdout)
                return cookies
            except json.JSONDecodeError:
                # หรือเป็น plain text — parse เอา
                return _parse_cookie_text(result.stdout)
    except FileNotFoundError:
        pass
    return None


def try_adb_chrome_cookie(platform):
    """
    วิธีที่ 2: ใช้ adb + Chrome DevTools Protocol
    เชื่อมต่อ Chrome/Kiwi ที่เปิดอยู่บนมือถือ → ดึง cookie
    """
    domain = PLATFORMS.get(platform, {}).get("domain", "")

    try:
        # หา remote debugging port ของ Chrome/Kiwi
        result = subprocess.run(
            ["adb", "shell", "cat", "/proc/net/unix"],
            capture_output=True, text=True, timeout=5,
        )
        ports = re.findall(r'chrome_devtools_remote.*?(\d+)', result.stdout)
        if not ports:
            ports = re.findall(r'@chrome_devtools_remote.*?(\d+)', result.stdout)

        for port in ports[:3]:  # ลอง 3 port แรก
            try:
                proxy = f"http://127.0.0.1:{port}/json"
                resp = requests.get(proxy, timeout=3)
                tabs = resp.json()
                for tab in tabs[:3]:
                    tab_url = tab.get("webSocketDebuggerUrl", "")
                    if tab_url:
                        # get cookies via CDP
                        cdp_resp = requests.post(
                            tab_url.replace("ws://", "http://").replace("/devtools/", "/json/devtools/"),
                            json={"method": "Network.getCookies", "params": {"urls": [f"https://{domain}"]}},
                            timeout=3,
                        )
                        cdp_data = cdp_resp.json()
                        cookies_raw = cdp_data.get("result", {}).get("cookies", [])
                        if cookies_raw:
                            cookies = {}
                            for c in cookies_raw:
                                cookies[c["name"]] = c["value"]
                            return cookies
            except:
                continue
    except FileNotFoundError:
        pass
    return None


def try_termux_open_url(platform):
    """
    วิธีที่ 3: เปิด URL ใน browser → ให้ user login
    แล้วใช้ Python + JavaScript injection ดึง cookie
    """
    info = PLATFORMS.get(platform, {})
    url = info.get("login_url", "")

    print(f"\n📱 เปิด {platform.upper()} ใน browser...")
    try:
        subprocess.run(["termux-open-url", url], timeout=3)
    except:
        pass

    print(f"⏳ กรุณา LOGIN ให้เรียบร้อย")
    input("   แล้วกด Enter เมื่อ login เสร็จ...")

    # browser-based cookie extraction (แบบ automatic)
    # ใช้ requests เก็บ cookie ที่ browser ส่งมา
    try:
        # ลองเรียกหน้าเดิม → cookie น่าจะอยู่ใน session
        check_url = info.get("check_url", url)
        resp = requests.get(check_url, timeout=10)
        found = {}
        for c in resp.cookies:
            if platform == "tiktok" and "sessionid" in c.name.lower():
                found[c.name] = c.value
            elif platform == "facebook" and "c_user" in c.name:
                found[c.name] = c.value
            elif platform == "twitter_x" and "auth_token" in c.name:
                found[c.name] = c.value

        if found:
            print(f"✅ ได้ cookie {len(found)} รายการ")
            return found
        else:
            print("⚠️ ไม่เจอ cookie จากการเรียกหน้าเว็บ — ใช้วิธีอื่น")
            return None
    except:
        return None


def try_termux_clipboard(platform):
    """
    วิธีที่ 4: ใช้ termux-clipboard-get
    ผู้ใช้ copy cookie จาก browser → Termux ดึงจาก Clipboard
    """
    try:
        result = subprocess.run(
            ["termux-clipboard-get"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0 and result.stdout.strip():
            text = result.stdout.strip()
            # พยายาม parse
            try:
                cookies = json.loads(text)
                return cookies
            except:
                parsed = _parse_cookie_text(text)
                if parsed:
                    return parsed
    except FileNotFoundError:
        pass
    return None


def _parse_cookie_text(text):
    """parse cookie format นานา"""
    cookies = {}
    # Format 1: name=value; name2=value2
    for part in text.split(";"):
        part = part.strip()
        if "=" in part:
            key, val = part.split("=", 1)
            cookies[key.strip()] = val.strip()
    # Format 2: JSON
    if not cookies and text.startswith("{"):
        try:
            cookies = json.loads(text)
        except:
            pass
    return cookies if cookies else None


def auto_fetch(platform, method="auto"):
    """
    ดึง cookie โดยอัตโนมัติ — ไม่ต้อง copy วาง!
    method: "auto" → ลองทุกวิธีที่ทำได้
            "chrome" → ใช้ Chrome DevTools
            "clipboard" → รอวางจาก clipboard
            "browser" → เปิด browser ให้ login
    """
    print(f"🔍 Auto-fetching cookie for {platform}...")

    methods = []

    if method == "auto":
        methods = [
            ("Chrome DevTools", try_adb_chrome_cookie),
            ("Chrome Cookie Tool", try_termux_chrome_cookie),
            ("Browser Login", try_termux_open_url),
            ("Clipboard", try_termux_clipboard),
        ]
    elif method == "chrome":
        methods = [("Chrome DevTools", try_adb_chrome_cookie)]
    elif method == "clipboard":
        methods = [("Clipboard", try_termux_clipboard)]
    elif method == "browser":
        methods = [("Browser Login", try_termux_open_url)]

    for method_name, method_fn in methods:
        print(f"  Trying: {method_name}...")
        try:
            cookies = method_fn(platform)
            if cookies and len(cookies) > 2:  # ต้องมีอย่างน้อย 2+ cookies
                save_cookies(platform, cookies)
                print(f"✅ {platform}: Auto-fetch สำเร็จ! ({len(cookies)} cookies)")
                return True
            elif cookies:
                print(f"  ⚠️ ได้ cookies {len(cookies)} รายการ — อาจไม่พอ")
        except Exception as e:
            print(f"  ❌ {method_name}: {e}")

    print(f"\n⚠️ Auto-fetch ไม่สำเร็จ — ต้อง manual")
    return False


# ═══════════════════════════════════════════════
#  INTERACTIVE LOGIN
# ═══════════════════════════════════════════════

def login_interactive(platform):
    """เปิด browser → login → auto-fetch cookie"""
    info = PLATFORMS.get(platform, {})
    url = info.get("login_url", "")

    print(f"""
╔══════════════════════════════════════════╗
║  🔐 Auto Login: {platform.upper():<18} ║
╠══════════════════════════════════════════╣
║  ขั้นตอน:                                 ║
║  1. Browser จะเปิดขึ้นมา                   ║
║  2. LOGIN ให้เรียบร้อย                     ║
║  3. กลับมา Termux แล้วกด Enter            ║
║  4. ✅ Cookie จะถูกดึงอัตโนมัติ!           ║
╚══════════════════════════════════════════╝
""")

    # เปิด browser
    try:
        subprocess.run(["termux-open-url", url], timeout=3)
    except:
        print(f"เปิดเอง: {url}")

    input("⏳ กด Enter หลังจาก Login เสร็จ...")

    # Auto-fetch
    if auto_fetch(platform):
        return

    # ถ้า auto-fetch ไม่ได้ — ให้ copy วาง
    print(f"\n📋 Auto-fetch ไม่ได้ — ใช้วิธี Clipboard แทน:")
    print(f"1. ไปที่ {url}")
    print(f"2. เปิด DevTools → Console → พิมพ์:")
    print(f"   document.cookie")
    print(f"3. Copy ผลลัพท์ → มา Termux → paste (กดค้าง)")
    print(f"4. Done!")

    input("\n⏳ วาง cookie แล้วกด Enter...")

    clipboard = try_termux_clipboard(platform)
    if clipboard:
        save_cookies(platform, clipboard)
        print(f"✅ {platform}: Cookie saved!")
    else:
        print(f"❌ ยังไม่สำเร็จ — เปิด {url} แล้วคัดลอก cookie เอง")
        print(f"   วางในไฟล์: cookies/{platform}.json")


# ═══════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cookie Manager — Auto Fetch")
    parser.add_argument("--platform", required=True, choices=list(PLATFORMS.keys()))
    parser.add_argument("--login", action="store_true", help="Login + auto-fetch cookie")
    parser.add_argument("--auto-fetch", action="store_true", help="ดึง cookie จาก Chrome โดยตรง")
    parser.add_argument("--check", action="store_true", help="ตรวจสอบ cookie")
    parser.add_argument("--show", action="store_true", help="แสดง cookie")
    parser.add_argument("--method", choices=["auto", "chrome", "clipboard", "browser"], default="auto")

    args = parser.parse_args()

    if args.login:
        login_interactive(args.platform)
    elif args.auto_fetch:
        auto_fetch(args.platform, args.method)
    elif args.check:
        check_cookie_valid(args.platform)
    elif args.show:
        data = load_cookies(args.platform)
        if data:
            print(json.dumps(data.get("cookies", {}), indent=2))
        else:
            print(f"⚠️ {args.platform}: No cookie file")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
