

"""Auth routes — forward to auth module (:8101)."""
import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from .deps import MODULE_URLS, _auth_json

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
async def auth_register(req: dict):
    return await _auth_json("POST", "/api/v1/auth/register", req=req)


@router.post("/login")
async def auth_login(req: dict):
    return await _auth_json("POST", "/api/v1/auth/login", req=req)


@router.get("/me")
async def auth_me(request: Request):
    hdrs = {"Authorization": request.headers.get("authorization", "")}
    return await _auth_json("GET", "/api/v1/auth/me", headers=hdrs)


@router.post("/biometric/register/begin")
async def auth_biometric_register_begin(req: dict, request: Request):
    hdrs = {"Authorization": request.headers.get("authorization", "")}
    return await _auth_json("POST", "/api/v1/auth/biometric/register/begin", req=req, headers=hdrs)


@router.post("/biometric/register/complete")
async def auth_biometric_register_complete(req: dict, request: Request):
    hdrs = {"Authorization": request.headers.get("authorization", "")}
    return await _auth_json("POST", "/api/v1/auth/biometric/register/complete", req=req, headers=hdrs)


@router.post("/biometric/login/begin")
async def auth_biometric_login_begin(req: dict):
    return await _auth_json("POST", "/api/v1/auth/biometric/login/begin", req=req)


@router.post("/biometric/login/complete")
async def auth_biometric_login_complete(req: dict):
    return await _auth_json("POST", "/api/v1/auth/biometric/login/complete", req=req)


@router.get("/biometric/credentials")
async def auth_biometric_list_credentials(request: Request):
    hdrs = {"Authorization": request.headers.get("authorization", "")}
    return await _auth_json("GET", "/api/v1/auth/biometric/credentials", headers=hdrs)


@router.delete("/biometric/credentials/{credential_id}")
async def auth_biometric_delete_credential(credential_id: str, request: Request):
    hdrs = {"Authorization": request.headers.get("authorization", "")}
    return await _auth_json("DELETE", f"/api/v1/auth/biometric/credentials/{credential_id}", headers=hdrs)


@router.get("/{provider}/login")
async def auth_oauth_login(provider: str):
    """OAuth login — transparently pass through the redirect from auth module."""
    base = MODULE_URLS.get("auth")
    if not base:
        raise HTTPException(status_code=400, detail="Auth module not configured")
    url = f"{base}/api/v1/auth/{provider}/login"
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        resp = await client.get(url, follow_redirects=False)
        # Pass through the redirect (307/302 to Google/LINE)
        if resp.status_code in (301, 302, 307, 308):
            location = resp.headers.get("location")
            if location:
                return RedirectResponse(url=location, status_code=resp.status_code)
        # Fallback: try to return as JSON
        if resp.status_code < 400:
            try:
                return {"ok": True, "status": resp.status_code, "data": resp.json()}
            except Exception:
                return {"ok": True, "status": resp.status_code, "data": {"text": resp.text}}
        return {"ok": False, "status": resp.status_code, "error": resp.text[:300], "data": None}


@router.get("/{provider}/callback")
async def auth_oauth_callback(provider: str, code: str = "", state: str = "", error: str = ""):
    """OAuth callback — transparently pass through redirect."""
    base = MODULE_URLS.get("auth")
    if not base:
        raise HTTPException(status_code=400, detail="Auth module not configured")
    url = f"{base}/api/v1/auth/{provider}/callback?code={code}&state={state}&error={error}"
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        resp = await client.get(url, follow_redirects=False)
        # Pass through redirect (usually redirects to frontend with token)
        if resp.status_code in (301, 302, 307, 308):
            location = resp.headers.get("location")
            if location:
                return RedirectResponse(url=location, status_code=resp.status_code)
        # Fallback: return as JSON
        if resp.status_code < 400:
            try:
                return {"ok": True, "status": resp.status_code, "data": resp.json()}
            except Exception:
                return {"ok": True, "status": resp.status_code, "data": {"text": resp.text}}
        return {"ok": False, "status": resp.status_code, "error": resp.text[:300], "data": None}

