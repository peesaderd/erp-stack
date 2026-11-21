from fastapi import APIRouter, HTTPException, Query, Body, Request
from fastapi.responses import HTMLResponse
from typing import Optional, List, Dict, Any

from .models import (
    init_affiliate_tables, get_db,
    NetworkConfigUpdate, CampaignUpdate, PostbackPayload
)
from .link_engine import generate_affiliate_link
from .postback_engine import process_network_postback
from .reconcile_engine import reconcile_order, get_reconciliation_summary
from .payout_engine import process_payout_request

# Initialize DB tables on startup
init_affiliate_tables()

router = APIRouter(prefix="/erp/affiliate", tags=["ERP Affiliate & Cashback"])

@router.get("/dashboard")
def get_dashboard_metrics():
    """
    Returns executive KPI metrics for ERP management.
    """
    data = get_reconciliation_summary()
    conn = get_db()
    cursor = conn.cursor()

    # Network distribution
    cursor.execute("""
    SELECT network, COUNT(*) as count, SUM(commission_total) as commission, SUM(cashback_amount) as cashback
    FROM cashback_orders
    GROUP BY network
    """)
    networks = [dict(r) for r in cursor.fetchall()]

    # Total PromptPay Paid Out
    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM withdrawals WHERE status = 'completed'")
    total_paid_out = cursor.fetchone()[0]

    # Active Campaigns
    cursor.execute("SELECT COUNT(*) FROM affiliate_campaigns WHERE is_active = 1")
    active_campaigns = cursor.fetchone()[0]

    conn.close()

    summary = data["summary"]
    return {
        "status": "success",
        "kpi": {
            "total_gmv": round(summary["total_gmv"], 2),
            "total_commission_revenue": round(summary["total_commission"], 2),
            "total_cashback_liability": round(summary["total_cashback"], 2),
            "total_net_profit": round(summary["total_profit"], 2),
            "net_margin_pct": round((summary["total_profit"] / summary["total_commission"] * 100) if summary["total_commission"] > 0 else 0, 1),
            "total_paid_out": round(total_paid_out, 2),
            "active_campaigns": active_campaigns
        },
        "order_counts": {
            "total": summary["total_orders"],
            "approved": summary["approved_count"],
            "pending": summary["pending_count"],
            "rejected": summary["rejected_count"]
        },
        "network_breakdown": networks,
        "pending_reviews": data["pending_reviews"]
    }

@router.get("/networks")
def list_networks():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM affiliate_networks")
    networks = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"status": "success", "networks": networks}

@router.patch("/networks/{slug}")
def update_network(slug: str, payload: NetworkConfigUpdate):
    conn = get_db()
    cursor = conn.cursor()
    fields = []
    values = []
    if payload.api_key is not None:
        fields.append("api_key = ?"); values.append(payload.api_key)
    if payload.api_secret is not None:
        fields.append("api_secret = ?"); values.append(payload.api_secret)
    if payload.webhook_secret is not None:
        fields.append("webhook_secret = ?"); values.append(payload.webhook_secret)
    if payload.is_active is not None:
        fields.append("is_active = ?"); values.append(1 if payload.is_active else 0)

    if not fields:
        conn.close()
        return {"status": "no_change"}

    values.append(slug)
    cursor.execute(f"UPDATE affiliate_networks SET {', '.join(fields)} WHERE slug = ?", values)
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"อัปเดตการตั้งค่าเครือข่าย {slug} เรียบร้อย"}

@router.get("/campaigns")
def list_campaigns():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM affiliate_campaigns ORDER BY is_active DESC, store_name ASC")
    campaigns = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"status": "success", "campaigns": campaigns}

@router.patch("/campaigns/{store_key}")
def update_campaign(store_key: str, payload: CampaignUpdate):
    conn = get_db()
    cursor = conn.cursor()
    fields = []
    values = []
    if payload.commission_rate is not None:
        fields.append("commission_rate = ?"); values.append(payload.commission_rate)
    if payload.cashback_share is not None:
        fields.append("cashback_share = ?"); values.append(payload.cashback_share)
    if payload.is_active is not None:
        fields.append("is_active = ?"); values.append(1 if payload.is_active else 0)

    if not fields:
        conn.close()
        return {"status": "no_change"}

    values.append(store_key)
    cursor.execute(f"UPDATE affiliate_campaigns SET {', '.join(fields)} WHERE store_key = ?", values)
    conn.commit()
    conn.close()
    return {"status": "success", "message": f"อัปเดตร้านค้า {store_key} เรียบร้อย"}

@router.get("/orders")
def list_orders(status: Optional[str] = None, limit: int = 50, offset: int = 0):
    conn = get_db()
    cursor = conn.cursor()
    if status:
        cursor.execute("""
        SELECT o.*, u.name as user_name 
        FROM cashback_orders o 
        LEFT JOIN users u ON o.user_code = u.user_code 
        WHERE o.status = ? 
        ORDER BY o.created_at DESC LIMIT ? OFFSET ?
        """, (status, limit, offset))
    else:
        cursor.execute("""
        SELECT o.*, u.name as user_name 
        FROM cashback_orders o 
        LEFT JOIN users u ON o.user_code = u.user_code 
        ORDER BY o.created_at DESC LIMIT ? OFFSET ?
        """, (limit, offset))
    orders = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"status": "success", "count": len(orders), "orders": orders}

@router.post("/orders/{order_id}/reconcile")
def reconcile_order_endpoint(order_id: str, new_status: str = Query(...), notes: Optional[str] = Query(None)):
    res = reconcile_order(order_id, new_status, notes or "")
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res

@router.get("/ledger")
def get_ledger_records(limit: int = 50):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM affiliate_ledger ORDER BY created_at DESC LIMIT ?", (limit,))
    entries = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"status": "success", "entries": entries}

@router.post("/link/generate")
def generate_link_endpoint(user_code: str = Body(...), url: str = Body(...)):
    return generate_affiliate_link(user_code, url)

@router.post("/postback/webhook")
def receive_postback_webhook(payload: PostbackPayload):
    return process_network_postback(payload)

@router.post("/payout/execute")
def execute_payout(user_code: str = Body(...), promptpay_id: str = Body(...), amount: float = Body(...)):
    res = process_payout_request(user_code, promptpay_id, amount)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res["message"])
    return res

@router.get("/ui", response_class=HTMLResponse)
def get_dashboard_html():
    """
    Returns modern executive dashboard view in Thai.
    """
    html = """<!DOCTYPE html>
<html lang="th">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>ERP Modular - Affiliate & Cashback Command Center</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600;700;800&display=swap" rel="stylesheet"/>
  <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined" rel="stylesheet"/>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body { font-family: 'Prompt', sans-serif; background-color: #0f172a; color: #f8fafc; }
    .material-symbols-outlined { font-family: 'Material Symbols Outlined' !important; }
  </style>
</head>
<body class="p-6">
  <div class="max-w-7xl mx-auto flex flex-col gap-6">
    
    <!-- Header -->
    <div class="flex items-center justify-between pb-4 border-b border-slate-800">
      <div class="flex items-center gap-3">
        <div class="w-12 h-12 rounded-2xl bg-indigo-600 flex items-center justify-center text-white font-black text-2xl shadow-lg">
          ⚡
        </div>
        <div>
          <h1 class="text-xl font-bold flex items-center gap-2">
            Affiliate & Cashback Management Module
            <span class="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30">ERP Active</span>
          </h1>
          <p class="text-xs text-slate-400">ระบบควบคุมรายได้ค่าคอมมิชชัน, การกระทบยอดคำสั่งซื้อ และสมุดบัญชีเงินคืน</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button onclick="refreshDashboard()" class="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-xs font-bold rounded-xl border border-slate-700 flex items-center gap-1.5 transition-colors">
          <span class="material-symbols-outlined text-[16px]">refresh</span>
          <span>รีเฟรชข้อมูล</span>
        </button>
        <a href="/smartback/" target="_blank" class="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold rounded-xl shadow flex items-center gap-1.5 transition-colors">
          <span class="material-symbols-outlined text-[16px]">open_in_new</span>
          <span>เปิดแอป SmartBack PWA</span>
        </a>
      </div>
    </div>

    <!-- 4 KPI Cards -->
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-4">
        <span class="text-xs text-slate-400">ยอดขายรวมสินค้า (Total GMV)</span>
        <h3 class="text-2xl font-black text-white mt-1" id="kpiGmv">฿0.00</h3>
        <span class="text-[10px] text-slate-500 mt-1 block">จากทุกแคมเปญร้านค้า</span>
      </div>

      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-4">
        <span class="text-xs text-slate-400">รายได้คอมมิชชันรวม (Revenue)</span>
        <h3 class="text-2xl font-black text-emerald-400 mt-1" id="kpiCommission">฿0.00</h3>
        <span class="text-[10px] text-emerald-500/80 mt-1 block">รับจาก AccessTrade & Involve Asia</span>
      </div>

      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-4">
        <span class="text-xs text-slate-400">เงินคืนจ่ายสมาชิก (Cashback)</span>
        <h3 class="text-2xl font-black text-amber-400 mt-1" id="kpiCashback">฿0.00</h3>
        <span class="text-[10px] text-amber-500/80 mt-1 block">หนี้สินเงินคืนค้างจ่ายสะสม</span>
      </div>

      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-4">
        <span class="text-xs text-slate-400">กำไรสุทธิส่วนต่าง (Net Profit)</span>
        <h3 class="text-2xl font-black text-indigo-400 mt-1" id="kpiProfit">฿0.00</h3>
        <span class="text-[10px] text-indigo-400/80 mt-1 block" id="kpiMargin">มาร์จิ้น: 0%</span>
      </div>
    </div>

    <!-- Main 2 Column View -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      <!-- Left 2 Cols: Orders & Reconcile Table -->
      <div class="lg:col-span-2 bg-slate-900/80 border border-slate-800 rounded-2xl p-5 flex flex-col gap-4">
        <div class="flex items-center justify-between">
          <div>
            <h3 class="text-sm font-bold text-white flex items-center gap-1.5">
              <span class="material-symbols-outlined text-indigo-400 text-[18px]">receipt_long</span>
              รายการคำสั่งซื้อ & กระทบยอด (Order Reconciliation)
            </h3>
            <p class="text-xs text-slate-400">ตรวจสอบและยืนยันการอนุมัติเงินคืนก่อนโอนเงิน</p>
          </div>
          <div class="flex items-center gap-1 text-xs">
            <button onclick="loadOrders('')" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold">ทั้งหมด</button>
            <button onclick="loadOrders('pending')" class="px-2.5 py-1 rounded-lg bg-amber-950/60 text-amber-400 font-semibold border border-amber-500/30">รอตรวจ</button>
            <button onclick="loadOrders('approved')" class="px-2.5 py-1 rounded-lg bg-emerald-950/60 text-emerald-400 font-semibold border border-emerald-500/30">อนุมัติแล้ว</button>
          </div>
        </div>

        <div class="overflow-x-auto">
          <table class="w-full text-xs text-left text-slate-300">
            <thead class="text-[11px] text-slate-400 uppercase bg-slate-800/60 border-b border-slate-700">
              <tr>
                <th class="px-3 py-2.5">รหัสออเดอร์</th>
                <th class="px-3 py-2.5">ร้านค้า</th>
                <th class="px-3 py-2.5">ผู้ซื้อ</th>
                <th class="px-3 py-2.5">ยอดซื้อ</th>
                <th class="px-3 py-2.5">เงินคืน</th>
                <th class="px-3 py-2.5">กำไรเรา</th>
                <th class="px-3 py-2.5">สถานะ</th>
                <th class="px-3 py-2.5 text-right">ดำเนินการ</th>
              </tr>
            </thead>
            <tbody id="ordersTbody" class="divide-y divide-slate-800">
              <tr><td colspan="8" class="text-center py-6 text-slate-500">กำลังโหลดข้อมูล...</td></tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Right Col: Networks & Campaigns Settings -->
      <div class="flex flex-col gap-5">
        
        <!-- Networks Config -->
        <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 flex flex-col gap-3">
          <h3 class="text-sm font-bold text-white flex items-center gap-1.5">
            <span class="material-symbols-outlined text-emerald-400 text-[18px]">hub</span>
            สถานะเครือข่ายพันธมิตร (Networks)
          </h3>
          <div id="networksList" class="flex flex-col gap-2">
            <!-- Dynamic Networks -->
          </div>
        </div>

        <!-- Store Campaigns Overview -->
        <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 flex flex-col gap-3">
          <h3 class="text-sm font-bold text-white flex items-center gap-1.5">
            <span class="material-symbols-outlined text-amber-400 text-[18px]">storefront</span>
            แคมเปญร้านค้า (Store Catalogs)
          </h3>
          <div id="campaignsList" class="flex flex-col gap-2 max-h-72 overflow-y-auto pr-1">
            <!-- Dynamic Campaigns -->
          </div>
        </div>

      </div>

    </div>

  </div>

  <script>
    const API_BASE = '/smartback/api/erp/affiliate';

    async function refreshDashboard() {
      try {
        const res = await fetch(`${API_BASE}/dashboard`);
        const data = await res.json();
        if (data.status === 'success') {
          document.getElementById('kpiGmv').textContent = '฿' + data.kpi.total_gmv.toLocaleString('th-TH', {minimumFractionDigits: 2});
          document.getElementById('kpiCommission').textContent = '฿' + data.kpi.total_commission_revenue.toLocaleString('th-TH', {minimumFractionDigits: 2});
          document.getElementById('kpiCashback').textContent = '฿' + data.kpi.total_cashback_liability.toLocaleString('th-TH', {minimumFractionDigits: 2});
          document.getElementById('kpiProfit').textContent = '฿' + data.kpi.total_net_profit.toLocaleString('th-TH', {minimumFractionDigits: 2});
          document.getElementById('kpiMargin').textContent = 'มาร์จิ้นกำไรขั้นต้น: ' + data.kpi.net_margin_pct + '%';
        }
      } catch (err) {
        console.error('Err dashboard:', err);
      }
      loadNetworks();
      loadCampaigns();
      loadOrders();
    }

    async function loadNetworks() {
      try {
        const res = await fetch(`${API_BASE}/networks`);
        const data = await res.json();
        const container = document.getElementById('networksList');
        if (container && data.networks) {
          container.innerHTML = data.networks.map(n => `
            <div class="p-2.5 rounded-xl bg-slate-800/80 border border-slate-700/80 flex items-center justify-between">
              <div>
                <span class="text-xs font-bold text-white block">${n.name}</span>
                <span class="text-[10px] text-slate-400">Webhook: /smartback/api/erp/affiliate/postback/webhook</span>
              </div>
              <span class="text-[9px] px-2 py-0.5 rounded-full ${n.is_active ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'bg-red-500/20 text-red-400'} font-bold">
                ${n.is_active ? 'เชื่อมต่อแล้ว' : 'ปิด'}
              </span>
            </div>
          `).join('');
        }
      } catch (e) {}
    }

    async function loadCampaigns() {
      try {
        const res = await fetch(`${API_BASE}/campaigns`);
        const data = await res.json();
        const container = document.getElementById('campaignsList');
        if (container && data.campaigns) {
          container.innerHTML = data.campaigns.map(c => `
            <div class="p-2 rounded-xl bg-slate-800/60 border border-slate-700/60 flex items-center justify-between text-xs">
              <div class="flex items-center gap-2">
                <span>${c.icon}</span>
                <span class="font-bold text-white">${c.store_name}</span>
              </div>
              <div class="text-right">
                <span class="text-[11px] text-emerald-400 font-bold block">คอม ${(c.commission_rate * 100).toFixed(1)}%</span>
                <span class="text-[9px] text-slate-400">คืนลูกค้า ${(c.commission_rate * c.cashback_share * 100).toFixed(1)}%</span>
              </div>
            </div>
          `).join('');
        }
      } catch (e) {}
    }

    async function loadOrders(status = '') {
      try {
        const url = status ? `${API_BASE}/orders?status=${status}` : `${API_BASE}/orders`;
        const res = await fetch(url);
        const data = await res.json();
        const tbody = document.getElementById('ordersTbody');
        if (tbody && data.orders) {
          if (data.orders.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="text-center py-6 text-slate-500">ไม่พบคำสั่งซื้อ</td></tr>';
            return;
          }
          tbody.innerHTML = data.orders.map(o => `
            <tr class="hover:bg-slate-800/40">
              <td class="px-3 py-2.5 font-mono text-[11px] font-bold text-slate-300">${o.order_id}</td>
              <td class="px-3 py-2.5">${o.store_name}</td>
              <td class="px-3 py-2.5">${o.user_name || o.user_code}</td>
              <td class="px-3 py-2.5 font-bold">฿${o.order_amount.toFixed(2)}</td>
              <td class="px-3 py-2.5 text-emerald-400 font-bold">+฿${o.cashback_amount.toFixed(2)}</td>
              <td class="px-3 py-2.5 text-indigo-400 font-bold">+฿${o.our_profit.toFixed(2)}</td>
              <td class="px-3 py-2.5">
                <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${
                  o.status === 'approved' ? 'bg-emerald-500/20 text-emerald-400' :
                  o.status === 'pending' ? 'bg-amber-500/20 text-amber-400' : 'bg-red-500/20 text-red-400'
                }">
                  ${o.status}
                </span>
              </td>
              <td class="px-3 py-2.5 text-right">
                ${o.status === 'pending' ? `
                  <button onclick="reconcileOrder('${o.order_id}', 'approved')" class="px-2 py-1 bg-emerald-600 hover:bg-emerald-500 text-white font-bold rounded text-[10px] mr-1">อนุมัติ</button>
                  <button onclick="reconcileOrder('${o.order_id}', 'rejected')" class="px-2 py-1 bg-red-600/80 hover:bg-red-500 text-white font-bold rounded text-[10px]">ปฏิเสธ</button>
                ` : '<span class="text-slate-500 text-[10px]">เสร็จสิ้น</span>'}
              </td>
            </tr>
          `).join('');
        }
      } catch (e) {}
    }

    async function reconcileOrder(orderId, newStatus) {
      if (!confirm(`ยืนยันเปลี่ยนสถานะคำสั่งซื้อ ${orderId} เป็น ${newStatus}?`)) return;
      try {
        const res = await fetch(`${API_BASE}/orders/${orderId}/reconcile?new_status=${newStatus}`, { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
          refreshDashboard();
        } else {
          alert(data.detail || 'เกิดข้อผิดพลาด');
        }
      } catch (err) {
        alert('เกิดข้อผิดพลาดในการเชื่อมต่อ');
      }
    }

    window.addEventListener('DOMContentLoaded', refreshDashboard);
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html)
