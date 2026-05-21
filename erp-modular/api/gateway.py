"""API Gateway — Reverse Proxy + Routing + Auth สำหรับ ERP Modular

หน้าที่:
1. เป็นทางเข้าออกเดียวสำหรับ Mini App ทั้งหมด
2. ตรวจสอบ JWT/API Key ทุก request
3. Route ไปยัง backend ที่ถูกต้อง (ERP API หรือ Mini App)
4. เก็บ audit log

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

from .auth import (
    TokenData, require_auth, require_permission,
    create_access_token, decode_token, PERM_ADMIN,
)
from .rate_limit import get_rate_limiter

logger = logging.getLogger("erp.gateway")

router = APIRouter(prefix="/gateway")

# ─── Mini App Registry ──────────────────────────────────────────────────────

# TODO: โหลดจาก database (App model) แทน hardcode
MINI_APPS: dict[str, dict] = {
    "plane": {
        "name": "Plane",
        "base_url": os.environ.get("PLANE_URL", "http://localhost:54512"),
        "description": "Project Management",
        "required_role": "editor",
    },
    "planka": {
        "name": "Planka",
        "base_url": os.environ.get("PLANKA_URL", "http://localhost:54513"),
        "description": "Kanban Board",
        "required_role": "editor",
    },
    "bookstack": {
        "name": "BookStack",
        "base_url": os.environ.get("BOOKSTACK_URL", "http://localhost:54515"),
        "description": "Documentation Wiki",
        "required_role": "viewer",
    },
    "siyuan": {
        "name": "Siyuan",
        "base_url": os.environ.get("SIYUAN_URL", "http://localhost:54511"),
        "description": "Knowledge Base",
        "required_role": "viewer",
    },
    "openobserve": {
        "name": "OpenObserve",
        "base_url": os.environ.get("OPENOBSERVE_URL", "http://localhost:54514"),
        "description": "Logging & Metrics",
        "required_role": "admin",
    },
}


# ─── Auth Endpoints ─────────────────────────────────────────────────────────

@router.post("/auth/token")
def get_token(
    client_id: str = "default",
    role: str = "viewer",
):
    """สร้าง JWT token สำหรับ Mini App หรือ User

    ใช้งาน: POST /gateway/auth/token?client_id=my-app&role=editor
    """
    if role not in ("viewer", "editor", "developer", "admin", "mini-app"):
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
def list_apps(token_data: TokenData = Depends(require_auth)):
    """รายชื่อ Mini App ที่ Gateway รู้จัก"""
    apps = []
    for slug, info in MINI_APPS.items():
        # กรองตาม role
        role_hierarchy = ["viewer", "editor", "developer", "mini-app", "admin"]
        user_level = role_hierarchy.index(token_data.role) if token_data.role in role_hierarchy else -1
        req_level = role_hierarchy.index(info["required_role"]) if info["required_role"] in role_hierarchy else 99
        if user_level >= req_level:
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
):
    """Reverse proxy: ส่ง request ต่อไปยัง Mini App backend

    ใช้งาน: GET /gateway/proxy/plane/api/projects
    Header: Authorization: Bearer <token>
    """
    # ตรวจสอบว่า Mini App มีอยู่
    app_info = MINI_APPS.get(app_slug)
    if not app_info:
        raise HTTPException(status_code=404, detail=f"ไม่พบ Mini App '{app_slug}'")

    # ตรวจสอบ role
    role_hierarchy = ["viewer", "editor", "developer", "mini-app", "admin"]
    user_level = role_hierarchy.index(token_data.role) if token_data.role in role_hierarchy else -1
    req_level = role_hierarchy.index(app_info["required_role"]) if app_info["required_role"] in role_hierarchy else 99
    if user_level < req_level:
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
    for slug, info in MINI_APPS.items():
        apps_status[slug] = {
            "name": info["name"],
            "url": info["base_url"],
            "status": "unknown",
        }
    return {
        "gateway": "online",
        "version": "0.1.0",
        "apps": apps_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
