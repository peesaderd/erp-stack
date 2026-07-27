#!/usr/bin/env python3
"""
POS Intelligence Agent v2
=========================
Phase 1: Customer Memory Foundation

Reads orders directly from ERP Core SQLite database,
builds/updates customer profiles in Schema Engine,
writes profiles + daily summaries to BookStack.

Auto-run via cron:
    0 22 * * * cd /home/openhands/erp-stack && python3 modules/pos_intelligence/agent.py
"""

import json
import urllib.request
import urllib.error
import sqlite3
import os
import sys
import urllib.parse
from datetime import datetime, timezone, timedelta
from collections import Counter, defaultdict

# ── Config ──
SCHEMA_ENGINE = "http://localhost:8100"
BOOKSTACK_URL = "http://89.167.82.205:54515"
ERP_CORE_DB = "/home/openhands/erp-core/erp-core/packages/server/data/erp-core.db"

# BookStack auth
BS_AUTH = f"Token {os.environ.get('BOOKSTACK_TOKEN_ID', 'uZTNikZA8fqWiFIUWqPfWtDdjneoQ6qO')}:{os.environ.get('BOOKSTACK_TOKEN_SECRET', 'loc2XsVH5CcHzifBTROQq8YvKa5oVtyV')}"

# ── API Helpers ──

def schema_api(method, path, data=None):
    url = f"{SCHEMA_ENGINE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  ⚠️ Schema Engine: {e}")
        return None

def bs_api(method, path, data=None):
    url = f"{BOOKSTACK_URL}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"Authorization": BS_AUTH, "Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  ⚠️ BookStack HTTP {e.code}")
        return None
    except Exception as e:
        print(f"  ⚠️ BookStack: {e}")
        return None

# ── Data Layer ──

def get_all_orders():
    """Read orders + items directly from ERP Core SQLite."""
    print("  📦 Reading orders from ERP Core SQLite...")
    conn = sqlite3.connect(ERP_CORE_DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("""
        SELECT o.*, oi.name as item_name, oi.quantity, oi.unit_price, oi.total_price as item_total
        FROM orders o
        LEFT JOIN order_items oi ON oi.order_id = o.id
        ORDER BY o.created_at DESC
    """)
    
    rows = c.fetchall()
    
    # Group items by order
    orders_dict = {}
    for row in rows:
        oid = row["id"]
        if oid not in orders_dict:
            orders_dict[oid] = {
                "id": oid,
                "order_number": row["order_number"],
                "customer_name": row["customer_name"],
                "customer_email": row["customer_email"],
                "status": row["status"],
                "subtotal": row["subtotal"],
                "total": row["total"],
                "channel": row["channel"],
                "notes": row["notes"] or "",
                "created_at": row["created_at"],
                "customer_items": [],
            }
        if row["item_name"]:
            orders_dict[oid]["customer_items"].append({
                "name": row["item_name"],
                "qty": row["quantity"],
                "price": row["unit_price"],
            })
    
    conn.close()
    return list(orders_dict.values())

def get_products():
    """Get products for name resolution."""
    conn = sqlite3.connect(ERP_CORE_DB)
    c = conn.cursor()
    c.execute("SELECT id, name, sku FROM products")
    products = {row[0]: {"name": row[1], "sku": row[2]} for row in c.fetchall()}
    conn.close()
    return products

# ── Profile Builder ──

def build_profiles(orders, products=None):
    """Build customer profiles from order history."""
    print("  🔍 Building profiles from order data...")
    
    if products is None:
        products = {}
    
    # Group by customer name (case-insensitive)
    customer_groups = defaultdict(list)
    skip_names = {"", "unknown", "walk-in", "guest", "pos-take-away", "pos-table 1",
                  "test customer", "pos-table 2", "pos-table 3", "pos-table 4", "pos-table 5"}
    
    for order in orders:
        name = (order.get("customer_name") or "").strip()
        name_lower = name.lower()
        if not name or name_lower in skip_names:
            continue
        customer_groups[name].append(order)
    
    profiles = []
    for name, ords in customer_groups.items():
        total_visits = len(ords)
        total_value = sum(o.get("total", 0) or 0 for o in ords)
        avg_value = round(total_value / total_visits, 2) if total_visits else 0
        
        # Sort by date desc
        ords.sort(key=lambda o: o.get("created_at", 0), reverse=True)
        last = ords[0]
        last_ts = last.get("created_at", 0)
        last_date = datetime.fromtimestamp(last_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M") if last_ts else ""
        
        # Favorite items
        items_counter = Counter()
        all_items = []
        for o in ords:
            for item in o.get("customer_items", []):
                items_counter[item["name"]] += item.get("qty", 1)
                all_items.append(item["name"])
        
        favorites = [item for item, _ in items_counter.most_common(5)]
        
        # Recent items (last 3 orders)
        recent_items = []
        for o in ords[:3]:
            for item in o.get("customer_items", []):
                recent_items.append(item["name"])
        
        # Last order summary
        last_items_str = ", ".join(
            f"{item['name']}×{item['qty']}" 
            for item in last.get("customer_items", [])
        ) if last.get("customer_items") else "—"
        last_summary = f"สั่ง {last_items_str} รวม ฿{last.get('total', 0):.0f} ({last_date})"
        
        # Tier
        tier = "new"
        if total_visits >= 10 or total_value >= 10000:
            tier = "whale"
        elif total_visits >= 5 or total_value >= 3000:
            tier = "vip"
        elif total_visits >= 3:
            tier = "regular"
        
        # Churn risk (no visit > 30 days)
        now = datetime.now(timezone.utc)
        last_dt = datetime.fromtimestamp(last_ts, tz=timezone.utc) if last_ts else None
        days_since = (now - last_dt).days if last_dt else 999
        tags = []
        if days_since > 30:
            tags.append("⚠️ churn_risk")
        if total_visits >= 5:
            tags.append("frequent")
        if total_value >= 5000:
            tags.append("high_value")
        
        profile = {
            "name": name,
            "phone": "",
            "total_visits": total_visits,
            "lifetime_value": int(total_value),
            "avg_order_value": avg_value,
            "last_visit": last_date,
            "favorite_items": favorites,
            "allergens": [],
            "preferences": "",
            "tags": tags,
            "tier": tier,
            "last_order_summary": last_summary,
            "notes": "",
            "birthday": "",
        }
        profiles.append(profile)
    
    return profiles

# ── Schema Engine Sync ──

def sync_profile(profile):
    """Upsert one profile to Schema Engine."""
    name = profile["name"]
    
    # Search by name
    qname = urllib.parse.quote(name)
    result = schema_api("GET", f"/api/v1/data/customer_profile?search={qname}")
    existing = None
    if result and result.get("success"):
        records = result.get("data", [])
        for r in records:
            if r.get("data", {}).get("name", "").lower() == name.lower():
                existing = r
                break
    
    if existing:
        eid = existing["id"]
        ed = existing.get("data", {})
        # Merge: accumulate visits and value
        old_visits = ed.get("total_visits", 0) or 0
        old_ltv = ed.get("lifetime_value", 0) or 0
        
        # Only update if new data has more visits
        if profile["total_visits"] > old_visits:
            for k, v in profile.items():
                if v:  # don't overwrite with empty
                    if k == "lifetime_value":
                        ed[k] = old_ltv + v  # accumulate
                    elif k == "total_visits":
                        ed[k] = old_visits + v  # accumulate
                    elif k == "avg_order_value":
                        total_v = ed.get("total_visits", old_visits + profile["total_visits"])
                        ed[k] = round(ed.get("lifetime_value", 0) / total_v, 2) if total_v else 0
                    elif k in ("last_visit", "last_order_summary"):
                        ed[k] = v  # latest wins
                    elif k == "favorite_items":
                        existing_items = ed.get("favorite_items", []) or []
                        merged = list(dict.fromkeys(existing_items + v))
                        ed[k] = merged[:10]
                    elif k == "tags":
                        existing_tags = set(ed.get("tags", []) or [])
                        ed["tags"] = list(existing_tags | set(v))
                    else:
                        ed[k] = ed.get(k) or v
            
            # Recalculate tier
            visits = ed.get("total_visits", 0)
            ltv = ed.get("lifetime_value", 0)
            if visits >= 10 or ltv >= 10000:
                ed["tier"] = "whale"
            elif visits >= 5 or ltv >= 3000:
                ed["tier"] = "vip"
            elif visits >= 3:
                ed["tier"] = "regular"
            
            result = schema_api("PUT", f"/api/v1/data/customer_profile/{eid}", ed)
            if result and result.get("success"):
                print(f"  ✅ {name} — updated ({ed.get('total_visits')} visits, ฿{ed.get('lifetime_value')})")
            return ed
        else:
            print(f"  ⏩ {name} — no new data (already {old_visits} visits)")
            return ed
    else:
        result = schema_api("POST", "/api/v1/data/customer_profile", profile)
        if result and result.get("success"):
            print(f"  ✅ {name} — created ({profile['total_visits']} visits, ฿{profile['lifetime_value']})")
        return profile

# ── BookStack Writer ──

def write_bookstack(profiles, orders):
    """Write daily summary + customer profiles to BookStack."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # Total revenue from all orders (including anonymous)
    total_revenue = sum(o.get("total", 0) or 0 for o in orders)
    total_orders = len(orders)
    avg_order = round(total_revenue / total_orders, 2) if total_orders else 0
    
    profiles.sort(key=lambda p: p.get("lifetime_value", 0), reverse=True)
    
    # ── Daily Summary Page ──
    md = f"""# 📊 POS Intelligence — Daily Summary ({today})

## Today's POS Stats
| Metric | Value |
|--------|-------|
| **Total Orders (all-time)** | {total_orders} |
| **Total Revenue** | ฿{total_revenue:,.2f} |
| **Avg Order Value** | ฿{avg_order:,.2f} |
| **Customer Profiles** | {len(profiles)} |

## Customer Tiers
| Tier | Count | Criteria |
|------|-------|----------|
| 🐳 **Whale** | {sum(1 for p in profiles if p.get('tier') == 'whale')} | 10+ visits or ฿10K+ |
| ⭐ **VIP** | {sum(1 for p in profiles if p.get('tier') == 'vip')} | 5+ visits or ฿3K+ |
| 🔄 **Regular** | {sum(1 for p in profiles if p.get('tier') == 'regular')} | 3+ visits |
| 🆕 **New** | {sum(1 for p in profiles if p.get('tier') == 'new')} | < 3 visits |

## Top Customers by Lifetime Value
| Rank | Name | Visits | LTV | Tier |
|------|------|--------|-----|------|
"""
    for i, p in enumerate(profiles[:20], 1):
        md += f"| {i} | {p.get('name','-')} | {p.get('total_visits',0)} | ฿{p.get('lifetime_value',0):,} | {p.get('tier','new').upper()} |\n"
    
    # Churn risk
    md += "\n## ⚠️ Churn Risk (No visit > 30 days)\n"
    churned = [p for p in profiles if "churn_risk" in (p.get("tags") or [])]
    if churned:
        for p in churned:
            md += f"- {p.get('name','-')} — last visit: {p.get('last_visit','?')}, LTV: ฿{p.get('lifetime_value',0):,}\n"
    else:
        md += "- None identified ✅\n"
    
    # Seasoned items
    md += "\n## 🍽️ Most Ordered Items\n"
    item_counter = Counter()
    for o in orders:
        for item in o.get("customer_items", []):
            if item.get("name"):
                item_counter[item["name"]] += item.get("qty", 1)
    if item_counter:
        for item, count in item_counter.most_common(10):
            md += f"- {item} ({count} orders)\n"
    else:
        md += "- No item data available\n"
    
    md += "\n---\n*Auto-generated by POS Intelligence Agent*"
    
    page_name = f"POS Daily Summary — {today}"
    qpn = urllib.parse.quote(page_name)
    existing = bs_api("GET", f"/api/pages?filter[name]={qpn}")
    if existing and existing.get("data"):
        pid = existing["data"][0]["id"]
        bs_api("PUT", f"/api/pages/{pid}", {"name": page_name, "markdown": md})
        print(f"  📝 BookStack: Updated '{page_name}'")
    else:
        bs_api("POST", "/api/pages", {"book_id": 4, "name": page_name, "markdown": md})
        print(f"  📝 BookStack: Created '{page_name}'")
    
    # ── Customer Profile Pages ──
    chapters = bs_api("GET", "/api/chapters?book_id=4")
    chap_id = None
    if chapters:
        for ch in chapters.get("data", []):
            if ch["name"] == "Customer Profiles":
                chap_id = ch["id"]
                break
    
    if not chap_id:
        chap = bs_api("POST", "/api/chapters", {
            "book_id": 4,
            "name": "Customer Profiles",
            "description": "Customer memory profiles auto-built from POS data by AI Agent"
        })
        if chap:
            chap_id = chap["id"]
    
    if chap_id:
        for p in profiles:
            items_str = ", ".join(p.get("favorite_items", []) or [])
            tags_str = ", ".join(p.get("tags", []) or [])
            profile_md = f"""# 👤 {p.get('name','')}

## Profile

| Field | Value |
|-------|-------|
| **Tier** | {p.get('tier','new').upper()} |
| **Total Visits** | {p.get('total_visits', 0)} |
| **Lifetime Value** | ฿{p.get('lifetime_value', 0):,.2f} |
| **Avg Order Value** | ฿{p.get('avg_order_value', 0):,.2f} |
| **Last Visit** | {p.get('last_visit', 'N/A')} |
| **Phone** | {p.get('phone', '—')} |
| **Tags** | {tags_str or '—'} |
| **Birthday** | {p.get('birthday', '—')} |

## Favorites
{favorites_str if (favorites_str := items_str) else 'ยังไม่มีข้อมูล'}

## Preferences
{p.get('preferences') or 'ยังไม่มีข้อมูล'}

## Last Order
{p.get('last_order_summary', '—')}

## Notes
{p.get('notes', '—')}

---
*Auto-updated by POS Intelligence Agent | Last sync: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC*
"""
            pname = f"👤 {p.get('name','')}"
            qpn = urllib.parse.quote(pname[:100])
            existing_p = bs_api("GET", f"/api/pages?filter[name]={qpn}")
            
            if existing_p and existing_p.get("data"):
                pid = existing_p["data"][0]["id"]
                bs_api("PUT", f"/api/pages/{pid}", {"name": pname[:200], "markdown": profile_md})
            else:
                bs_api("POST", "/api/pages", {
                    "book_id": 4,
                    "chapter_id": chap_id,
                    "name": pname[:200],
                    "markdown": profile_md,
                })

# ── Main ──

def main():
    print("=" * 55)
    print("  🤖 POS Intelligence Agent v2")
    print(f"  ⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("=" * 55)
    
    if not os.path.exists(ERP_CORE_DB):
        print(f"  ❌ ERP Core DB not found at: {ERP_CORE_DB}")
        return
    
    # Step 1: Read all orders
    orders = get_all_orders()
    if not orders:
        print("  No orders found.")
        return
    
    named_orders = [o for o in orders if o.get("customer_name", "").strip().lower() not in 
                    {"", "unknown", "walk-in", "guest", "pos-take-away", "pos-table 1", "test customer",
                     "pos-table 2", "pos-table 3", "pos-table 4", "pos-table 5"}]
    anon_count = len(orders) - len(named_orders)
    print(f"  Orders: {len(orders)} ({len(named_orders)} named, {anon_count} anonymous)")
    
    # Step 2: Build profiles
    profiles = build_profiles(orders)
    print(f"  Customer profiles: {len(profiles)}")
    
    # Step 3: Sync to Schema Engine
    print("  ── Syncing to Schema Engine ──")
    for p in profiles:
        sync_profile(p)
    
    # Step 4: Write BookStack
    print("  ── Writing BookStack pages ──")
    write_bookstack(profiles, orders)
    
    print("=" * 55)
    print("  ✅ Phase 1: Customer Memory Complete!")
    print(f"  📊 {len(profiles)} profiles in Schema Engine")
    print(f"  📝 BookStack: Business Operations / Customer Profiles")
    print(f"  🔗 https://bookstack.m2igen.com")
    print("=" * 55)

if __name__ == "__main__":
    main()
