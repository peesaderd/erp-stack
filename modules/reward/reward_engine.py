"""
Reward Engine — Business Logic

Points earning, spending, tier calculation, bonuses.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from reward.config import TIERS, DEFAULT_EARN_RATE, BONUS_ON_REGISTER, BONUS_ON_BIRTHDAY, MAX_EARN_PER_DAY
from reward.schema_client import (
    find_member_by_line, get_member, create_member, update_member,
    create_ledger_entry, get_ledger_for_member,
    list_active_rewards, get_reward,
    _get_fields,
)

logger = logging.getLogger("reward.engine")


def _calculate_tier(total_points: int) -> str:
    """Determine tier based on lifetime earned points."""
    sorted_tiers = sorted(TIERS.items(), key=lambda t: t[1]["min_points"], reverse=True)
    for slug, cfg in sorted_tiers:
        if total_points >= cfg["min_points"]:
            return slug
    return "bronze"


def _get_tier_multiplier(tier: str) -> float:
    """Get points multiplier for a tier level."""
    return TIERS.get(tier, TIERS["bronze"])["multiplier"]


# ── Member Management ─────────────────────────────────────────────

def get_or_create_member(line_user_id: str, display_name: str = "") -> Optional[dict]:
    """Find existing member by LINE ID, or create a new one."""
    existing = find_member_by_line(line_user_id)
    if existing:
        return existing

    # Create new member
    fields = {
        "full_name": display_name or f"LINE-{line_user_id[:8]}",
        "line_user_id": line_user_id,
        "points": BONUS_ON_REGISTER,
        "tier": "bronze",
        "is_active": True,
    }
    member = create_member(fields)
    if not member:
        logger.error(f"Failed to create member for LINE {line_user_id}")
        return None

    member_id = member.get("id", "")
    # Record sign-up bonus
    create_ledger_entry({
        "member_id": member_id,
        "type": "bonus",
        "points": BONUS_ON_REGISTER,
        "balance_after": BONUS_ON_REGISTER,
        "reference_type": "manual",
        "description": "🎉 สมัครสมาชิกใหม่ — รับแต้มต้อนรับ",
    })

    logger.info(f"Created member {member_id} for LINE {line_user_id} with {BONUS_ON_REGISTER} bonus points")
    return member


def get_member_profile(line_user_id: str) -> Optional[dict]:
    """Get full member profile with tier info and balance."""
    member = find_member_by_line(line_user_id)
    if not member:
        return None

    fields = _get_fields(member)
    points = fields.get("points", 0)
    tier = fields.get("tier", "bronze")
    tier_cfg = TIERS.get(tier, TIERS["bronze"])

    return {
        "member_id": member.get("id"),
        "name": fields.get("full_name", ""),
        "points": points,
        "tier": tier,
        "tier_label": tier_cfg["label"],
        "tier_color": tier_cfg["color"],
        "multiplier": _get_tier_multiplier(tier),
        "next_tier": _get_next_tier(tier, points),
        "is_active": fields.get("is_active", True),
    }


def _get_next_tier(current_tier: str, current_points: int) -> Optional[dict]:
    """Get next tier upgrade info."""
    sorted_tiers = sorted(TIERS.items(), key=lambda t: t[1]["min_points"])
    found = False
    for slug, cfg in sorted_tiers:
        if found:
            return {
                "tier": slug,
                "label": cfg["label"],
                "points_needed": max(0, cfg["min_points"] - current_points),
            }
        if slug == current_tier:
            found = True
    return None


# ── Points Management ─────────────────────────────────────────────

def earn_points(
    line_user_id: str,
    amount_baht: float,
    reference_type: str = "pos_order",
    reference_id: str = "",
    description: str = "",
) -> dict:
    """
    Earn points based on spending amount.

    Args:
        line_user_id: LINE User ID
        amount_baht: Total amount spent (in baht)
        reference_type: Source of earn (pos_order, booking, manual, promotion)
        reference_id: Order/Reference ID
        description: Optional description

    Returns:
        dict with success status and details
    """
    member = find_member_by_line(line_user_id)
    if not member:
        return {"success": False, "error": "Member not found"}

    member_id = member.get("id")
    fields = _get_fields(member)
    current_points = fields.get("points", 0)
    current_tier = fields.get("tier", "bronze")

    # Calculate points
    multiplier = _get_tier_multiplier(current_tier)
    base_points = int(amount_baht / DEFAULT_EARN_RATE)
    earned = max(1, int(base_points * multiplier))

    # Update balance
    new_balance = current_points + earned
    total_earned = fields.get("total_earned", 0) + earned

    # Determine new tier
    new_tier = _calculate_tier(total_earned)

    # Update member
    update_fields = {
        "points": new_balance,
        "tier": new_tier,
    }
    update_member(member_id, update_fields)

    # Record ledger entry
    ledeger_desc = description or f"💰 รับแต้มจากการซื้อ ({amount_baht:.0f} บาท)"
    create_ledger_entry({
        "member_id": member_id,
        "type": "earn",
        "points": earned,
        "balance_after": new_balance,
        "reference_type": reference_type,
        "reference_id": reference_id,
        "description": ledeger_desc,
    })

    tier_upgraded = new_tier != current_tier

    return {
        "success": True,
        "points_earned": earned,
        "points_before": current_points,
        "points_balance": new_balance,
        "tier": new_tier,
        "tier_upgraded": tier_upgraded,
        "multiplier": multiplier,
        "amount_baht": amount_baht,
    }


def redeem_points(
    line_user_id: str,
    reward_slug_or_id: str,
    description: str = "",
) -> dict:
    """
    Redeem points for a reward.

    Args:
        line_user_id: LINE User ID
        reward_slug_or_id: Reward catalog item ID
        description: Optional description

    Returns:
        dict with success status and details
    """
    member = find_member_by_line(line_user_id)
    if not member:
        return {"success": False, "error": "ไม่พบข้อมูลสมาชิก"}

    member_id = member.get("id")
    fields = _get_fields(member)
    current_points = fields.get("points", 0)

    # Find reward
    reward = get_reward(reward_slug_or_id)
    if not reward:
        # Try searching by name/slug
        rewards = list_active_rewards()
        for r in rewards:
            r_fields = _get_fields(r)
            if r_fields.get("name", "").lower() == reward_slug_or_id.lower():
                reward = r
                break

    if not reward:
        return {"success": False, "error": "ไม่พบรางวัลนี้"}

    reward_fields = _get_fields(reward)
    points_required = reward_fields.get("points_required", 0)
    reward_name = reward_fields.get("name", "รางวัล")
    discount_type = reward_fields.get("discount_type", "fixed")
    discount_value = reward_fields.get("discount_value", 0)

    # Check balance
    if current_points < points_required:
        return {
            "success": False,
            "error": f"แต้มไม่พอ ต้องการ {points_required} แต้ม คุณมี {current_points} แต้ม",
            "points_required": points_required,
            "points_balance": current_points,
        }

    # Process redemption
    new_balance = current_points - points_required

    update_member(member_id, {"points": new_balance})

    redemption_desc = description or f"🎁 แลก {reward_name} ({points_required} แต้ม)"
    create_ledger_entry({
        "member_id": member_id,
        "type": "redeem",
        "points": -points_required,
        "balance_after": new_balance,
        "reference_type": "manual",
        "reference_id": "",
        "description": redemption_desc,
    })

    # Build reward info
    if discount_type == "percent":
        reward_info = f"ส่วนลด {discount_value}%"
    elif discount_type == "free_item":
        reward_info = f"ของฟรี มูลค่า {discount_value} บาท"
    else:  # fixed
        reward_info = f"ส่วนลด {discount_value} บาท"

    return {
        "success": True,
        "reward_name": reward_name,
        "reward_info": reward_info,
        "points_spent": points_required,
        "points_balance": new_balance,
        "discount_type": discount_type,
        "discount_value": discount_value,
    }


def get_ledger_history(line_user_id: str, limit: int = 10) -> dict:
    """Get recent transaction history."""
    member = find_member_by_line(line_user_id)
    if not member:
        return {"success": False, "error": "Member not found", "entries": []}

    member_id = member.get("id")
    entries = get_ledger_for_member(member_id, limit)

    result = []
    for e in entries:
        f = _get_fields(e)
        pts = f.get("points", 0)
        entry_type = f.get("type", "")
        if entry_type == "earn":
            icon = "💰"
        elif entry_type == "redeem":
            icon = "🎁"
        elif entry_type == "bonus":
            icon = "🎉"
        elif entry_type == "expire":
            icon = "⏳"
        else:
            icon = "📝"

        result.append({
            "id": e.get("id"),
            "type": entry_type,
            "icon": icon,
            "points": pts,
            "balance_after": f.get("balance_after", 0),
            "description": f.get("description", ""),
            "created_at": e.get("created_at", ""),
        })

    total_earned = sum(r["points"] for r in result if r["type"] in ("earn", "bonus") and r["points"] > 0)
    total_spent = sum(abs(r["points"]) for r in result if r["type"] == "redeem")

    return {
        "success": True,
        "entries": result,
        "summary": {
            "total_earned_this_page": total_earned,
            "total_spent_this_page": total_spent,
        },
    }


def calculate_order_points(order_total_baht: float, line_user_id: str = "") -> dict:
    """
    Calculate how many points an order would earn.
    """
    multiplier = 1.0
    tier = "bronze"

    if line_user_id:
        member = find_member_by_line(line_user_id)
        if member:
            tier = _get_fields(member).get("tier", "bronze")
            multiplier = _get_tier_multiplier(tier)

    base_points = int(order_total_baht / DEFAULT_EARN_RATE)
    earned = max(1, int(base_points * multiplier))

    return {
        "success": True,
        "order_total": order_total_baht,
        "earn_rate": f"1 แต้ม / {DEFAULT_EARN_RATE} บาท",
        "tier_multiplier": f"{multiplier:.1f}x",
        "tier": tier,
        "points_earned": earned,
    }
