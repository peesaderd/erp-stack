#!/usr/bin/env python3
"""
termux_main.py — ตัวหลักของ Termux Auto Post System

วิธีใช้:
  # รันครั้งแรก — ตั้งค่า
  python3 termux_main.py --setup

  # ทดสอบดึงสินค้า
  python3 termux_main.py --scrape

  # ทดสอบสร้าง content
  python3 termux_main.py --generate

  # โพสต์ไป platform เดียว
  python3 termux_main.py --post --platform tiktok

  # โพสต์ทุก platform
  python3 termux_main.py --post --all

  # รัน schedule ต่อเนื่อง (cron mode)
  python3 termux_main.py --schedule

  # แสดงสถานะ
  python3 termux_main.py --status

ตัวอย่างใน Termux:
  # รัน schedule 24/7 (ใช้ termux-wake-lock ป้องกันหลับ)
  termux-wake-lock
  python3 termux_main.py --schedule
  
  # ตาราง:
  #   TikTok → ทุก 6 ชม.
  #   FB/IG/Threads → ทุก 12 ชม.
  #   X → ทุก 8 ชม.
"""

import json
import sys
import time
import random
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table

# ─── Modules ──────────────────────────────────────────────

from scrape_data import (
    scrape_tiktok_shop,
    scrape_shopee,
    filter_products,
    get_random_product,
)
from content_gen import (
    generate_caption,
    generate_review_script,
    generate_hashtags,
    generate_affiliate_caption,
)
from platforms.tiktok import TikTok
from platforms.facebook import Facebook
from platforms.instagram import Instagram
from platforms.twitter_x import TwitterX
from platforms.threads import Threads
from platforms.shopee import Shopee

console = Console()

# ─── Config ───────────────────────────────────────────────

CONFIG_PATH = Path(__file__).parent / "config.json"

def load_config():
    """โหลด config"""
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    else:
        example = Path(__file__).parent / "config.example.json"
        if example.exists():
            print(f"⚠️ ไม่พบ config.json — คัดลอกจาก config.example.json")
            print(f"   cp config.example.json config.json")
            print(f"   แล้วแก้ config.json ให้ถูกต้อง")
            sys.exit(1)
        return {}

def save_config(config):
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False))


# ─── Platform Registry ────────────────────────────────────

def get_platforms(config):
    """สร้าง platform instances จาก config"""
    platform_configs = config.get("platforms", {})

    registry = {
        "tiktok": TikTok,
        "facebook": Facebook,
        "instagram": Instagram,
        "twitter_x": TwitterX,
        "threads": Threads,
        "shopee": Shopee,
    }

    instances = {}
    for name, cls in registry.items():
        pconfig = platform_configs.get(name, {})
        if pconfig.get("enabled", False):
            instances[name] = cls(pconfig)

    return instances


# ─── Core Flow ────────────────────────────────────────────

def do_scrape(config):
    """Step 1: ดึงสินค้าจาก Platform"""
    console.print("[bold cyan]🔍 Scraping Products...[/bold cyan]")

    sources = config.get("content", {}).get("scrape_sources", ["tiktok_shop", "shopee"])
    all_products = []

    if "tiktok_shop" in sources:
        products = scrape_tiktok_shop(limit=10)
        all_products.extend(products)

    if "shopee" in sources:
        products = scrape_shopee(limit=10)
        all_products.extend(products)

    # กรอง
    filtered = filter_products(all_products, min_rating=4.0)
    
    console.print(f"[green]✅ ได้ {len(filtered)} สินค้าที่ผ่านเกณฑ์[/green]")

    # บันทึก
    cache_dir = Path(__file__).parent / "cache"
    cache_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    cache_path = cache_dir / f"products_{ts}.json"
    cache_path.write_text(json.dumps(filtered, indent=2, ensure_ascii=False))
    console.print(f"💾 บันทึกที่ {cache_path}")

    return filtered


def do_generate(product):
    """Step 2: สร้าง Content จาก AI"""
    console.print(f"[bold cyan]🎨 Generating Content for: {product.get('product_name')}[/bold cyan]")

    content = {
        "product": product,
        "type": "video",  # default
        "media": product.get("images", []),
        "link": product.get("affiliate_link", ""),
    }

    # Caption
    print("  📝 Generating caption...")
    content["caption"] = generate_caption(product) or ""

    # Hashtags
    print("  #️⃣ Generating hashtags...")
    content["hashtags"] = generate_hashtags(product, count=5)

    # Review script
    print("  🎬 Generating review script...")
    content["review_script"] = generate_review_script(product) or ""

    # Affiliate
    print("  🔗 Generating affiliate text...")
    content["affiliate_text"] = generate_affiliate_caption(product) or ""

    return content


def do_post_one(platform_name, platform_instance, content):
    """โพสต์ content ไป platform เดียว"""
    console.print(f"[bold]{'─'*50}[/bold]")
    console.print(f"[bold yellow]📤 Posting to {platform_name.upper()}...[/bold yellow]")

    try:
        result = platform_instance.post_content(content)
        if result:
            console.print(f"[green]✅ {platform_name}: โพสต์สำเร็จ![/green]")
        else:
            console.print(f"[red]❌ {platform_name}: โพสต์ล้มเหลว[/red]")
        return result
    except Exception as e:
        console.print(f"[red]❌ {platform_name}: Error — {e}[/red]")
        return False


def do_post_all(config, specific_platform=None):
    """วนลูปทุก platform ที่เปิดใช้งาน"""
    console.print("[bold cyan]🚀 Auto Post Run[/bold cyan]")
    console.print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    platforms = get_platforms(config)
    if not platforms:
        console.print("[red]❌ ไม่มี platform ไหนเปิดใช้งานใน config.json[/red]")
        return

    # Step 1: Scrape / Load products
    products = do_scrape(config)
    if not products:
        console.print("[red]❌ ไม่มีสินค้าที่จะโพสต์[/red]")
        return

    # เลือกสินค้ามาใช้
    product = get_random_product(products)
    if not product:
        return

    # Step 2: Generate content
    content = do_generate(product)

    # Step 3: Format + Post ตาม platform
    results = {}
    for name, inst in platforms.items():
        if specific_platform and name != specific_platform:
            continue

        # Format content ให้เหมาะกับ platform
        platform_content = inst.format_for_platform(content, product)
        
        # Post
        delay = random.uniform(3, 10)
        console.print(f"⏳ หน่วง {delay:.0f} วิ...")
        time.sleep(delay)

        result = do_post_one(name, inst, platform_content)
        results[name] = result

    # Summary
    console.print(f"\n[bold]{'='*50}[/bold]")
    console.print("[bold]📊 สรุปผลการโพสต์[/bold]")
    for name, ok in results.items():
        icon = "✅" if ok else "❌"
        console.print(f"  {icon} {name}")

    return results


def do_schedule(config):
    """รัน schedule ต่อเนื่อง"""
    from schedule import Scheduler

    scheduler = Scheduler(config)
    scheduler.run_forever()


def do_status(config):
    """แสดงสถานะของระบบ"""
    platforms = get_platforms(config)

    table = Table(title="📊 Termux Auto Post — สถานะ")
    table.add_column("Platform", style="cyan")
    table.add_column("Method", style="yellow")
    table.add_column("Enabled", style="green")
    table.add_column("Schedule")

    for name, inst in platforms.items():
        pconfig = config.get("platforms", {}).get(name, {})
        method = inst.method
        enabled = "✅" if pconfig.get("enabled") else "❌"
        hours = pconfig.get("schedule_hours", "-")
        table.add_row(name, method, enabled, f"ทุก {hours} ชม.")

    console.print(table)

    # ตรวจสอบ cookie
    console.print("\n[bold]🔐 สถานะ Cookie:[/bold]")
    cookie_dir = Path(__file__).parent / "cookies"
    for platform in ["tiktok", "twitter_x"]:
        cf = cookie_dir / f"{platform}.json"
        if cf.exists():
            data = json.loads(cf.read_text())
            saved_at = data.get("saved_at", "unknown")
            console.print(f"  ✅ {platform}: cookie มีอยู่ (บันทึกเมื่อ {saved_at})")
        else:
            console.print(f"  ⚠️ {platform}: ยังไม่ได้ login (รัน --login)")


def do_setup():
    """ตั้งค่าระบบครั้งแรก"""
    console.print("[bold cyan]🔧 ตั้งค่าระบบ Termux Auto Post[/bold cyan]")
    console.print()

    # เช็ค Python
    import sys
    console.print(f"✅ Python {sys.version}")

    # เช็ค dependencies
    try:
        import requests
        console.print("✅ requests")
    except:
        console.print("❌ requests — ลง: pip install requests")

    # สร้าง config
    example = Path(__file__).parent / "config.example.json"
    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists() and example.exists():
        config_path.write_text(example.read_text())
        console.print("✅ สร้าง config.json แล้ว — แก้ไขให้ถูกต้อง")
    else:
        console.print("✅ config.json มีอยู่แล้ว")

    # สร้างโฟลเดอร์
    (Path(__file__).parent / "cookies").mkdir(exist_ok=True)
    (Path(__file__).parent / "cache").mkdir(exist_ok=True)
    (Path(__file__).parent / "media").mkdir(exist_ok=True)
    console.print("✅ สร้างโฟลเดอร์แล้ว")

    console.print(f"""
[bold green]✅ Setup Complete![/bold green]

ขั้นตอนต่อไป:
  1. แก้ไข config.json — ใส่ API keys, platform settings
  2. login — python3 cookie_manager.py --platform tiktok --login
  3. ทดสอบ — python3 termux_main.py --post --all
  4. schedule — python3 termux_main.py --schedule
""")


# ─── CLI ──────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="📱 Termux Auto Post System")
    parser.add_argument("--setup", action="store_true", help="ตั้งค่าระบบครั้งแรก")
    parser.add_argument("--scrape", action="store_true", help="ทดสอบดึงสินค้า")
    parser.add_argument("--generate", action="store_true", help="ทดสอบสร้าง content")
    parser.add_argument("--post", action="store_true", help="โพสต์ content")
    parser.add_argument("--platform", default=None, help="เฉพาะ platform (tiktok, facebook, ...)")
    parser.add_argument("--all", action="store_true", help="โพสต์ทุก platform")
    parser.add_argument("--schedule", action="store_true", help="รัน schedule")
    parser.add_argument("--status", action="store_true", help="แสดงสถานะ")
    parser.add_argument("--login", type=str, default=None, help="login platform (ใช้ cookie_manager)")

    args = parser.parse_args()

    if args.setup:
        do_setup()
        return

    if args.login:
        from cookie_manager import login_interactive
        login_interactive(args.login)
        return

    config = load_config()

    if args.status:
        do_status(config)
    elif args.scrape:
        do_scrape(config)
    elif args.generate:
        products = do_scrape(config)
        if products:
            do_generate(products[0])
    elif args.post:
        if args.all:
            do_post_all(config)
        elif args.platform:
            platforms = get_platforms(config)
            if args.platform in platforms:
                products = do_scrape(config)
                if products:
                    content = do_generate(products[0])
                    do_post_one(args.platform, platforms[args.platform], content)
            else:
                console.print(f"[red]❌ ไม่พบ platform: {args.platform}[/red]")
                console.print(f"   มี: {', '.join(platforms.keys())}")
        else:
            parser.print_help()
    elif args.schedule:
        do_schedule(config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
