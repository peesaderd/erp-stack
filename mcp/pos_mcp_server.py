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
POS_API_URL = os.environ.get("POS_API_URL", "http://localhost:8114")

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

@mcp.tool()
def get_categories() -> list[dict]:
    """Get all menu categories (active only, sorted by order)."""
    conn = _get_db()
    if not conn:
        return _fallback_categories()
    try:
        rows = conn.execute(
            "SELECT id, name, sort_order FROM pos_categories WHERE is_active = 1 ORDER BY sort_order, name"
        ).fetchall()
        conn.close()
        if rows:
            return [dict(r) for r in rows]
    except Exception:
        pass
    conn.close()
    return _fallback_categories()


def _fallback_categories() -> list[dict]:
    return [
        {"id": "cat_app", "name": "Appetizer", "sort_order": 1},
        {"id": "cat_main", "name": "Main Course", "sort_order": 2},
        {"id": "cat_des", "name": "Dessert", "sort_order": 3},
        {"id": "cat_bev", "name": "Beverage", "sort_order": 4},
        {"id": "cat_side", "name": "Side Dish", "sort_order": 5},
    ]


@mcp.tool()
def get_menu(category: str = "") -> list[dict]:
    """
    Get menu items. Optionally filter by category name or id.
    
    Args:
        category: Filter by category name (e.g. "Appetizer", "Main Course") or id ("cat_app"). Empty = all.
    """
    # Try loading from POS API first (includes ERP Core products if available)
    try:
        import httpx
        url = f"{POS_API_URL}/pos/public/menu"
        if category:
            url += f"?category={category}"
        resp = httpx.get(url, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            if data:
                return data
    except Exception:
        pass

    # Fallback to known menu items from pos_engine
    return _get_mock_menu(category)


@mcp.tool()
def search_menu(query: str) -> list[dict]:
    """
    Search menu items by name (case-insensitive).
    
    Args:
        query: Search keyword (e.g. "ผัด", "ไก่", "pad thai")
    """
    conn = _get_db()
    if conn:
        try:
            # Try searching from pos_orders items (historical order data for RAG)
            rows = conn.execute(
                "SELECT DISTINCT json_extract(value, '$.name') as name, "
                "json_extract(value, '$.price') as price "
                "FROM pos_orders, json_each(pos_orders.items) "
                "WHERE json_extract(value, '$.name') LIKE ? "
                "LIMIT 20",
                (f"%{query}%",)
            ).fetchall()
            conn.close()
            if rows:
                return [dict(r) for r in rows if r["name"]]
        except Exception:
            pass
        conn.close()

    # Fallback: search mock menu
    items = _get_mock_menu()
    query_lower = query.lower()
    return [i for i in items if query_lower in i["name"].lower() or query_lower in i.get("description", "").lower()]


@mcp.tool()
def get_order(order_id: str) -> dict | None:
    """
    Get order details by order ID.
    
    Args:
        order_id: Order ID (e.g. "ORD-001", "ORD-abc123")
    """
    conn = _get_db()
    if not conn:
        return {"error": "Database not available"}
    try:
        row = conn.execute("SELECT * FROM pos_orders WHERE order_id = ?", (order_id,)).fetchone()
        conn.close()
        if row:
            d = dict(row)
            d["items"] = json.loads(d.get("items", "[]"))
            return d
        return None
    except Exception as e:
        conn.close()
        return {"error": str(e)}


@mcp.tool()
def get_tables() -> list[dict]:
    """Get all tables and their current status (available/occupied/reserved)."""
    conn = _get_db()
    if not conn:
        return _mock_tables()
    try:
        # Get active orders to determine occupied tables
        active = conn.execute(
            "SELECT DISTINCT table_id, table_name FROM pos_orders WHERE status NOT IN ('paid', 'completed', 'cancelled')"
        ).fetchall()
        occupied_ids = {r["table_id"] for r in active}
        conn.close()
    except Exception:
        conn.close()
        occupied_ids = set()

    tables = _mock_tables()
    for t in tables:
        if t["id"] in occupied_ids:
            t["status"] = "occupied"
    return tables


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
        import httpx
        items = json.loads(items_json)
        payload = {
            "table_id": table_id,
            "items": items,
            "notes": notes,
        }
        resp = httpx.post(
            f"{POS_API_URL}/pos/orders",
            json=payload,
            timeout=10.0,
        )
        if resp.status_code in (200, 201):
            return resp.json()
        return {"error": f"API returned {resp.status_code}: {resp.text}"}
    except Exception as e:
        return {"error": str(e)}


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
