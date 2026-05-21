"""ERP Modular - FastAPI Application

API Gateway + Auth + Rate Limiting + CRUD + Agent Logging
"""

import logging
from datetime import datetime
from fastapi import FastAPI, Request
from api.router import router as crud_router
from api.gateway import router as gateway_router
from api.rate_limit import RateLimitMiddleware, get_rate_limiter
from core.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("erp")

app = FastAPI(
    title="ERP Modular",
    version="0.1.0",
    description="ERP Core แบบ Modular — API Gateway + Auth + Rate Limiting + Agent Logging",
)

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
def post_agent_log(
    activity: str,
    detail: str = "",
    status: str = "info",
    request: Request = None,
):
    """รับ Log จาก Agent ภายนอก (เช่น inner-monologue-agent)"""
    # ตรวจสอบ secret token ถ้ามี
    auth_header = request.headers.get("Authorization", "") if request else ""
    expected_token = "erp-agent-log-2026"
    if auth_header and not auth_header.endswith(expected_token):
        # ถ้ามี Authorization header แต่ไม่ตรง — ไม่อนุญาต
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
