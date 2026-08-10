#!/usr/bin/env python3
"""
Voice Ordering System — Voice Gateway Service
==============================================
Phase 3 of POS Intelligence System.

Endpoints:
  POST /voice/incoming    — Receive audio URL → STT → NLP → Action
  POST /voice/text/message  — Direct text (for testing)
  POST /voice/respond     — Generate TTS audio
  GET  /voice/sessions    — Recent voice sessions
  POST /voice/preview     — Preview: see what agent would say with customer data
  GET  /health            — Health check

Run: python3 voice_gateway.py
Port: 8113
"""

import json
import urllib.request
import urllib.error
import os
import uuid
import base64
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ── Config ──
SCHEMA_ENGINE = "http://localhost:8100"
QUEUE_SERVICE = "http://localhost:8112"
CF_ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "c4c9b706dc3b71a3a6304531834a23db")
CF_TOKEN = os.environ.get("CF_WORKERS_AI_TOKEN", os.environ.get("CLOUDFLARE_AI_TOKEN", ""))
CLOUDFLARE_AI = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/run"
HOST = "0.0.0.0"
PORT = 8113

# ── Thai TTS Text Normalizer ──

_THAI_DIGITS = {'0': 'ศูนย์', '1': 'หนึ่ง', '2': 'สอง', '3': 'สาม', '4': 'สี่', '5': 'ห้า', '6': 'หก', '7': 'เจ็ด', '8': 'แปด', '9': 'เก้า'}

def _to_thai_num(n):
    """Convert integer to Thai number words (0-999)."""
    if n == 0:
        return "ศูนย์"
    if n < 10:
        return _THAI_DIGITS[str(n)]
    if n < 20:
        if n == 10:
            return "สิบ"
        return "สิบ" + _THAI_DIGITS[str(n - 10)]
    if n < 100:
        tens = n // 10
        ones = n % 10
        result = _THAI_DIGITS[str(tens)] + "สิบ"
        if ones:
            result += _THAI_DIGITS[str(ones)]
        return result
    hundreds = n // 100
    remainder = n % 100
    result = _THAI_DIGITS[str(hundreds)] + "ร้อย"
    if remainder:
        if remainder < 10:
            result += "เอ็ด" if remainder == 1 else _THAI_DIGITS[str(remainder)]
        else:
            result += _to_thai_num(remainder)
    return result


def _normalize_time(match):
    """Convert HH:MM to natural Thai time speech."""
    h, m = int(match.group(1)), int(match.group(2))
    if h < 6:
        period = "ตี"
        hour_word = _to_thai_num(h if h != 0 else 12)
    elif h < 12:
        period = ""
        hour_word = _to_thai_num(h)
    elif h < 13:
        period = ""
        hour_word = "สิบสอง"
    elif h < 18:
        period = "บ่าย"
        hour_word = _to_thai_num(h - 12)
    else:
        # 18-23 = 1-6 ทุ่ม (18:00=1ทุ่ม, 19:00=2ทุ่ม, ..., 23:00=6ทุ่ม)
        return f"{_to_thai_num(h - 17)}ทุ่ม" + (f"{_to_thai_num(m)}นาที" if m else "")
    if m == 0:
        return f"{period}{hour_word}โมง"
    elif m == 15:
        return f"{period}{hour_word}โมงสิบห้านาที"
    elif m == 30:
        return f"{period}{hour_word}โมงครึ่ง"
    elif m == 45:
        return f"{period}{hour_word}โมงสี่สิบห้านาที"
    else:
        return f"{period}{hour_word}โมง{m}นาที"


def normalize_for_tts(text):
    """Full normalization pipeline for Thai TTS — convert raw numbers/time to natural speech."""
    # Step 1: Convert time patterns HH:MM
    text = re.sub(r'(\d{1,2}):(\d{2})', _normalize_time, text)
    # Step 2: Convert standalone numbers 1-999 to Thai words
    def _replace_num(m):
        num = int(m.group(0))
        return _to_thai_num(num) if num <= 999 else m.group(0)
    text = re.sub(r'(?<!\d)(?<![:\-])(\d{1,3})(?![:\d])', _replace_num, text)
    return text


# Shop info
SHOP_NAME = "ร้านอาหารบ้านเรา"
SHOP_PHONE = "02-123-4567"
SHOP_HOURS = "เปิด 10:00-22:00 ทุกวัน"
POS_API = "http://localhost:54532"

# ── POS Menu Cache ──
_menu_cache = None
_menu_cache_time = 0

def fetch_pos_menu():
    """Fetch menu from POS API (cached 60s)."""
    global _menu_cache, _menu_cache_time
    import time
    now = time.time()
    if _menu_cache and (now - _menu_cache_time) < 60:
        return _menu_cache
    try:
        req = urllib.request.Request(f"{POS_API}/api/pos/menu")
        with urllib.request.urlopen(req, timeout=5) as resp:
            items = json.loads(resp.read())
            _menu_cache = items
            _menu_cache_time = now
            print(f"  📋 POS menu loaded: {len(items)} items")
            return items
    except Exception as e:
        print(f"  ⚠️ POS menu fetch failed: {e}")
        return _menu_cache or []

def format_menu_for_llm():
    """Format POS menu as text for LLM prompt."""
    items = fetch_pos_menu()
    if not items:
        return "(ไม่สามารถดึงเมนูได้)"
    lines = []
    for item in items:
        lines.append(f"- {item['id']}: {item['name']} ({item['category']}) ฿{item['price']}")
    return "\n".join(lines)

def match_menu_item(name, items=None):
    """Match a spoken name to POS menu item by name similarity."""
    if items is None:
        items = fetch_pos_menu()
    name_lower = name.lower().strip()
    # Exact match
    for item in items:
        if item['name'].lower() == name_lower:
            return item
    # Partial match
    for item in items:
        if name_lower in item['name'].lower() or item['name'].lower() in name_lower:
            return item
    # Thai name match (common aliases)
    thai_aliases = {
        'ผัดกะเพรา': 'Pad Kra Pao Moo',
        'ผัดไทย': 'Pad Thai Goong',
        'ต้มยำ': 'Tom Yum Soup',
        'แกงเขียวหวาน': 'Green Curry Chicken',
        'แกงมัสมั่น': 'Massaman Curry',
        'ข้าวผัด': 'Fried Rice Seafood',
        'ผัดซีอิ๊ว': 'Pad See Ew',
        'ข้าวซอย': 'Khao Soi',
        'พะแนง': 'Panang Curry',
        'ส้มตำ': 'Som Tum Thai',
        'ลาบ': 'Larb Gai',
        'ไก่สะเต๊ะ': 'Satay Chicken (4 pcs)',
        'ทอดมันกุ้ง': 'Tod Mun Goong',
        'ปอเปี๊ยะ': 'Spring Rolls',
        'มะม่วงข้าวเหนียว': 'Mango Sticky Rice',
        'โรตี': 'Thai Roti',
        'ไอศครีม': 'Ice Cream (Coconut)',
        'ชาเย็น': 'Thai Iced Tea',
        'กาแฟเย็น': 'Thai Iced Coffee',
        'น้ำมะพร้าว': 'Coconut Water',
        'น้ำมะนาว': 'Lemonade',
        'น้ำอัดลม': 'Soda',
        'น้ำเปล่า': 'Water',
        'เบียร์สิงห์': 'Singha Beer',
        'เบียร์ช้าง': 'Chang Beer',
        'สมูทตี้': 'Smoothie (Fruit)',
        'ข้าวสวย': 'Steamed Rice',
        'ข้าวเหนียว': 'Sticky Rice',
        'ไข่ดาว': 'Fried Egg',
        'ผักเพิ่ม': 'Extra Veggies',
    }
    for thai, eng in thai_aliases.items():
        if thai in name_lower:
            for item in items:
                if item['name'] == eng:
                    return item
    return None

# ── Cloudflare AI Helpers ──

def cf_stt(audio_url_or_base64, model="@cf/openai/whisper-large-v3-turbo"):
    """Speech-to-Text via Cloudflare Workers AI."""
    # Check if it's a URL or base64
    payload = {}
    if audio_url_or_base64.startswith("http"):
        payload["audio"] = {"url": audio_url_or_base64}
    else:
        payload["audio"] = {"data": audio_url_or_base64}
    
    req = urllib.request.Request(
        f"{CLOUDFLARE_AI}/{model}",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            if result.get("success"):
                return result["result"].get("text", "")
            return f"[STT error: {result.get('errors', '?')}]"
    except Exception as e:
        return f"[STT error: {e}]"

def cf_llm(prompt, system="คุณเป็นพนักงานร้านอาหาร พูดจาสุภาพ เป็นกันเอง"):
    """Text generation via Cloudflare Llama."""
    payload = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 500,
    }
    req = urllib.request.Request(
        f"{CLOUDFLARE_AI}/@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            if result.get("success"):
                resp_val = result["result"].get("response", "")
                # The LLM sometimes returns a Python dict literal as response string
                # which is fine — it's a string. But if Cloudflare returns nested dict,
                # handle that too
                if isinstance(resp_val, str):
                    return resp_val
                elif isinstance(resp_val, dict):
                    # LLM returned structured response
                    return json.dumps(resp_val, ensure_ascii=False)
                return str(resp_val)
            return f"[LLM error: {result.get('errors', '?')}]"
    except Exception as e:
        return f"[LLM error: {e}]"

def cf_tts(text, model="@cf/openai/whisper-large-v3-turbo"):
    """TTS — Cloudflare Whisper doesn't do TTS. Return text for now.
    Real TTS would use ElevenLabs, Google TTS, or OpenClaw tts tool.
    """
    # For now return the text — real TTS integration comes next
    return None

# ── Schema Engine Helpers ──

def schema_api(method, path, data=None):
    url = f"{SCHEMA_ENGINE}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_data = e.read().decode()
        try:
            return {"error": json.loads(body_data).get("error", str(e))}
        except:
            return {"error": f"HTTP {e.code}: {body_data[:200]}"}
    except Exception as e:
        return {"error": str(e)}

def lookup_customer(phone=""):
    """Find customer profile by phone number."""
    if not phone:
        return None
    result = schema_api("GET", f"/api/v1/data/customer_profile?phone={phone}")
    if result.get("success"):
        records = result.get("data", [])
        if records:
            return records[0]
    # Try search
    result = schema_api("GET", f"/api/v1/data/customer_profile?search={phone}")
    if result.get("success"):
        records = result.get("data", [])
        if records:
            return records[0]
    return None

# ── NLP Intent Parser ──

def parse_intent(transcript, customer=None):
    """Use LLM to detect intent, extract order items, queue request, etc."""
    profile_info = ""
    if customer:
        rd = customer.get("data", {})
        profile_info = f"""
ลูกค้าคนนี้: {rd.get('name', '?')}
- สั่งมาแล้ว {rd.get('total_visits', 0)} ครั้ง
- เมนูที่ชอบ: {', '.join(rd.get('favorite_items', []) or [])}
- แพ้: {', '.join(rd.get('allergens', []) or [])}
- ความชอบ: {rd.get('preferences', '-')}
"""
    
    # Fetch real POS menu for LLM
    menu_text = format_menu_for_llm()
    
    prompt = f"""คุณเป็นพนักงานร้านอาหาร วิเคราะห์บทสนทนาของลูกค้า

{profile_info}
ร้านอยู่ที่ตำแหน่ง GPS: 13.7563, 100.5018 (Bangkok)

เมนูร้านนี้ (ใช้ชื่อเมนูและ ID นี้เท่านั้น):
{menu_text}

ลูกค้าพูดว่า: "{transcript}"

วิเคราะห์และตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่น:
{{
  "intent": "order" หรือ "queue" หรือ "inquiry" หรือ "complaint" หรือ "faq" หรือ "other",
  "order_items": [{{"id": "ITEM_ID", "name": "ชื่อเมนูภาษาอังกฤษ", "name_th": "ชื่อเมนูภาษาไทย", "qty": จำนวน, "price": ราคา}}],
  "queue_request": "check_in" หรือ "pre_order" หรือ "status" หรือ "cancel" หรือ "",
  "faq_topic": "hours" หรือ "menu" หรือ "price" หรือ "location" หรือ "contact" หรือ "other" หรือ "",
  "customer_mood": "happy" หรือ "normal" หรือ "frustrated" หรือ "urgent",
  "summary": "สรุปสั้นๆ ว่าลูกค้าต้องการอะไร"
}}"""

    response = cf_llm(prompt, system="คุณคือ AI พนักงานร้านอาหารตอบเป็น JSON เท่านั้น")
    
    # Extract JSON/dict from response — LLM may return Python dict (single quotes) or JSON (double quotes)
    import ast
    try:
        dict_match = re.search(r'\{.*\}', response, re.DOTALL)
        if dict_match:
            raw = dict_match.group()
            print(f"    📦 Raw dict extract: {raw[:300]}")
            # Try ast.literal_eval for Python dict format first
            try:
                intent = ast.literal_eval(raw)
                if isinstance(intent, dict):
                    return intent
            except Exception as e:
                print(f"    ⚠️ ast parse failed: {e}")
            # Try json.loads
            try:
                intent = json.loads(raw)
                if isinstance(intent, dict):
                    return intent
            except Exception as e:
                print(f"    ⚠️ json parse failed: {e}")
            # Try replacing single quotes with double quotes
            try:
                fixed = raw.replace("'", '"')
                intent = json.loads(fixed)
                if isinstance(intent, dict):
                    return intent
            except Exception as e:
                print(f"    ⚠️ quote fix failed: {e}")
    except Exception as e:
        print(f"    ⚠️ dict_match failed: {e}")
    
    print(f"    ⚠️ Could not parse LLM response: {response[:300]}")
    # Fallback
    return {
        "intent": "other",
        "order_items": [],
        "queue_request": "",
        "faq_topic": "",
        "customer_mood": "normal",
        "summary": transcript,
    }

def generate_response(intent, customer=None):
    """Generate a natural Thai response based on intent + customer data."""
    profile_str = ""
    if customer:
        rd = customer.get("data", {})
        name = rd.get("name", "")
        fav_items = rd.get("favorite_items", [])
        if name:
            profile_str = f"- ลูกค้าชื่อ: {name}\n"
            if fav_items:
                profile_str += f"- เมนูที่ชอบ: {', '.join(fav_items)}\n"
    
    menu_text = format_menu_for_llm()
    
    prompt = f"""คุณเป็นพนักงานร้าน{SHOP_NAME} พูดจาสุภาพ เป็นกันเอง ใช้ภาษาไทยธรรมชาติ

{profile_str}
ร้านเปิด {SHOP_HOURS}
เบอร์โทร: {SHOP_PHONE}

เมนูร้านนี้:
{menu_text}

จาก intent ที่วิเคราะห์ได้:
intent: {intent.get('intent', 'other')}
order_items: {json.dumps(intent.get('order_items', []), ensure_ascii=False)}
queue_request: {intent.get('queue_request', '')}
faq_topic: {intent.get('faq_topic', '')}
customer_mood: {intent.get('customer_mood', 'normal')}
summary: {intent.get('summary', '')}

ตอบเป็นข้อความสั้นๆ ที่จะเอาไปพูดกับลูกค้าทางโทรศัพท์ (ความยาวไม่เกิน 3-4 ประโยค)
ห้ามใส่เครื่องหมายคำพูด ห้ามใส่ emoji ที่เสียงอ่านไม่ออก ให้ใช้คำพูดธรรมชาติ
ห้ามบอกตัวเลขราคา ให้บอกชื่อเมนูและจำนวนเท่านั้น"""

    return cf_llm(prompt, system=f"คุณคือพนักงานร้าน{SHOP_NAME} ตอบสั้น กระชับ เป็นธรรมชาติ")

# ── Voice Session Logger ──

def log_session(caller_phone, transcript, intent, response_text, action_taken):
    """Log voice session to Schema Engine voice_session schema (dynamic)."""
    session = {
        "customer_name": intent.get("customer_name", ""),
        "phone": caller_phone,
        "transcript": transcript,
        "intent": intent.get("intent", "other"),
        "summary": intent.get("summary", ""),
        "mood": intent.get("customer_mood", "normal"),
        "response_summary": response_text[:200] if response_text else "",
        "action_taken": action_taken,
        "duration_seconds": 0,
    }
    
    # Try to save — schema might not exist yet, create it dynamically
    result = schema_api("POST", "/api/v1/data/voice_session", session)
    if result.get("error") and "not found" in str(result.get("error", "")).lower():
        # Create the schema first
        create_voice_session_schema()
        result = schema_api("POST", "/api/v1/data/voice_session", session)
    
    return result.get("success", False)

def create_voice_session_schema():
    """Create voice_session schema if it doesn't exist."""
    schema = {
        "name": "Voice Session",
        "slug": "voice_session",
        "description": "Voice ordering sessions — transcript, intent, response, actions",
        "config": {"icon": "🎤", "color": "#8B5CF6", "enableSearch": True, "searchFields": ["customer_name", "phone"]},
        "fields": [
            {"name": "customer_name", "type": "string", "label": "ชื่อลูกค้า"},
            {"name": "phone", "type": "string", "label": "เบอร์โทร"},
            {"name": "transcript", "type": "text", "label": "ข้อความที่ลูกค้าพูด"},
            {"name": "intent", "type": "string", "label": "Intent ที่ตรวจจับได้"},
            {"name": "summary", "type": "text", "label": "สรุปความต้องการ"},
            {"name": "mood", "type": "string", "label": "อารมณ์ลูกค้า"},
            {"name": "response_summary", "type": "text", "label": "สิ่งที่ Agent ตอบ"},
            {"name": "action_taken", "type": "text", "label": "Action ที่ดำเนินการ"},
            {"name": "duration_seconds", "type": "number", "label": "ระยะเวลาสนทนา (วินาที)"},
        ],
    }
    return schema_api("POST", "/api/v1/schema", schema)

# ── Action Engine ──

def execute_action(intent, caller_phone="", customer=None):
    """Execute the detected intent: create order, queue check-in, etc."""
    action_log = []
    
    # Determine customer name: from profile > intent summary > default
    customer_name = ""
    if customer:
        customer_name = customer.get("data", {}).get("name", "")
    if not customer_name and intent.get("customer_name"):
        customer_name = intent["customer_name"]
    if not customer_name:
        # Try to extract from transcript summary if it starts with a name pattern
        summary = intent.get("summary", "")
        if summary:
            customer_name = "Voice Customer"
        else:
            customer_name = "Voice Customer"
    
    if intent.get("intent") == "order" and intent.get("order_items"):
        # Create order via queue pre-order service
        try:
            order_payload = {
                "customer_name": customer_name,
                "phone": caller_phone,
                "items": intent["order_items"],
                "party_size": 1,
                "latitude": 13.7563,
                "longitude": 100.5018,
                "source": "voice",
            }
            req = urllib.request.Request(
                f"{QUEUE_SERVICE}/queue/pre-order",
                data=json.dumps(order_payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                action_log.append(f"สร้างออเดอร์: ticket={result.get('ticket', '?')}")
        except Exception as e:
            action_log.append(f"สร้างออเดอร์ล้มเหลว: {e}")
    
    elif intent.get("queue_request") == "check_in":
        try:
            checkin_payload = {
                "customer_name": customer_name,
                "phone": caller_phone,
                "party_size": intent.get("order_items", [{}])[0].get("qty", 2) if intent.get("order_items") else 2,
                "source": "voice",
            }
            req = urllib.request.Request(
                f"{QUEUE_SERVICE}/queue/check-in",
                data=json.dumps(checkin_payload).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                action_log.append(f"เช็คอินคิว: ticket={result.get('ticket', '?')}, รอประมาณ {result.get('estimated_wait_minutes', '?')} นาที")
        except Exception as e:
            action_log.append(f"เช็คอินล้มเหลว: {e}")
    
    elif intent.get("intent") == "faq":
        action_log.append("ตอบคำถามลูกค้า")
    
    return "; ".join(action_log) if action_log else "ไม่มี action"

# ── HTTP Server ──

class VoiceGatewayHandler(BaseHTTPRequestHandler):
    
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
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
        
        if path == "/health":
            self._send_json({
                "status": "ok",
                "service": "voice-gateway",
                "version": "1.0",
                "shop": SHOP_NAME,
                "stt_model": "whisper-large-v3-turbo",
                "llm_model": "llama-3.3-70b-instruct",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        
        elif path == "/voice/sessions":
            result = schema_api("GET", "/api/v1/data/voice_session?limit=20")
            sessions = []
            if result.get("success"):
                for rec in result.get("data", []):
                    rd = rec.get("data", {})
                    sessions.append({
                        "id": rec["id"],
                        "customer": rd.get("customer_name", "?"),
                        "phone": rd.get("phone"),
                        "intent": rd.get("intent"),
                        "summary": rd.get("summary", "")[:100],
                        "time": rec.get("created_at", ""),
                    })
            self._send_json({"sessions": sessions, "count": len(sessions)})
        
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
        
        if path == "/voice/incoming":
            audio_url = body.get("audio_url", "")
            audio_base64 = body.get("audio_data", "")
            caller_phone = body.get("caller_phone", "")
            
            if not audio_url and not audio_base64:
                self._send_json({"error": "audio_url or audio_data required"}, 400)
                return
            
            # Step 1: STT
            print(f"  🎤 STT: processing audio...")
            transcript = cf_stt(audio_url or audio_base64)
            print(f"  📝 Transcript: {transcript[:200]}")
            
            # Step 2: Customer lookup
            customer = lookup_customer(caller_phone)
            if customer:
                rd = customer.get("data", {})
                print(f"  👤 Customer found: {rd.get('name', '?')} ({rd.get('tier', '?')})")
            
            # Step 3: NLP Intent
            print(f"  🧠 NLP: parsing intent...")
            intent = parse_intent(transcript, customer)
            if customer:
                intent["customer_name"] = customer.get("data", {}).get("name", "")
            else:
                intent["customer_name"] = ""
            print(f"  🎯 Intent: {intent.get('intent')} | {intent.get('summary', '')[:100]}")
            
            # Step 4: Execute action
            action_taken = execute_action(intent, caller_phone, customer)
            print(f"  ⚡ Action: {action_taken}")
            
            # Step 5: Generate response
            response_text = generate_response(intent, customer)
            print(f"  💬 Response: {response_text[:200]}")
            
            # Step 6: Log session
            logged = log_session(caller_phone, transcript, intent, response_text, action_taken)
            
            self._send_json({
                "success": True,
                "transcript": transcript,
                "intent": intent,
                "action_taken": action_taken,
                "response_text": response_text,
                "customer_found": bool(customer),
                "session_logged": logged,
            })
        
        elif path == "/voice/text/message" or path == "/api/voice/process":
            text = body.get("message", "") or body.get("text", "")
            caller_phone = body.get("caller_phone", "")
            
            if not text:
                self._send_json({"error": "message or text required"}, 400)
                return
            
            print(f"  📝 Text: {text[:200]}")
            
            customer = lookup_customer(caller_phone)
            if customer:
                print(f"  👤 Customer: {customer.get('data', {}).get('name', '?')}")
            
            intent = parse_intent(text, customer)
            if customer:
                intent["customer_name"] = customer.get("data", {}).get("name", "")
            print(f"  🎯 Intent: {intent.get('intent')} | {intent.get('summary', '')[:100]}")
            
            # DON'T execute action yet — frontend shows popup for user confirmation
            response_text = generate_response(intent, customer)
            
            logged = log_session(caller_phone, text, intent, response_text, "pending_confirmation")
            
            # Format for frontend compatibility
            action = intent.get('intent', 'unknown')
            items = []
            if intent.get('intent') == 'order' and intent.get('order_items'):
                action = 'identify'
                for oi in intent['order_items']:
                    menu_name = oi.get('name', '')
                    menu_price = oi.get('price', 0)
                    items.append({
                        'nameTh': menu_name,
                        'name': menu_name,
                        'quantity': oi.get('qty', 1),
                        'price': menu_price,
                    })
            elif intent.get('intent') == 'queue':
                action = 'queue'
            elif intent.get('intent') == 'faq':
                action = 'info'
            
            self._send_json({
                "success": True,
                "reply": response_text,
                "action": action,
                "items": items,
                "transcript": text,
                "intent": intent,
                "customer_found": bool(customer),
                "session_logged": logged,
            })
        
        elif path == "/voice/preview":
            """Preview: see what agent knows about a customer."""
            phone = body.get("caller_phone", "")
            name = body.get("customer_name", "")
            
            customer = lookup_customer(phone)
            if not customer and name:
                result = schema_api("GET", f"/api/v1/data/customer_profile?search={name}")
                if result.get("success") and result.get("data"):
                    customer = result["data"][0]
            
            if not customer:
                self._send_json({"customer_found": False, "message": "ไม่พบข้อมูลลูกค้าในระบบ"})
                return
            
            rd = customer.get("data", {})
            
            # Generate personalized greeting
            prompt = f"""ลูกค้าชื่อ {rd.get('name', '?')}
- มาครั้งที่ {rd.get('total_visits', 0)} 
- สั่งรวม ฿{rd.get('lifetime_value', 0):,}
- เมนูที่ชอบ: {', '.join(rd.get('favorite_items', []) or [])}
- แพ้: {', '.join(rd.get('allergens', []) or [])}
- ความชอบ: {rd.get('preferences', '-')}
- ระดับ: {rd.get('tier', 'new')}
- ออเดอร์ล่าสุด: {rd.get('last_order_summary', '-')[:150]}

สร้างข้อความทักทายที่จะใช้ตอนลูกค้าโทรมา ให้รู้สึกว่ารู้จักลูกค้า (ภาษาไทย เป็นกันเอง สั้นๆ 2-3 ประโยค)"""

            greeting = cf_llm(prompt, "คุณเป็นพนักงานร้านอาหารที่จำลูกค้าได้ทุกคน")
            
            self._send_json({
                "customer_found": True,
                "profile": rd,
                "personalized_greeting": greeting,
            })
        
        elif path == "/voice/tts":
            # Generate TTS audio via Edge TTS
            text = body.get("text", "")
            voice = body.get("voice", "th-TH-PremwadeeNeural")
            if not text:
                self._send_json({"error": "text required"}, 400)
                return
            
            # Normalize for TTS: convert time/numbers to natural Thai speech
            text = normalize_for_tts(text)
            # Clean text for TTS
            # Keep Thai, English, digits, spaces, basic punctuation
            # Keep Thai, English, digits, spaces, basic punctuation
            clean_text = re.sub('[^\u0e00-\u0e7fa-zA-Z0-9 \t.,!?-]', ' ', text)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            
            if not clean_text or len(clean_text) < 2:
                self._send_json({"error": "text too short"}, 400)
                return
            
            print(f"  🔊 TTS: {clean_text[:80]}...")
            
            try:
                # Generate audio with edge-tts
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
                    tmp_path = tmp.name
                
                cmd = [
                    'edge-tts',
                    '--voice', voice,
                    '--text', clean_text,
                    '--write-media', tmp_path
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                
                if result.returncode != 0:
                    print(f"  ❌ TTS error: {result.stderr[:200]}")
                    self._send_json({"error": f"TTS failed: {result.stderr[:200]}"}, 500)
                    return
                
                # Read and encode as base64
                with open(tmp_path, 'rb') as f:
                    audio_data = f.read()
                
                audio_b64 = base64.b64encode(audio_data).decode('utf-8')
                
                # Cleanup
                os.unlink(tmp_path)
                
                print(f"  ✅ TTS: {len(audio_data)} bytes")
                self._send_json({
                    "success": True,
                    "audio": audio_b64,
                    "format": "mp3",
                    "voice": voice,
                    "text": clean_text,
                })
            except subprocess.TimeoutExpired:
                self._send_json({"error": "TTS timeout"}, 500)
            except Exception as e:
                print(f"  ❌ TTS error: {e}")
                self._send_json({"error": str(e)}, 500)
        
        elif path == "/voice/respond":
            text = body.get("text", "")
            if not text:
                self._send_json({"error": "text required"}, 400)
                return
            
            self._send_json({
                "text": text,
                "tts_note": "TTS output — ใช้ OpenClaw tts tool หรือ ElevenLAS API แทน",
            })
        
        elif path == "/api/order/create":
            items = body.get("items", [])
            customer_name = body.get("customerName", "Voice Customer")
            table_id = body.get("tableId", "T01")
            
            if not items:
                self._send_json({"success": False, "error": "No items provided"}, 400)
                return
            
            print(f"  🍳 Creating order: {len(items)} items from {customer_name}")
            
            # Match items to POS menu IDs
            pos_items = []
            for item in items:
                menu_item = match_menu_item(item.get("name", ""))
                if menu_item:
                    pos_items.append({
                        "item_id": menu_item["id"],
                        "quantity": item.get("quantity", 1),
                        "notes": item.get("notes", ""),
                    })
                else:
                    # Fallback: use name as-is
                    pos_items.append({
                        "item_id": item.get("id", "MISC"),
                        "quantity": item.get("quantity", 1),
                        "notes": item.get("name", ""),
                    })
            
            try:
                # Create order via POS API
                order_payload = {
                    "table_id": table_id,
                    "items": pos_items,
                    "notes": f"Voice order from {customer_name}",
                }
                req = urllib.request.Request(
                    f"{POS_API}/api/pos/orders",
                    data=json.dumps(order_payload).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read())
                    order_id = result.get("order_id", "?")
                    total = result.get("total", 0)
                    print(f"  ✅ POS Order created: {order_id}, total={total}")
                    self._send_json({
                        "success": True,
                        "orderId": order_id,
                        "total": total,
                        "items": result.get("items", items),
                    })
            except Exception as e:
                print(f"  ❌ Order creation failed: {e}")
                self._send_json({"success": False, "error": str(e)}, 500)
        
        else:
            self._send_json({"error": "not found"}, 404)
    
    def log_message(self, format, *args):
        try:
            print(f"  🌐 {args[0]} {args[1]} {args[2]}")
        except (IndexError, KeyError):
            print(f"  🌐 {format % args if args else format}")

def main():
    print("=" * 55)
    print("  🎤 Voice Ordering Gateway v1")
    print(f"  ⏰ {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"  🏪 {SHOP_NAME}")
    print(f"  🔌 http://{HOST}:{PORT}")
    print("=" * 55)
    print("  Endpoints:")
    print("    POST /voice/incoming  — Audio → STT → NLP → Action")
    print("    POST /voice/text/message — Direct text input")
    print("    POST /voice/preview   — Customer greeting preview")
    print("    POST /voice/respond   — TTS text output")
    print("    GET  /voice/sessions  — Recent sessions")
    print("    GET  /health          — Health check")
    print("=" * 55)
    
    # Ensure voice_session schema exists on startup
    print("  📦 Ensuring voice_session schema...")
    create_voice_session_schema()
    
    server = HTTPServer((HOST, PORT), VoiceGatewayHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  👋 Shutting down...")
        server.server_close()

if __name__ == "__main__":
    main()
