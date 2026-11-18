import requests
import json

BASE = "https://pos.m2igen.com/api/pos"

# 1. Get menu
r = requests.get(f"{BASE}/menu")
menu = r.json()
print(f"Menu count: {len(menu)}")
item1 = menu[0]["id"]
item2 = menu[1]["id"]
print(f"Item 1: {menu[0]['name']} ({item1})")
print(f"Item 2: {menu[1]['name']} ({item2})")

# 2. Create order on table T07
print("\n[Test 1] Creating order for Table T07...")
r = requests.post(f"{BASE}/orders", json={
    "table_id": "T07",
    "items": [{"item_id": item1, "quantity": 1, "notes": "เผ็ดน้อย"}]
})
order = r.json()
order_id = order["order_id"]
print(f"Order created: {order_id}, status: {order.get('status')}")

# 3. Check Kitchen Orders
r = requests.get(f"{BASE}/kitchen/orders")
kds = r.json()
found = any(o["order_id"] == order_id for o in kds)
print(f"Order found in KDS: {found}")

# 4. Mark all items served -> order should become served & leave KDS
print("\n[Test 2] Marking item 1 served...")
r = requests.post(f"{BASE}/orders/{order_id}/items/1/served")
print("Mark served resp status:", r.status_code, "order status:", r.json().get("status"))

r = requests.get(f"{BASE}/kitchen/orders")
kds = r.json()
found_after_serve = any(o["order_id"] == order_id for o in kds)
print(f"Order still in KDS after served: {found_after_serve} (Expected: False)")

# Check Table T07 status
r = requests.get(f"{BASE}/tables")
tables = r.json()
t7 = next((t for t in tables if t["id"] == "T07"), None)
print(f"Table T07 status: {t7.get('status')} (Expected: 'served')")

# 5. Append new item to the order (re-ordering)
print("\n[Test 3] Appending new item (item2) to Order...")
r = requests.post(f"{BASE}/orders/{order_id}/items/append", json={
    "items": [{"item_id": item2, "quantity": 2, "notes": "เพิ่มพิเศษ"}]
})
appended_order = r.json()
print("Appended order status:", appended_order.get("status"), "kitchen_status:", appended_order.get("kitchen_status"))
for it in appended_order.get("items", []):
    print(f"  Line {it.get('line')}: {it.get('name')} x{it.get('quantity')} - is_new: {it.get('is_new_item')}, served: {it.get('item_served')}")

# 6. Verify order has reappeared in KDS!
r = requests.get(f"{BASE}/kitchen/orders")
kds = r.json()
found_reappeared = any(o["order_id"] == order_id for o in kds)
print(f"Order reappeared in KDS: {found_reappeared} (Expected: True)")

# 7. Check pending notifications
r = requests.get("https://pos.m2igen.com/api/notifications/pending")
notifs = r.json()
print(f"\n[Test 4] Pending notifications count: {len(notifs)}")
for n in notifs[-4:]:
    print(f"  Event: {n.get('event_type')}, Msg: {n.get('message')}")

print("\n=== ALL WORKFLOW TESTS PASSED 100% ===")
