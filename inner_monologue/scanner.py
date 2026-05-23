"""
System Bot Scanner — Auto-Discovery สำหรับ ERP Stack
สแกน PM2, Docker, Ports, Git, Endpoints ใน Oracle VM
และส่งข้อมูลให้ Inner Monologue Agent วิเคราะห์ด้วย LLM

Phase 7: Auto-Discovery + Semi-Supervised Learning
"""

import json
import logging
import os
import re
import socket
import subprocess
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Optional

log = logging.getLogger("brain.scanner")

# ──────────────────────────── Service Scanner ────────────────────────────

class ServiceScanner:
    """สแกน services ในระบบ — PM2, Docker, Ports, Git, Endpoints"""

    def __init__(self, ssh_host: Optional[str] = None, ssh_user: Optional[str] = None, ssh_pass: Optional[str] = None):
        self.ssh_host = ssh_host
        self.ssh_user = ssh_user
        self.ssh_pass = ssh_pass
        self._results: dict[str, Any] = {}

    def scan_all(self) -> dict[str, Any]:
        """สแกนทุกอย่างในระบบ"""
        log.info("[SCANNER] เริ่มสแกนระบบ...")
        self._results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "pm2": self._scan_pm2(),
            "docker": self._scan_docker(),
            "ports": self._scan_ports(),
            "git_repos": self._scan_git_repos(),
            "endpoints": [],
            "bridge_services": self._scan_bridge_services(),
            "erp_modules": self._scan_erp_modules(),
        }
        # ตรวจสอบ endpoints ที่พบ
        all_endpoints = self._discover_endpoints()
        self._results["endpoints"] = all_endpoints
        log.info("[SCANNER] สแกนเสร็จ — พบ %d services", len(all_endpoints))
        return self._results

    def _run_remote(self, cmd: str) -> str:
        """รันคำสั่งผ่าน SSH ถ้ามี remote host"""
        if self.ssh_host and self.ssh_user and self.ssh_pass:
            full_cmd = f'sshpass -p \'{self.ssh_pass}\' ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 {self.ssh_user}@{self.ssh_host} \'{cmd}\''
        else:
            full_cmd = cmd
        try:
            result = subprocess.run(full_cmd, shell=True, capture_output=True, timeout=15, text=True)
            return result.stdout
        except subprocess.TimeoutExpired:
            return "TIMEOUT"
        except Exception as e:
            return f"ERROR: {e}"

    def _scan_pm2(self) -> list[dict]:
        """สแกน PM2 processes"""
        log.info("[SCANNER] สแกน PM2...")
        out = self._run_remote("pm2 jlist 2>/dev/null || echo '[]'")
        if not out or out == "TIMEOUT":
            return []
        try:
            processes = json.loads(out)
            results = []
            for p in processes:
                name = p.get("name", "unknown")
                pm_id = p.get("pm_id", -1)
                status = p.get("pm2_env", {}).get("status", "unknown")
                pid = p.get("pid")
                monit = p.get("monit", {})
                cpu = monit.get("cpu", 0)
                memory = monit.get("memory", 0)
                # หา port จาก args หรือ env
                port = None
                pm_env = p.get("pm2_env", {})
                env = pm_env.get("env", {})
                port = env.get("PORT") or env.get("port")
                if not port:
                    # ลองหา port จาก args
                    args = " ".join(pm_env.get("args", []))
                    m = re.search(r'--port\s+(\d+)', args)
                    if m:
                        port = m.group(1)
                results.append({
                    "name": name,
                    "pm_id": pm_id,
                    "status": status,
                    "pid": pid,
                    "cpu": cpu,
                    "memory": memory,
                    "port": port,
                    "type": "pm2",
                })
            return results
        except json.JSONDecodeError:
            return []

    def _scan_docker(self) -> list[dict]:
        """สแกน Docker containers"""
        log.info("[SCANNER] สแกน Docker...")
        out = self._run_remote("docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}' 2>/dev/null || echo ''")
        if not out or out == "TIMEOUT":
            return []
        results = []
        for line in out.strip().split("\n"):
            if not line or "|" not in line:
                continue
            parts = line.split("|")
            name = parts[0] if len(parts) > 0 else ""
            image = parts[1] if len(parts) > 1 else ""
            status = parts[2] if len(parts) > 2 else ""
            ports_str = parts[3] if len(parts) > 3 else ""
            # extract ports
            ports = []
            for m in re.finditer(r'(\d+)->(\d+)/tcp', ports_str):
                ports.append({"host": m.group(1), "container": m.group(2)})
            results.append({
                "name": name,
                "image": image,
                "status": status,
                "ports": ports,
                "type": "docker",
            })
        return results

    def _scan_ports(self) -> list[dict]:
        """สแกน ports ที่เปิดอยู่"""
        log.info("[SCANNER] สแกน Ports...")
        out = self._run_remote("ss -tlnp 2>/dev/null | tail -n +2 || netstat -tlnp 2>/dev/null | tail -n +2 || echo ''")
        if not out or out == "TIMEOUT":
            return []
        results = []
        for line in out.strip().split("\n"):
            if not line:
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            addr = parts[3] if "ss" in out else parts[3]
            # extract port
            m = re.search(r':(\d+)$', addr)
            if not m:
                continue
            port = int(m.group(1))
            if port < 1024:
                continue  # ข้าม system ports
            # extract process
            proc = ""
            if len(parts) > 4:
                proc = parts[-1] if "users:" in parts[-1] else ""
            results.append({
                "port": port,
                "process": proc,
                "type": "port",
            })
        return results

    def _scan_git_repos(self) -> list[dict]:
        """สแกน Git repositories ใน workspace"""
        log.info("[SCANNER] สแกน Git repos...")
        out = self._run_remote("find /workspace -name '.git' -maxdepth 3 -type d 2>/dev/null | sed 's|/.git$||' || echo ''")
        if not out or out == "TIMEOUT":
            return []
        results = []
        for repo_path in out.strip().split("\n"):
            if not repo_path:
                continue
            # get remote URL
            remote = self._run_remote(f"cd {repo_path} && git remote get-url origin 2>/dev/null || echo ''")
            # get branch
            branch = self._run_remote(f"cd {repo_path} && git branch --show-current 2>/dev/null || echo ''")
            results.append({
                "path": repo_path,
                "remote": remote.strip(),
                "branch": branch.strip(),
                "type": "git",
            })
        return results

    def _scan_bridge_services(self) -> list[dict]:
        """สแกน Bridge Service Registry"""
        log.info("[SCANNER] สแกน Bridge services...")
        # ลองหลาย port
        for port in [51517, 51518, 51519]:
            url = f"http://89.167.82.205:{port}/api/services"
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                    if isinstance(data, list):
                        return data
                    if isinstance(data, dict) and "services" in data:
                        return data["services"]
            except Exception:
                continue
        return []

    def _scan_erp_modules(self) -> list[dict]:
        """สแกน ERP Modular API"""
        log.info("[SCANNER] สแกน ERP Modules...")
        try:
            req = urllib.request.Request("http://89.167.82.205:8102/api/v1/modules/")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read())
        except Exception:
            return []

    def _discover_endpoints(self) -> list[dict]:
        """ค้นหา endpoints ทั้งหมดจากข้อมูลที่สแกนมา"""
        endpoints = []

        # จาก PM2 — ลองเรียก health check
        for proc in self._results.get("pm2", []):
            name = proc.get("name", "")
            port = proc.get("port")
            if port:
                endpoints.append({
                    "name": name,
                    "port": int(port),
                    "source": "pm2",
                    "status": proc.get("status"),
                })

        # จาก Docker
        for container in self._results.get("docker", []):
            for p in container.get("ports", []):
                endpoints.append({
                    "name": container.get("name", ""),
                    "port": int(p["host"]),
                    "source": "docker",
                    "status": container.get("status"),
                })

        # Deduplicate by port
        seen_ports = set()
        unique = []
        for ep in sorted(endpoints, key=lambda x: x.get("port", 0)):
            port = ep.get("port")
            if port and port not in seen_ports:
                seen_ports.add(port)
                unique.append(ep)
        return unique


# ──────────────────────────── Service Classifier ────────────────────────────

class ServiceClassifier:
    """วิเคราะห์ services ด้วย LLM ว่าอันไหนคือ ERP Module"""

    # หมวดหมู่ที่รู้จัก — ใช้เป็น hint ให้ LLM
    KNOWN_PATTERNS = {
        "erp-modular": {"category": "erp-core", "confidence": 0.95},
        "brain-server": {"category": "ai-agent", "confidence": 0.95},
        "bridge": {"category": "bridge", "confidence": 0.95},
        "bookstack": {"category": "knowledge-base", "confidence": 0.95},
        "plane": {"category": "project-management", "confidence": 0.9},
        "planka": {"category": "project-management", "confidence": 0.9},
        "siyuan": {"category": "knowledge-base", "confidence": 0.9},
        "openobserve": {"category": "monitoring", "confidence": 0.9},
        "noteforge": {"category": "knowledge-base", "confidence": 0.85},
        "task-manager": {"category": "task-management", "confidence": 0.85},
        "etsy-connector": {"category": "ecommerce", "confidence": 0.85},
        "mcp-gateway": {"category": "gateway", "confidence": 0.85},
        "postgres": {"category": "database", "confidence": 0.95},
        "redis": {"category": "cache", "confidence": 0.95},
        "nginx": {"category": "proxy", "confidence": 0.9},
    }

    # Services ที่รู้แล้วว่าไม่ใช่ ERP Module
    KNOWN_NON_MODULES = {
        "postgres", "redis", "nginx", "traefik", "prometheus",
        "grafana", "openobserve", "bookstack", "plane", "planka",
        "siyuan", "mcp-gateway",
    }

    def __init__(self, llm_call_fn: Optional[callable] = None):
        self.llm_call_fn = llm_call_fn
        self._classification_history: list[dict] = []
        self._user_feedback: dict[str, bool] = {}  # service_name → is_module

    def set_llm_fn(self, fn: callable):
        self.llm_call_fn = fn

    def classify(self, service: dict, scan_data: dict) -> dict:
        """วิเคราะห์ service ว่าควรเป็น ERP Module หรือไม่"""
        name = service.get("name", "").lower()
        port = service.get("port", 0)

        # 1. ตรวจสอบจาก KNOWN_NON_MODULES
        if name in self.KNOWN_NON_MODULES:
            return {
                "service": name,
                "port": port,
                "is_module": False,
                "confidence": 0.95,
                "category": self.KNOWN_PATTERNS.get(name, {}).get("category", "infrastructure"),
                "reason": "รู้จักแล้วว่าไม่ใช่ ERP Module",
                "auto": True,
            }

        # 2. ตรวจสอบจาก KNOWN_PATTERNS
        if name in self.KNOWN_PATTERNS:
            pattern = self.KNOWN_PATTERNS[name]
            is_module = pattern["category"] in ("erp-core", "ecommerce", "task-management")
            return {
                "service": name,
                "port": port,
                "is_module": is_module,
                "confidence": pattern["confidence"],
                "category": pattern["category"],
                "reason": f"รู้จัก pattern: {pattern['category']}",
                "auto": True,
            }

        # 3. ตรวจสอบจาก user feedback history
        if name in self._user_feedback:
            return {
                "service": name,
                "port": port,
                "is_module": self._user_feedback[name],
                "confidence": 0.9,
                "category": "unknown",
                "reason": "จาก feedback ผู้ใช้ครั้งก่อน",
                "auto": True,
            }

        # 4. ใช้ LLM วิเคราะห์
        if self.llm_call_fn:
            return self._classify_with_llm(service, scan_data)

        # 5. Default — ไม่แน่ใจ
        return {
            "service": name,
            "port": port,
            "is_module": None,
            "confidence": 0.0,
            "category": "unknown",
            "reason": "ไม่สามารถวิเคราะห์ได้ — ไม่มี LLM",
            "auto": False,
        }

    def _classify_with_llm(self, service: dict, scan_data: dict) -> dict:
        """ใช้ LLM วิเคราะห์ service"""
        name = service.get("name", "")
        port = service.get("port", 0)
        source = service.get("source", "unknown")

        prompt = f"""คุณคือ System Analyst ที่วิเคราะห์ services ใน ERP Stack

## Service ที่พบ:
- Name: {name}
- Port: {port}
- Source: {source}

## ข้อมูลระบบอื่นๆ:
- PM2 processes: {[p.get("name") for p in scan_data.get("pm2", [])[:10]]}
- Docker containers: {[c.get("name") for c in scan_data.get("docker", [])[:10]]}
- Bridge services: {[s.get("slug") if isinstance(s, dict) else s for s in scan_data.get("bridge_services", [])[:10]]}
- ERP Modules ที่ register แล้ว: {[m.get("slug") for m in scan_data.get("erp_modules", [])]}

## วิเคราะห์ว่า service "{name}" ควรเป็น ERP Module หรือไม่?
พิจารณาจาก:
1. ชื่อ service — ถ้าเกี่ยวกับ ERP, Business, Finance, HR, Logistic, Product → น่าจะใช่
2. ถ้าเป็น infrastructure (DB, cache, proxy, monitoring) → ไม่ใช่
3. ถ้าเป็น knowledge base, project management → ไม่ใช่ (เป็น tools สนับสนุน)
4. ถ้าเป็น AI agent, bridge, gateway → ไม่ใช่ (เป็นระบบเชื่อมต่อ)

ตอบเป็น JSON:
{{"is_module": true/false, "confidence": 0.0-1.0, "category": "หมวดหมู่", "reason": "เหตุผลสั้นๆ"}}"""

        try:
            response = self.llm_call_fn(prompt)
            # extract JSON
            m = re.search(r'\{.*\}', response, re.DOTALL)
            if m:
                data = json.loads(m.group())
                result = {
                    "service": name,
                    "port": port,
                    "is_module": data.get("is_module"),
                    "confidence": data.get("confidence", 0.5),
                    "category": data.get("category", "unknown"),
                    "reason": data.get("reason", ""),
                    "auto": False,
                }
                self._classification_history.append(result)
                return result
        except Exception as e:
            log.warning("[CLASSIFIER] LLM error: %s", e)

        return {
            "service": name,
            "port": port,
            "is_module": None,
            "confidence": 0.0,
            "category": "unknown",
            "reason": "LLM ไม่สามารถวิเคราะห์ได้",
            "auto": False,
        }

    def record_feedback(self, service_name: str, is_module: bool):
        """บันทึก feedback จากผู้ใช้"""
        self._user_feedback[service_name.lower()] = is_module
        # อัปเดตประวัติ
        for h in self._classification_history:
            if h["service"].lower() == service_name.lower():
                h["is_module"] = is_module
                h["confidence"] = 0.95
                h["auto"] = True
                h["reason"] = "ยืนยันโดยผู้ใช้"

    def get_uncertain_services(self) -> list[dict]:
        """รายการ services ที่ไม่แน่ใจ — รอ feedback จากผู้ใช้"""
        return [
            h for h in self._classification_history
            if h.get("is_module") is None or h.get("confidence", 0) < 0.7
        ]

    def get_summary(self) -> dict:
        """สรุปผลการจำแนก"""
        modules = [h for h in self._classification_history if h.get("is_module") is True]
        non_modules = [h for h in self._classification_history if h.get("is_module") is False]
        uncertain = self.get_uncertain_services()
        return {
            "total_classified": len(self._classification_history),
            "modules": len(modules),
            "non_modules": len(non_modules),
            "uncertain": len(uncertain),
            "module_list": [m["service"] for m in modules],
            "uncertain_list": [u["service"] for u in uncertain],
        }


# ──────────────────────────── Auto-Discovery Engine ────────────────────────────

class AutoDiscoveryEngine:
    """Engine หลักสำหรับ Auto-Discovery — สแกน → วิเคราะห์ → ลงทะเบียน"""

    def __init__(self, llm_call_fn: Optional[callable] = None):
        self.scanner = ServiceScanner()
        self.classifier = ServiceClassifier(llm_call_fn=llm_call_fn)
        self._scan_results: Optional[dict] = None
        self._classification_results: list[dict] = []

    def set_llm_fn(self, fn: callable):
        self.classifier.set_llm_fn(fn)

    def run_discovery(self) -> dict:
        """รัน Auto-Discovery เต็มรูปแบบ"""
        log.info("[DISCOVERY] === เริ่ม Auto-Discovery ===")

        # 1. สแกน
        self._scan_results = self.scanner.scan_all()

        # 2. วิเคราะห์แต่ละ endpoint
        self._classification_results = []
        for ep in self._scan_results.get("endpoints", []):
            result = self.classifier.classify(ep, self._scan_results)
            self._classification_results.append(result)
            log.info("[DISCOVERY] %s → is_module=%s confidence=%.2f (%s)",
                     ep.get("name"), result.get("is_module"), result.get("confidence", 0), result.get("reason", ""))

        # 3. วิเคราะห์ Bridge services
        for svc in self._scan_results.get("bridge_services", []):
            svc_name = svc.get("slug") or svc.get("name", "")
            if not svc_name:
                continue
            # ตรวจสอบว่าซ้ำกับ endpoint หรือไม่
            if any(r["service"] == svc_name for r in self._classification_results):
                continue
            result = self.classifier.classify({"name": svc_name, "port": 0, "source": "bridge"}, self._scan_results)
            self._classification_results.append(result)

        # 4. วิเคราะห์ ERP Modules ที่มีอยู่แล้ว
        for mod in self._scan_results.get("erp_modules", []):
            mod_name = mod.get("slug", "")
            if not mod_name:
                continue
            if any(r["service"] == mod_name for r in self._classification_results):
                continue
            self._classification_results.append({
                "service": mod_name,
                "port": 0,
                "is_module": True,
                "confidence": 1.0,
                "category": "erp-core",
                "reason": "ลงทะเบียนเป็น ERP Module อยู่แล้ว",
                "auto": True,
            })

        return self.get_summary()

    def get_summary(self) -> dict:
        """สรุปผลการค้นพบทั้งหมด"""
        uncertain = self.classifier.get_uncertain_services()
        modules = [r for r in self._classification_results if r.get("is_module") is True]
        non_modules = [r for r in self._classification_results if r.get("is_module") is False]

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_endpoints": len(self._scan_results.get("endpoints", [])) if self._scan_results else 0,
            "total_classified": len(self._classification_results),
            "modules_found": len(modules),
            "non_modules_found": len(non_modules),
            "uncertain": len(uncertain),
            "modules": [
                {"name": m["service"], "port": m["port"], "category": m.get("category", ""), "confidence": m.get("confidence", 0)}
                for m in modules
            ],
            "uncertain_services": [
                {"name": u["service"], "port": u["port"], "reason": u.get("reason", "")}
                for u in uncertain
            ],
            "scan_summary": {
                "pm2_processes": len(self._scan_results.get("pm2", [])),
                "docker_containers": len(self._scan_results.get("docker", [])),
                "ports_found": len(self._scan_results.get("ports", [])),
                "git_repos": len(self._scan_results.get("git_repos", [])),
                "bridge_services": len(self._scan_results.get("bridge_services", [])),
                "erp_modules": len(self._scan_results.get("erp_modules", [])),
            } if self._scan_results else {},
        }

    def get_scan_results(self) -> Optional[dict]:
        return self._scan_results

    def get_classification_results(self) -> list[dict]:
        return self._classification_results
