"""Auth Module — user registration, login, OAuth (Google, Facebook, Line), biometric"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'), override=True)

import uuid
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

import jwt
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
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
                provider_user_id=req.email,
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
                provider_user_id=req.email,
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
# WebAuthn / Biometric (Passkeys)
# ──────────────────────────────────────────────
"""
WebAuthn (Passkeys) — ใช้ Face ID / Touch ID / Fingerprint เข้าสู่ระบบ
ทำงานได้ทั้ง iOS Safari และ Android Chrome

Flow:
  Register: login → register/begin → browser creates credential → register/complete
  Login:    login/begin → browser gets assertion → login/complete → JWT
"""

import base64
import json
import time

from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
    COSEAlgorithmIdentifier,
    PublicKeyCredentialType,
    PublicKeyCredentialHint,
)

from shared.models import WebAuthnCredential as WebAuthnCredentialModel

# ── RP (Relying Party) info ──
RP_ID = os.environ.get("WEBAUTHN_RP_ID", "m2igen.com")
RP_NAME = "M2I App Store"
ORIGIN = os.environ.get("WEBAUTHN_ORIGIN", "https://m2igen.com")

# ── In-memory challenge store (short-lived) ──
# { state_token: { "challenge": bytes, "user_id": str, "expires_at": float } }
_challenge_store: dict = {}

def _clean_expired_challenges():
    now = time.time()
    expired = [k for k, v in _challenge_store.items() if v.get("expires_at", 0) < now]
    for k in expired:
        _challenge_store.pop(k, None)


def _make_state_token() -> str:
    return secrets.token_urlsafe(32)


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _base64url_decode(s: str) -> bytes:
    # Add padding back
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


# ── DB helpers ──

async def _get_user_credentials(user_id: str, db: AsyncSession) -> list:
    result = await db.execute(
        select(WebAuthnCredentialModel).where(WebAuthnCredentialModel.user_id == user_id)
    )
    return result.scalars().all()


def _credential_to_dict(c: WebAuthnCredentialModel) -> dict:
    return {
        "id": c.id,
        "credential_id": c.credential_id,
        "device_name": c.device_name,
        "transports": c.transports or [],
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "last_used_at": c.last_used_at.isoformat() if c.last_used_at else None,
    }


# ──────────────────────────────────────────────
# 1. REGISTER — เริ่มต้น (ต้อง login ก่อน)
# ──────────────────────────────────────────────

@app.post("/api/v1/auth/biometric/register/begin")
async def biometric_register_begin(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """สร้าง challenge สำหรับ register device ใหม่"""
    _clean_expired_challenges()

    # Get existing credentials to exclude them
    existing = await _get_user_credentials(user.id, db)
    exclude_creds = []
    for c in existing:
        cid_bytes = _base64url_decode(c.credential_id)
        exclude_creds.append(
            PublicKeyCredentialDescriptor(id=cid_bytes, type=PublicKeyCredentialType.PUBLIC_KEY)
        )

    challenge = os.urandom(32)

    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_name=user.email,
        user_id=user.id.encode(),
        user_display_name=user.name,
        challenge=challenge,
        timeout=60000,  # 60s
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=exclude_creds if exclude_creds else None,
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.ECDSA_SHA_256,       # -7  P-256
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,  # -257 RSA
        ],
    )

    # Store challenge
    state_token = _make_state_token()
    _challenge_store[state_token] = {
        "challenge": challenge,
        "user_id": user.id,
        "expires_at": time.time() + 120,  # 2 min
    }

    # Build the PublicKeyCredentialCreationOptions dict in camelCase for browser
    exclude_creds_list = []
    if options.exclude_credentials:
        for ec in options.exclude_credentials:
            exclude_creds_list.append({
                "id": _base64url_encode(ec.id),
                "type": "public-key",
            })

    opt_dict = {
        "rp": {"id": RP_ID, "name": RP_NAME},
        "user": {
            "id": _base64url_encode(user.id.encode()),
            "name": user.email,
            "displayName": user.name,
        },
        "challenge": _base64url_encode(challenge),
        "pubKeyCredParams": [
            {"type": "public-key", "alg": p.alg.value}
            for p in (options.pub_key_cred_params or [])
        ] if options.pub_key_cred_params else [
            {"type": "public-key", "alg": -7},
            {"type": "public-key", "alg": -257},
        ],
        "timeout": options.timeout or 60000,
        "excludeCredentials": exclude_creds_list,
        "authenticatorSelection": {
            "userVerification": options.authenticator_selection.user_verification.value
            if options.authenticator_selection and options.authenticator_selection.user_verification
            else "required",
        },
        "attestation": options.attestation.value if options.attestation else "none",
    }

    return {
        "ok": True,
        "state_token": state_token,
        "options": opt_dict,
    }


# ──────────────────────────────────────────────
# 2. REGISTER — ยืนยัน
# ──────────────────────────────────────────────

class BiometricRegisterCompleteRequest(BaseModel):
    state_token: str
    credential: dict  # The PublicKeyCredential from browser
    device_name: str = ""


@app.post("/api/v1/auth/biometric/register/complete")
async def biometric_register_complete(
    req: BiometricRegisterCompleteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """ตรวจสอบและบันทึก credential"""
    _clean_expired_challenges()

    stored = _challenge_store.pop(req.state_token, None)
    if not stored:
        raise HTTPException(status_code=400, detail="Challenge expired or invalid. Please try again.")
    if stored["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="State token does not match current user")

    expected_challenge = stored["challenge"]

    try:
        verification = verify_registration_response(
            credential=req.credential,
            expected_challenge=expected_challenge,
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
            require_user_verification=True,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Verification failed: {str(e)}")

    # Store credential
    credential_id_b64 = _base64url_encode(verification.credential_id)
    public_key_b64 = _base64url_encode(verification.credential_public_key)
    transports = [t.value for t in (verification.transports or [])]

    # Check for duplicate
    existing = await db.execute(
        select(WebAuthnCredentialModel).where(
            WebAuthnCredentialModel.credential_id == credential_id_b64
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Credential already registered")

    cred = WebAuthnCredentialModel(
        user_id=user.id,
        credential_id=credential_id_b64,
        public_key=public_key_b64,
        sign_count=verification.sign_count,
        device_name=req.device_name or "อุปกรณ์ของฉัน",
        transports=transports,
    )
    db.add(cred)
    await db.commit()
    await db.refresh(cred)

    return {
        "ok": True,
        "credential": _credential_to_dict(cred),
        "message": "✅ ลงทะเบียน biometric สำเร็จ",
    }


# ──────────────────────────────────────────────
# 3. LOGIN — เริ่มต้น (ไม่ต้อง login)
# ──────────────────────────────────────────────

class BiometricLoginBeginRequest(BaseModel):
    email: Optional[str] = None  # ถ้ารู้ email จะส่งมา filter credential


@app.post("/api/v1/auth/biometric/login/begin")
async def biometric_login_begin(
    req: BiometricLoginBeginRequest,
    db: AsyncSession = Depends(get_db),
):
    """สร้าง challenge สำหรับ login ด้วย biometric"""
    _clean_expired_challenges()

    # Find user credentials
    user_id = None
    if req.email:
        result = await db.execute(select(User).where(User.email == req.email))
        user = result.scalar_one_or_none()
        if user:
            user_id = user.id

    allow_creds = []
    if user_id:
        existing = await _get_user_credentials(user_id, db)
        for c in existing:
            cid_bytes = _base64url_decode(c.credential_id)
            allow_creds.append(
                PublicKeyCredentialDescriptor(
                    id=cid_bytes,
                    type=PublicKeyCredentialType.PUBLIC_KEY,
                    transports=c.transports or [],
                )
            )

    challenge = os.urandom(32)

    options = generate_authentication_options(
        rp_id=RP_ID,
        challenge=challenge,
        timeout=60000,
        allow_credentials=allow_creds if allow_creds else None,
        user_verification=UserVerificationRequirement.REQUIRED,
    )

    state_token = _make_state_token()
    _challenge_store[state_token] = {
        "challenge": challenge,
        "preferred_user_id": user_id,  # เพื่อ map กลับตอน complete
        "expires_at": time.time() + 120,
    }

    # Build PublicKeyCredentialRequestOptions in camelCase
    allow_creds_list = []
    if options.allow_credentials:
        for ac in options.allow_credentials:
            allow_creds_list.append({
                "id": _base64url_encode(ac.id),
                "type": "public-key",
                "transports": [t.value for t in ac.transports] if ac.transports else [],
            })

    opt_dict = {
        "challenge": _base64url_encode(challenge),
        "timeout": options.timeout or 60000,
        "rpId": RP_ID,
        "allowCredentials": allow_creds_list,
        "userVerification": options.user_verification.value
        if options.user_verification else "required",
    }

    return {
        "ok": True,
        "state_token": state_token,
        "options": opt_dict,
    }


# ──────────────────────────────────────────────
# 4. LOGIN — ยืนยัน
# ──────────────────────────────────────────────

class BiometricLoginCompleteRequest(BaseModel):
    state_token: str
    credential: dict  # The PublicKeyCredential from browser


@app.post("/api/v1/auth/biometric/login/complete")
async def biometric_login_complete(
    req: BiometricLoginCompleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """ตรวจสอบ assertion และออก JWT token"""
    _clean_expired_challenges()

    stored = _challenge_store.pop(req.state_token, None)
    if not stored:
        raise HTTPException(status_code=400, detail="Challenge expired or invalid. Please try again.")

    expected_challenge = stored["challenge"]

    # Get credential_id from response
    raw_id = req.credential.get("rawId") or req.credential.get("id", "")
    if not raw_id:
        raise HTTPException(status_code=400, detail="Missing credential ID")

    credential_id_b64 = raw_id if isinstance(raw_id, str) else str(raw_id)

    # Look up stored credential
    result = await db.execute(
        select(WebAuthnCredentialModel).where(
            WebAuthnCredentialModel.credential_id == credential_id_b64
        )
    )
    stored_cred = result.scalar_one_or_none()
    if not stored_cred:
        raise HTTPException(status_code=404, detail="Credential not found. Please register first.")

    # Get user
    user_result = await db.execute(select(User).where(User.id == stored_cred.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled or not found")

    try:
        verification = verify_authentication_response(
            credential=req.credential,
            expected_challenge=expected_challenge,
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
            credential_public_key=_base64url_decode(stored_cred.public_key),
            credential_current_sign_count=stored_cred.sign_count,
            require_user_verification=True,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Verification failed: {str(e)}")

    # Update sign count + last used
    stored_cred.sign_count = verification.new_sign_count
    stored_cred.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    # Issue JWT
    token = _create_token(user.id)

    return {
        "ok": True,
        "token": token,
        "user": _user_to_dict(user),
        "message": "✅ Biometric login สำเร็จ",
    }


# ──────────────────────────────────────────────
# 5. LIST — แสดง credentials ของ user
# ──────────────────────────────────────────────

@app.get("/api/v1/auth/biometric/credentials")
async def biometric_list_credentials(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await _get_user_credentials(user.id, db)
    return {
        "ok": True,
        "credentials": [_credential_to_dict(c) for c in existing],
    }


# ──────────────────────────────────────────────
# 6. DELETE — ลบ credential
# ──────────────────────────────────────────────

@app.delete("/api/v1/auth/biometric/credentials/{credential_id}")
async def biometric_delete_credential(
    credential_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WebAuthnCredentialModel).where(
            WebAuthnCredentialModel.id == credential_id,
            WebAuthnCredentialModel.user_id == user.id,
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")

    await db.delete(cred)
    await db.commit()
    return {"ok": True, "message": "ลบ credential สำเร็จ"}


# ──────────────────────────────────────────────
# OAuth Routes (Google, Facebook, Line Redirect Flow)
# ──────────────────────────────────────────────

@app.get("/api/v1/auth/google/login")
async def google_login():
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID")
    redirect_uri = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI") or os.environ.get("GOOGLE_REDIRECT_URI")
    if not client_id or not redirect_uri:
        raise HTTPException(status_code=400, detail="Google OAuth not configured on server")
    
    from urllib.parse import urlencode
    import secrets
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": secrets.token_urlsafe(16),
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url)


@app.get("/api/v1/auth/google/callback")
async def google_callback(code: str, state: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID") or os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET") or os.environ.get("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI") or os.environ.get("GOOGLE_REDIRECT_URI")
    
    if not all([client_id, client_secret, redirect_uri]):
        raise HTTPException(status_code=500, detail="Google OAuth credentials missing")
    
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
                "grant_type": "authorization_code",
            }
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Failed to exchange Google code: {token_resp.text}")
        
        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        
        user_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get Google user info")
        
        user_info = user_resp.json()
        email = user_info.get("email")
        name = user_info.get("name", email.split("@")[0] if email else "")
        avatar_url = user_info.get("picture", "")
        
        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Google")
        
        result = await db.execute(
            select(AuthProvider).where(
                AuthProvider.provider == "google",
                AuthProvider.provider_email == email,
            )
        )
        provider_link = result.scalar_one_or_none()
        
        if provider_link:
            user_result = await db.execute(select(User).where(User.id == provider_link.user_id))
            user = user_result.scalar_one_or_none()
            # Update name and avatar from provider
            if user:
                if name: user.name = name
                if avatar_url: user.avatar_url = avatar_url
        else:
            user_result = await db.execute(select(User).where(User.email == email))
            user = user_result.scalar_one_or_none()
            
            if user:
                # Existing user: add provider link + update name/avatar
                if name: user.name = name
                if avatar_url: user.avatar_url = avatar_url
                link = AuthProvider(
                    user_id=user.id,
                    provider="google",
                    provider_email=email,
                    provider_user_id=user_info.get("sub") or email,
                )
                db.add(link)
            else:
                user = User(
                    email=email,
                    name=name,
                    avatar_url=avatar_url,
                    member_tier="bronze",
                    credits=1.0,
                )
                db.add(user)
                await db.flush()
                
                link = AuthProvider(
                    user_id=user.id,
                    provider="google",
                    provider_email=email,
                    provider_user_id=user_info.get("sub") or email,
                )
                db.add(link)
            
            await db.commit()
            await db.refresh(user)
            
        if not user or not user.is_active:
            raise HTTPException(status_code=403, detail="Account is disabled")
        
        jwt_token = _create_token(user.id)
        return RedirectResponse(f"https://m2igen.com/?token={jwt_token}")


@app.get("/api/v1/auth/facebook/login")
async def facebook_login():
    app_id = os.environ.get("FACEBOOK_APP_ID")
    redirect_uri = os.environ.get("FACEBOOK_REDIRECT_URI") or "https://openhands.m2igen.com/api/auth/facebook/callback"
    if not app_id:
        raise HTTPException(status_code=400, detail="Facebook OAuth not configured on server")
    
    from urllib.parse import urlencode
    import secrets
    params = {
        "client_id": app_id,
        "redirect_uri": redirect_uri,
        "state": secrets.token_urlsafe(16),
        "scope": "email,public_profile",
    }
    url = f"https://www.facebook.com/v18.0/dialog/oauth?{urlencode(params)}"
    return RedirectResponse(url)


@app.get("/api/v1/auth/facebook/callback")
async def facebook_callback(code: str, state: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    app_id = os.environ.get("FACEBOOK_APP_ID")
    app_secret = os.environ.get("FACEBOOK_APP_SECRET")
    redirect_uri = os.environ.get("FACEBOOK_REDIRECT_URI") or "https://openhands.m2igen.com/api/auth/facebook/callback"
    
    if not all([app_id, app_secret]):
        raise HTTPException(status_code=500, detail="Facebook OAuth credentials missing")
    
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.get(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            params={
                "client_id": app_id,
                "redirect_uri": redirect_uri,
                "client_secret": app_secret,
                "code": code,
            }
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Failed to exchange Facebook code: {token_resp.text}")
        
        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        
        user_resp = await client.get(
            "https://graph.facebook.com/me",
            params={
                "fields": "id,name,email,picture.type(large)",
                "access_token": access_token
            }
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get Facebook user info")
        
        user_info = user_resp.json()
        email = user_info.get("email") or f"{user_info.get('id')}@facebook.com"
        name = user_info.get("name", email.split("@")[0])
        avatar_url = user_info.get("picture", {}).get("data", {}).get("url", "")
        
        result = await db.execute(
            select(AuthProvider).where(
                AuthProvider.provider == "facebook",
                AuthProvider.provider_email == email,
            )
        )
        provider_link = result.scalar_one_or_none()
        
        if provider_link:
            user_result = await db.execute(select(User).where(User.id == provider_link.user_id))
            user = user_result.scalar_one_or_none()
            if user:
                if name: user.name = name
                if avatar_url: user.avatar_url = avatar_url
        else:
            user_result = await db.execute(select(User).where(User.email == email))
            user = user_result.scalar_one_or_none()
            
            if user:
                if name: user.name = name
                if avatar_url: user.avatar_url = avatar_url
                link = AuthProvider(
                    user_id=user.id,
                    provider="facebook",
                    provider_email=email,
                    provider_user_id=user_info.get("id") or email,
                )
                db.add(link)
            else:
                user = User(
                    email=email,
                    name=name,
                    avatar_url=avatar_url,
                    member_tier="bronze",
                    credits=1.0,
                )
                db.add(user)
                await db.flush()
                
                link = AuthProvider(
                    user_id=user.id,
                    provider="facebook",
                    provider_email=email,
                    provider_user_id=user_info.get("id") or email,
                )
                db.add(link)
            
            await db.commit()
            await db.refresh(user)
            
        if not user or not user.is_active:
            raise HTTPException(status_code=403, detail="Account is disabled")
        
        jwt_token = _create_token(user.id)
        return RedirectResponse(f"https://m2igen.com/?token={jwt_token}")


@app.get("/api/v1/auth/line/login")
async def line_login():
    channel_id = os.environ.get("LINE_CHANNEL_ID")
    redirect_uri = os.environ.get("LINE_REDIRECT_URI") or "https://m2igen.com/api/auth/line/callback"
    if not channel_id:
        raise HTTPException(status_code=400, detail="LINE login not configured on server")
    
    from urllib.parse import urlencode
    import secrets
    params = {
        "response_type": "code",
        "client_id": channel_id,
        "redirect_uri": redirect_uri,
        "state": secrets.token_urlsafe(16),
        "scope": "profile openid email",
    }
    url = f"https://access.line.me/oauth2/v2.1/authorize?{urlencode(params)}"
    return RedirectResponse(url)


@app.get("/api/v1/auth/line/callback")
async def line_callback(code: str, state: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    channel_id = os.environ.get("LINE_CHANNEL_ID")
    channel_secret = os.environ.get("LINE_CHANNEL_SECRET")
    redirect_uri = os.environ.get("LINE_REDIRECT_URI") or "https://m2igen.com/api/auth/line/callback"
    
    if not all([channel_id, channel_secret]):
        raise HTTPException(status_code=500, detail="LINE credentials missing")
    
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(
            "https://api.line.me/oauth2/v2.1/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": channel_id,
                "client_secret": channel_secret,
            }
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Failed to exchange LINE code: {token_resp.text}")
        
        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        
        user_resp = await client.get(
            "https://api.line.me/v2/profile",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get LINE profile")
        
        user_info = user_resp.json()
        line_user_id = user_info.get("userId")
        name = user_info.get("displayName", "")
        avatar_url = user_info.get("pictureUrl", "")
        email = f"{line_user_id}@line.me"
        
        result = await db.execute(
            select(AuthProvider).where(
                AuthProvider.provider == "line",
                AuthProvider.provider_email == email,
            )
        )
        provider_link = result.scalar_one_or_none()
        
        if provider_link:
            user_result = await db.execute(select(User).where(User.id == provider_link.user_id))
            user = user_result.scalar_one_or_none()
            if user:
                if name: user.name = name
                if avatar_url: user.avatar_url = avatar_url
        else:
            user_result = await db.execute(select(User).where(User.email == email))
            user = user_result.scalar_one_or_none()
            
            if user:
                if name: user.name = name
                if avatar_url: user.avatar_url = avatar_url
                link = AuthProvider(
                    user_id=user.id,
                    provider="line",
                    provider_email=email,
                    provider_user_id=line_user_id or email,
                )
                db.add(link)
            else:
                user = User(
                    email=email,
                    name=name,
                    avatar_url=avatar_url,
                    member_tier="bronze",
                    credits=1.0,
                )
                db.add(user)
                await db.flush()
                
                link = AuthProvider(
                    user_id=user.id,
                    provider="line",
                    provider_email=email,
                    provider_user_id=line_user_id or email,
                )
                db.add(link)
            
            await db.commit()
            await db.refresh(user)
            
        if not user or not user.is_active:
            raise HTTPException(status_code=403, detail="Account is disabled")
        
        jwt_token = _create_token(user.id)
        return RedirectResponse(f"https://m2igen.com/?token={jwt_token}")




if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8101"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
