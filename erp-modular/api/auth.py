"""Auth/Authorization — JWT + RBAC สำหรับ ERP Modular API Gateway

โครงสร้าง:
- JWT token generation (สำหรับ Mini App)
- API Key validation (สำหรับ Machine-to-Machine)
- RBAC: Role → Permissions
- FastAPI dependency สำหรับ protect endpoints
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from pydantic import BaseModel

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# ─── JWT ────────────────────────────────────────────────────────────────────

try:
    from jose import JWTError, jwt
    HAS_JOSE = True
except ImportError:
    HAS_JOSE = False
    jwt = None  # type: ignore
    JWTError = Exception


# ─── Config ─────────────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get("ERP_JWT_SECRET", "erp-modular-dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ERP_JWT_EXPIRE_MINUTES", "60"))

security = HTTPBearer(auto_error=False)


# ─── RBAC Models ────────────────────────────────────────────────────────────

class Permission(str):
    """String constant สำหรับ permission names"""
    pass


# Permission constants
PERM_READ = "read"
PERM_WRITE = "write"
PERM_DELETE = "delete"
PERM_ADMIN = "admin"
PERM_MANAGE_PLUGINS = "manage:plugins"
PERM_MANAGE_APPS = "manage:apps"
PERM_MANAGE_USERS = "manage:users"
PERM_MANAGE_TEMPLATES = "manage:templates"
PERM_DEPLOY = "deploy"

# Role definitions
ROLES: dict[str, set[str]] = {
    "admin": {
        PERM_READ, PERM_WRITE, PERM_DELETE, PERM_ADMIN,
        PERM_MANAGE_PLUGINS, PERM_MANAGE_APPS, PERM_MANAGE_USERS,
        PERM_MANAGE_TEMPLATES, PERM_DEPLOY,
    },
    "developer": {
        PERM_READ, PERM_WRITE, PERM_DELETE,
        PERM_MANAGE_PLUGINS, PERM_MANAGE_TEMPLATES,
    },
    "editor": {
        PERM_READ, PERM_WRITE,
        PERM_MANAGE_TEMPLATES,
    },
    "viewer": {
        PERM_READ,
    },
    "mini-app": {
        PERM_READ, PERM_WRITE,
    },
}


# ─── Token Data ─────────────────────────────────────────────────────────────

class TokenData(BaseModel):
    """ข้อมูลใน JWT token"""
    sub: str  # client_id หรือ username
    role: str = "viewer"
    permissions: set[str] = set()
    scopes: List[str] = []
    client_type: str = "user"  # "user" | "mini-app" | "api-key"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = ACCESS_TOKEN_EXPIRE_MINUTES
    role: str = "viewer"


# ─── JWT Functions ──────────────────────────────────────────────────────────

def create_access_token(
    subject: str,
    role: str = "viewer",
    client_type: str = "user",
    scopes: Optional[List[str]] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """สร้าง JWT token"""
    if not HAS_JOSE:
        raise RuntimeError("python-jose ไม่ได้ติดตั้ง กรุณารัน: pip install python-jose[cryptography]")

    permissions = ROLES.get(role, set())
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

    payload = {
        "sub": subject,
        "role": role,
        "permissions": list(permissions),
        "scopes": scopes or [],
        "client_type": client_type,
        "iat": datetime.now(timezone.utc),
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenData:
    """ถอดรหัส JWT token → TokenData"""
    if not HAS_JOSE:
        raise RuntimeError("python-jose ไม่ได้ติดตั้ง กรุณารัน: pip install python-jose[cryptography]")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenData(
            sub=payload.get("sub", ""),
            role=payload.get("role", "viewer"),
            permissions=set(payload.get("permissions", [])),
            scopes=payload.get("scopes", []),
            client_type=payload.get("client_type", "user"),
        )
    except JWTError:
        raise HTTPException(status_code=401, detail="Token ไม่ถูกต้องหรือหมดอายุ")


# ─── FastAPI Dependencies ───────────────────────────────────────────────────

def get_token_data(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> Optional[TokenData]:
    """FastAPI dependency: ดึง TokenData จาก Authorization header (optional)"""
    if credentials is None:
        return None
    return decode_token(credentials.credentials)


def require_auth(
    token_data: Optional[TokenData] = Depends(get_token_data),
) -> TokenData:
    """FastAPI dependency: บังคับต้องมี token"""
    if token_data is None:
        raise HTTPException(
            status_code=401,
            detail="ไม่พบ Authorization header กรุณาส่ง Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token_data


def require_permission(permission: str):
    """FastAPI dependency factory: ตรวจสอบ permission

     ใช้งาน:
        @router.get("/admin")
        def admin_endpoint(token: TokenData = Depends(require_permission("admin"))):
            ...
    """
    def _check(token_data: TokenData = Depends(require_auth)):
        if permission not in token_data.permissions:
            raise HTTPException(
                status_code=403,
                detail=f"ไม่มีสิทธิ์ {permission} — ต้องมี role ที่สูงขึ้น",
            )
        return token_data
    return _check


def require_role(role: str):
    """FastAPI dependency factory: ตรวจสอบ role ขั้นต่ำ

    ใช้งาน:
        @router.get("/admin")
        def admin_endpoint(token: TokenData = Depends(require_role("admin"))):
            ...
    """
    role_hierarchy = ["viewer", "editor", "developer", "mini-app", "admin"]
    min_level = role_hierarchy.index(role) if role in role_hierarchy else 99

    def _check(token_data: TokenData = Depends(require_auth)):
        user_level = role_hierarchy.index(token_data.role) if token_data.role in role_hierarchy else -1
        if user_level < min_level:
            raise HTTPException(
                status_code=403,
                detail=f"ต้องการ role {role} ขึ้นไป — ปัจจุบันคือ {token_data.role}",
            )
        return token_data
    return _check


# ─── API Key Auth ───────────────────────────────────────────────────────────

def validate_api_key(api_key: str) -> Optional[TokenData]:
    """ตรวจสอบ API Key — ในระบบจริงควรตรวจจาก DB"""
    # TODO: ตรวจสอบ API Key จาก App model ใน database
    # ปัจจุบันใช้ simple check: key ต้องมีความยาว >= 16
    if len(api_key) >= 16:
        return TokenData(
            sub=api_key[:8],
            role="mini-app",
            permissions=ROLES.get("mini-app", set()),
            client_type="api-key",
        )
    return None
