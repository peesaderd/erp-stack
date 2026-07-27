"""
Platform Adapter — Abstract layer สำหรับ Printful → หลาย Platform

Architecture:
  Printful API (supplier) → PlatformAdapter → Etsy, Amazon, Shopify, ...
  
ของใครของมัน: แต่ละ platform มี config + validation ของตัวเอง
  แต่ backend core (POD wizard, AI gen, Printful API) ใช้ร่วมกัน
"""

import os
import json
import logging
from typing import Optional

logger = logging.getLogger("platform-adapter")

# ─── Platform Registry ─────────────────────────────────────────────────

PLATFORMS = {
    "etsy": {
        "name": "Etsy",
        "icon": "🛍️",
        "description": "Etsy Marketplace — สินค้าแฮนด์เมด, วินเทจ, craft supplies",
        "sync_method": "printful_push",  # Printful POST /sync/products/push
        "requires_store_connection": True,
        "status": "active",
    },
    "amazon": {
        "name": "Amazon",
        "icon": "📦",
        "description": "Amazon Marketplace",
        "sync_method": "printful_push",
        "requires_store_connection": True,
        "status": "coming_soon",
    },
    "shopify": {
        "name": "Shopify",
        "icon": "🛒",
        "description": "Shopify Online Store",
        "sync_method": "printful_push",
        "requires_store_connection": True,
        "status": "coming_soon",
    },
    "woocommerce": {
        "name": "WooCommerce",
        "icon": "🌐",
        "description": "WooCommerce WordPress Store",
        "sync_method": "printful_push",
        "requires_store_connection": True,
        "status": "coming_soon",
    },
}


def get_platforms() -> dict:
    """Get all available platforms"""
    return {
        "ok": True,
        "platforms": PLATFORMS,
        "count": len(PLATFORMS),
    }


def get_platform(platform_id: str) -> Optional[dict]:
    """Get single platform config"""
    return PLATFORMS.get(platform_id)


# ─── Dashboard Stats ───────────────────────────────────────────────────

def get_dashboard_stats(platform_id: str = "etsy") -> dict:
    """
    Get dashboard summary stats for a platform.
    TODO: ดึงจาก Printful orders + local DB จริง
    ปัจจุบัน: mock data + คำนวณจาก Printful API call count
    """
    from pod_data import get_printful_api, PrintfulAPI
    
    # Try to get real data from Printful
    stats = {
        "total_listings": 0,
        "active_listings": 0,
        "total_orders": 0,
        "pending_orders": 0,
        "revenue_month": 0,
        "profit_month": 0,
        "platform": platform_id,
        "source": "local",
    }
    
    try:
        api = get_printful_api()
        key = api._load_printful_key() if api else ""
        if key:
            # Printful API key exists — real data possible
            stats["printful_connected"] = True
        else:
            stats["printful_connected"] = False
    except Exception:
        stats["printful_connected"] = False
    
    # POD wizard sessions count
    import os, glob
    sessions_dir = os.path.join(os.path.dirname(__file__), "sessions")
    if os.path.exists(sessions_dir):
        session_files = glob.glob(os.path.join(sessions_dir, "*.json"))
        stats["draft_sessions"] = len(session_files)
    
    return stats


# ─── Listing Management ────────────────────────────────────────────────

def get_listings(platform_id: str = "etsy", limit: int = 50, offset: int = 0) -> dict:
    """
    Get listings for a platform.
    TODO: อ่านจาก local DB (analyzed_products / post_queue) จริง
    """
    # For now, read from analyzed products as a source
    listings = []
    
    try:
        # Try reading from TUS products db
        import sqlite3
        tus_db = os.path.join(
            os.path.dirname(__file__), "..", "tiktok-ugc-studio", "tus_products.db"
        )
        if os.path.exists(tus_db):
            conn = sqlite3.connect(tus_db)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM analyzed_products ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = cur.fetchall()
            for row in rows:
                d = dict(row)
                listings.append({
                    "id": d.get("id"),
                    "title": d.get("title") or d.get("product_name") or "Untitled",
                    "title_th": d.get("title_th", ""),
                    "product_url": d.get("product_url", ""),
                    "image_url": d.get("image_url", ""),
                    "keywords": json.loads(d.get("keywords") or "[]"),
                    "platform": platform_id,
                    "status": "draft",
                    "price": d.get("price_estimate", 0),
                })
            conn.close()
            return {"ok": True, "listings": listings, "total": len(listings), "source": "tus_products"}
    except Exception as e:
        logger.warning(f"get_listings: {e}")
    
    return {"ok": True, "listings": listings, "total": 0, "source": "empty"}


# ─── Orders ────────────────────────────────────────────────────────────

def get_orders(platform_id: str = "etsy", limit: int = 20, offset: int = 0) -> dict:
    """
    Get orders for a platform.
    TODO: ดึงจาก Printful API / POS DB จริง
    """
    orders = []
    
    # Try POS orders as fallback
    try:
        import sqlite3
        pos_db = os.path.join(
            os.path.dirname(__file__), "..", "super-appsheet", "data", "pos.db"
        )
        if os.path.exists(pos_db):
            conn = sqlite3.connect(pos_db)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM orders ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = cur.fetchall()
            for row in rows:
                d = dict(row)
                orders.append({
                    "id": d.get("id"),
                    "order_number": d.get("order_number") or f"POS-{d.get('id')}",
                    "customer": d.get("customer_name") or "Walk-in",
                    "total": d.get("grand_total", 0),
                    "status": d.get("status", "pending"),
                    "items": json.loads(d.get("items") or "[]"),
                    "created_at": d.get("created_at", ""),
                    "platform": "pos",
                })
            conn.close()
    except Exception as e:
        logger.warning(f"get_orders: {e}")
    
    return {
        "ok": True,
        "orders": orders,
        "total": len(orders),
        "source": "pos_db" if orders else "empty",
    }


# ─── Analytics ─────────────────────────────────────────────────────────

def get_analytics(platform_id: str = "etsy", period: str = "30d") -> dict:
    """
    Get analytics data for a platform.
    TODO: real analytics from Printful/Platform API
    """
    return {
        "ok": True,
        "platform": platform_id,
        "period": period,
        "total_views": 0,
        "total_sales": 0,
        "conversion_rate": 0,
        "top_products": [],
        "revenue_chart": [],
        "source": "mock",
    }


# ─── Publish ───────────────────────────────────────────────────────────

def publish_to_platform(
    platform_id: str,
    product_data: dict,
) -> dict:
    """
    Publish product to platform via Printful.
    ใช้ Printful POST /sync/products/push
    
    TODO: ต้องมี Printful API key + connected store
    """
    from pod_data import get_printful_api
    
    api = get_printful_api()
    api_key = api._load_printful_key() if api else ""
    if not api_key:
        return {"ok": False, "error": "Printful API Key not configured — ตั้งค่าใน .env ก่อน"}
    
    # Build sync product payload
    sync_product = {
        "sync_product": {
            "name": product_data.get("title") or product_data.get("name", "Untitled"),
            "description": product_data.get("description", ""),
            "tags": ",".join(product_data.get("tags", [])),
        },
        "sync_variants": product_data.get("variants", []),
    }
    
    # If platform is Etsy, add Etsy-specific fields
    if platform_id == "etsy":
        sync_product["sync_product"]["external"] = {
            "etsy": {
                "who_made": product_data.get("who_made", "collective"),
                "when_made": product_data.get("when_made", "made_to_order"),
                "is_supply": product_data.get("is_supply", False),
                "is_customizable": product_data.get("is_customizable", False),
            }
        }
    
    # TODO: Call actual Printful API
    # For now, return planned payload
    return {
        "ok": True,
        "message": f"พร้อม publish ไปยัง {PLATFORMS.get(platform_id, {}).get('name', platform_id)}",
        "platform": platform_id,
        "payload": sync_product,
        "requires_printful_api_call": True,
    }
