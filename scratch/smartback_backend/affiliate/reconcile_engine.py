import uuid
from typing import Dict, Any, List
from .models import get_db

def reconcile_order(order_id: str, new_status: str, notes: str = "") -> Dict[str, Any]:
    """
    Updates the approval/rejection status of an affiliate order.
    If rejected, voids the cashback liability in the ledger.
    """
    if new_status not in ["approved", "rejected", "pending"]:
        return {"status": "error", "message": "สถานะไม่ถูกต้อง (ต้องเป็น approved, rejected, หรือ pending)"}

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM cashback_orders WHERE order_id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return {"status": "error", "message": f"ไม่พบคำสั่งซื้อรหัส {order_id}"}

    old_status = order["status"]
    cursor.execute("""
    UPDATE cashback_orders 
    SET status = ?, notes = ? 
    WHERE order_id = ?
    """, (new_status, notes or f"Reconciled from {old_status} to {new_status}", order_id))

    # If transitioning to rejected, reverse the ledger liability
    if new_status == "rejected" and old_status != "rejected":
        reversal_id = f"REV-{uuid.uuid4().hex[:6].upper()}"
        cursor.execute("""
        INSERT INTO affiliate_ledger (entry_id, order_ref, user_code, debit_account, credit_account, amount, description)
        VALUES (?, ?, ?, '2120-Member-Cashback-Liability', '1120-Network-Receivable', ?, ?)
        """, (reversal_id, order_id, order["user_code"], order["cashback_amount"], f"ยกเลิกเงินคืนเนื่องจากออเดอร์ถูกปฏิเสธ ({order_id})"))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "order_id": order_id,
        "old_status": old_status,
        "new_status": new_status,
        "cashback_amount": order["cashback_amount"],
        "user_code": order["user_code"]
    }

def get_reconciliation_summary() -> Dict[str, Any]:
    """
    Returns monthly reconciliation metrics for ERP Dashboard.
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT 
        COUNT(*) as total_orders,
        COALESCE(SUM(order_amount), 0) as total_gmv,
        COALESCE(SUM(commission_total), 0) as total_commission,
        COALESCE(SUM(cashback_amount), 0) as total_cashback,
        COALESCE(SUM(our_profit), 0) as total_profit,
        SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved_count,
        SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending_count,
        SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected_count
    FROM cashback_orders
    """)
    summary = dict(cursor.fetchone())

    # Recent unapproved orders needing review
    cursor.execute("""
    SELECT order_id, user_code, store_name, order_amount, cashback_amount, status, created_at
    FROM cashback_orders
    WHERE status = 'pending'
    ORDER BY created_at DESC LIMIT 10
    """)
    pending_list = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {
        "summary": summary,
        "pending_reviews": pending_list
    }
