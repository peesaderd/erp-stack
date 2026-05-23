"""Brain Server v6.3 — Inner Monologue Agent + Memory + Self-Reflection + Resilience

Integrates InnerMonologueAgent (v6.2) with:
- ChatVoipClient for messaging
- PulseDetector for system health monitoring
- EscalationEngine for alert routing
- Webhook HTTP server for API access
- SystemBot for system administration
- BookStackClient for knowledge base access
- ConversationMemory for cross-session context
- SelfReflection for learning from interactions
- Resilience (Retry, Fallback, CircuitBreaker) for robustness
- Delegation (SubAgentManager) for complex tasks
"""

import json, logging, os, sys, time, uuid, threading
from datetime import datetime, timezone
from typing import Any, Optional
from collections import deque
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

from system_bot import SystemBot
from bookstack_client import BookStackClient
from inner_monologue.agent import InnerMonologueAgent
from inner_monologue.memory import ConversationMemory
from inner_monologue.heartbeat import Heartbeat
from inner_monologue.self_reflection import SelfReflection
from inner_monologue.hitl import HITL
from inner_monologue.resilience import RetryStrategy, FallbackProvider, CircuitBreaker
from inner_monologue.delegation import SubAgentManager
from inner_monologue.scanner import AutoDiscoveryEngine, ServiceScanner, ServiceClassifier

# Configuration
CHATVOIP_BASE = os.getenv("CHATVOIP_BASE", "http://localhost:3001")
CHATVOIP_BOT_TOKEN = os.getenv("CHATVOIP_BOT_TOKEN", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6ImNtcGdzeGh0NTAwMDBrandoNml4ZTBodWYiLCJpYXQiOjE3Nzk0NDcyMTksImV4cCI6MTc4MDA1MjAxOX0.fN0t0j21H7C9oJ23x2nLJfPQzRb99q1_Gukzc0p3V8E")
CHATVOIP_ROOM = os.getenv("CHATVOIP_ROOM", "cmpgt08e10000bk2isvaf47ge")
BOOKSTACK_URL = os.getenv("BOOKSTACK_URL", "http://89.167.82.205:54515")
BOOKSTACK_TOKEN_ID = os.getenv("BOOKSTACK_TOKEN_ID", "SQzJHJKFY2YvncKVEy4GKMsbLiJJ8JoW")
BOOKSTACK_TOKEN_SECRET = os.getenv("BOOKSTACK_TOKEN_SECRET", "J3WJC2aEfs5R2sSAcLX6ck4uocJx4ACo")
BRAIN_NAME = os.getenv("BRAIN_NAME", "Brain Server v6.3")
LOG_FILE = os.getenv("LOG_FILE", "/home/openhands/brain-server/brain.log")
STATE_FILE = os.getenv("STATE_FILE", "/home/openhands/brain-server/state.json")
PORT = int(os.getenv("PORT", "8101"))

CONDENSE_AFTER_THOUGHTS = 30
MAX_RECENT_THOUGHTS = 10
IDLE_HEARTBEAT_INTERVAL = 300  # 5 นาที — แทน 30 วินาที
PULSE_INTERVAL = 10
DISK_CRITICAL = 95
DISK_HIGH = 90
MEMORY_HIGH = 85
ESCALATE_WAIT_SECONDS = 300

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("brain")


class ChatVoipClient:
    """Send messages to chat-voip API."""

    def __init__(self, base_url: str, bot_token: str, room_id: str):
        self.base_url = base_url.rstrip("/")
        self.bot_token = bot_token
        self.room_id = room_id
        self._available = True
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": "Bearer " + bot_token,
            "Content-Type": "application/json",
        })
        try:
            resp = self._session.get(self.base_url + "/api/health", timeout=3)
            resp.raise_for_status()
        except requests.RequestException:
            try:
                resp = self._session.get(self.base_url, timeout=3)
                resp.raise_for_status()
            except requests.RequestException:
                log.warning("Chat-VoIP server not reachable at %s", base_url)
                self._available = False

    def send_message(self, text: str) -> bool:
        if not self._available:
            return False
        url = "{}/api/messages/{}".format(self.base_url, self.room_id)
        try:
            resp = self._session.post(url, json={"content": text}, timeout=10)
            resp.raise_for_status()
            log.info("Chat-VoIP message sent: %s", text[:80])
            return True
        except requests.RequestException as e:
            if hasattr(e, 'response') and e.response is not None and e.response.status_code in (404, 405):
                self._available = False
            else:
                log.warning("Chat-VoIP send failed: %s", e)
            return False

    def send_notice(self, text: str) -> bool:
        return self.send_message("\U0001f9e0 **" + BRAIN_NAME + "** \u2014 " + text)


class PulseDetector(threading.Thread):
    """Daemon thread for system health monitoring."""

    def __init__(self, system: SystemBot, chat: ChatVoipClient, interval: int = PULSE_INTERVAL):
        super().__init__(daemon=True)
        self.system = system
        self.chat = chat
        self.interval = interval
        self._running = False
        self._event_queue: deque = deque()
        self._last_events: dict[str, float] = {}
        self._event_cooldown = 300

    CHECKS = [
        ("disk_critical", "CRITICAL",
         lambda s: s.get("disk_pct", 0) > DISK_CRITICAL,
         "Disk usage > {}%".format(DISK_CRITICAL)),
        ("disk_high", "HIGH",
         lambda s: s.get("disk_pct", 0) > DISK_HIGH,
         "Disk usage > {}%".format(DISK_HIGH)),
        ("service_down", "CRITICAL",
         lambda s: "inactive" in s.get("erp_service", "") or "failed" in s.get("erp_service", ""),
         "ERP service is down"),
        ("memory_high", "MEDIUM",
         lambda s: s.get("mem_pct", 0) > MEMORY_HIGH,
         "Memory usage > {}%".format(MEMORY_HIGH)),
    ]

    def run(self):
        self._running = True
        log.info("[PULSE] PulseDetector started (interval=%ds)", self.interval)
        while self._running:
            try:
                snapshot = self._take_snapshot()
                for name, severity, check, desc in self.CHECKS:
                    if check(snapshot):
                        self._queue_event(name, severity, desc, snapshot)
                time.sleep(self.interval)
            except Exception as e:
                log.error("[PULSE] Error: %s", e)
                time.sleep(5)

    def _take_snapshot(self) -> dict:
        disk = self.system.check_disk()
        mem = self.system.check_memory()
        svc = self.system.check_service("brain-server")
        return {
            "disk_pct": disk.get("usage_percent", 0) if isinstance(disk, dict) else 0,
            "disk_free_gb": disk.get("free_gb", 0) if isinstance(disk, dict) else 0,
            "mem_pct": mem.get("percent", 0) if isinstance(mem, dict) else 0,
            "mem_free_mb": mem.get("available_mb", 0) if isinstance(mem, dict) else 0,
            "erp_service": svc.get("status", "unknown") if isinstance(svc, dict) else "unknown",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _queue_event(self, name: str, severity: str, desc: str, snapshot: dict):
        now = time.time()
        last = self._last_events.get(name, 0)
        if now - last < self._event_cooldown:
            return
        self._last_events[name] = now
        event = {
            "name": name, "severity": severity, "description": desc,
            "snapshot": {k: v for k, v in snapshot.items()},
            "timestamp": snapshot["timestamp"],
        }
        self._event_queue.append(event)
        log.info("[PULSE] Event queued: [%s] %s \u2014 %s", severity, name, desc)

    def get_event(self) -> Optional[dict]:
        if not self._event_queue:
            return None
        return self._event_queue.popleft()

    def has_events(self) -> bool:
        return len(self._event_queue) > 0

    def stop(self):
        self._running = False


class EscalationEngine:
    """Routes events based on severity."""

    def __init__(self, chat: ChatVoipClient):
        self.chat = chat
        self._pending_high: list[dict] = []
        self._digest_log: list[str] = []

    def process(self, event: dict, force_interrupt_callback=None):
        severity = event.get("severity", "LOW")
        name = event.get("name", "unknown")
        desc = event.get("description", "")
        ts = event.get("timestamp", "")

        if severity == "CRITICAL":
            self._handle_critical(name, desc, ts, force_interrupt_callback)
        elif severity == "HIGH":
            self._handle_high(name, desc, ts)
        elif severity == "MEDIUM":
            self._handle_medium(name, desc, ts)
        else:
            self._handle_low(name, desc, ts)

    def _handle_critical(self, name: str, desc: str, ts: str, interrupt_cb):
        msg = "\U0001f534 **CRITICAL** [{}] {} \u2014 {}".format(ts[-8:], name, desc)
        self.chat.send_message(msg)
        if interrupt_cb:
            interrupt_cb(name, desc)

    def _handle_high(self, name: str, desc: str, ts: str):
        msg = "\U0001f7e0 **HIGH** [{}] {} \u2014 {}".format(ts[-8:], name, desc)
        self.chat.send_message(msg)
        self._pending_high.append({"name": name, "description": desc, "timestamp": ts, "alert_time": time.time()})

    def _handle_medium(self, name: str, desc: str, ts: str):
        msg = "\U0001f7e1 **MEDIUM** [{}] {} \u2014 {}".format(ts[-8:], name, desc)
        self.chat.send_message(msg)

    def _handle_low(self, name: str, desc: str, ts: str):
        self._digest_log.append("- [{}] {}: {}".format(ts[-8:], name, desc))

    def check_escalations(self) -> list[dict]:
        now = time.time()
        escalated = []
        still_pending = []
        for event in self._pending_high:
            if now - event["alert_time"] >= ESCALATE_WAIT_SECONDS:
                escalated.append(event)
            else:
                still_pending.append(event)
        self._pending_high = still_pending
        return escalated

    def get_digest(self) -> str:
        if not self._digest_log:
            return ""
        digest = "Daily Digest:\n" + "\n".join(self._digest_log)
        self._digest_log.clear()
        return digest


class BrainServerV6:
    """Brain Server v6.3 — Inner Monologue Agent + Memory + Self-Reflection + Resilience"""

    def __init__(self):
        self.chat = ChatVoipClient(CHATVOIP_BASE, CHATVOIP_BOT_TOKEN, CHATVOIP_ROOM)
        self.system = SystemBot()
        self.bookstack = BookStackClient(BOOKSTACK_URL, BOOKSTACK_TOKEN_ID, BOOKSTACK_TOKEN_SECRET)
        self.pulse = PulseDetector(self.system, self.chat)
        self.escalation = EscalationEngine(self.chat)

        # Persistent memory for cross-session context
        self.memory = ConversationMemory(persistence_dir="/home/openhands/brain-server/.inner-memory")
        self.memory.load()

        # Self-Reflection system — learns from user interactions
        self.self_reflection = SelfReflection(persistence_dir="/home/openhands/brain-server/.inner-memory")
        self.self_reflection.set_llm_fn(self._call_llm_for_reflection)

        # Heartbeat for real-time status display
        self.heartbeat = Heartbeat(verbose=True)

        # HITL for destructive action confirmation
        self.hitl = HITL(workspace="/home/openhands/brain-server")

        # Resilience components
        self.retry = RetryStrategy(max_retries=3, base_delay=1.0, max_delay=30.0)
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60.0)

        # Delegation system
        self.delegation = SubAgentManager(
            llm_call_fn=self._call_llm_for_delegation,
            workspace="/home/openhands/brain-server",
        )

        # Auto-Discovery Engine — สแกนและวิเคราะห์ services ในระบบ
        self.discovery = AutoDiscoveryEngine(llm_call_fn=self._call_llm_for_discovery)
        self._discovery_results: Optional[dict] = None
        self._pending_questions: list[dict] = []  # รอถามผู้ใช้

        # Inner Monologue Agent — uses all components above
        self.agent = InnerMonologueAgent(
            llm_config={
                "api_key": os.getenv("LLM_API_KEY", ""),
                "model": "deepseek/deepseek-chat",
            },
            memory=self.memory,
            heartbeat=self.heartbeat,
            self_reflection=self.self_reflection,
            hitl=self.hitl,
            workspace="/home/openhands/brain-server",
        )

        self._running = False
        self._background_thread: Optional[threading.Thread] = None
        self._thought_log: list[dict] = []
        self._action_log: list[dict] = []
        self._session_start = datetime.now(timezone.utc).isoformat()
        self._total_thoughts = 0
        self._total_actions = 0
        self._last_idle_beat = 0.0

    def _call_llm_for_reflection(self, prompt: str) -> str:
        """Wrapper for Self-Reflection to call LLM"""
        return self.agent._call_llm_for_condense(prompt)

    def _call_llm_for_delegation(self, prompt: str) -> str:
        """Wrapper for Delegation to call LLM"""
        return self.agent._call_llm_for_condense(prompt)

    def _call_llm_for_discovery(self, prompt: str) -> str:
        """Wrapper for Auto-Discovery to call LLM"""
        return self.agent._call_llm_for_condense(prompt)

    def run_discovery(self) -> dict:
        """รัน Auto-Discovery — สแกนระบบและวิเคราะห์ services"""
        self._think("Starting Auto-Discovery of ERP Stack...", "plan")
        self.chat.send_notice("\U0001f50d **Auto-Discovery** เริ่มสแกนระบบ...")

        try:
            # 1. สแกนและวิเคราะห์
            summary = self.discovery.run_discovery()
            self._discovery_results = summary

            # 2. บันทึกผล
            self._think(f"Discovery complete: {summary['modules_found']} modules, {summary['uncertain']} uncertain", "observation")

            # 3. ถ้ามี services ที่ไม่แน่ใจ — ถามผู้ใช้
            uncertain = summary.get("uncertain_services", [])
            if uncertain:
                self._pending_questions = uncertain
                msg = "\u2753 **Auto-Discovery** พบ services ที่ไม่แน่ใจ:\n"
                for svc in uncertain:
                    msg += f"- {svc['name']} (port {svc['port']}) — {svc.get('reason', 'ไม่ทราบ')}\n"
                msg += "\nกรุณาตอบว่าใช่ ERP Module หรือไม่? (ใช่/ไม่ใช่)"
                self.chat.send_message(msg)
                self._think(f"Asked user about {len(uncertain)} uncertain services", "question")

            # 4. สรุปผล
            modules = summary.get("modules", [])
            if modules:
                mod_list = "\n".join([f"  - {m['name']} ({m.get('category', 'unknown')})" for m in modules])
                self.chat.send_message(f"\u2705 **Auto-Discovery** พบ ERP Modules ทั้งหมด {len(modules)} ตัว:\n{mod_list}")

            self.memory.add_entry("discovery", json.dumps(summary, indent=2))
            self.memory.save()
            return summary

        except Exception as e:
            error_msg = f"Auto-Discovery ล้มเหลว: {e}"
            self._think(error_msg, "error")
            self.chat.send_notice(f"\u274c {error_msg}")
            return {"error": error_msg}

    def answer_discovery_question(self, service_name: str, is_module: bool) -> str:
        """รับคำตอบจากผู้ใช้เกี่ยวกับ service ที่ไม่แน่ใจ"""
        self.discovery.classifier.record_feedback(service_name, is_module)
        # ลบออกจาก pending
        self._pending_questions = [q for q in self._pending_questions if q["name"] != service_name]
        status = "Module" if is_module else "ไม่ใช่ Module"
        self.chat.send_message(f"\u2705 **Auto-Discovery** บันทึก: {service_name} → {status}")
        self._think(f"User confirmed: {service_name} is_module={is_module}", "learning")
        self.memory.add_entry("discovery_feedback", f"{service_name}: {status}")
        self.memory.save()
        return f"บันทึก: {service_name} → {status}"

    def start(self):
        self._running = True
        self.pulse.start()
        self._background_thread = threading.Thread(target=self._background_loop, daemon=True)
        self._background_thread.start()
        self.chat.send_notice("\U0001f7e2 **Online** \u2014 v6.3 started")
        log.info("=" * 50)
        log.info("\U0001f9e0 %s started", BRAIN_NAME)
        log.info("=" * 50)

    def stop(self):
        self._running = False
        self.pulse.stop()
        self.memory.save()
        self.chat.send_notice("\U0001f534 **Offline** \u2014 Shutting down")
        log.info("\U0001f9e0 Brain Server stopped")

    def _background_loop(self):
        """Idle loop — only processes pulse events and periodic heartbeat.
        Does NOT call LLM. PulseDetector handles system monitoring separately."""
        while self._running:
            try:
                # Process pulse events (system health alerts)
                while self.pulse.has_events():
                    event = self.pulse.get_event()
                    if event:
                        self.escalation.process(event, self._on_force_interrupt)

                # Check for escalated events
                escalated = self.escalation.check_escalations()
                for ev in escalated:
                    self.chat.send_message("\u26a1 **Escalated** [{}] \u2014 {}".format(ev["name"], ev["description"]))

                # Idle heartbeat every 5 minutes (not 30s — saves log spam)
                now = time.time()
                if now - self._last_idle_beat >= IDLE_HEARTBEAT_INTERVAL:
                    self._last_idle_beat = now
                    log.info("[IDLE] Brain Server online — thoughts=%d actions=%d pulse=%s",
                             self._total_thoughts, self._total_actions,
                             "alive" if self.pulse.is_alive() else "dead")

                time.sleep(5)  # Check every 5 seconds (responsive but low CPU)
            except Exception as e:
                log.error("Background loop error: %s", e)
                time.sleep(5)

    def _on_force_interrupt(self, name: str, desc: str):
        log.warning("\u26a1 FORCE INTERRUPT: %s \u2014 %s", name, desc)

    def _think(self, content: str, thought_type: str = "reasoning"):
        entry = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content": content,
            "type": thought_type,
        }
        self._thought_log.append(entry)
        self._total_thoughts += 1
        log.info("\U0001f4ad [%s] %s", thought_type.upper(), content)
        self._save_state()

    def _act(self, action_type: str, params: dict = None) -> dict:
        entry = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": action_type,
            "params": params or {},
            "result": None,
        }
        log.info("\u26a1 [%s] %s", action_type.upper(), json.dumps(params or {}))

        if action_type == "notify":
            text = params.get("text", "")
            entry["result"] = {"sent": self.chat.send_message(text)}
        elif action_type == "notify_notice":
            text = params.get("text", "")
            entry["result"] = {"sent": self.chat.send_notice(text)}
        elif action_type == "delegate_system":
            entry["result"] = self.system.run_command(params.get("cmd", ""), params.get("timeout", 30))
        elif action_type == "delegate_bookstack":
            cmd = params.get("command", "")
            try:
                if cmd == "search":
                    entry["result"] = {"pages": self.bookstack.search_pages(params.get("query", ""))}
                elif cmd == "list_books":
                    entry["result"] = {"books": self.bookstack.list_books()}
                elif cmd == "create_page":
                    entry["result"] = self.bookstack.create_page(
                        params.get("book_id", 0), params.get("name", ""), params.get("markdown", ""))
                else:
                    entry["result"] = {"error": "Unknown bookstack command"}
            except Exception as e:
                entry["result"] = {"error": str(e)}
        else:
            entry["result"] = {"error": "Unknown action type: " + action_type}

        self._action_log.append(entry)
        self._total_actions += 1
        self._save_state()
        return entry

    def run_task(self, task: str) -> str:
        """Run a task through the Inner Monologue Agent with full context."""
        self._think("Received task: " + task[:100], "plan")
        self.chat.send_notice("\U0001f4ac Processing: " + task[:100])

        # Load memory context before starting (cross-session memory)
        self.memory.load()
        context = self.memory.get_context(max_entries=10)
        if context:
            log.info("[MEMORY] Loaded context for task: %.100s", context[:100])

        try:
            # Run agent with resilience wrapping
            result = self.retry.execute(self.agent.run, task)
            self._think("Task complete: " + result[:100], "observation")
            self.chat.send_notice("\u2705 Done: " + result[:100])

            # Self-Reflection: learn from this interaction
            try:
                history = self.agent.get_history
                self.self_reflection.reflect(history)
                insights = self.self_reflection.get_insights()
                if insights:
                    log.info("[REFLECT] Insights: %s", insights[:200])
            except Exception as ref_err:
                log.warning("[REFLECT] Error: %s", ref_err)

            # Save memory after task
            self.memory.save()
            log.info("[MEMORY] Saved after task — %d entries", self.memory.entry_count)

            return result
        except Exception as e:
            error_msg = str(e)
            self._think("Task failed: " + error_msg, "error")
            self.chat.send_notice("\u274c Error: " + error_msg[:100])
            self.memory.add_entry("error", error_msg)
            self.memory.save()
            return "Error: " + error_msg

    def get_state_summary(self) -> dict:
        return {
            "brain": BRAIN_NAME,
            "thoughts": self._total_thoughts,
            "actions": self._total_actions,
            "session_start": self._session_start,
            "last_thought": self._thought_log[-1] if self._thought_log else None,
            "last_action": self._action_log[-1] if self._action_log else None,
            "pulse_running": self.pulse.is_alive() if self.pulse else False,
            "memory_entries": self.memory.entry_count if self.memory else 0,
        }

    def _save_state(self):
        try:
            state = {
                "memory": {
                    "session_start": self._session_start,
                    "total_thoughts": self._total_thoughts,
                    "total_actions": self._total_actions,
                },
                "recent_thoughts": self._thought_log[-20:],
                "recent_actions": self._action_log[-20:],
            }
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            log.error("Failed to save state: %s", e)


# Webhook HTTP Server
brain_server: Optional[BrainServerV6] = None


class BrainHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def do_GET(self):
        if self.path == "/health":
            self._send_json({
                "status": "ok",
                "brain": BRAIN_NAME,
                "thoughts": brain_server._total_thoughts if brain_server else 0,
                "actions": brain_server._total_actions if brain_server else 0,
                "pulse": brain_server.pulse.is_alive() if brain_server and brain_server.pulse else False,
                "memory_entries": brain_server.memory.entry_count if brain_server and brain_server.memory else 0,
            })
        elif self.path == "/state":
            self._send_json(brain_server.get_state_summary() if brain_server else {"error": "not started"})
        elif self.path == "/thoughts":
            self._send_json({"thoughts": brain_server._thought_log[-50:] if brain_server else []})
        elif self.path == "/actions":
            self._send_json({"actions": brain_server._action_log[-50:] if brain_server else []})
        elif self.path == "/memory":
            if brain_server and brain_server.memory:
                self._send_json({
                    "entries": brain_server.memory.entry_count,
                    "summary": brain_server.memory.summary or "",
                    "recent": brain_server.memory.get_recent(10),
                })
            else:
                self._send_json({"error": "no memory"}, 404)
        elif self.path == "/reflect":
            if brain_server and brain_server.self_reflection:
                self._send_json({
                    "insights": brain_server.self_reflection.get_insights(),
                    "profile": brain_server.self_reflection.user_profile.to_dict(),
                })
            else:
                self._send_json({"error": "no reflection"}, 404)
        elif self.path == "/discovery":
            if brain_server and brain_server._discovery_results:
                self._send_json(brain_server._discovery_results)
            else:
                self._send_json({"status": "not_run", "message": "ยังไม่เคยรัน Auto-Discovery"})
        elif self.path == "/discovery/scan":
            if brain_server:
                # รัน discovery แบบไม่ต้องรอ — ใช้ thread แยก
                import threading
                t = threading.Thread(target=brain_server.run_discovery, daemon=True)
                t.start()
                self._send_json({"status": "started", "message": "Auto-Discovery กำลังทำงาน..."})
            else:
                self._send_json({"error": "brain not started"}, 404)
        elif self.path == "/discovery/pending":
            if brain_server:
                self._send_json({
                    "pending": brain_server._pending_questions,
                    "count": len(brain_server._pending_questions),
                })
            else:
                self._send_json({"error": "brain not started"}, 404)
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b"{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {}

        if self.path == "/think":
            prompt = data.get("prompt", "")
            if prompt:
                result = brain_server.run_task(prompt)
                self._send_json({
                    "status": "ok",
                    "result": result,
                    "thoughts": brain_server._total_thoughts,
                    "actions": brain_server._total_actions,
                })
            else:
                self._send_json({"error": "No prompt provided"}, 400)
        elif self.path == "/reset":
            if os.path.exists(STATE_FILE):
                os.remove(STATE_FILE)
            if brain_server and brain_server.memory:
                brain_server.memory.clear()
            self._send_json({"status": "reset", "message": "Brain state cleared"})
        elif self.path == "/discovery/answer":
            service_name = data.get("service", "")
            is_module = data.get("is_module", False)
            if service_name and brain_server:
                result = brain_server.answer_discovery_question(service_name, is_module)
                self._send_json({"status": "ok", "result": result})
            else:
                self._send_json({"error": "Missing service name"}, 400)
        elif self.path == "/discovery/register":
            """ลงทะเบียน service ที่ยืนยันแล้วเป็น ERP Module"""
            service_name = data.get("service", "")
            category = data.get("category", "erp-core")
            if service_name and brain_server:
                brain_server.discovery.classifier.record_feedback(service_name, True)
                brain_server._think(f"Registered {service_name} as ERP Module ({category})", "action")
                brain_server.chat.send_message(f"\u2705 **ERP Module Registered**: {service_name} ({category})")
                self._send_json({"status": "ok", "message": f"{service_name} registered as ERP Module"})
            else:
                self._send_json({"error": "Missing service name"}, 400)
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        log.info("%s - %s", self.client_address[0], format % args)


def main():
    global brain_server
    brain_server = BrainServerV6()
    brain_server.start()

    server = HTTPServer(("0.0.0.0", PORT), BrainHandler)
    log.info("=" * 50)
    log.info("%s Webhook API running on port %d", BRAIN_NAME, PORT)
    log.info("Endpoints:")
    log.info("  GET  /health          - Health check")
    log.info("  GET  /state           - Brain state summary")
    log.info("  GET  /thoughts        - Recent thoughts")
    log.info("  GET  /actions         - Recent actions")
    log.info("  GET  /memory          - Memory context & summary")
    log.info("  GET  /reflect         - Self-reflection insights")
    log.info("  GET  /discovery       - Auto-Discovery results")
    log.info("  GET  /discovery/scan  - Run Auto-Discovery")
    log.info("  GET  /discovery/pending - Pending questions")
    log.info("  POST /think           - Send a prompt to the brain")
    log.info("  POST /reset           - Reset brain state")
    log.info("  POST /discovery/answer - Answer discovery question")
    log.info("  POST /discovery/register - Register service as Module")
    log.info("=" * 50)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down...")
        brain_server.stop()
        server.shutdown()


if __name__ == "__main__":
    main()
