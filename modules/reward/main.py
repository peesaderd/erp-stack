"""
Reward / Loyalty Service — FastAPI Application
===============================================
Points-based loyalty system integrated with LINE Bot.

Features:
  - Member registration (auto via LINE)
  - Points earning (manual, order-based)
  - Points redemption (discounts, free items)
  - Tier system (Bronze → Silver → Gold → Platinum)
  - Transaction history
  - LINE Messaging API integration

Port: 8120
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ─── Path setup ──────────────────────────────────────────────────────
_this_dir = Path(__file__).parent
_modules_dir = _this_dir.parent  # modules/
if str(_modules_dir) not in sys.path:
    sys.path.insert(0, str(_modules_dir))

from reward.reward_engine import (
    get_or_create_member, get_member_profile,
    earn_points, redeem_points, get_ledger_history, calculate_order_points,
)
from reward import config
from reward.schema_client import list_active_rewards, list_members, _get_fields

# ─── Logging ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [reward] %(levelname)s %(message)s",
)
logger = logging.getLogger("reward")

# ─── FastAPI ─────────────────────────────────────────────────────────
app = FastAPI(
    title="Reward / Loyalty Service",
    description="Points-based loyalty system with LINE integration",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════
# Pydantic Models
# ═══════════════════════════════════════════════════════════════════════

class MemberRegisterRequest(BaseModel):
    line_user_id: str
    display_name: str = ""


class EarnRequest(BaseModel):
    line_user_id: str
    amount_baht: float
    reference_type: str = "pos_order"
    reference_id: str = ""
    description: str = ""


class RedeemRequest(BaseModel):
    line_user_id: str
    reward_id: str
    description: str = ""


class OrderPointsRequest(BaseModel):
    order_total: float
    line_user_id: str = ""


# ═══════════════════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    """Health check."""
    return {
        "ok": True,
        "module": "reward",
        "version": "1.0.0",
    }


# ── Member ──────────────────────────────────────────────────────────

@app.post("/api/v1/members/register")
async def register_member(req: MemberRegisterRequest):
    """Register or retrieve a member by LINE User ID."""
    member = get_or_create_member(req.line_user_id, req.display_name)
    if not member:
        raise HTTPException(status_code=500, detail="Failed to create member")

    profile = get_member_profile(req.line_user_id)
    return {"success": True, "member": profile}


@app.get("/api/v1/members/{line_user_id}")
async def get_member(line_user_id: str):
    """Get member profile."""
    profile = get_member_profile(line_user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"success": True, "member": profile}


@app.get("/api/v1/members/{line_user_id}/balance")
async def get_balance(line_user_id: str):
    """Get points balance and tier info."""
    profile = get_member_profile(line_user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"success": True, "balance": profile}


@app.get("/api/v1/members/{line_user_id}/ledger")
async def get_history(line_user_id: str, limit: int = 10):
    """Get points transaction history."""
    result = get_ledger_history(line_user_id, limit)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", ""))
    return result


# ── Points ──────────────────────────────────────────────────────────

@app.post("/api/v1/points/earn")
async def api_earn_points(req: EarnRequest):
    """Earn points from a purchase."""
    result = earn_points(
        line_user_id=req.line_user_id,
        amount_baht=req.amount_baht,
        reference_type=req.reference_type,
        reference_id=req.reference_id,
        description=req.description,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", ""))
    return result


@app.post("/api/v1/points/redeem")
async def api_redeem_points(req: RedeemRequest):
    """Redeem points for a reward."""
    result = redeem_points(
        line_user_id=req.line_user_id,
        reward_slug_or_id=req.reward_id,
        description=req.description,
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", ""))
    return result


@app.post("/api/v1/points/calculate")
async def api_calculate(req: OrderPointsRequest):
    """Calculate how many points an order would earn."""
    result = calculate_order_points(req.order_total, req.line_user_id)
    return result


# ── Rewards Catalog ─────────────────────────────────────────────────

@app.get("/api/v1/catalog")
async def list_catalog():
    """List all active redeemable rewards."""
    rewards = list_active_rewards()
    items = []
    for r in rewards:
        f = _get_fields(r)
        items.append({
            "id": r.get("id"),
            "name": f.get("name", ""),
            "points_required": f.get("points_required", 0),
            "discount_type": f.get("discount_type", "fixed"),
            "discount_value": f.get("discount_value", 0),
            "description": f.get("description", ""),
            "icon": f.get("icon", "🎁"),
        })
    return {"success": True, "items": items}


# ── Admin ───────────────────────────────────────────────────────────

@app.get("/api/v1/admin/members")
async def list_all_members(search: str = "", limit: int = 50):
    """List all members (admin)."""
    members = list_members(search, limit)
    result = []
    for m in members:
        f = _get_fields(m)
        result.append({
            "id": m.get("id"),
            "name": f.get("full_name", ""),
            "points": f.get("points", 0),
            "tier": f.get("tier", "bronze"),
            "line_user_id": f.get("line_user_id", ""),
            "is_active": f.get("is_active", True),
            "created_at": m.get("created_at", ""),
        })
    return {"success": True, "members": result, "total": len(result)}
