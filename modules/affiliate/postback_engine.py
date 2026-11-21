import uuid
from datetime import datetime
from typing import Dict, Any
from .models import get_db, PostbackPayload

def process_network_postback(payload: PostbackPayload) -> Dict[str, Any]:
    """
    Core Postback Webhook Engine:
    - Parses Sub-ID to identify the target user
    - Applies VIP tier bonus multipliers
    - Writes cashback record
    - Writes double-entry bookkeeping ledger
    """
    sub_id = payload.sub_id.strip()
    user_code = "user_pw_9821" # Default fallback

    # Extract user_code from format sb_{user_code}_{ts}_{hash}
    if sub_id.startswith("sb_"):
        parts = sub_id.split("_")
        if len(parts) >= 3:
            # sb_user_line_somchai_170000_abcd -> user_line_somchai
            user_code = "_".join(parts[1:-2]) if len(parts) > 3 else parts[1]

    conn = get_db()
    cursor = conn.cursor()

    # Get User Tier & Multiplier
    cursor.execute("SELECT * FROM users WHERE user_code = ?", (user_code,))
    user = cursor.fetchone()
    bonus_multiplier = user["bonus_multiplier"] if user and "bonus_multiplier" in user.keys() else 1.2
    user_name = user["name"] if user else "ผู้ใช้ SmartBack"

    # Store Campaign Defaults
    store_name = payload.store_name or ("Lotus's Online" if payload.network == 'accesstrade' else "Makro PRO")
    commission_total = round(payload.commission, 2)
    
    # Calculate Cashback & Profit
    # Standard member gets 70% of commission; VIP gets multiplier boost up to 90%
    base_share = 0.70
    effective_share = min(0.90, base_share * (bonus_multiplier / 1.2))
    cashback_amount = round(commission_total * effective_share, 2)
    our_profit = round(commission_total - cashback_amount, 2)

    status = payload.status # 'pending', 'approved', 'rejected'

    # Check if order already recorded
    cursor.execute("SELECT id FROM cashback_orders WHERE order_id = ?", (payload.order_id,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
        UPDATE cashback_orders 
        SET status = ?, commission_total = ?, cashback_amount = ?, our_profit = ?
        WHERE order_id = ?
        """, (status, commission_total, cashback_amount, our_profit, payload.order_id))
    else:
        cursor.execute("""
        INSERT INTO cashback_orders (
            order_id, user_code, store_name, order_amount, commission_total,
            cashback_rate, cashback_amount, our_profit, status, network, notes, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            payload.order_id, user_code, store_name, payload.sale_amount, commission_total,
            round((commission_total / payload.sale_amount) * 100, 2) if payload.sale_amount > 0 else 5.0,
            cashback_amount, our_profit, status, payload.network, f"Postback จาก {payload.network}"
        ))

    # --- Double-Entry Bookkeeping Ledger ---
    # 1. Debit: Network Accounts Receivable
    # 2. Credit: Member Cashback Liability
    # 3. Credit: Company Net Revenue
    entry_id = f"JRN-{int(datetime.now().timestamp())}-{uuid.uuid4().hex[:4].upper()}"
    cursor.execute("""
    INSERT INTO affiliate_ledger (entry_id, order_ref, user_code, debit_account, credit_account, amount, description)
    VALUES 
    (?, ?, ?, '1120-Network-Receivable', '2120-Member-Cashback-Liability', ?, ?),
    (?, ?, ?, '1120-Network-Receivable', '4110-Affiliate-Revenue', ?, ?)
    """, (
        entry_id, payload.order_id, user_code, cashback_amount, f"เงินคืนค้างจ่ายลูกค้า {user_name} ({payload.order_id})",
        entry_id + "-REV", payload.order_id, user_code, our_profit, f"รายได้ส่วนต่างคอมมิชชัน ({payload.order_id})"
    ))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "order_id": payload.order_id,
        "user_code": user_code,
        "user_name": user_name,
        "network": payload.network,
        "sale_amount": payload.sale_amount,
        "commission_total": commission_total,
        "cashback_amount": cashback_amount,
        "our_profit": our_profit,
        "order_status": status,
        "ledger_entry": entry_id
    }
