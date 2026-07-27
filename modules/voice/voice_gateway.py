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

# Shop info
SHOP_NAME = "ร้านอาหารบ้านเรา"
SHOP_PHONE = "02-123-4567"
SHOP_HOURS = "เปิด 10:00-22:00 ทุกวัน"

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
    
    prompt = f"""คุณเป็นพนักงานร้านอาหาร วิเคราะห์บทสนทนาของลูกค้า

{profile_info}
ร้านอยู่ที่ตำแหน่ง GPS: 13.7563, 100.5018 (Bangkok)

ลูกค้าพูดว่า: "{transcript}"

วิเคราะห์และตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่น:
{{
  "intent": "order" หรือ "queue" หรือ "inquiry" หรือ "complaint" หรือ "faq" หรือ "other",
  "order_items": [{{"name": "ชื่อเมนู", "qty": จำนวน}}],
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
    
    prompt = f"""คุณเป็นพนักงานร้าน{SHOP_NAME} พูดจาสุภาพ เป็นกันเอง ใช้ภาษาไทยธรรมชาติ

{profile_str}
ร้านเปิด {SHOP_HOURS}
เบอร์โทร: {SHOP_PHONE}

จาก intent ที่วิเคราะห์ได้:
intent: {intent.get('intent', 'other')}
order_items: {json.dumps(intent.get('order_items', []), ensure_ascii=False)}
queue_request: {intent.get('queue_request', '')}
faq_topic: {intent.get('faq_topic', '')}
customer_mood: {intent.get('customer_mood', 'normal')}
summary: {intent.get('summary', '')}

ตอบเป็นข้อความสั้นๆ ที่จะเอาไปพูดกับลูกค้าทางโทรศัพท์ (ความยาวไม่เกิน 3-4 ประโยค)
ห้ามใส่เครื่องหมายคำพูด ห้ามใส่ emoji ที่เสียงอ่านไม่ออก ให้ใช้คำพูดธรรมชาติ"""

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
        
        elif path == "/voice/text/message":
            text = body.get("message", "")
            caller_phone = body.get("caller_phone", "")
            
            if not text:
                self._send_json({"error": "message required"}, 400)
                return
            
            print(f"  📝 Text: {text[:200]}")
            
            customer = lookup_customer(caller_phone)
            if customer:
                print(f"  👤 Customer: {customer.get('data', {}).get('name', '?')}")
            
            intent = parse_intent(text, customer)
            if customer:
                intent["customer_name"] = customer.get("data", {}).get("name", "")
            print(f"  🎯 Intent: {intent.get('intent')} | {intent.get('summary', '')[:100]}")
            
            action_taken = execute_action(intent, caller_phone, customer)
            response_text = generate_response(intent, customer)
            
            logged = log_session(caller_phone, text, intent, response_text, action_taken)
            
            self._send_json({
                "success": True,
                "transcript": text,
                "intent": intent,
                "action_taken": action_taken,
                "response_text": response_text,
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
        
        elif path == "/voice/respond":
            text = body.get("text", "")
            if not text:
                self._send_json({"error": "text required"}, 400)
                return
            
            self._send_json({
                "text": text,
                "tts_note": "TTS output — ใช้ OpenClaw tts tool หรือ ElevenLAS API แทน",
            })
        
        else:
            self._send_json({"error": "not found"}, 404)
    
    def log_message(self, format, *args):
        print(f"  🌐 {args[0]} {args[1]} {args[2]}")

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
