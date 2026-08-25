"""
POS MCP Server — ให้ AI Agent เข้าถึงข้อมูล POS และสั่งอาหาร
===========================================================
Exposes SuperAppsheet POS data and actions as MCP tools:
  - Menu search / browse
  - Category list
  - Order status check
  - Order creation (via POS API)
  - Table info
  - Product search

Usage:
  python3 pos_mcp_server.py                    # stdio mode
  python3 pos_mcp_server.py --http :8200       # SSE mode

For OpenClaw config (openclaw.json):
  "mcpServers": {
    "pos": {
      "type": "stdio",
      "command": "python3",
      "args": ["/home/openhands/erp-stack/mcp/pos_mcp_server.py"]
    }
  }
"""

import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP

logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger("pos-mcp")

# ── Config ───────────────────────────────────────────────────────────────

POS_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "super-appsheet", "data", "pos.db")
# Live API ผ่าน nginx (pos.m2igen.com) — อย่าใช้ localhost เป็น default
POS_API_URL = os.environ.get("POS_API_URL", "https://pos.m2igen.com/api")

# Ensure db path is absolute
POS_DB_PATH = os.path.abspath(POS_DB_PATH)

# ── MCP Server ──────────────────────────────────────────────────────────

mcp = FastMCP(
    "POS MCP",
    instructions="""POS MCP Server — ให้ AI Agent อ่านข้อมูลร้านอาหาร POS และสั่งอาหารได้

Tools ที่มี:
  1. get_categories — ดูหมวดหมู่เมนูทั้งหมด
  2. get_menu — ดูรายการอาหาร (กรองตามหมวดหมู่ได้)
  3. search_menu — ค้นหาเมนูตามชื่อ
  4. get_order — เช็คสถานะออเดอร์
  5. get_tables — ดูโต๊ะและสถานะ
  6. create_order — สร้างออเดอร์ใหม่
""",
)


# ── DB Helper ────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection | None:
    if not os.path.exists(POS_DB_PATH):
        return None
    conn = sqlite3.connect(POS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Tools ────────────────────────────────────────────────────────────────

def _api_get(path: str, params: dict | None = None):
    """GET จาก Live POS API (https://pos.m2igen.com/api) — return None ถ้า fail"""
    try:
        import urllib.request
        import urllib.parse
        url = f"{POS_API_URL}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
            logger.warning("Live API %s -> %s", path, resp.status)
    except Exception as e:
        logger.warning("Live API %s failed: %s", path, e)
    return None


def _api_post(path: str, payload: dict):
    try:
        import urllib.request
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{POS_API_URL}{path}",
            data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            if resp.status in (200, 201):
                return json.loads(body)
            return {"error": f"API returned {resp.status}: {body[:300]}"}
    except Exception as e:
        return {"error": str(e)}


# Thai names + spoken aliases by item id (live POS menu is English-only)
TH_NAMES_BY_ID = {
    "APP001": ("ปอเปี๊ยะทอด", ["ปอเปี๊ยะ"]), "APP002": ("ต้มยำกุ้ง", ["ต้มยำ"]),
    "APP003": ("ส้มตำไทย", ["ส้มตำ"]), "APP004": ("สะเต๊ะไก่", ["สะเต๊ะ", "หมูสเต๊ะ"]),
    "APP005": ("ทอดมันปลา", []), "APP006": ("ทอดมันกุ้ง", []),
    "APP007": ("ลาบไก่", ["ลาบ"]), "APP008": ("เมี่ยงคำ", []),
    "MAIN001": ("ผัดไทยกุ้ง", ["ผัดไทย", "ผัดไท่"]), "MAIN002": ("แกงเขียวหวานไก่", ["แกงเขียวหวาน", "เขียวหวาน"]),
    "MAIN003": ("แกงมัสมั่น", ["มัสมั่น"]), "MAIN004": ("ผัดกะเพราหมู", ["ข้าวผัดกะเพราหมู", "กะเพราหมู", "ผัดกะเพรา", "กะเพรา"]),
    "MAIN005": ("ต้มข่าไก่", ["ต้มข่า"]), "MAIN006": ("ผัดซีอิ๊ว", ["ผัดซีอิ๊วหมู", "ซีอิ๊ว"]),
    "MAIN007": ("ข้าวซอย", []), "MAIN008": ("แกงพะแนง", ["พะแนง"]),
    "MAIN009": ("ข้าวผัดทะเล", []), "MAIN010": ("ผัดกะเพราทะเล", ["กะเพราทะเล"]),
    "MAIN011": ("คอหมูย่าง", ["สันคอหมูย่าง"]), "MAIN012": ("ปลากะพงนึ่งมะนาว", ["ปลานึ่งมะนาว", "ปลานึ่ง"]),
    "DES001": ("ข้าวเหนียวมะม่วง", ["มะม่วงข้าวเหนียว"]), "DES002": ("โรตี", []),
    "DES003": ("ไอศกรีมมะพร้าว", ["ไอศครีมกะทิ", "ไอติม"]), "DES004": ("ข้าวต้มมัด", []),
    "DES005": ("ลอดช่อง", []), "DES006": ("บัวลอย", []),
    "BEV001": ("ชาเย็น", ["ชาไทย"]), "BEV002": ("กาแฟเย็น", ["โอเลี้ยง"]),
    "BEV003": ("น้ำมะพร้าว", []), "BEV004": ("น้ำมะนาว", ["มะนาว"]),
    "BEV005": ("โซดา", ["น้ำโซดา"]), "BEV006": ("น้ำเปล่า", ["น้ำ"]),
    "BEV007": ("เบียร์สิงห์", ["สิงห์"]), "BEV008": ("เบียร์ช้าง", ["ช้าง"]),
    "BEV009": ("สมูทตี้", ["สมูทที่"]),
    "SID001": ("ข้าวสวย", []), "SID002": ("ข้าวเหนียว", []),
    "SID003": ("ไข่ดาว", ["fried egg", "ไข่เจียวดาว"]), "SID004": ("ผักเพิ่ม", ["ผักรวม"]),
}


def _enrich_th(items: list[dict]) -> list[dict]:
    """Attach nameTh/aliases from TH_NAMES_BY_ID so agents can match Thai orders."""
    out = []
    for it in items:
        th = TH_NAMES_BY_ID.get(str(it.get("id", "")))
        if th and not it.get("nameTh"):
            it = {**it, "nameTh": th[0], "aliases": [th[0], *th[1]]}
        out.append(it)
    return out


@mcp.tool()
def get_categories() -> list[dict]:
    """Get all menu categories (active only, sorted by order). Data from Live API."""
    data = _api_get("/pos/categories")
    if isinstance(data, list) and data:
        return data
    # fallback: public categories endpoint
    data = _api_get("/pos/public/menu/categories")
    if isinstance(data, list) and data:
        return data
    return _fallback_categories()


def _fallback_categories() -> list[dict]:
    return [
        {"id": "cat_app", "name": "Appetizer", "sort_order": 1},
        {"id": "cat_main", "name": "Main Course", "sort_order": 2},
        {"id": "cat_des", "name": "Dessert", "sort_order": 3},
        {"id": "cat_bev", "name": "Beverage", "sort_order": 4},
        {"id": "cat_side", "name": "Side Dish", "sort_order": 5},
    ]


_CATEGORY_ALIASES = {
    "app": "Appetizer", "catapp": "Appetizer", "appetizer": "Appetizer", "appetizers": "Appetizer",
    "main": "Main Course", "catmain": "Main Course", "maincourse": "Main Course", "mains": "Main Course",
    "des": "Dessert", "catdes": "Dessert", "dessert": "Dessert", "desserts": "Dessert",
    "bev": "Beverage", "catbev": "Beverage", "beverage": "Beverage", "beverages": "Beverage",
    "drink": "Beverage", "drinks": "Beverage",
    "sid": "Side Dish", "catsid": "Side Dish", "catside": "Side Dish", "sidedish": "Side Dish",
    "side": "Side Dish", "sides": "Side Dish",
}


def _norm_category(cat: str) -> str:
    """Map ID-prefix/short forms (APP, sid, cat_main...) to live-API category names."""
    c = (cat or "").strip()
    if not c:
        return ""
    key = c.lower().replace("_", "").replace("-", "").replace(" ", "")
    return _CATEGORY_ALIASES.get(key, c)


@mcp.tool()
def get_menu(category: str = "") -> list[dict]:
    """
    Get menu items from Live API. Optionally filter by category name or id.
    
    Args:
        category: Filter by category name (e.g. "Appetizer", "Main Course") or id ("cat_app"). Empty = all.
    """
    category = _norm_category(category)
    data = _api_get("/pos/menu", params={"category": category} if category else None)
    if isinstance(data, list) and data:
        return _enrich_th(data)
    # fallback: public menu endpoint
    data = _api_get("/pos/public/menu", params={"category": category} if category else None)
    if isinstance(data, list) and data:
        return _enrich_th(data)
    return _get_mock_menu(category)


@mcp.tool()
def search_menu(query: str) -> list[dict]:
    """
    Search menu items by name (case-insensitive). Searches the full Live API menu.
    
    Args:
        query: Search keyword (e.g. "ผัด", "ไก่", "pad thai")
    """
    items = _api_get("/pos/menu")
    if not (isinstance(items, list) and items):
        items = _api_get("/pos/public/menu")
    if not (isinstance(items, list) and items):
        items = _get_mock_menu()
    items = _enrich_th(items)

    def _norm(s: str) -> str:
        return str(s or "").lower().replace(" ", "")

    def _variants(q: str) -> list[str]:
        # classic Thai typos: กระ <-> กะ
        vs = {q}
        if "\u0e01\u0e23\u0e30" in q:
            vs.add(q.replace("\u0e01\u0e23\u0e30", "\u0e01\u0e30"))
        if "\u0e01\u0e30" in q:
            vs.add(q.replace("\u0e01\u0e30", "\u0e01\u0e23\u0e30"))
        return sorted(vs, key=len, reverse=True)

    def _match_one(nqv: str) -> list[dict]:
        return [
            i for i in items
            if nqv in _norm(i.get("name", ""))
            or nqv in _norm(i.get("description", ""))
            or nqv in _norm(i.get("nameTh", ""))
            or (_norm(i.get("nameTh", "")) and _norm(i.get("nameTh", "")) in nqv)
            or any(nqv in _norm(a) or _norm(a) in nqv for a in i.get("aliases", []) if len(_norm(a)) >= 3)
        ]

    seen: set[str] = set()
    out: list[dict] = []

    def _add(matches: list[dict]) -> None:
        for i in matches:
            iid = i.get("id")
            if iid and iid not in seen:
                seen.add(iid)
                out.append(i)

    nq = _norm(query)
    for v in _variants(nq):
        _add(_match_one(v))
    if not out:
        import re as _re
        tokens = [t for t in _re.split(r"[\s,+/&]+|\u0e41\u0e25\u0e30|\u0e01\u0e31\u0e1a", query) if t.strip()]
        for tok in tokens:
            t = _norm(tok)
            if len(t) >= 3:
                for v in _variants(t):
                    _add(_match_one(v))
    return out


@mcp.tool()
def get_order(order_id: str) -> dict | None:
    """
    Get order details by order ID from Live API.
    
    Args:
        order_id: Order ID (e.g. "ORD-001", "ORD-abc123")
    """
    return _api_get(f"/pos/orders/{order_id}")


@mcp.tool()
def get_tables() -> list[dict]:
    """Get all tables (21 tables / 6 zones) and their current status from Live API."""
    data = _api_get("/pos/tables")
    if isinstance(data, list) and data:
        return data
    return _mock_tables()


# ── LINE Flex receipt (push after order created) ─────────────────────────

_LINE_CFG_PATH = "/home/openhands/.openclaw/openclaw.json"
_DEFAULT_PUSH_TO = "U59a6080f40e4ac45f07b1ae17d41875f"  # Pete's LINE user id


def _baht(v) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return f"฿{f:,.2f}".replace(".00", "")


def _load_line_token() -> str | None:
    try:
        cfg = json.load(open(_LINE_CFG_PATH))
        acc = cfg.get("channels", {}).get("line", {}).get("accounts", {}).get("pos_bot", {})
        tok = acc.get("channelAccessToken") or acc.get("token")
        return tok or None
    except Exception:
        return None


def _item_label(item_id: str, fallback: str) -> str:
    th = TH_NAMES_BY_ID.get(str(item_id))
    if isinstance(th, dict):
        return th.get("nameTh") or fallback
    if isinstance(th, str):
        return th
    return fallback


def _order_flex(order: dict) -> dict:
    oid = order.get("order_id", "-")
    takeaway = str(order.get("table_id", "")) == "takeaway"
    place = "🥡 Take-away" if takeaway else f"🍽 {order.get('table_name') or order.get('table_id', '')}"

    rows = []
    for it in order.get("items", []):
        label = _item_label(it.get("item_id"), it.get("name", ""))
        qty = int(it.get("quantity") or 1)
        rows.append({
            "type": "box", "layout": "horizontal", "margin": "sm",
            "contents": [
                {"type": "text", "text": label, "size": "sm", "wrap": True, "flex": 4, "color": "#333333"},
                {"type": "text", "text": f"x{qty}", "size": "sm", "flex": 1, "align": "end", "color": "#888888"},
                {"type": "text", "text": _baht(it.get("line_total")), "size": "sm", "flex": 2, "align": "end"},
            ],
        })

    def fee_row(label: str, value) -> dict:
        return {
            "type": "box", "layout": "horizontal", "margin": "sm",
            "contents": [
                {"type": "text", "text": label, "size": "xs", "color": "#888888", "flex": 5},
                {"type": "text", "text": _baht(value), "size": "xs", "align": "end", "color": "#888888", "flex": 2},
            ],
        }

    body_contents = rows + [{"type": "separator", "margin": "md"}]
    if order.get("service_charge"):
        body_contents.append(fee_row("ค่าบริการ", order["service_charge"]))
    if order.get("vat"):
        body_contents.append(fee_row("ภาษีมูลค่าเพิม (VAT)", order["vat"]))
    body_contents.append({
        "type": "box", "layout": "horizontal", "margin": "md",
        "contents": [
            {"type": "text", "text": "ยอดรวม", "size": "lg", "weight": "bold", "flex": 5},
            {"type": "text", "text": _baht(order.get("grand_total")), "size": "lg", "weight": "bold",
             "align": "end", "color": "#07c160", "flex": 3},
        ],
    })

    return {
        "type": "bubble",
        "header": {
            "type": "box", "layout": "vertical", "backgroundColor": "#16213e",
            "paddingAll": "16px", "contents": [
                {"type": "text", "text": "🧾 POS ORDER", "color": "#f5a623", "size": "xs", "weight": "bold"},
                {"type": "text", "text": oid, "color": "#ffffff", "size": "lg", "weight": "bold"},
                {"type": "text", "text": place, "color": "#aab4cc", "size": "xs", "margin": "sm"},
            ],
        },
        "body": {"type": "box", "layout": "vertical", "paddingAll": "16px", "contents": body_contents},
        "footer": {
            "type": "box", "layout": "vertical", "paddingAll": "12px",
            "contents": [{
                "type": "button", "style": "primary", "color": "#16213e",
                "action": {"type": "uri", "label": "📋 ดูที่ pos.m2igen.com", "uri": "https://pos.m2igen.com"},
            }],
        },
    }


def _push_line_flex(order: dict) -> None:
    """Best-effort push of a Flex receipt. NEVER raises — ordering must not break."""
    try:
        token = _load_line_token()
        if not token:
            logging.warning("[flex] no LINE token found; skip push")
            return
        to = os.environ.get("LINE_PUSH_TO", _DEFAULT_PUSH_TO).removeprefix("line:")
        message = {
            "to": to,
            "messages": [{
                "type": "flex",
                "altText": f"🧾 ออเดอร์ {order.get('order_id', '')} ยอดรวม {_baht(order.get('grand_total'))}",
                "contents": _order_flex(order),
            }],
        }
        import urllib.request
        req = urllib.request.Request(
            "https://api.line.me/v2/bot/message/push",
            data=json.dumps(message).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            logging.info("[flex] pushed receipt for %s -> %s (http %s)", order.get("order_id"), to, resp.status)
    except Exception as e:  # noqa: BLE001
        logging.warning("[flex] push failed (non-fatal): %s", e)


@mcp.tool()
def create_order(table_id: str, items_json: str, notes: str = "") -> dict:
    """
    Create a new POS order.
    
    Args:
        table_id: Table ID (e.g. "T01", "T02", "takeaway")
        items_json: JSON string of items array, e.g. '[{"item_id":"MAIN001","quantity":2}]'
        notes: Optional order notes
    """
    try:
        items = json.loads(items_json)
        payload = {
            "table_id": table_id,
            "items": items,
            "notes": notes,
        }
        result = _api_post("/pos/orders", payload)
        if result is None:
            return {"error": "Live API unavailable"}
        if isinstance(result, dict) and result.get("order_id") and not result.get("error"):
            full = _api_get(f"/pos/orders/{result['order_id']}")
            _push_line_flex(full if isinstance(full, dict) and full.get("items") else result)
        return result
    except json.JSONDecodeError as e:
        return {"error": f"Invalid items_json: {e}"}


# ── Mock Data (fallback when DB/API unavailable) ─────────────────────────

def _get_mock_menu(category: str = "") -> list[dict]:
    """Return mock menu items matching the ERP-less POS data."""
    items = [
        {"id": "APP001", "name": "Spring Rolls", "category": "Appetizer", "price": 59, "description": "เปาะเปี๊ยะทอด", "available": True},
        {"id": "APP002", "name": "Tom Yum Soup", "category": "Appetizer", "price": 89, "description": "ต้มยำ", "available": True},
        {"id": "APP003", "name": "Som Tum Thai", "category": "Appetizer", "price": 69, "description": "ส้มตำไทย", "available": True},
        {"id": "APP004", "name": "Satay Chicken (4 pcs)", "category": "Appetizer", "price": 79, "description": "สะเต๊ะไก่", "available": True},
        {"id": "APP005", "name": "Fish Cakes (6 pcs)", "category": "Appetizer", "price": 89, "description": "ทอดมันปลา", "available": True},
        {"id": "APP006", "name": "Tod Mun Goong", "category": "Appetizer", "price": 99, "description": "ทอดมันกุ้ง", "available": True},
        {"id": "APP007", "name": "Larb Gai", "category": "Appetizer", "price": 79, "description": "ลาบไก่", "available": True},
        {"id": "MAIN001", "name": "Pad Thai Goong", "category": "Main Course", "price": 89, "description": "ผัดไทยกุ้ง", "available": True},
        {"id": "MAIN002", "name": "Green Curry Chicken", "category": "Main Course", "price": 99, "description": "แกงเขียวหวานไก่", "available": True},
        {"id": "MAIN003", "name": "Massaman Curry", "category": "Main Course", "price": 109, "description": "แกงมัสมั่น", "available": True},
        {"id": "MAIN004", "name": "Pad Kra Pao Moo", "category": "Main Course", "price": 79, "description": "ผัดกะเพราหมู", "available": True},
        {"id": "MAIN005", "name": "Tom Kha Gai", "category": "Main Course", "price": 99, "description": "ต้มข่าไก่", "available": True},
        {"id": "MAIN006", "name": "Pad See Ew", "category": "Main Course", "price": 79, "description": "ผัดซีอิ๊ว", "available": True},
        {"id": "MAIN007", "name": "Khao Soi", "category": "Main Course", "price": 89, "description": "ข้าวซอย", "available": True},
        {"id": "MAIN008", "name": "Panang Curry", "category": "Main Course", "price": 99, "description": "พะแนง", "available": True},
        {"id": "MAIN009", "name": "Fried Rice Seafood", "category": "Main Course", "price": 109, "description": "ข้าวผัดทะเล", "available": True},
        {"id": "DES001", "name": "Mango Sticky Rice", "category": "Dessert", "price": 69, "description": "ข้าวเหนียวมะม่วง", "available": True},
        {"id": "DES002", "name": "Thai Roti", "category": "Dessert", "price": 49, "description": "โรตี", "available": True},
        {"id": "BEV001", "name": "Thai Iced Tea", "category": "Beverage", "price": 39, "description": "ชาเย็น", "available": True},
        {"id": "BEV002", "name": "Thai Iced Coffee", "category": "Beverage", "price": 45, "description": "กาแฟเย็น", "available": True},
        {"id": "BEV003", "name": "Coconut Water", "category": "Beverage", "price": 49, "description": "น้ำมะพร้าว", "available": True},
        {"id": "BEV004", "name": "Lemonade", "category": "Beverage", "price": 39, "description": "น้ำมะนาว", "available": True},
        {"id": "SID001", "name": "Steamed Rice", "category": "Side Dish", "price": 15, "description": "ข้าวเปล่า", "available": True},
        {"id": "SID002", "name": "Sticky Rice", "category": "Side Dish", "price": 15, "description": "ข้าวเหนียว", "available": True},
    ]
    if category:
        items = [i for i in items if i["category"] == category or i["category"] == _cat_id_to_name(category)]
    return items


def _cat_id_to_name(cat: str) -> str:
    mapping = {
        "cat_app": "Appetizer", "cat_main": "Main Course",
        "cat_des": "Dessert", "cat_bev": "Beverage", "cat_side": "Side Dish",
    }
    return mapping.get(cat, cat)


def _mock_tables() -> list[dict]:
    return [
        {"id": "T01", "name": "Table 1", "capacity": 2, "zone": "Indoor", "status": "available"},
        {"id": "T02", "name": "Table 2", "capacity": 2, "zone": "Indoor", "status": "available"},
        {"id": "T03", "name": "Table 3", "capacity": 4, "zone": "Indoor", "status": "available"},
        {"id": "T04", "name": "Table 4", "capacity": 4, "zone": "Indoor", "status": "available"},
        {"id": "T05", "name": "Table 5", "capacity": 6, "zone": "Indoor", "status": "available"},
        {"id": "T06", "name": "Table 6", "capacity": 6, "zone": "Indoor", "status": "available"},
        {"id": "T12", "name": "Table 12", "capacity": 2, "zone": "Garden", "status": "available"},
        {"id": "T13", "name": "VIP Room A", "capacity": 10, "zone": "VIP", "status": "available"},
    ]


# ── Main ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--http" in sys.argv:
        idx = sys.argv.index("--http")
        host_port = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ":8200"
        host, _, port_str = host_port.partition(":")
        port = int(port_str) if port_str else 8200
        logger.info("Starting POS MCP HTTP on %s:%d", host or "0.0.0.0", port)
        mcp.run(transport="sse", host=host or "0.0.0.0", port=port)
    else:
        logger.info("Starting POS MCP in stdio mode")
        mcp.run(transport="stdio")
