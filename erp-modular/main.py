"""ERP Modular - FastAPI Application

API Gateway + Auth + Rate Limiting + CRUD + Agent Logging + Micro-frontend Shell
"""

import os
import logging
import requests
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from api.router import router as crud_router
from api.gateway import router as gateway_router
from api.rate_limit import RateLimitMiddleware, get_rate_limiter
from core.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("erp")

app = FastAPI(
    title="ERP Modular",
    version="0.2.0",
    description="ERP Core แบบ Modular — API Gateway + Auth + Rate Limiting + Agent Logging + Micro-frontend Shell",
)

# ─── Static Files (Micro-frontend Shell) ────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    def serve_shell():
        """เสิร์ฟ Micro-frontend Shell"""
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    logger.info("Micro-frontend Shell พร้อมที่ / (static)")
else:
    logger.warning("ไม่พบ frontend/ — Micro-frontend Shell ไม่ทำงาน")

# ─── Agent Activity Log (in-memory) ─────────────────────────────────────────
agent_log: list[dict] = []
MAX_AGENT_LOG = 500


def log_agent_activity(activity: str, detail: str = "", status: str = "info"):
    """บันทึกกิจกรรมของ Agent — ดูได้ที่ /agent/logs"""
    global agent_log
    agent_log.append({
        "timestamp": datetime.now().isoformat(),
        "activity": activity,
        "detail": detail[:500],
        "status": status,
    })
    # เก็บเฉพาะ 500 รายการล่าสุด
    if len(agent_log) > MAX_AGENT_LOG:
        agent_log = agent_log[-MAX_AGENT_LOG:]
    logger.info(f"[Agent] {activity}: {detail[:100]}")


# ─── Middleware ──────────────────────────────────────────────────────────────
app.add_middleware(RateLimitMiddleware)

# ─── Routers ────────────────────────────────────────────────────────────────
app.include_router(crud_router)       # /api/v1/*
app.include_router(gateway_router)    # /gateway/*


@app.on_event("startup")
def on_startup():
    init_db()
    log_agent_activity("system", "ERP Modular started — Gateway + Auth + Rate Limit enabled")
    logger.info("ERP Modular started — Gateway + Auth + Rate Limit enabled")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "0.1.0",
        "gateway": True,
        "auth": True,
        "rate_limit": True,
    }


# ─── Agent Logging Endpoints ────────────────────────────────────────────────

@app.get("/agent/logs")
def get_agent_logs(limit: int = 50, status: str = ""):
    """ดู Log กิจกรรมของ Agent — เรียงจากล่าสุด"""
    logs = agent_log.copy()
    if status:
        logs = [l for l in logs if l["status"] == status]
    logs.reverse()  # ล่าสุดขึ้นก่อน
    return {
        "total": len(logs),
        "returned": min(limit, len(logs)),
        "logs": logs[:limit],
    }


@app.post("/agent/logs")
async def post_agent_log(
    request: Request,
):
    """รับ Log จาก Agent ภายนอก (เช่น inner-monologue-agent)"""
    # รองรับทั้ง JSON body และ query params
    body = {}
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            body = {}

    activity = body.get("activity") or request.query_params.get("activity")
    detail = body.get("detail") or request.query_params.get("detail") or ""
    status = body.get("status") or request.query_params.get("status") or "info"

    if not activity:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="activity is required")

    # ตรวจสอบ secret token ถ้ามี
    auth_header = request.headers.get("Authorization", "") if request else ""
    expected_token = "erp-agent-log-2026"
    if auth_header and not auth_header.endswith(expected_token):
        if auth_header.startswith("Bearer "):
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Invalid token")

    log_agent_activity(activity, detail, status)
    return {"ok": True, "logged": activity}


@app.get("/agent/stats")
def get_agent_stats():
    """ดูสถิติการทำงานของ Agent"""
    logs = agent_log
    total = len(logs)
    if total == 0:
        return {"total": 0, "by_status": {}, "recent_activities": []}

    by_status = {}
    for l in logs:
        s = l["status"]
        by_status[s] = by_status.get(s, 0) + 1

    # กิจกรรมล่าสุด 10 รายการ
    recent = [l["activity"] for l in logs[-10:]]

    return {
        "total": total,
        "by_status": by_status,
        "recent_activities": recent,
        "last_activity": logs[-1]["timestamp"] if logs else None,
    }


@app.delete("/agent/logs")
def clear_agent_logs():
    """ล้าง Log ทั้งหมด"""
    global agent_log
    agent_log = []
    return {"ok": True, "cleared": True}


# ─── Prompt Studio Bridge ────────────────────────────────────────────────────

PROMPT_STUDIO_URL = os.environ.get("PROMPT_STUDIO_URL", "http://localhost:8108")


@app.get("/prompts")
def list_all_prompts():
    """List all available prompt modules from Prompt Studio (MCP bridge)"""
    try:
        resp = requests.get(f"{PROMPT_STUDIO_URL}/modules", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning(f"Prompt Studio unreachable: {e}")
    return {"modules": [], "total": 0, "mode": "unavailable"}


@app.get("/prompts/{module}")
def list_module_prompts(module: str):
    """List prompts in a module from Prompt Studio"""
    try:
        resp = requests.get(f"{PROMPT_STUDIO_URL}/prompts/{module}", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning(f"Prompt Studio unreachable: {e}")
    return {"module": module, "files": [], "total": 0, "mode": "unavailable"}


@app.get("/prompts/{module}/{name:path}")
def get_prompt(module: str, name: str):
    """Get a specific prompt content from Prompt Studio"""
    try:
        resp = requests.get(f"{PROMPT_STUDIO_URL}/prompts/{module}/{name}", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return {"error": "prompt not found"}


@app.get("/mcp/prompts")
def mcp_prompts_list():
    """MCP prompts_list() compatible — returns prompt catalog for agents"""
    try:
        resp = requests.get(f"{PROMPT_STUDIO_URL}/modules", timeout=5)
        if resp.status_code != 200:
            return []
        return resp.json().get("modules", [])
    except:
        return []


@app.get("/mcp/resources")
def mcp_resources_list():
    """MCP resources_list() compatible — returns available prompt files"""
    resources = []
    try:
        modules_resp = requests.get(f"{PROMPT_STUDIO_URL}/modules", timeout=5)
        if modules_resp.status_code == 200:
            for mod in modules_resp.json().get("modules", []):
                mod_name = mod["name"]
                prompts_resp = requests.get(f"{PROMPT_STUDIO_URL}/prompts/{mod_name}", timeout=5)
                if prompts_resp.status_code == 200:
                    for f in prompts_resp.json().get("files", []):
                        resources.append({
                            "name": f"prompts/{mod_name}/{f['name']}",
                            "module": mod_name,
                            "path": f["path"],
                            "size": f["size"],
                        })
    except:
        pass
    return resources
