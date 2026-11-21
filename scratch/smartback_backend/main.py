import os
import time
import json
import uuid
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import get_db, init_db
from affiliate.main import router as affiliate_router

# Initialize database on startup
init_db()

app = FastAPI(title="SmartBack Cashback API & ERP Module", version="1.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount ERP Affiliate & Cashback Command Center
app.include_router(affiliate_router)

STORE_CATALOG = {
    "lotus": {
        "name": "Lotus's Online",
        "domain": "lotuss.com",
        "rate": "คืนสูงสุด 5.5%",
        "commission_rate": 0.055,
        "cashback_share": 0.70,
        "icon": "🛒",
        "offer_id": "10928"
    },
    "makro": {
        "name": "Makro PRO",
        "domain": "makro.pro",
        "rate": "คืน 4.0% (ยกลัง)",
        "commission_rate": 0.040,
        "cashback_share": 0.75,
        "icon": "📦",
        "offer_id": "14821"
    },
    "agoda": {
        "name": "Agoda",
        "domain": "agoda.com",
        "rate": "คืนสูงสุด 8.5%",
        "commission_rate": 0.085,
        "cashback_share": 0.70,
        "icon": "🏨",
        "offer_id": "8910"
    },
    "trip": {
        "name": "Trip.com",
        "domain": "trip.com",
        "rate": "คืนสูงสุด 7.0%",
        "commission_rate": 0.070,
        "cashback_share": 0.70,
        "icon": "✈️",
        "offer_id": "9812"
    },
    "klook": {
        "name": "Klook",
        "domain": "klook.com",
        "rate": "คืน 6.0%",
        "commission_rate": 0.060,
        "cashback_share": 0.70,
        "icon": "🎡",
        "offer_id": "11520"
    },
    "bigc": {
        "name": "Big C Online",
        "domain": "bigc.co.th",
        "rate": "คืน 4.0%",
        "commission_rate": 0.040,
        "cashback_share": 0.70,
        "icon": "🛍️",
        "offer_id": "10502"
    },
    "central": {
        "name": "Central Online",
        "domain": "central.co.th",
        "rate": "คืน 6.0%",
        "commission_rate": 0.060,
        "cashback_share": 0.70,
        "icon": "🏬",
        "offer_id": "12300"
    },
    "advice": {
        "name": "Advice IT",
        "domain": "advice.co.th",
        "rate": "คืน 2.5%",
        "commission_rate": 0.025,
        "cashback_share": 0.70,
        "icon": "💻",
        "offer_id": "13410"
    }
}

# --- Request / Response Models ---
class ConvertLinkRequest(BaseModel):
    user_code: str = "user_pw_9821"
    original_url: str

class WithdrawRequest(BaseModel):
    user_code: str = "user_pw_9821"
    promptpay_id: str
    amount: float

class SimulateOrderRequest(BaseModel):
    user_code: str = "user_pw_9821"
    store_key: str = "lotus"
    order_amount: float = 1200.00
    status: str = "pending" # 'pending' or 'approved'
    notes: Optional[str] = "ทดสอบสั่งซื้อสินค้า"

class LineAuthRequest(BaseModel):
    code: Optional[str] = None
    redirect_uri: Optional[str] = None
    display_name: Optional[str] = "คุณสมชาย ช้อปเพลิน (LINE)"
    picture_url: Optional[str] = "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150"
    line_id: Optional[str] = None

class GoogleAuthRequest(BaseModel):
    credential: Optional[str] = None # Google ID token
    email: Optional[str] = "somchai.shopkru@gmail.com"
    name: Optional[str] = "Somchai Shopkru (Google)"
    avatar_url: Optional[str] = "https://images.unsplash.com/photo-1570295999919-56ceb5ecca61?w=150"
    google_id: Optional[str] = None

# --- Helper function: Fetch User & Wallet ---
def get_user_wallet_data(user_code: str):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE user_code = ?", (user_code,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return None

    # Approved Cashback
    cursor.execute("""
        SELECT COALESCE(SUM(cashback_amount), 0) FROM cashback_orders 
        WHERE user_code = ? AND status = 'approved'
    """, (user_code,))
    total_approved = cursor.fetchone()[0]

    # Completed Withdrawals
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM withdrawals 
        WHERE user_code = ? AND status = 'completed'
    """, (user_code,))
    total_withdrawn = cursor.fetchone()[0]

    available_balance = max(0.0, total_approved - total_withdrawn)

    # Pending Cashback
    cursor.execute("""
        SELECT COALESCE(SUM(cashback_amount), 0) FROM cashback_orders 
        WHERE user_code = ? AND status = 'pending'
    """, (user_code,))
    pending_balance = cursor.fetchone()[0]

    # Total historical earned
    cursor.execute("""
        SELECT COALESCE(SUM(cashback_amount), 0) FROM cashback_orders 
        WHERE user_code = ? AND status IN ('approved', 'completed')
    """, (user_code,))
    total_earned = cursor.fetchone()[0]

    # Recent Cashback Orders
    cursor.execute("""
        SELECT id, order_id, store_name, order_amount, cashback_amount, status, notes, created_at
        FROM cashback_orders
        WHERE user_code = ?
        ORDER BY created_at DESC LIMIT 15
    """, (user_code,))
    orders = [dict(row) for row in cursor.fetchall()]

    # Recent Withdrawals
    cursor.execute("""
        SELECT id, ref_code, promptpay_id, amount, status, created_at
        FROM withdrawals
        WHERE user_code = ?
        ORDER BY created_at DESC LIMIT 10
    """, (user_code,))
    withdrawals = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "user": {
            "user_code": user["user_code"],
            "name": user["name"],
            "email": user["email"] if "email" in user.keys() else None,
            "provider": user["provider"] if "provider" in user.keys() else "guest",
            "avatar_url": user["avatar_url"] if "avatar_url" in user.keys() else None,
            "vip_tier": user["vip_tier"],
            "bonus_multiplier": user["bonus_multiplier"],
            "promptpay_id": user["promptpay_id"],
            "token": user["token"] if "token" in user.keys() else None
        },
        "wallet": {
            "available_balance": round(available_balance, 2),
            "pending_balance": round(pending_balance, 2),
            "total_withdrawn": round(total_withdrawn, 2),
            "total_earned": round(total_earned, 2)
        },
        "recent_orders": orders,
        "recent_withdrawals": withdrawals
    }

# --- Routes ---

@app.get("/")
def read_root():
    return {
        "app": "SmartBack Backend API",
        "version": "1.1.0",
        "auth_methods": ["line", "google", "guest"],
        "status": "online",
        "server_time": datetime.now().isoformat()
    }

@app.get("/auth/config")
def get_auth_config():
    line_channel_id = os.environ.get("LINE_CHANNEL_ID", "")
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    return {
        "line": {
            "channel_id": line_channel_id or "2006899120", # Demo / Preconfigured ID
            "is_configured": bool(line_channel_id),
            "mode": "live" if line_channel_id else "sandbox_demo"
        },
        "google": {
            "client_id": google_client_id or "982138765412-sbapp.apps.googleusercontent.com",
            "is_configured": bool(google_client_id),
            "mode": "live" if google_client_id else "sandbox_demo"
        }
    }

@app.post("/auth/line")
def login_with_line(req: LineAuthRequest):
    """
    Handle LINE Login:
    - If OAuth authorization code is provided and LINE_CHANNEL_SECRET is set, exchanges code for access token and profile.
    - Seamless 1-click Login in Sandbox / Demo mode.
    """
    conn = get_db()
    cursor = conn.cursor()

    line_channel_id = os.environ.get("LINE_CHANNEL_ID")
    line_channel_secret = os.environ.get("LINE_CHANNEL_SECRET")

    user_line_id = req.line_id or "U" + uuid.uuid4().hex[:12]
    display_name = req.display_name or "ผู้ใช้ LINE SmartBack"
    picture_url = req.picture_url or "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=150"

    # If code provided & secret present, execute real OAuth exchange with LINE
    if req.code and line_channel_secret:
        try:
            token_url = "https://api.line.me/oauth2/v2.1/token"
            data = urllib.parse.urlencode({
                "grant_type": "authorization_code",
                "code": req.code,
                "redirect_uri": req.redirect_uri or "https://m2igen.com/smartback/",
                "client_id": line_channel_id,
                "client_secret": line_channel_secret
            }).encode('utf-8')
            token_req = urllib.request.Request(token_url, data=data, method="POST")
            with urllib.request.urlopen(token_req, timeout=10) as resp:
                token_res = json.loads(resp.read().decode('utf-8'))
                access_token = token_res.get("access_token")

            # Fetch Profile
            prof_req = urllib.request.Request("https://api.line.me/v2/profile", headers={
                "Authorization": f"Bearer {access_token}"
            })
            with urllib.request.urlopen(prof_req, timeout=10) as resp:
                prof_res = json.loads(resp.read().decode('utf-8'))
                user_line_id = prof_res.get("userId", user_line_id)
                display_name = prof_res.get("displayName", display_name)
                picture_url = prof_res.get("pictureUrl", picture_url)
        except Exception as e:
            print("LINE OAuth exception fallback:", e)

    # Find or create user
    user_code = "user_line_somchai" if not req.line_id and not req.code else f"user_line_{user_line_id[:8]}"
    cursor.execute("SELECT * FROM users WHERE provider_id = ? OR user_code = ?", (user_line_id, user_code))
    user = cursor.fetchone()

    session_token = "tok_line_" + uuid.uuid4().hex[:20]

    if user:
        user_code = user["user_code"]
        cursor.execute("""
            UPDATE users 
            SET name = ?, avatar_url = ?, token = ?, last_login = CURRENT_TIMESTAMP
            WHERE user_code = ?
        """, (display_name, picture_url, session_token, user_code))
    else:
        cursor.execute("""
            INSERT INTO users (user_code, name, email, promptpay_id, provider, provider_id, avatar_url, token, vip_tier, bonus_multiplier)
            VALUES (?, ?, ?, ?, 'line', ?, ?, ?, 'VIP Platinum (1.5x)', 1.5)
        """, (user_code, display_name, f"{user_code}@smartback.line", "081-998-7766", user_line_id, picture_url, session_token))

        # Seed welcoming initial bonus order for new LINE members!
        cursor.execute("""
            INSERT INTO cashback_orders (order_id, user_code, store_name, order_amount, commission_total, cashback_rate, cashback_amount, our_profit, status, network, notes, created_at)
            VALUES (?, ?, 'Lotus''s Online', 1500.00, 82.50, 5.5, 66.00, 16.50, 'approved', 'accesstrade', 'โบนัสต้อนรับสมาชิก LINE สั่งซื้อครั้งแรก', datetime('now'))
        """, (f"ORD-LN-{uuid.uuid4().hex[:6].upper()}", user_code))

    conn.commit()
    conn.close()

    data = get_user_wallet_data(user_code)
    return {
        "status": "success",
        "provider": "line",
        "message": f"เข้าสู่ระบบด้วย LINE สำเร็จ ({display_name})",
        "token": session_token,
        **data
    }

@app.post("/auth/google")
def login_with_google(req: GoogleAuthRequest):
    """
    Handle Google Sign-In:
    - If Google ID token credential provided, verify via Google OAuth endpoint.
    - Seamless 1-click Login in Sandbox / Demo mode.
    """
    conn = get_db()
    cursor = conn.cursor()

    email = req.email or "somchai.shopkru@gmail.com"
    name = req.name or "Somchai Shopkru (Google)"
    avatar_url = req.avatar_url or "https://images.unsplash.com/photo-1570295999919-56ceb5ecca61?w=150"
    google_id = req.google_id or "G" + uuid.uuid4().hex[:12]

    # Verify ID token if provided
    if req.credential:
        try:
            val_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={req.credential}"
            with urllib.request.urlopen(val_url, timeout=10) as resp:
                g_res = json.loads(resp.read().decode('utf-8'))
                email = g_res.get("email", email)
                name = g_res.get("name", name)
                avatar_url = g_res.get("picture", avatar_url)
                google_id = g_res.get("sub", google_id)
        except Exception as e:
            print("Google credential check fallback:", e)

    user_code = "user_google_somchai" if not req.google_id and not req.credential else f"user_gg_{google_id[:8]}"
    cursor.execute("SELECT * FROM users WHERE email = ? OR provider_id = ? OR user_code = ?", (email, google_id, user_code))
    user = cursor.fetchone()

    session_token = "tok_google_" + uuid.uuid4().hex[:20]

    if user:
        user_code = user["user_code"]
        cursor.execute("""
            UPDATE users 
            SET name = ?, avatar_url = ?, token = ?, last_login = CURRENT_TIMESTAMP
            WHERE user_code = ?
        """, (name, avatar_url, session_token, user_code))
    else:
        cursor.execute("""
            INSERT INTO users (user_code, name, email, promptpay_id, provider, provider_id, avatar_url, token, vip_tier, bonus_multiplier)
            VALUES (?, ?, ?, ?, 'google', ?, ?, ?, 'VIP Diamond (2.0x)', 2.0)
        """, (user_code, name, email, "086-554-3322", google_id, avatar_url, session_token))

        # Seed welcoming initial bonus order for new Google members!
        cursor.execute("""
            INSERT INTO cashback_orders (order_id, user_code, store_name, order_amount, commission_total, cashback_rate, cashback_amount, our_profit, status, network, notes, created_at)
            VALUES (?, ?, 'Advice IT', 3200.00, 80.00, 2.5, 64.00, 16.00, 'approved', 'accesstrade', 'โบนัสต้อนรับสมาชิก Google ซื้อสินค้าไอที', datetime('now'))
        """, (f"ORD-GG-{uuid.uuid4().hex[:6].upper()}", user_code))

    conn.commit()
    conn.close()

    data = get_user_wallet_data(user_code)
    return {
        "status": "success",
        "provider": "google",
        "message": f"เข้าสู่ระบบด้วย Google สำเร็จ ({name})",
        "token": session_token,
        **data
    }

@app.get("/auth/me")
def get_current_user_profile(
    authorization: Optional[str] = Header(None),
    user_code: Optional[str] = Query(None)
):
    """
    Returns the currently active user profile & wallet stats.
    """
    conn = get_db()
    cursor = conn.cursor()

    resolved_user_code = user_code
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "").strip()
        cursor.execute("SELECT user_code FROM users WHERE token = ?", (token,))
        row = cursor.fetchone()
        if row:
            resolved_user_code = row["user_code"]

    if not resolved_user_code:
        resolved_user_code = "user_pw_9821" # Default fallback

    conn.close()

    data = get_user_wallet_data(resolved_user_code)
    if not data:
        raise HTTPException(status_code=404, detail="User not found")
    return data

@app.post("/auth/logout")
def logout():
    return {
        "status": "success",
        "message": "ออกจากระบบเรียบร้อยแล้ว"
    }

@app.get("/wallet/{user_code}")
def get_user_wallet(user_code: str):
    data = get_user_wallet_data(user_code)
    if not data:
        raise HTTPException(status_code=404, detail="User not found")
    return data

@app.post("/link/convert")
def convert_link(payload: ConvertLinkRequest):
    raw_url = payload.original_url.strip()
    if not raw_url.startswith("http"):
        raw_url = "https://" + raw_url

    matched_key = None
    for key, info in STORE_CATALOG.items():
        if info["domain"] in raw_url:
            matched_key = key
            break

    if not matched_key:
        matched_key = "lotus"
        store_info = STORE_CATALOG["lotus"]
    else:
        store_info = STORE_CATALOG[matched_key]

    click_id = f"sb_{payload.user_code}_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    encoded_destination = urllib.parse.quote(raw_url, safe='')

    if matched_key in ["lotus", "bigc", "central", "advice"]:
        affiliate_network = "accesstrade"
        tracking_url = f"https://click.accesstrade.in.th/adv.php?rk={store_info['offer_id']}&sub_id={click_id}&url={encoded_destination}"
    else:
        affiliate_network = "involve_asia"
        tracking_url = f"https://invol.co/aff_m?offer_id={store_info['offer_id']}&aff_sub={click_id}&url={encoded_destination}"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO clicks (click_id, user_code, store_key, original_url, tracking_url)
        VALUES (?, ?, ?, ?, ?)
    """, (click_id, payload.user_code, matched_key, raw_url, tracking_url))
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "store_key": matched_key,
        "store_name": store_info["name"],
        "cashback_rate": store_info["rate"],
        "icon": store_info["icon"],
        "click_id": click_id,
        "network": affiliate_network,
        "original_url": raw_url,
        "tracking_url": tracking_url,
        "instructions": "เปิดลิงก์นี้แล้วสั่งซื้อสินค้าภายใน 24 ชม. ระบบจะบันทึกเงินคืนเข้าวอลเล็ตโดยอัตโนมัติ"
    }

@app.post("/postback/simulate")
def simulate_postback(payload: SimulateOrderRequest):
    store_info = STORE_CATALOG.get(payload.store_key, STORE_CATALOG["lotus"])
    order_id = f"SIM-{payload.store_key.upper()}-{uuid.uuid4().hex[:6].upper()}"

    commission_total = round(payload.order_amount * store_info["commission_rate"], 2)
    cashback_amount = round(commission_total * store_info["cashback_share"], 2)
    our_profit = round(commission_total - cashback_amount, 2)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO cashback_orders (
            order_id, user_code, store_name, order_amount, commission_total, 
            cashback_rate, cashback_amount, our_profit, status, network, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'simulator', ?)
    """, (
        order_id, payload.user_code, store_info["name"], payload.order_amount,
        commission_total, round(store_info["commission_rate"] * 100, 1),
        cashback_amount, our_profit, payload.status, payload.notes
    ))
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "message": f"จำลองบันทึกยอดเงินคืนสำเร็จ: {store_info['name']} คืน ฿{cashback_amount:.2f}",
        "order": {
            "order_id": order_id,
            "user_code": payload.user_code,
            "store_name": store_info["name"],
            "order_amount": payload.order_amount,
            "cashback_amount": cashback_amount,
            "status": payload.status
        }
    }

@app.post("/withdraw")
def request_withdrawal(payload: WithdrawRequest):
    if payload.amount < 100.0:
        raise HTTPException(status_code=400, detail="ยอดถอนขั้นต่ำคือ 100.00 บาท")

    data = get_user_wallet_data(payload.user_code)
    if not data or data["wallet"]["available_balance"] < payload.amount:
        raise HTTPException(status_code=400, detail="ยอดเงินคืนที่ถอนได้ไม่เพียงพอ")

    ref_code = f"WD-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}"
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO withdrawals (ref_code, user_code, promptpay_id, amount, status)
        VALUES (?, ?, ?, ?, 'completed')
    """, (ref_code, payload.user_code, payload.promptpay_id, payload.amount))
    conn.commit()
    conn.close()

    updated = get_user_wallet_data(payload.user_code)
    return {
        "status": "success",
        "message": f"โอนเงินคืน ฿{payload.amount:.2f} เข้าพร้อมเพย์ {payload.promptpay_id} สำเร็จเรียบร้อย!",
        "ref_code": ref_code,
        "withdrawn_amount": payload.amount,
        "remaining_balance": updated["wallet"]["available_balance"]
    }
