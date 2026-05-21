"""ERP Modular - FastAPI Application

API Gateway + Auth + Rate Limiting + CRUD
"""

import logging
from fastapi import FastAPI
from api.router import router as crud_router
from api.gateway import router as gateway_router
from api.rate_limit import RateLimitMiddleware, get_rate_limiter
from core.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("erp")

app = FastAPI(
    title="ERP Modular",
    version="0.1.0",
    description="ERP Core แบบ Modular — API Gateway + Auth + Rate Limiting",
)

# ─── Middleware ──────────────────────────────────────────────────────────────
app.add_middleware(RateLimitMiddleware)

# ─── Routers ────────────────────────────────────────────────────────────────
app.include_router(crud_router)       # /api/v1/*
app.include_router(gateway_router)    # /gateway/*


@app.on_event("startup")
def on_startup():
    init_db()
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
