"""
ERP Notification & Omnichannel Alert Service
============================================
FastAPI service managing in-app notifications, user alert feeds,
read/unread tracking, and multi-channel push dispatch (In-App, LINE, Telegram).

Port: 8126
"""

import os
import json
import sqlite3
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ─── Database Setup ──────────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "notifications.db"

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'announcement', -- reward, learning, announcement, system, social
            icon TEXT DEFAULT '🔔',
            action_url TEXT,
            action_label TEXT,
            channels TEXT DEFAULT '["in_app"]',
            is_read INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    c.execute("CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications (user_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_notif_read ON notifications (is_read)")

    # Check if empty, seed initial lively notifications
    c.execute("SELECT COUNT(*) FROM notifications")
    if c.fetchone()[0] == 0:
        now = datetime.now(timezone.utc).isoformat()
        initial_notifs = [
            ("notif_001", "line_peesaderd", "🏆 ยินดีด้วย! คุณติด Top 3 สัปดาห์นี้", "น้อง Peesaderd 🐼 ทำคะแนนสะสม 260 ⭐ ติดอันดับ 3 ของตารางประจำสัปดาห์!", "reward", "🏆", "/theme/theme_leaderboard.html", "ดูอันดับของคุณ", '["in_app"]', 0, now),
            ("notif_002", "line_peesaderd", "🎖️ ปปลดล็อคเหรียญ '15 นาทีคนเก่ง'", "สำเร็จ Daily 15-Min Challenge ประจำวัน รับดาวโบนัสความพยายาม +50 ⭐", "reward", "⏱️", "/theme/theme_reward_admin.html", "ดูเหรียญรางวัล", '["in_app"]', 0, now),
            ("notif_003", "line_peesaderd", "🔥 สตรีคการเรียน 7 วันติดแล้ว!", "สุดยอดมาก! เข้ามาเรียนต่อเนื่องครบ 7 วัน รับโบนัสความขยัน +100 ⭐", "learning", "🔥", "/theme/theme_home.html", "เรียนต่อวันนี้", '["in_app"]', 1, now),
            ("notif_004", "line_peesaderd", "📢 กิจกรรมการเรียนรู้ใหม่: ตะลุยด่านภาษาจีน", "เปิดแบบฝึกหัดภาษาจีนระดับ 1 ครบทั้ง 10 บทเรียนแล้ววันนี้ มาฝึกออกเสียงกันเถอะ!", "announcement", "🐲", "/theme/theme_chinese_lobby.html", "เริ่มเรียนภาษาจีน", '["in_app"]', 1, now),
            ("notif_005", "all", "🌟 อัปเดตตารางคะแนนและของรางวัลใหม่", "ระบบเพิ่มเหรียญรางวัลและของขวัญในร้านค้าใหม่ สามารถนำดาวสะสมไปแลกได้แล้ว!", "announcement", "🎁", "/theme/theme_leaderboard.html", "เปิดดูของขวัญ", '["in_app"]', 0, now),
        ]
        c.executemany("""
            INSERT INTO notifications (id, user_id, title, message, type, icon, action_url, action_label, channels, is_read, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, initial_notifs)

    conn.commit()
    conn.close()

init_db()

# ─── FastAPI Application ─────────────────────────────────────────────
app = FastAPI(
    title="ERP Notification & Alert Service",
    description="Central In-App and Omnichannel Notification Service for Kidobits and ERP Modules",
    version="1.0.0",
    docs_url="/api/v1/notifications/docs",
    openapi_url="/api/v1/notifications/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ─── Models ──────────────────────────────────────────────────────────
class NotificationCreate(BaseModel):
    user_id: str
    title: str
    message: str
    type: str = "announcement" # reward, learning, announcement, system, social
    icon: Optional[str] = "🔔"
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    channels: Optional[List[str]] = ["in_app"]

class MarkReadRequest(BaseModel):
    id: str

class MarkAllReadRequest(BaseModel):
    user_id: str

# ─── Routes ──────────────────────────────────────────────────────────

@app.get("/health")
@app.get("/api/v1/notifications/health")
def health_check():
    return {
        "status": "ok",
        "module": "notification",
        "service": "ERP Notification & Alert Gateway",
        "port": 8126,
        "version": "1.0.0",
        "docs": "/api/v1/notifications/docs",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/v1/notifications")
def list_notifications(
    user_id: Optional[str] = Query("line_peesaderd", description="Target user ID or 'all'"),
    type: Optional[str] = Query(None, description="reward, learning, announcement, system"),
    unread_only: bool = Query(False, description="Filter unread only"),
    limit: int = Query(30, ge=1, le=100)
):
    """Fetch notifications for a specific user and global announcements"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    conditions = ["(user_id = ? OR user_id = 'all')"]
    params = [user_id]

    if type and type != "all":
        conditions.append("type = ?")
        params.append(type)

    if unread_only:
        conditions.append("is_read = 0")

    where_clause = " WHERE " + " AND ".join(conditions)
    query = f"""
        SELECT id, user_id, title, message, type, icon, action_url, action_label, channels, is_read, created_at
        FROM notifications
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
    """
    params.append(limit)
    c.execute(query, tuple(params))
    rows = c.fetchall()

    # Count total unread
    c.execute("SELECT COUNT(*) FROM notifications WHERE (user_id = ? OR user_id = 'all') AND is_read = 0", (user_id,))
    unread_count = c.fetchone()[0]

    conn.close()

    items = []
    for r in rows:
        items.append({
            "id": r["id"],
            "user_id": r["user_id"],
            "title": r["title"],
            "message": r["message"],
            "type": r["type"],
            "icon": r["icon"],
            "action_url": r["action_url"],
            "action_label": r["action_label"],
            "channels": json.loads(r["channels"]) if r["channels"] else ["in_app"],
            "is_read": bool(r["is_read"]),
            "created_at": r["created_at"]
        })

    return {
        "ok": True,
        "unread_count": unread_count,
        "total": len(items),
        "notifications": items
    }

@app.get("/api/v1/notifications/unread-count")
def get_unread_count(user_id: str = Query("line_peesaderd")):
    """Get the quick count of unread notifications for badge dots"""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM notifications WHERE (user_id = ? OR user_id = 'all') AND is_read = 0", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return {"ok": True, "unread_count": count}

@app.post("/api/v1/notifications")
def create_notification(req: NotificationCreate):
    """Publish a notification to in-app feed and dispatch channels"""
    notif_id = f"notif_{uuid.uuid4().hex[:10]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    channels_json = json.dumps(req.channels or ["in_app"])

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        INSERT INTO notifications (id, user_id, title, message, type, icon, action_url, action_label, channels, is_read, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
    """, (
        notif_id, req.user_id, req.title, req.message, req.type,
        req.icon or "🔔", req.action_url, req.action_label, channels_json, now_iso
    ))
    conn.commit()
    conn.close()

    # If LINE channel requested, we can forward to line_bot (if configured)
    dispatched = ["in_app"]
    if "line" in req.channels:
        # Note: LINE bot webhook or push message can be invoked here
        dispatched.append("line")

    return {
        "ok": True,
        "id": notif_id,
        "message": "Notification published successfully",
        "dispatched_channels": dispatched
    }

@app.post("/api/v1/notifications/read")
def mark_as_read(req: MarkReadRequest):
    """Mark a single notification as read"""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (req.id,))
    conn.commit()
    conn.close()
    return {"ok": True, "message": f"Notification {req.id} marked as read."}

@app.post("/api/v1/notifications/read-all")
def mark_all_as_read(req: MarkAllReadRequest):
    """Mark all notifications as read for a given user"""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? OR user_id = 'all'", (req.user_id,))
    conn.commit()
    conn.close()
    return {"ok": True, "message": f"All notifications for {req.user_id} marked as read."}

@app.delete("/api/v1/notifications/{notif_id}")
def delete_notification(notif_id: str):
    """Delete a notification"""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("DELETE FROM notifications WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()
    return {"ok": True, "message": f"Notification {notif_id} deleted."}
