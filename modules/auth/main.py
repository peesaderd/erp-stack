"""Auth Module — user registration, login, OAuth (Google, Facebook, Line), biometric"""
import os
import uuid
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db, init_db, Base
from shared.models import User, Session as UserSession, AuthProvider
from erp_bridge import register_module

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGO = "HS256"
JWT_EXPIRE_HOURS = 72

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
FACEBOOK_APP_ID = os.environ.get("FACEBOOK_APP_ID", "")
LINE_CHANNEL_ID = os.environ.get("LINE_CHANNEL_ID", "")

app = FastAPI(title="Auth Module", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ──────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


class LoginRequest(BaseModel):
    email: str
    password: str


class OAuthRequest(BaseModel):
    provider: str  # "google", "facebook", "line"
    token: str     # OAuth access token from client SDK
    name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None


class BiometricRequest(BaseModel):
    credential_id: str
    public_key: str
    device_name: str = ""


class AuthResponse(BaseModel):
    ok: bool
    token: Optional[str] = None
    user: Optional[dict] = None
    message: Optional[str] = None


class UserProfile(BaseModel):
    id: str
    email: str
    name: str
    avatar_url: str
    member_tier: str
    credits: float
    is_active: bool


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def _verify_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except jwt.PyJWTError:
        return None


def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "member_tier": user.member_tier,
        "credits": user.credits,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


# ──────────────────────────────────────────────
# Startup
# ──────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    await init_db()
    await register_module(
        name="auth",
        version="1.0.0",
        port=8101,
        description="User authentication (email, OAuth, biometric)",
        tables=["users", "sessions", "auth_providers"],
        permissions=["user.read", "user.write", "user.admin"],
    )


# ──────────────────────────────────────────────
# Middleware: get current user
# ──────────────────────────────────────────────

async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = auth[7:]
    payload = _verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    
    return user


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"ok": True, "module": "auth", "version": "1.0.0"}


@app.post("/api/v1/auth/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register with email + password."""
    # Check existing
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(
        email=req.email,
        name=req.name,
        password_hash=_hash_password(req.password),
        member_tier="bronze",
        credits=1.0,  # welcome credits
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    token = _create_token(user.id)
    return AuthResponse(ok=True, token=token, user=_user_to_dict(user))


@app.post("/api/v1/auth/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email + password."""
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    
    if not user or user.password_hash != _hash_password(req.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    
    token = _create_token(user.id)
    return AuthResponse(ok=True, token=token, user=_user_to_dict(user))


@app.post("/api/v1/auth/oauth", response_model=AuthResponse)
async def oauth_login(req: OAuthRequest, db: AsyncSession = Depends(get_db)):
    """Login/register via OAuth (Google, Facebook, Line)."""
    if not req.email:
        raise HTTPException(status_code=400, detail="Email required from OAuth provider")
    
    # Check if provider account exists
    result = await db.execute(
        select(AuthProvider).where(
            AuthProvider.provider == req.provider,
            AuthProvider.provider_email == req.email,
        )
    )
    provider_link = result.scalar_one_or_none()
    
    if provider_link:
        # Existing link — get user
        user_result = await db.execute(select(User).where(User.id == provider_link.user_id))
        user = user_result.scalar_one_or_none()
    else:
        # Check if email already has an account
        user_result = await db.execute(select(User).where(User.email == req.email))
        user = user_result.scalar_one_or_none()
        
        if user:
            # Link provider to existing user
            link = AuthProvider(
                user_id=user.id,
                provider=req.provider,
                provider_email=req.email,
            )
            db.add(link)
        else:
            # Create new user
            user = User(
                email=req.email,
                name=req.name or req.email.split("@")[0],
                avatar_url=req.avatar_url or "",
                member_tier="bronze",
                credits=1.0,
            )
            db.add(user)
            await db.flush()
            
            link = AuthProvider(
                user_id=user.id,
                provider=req.provider,
                provider_email=req.email,
            )
            db.add(link)
        
        await db.commit()
        await db.refresh(user)
    
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    
    token = _create_token(user.id)
    return AuthResponse(ok=True, token=token, user=_user_to_dict(user))


@app.get("/api/v1/auth/me", response_model=AuthResponse)
async def get_profile(user: User = Depends(get_current_user)):
    """Get current user profile."""
    return AuthResponse(ok=True, user=_user_to_dict(user))


@app.put("/api/v1/auth/profile")
async def update_profile(
    name: Optional[str] = None,
    avatar_url: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user profile."""
    if name:
        user.name = name
    if avatar_url:
        user.avatar_url = avatar_url
    await db.commit()
    await db.refresh(user)
    return {"ok": True, "user": _user_to_dict(user)}


# ──────────────────────────────────────────────
# Entry
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8101"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
