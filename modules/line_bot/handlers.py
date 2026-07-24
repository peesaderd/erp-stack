"""
LINE Bot Message Handlers
=========================
จัดการข้อความและ events จาก LINE webhook:
  - text → สั่งเมนู, ค้นหา, สั่งอาหาร
  - postback → กดปุ่มใน Flex/Rich Menu
  - follow → ผู้ใช้เพิ่มเพื่อน
  - unfollow → ผู้ใช้บล็อก
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

import httpx

from line_client import line_client, LineProfile

# ── Reward Module Integration ─────────────────────────────────────────
REWARD_BASE = os.environ.get("REWARD_BASE", "http://localhost:8121")
REWARD_ENABLED = True  # set False to disable reward features

# Lazy import reward handler
_reward_handler = None
async def _get_reward_handler():
    global _reward_handler
    if _reward_handler is None:
        try:
            import sys
            from pathlib import Path
            _modules_dir = Path(__file__).parent.parent  # modules/
            if str(_modules_dir) not in sys.path:
                sys.path.insert(0, str(_modules_dir))
            from reward.line_handler import handle_reward_commands, auto_earn_from_order
            _reward_handler = (handle_reward_commands, auto_earn_from_order)
        except Exception as e:
            logger.warning(f"Reward module not available: {e}")
            return None, None
    return _reward_handler


logger = logging.getLogger("line-bot.handlers")

# ── Config ───────────────────────────────────────────────────────────────

ERP_MODULAR_URL = os.environ.get("ERP_MODULAR_URL", "http://localhost:8102")
POS_API_URL = os.environ.get("POS_API_URL", "http://localhost:8114")
POS_MCP_URL = os.environ.get("POS_MCP_URL", "http://localhost:8200")

# POS mock menu (fallback)
_MOCK_MENU = [
    {"id": "APP001", "name": "Spring Rolls", "category": "Appetizer", "price": 59, "description": "เปาะเปี๊ยะทอด"},
    {"id": "APP002", "name": "Tom Yum Soup", "category": "Appetizer", "price": 89, "description": "ต้มยำ"},
    {"id": "APP003", "name": "Som Tum Thai", "category": "Appetizer", "price": 69, "description": "ส้มตำไทย"},
    {"id": "MAIN001", "name": "Pad Thai Goong", "category": "Main Course", "price": 89, "description": "ผัดไทยกุ้ง"},
    {"id": "MAIN002", "name": "Green Curry Chicken", "category": "Main Course", "price": 99, "description": "แกงเขียวหวานไก่"},
    {"id": "MAIN003", "name": "Massaman Curry", "category": "Main Course", "price": 109, "description": "แกงมัสมั่น"},
    {"id": "MAIN004", "name": "Pad Kra Pao Moo", "category": "Main Course", "price": 79, "description": "ผัดกะเพราหมู"},
    {"id": "MAIN005", "name": "Tom Kha Gai", "category": "Main Course", "price": 99, "description": "ต้มข่าไก่"},
    {"id": "MAIN006", "name": "Pad See Ew", "category": "Main Course", "price": 79, "description": "ผัดซีอิ๊ว"},
    {"id": "DES001", "name": "Mango Sticky Rice", "category": "Dessert", "price": 69, "description": "ข้าวเหนียวมะม่วง"},
    {"id": "BEV001", "name": "Thai Iced Tea", "category": "Beverage", "price": 39, "description": "ชาเย็น"},
    {"id": "BEV002", "name": "Thai Iced Coffee", "category": "Beverage", "price": 45, "description": "กาแฟเย็น"},
    {"id": "SID001", "name": "Steamed Rice", "category": "Side Dish", "price": 15, "description": "ข้าวเปล่า"},
]

_MOCK_TABLES = [
    {"id": "T01", "name": "Table 1", "capacity": 2, "zone": "Indoor"},
    {"id": "T02", "name": "Table 2", "capacity": 2, "zone": "Indoor"},
    {"id": "T03", "name": "Table 3", "capacity": 4, "zone": "Indoor"},
    {"id": "T04", "name": "Table 4", "capacity": 4, "zone": "Indoor"},
    {"id": "T12", "name": "Table 12", "capacity": 2, "zone": "Garden"},
    {"id": "VIP01", "name": "VIP Room A", "capacity": 10, "zone": "VIP"},
]

# In-memory user sessions (ค้าง订单)
_user_sessions: dict[str, dict] = {}

# ── POS API helpers ──────────────────────────────────────────────────────

async def _get_menu_from_pos() -> list[dict]:
    """Fetch menu from POS API, fallback to mock."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{POS_API_URL}/pos/public/menu")
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    return data
    except Exception:
        pass
    return _MOCK_MENU


async def _place_order(table_id: str, items: list[dict], notes: str = "") -> dict:
    """Send order to POS system."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{POS_API_URL}/pos/orders",
                json={"table_id": table_id, "items": items, "notes": notes},
            )
            if resp.status_code in (200, 201):
                return resp.json()
            return {"error": f"API error: {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


async def _get_order_status(order_id: str) -> Optional[dict]:
    """Check order status."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{POS_API_URL}/pos/orders/{order_id}")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return None


async def _get_tables_from_pos() -> list[dict]:
    """Get table list from POS."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{POS_API_URL}/pos/tables")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return _MOCK_TABLES


# ── Cart Helpers ─────────────────────────────────────────────────────────

def _get_cart(user_id: str) -> dict:
    if user_id not in _user_sessions:
        _user_sessions[user_id] = {"cart": [], "table_id": "", "state": "idle"}
    return _user_sessions[user_id]


def _format_cart(cart: list[dict]) -> str:
    if not cart:
        return "🛒 ตะกร้าว่างเปล่า"
    lines = ["🛒 **รายการในตะกร้า**\n"]
    total = 0
    for i, item in enumerate(cart, 1):
        subtotal = item["price"] * item["qty"]
        total += subtotal
        lines.append(f"{i}. {item['name']} × {item['qty']} = {subtotal:.0f} บาท")
    lines.append(f"\n💵 **รวมทั้งหมด: {total:.0f} บาท**")
    lines.append("\nพิมพ์ `ยืนยัน` เพื่อสั่ง หรือ `ยกเลิก` เพื่อยกเลิก")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN WEBHOOK HANDLER
# ═══════════════════════════════════════════════════════════════════════════

async def handle_webhook(body: dict, signature: str = ""):
    """Handle incoming LINE webhook events."""
    events = body.get("events", [])
    logger.info(f"Received {len(events)} event(s)")

    for event in events:
        event_type = event.get("type", "")
        reply_token = event.get("replyToken", "")
        source = event.get("source", {})
        user_id = source.get("userId", "")
        group_id = source.get("groupId", "")
        timestamp = event.get("timestamp", 0)

        if not user_id and not group_id:
            continue

        try:
            if event_type == "message":
                await _handle_message(event, reply_token, user_id)
            elif event_type == "postback":
                await _handle_postback(event, reply_token, user_id)
            elif event_type == "follow":
                await _handle_follow(event, reply_token, user_id)
            elif event_type == "unfollow":
                await _handle_unfollow(event, user_id)
            elif event_type == "beacon":
                await _handle_beacon(event, reply_token, user_id)
            else:
                logger.debug(f"Unhandled event type: {event_type}")
        except Exception as e:
            logger.error(f"Error handling event {event_type} for {user_id}: {e}", exc_info=True)
            # Try sending error reply
            try:
                await line_client.reply(reply_token, [line_client.text("⚠️ ขออภัย เกิดข้อผิดพลาด กรุณาลองใหม่อีกครั้ง")])
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════════════
# MESSAGE HANDLER
# ═══════════════════════════════════════════════════════════════════════════

async def _handle_message(event: dict, reply_token: str, user_id: str):
    msg = event.get("message", {})
    msg_type = msg.get("type", "")
    text = msg.get("text", "").strip()

    session = _get_cart(user_id)

    if msg_type == "text":
        await _handle_text(text, session, reply_token, user_id)
    elif msg_type == "location":
        await _handle_location(msg, reply_token, user_id)
    elif msg_type == "image":
        await line_client.reply(reply_token, [
            line_client.text("📸 ได้รับรูปภาพแล้วครับ ถ้าต้องการสั่งอาหารพิมพ์รายการที่ต้องการเลย!")
        ])
    else:
        logger.debug(f"Unhandled message type: {msg_type}")


async def _handle_text(text: str, session: dict, reply_token: str, user_id: str):
    """Handle text message — commands and natural language."""
    text_lower = text.lower().strip()

    
    # ── TUS UGC Studio Commands ────────────────────────────────────────
    if text_lower in ("tus", "ugc", "studio", "สินค้า", "products"):
        await _show_tus_products(reply_token)
        return
    if text_lower.startswith("create ") or text_lower.startswith("สร้าง "):
        product_id_or_title = text.split(" ", 1)[1].strip()
        await _trigger_tus_video_gen(reply_token, product_id_or_title)
        return
    if text_lower in ("jobs", "สถานะ", "status"):
        await _show_tus_jobs(reply_token)
        return

    # ── Reward / Points commands ────────────────────────────────────
    if REWARD_ENABLED and text_lower in (
        "แต้มฉัน", "my points", "balance", "points", "แต้ม", "คะแนน",
        "แต้มสะสม", "history", "ประวัติ", "ประวัติแต้ม",
        "แลกแต้ม", "redeem", "แลก", "รางวัล", "rewards", "catalog",
    ):
        handler, _ = await _get_reward_handler()
        if handler:
            messages, handled = await handler(text, user_id, "")
            if handled and messages:
                await line_client.reply(reply_token, messages)
                return

    if REWARD_ENABLED and (text_lower.startswith("แต้ม ") or text_lower.startswith("แลก ")):
        handler, _ = await _get_reward_handler()
        if handler:
            messages, handled = await handler(text, user_id, "")
            if handled and messages:
                await line_client.reply(reply_token, messages)
                return

    # ── Cart commands ──────────────────────────────────────────────────
    if text_lower in ("ยืนยัน", "ยีนยัน", "confirm", "สั่งเลย", "checkout"):
        await _handle_checkout(session, reply_token, user_id)
        return

    if text_lower in ("ยกเลิก", "cancel", "clear cart", "clear"):
        session["cart"] = []
        session["state"] = "idle"
        await line_client.reply(reply_token, [
            line_client.text("🗑️ ยกเลิกรายการทั้งหมดแล้วครับ")
        ])
        return

    if text_lower in ("cart", "ตะกร้า", "ดูตะกร้า", "my cart", "บิล"):
        await line_client.reply(reply_token, [
            line_client.text(_format_cart(session["cart"]))
        ])
        return

    # ── Main commands ──────────────────────────────────────────────────
    if text_lower in ("เมนู", "menu", "ดูเมนู", "list menu", "list"):
        await _show_menu(reply_token)
        return

    if text_lower in ("หมวดหมู่", "category", "cat", "ประเภท", "categories"):
        await _show_categories(reply_token)
        return

    if text_lower in ("help", "help!", "ช่วยเหลือ", "?", "คำสั่ง"):
        await _show_help(reply_token)
        return

    if text_lower in ("โต๊ะ", "table", "tables", "ที่นั่ง", "ดูโต๊ะ"):
        await _show_tables(reply_token)
        return

    if text_lower in ("profile", "โปรไฟล์", "ข้อมูล"):
        await _show_profile(reply_token, user_id)
        return

    if text_lower.startswith("order ") or text_lower.startswith("เช็คออเดอร์ "):
        order_id = text.split(" ", 1)[1].strip()
        await _check_order(reply_token, order_id)
        return

    # ── Search menu ────────────────────────────────────────────────────
    # Check if text matches a menu item pattern
    menu = await _get_menu_from_pos()
    found = [m for m in menu if text_lower in m["name"].lower() or text_lower in m.get("description", "").lower()]

    if found:
        # Show matching items with add-to-cart buttons
        bubbles = []
        for item in found[:10]:
            bubble = line_client.flex_bubble(
                body_boxes=[
                    line_client.flex_text(item["name"], weight="bold", size="lg"),
                    line_client.flex_text(
                        item.get("description", item["name"]),
                        size="sm", color="#888888", wrap=True
                    ),
                    line_client.flex_text(
                        f"💰 {item['price']:.0f} บาท",
                        size="md", color="#ff6600", weight="bold", margin="md"
                    ),
                ],
                footer=[
                    line_client.flex_button(
                        "➕ เพิ่มในตะกร้า", "postback",
                        data=f"add_cart|{item['id']}|{item['name']}|{item['price']}",
                        displayText=f"เพิ่ม {item['name']} ในตะกร้า"
                    ),
                ],
            )
            bubbles.append(bubble)

        if bubbles:
            carousel = line_client.flex_carousel(bubbles)
            await line_client.reply(reply_token, [
                line_client.text(f"🔍 พบ {len(found)} รายการ:"),
                line_client.flex("รายการอาหาร", carousel),
            ])
            return
        else:
            # Try adding to cart by exact name match
            exact = [m for m in menu if text_lower == m["name"].lower()]
            if exact:
                item = exact[0]
                session["cart"].append({
                    "id": item["id"],
                    "name": item["name"],
                    "price": item["price"],
                    "qty": 1,
                })
                await line_client.reply(reply_token, [
                    line_client.text(f"✅ เพิ่ม {item['name']} ({item['price']:.0f} บาท) ในตะกร้าแล้ว\n\n{_format_cart(session['cart'])}")
                ])
                return

    # ── Default: search menu by keyword ────────────────────────────────
    await _search_and_show(reply_token, text)


async def _search_and_show(reply_token: str, keyword: str):
    """Search menu and show results."""
    menu = await _get_menu_from_pos()
    kw = keyword.lower()
    results = [m for m in menu if kw in m["name"].lower() or kw in m.get("description", "").lower()
               or kw in m.get("category", "").lower()]

    if not results:
        await line_client.reply(reply_token, [
            line_client.text(
                f"😅 ไม่พบ '{keyword}' ในเมนู\n\n"
                f"พิมพ์ `เมนู` เพื่อดูรายการทั้งหมด\n"
                f"พิมพ์ `หมวดหมู่` เพื่อดูหมวดหมู่\n"
                f"หรือพิมพ์ชื่ออาหารที่ต้องการ"
            )
        ])
        return

    items_text = "\n".join(
        f"• {m['name']} — {m['price']:.0f} บาท"
        for m in results[:15]
    )
    await line_client.reply(reply_token, [
        line_client.text(
            f"🔍 พบ {len(results)} รายการ:\n\n{items_text}\n\n"
            f"พิมพ์ชื่อเมนูเพื่อเพิ่มในตะกร้า 📝"
        )
    ])


# ═══════════════════════════════════════════════════════════════════════════
# POSTBACK HANDLER
# ═══════════════════════════════════════════════════════════════════════════

async def _handle_postback(event: dict, reply_token: str, user_id: str):
    postback = event.get("postback", {})
    data = postback.get("data", "")
    if data.startswith("create_video:"):
        pid = data.split(":", 1)[1]
        await _trigger_tus_video_gen(reply_token, pid)
        return
    postback = event.get("postback", {})
    data = postback.get("data", "")
    params = postback.get("params", {})

    logger.info(f"Postback from {user_id}: {data}")

    session = _get_cart(user_id)

    parts = data.split("|")
    action = parts[0] if parts else ""

    if action == "add_cart" and len(parts) >= 4:
        item_id, name, price_str = parts[1], parts[2], parts[3]
        price = float(price_str)
        session["cart"].append({"id": item_id, "name": name, "price": price, "qty": 1})
        await line_client.reply(reply_token, [
            line_client.text(f"✅ เพิ่ม {name} ({price:.0f} บาท) ในตะกร้าแล้ว\n\n{_format_cart(session['cart'])}")
        ])

    elif action == "view_cart":
        await line_client.reply(reply_token, [
            line_client.text(_format_cart(session["cart"]))
        ])

    elif action == "clear_cart":
        session["cart"] = []
        session["state"] = "idle"
        await line_client.reply(reply_token, [
            line_client.text("🗑️ ล้างตะกร้าเรียบร้อย")
        ])

    elif action == "checkout":
        await _handle_checkout(session, reply_token, user_id)

    elif action == "show_menu":
        await _show_menu(reply_token)

    elif action == "show_categories":
        await _show_categories(reply_token)

    elif action == "category":
        cat_name = parts[1] if len(parts) > 1 else ""
        await _show_menu_by_category(reply_token, cat_name)

    elif action == "show_tables":
        await _show_tables(reply_token)

    elif action == "select_table":
        table_id = parts[1] if len(parts) > 1 else ""
        table_name = parts[2] if len(parts) > 2 else table_id
        session["table_id"] = table_id
        session["state"] = "ordering"
        await line_client.reply(reply_token, [
            line_client.text(f"✅ เลือกโต๊ะ {table_name} แล้ว\n\nพิมพ์ชื่อเมนูที่ต้องการสั่งได้เลย! 📝")
        ])

    elif action == "show_help":
        await _show_help(reply_token)

    elif action == "show_profile":
        await _show_profile(reply_token, user_id)

    elif action == "set_table":
        # Show table selection
        await _show_tables(reply_token)

    else:
        logger.debug(f"Unhandled postback data: {data}")


# ═══════════════════════════════════════════════════════════════════════════
# FOLLOW / UNFOLLOW
# ═══════════════════════════════════════════════════════════════════════════

async def _handle_follow(event: dict, reply_token: str, user_id: str):
    profile = await line_client.get_profile(user_id)
    name = profile.display_name if profile else "คุณ"

    welcome_text = (
        f"🎉 สวัสดีครับ {name}!\n\n"
        f"ยินดีต้อนรับสู่ LINE Bot ร้านอาหารของเรา 🍽️\n\n"
        f"**คำสั่งที่ใช้ได้:**\n"
        f"📋 `เมนู` — ดูเมนูทั้งหมด\n"
        f"🔍 `ก๋วยเตี๋ยว` — ค้นหาอาหาร\n"
        f"🛒 `cart` — ดูตะกร้า\n"
        f"✅ `ยืนยัน` — สั่งอาหาร\n"
        f"🪑 `โต๊ะ` — ดูโต๊ะว่าง\n"
        f"❓ `help` — วิธีใช้\n"
    )

    await line_client.reply(reply_token, [
        line_client.text(welcome_text),
        line_client.sticker("446", "1988"),  # LINE greeting sticker
    ])


async def _handle_unfollow(event: dict, user_id: str):
    logger.info(f"User unfollowed: {user_id}")
    # Clean up session
    _user_sessions.pop(user_id, None)


async def _handle_beacon(event: dict, reply_token: str, user_id: str):
    """Handle beacon events (BLE proximity)."""
    hwid = event.get("beacon", {}).get("hwid", "")
    beacon_type = event.get("beacon", {}).get("type", "")
    logger.info(f"Beacon from {user_id}: {beacon_type} ({hwid})")
    await line_client.reply(reply_token, [
        line_client.text(f"📡 ยินดีต้อนรับ! \n(Beacon: {beacon_type})")
    ])


async def _handle_location(msg: dict, reply_token: str, user_id: str):
    title = msg.get("title", "")
    address = msg.get("address", "")
    lat = msg.get("latitude", 0)
    lon = msg.get("longitude", 0)
    await line_client.reply(reply_token, [
        line_client.text(f"📍 ได้รับตำแหน่งของคุณแล้ว: {title or address}")
    ])


# ═══════════════════════════════════════════════════════════════════════════
# ACTION HANDLERS
# ═══════════════════════════════════════════════════════════════════════════

async def _show_menu(reply_token: str):
    """Show full menu as flex carousel grouped by category."""
    menu = await _get_menu_from_pos()
    categories = {}
    for item in menu:
        cat = item.get("category", "Other")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)

    # First reply: list categories as quick reply
    quick_items = []
    for cat in categories:
        quick_items.append(
            line_client.quick_reply_item(cat, f"category|{cat}", f"ดูเมนู{cat}")
        )

    await line_client.reply(reply_token, [
        line_client.quick_reply(
            "📋 **เลือกหมวดหมู่เมนู**\nหรือพิมพ์ชื่ออาหารที่ต้องการ",
            quick_items[:13]
        )
    ])


async def _show_categories(reply_token: str):
    """Show categories as a flex carousel."""
    menu = await _get_menu_from_pos()
    categories = {}
    for item in menu:
        cat = item.get("category", "Other")
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += 1

    cat_config = {
        "Appetizer": {"emoji": "🥟", "color": "#ff6b6b"},
        "Main Course": {"emoji": "🍛", "color": "#ffa726"},
        "Dessert": {"emoji": "🍰", "color": "#ab47bc"},
        "Beverage": {"emoji": "🥤", "color": "#42a5f5"},
        "Side Dish": {"emoji": "🥗", "color": "#66bb6a"},
    }

    bubbles = []
    for cat, count in categories.items():
        cfg = cat_config.get(cat, {"emoji": "🍽️", "color": "#888888"})
        bubble = {
            "type": "bubble",
            "hero": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"{cfg['emoji']} {cat}",
                        "size": "xxl",
                        "weight": "bold",
                        "color": "#ffffff",
                        "align": "center",
                    },
                    {
                        "type": "text",
                        "text": f"{count} รายการ",
                        "size": "md",
                        "color": "#ffffffCC",
                        "align": "center",
                        "margin": "sm",
                    },
                ],
                "paddingAll": "20px",
                "backgroundColor": cfg["color"],
                "height": "120px",
                "justifyContent": "center",
                "alignItems": "center",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "postback",
                            "label": f"ดู {cat}",
                            "data": f"category|{cat}",
                            "displayText": f"แสดงเมนู {cat}",
                        },
                        "style": "primary",
                        "color": cfg["color"],
                    }
                ],
            },
        }
        bubbles.append(bubble)

    if bubbles:
        carousel = line_client.flex_carousel(bubbles)
        await line_client.reply(reply_token, [
            line_client.flex("หมวดหมู่เมนู", carousel)
        ])
    else:
        await line_client.reply(reply_token, [
            line_client.text("😅 ยังไม่มีเมนูในระบบ")
        ])


async def _show_menu_by_category(reply_token: str, category: str):
    """Show menu items in a specific category."""
    menu = await _get_menu_from_pos()
    items = [m for m in menu if m.get("category", "").lower() == category.lower()]

    if not items:
        await line_client.reply(reply_token, [
            line_client.text(f"😅 ไม่พบเมนูในหมวด {category}")
        ])
        return

    emoji_map = {"Appetizer": "🥟", "Main Course": "🍛", "Dessert": "🍰", "Beverage": "🥤", "Side Dish": "🥗"}
    emoji = emoji_map.get(category, "🍽️")

    bubbles = []
    for item in items[:10]:
        bubble = line_client.flex_bubble(
            body_boxes=[
                line_client.flex_text(item["name"], weight="bold", size="md"),
                line_client.flex_text(
                    item.get("description", ""), size="xs", color="#888888", wrap=True
                ) if item.get("description") else line_client.flex_spacer("xs"),
                line_client.flex_spacer("sm"),
                line_client.flex_text(
                    f"💰 {item['price']:.0f} บาท",
                    size="md", color="#ff6600", weight="bold"
                ),
            ],
            footer=[
                line_client.flex_button(
                    "➕ เพิ่มในตะกร้า", "postback",
                    data=f"add_cart|{item['id']}|{item['name']}|{item['price']}",
                    displayText=f"เพิ่ม {item['name']}",
                ),
            ],
        )
        bubbles.append(bubble)

    carousel = line_client.flex_carousel(bubbles)
    await line_client.reply(reply_token, [
        line_client.text(f"{emoji} **{category}** ({len(items)} รายการ)"),
        line_client.flex(f"เมนู {category}", carousel),
    ])


async def _show_tables(reply_token: str):
    """Show available tables for selection."""
    tables = await _get_tables_from_pos()

    if not tables:
        await line_client.reply(reply_token, [
            line_client.text("😅 ไม่พบข้อมูลโต๊ะในระบบ")
        ])
        return

    bubbles = []
    for table in tables[:10]:
        capacity = table.get("capacity", 2)
        zone = table.get("zone", "")
        table_name = table.get("name", table.get("id", ""))
        zone_emoji = {"Indoor": "🏠", "Garden": "🌿", "VIP": "⭐", "Outdoor": "🌞"}
        emoji = zone_emoji.get(zone, "🪑")

        bubble = line_client.flex_bubble(
            body_boxes=[
                line_client.flex_text(f"{emoji} {table_name}", weight="bold", size="lg"),
                line_client.flex_text(f"Zone: {zone}", size="sm", color="#888888"),
                line_client.flex_text(f"👥 {capacity} ที่นั่ง", size="sm", color="#888888"),
            ],
            footer=[
                line_client.flex_button(
                    "✅ เลือกโต๊ะนี้", "postback",
                    data=f"select_table|{table['id']}|{table_name}",
                    displayText=f"เลือก {table_name}",
                ),
            ],
        )
        bubbles.append(bubble)

    carousel = line_client.flex_carousel(bubbles)
    await line_client.reply(reply_token, [
        line_client.text("🪑 **เลือกโต๊ะของคุณ**"),
        line_client.flex("เลือกโต๊ะ", carousel),
    ])


async def _handle_checkout(session: dict, reply_token: str, user_id: str):
    """Confirm and place order."""
    cart = session.get("cart", [])
    if not cart:
        await line_client.reply(reply_token, [
            line_client.text("🛒 ตะกร้าว่างเปล่า\nพิมพ์ชื่อเมนูหรือกด `เมนู` เพื่อเริ่มสั่ง")
        ])
        return

    table_id = session.get("table_id", "")

    # Build order
    items = []
    total = 0
    for c in cart:
        items.append({"item_id": c["id"], "name": c["name"], "quantity": c["qty"], "price": c["price"]})
        total += c["price"] * c["qty"]

    # Place order via POS system
    result = await _place_order(table_id, items)

    order_id = result.get("order_id", result.get("id", f"ORD-{datetime.now().strftime('%y%m%d%H%M%S')}"))
    table_str = f"ที่โต๊ะ {session.get('table_id', '')}" if table_id else "(ไม่ระบุโต๊ะ)"

    # ── Auto-earn points ────────────────────────────────────────────
    points_earned = 0
    if REWARD_ENABLED:
        try:
            _, earn_func = await _get_reward_handler()
            if earn_func:
                earn_result = await earn_func(user_id, total, order_id)
                if earn_result and earn_result.get("success"):
                    points_earned = earn_result.get("points_earned", 0)
        except Exception as e:
            logger.warning(f"Auto-earn points failed: {e}")

    if "error" not in result:
        pts_line = f"\n⭐ **ได้รับ {points_earned} แต้มสะสม!**" if points_earned > 0 else ""
        confirm_text = (
            f"✅ **สั่งอาหารสำเร็จ!**\n\n"
            f"📄 เลขออเดอร์: `{order_id}`\n"
            f"{table_str}\n"
            f"\n💵 รวมทั้งหมด: **{total:.0f} บาท**"
            f"{pts_line}\n"
            f"\n⏳ รอเชฟทำให้ก่อนนะครับ 🧑‍🍳\n"
            f"\nพิมพ์ `เช็คออเดอร์ {order_id}` เพื่อดูสถานะ"
        )
    else:
        # Even if POS fails, show the order
        confirm_text = (
            f"✅ **รับออเดอร์แล้ว!**\n\n"
            f"📄 เลขออเดอร์: `{order_id}`\n"
            f"\n💵 รวมทั้งหมด: **{total:.0f} บาท**\n"
            f"⏳ รอสักครู่ครับ\n"
        )

    # Clear cart after order
    item_rows = []
    for it in items:
        item_rows.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": f"{it['name']} x{it['quantity']}", "size": "sm", "color": "#555555", "flex": 4, "wrap": True},
                {"type": "text", "text": f"฿{it['price'] * it['quantity']:.0f}", "size": "sm", "color": "#111111", "align": "end", "flex": 2, "weight": "bold"}
            ]
        })

    receipt_bubble = {
        "type": "bubble",
        "styles": {"header": {"backgroundColor": "#4f46e5"}},
        "header": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": "🧾 ใบเสร็จรับเงิน / สรุปออเดอร์", "weight": "bold", "color": "#ffffff", "size": "lg"},
                {"type": "text", "text": f"เลขออเดอร์: {order_id}", "color": "#c7d2fe", "size": "xs", "margin": "xs"}
            ]
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {"type": "text", "text": f"📍 {table_str}", "size": "sm", "weight": "bold", "color": "#4338ca"},
                {"type": "separator", "margin": "md"},
                {"type": "box", "layout": "vertical", "margin": "md", "spacing": "sm", "contents": item_rows},
                {"type": "separator", "margin": "md"},
                {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "md",
                    "contents": [
                        {"type": "text", "text": "ยอดรวมสุทธิ", "weight": "bold", "size": "md", "color": "#111111"},
                        {"type": "text", "text": f"฿{total:.0f}", "weight": "bold", "size": "xl", "color": "#4f46e5", "align": "end"}
                    ]
                },
                {"type": "text", "text": f"⭐ ได้รับแต้มสะสม +{points_earned} แต้ม" if points_earned > 0 else "⭐ สะสมแต้มกับสมาชิก POS", "size": "xs", "color": "#059669", "margin": "md"}
            ]
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "action": {"type": "postback", "label": "💳 สแกนจ่าย (PromptPay)", "data": f"pay_promptpay|{order_id}|{total}"},
                    "style": "primary",
                    "color": "#4f46e5"
                },
                {
                    "type": "button",
                    "action": {"type": "message", "label": "🔍 เช็คสถานะออเดอร์", "text": f"เช็คออเดอร์ {order_id}"},
                    "style": "secondary"
                }
            ]
        }
    }

    session["cart"] = []
    session["state"] = "idle"

    await line_client.reply(reply_token, [
        line_client.flex(f"สรุปออเดอร์ {order_id}", receipt_bubble)
    ])


async def _check_order(reply_token: str, order_id: str):
    """Check order status."""
    order = await _get_order_status(order_id)

    if not order:
        await line_client.reply(reply_token, [
            line_client.text(f"😅 ไม่พบออเดอร์ `{order_id}`")
        ])
        return

    items = order.get("items", [])
    status = order.get("status", "pending")
    status_emoji = {"pending": "⏳", "preparing": "👨‍🍳", "served": "✅", "paid": "💳", "completed": "🎉"}

    item_lines = []
    total = 0
    for item in items:
        qty = item.get("quantity", 1)
        price = item.get("price", 0)
        total += qty * price
        item_lines.append(f"• {item.get('name', '')} × {qty} = {qty * price:.0f} บาท")

    status_text = (
        f"📄 **ออเดอร์ {order_id}**\n\n"
        f"สถานะ: {status_emoji.get(status, '⏳')} **{status}**\n"
        f"\n"
        + "\n".join(item_lines) +
        f"\n\n💵 รวม: **{total:.0f} บาท**"
    )

    await line_client.reply(reply_token, [
        line_client.text(status_text)
    ])


async def _show_profile(reply_token: str, user_id: str):
    """Show user profile."""
    profile = await line_client.get_profile(user_id)
    if profile:
        text = (
            f"👤 **โปรไฟล์ของคุณ**\n\n"
            f"ชื่อ: {profile.display_name}\n"
            f"LINE ID: {profile.user_id[:10]}...\n"
        )
        if profile.picture_url:
            await line_client.reply(reply_token, [
                line_client.image(profile.picture_url),
                line_client.text(text),
            ])
        else:
            await line_client.reply(reply_token, [line_client.text(text)])
    else:
        await line_client.reply(reply_token, [
            line_client.text("😅 ไม่สามารถดึงข้อมูลโปรไฟล์ได้")
        ])


async def _show_help(reply_token: str):
    """Show help message."""
    help_text = (
        "🤖 **วิธีใช้ LINE Bot**\n\n"
        "**คำสั่งหลัก:**\n"
        "📋 `เมนู` — ดูเมนูทั้งหมด\n"
        "📂 `หมวดหมู่` — ดูหมวดอาหาร\n"
        "🔍 `พิซซ่า` — ค้นหาเมนู\n"
        "🛒 `cart` — ดูตะกร้าสินค้า\n"
        "✅ `ยืนยัน` — สั่งอาหาร\n"
        "🗑️ `ยกเลิก` — ล้างตะกร้า\n"
        "🪑 `โต๊ะ` — เลือกโต๊ะ\n"
        "🔎 `เช็คออเดอร์ ABC` — ดูสถานะ\n"
        "👤 `profile` — ดูโปรไฟล์\n"
        "\n**การสั่งอาหาร:**\n"
        "1. เลือกโต๊ะ\n"
        "2. พิมพ์ชื่อเมนูที่ต้องการ\n"
        "3. พิมพ์ `ยืนยัน` เพื่อสั่ง\n"
        "\n💡 หรือกดปุ่มใน Rich Menu ด้านล่าง!"
    )
    await line_client.reply(reply_token, [line_client.text(help_text)])
