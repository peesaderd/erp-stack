#!/usr/bin/env python3
"""
GPS Detection + Queue Manager Service
======================================
Phase 2 of POS Intelligence System.

GPS Detection endpoints:
  POST /gps/ping          — Receive GPS location from LINE/app
  GET  /gps/nearby        — Who's approaching? (geofence < 1km)
  GET  /gps/logs          — Recent location logs
  GET  /gps/customer/:name — GPS history for one customer

Queue Management endpoints:
  GET  /queue              — Current queue status (sorted by distance + priority)
  POST /queue/check-in     — Check in via GPS (auto or manual)
  POST /queue/pre-order    — Pre-order from LINE (creates queue + order)
  POST /queue/call         — Call next ticket
  POST /queue/complete     — Mark ticket served
  GET  /queue/wait-time    — Estimated wait time for party size

Health:
  GET  /health

Run: python3 gps_queue_service.py
Port: 8112
"""

import json
import math
import urllib.request
import urllib.error
import os
import uuid
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ── Config ──
SCHEMA_ENGINE = "http://localhost:8100"
HOST = "0.0.0.0"
PORT = 8112

# ร้านอาหารตำแหน่ง (Bangkok example — 13.7563, 100.5018)
SHOP_LAT = 13.7563
SHOP_LNG = 100.5018
GEOFENCE_METERS = 1000  # 1 km radius
GEOFENCE_NEARBY_METERS = 2000  # 2 km = nearby
GEOFENCE_APPROACHING_METERS = 3000  # 3 km = approaching
LINE_BOT_URL = os.environ.get("LINE_BOT_URL", "http://localhost:8140")
POS_API_URL = os.environ.get("POS_API_URL", "http://localhost:8114")

# ── POS Integration Helpers ──

def _create_pos_order(ticket_data: dict) -> dict:
    """Create a draft order in POS when a ticket is called/seated."""
    try:
        # Build order items from pre_order_items or create empty draft
        items = ticket_data.get("pre_order_items", [])
        if not items:
            # Create empty draft order — staff will add items
            items = []
        
        pos_items = []
        for item in items:
            pos_items.append({
                "item_id": item.get("item_id", item.get("name", "UNKNOWN")),
                "quantity": item.get("qty", 1),
                "notes": item.get("notes", ""),
            })
        
        # Use QUEUE table for queue orders (pre-defined in pos_engine.py)
        table_id = "QUEUE"
        
        url = f"{POS_API_URL}/pos/orders"
        body = json.dumps({"table_id": table_id, "items": pos_items}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            print(f"  📦 POS order created: {result.get('order_id', '?')}")
            return result
    except Exception as e:
        print(f"  ⚠️ POS order creation failed: {e}")
        return {"error": str(e)}


def _complete_pos_order(order_id: str) -> dict:
    """Mark POS order as completed."""
    try:
        url = f"{POS_API_URL}/pos/orders/{order_id}/status"
        body = json.dumps({"status": "completed"}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="PUT")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  ⚠️ POS order complete failed: {e}")
        return {"error": str(e)}


# ── LINE Bot Webhook Helpers ──

def _notify_line(customer_name: str, ticket: str, notify_type: str = "called", message: str = ""):
    """Push notification to LINE user via LINE Bot webhook."""
    try:
        url = f"{LINE_BOT_URL}/webhook/queue/notify"
        body = json.dumps({"customer_name": customer_name, "ticket": ticket, "type": notify_type, "message": message}).encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  ⚠️ LINE notify failed: {e}")
        return {"ok": False, "error": str(e)}


# ── Schema Engine Helpers ──

def schema_api(method, path, data=None):
    url = f"{SCHEMA_ENGINE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return {"error": json.loads(body).get("error", str(e))}
        except:
            return {"error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"error": str(e)}

def get_schema_data(slug, search=None):
    path = f"/api/v1/data/{slug}"
    if search:
        import urllib.parse
        path += f"?search={urllib.parse.quote(search)}"
    return schema_api("GET", path)

def create_record(slug, data):
    return schema_api("POST", f"/api/v1/data/{slug}", data)

def update_record(slug, record_id, data):
    return schema_api("PUT", f"/api/v1/data/{slug}/{record_id}", data)

def _calc_wait_time(party_size):
    """Estimate wait time based on party size and current queue."""
    result = get_schema_data("queue_ticket")
    tickets = [r.get("data", {}) for r in result.get("data", [])]
    waiting = [t for t in tickets if t.get("status") == "waiting"]
    
    # Base: 15 min per party ahead + 5 min per additional person
    base_wait = len(waiting) * 15 + (party_size - 1) * 5
    return max(base_wait, 15)  # minimum 15 min

# ── GPS Math ──

def haversine(lat1, lng1, lat2, lng2):
    """Distance in meters between two lat/lng points."""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def get_geofence_status(dist_m):
    if dist_m <= GEOFENCE_METERS:
        return "arrived"
    elif dist_m <= GEOFENCE_NEARBY_METERS:
        return "nearby"
    elif dist_m <= GEOFENCE_APPROACHING_METERS:
        return "approaching"
    return "unknown"

# ── GPS Detection ──

def process_gps_ping(customer_name, lat, lng, phone="", source="line", accuracy=0):
    """Process a GPS ping: log it, check geofence, update any active queue ticket."""
    dist = haversine(SHOP_LAT, SHOP_LNG, lat, lng)
    status = get_geofence_status(dist)
    
    # 1. Log to Schema Engine
    log_entry = {
        "customer_name": customer_name,
        "phone": phone,
        "latitude": lat,
        "longitude": lng,
        "geofence_status": status,
        "accuracy": accuracy,
        "source": source,
        "notes": f"ระยะ {int(dist)}m จากร้าน → {status}",
    }
    result = create_record("location_log", log_entry)
    
    # 2. If arrived/nearby, check for active queue ticket
    if status in ("arrived", "nearby"):
        check_customer_queue(customer_name, phone, dist)
    
    return {
        "distance_meters": int(dist),
        "geofence_status": status,
        "logged": result.get("success", False),
    }

def check_customer_queue(customer_name, phone, dist):
    """Find active queue tickets for this customer and update GPS fields."""
    result = get_schema_data("queue_ticket")
    if not result.get("success"):
        return
    
    for rec in result.get("data", []):
        rd = rec.get("data", {})
        if rd.get("status") in ("waiting",) and (
            rd.get("customer_name", "").lower() == customer_name.lower()
            or (phone and rd.get("phone") == phone)
        ):
            # Update this ticket with GPS info
            rid = rec["id"]
            rd["gps_distance"] = int(dist)
            rd["gps_lat"] = SHOP_LAT  # We'd use actual customer GPS in real scenario
            rd["gps_lng"] = SHOP_LNG
            rd["estimated_arrival"] = (
                datetime.now(timezone.utc) + timedelta(minutes=max(1, int(dist / 80)))
            ).isoformat()
            if dist <= GEOFENCE_METERS:
                rd["notification_sent"] = True
            update_record("queue_ticket", rid, rd)

# ── Queue Management ──

def get_queue_sorted():
    """Get all active queue tickets sorted by distance + priority."""
    result = get_schema_data("queue_ticket")
    if not result.get("success"):
        return []
    
    tickets = []
    now = datetime.now(timezone.utc)
    
    for rec in result.get("data", []):
        rd = rec.get("data", {})
        if rd.get("status") not in ("waiting", "called"):
            continue
        
        # Check hold
        hold_str = rd.get("hold_until", "")
        if hold_str:
            try:
                hold_dt = datetime.fromisoformat(hold_str.replace("Z", "+00:00"))
                if hold_dt > now:
                    continue  # Not ready yet
            except:
                pass
        
        dist = rd.get("gps_distance", 999999) or 999999
        priority = rd.get("priority", 0) or 0
        
        score = priority * 1000 - (dist / 10)
        tickets.append({
            "record_id": rec["id"],
            "data": rd,
            "distance_meters": dist,
            "priority": priority,
            "score": score,
        })
    
    # Sort by score descending
    tickets.sort(key=lambda t: t["score"], reverse=True)
    return tickets

def estimate_wait(party_size):
    """Estimate wait time in minutes for given party size."""
    queue = get_queue_sorted()
    ahead = 0
    for t in queue:
        if t["data"].get("status") == "waiting":
            ps = t["data"].get("party_size", 1) or 1
            ahead += ps
    
    # Rough: 15 min per group of 2-4
    wait = max(5, (ahead // 2) * 15)
    return wait

# ── Cleanup ──

def cleanup_old_tickets(days=7):
    """Remove completed/cancelled tickets older than N days."""
    result = get_schema_data("queue_ticket")
    if not result.get("success"):
        return {"cleaned": 0, "error": result.get("error")}
    
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    cleaned = 0
    
    for rec in result.get("data", []):
        rd = rec.get("data", {})
        status = rd.get("status", "")
        
        # Only cleanup completed/cancelled tickets
        if status not in ("completed", "cancelled"):
            continue
        
        # Check age via served_at or created_at
        ts_str = rd.get("served_at", "") or rec.get("created_at", "")
        if not ts_str:
            continue
        
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if ts < cutoff:
                # Delete via Schema Engine
                del_result = schema_api("DELETE", f"/api/v1/data/queue_ticket/{rec['id']}")
                if del_result.get("success", False):
                    cleaned += 1
        except:
            pass
    
    return {"cleaned": cleaned, "cutoff": cutoff.isoformat()}

# ── Customer GPS History ──

def _normalize_name(name):
    """Normalize name for comparison: lowercase, strip, collapse spaces."""
    return " ".join(name.lower().split())

def get_customer_gps_history(customer_name):
    """Get GPS location history for a specific customer."""
    result = get_schema_data("location_log")
    if not result.get("success"):
        return {"customer": customer_name, "logs": [], "count": 0}
    
    norm_target = _normalize_name(customer_name)
    logs = []
    for rec in result.get("data", []):
        rd = rec.get("data", {})
        db_name = _normalize_name(rd.get("customer_name", ""))
        # Exact match or one contains the other (handles URL encoding issues)
        if db_name == norm_target or norm_target in db_name or db_name in norm_target:
            logs.append({
                "id": rec["id"],
                "latitude": rd.get("latitude"),
                "longitude": rd.get("longitude"),
                "geofence_status": rd.get("geofence_status"),
                "accuracy": rd.get("accuracy", 0),
                "source": rd.get("source", ""),
                "notes": rd.get("notes", ""),
                "time": rec.get("created_at", ""),
            })
    
    # Sort by time descending (newest first)
    logs.sort(key=lambda x: x.get("time", ""), reverse=True)
    
    # Get active queue ticket if any
    qt_result = get_schema_data("queue_ticket")
    active_ticket = None
    if qt_result.get("success"):
        for rec in qt_result.get("data", []):
            rd = rec.get("data", {})
            if (rd.get("customer_name", "").lower() == customer_name.lower()
                    and rd.get("status") in ("waiting", "called")):
                active_ticket = {
                    "ticket_number": rd.get("ticket_number"),
                    "status": rd.get("status"),
                    "party_size": rd.get("party_size", 1),
                    "source": rd.get("source", ""),
                    "estimated_wait_minutes": rd.get("estimated_wait_minutes", 0),
                }
                break
    
    return {
        "customer": customer_name,
        "logs": logs,
        "count": len(logs),
        "active_ticket": active_ticket,
    }

# ── HTTP Server ──

class GPSQueueHandler(BaseHTTPRequestHandler):
    
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def _send_html(self, html, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(html.encode())
    
    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            body = self.rfile.read(length)
            return json.loads(body)
        return {}
    
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        # Serve dashboard HTML
        if path in ("/dashboard", "/dashboard.html"):
            dashboard_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
            try:
                with open(dashboard_path, "r") as f:
                    html = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode())
            except FileNotFoundError:
                self._send_json({"error": "dashboard.html not found"}, 404)
            return
        
        if path == "/health":
            self._send_json({
                "status": "ok",
                "service": "gps-queue-service",
                "version": "1.0",
                "shop_location": {"lat": SHOP_LAT, "lng": SHOP_LNG},
                "geofence_meters": GEOFENCE_METERS,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        
        elif path == "/gps/nearby":
            # Fetch all location_log and filter in Python for latest unique per customer
            result = get_schema_data("location_log")
            nearby = []
            seen_customers = {}
            if result.get("success"):
                for rec in result.get("data", []):
                    rd = rec.get("data", {})
                    status = rd.get("geofence_status", "unknown")
                    if status in ("arrived", "nearby", "approaching"):
                        name = rd.get("customer_name", "")
                        # Keep only latest per customer
                        if name not in seen_customers or rec.get("created_at", "") > seen_customers[name]["time"]:
                            seen_customers[name] = {
                                "customer": name,
                                "phone": rd.get("phone", ""),
                                "status": status,
                                "lat": rd.get("latitude"),
                                "lng": rd.get("longitude"),
                                "time": rec.get("created_at", ""),
                            }
            nearby = list(seen_customers.values())
            self._send_json({"nearby": nearby, "count": len(nearby)})
        
        elif path == "/queue":
            queue = get_queue_sorted()
            now_ts = datetime.now(timezone.utc).isoformat()
            tickets = []
            for t in queue:
                rd = t["data"]
                tickets.append({
                    "ticket": rd.get("ticket_number", "?"),
                    "customer": rd.get("customer_name", "?"),
                    "party_size": rd.get("party_size", 1),
                    "status": rd.get("status"),
                    "distance_m": t["distance_meters"],
                    "priority": t["priority"],
                    "estimated_arrival": rd.get("estimated_arrival", ""),
                    "source": rd.get("source", ""),
                    "wait_estimate": estimate_wait(rd.get("party_size", 1)),
                })
            self._send_json({
                "queue": tickets,
                "count": len(tickets),
                "timestamp": now_ts,
            })
        
        elif path == "/queue/wait-time":
            ps = int(params.get("party_size", [2])[0])
            wait = estimate_wait(ps)
            self._send_json({"party_size": ps, "estimated_wait_minutes": wait})
        
        elif path.startswith("/gps/logs"):
            result = get_schema_data("location_log")
            logs = []
            if result.get("success"):
                for rec in result.get("data", []):
                    rd = rec.get("data", {})
                    logs.append({
                        "id": rec["id"],
                        "customer": rd.get("customer_name", "?"),
                        "lat": rd.get("latitude"),
                        "lng": rd.get("longitude"),
                        "status": rd.get("geofence_status"),
                        "source": rd.get("source"),
                        "time": rd.get("created_at", ""),
                    })
            self._send_json({"logs": logs, "count": len(logs)})
        
        elif path.startswith("/gps/customer/"):
            # /gps/customer/สมชาย → extract name from path
            customer_name = path.split("/gps/customer/", 1)[1]
            if not customer_name:
                self._send_json({"error": "customer name required in path"}, 400)
                return
            # URL decode the name (handle double-encoding)
            import urllib.parse as _up
            customer_name = _up.unquote(_up.unquote(customer_name))
            # Also try raw path segment as-is (some clients don't encode)
            history = get_customer_gps_history(customer_name)
            # If no results, try matching with the raw URL segment
            if history["count"] == 0:
                raw_name = path.split("/gps/customer/", 1)[1]
                if raw_name != customer_name:
                    history = get_customer_gps_history(raw_name)
            self._send_json(history)
        
        elif path == "/queue/cleanup":
            # Manual trigger for cleanup (or could be called by cron)
            days = int(params.get("days", [7])[0])
            result = cleanup_old_tickets(days)
            self._send_json(result)
        
        elif path == "/analytics":
            # Analytics Dashboard HTML
            html = open(os.path.join(os.path.dirname(__file__), "analytics.html")).read()
            self._send_html(html)
        
        elif path == "/queue/analytics":
            result = get_schema_data("queue_ticket")
            tickets = [r.get("data", {}) for r in result.get("data", [])]
            
            total = len(tickets)
            completed = len([t for t in tickets if t.get("status") == "completed"])
            waiting = len([t for t in tickets if t.get("status") == "waiting"])
            called = len([t for t in tickets if t.get("status") == "called"])
            
            # Wait time stats (from created_at to served_at)
            wait_times = []
            for t in tickets:
                if t.get("served_at") and t.get("created_at"):
                    try:
                        created = datetime.fromisoformat(t["created_at"].replace("Z", "+00:00"))
                        served = datetime.fromisoformat(t["served_at"].replace("Z", "+00:00"))
                        wait_min = (served - created).total_seconds() / 60
                        if 0 < wait_min < 480:  # skip outliers > 8 hours
                            wait_times.append(wait_min)
                    except:
                        pass
            
            avg_wait = round(sum(wait_times) / len(wait_times), 1) if wait_times else 0
            max_wait = round(max(wait_times), 1) if wait_times else 0
            min_wait = round(min(wait_times), 1) if wait_times else 0
            
            # Peak hours
            hourly = {}
            for t in tickets:
                created = t.get("created_at", "")
                if "T" in created:
                    hour = int(created.split("T")[1].split(":")[0])
                    hourly[hour] = hourly.get(hour, 0) + 1
            
            peak_hour = max(hourly, key=hourly.get) if hourly else None
            
            # Source breakdown
            sources = {}
            for t in tickets:
                src = t.get("source", "unknown")
                sources[src] = sources.get(src, 0) + 1
            
            # Revenue (from POS)
            revenue_tickets = [t for t in tickets if t.get("pos_order_id")]
            
            self._send_json({
                "total_tickets": total,
                "waiting": waiting,
                "called": called,
                "completed": completed,
                "avg_wait_minutes": avg_wait,
                "max_wait_minutes": max_wait,
                "min_wait_minutes": min_wait,
                "peak_hour": peak_hour,
                "hourly_distribution": dict(sorted(hourly.items())),
                "sources": sources,
                "revenue_tickets": len(revenue_tickets),
            })
        
        else:
            self._send_json({"error": "not found"}, 404)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        try:
            body = self._read_body()
        except:
            self._send_json({"error": "invalid json body"}, 400)
            return
        
        if path == "/gps/ping":
            name = body.get("customer_name", "")
            lat = body.get("latitude")
            lng = body.get("longitude")
            phone = body.get("phone", "")
            source = body.get("source", "line")
            accuracy = body.get("accuracy", 0)
            
            if not name or lat is None or lng is None:
                self._send_json({"error": "customer_name, latitude, longitude required"}, 400)
                return
            
            result = process_gps_ping(name, lat, lng, phone, source, accuracy)
            self._send_json(result)
        
        elif path == "/queue/check-in":
            name = body.get("customer_name", "")
            phone = body.get("phone", "")
            party_size = body.get("party_size", 1)
            lat = body.get("latitude")
            lng = body.get("longitude")
            source = body.get("source", "gps")
            
            if not name:
                self._send_json({"error": "customer_name required"}, 400)
                return
            
            # Calculate distance
            dist_m = haversine(SHOP_LAT, SHOP_LNG, lat, lng) if lat and lng else 0
            wait = estimate_wait(party_size)
            
            # Create queue ticket
            ticket_num = f"Q-{datetime.now().strftime('%H%M')}-{uuid.uuid4().hex[:4].upper()}"
            ticket = {
                "ticket_number": ticket_num,
                "customer_name": name,
                "phone": phone,
                "party_size": party_size,
                "status": "waiting",
                "source": source,
                "gps_distance": int(dist_m),
                "gps_lat": lat,
                "gps_lng": lng,
                "estimated_wait_minutes": wait,
                "estimated_arrival": datetime.now(timezone.utc).isoformat() if dist_m <= GEOFENCE_METERS else "",
                "notes": f"Check-in via {source}, {int(dist_m)}m from shop",
            }
            result = create_record("queue_ticket", ticket)
            
            if result.get("success"):
                # Store LINE user_id mapping for push notifications
                user_id = body.get("user_id", "")
                if user_id and source == "line":
                    try:
                        url = f"{LINE_BOT_URL}/webhook/queue/checkin"
                        body_data = json.dumps({"customer_name": name, "user_id": user_id}).encode()
                        req = urllib.request.Request(url, data=body_data, headers={"Content-Type": "application/json"}, method="POST")
                        urllib.request.urlopen(req, timeout=5)
                    except Exception as e:
                        print(f"  ⚠️ LINE mapping failed: {e}")

                self._send_json({
                    "ticket": ticket_num,
                    "customer": name,
                    "party_size": party_size,
                    "estimated_wait_minutes": wait,
                    "distance_meters": int(dist_m),
                }, 201)
            else:
                self._send_json({"error": f"create failed: {result.get('error', '?')}"}, 500)
        
        elif path == "/queue/pre-order":
            name = body.get("customer_name", "")
            phone = body.get("phone", "")
            items = body.get("items", [])
            party_size = body.get("party_size", 1)
            lat = body.get("latitude")
            lng = body.get("longitude")
            
            if not name or not items:
                self._send_json({"error": "customer_name and items required"}, 400)
                return
            
            dist_m = haversine(SHOP_LAT, SHOP_LNG, lat, lng) if lat and lng else 0
            wait = estimate_wait(party_size)
            
            ticket_num = f"P-{datetime.now().strftime('%H%M')}-{uuid.uuid4().hex[:4].upper()}"
            items_str = ", ".join(f"{i.get('name','?')}×{i.get('qty',1)}" for i in items)
            
            ticket = {
                "ticket_number": ticket_num,
                "customer_name": name,
                "phone": phone,
                "party_size": party_size,
                "status": "waiting",
                "source": "line_preorder",
                "gps_distance": int(dist_m),
                "gps_lat": lat,
                "gps_lng": lng,
                "estimated_wait_minutes": wait,
                "pre_order_items": items,
                "notes": f"Pre-order: {items_str}",
            }
            result = create_record("queue_ticket", ticket)
            
            if result.get("success"):
                self._send_json({
                    "ticket": ticket_num,
                    "customer": name,
                    "items": items,
                    "estimated_wait_minutes": wait,
                }, 201)
            else:
                self._send_json({"error": f"create failed: {result.get('error', '?')}"}, 500)
        
        elif path == "/queue/call":
            ticket_id = body.get("ticket") or body.get("ticket_id") or body.get("ticket_number") or ""
            if not ticket_id:
                self._send_json({"error": "ticket required (UUID or ticket_number like Q-0842-a1b2)"}, 400)
                return
            
            result = get_schema_data("queue_ticket")
            found = None
            for rec in result.get("data", []):
                if rec["id"] == ticket_id or rec.get("data", {}).get("ticket_number") == ticket_id:
                    found = rec
                    break
            
            if not found:
                self._send_json({"error": f"ticket '{ticket_id}' not found"}, 404)
                return
            
            rd = found["data"]
            rd["status"] = "called"
            rd["called_at"] = datetime.now(timezone.utc).isoformat()
            up = update_record("queue_ticket", found["id"], rd)
            
            # Notify customer via LINE
            _notify_line(rd.get("customer_name", ""), rd.get("ticket_number", ""), "called")
            
            # Create POS order if pre-order items exist
            pos_order = None
            if rd.get("pre_order_items"):
                pos_order = _create_pos_order(rd)
                if pos_order and pos_order.get("order_id"):
                    rd["pos_order_id"] = pos_order["order_id"]
                    update_record("queue_ticket", found["id"], rd)
            
            self._send_json({
                "success": up.get("success", False),
                "ticket": rd.get("ticket_number"),
                "customer": rd.get("customer_name"),
                "status": "called",
                "pos_order_id": pos_order.get("order_id") if pos_order else None,
            })
        
        elif path == "/queue/complete":
            ticket_id = body.get("ticket") or body.get("ticket_id") or body.get("ticket_number") or ""
            if not ticket_id:
                self._send_json({"error": "ticket required (UUID or ticket_number like Q-0842-a1b2)"}, 400)
                return
            
            result = get_schema_data("queue_ticket")
            found = None
            for rec in result.get("data", []):
                if rec["id"] == ticket_id or rec.get("data", {}).get("ticket_number") == ticket_id:
                    found = rec
                    break
            
            if not found:
                self._send_json({"error": f"ticket '{ticket_id}' not found"}, 404)
                return
            
            rd = found["data"]
            rd["status"] = "completed"
            rd["served_at"] = datetime.now(timezone.utc).isoformat()
            up = update_record("queue_ticket", found["id"], rd)
            
            # Notify customer via LINE
            _notify_line(rd.get("customer_name", ""), rd.get("ticket_number", ""), "completed")
            
            self._send_json({
                "success": up.get("success", False),
                "ticket": rd.get("ticket_number"),
                "customer": rd.get("customer_name"),
                "status": "completed",
            })
        
        elif path == "/webhook/pos/payment":
            # POS notifies GPS Queue when payment is completed
            order_id = body.get("order_id", "")
            if not order_id:
                self._send_json({"error": "order_id required"}, 400)
                return
            
            # Find queue ticket by pos_order_id
            result = get_schema_data("queue_ticket")
            found = None
            for rec in result.get("data", []):
                rd = rec.get("data", {})
                if rd.get("pos_order_id") == order_id:
                    found = rec
                    break
            
            if not found:
                self._send_json({"error": f"no queue ticket for order {order_id}"}, 404)
                return
            
            rd = found["data"]
            rd["status"] = "completed"
            rd["served_at"] = datetime.now(timezone.utc).isoformat()
            rd["payment_completed"] = True
            up = update_record("queue_ticket", found["id"], rd)
            
            # Notify customer via LINE
            _notify_line(rd.get("customer_name", ""), rd.get("ticket_number", ""), "completed", 
                        f"✅ ชำระเงินเรียบร้อย! คิว {rd.get('ticket_number', '')} เสร็จสิ้น")
            
            self._send_json({
                "success": up.get("success", False),
                "ticket": rd.get("ticket_number"),
                "status": "completed",
            })
        
        # ── Walk-in Check-in ──
        elif path == "/queue/walk-in":
            # Walk-in: customer arrives at kiosk, auto check-in
            customer_name = body.get("customer_name", f"Walk-in {datetime.now(timezone.utc).strftime('%H%M')}")
            party_size = body.get("party_size", 1)
            phone = body.get("phone", "")
            
            ticket_number = f"W-{datetime.now(timezone.utc).strftime('%m%d')}-{uuid.uuid4().hex[:4].upper()}"
            ticket_data = {
                "ticket_number": ticket_number,
                "customer_name": customer_name,
                "phone": phone,
                "party_size": party_size,
                "status": "waiting",
                "source": "kiosk",
                "gps_distance": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "pre_order_items": [],
            }
            
            res = create_record("queue_ticket", ticket_data)
            print(f"  🎫 Walk-in: {ticket_number} ({customer_name}, party={party_size})")
            
            self._send_json({
                "ticket": ticket_number,
                "customer": customer_name,
                "party_size": party_size,
                "position": len(get_schema_data("queue_ticket").get("data", [])),
            }, 201)
        
        # ── Web Booking ──
        elif path == "/queue/book":
            # Web booking: customer books online
            customer_name = body.get("customer_name", "")
            party_size = body.get("party_size", 2)
            phone = body.get("phone", "")
            booking_time = body.get("booking_time", "")
            pre_order_items = body.get("items", [])
            
            if not customer_name:
                self._send_json({"error": "customer_name required"}, 400)
                return
            
            ticket_number = f"B-{datetime.now(timezone.utc).strftime('%m%d')}-{uuid.uuid4().hex[:4].upper()}"
            ticket_data = {
                "ticket_number": ticket_number,
                "customer_name": customer_name,
                "phone": phone,
                "party_size": party_size,
                "status": "waiting",
                "source": "web",
                "gps_distance": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "pre_order_items": pre_order_items,
                "booking_time": booking_time,
            }
            
            res = create_record("queue_ticket", ticket_data)
            print(f"  🌐 Web booking: {ticket_number} ({customer_name}, party={party_size})")
            
            self._send_json({
                "ticket": ticket_number,
                "customer": customer_name,
                "party_size": party_size,
                "booking_time": booking_time,
                "estimated_wait_minutes": _calc_wait_time(party_size),
            }, 201)
        
        else:
            self._send_json({"error": "not found"}, 404)
    
    def log_message(self, format, *args):
        print(f"  🌐 {args[0]} {args[1]} {args[2]}")

def main():
    print("=" * 55)
    print("  🛰️  GPS Detection + Queue Manager Service")
    print(f"  ⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"  📍 Shop: {SHOP_LAT}, {SHOP_LNG}")
    print(f"  🎯 Geofence: {GEOFENCE_METERS}m")
    print(f"  🔌 http://{HOST}:{PORT}")
    print("=" * 55)
    print("  Endpoints:")
    print("    GET  /health              — Health check")
    print("    POST /gps/ping            — Receive GPS location")
    print("    GET  /gps/nearby          — Who's near?")
    print("    GET  /gps/logs            — Location history")
    print("    GET  /gps/customer/:name  — GPS history for customer")
    print("    GET  /queue               — Queue sorted by distance")
    print("    POST /queue/check-in      — Check in via GPS")
    print("    POST /queue/pre-order     — Pre-order from LINE")
    print("    POST /queue/call          — Call next ticket (id or number)")
    print("    POST /queue/complete      — Complete ticket (id or number)")
    print("    GET  /queue/wait-time     — Estimate wait")
    print("    GET  /queue/cleanup?days=7 — Cleanup old tickets")
    print("    POST /webhook/pos/payment — POS payment completed webhook")
    print("    POST /queue/walk-in       — Walk-in check-in (kiosk)")
    print("    POST /queue/book          — Web booking")
    print("    GET  /queue/analytics     — Queue statistics")
    print("    GET  /analytics           — Analytics Dashboard UI")
    print("    GET  /dashboard           — Queue Dashboard UI")
    print("=" * 55)
    
    server = HTTPServer((HOST, PORT), GPSQueueHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  👋 Shutting down...")
        server.server_close()

if __name__ == "__main__":
    main()
