import re
import uuid
import time
from typing import Dict, Any, List
from .models import get_db

def validate_promptpay_id(pp_id: str) -> bool:
    """Validates Thai PromptPay Identifier (10-digit mobile or 13-digit Citizen ID)."""
    cleaned = re.sub(r'[^0-9]', '', pp_id.strip())
    return len(cleaned) in [10, 13]

def process_payout_request(user_code: str, promptpay_id: str, amount: float) -> Dict[str, Any]:
    """
    Submits and processes a PromptPay withdrawal with ledger accounting.
    """
    if not validate_promptpay_id(promptpay_id):
        return {"status": "error", "message": "เบอร์พร้อมเพย์หรือเลขบัตรประชาชนไม่ถูกต้อง (ต้องเป็น 10 หรือ 13 หลัก)"}

    if amount < 100.0:
        return {"status": "error", "message": "ยอดถอนขั้นต่ำคือ 100.00 บาท"}

    conn = get_db()
    cursor = conn.cursor()

    # Calculate current verified available balance
    cursor.execute("""
    SELECT COALESCE(SUM(cashback_amount), 0) FROM cashback_orders
    WHERE user_code = ? AND status = 'approved'
    """, (user_code,))
    total_approved = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COALESCE(SUM(amount), 0) FROM withdrawals
    WHERE user_code = ? AND status = 'completed'
    """, (user_code,))
    total_withdrawn = cursor.fetchone()[0]

    available = total_approved - total_withdrawn
    if available < amount:
        conn.close()
        return {
            "status": "error", 
            "message": f"ยอดเงินคงเหลือไม่เพียงพอ (ยอดที่ถอนได้คือ ฿{available:.2f})"
        }

    # Record withdrawal
    ref_code = f"WD-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}"
    cursor.execute("""
    INSERT INTO withdrawals (ref_code, user_code, promptpay_id, amount, status, created_at)
    VALUES (?, ?, ?, ?, 'completed', CURRENT_TIMESTAMP)
    """, (ref_code, user_code, promptpay_id, amount))

    # Record double-entry settlement in Ledger
    # Debit: Member Cashback Liability (Clearing debt to member)
    # Credit: PromptPay Cash Bank Account (Money leaving our bank)
    entry_id = f"JRN-PAY-{uuid.uuid4().hex[:6].upper()}"
    cursor.execute("""
    INSERT INTO affiliate_ledger (entry_id, order_ref, user_code, debit_account, credit_account, amount, description)
    VALUES (?, ?, ?, '2120-Member-Cashback-Liability', '1110-PromptPay-Bank-Account', ?, ?)
    """, (entry_id, ref_code, user_code, amount, f"โอนเงินคืนเข้าพร้อมเพย์ {promptpay_id} ({ref_code})"))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "message": f"โอนเงินคืน ฿{amount:.2f} เข้าพร้อมเพย์ {promptpay_id} สำเร็จเรียบร้อย",
        "ref_code": ref_code,
        "amount": amount,
        "remaining_balance": round(available - amount, 2),
        "ledger_entry": entry_id
    }
