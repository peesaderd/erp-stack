"""
LINE Bot Reward Handlers
========================
These functions can be called from the LINE bot to handle reward-related commands.
They return LINE-compatible message parts (text, flex, etc.).
"""

import logging
from typing import Optional
import httpx

from reward.config import SCHEMA_ENGINE_URL

logger = logging.getLogger("reward.line_handler")

REWARD_API_BASE = "http://localhost:8121"


async def _api_call(method: str, path: str, data: Optional[dict] = None) -> Optional[dict]:
    """Internal async API call to reward service."""
    url = f"{REWARD_API_BASE}{path}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method == "GET":
                resp = await client.get(url)
            else:
                resp = await client.post(url, json=data)

            if resp.status_code in (200, 201):
                return resp.json()
            logger.error(f"Reward API {method} {path} -> {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        logger.error(f"Reward API error: {e}")
        return None


async def handle_reward_commands(text: str, line_user_id: str, display_name: str = ""):
    """
    Main entry point for LINE reward commands.
    Returns (messages_list, handled) tuple.

    Recognized commands:
      - แต้มฉัน, my points, balance, points → show balance
      - แต้มสะสม, history, ประวัติ → show ledger
      - แลกแต้ม, redeem, แลก → show catalog
      - แต้ม (number), points (number) → calculate
    """
    text_lower = text.lower().strip()

    # ── Points Balance ──────────────────────────────────────────
    if text_lower in ("แต้มฉัน", "my points", "balance", "points", "แต้ม", "คะแนน", "my balance"):
        return await _show_balance(line_user_id, display_name)

    # ── Points History ──────────────────────────────────────────
    if text_lower in ("แต้มสะสม", "history", "ประวัติ", "ประวัติแต้ม", "transactions"):
        return await _show_history(line_user_id, display_name)

    # ── Redeem / Catalog ────────────────────────────────────────
    if text_lower in ("แลกแต้ม", "redeem", "แลก", "รางวัล", "rewards", "catalog", "แลกของ"):
        return await _show_catalog(line_user_id, display_name)

    # ── Earn Calculation ────────────────────────────────────────
    if text_lower.startswith("แต้ม ") or text_lower.startswith("points "):
        try:
            amount = float(text.split(" ", 1)[1].replace(",", "").replace("บาท", "").strip())
            return await _show_calculation(amount, line_user_id)
        except (ValueError, IndexError):
            pass

    # Not handled
    return [], False


async def _show_balance(line_user_id: str, display_name: str = "") -> tuple:
    """Show points balance + tier info."""
    # Auto-register if new user
    profile = await _api_call("GET", f"/api/v1/members/{line_user_id}")
    if not profile:
        await _api_call("POST", "/api/v1/members/register", {
            "line_user_id": line_user_id,
            "display_name": display_name,
        })
        profile = await _api_call("GET", f"/api/v1/members/{line_user_id}")

    if not profile:
        return [{"type": "text", "text": "😅 ไม่สามารถดึงข้อมูลแต้มได้ กรุณาลองใหม่"}], True

    member = profile.get("member", {})
    points = member.get("points", 0)
    tier = member.get("tier_label", "Bronze")
    multiplier = member.get("multiplier", 1.0)
    next_tier = member.get("next_tier")

    lines = [
        f"⭐ **แต้มสะสมของคุณ**\n",
        f"💎 คงเหลือ: **{points:,} แต้ม**",
        f"🏅 ระดับ: {tier}",
        f"📈 อัตราสะสม: {multiplier:.1f}x",
    ]

    if next_tier:
        lines.append(f"\n🔜 อัปเกรดเป็น {next_tier['label']} อีก {next_tier['points_needed']:,} แต้ม")

    lines.append("\n━━━━━━━━━━━━━━━━")
    lines.append("📋 `แลกแต้ม` — ดูรางวัล")
    lines.append("📜 `ประวัติ` — ดูประวัติการใช้แต้ม")

    return [{"type": "text", "text": "\n".join(lines)}], True


async def _show_history(line_user_id: str, display_name: str = "") -> tuple:
    """Show recent points transaction history."""
    # Ensure member exists
    await _api_call("POST", "/api/v1/members/register", {
        "line_user_id": line_user_id,
        "display_name": display_name or f"LINE-{line_user_id[:8]}",
    })

    result = await _api_call("GET", f"/api/v1/members/{line_user_id}/ledger?limit=10")
    if not result or not result.get("entries"):
        return [{"type": "text", "text": "📜 ยังไม่มีประวัติการใช้แต้ม\n\nเริ่มสะสมแต้มโดยการสั่งอาหารกับเรา! 🍽️"}], True

    entries = result["entries"]
    lines = ["📜 **ประวัติแต้มล่าสุด**\n"]

    for entry in entries:
        pts = entry.get("points", 0)
        bal = entry.get("balance_after", 0)
        desc = entry.get("description", "")
        icon = entry.get("icon", "📝")

        if pts > 0:
            lines.append(f"{icon} +{pts} แต้ม (รวม {bal})")
        else:
            lines.append(f"{icon} {pts} แต้ม (รวม {bal})")

        if desc:
            lines.append(f"   {desc}")

    return [{"type": "text", "text": "\n".join(lines)}], True


async def _show_catalog(line_user_id: str, display_name: str = "") -> tuple:
    """Show redeemable rewards catalog."""
    # Ensure member exists for balance
    await _api_call("POST", "/api/v1/members/register", {
        "line_user_id": line_user_id,
        "display_name": display_name,
    })

    catalog = await _api_call("GET", "/api/v1/catalog")
    items = catalog.get("items", []) if catalog else []

    if not items:
        return [{"type": "text", "text": "🎁 ยังไม่มีรางวัลให้แลกในตอนนี้\nเร็วๆ นี้มีมาแน่นอน! 🎉"}], True

    # Get balance
    profile = await _api_call("GET", f"/api/v1/members/{line_user_id}")
    balance = profile.get("member", {}).get("points", 0) if profile else 0

    lines = [
        f"🎁 **รางวัลสำหรับคุณ**\n",
        f"💎 คุณมี: **{balance:,} แต้ม**\n",
        "━━━━━━━━━━━━━━━━\n",
    ]

    for item in items:
        name = item.get("name", "")
        pts = item.get("points_required", 0)
        desc = item.get("description", "")
        icon = item.get("icon", "🎁")
        can_afford = "✅" if balance >= pts else "❌"

        lines.append(f"{icon} **{name}**")
        lines.append(f"   {can_afford} {pts:,} แต้ม")
        if desc:
            lines.append(f"   _{desc}_")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━")
    lines.append("พิมพ์ `แลก <ชื่อรางวัล>` เพื่อใช้แต้ม")
    lines.append("เช่น: `แลก ส่วนลด 50 บาท`")

    return [{"type": "text", "text": "\n".join(lines)}], True


async def _show_calculation(amount: float, line_user_id: str) -> tuple:
    """Show how many points an order would earn."""
    calc = await _api_call("POST", "/api/v1/points/calculate", {
        "order_total": amount,
        "line_user_id": line_user_id,
    })

    if not calc:
        return [
            {"type": "text", "text": f"💡 ยอด {amount:.0f} บาท จะได้ประมาณ {max(1, int(amount/10))} แต้ม"}
        ], True

    lines = [
        f"🧮 **คำนวณแต้ม**\n",
        f"💵 ยอดสั่งซื้อ: **{amount:,.0f} บาท**",
        f"📊 อัตรา: {calc.get('earn_rate', '1 แต้ม / 10 บาท')}",
        f"🏅 ระดับ: {calc.get('tier', 'bronze')} ({calc.get('tier_multiplier', '1.0x')})",
        f"",
        f"⭐ **จะได้รับ: {calc.get('points_earned', 0):,} แต้ม** ✨",
    ]

    return [{"type": "text", "text": "\n".join(lines)}], True


# ── Auto-earn Integration ─────────────────────────────────────────

async def auto_earn_from_order(
    line_user_id: str,
    order_total: float,
    order_id: str,
    display_name: str = "",
) -> Optional[dict]:
    """
    Called automatically after a successful order checkout via LINE.
    Awards points to the member.
    """
    # Ensure member exists
    await _api_call("POST", "/api/v1/members/register", {
        "line_user_id": line_user_id,
        "display_name": display_name,
    })

    result = await _api_call("POST", "/api/v1/points/earn", {
        "line_user_id": line_user_id,
        "amount_baht": order_total,
        "reference_type": "pos_order",
        "reference_id": order_id,
        "description": f"🧾 สั่งอาหารออเดอร์ {order_id}",
    })

    return result
