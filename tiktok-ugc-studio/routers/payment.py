"""Payment & profile proxy routes."""
from fastapi import APIRouter

from .deps import _proxy

router = APIRouter(tags=["payment"])
@router.post("/payment/create-checkout")
async def payment_create_checkout(req: dict):
    return await _proxy("POST", "payment", "/api/v1/checkout", req)

@router.post("/payment/create-qr")
async def payment_create_qr(req: dict):
    return await _proxy("POST", "payment", "/api/v1/qr", req)

@router.get("/payment/plans")
async def payment_plans():
    return await _proxy("GET", "payment", "/api/v1/plans")

@router.get("/payment/health")
async def payment_health():
    return await _proxy("GET", "payment", "/health")

@router.get("/profile/health")
async def profile_health():
    return await _proxy("GET", "profile", "/health")

@router.post("/profile/register")
async def profile_register(req: dict):
    return await _proxy("POST", "profile", "/api/v1/profiles", req)

@router.get("/profile/tier/{user_id}")
async def profile_tier(user_id: str):
    return await _proxy("GET", "profile", f"/api/v1/profiles/{user_id}/tier")

# ─── Products List ───────────────────────────────────────────────────────
