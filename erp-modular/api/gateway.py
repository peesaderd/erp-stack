"""API Gateway — Reverse Proxy + Routing + Auth สำหรับ ERP Modular

หน้าที่:
1. เป็นทางเข้าออกเดียวสำหรับ Mini App ทั้งหมด
2. ตรวจสอบ JWT/API Key ทุก request
3. Route ไปยัง backend ที่ถูกต้อง (ERP API หรือ Mini App)
4. เก็บ audit log
5. โหลด Mini Apps จาก Database (App model) + fallback hardcoded

โครงสร้าง:
    GatewayRouter: FastAPI router ที่รวม endpoints ต่างๆ
    proxy_request(): ส่ง request ต่อไปยัง Mini App backend
"""

import os
import json
import logging
from typing import Optional
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlmodel import Session, select

from .auth import (
    TokenData, require_auth, require_permission,
    create_access_token, decode_token, PERM_ADMIN,
)
from .rate_limit import get_rate_limiter
from models.entity import App
from core.database import get_session

logger = logging.getLogger("erp.gateway")

router = APIRouter(prefix="/gateway")

# ─── Role Hierarchy ─────────────────────────────────────────────────────────

ROLE_HIERARCHY = ["viewer", "editor", "developer", "mini-app", "admin"]


def _user_role_level(role: str) -> int:
    try:
        return ROLE_HIERARCHY.index(role)
    except ValueError:
        return -1


def _check_role(user_role: str, required_role: str) -> bool:
    return _user_role_level(user_role) >= _user_role_level(required_role)


# ─── Mini App Registry (Load from DB + Hardcoded fallback) ─────────────────

def _load_mini_apps(session: Optional[Session] = None) -> dict[str, dict]:
    """โหลด Mini Apps — DB ก่อน, hardcoded fallback สำหรับ service ที่ยังไม่ได้ migrate

    Priority:
        1. จาก DB (App model, enabled=True)
        2. จาก hardcoped dict (env fallback)
    """
    apps: dict[str, dict] = {}

    # 1. โหลดจาก Database (App model)
    if session is not None:
        try:
            db_apps = session.exec(select(App).where(App.enabled == True)).all()
            for app in db_apps:
                apps[app.slug] = {
                    "name": app.name,
                    "base_url": app.base_url or f"http://{app.slug}.local",
                    "description": app.description or "",
                    "required_role": "viewer",  # default role
                    "app_id": app.id,
                    "from_db": True,
                }
            if db_apps:
                logger.info(f"Gateway: โหลด Mini Apps จาก DB แล้ว {len(db_apps)} ตัว")
        except Exception as e:
            logger.warning(f"Gateway: ไม่สามารถโหลดจาก DB ได้ ({e}) — ใช้ hardcoded fallback")

    # 2. Hardcoded fallback (env-based) — สำหรับ service ที่ยังไม่ migrate
    hardcoded: dict[str, dict] = {
        "bookstack": {
            "name": "BookStack",
            "base_url": os.environ.get("BOOKSTACK_URL", "http://89.167.82.205:54515"),
            "description": "Documentation Wiki",
            "required_role": "viewer",
        },
    }
    for slug, info in hardcoded.items():
        if slug not in apps:  # DB มีค่ากว่า — ไม่ overwrite
            apps[slug] = {**info, "from_db": False}

    return apps


# ─── Auth Endpoints ─────────────────────────────────────────────────────────

@router.post("/auth/token")
def get_token(
    client_id: str = "default",
    role: str = "viewer",
):
    """สร้าง JWT token สำหรับ Mini App หรือ User

    ใช้งาน: POST /gateway/auth/token?client_id=my-app&role=editor
    """
    if role not in ROLE_HIERARCHY:
        raise HTTPException(status_code=400, detail=f"role '{role}' ไม่ถูกต้อง")

    token = create_access_token(
        subject=client_id,
        role=role,
        client_type="user" if role != "mini-app" else "mini-app",
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": role,
    }


@router.get("/auth/verify")
def verify_token(token_data: TokenData = Depends(require_auth)):
    """ตรวจสอบ token — คืนข้อมูล client

    ใช้งาน: GET /gateway/auth/verify
    Header: Authorization: Bearer <token>
    """
    return {
        "sub": token_data.sub,
        "role": token_data.role,
        "permissions": list(token_data.permissions),
        "client_type": token_data.client_type,
    }


# ─── Mini App Registry Endpoints ────────────────────────────────────────────

@router.get("/apps")
def list_apps(
    token_data: TokenData = Depends(require_auth),
    session: Session = Depends(get_session),
):
    """รายชื่อ Mini App ที่ Gateway รู้จัก — โหลดจาก Database + Hardcoded fallback"""
    apps = []
    for slug, info in _load_mini_apps(session).items():
        if _check_role(token_data.role, info["required_role"]):
            apps.append({
                "slug": slug,
                "name": info["name"],
                "description": info["description"],
                "url": info["base_url"],
            })
    return {"apps": apps, "total": len(apps)}


# ─── Proxy: ส่ง request ต่อไปยัง Mini App ───────────────────────────────────

@router.api_route("/proxy/{app_slug}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy_request(
    app_slug: str,
    path: str,
    request: Request,
    token_data: TokenData = Depends(require_auth),
    session: Session = Depends(get_session),
):
    """Reverse proxy: ส่ง request ต่อไปยัง Mini App backend

    ใช้งาน: GET /gateway/proxy/bookstack/api/shelves
    Header: Authorization: Bearer <token>
    """
    apps = _load_mini_apps(session)
    app_info = apps.get(app_slug)
    if not app_info:
        raise HTTPException(status_code=404, detail=f"ไม่พบ Mini App '{app_slug}'")

    # ตรวจสอบ role
    if not _check_role(token_data.role, app_info["required_role"]):
        raise HTTPException(
            status_code=403,
            detail=f"ต้องการ role {app_info['required_role']} ขึ้นไปเพื่อเข้าใช้ {app_slug}",
        )

    # สร้าง URL ปลายทาง
    target_url = f"{app_info['base_url']}/{path}"
    query_params = dict(request.query_params)
    if query_params:
        target_url += "?" + "&".join(f"{k}={v}" for k, v in query_params.items())

    # สร้าง headers (ไม่ส่ง Authorization header ต้นทางไป)
    headers = dict(request.headers)
    headers.pop("authorization", None)
    headers.pop("host", None)
    headers["X-Forwarded-For"] = request.client.host if request.client else "unknown"
    headers["X-ERP-User"] = token_data.sub
    headers["X-ERP-Role"] = token_data.role

    # อ่าน body
    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                follow_redirects=True,
            )

        # ส่ง response กลับ
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
        )
    except httpx.RequestError as e:
        logger.error(f"Gateway proxy error: {app_slug}/{path} — {e}")
        raise HTTPException(
            status_code=502,
            detail=f"ไม่สามารถเชื่อมต่อ {app_info['name']} ได้: {e}",
        )


# ─── Gateway Health ─────────────────────────────────────────────────────────

@router.get("/health")
def gateway_health():
    """สถานะ Gateway และ Mini App ทั้งหมด"""
    apps_status = {}
    for slug, info in _load_mini_apps().items():
        apps_status[slug] = {
            "name": info["name"],
            "url": info["base_url"],
            "status": "unknown",
            "from": "db" if info.get("from_db") else "hardcoded",
        }
    return {
        "gateway": "online",
        "version": "0.1.0",
        "apps": apps_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
