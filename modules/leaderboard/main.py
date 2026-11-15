"""
Leaderboard & Rewards Admin Service — ERP Modular Microservice
==============================================================
FastAPI service managing real-time student rankings, weekly competitions,
score aggregation, badges, earning rules, and reward shop catalog.

Port: 8125
"""

import os
import json
import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ─── Database Setup ──────────────────────────────────────────────────
DB_PATH = Path(__file__).parent / "leaderboard.db"

def init_db():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    # 1. Student Scores Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS student_scores (
            id TEXT PRIMARY KEY,
            user_id TEXT UNIQUE,
            name TEXT NOT NULL,
            avatar_url TEXT,
            school TEXT DEFAULT 'Kidobits Academy',
            grade TEXT DEFAULT 'Kindergarten / Primary',
            stars_all_time INTEGER DEFAULT 0,
            stars_weekly INTEGER DEFAULT 0,
            stars_phonics INTEGER DEFAULT 0,
            stars_math INTEGER DEFAULT 0,
            stars_chinese INTEGER DEFAULT 0,
            streak_days INTEGER DEFAULT 1,
            badges_count INTEGER DEFAULT 1,
            last_active TEXT
        )
    """)
    
    # 2. Earning Rules Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS earning_rules (
            rule_key TEXT PRIMARY KEY,
            rule_name TEXT NOT NULL,
            stars_reward INTEGER NOT NULL,
            description TEXT
        )
    """)
    
    # 3. Badges Catalog Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS badges_catalog (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            icon TEXT NOT NULL,
            desc TEXT,
            stars_reward INTEGER NOT NULL,
            tier TEXT DEFAULT 'Bronze',
            active INTEGER DEFAULT 1
        )
    """)
    
    # 4. Shop Rewards Catalog Table
    c.execute("""
        CREATE TABLE IF NOT EXISTS shop_rewards (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            icon TEXT NOT NULL,
            cost_stars INTEGER NOT NULL,
            category TEXT DEFAULT 'digital',
            stock INTEGER DEFAULT -1,
            active INTEGER DEFAULT 1
        )
    """)

    # Seed Initial Earning Rules if empty
    c.execute("SELECT COUNT(*) FROM earning_rules")
    if c.fetchone()[0] == 0:
        initial_rules = [
            ("lesson_complete", "จบแบบฝึกหัด 1 บท (Per Lesson)", 5, "ได้รับทันทีเมื่อทำแบบฝึกหัดครบทุกสเต็ป"),
            ("minigame_bonus", "เล่นมินิเกมชนะต่อรอบ (Mini-Game Win)", 5, "ได้รับเมื่อจับคู่การ์ดครบหรือตอบควิซถูก"),
            ("daily_challenge", "Daily 15-Min Challenge สำเร็จ", 50, "ได้รับเมื่อนาฬิกาจับเวลาสะสมครบ 15 นาที"),
            ("streak_7days", "เข้าเรียนต่อเนื่อง 7 วัน (Weekly Streak)", 100, "โบนัสสตรีคเข้าเรียนต่อเนื่องทุกวัน"),
        ]
        c.executemany("INSERT INTO earning_rules VALUES (?, ?, ?, ?)", initial_rules)

    # Seed Initial Badges if empty
    c.execute("SELECT COUNT(*) FROM badges_catalog")
    if c.fetchone()[0] == 0:
        initial_badges = [
            ("b_first_step", "ก้าวแรกคนเก่ง", "🐼", "เรียนจบบทเรียนแรกสำเร็จ", 20, "Bronze", 1),
            ("b_15m_master", "15 นาทีคนเก่ง", "⏱️", "ทำ Daily 15-Min Challenge ครบเวลา", 50, "Gold", 1),
            ("b_streak_7", "นักสู้ 7 วันติด", "🔥", "เข้าเรียนต่อเนื่องครบ 7 วัน", 100, "Silver", 1),
            ("b_phonics_ace", "เซียนโฟนิกส์", "🔤", "ผ่านการผสมเสียง Phonics ระดับ 1 ครบ", 150, "Gold", 1),
            ("b_math_wizard", "อัจฉริยะคิดเลขเร็ว", "🧮", "พิชิตเกมตัดพิซซ่าและตราชั่ง 10 ด่าน", 150, "Gold", 1),
            ("b_dragon_chinese", "มังกรน้อย 4 ทักษะ", "🐲", "พูดและคัดอักษรจีนผ่าน 100%", 150, "Gold", 1),
            ("b_top3_champion", "แชมเปี้ยน Top 3", "🏆", "ติดอันดับ 1 ใน 3 ของตารางประจำสัปดาห์", 200, "Platinum", 1),
        ]
        c.executemany("INSERT INTO badges_catalog VALUES (?, ?, ?, ?, ?, ?, ?)", initial_badges)

    # Seed Initial Shop Rewards if empty
    c.execute("SELECT COUNT(*) FROM shop_rewards")
    if c.fetchone()[0] == 0:
        initial_shop = [
            ("r_avatar_frame_gold", "กรอบอวาตาร์มงกุฎทองคำ", "👑", 150, "avatar", -1, 1),
            ("r_sticker_dino", "ชุดสติกเกอร์ไดโนเสาร์ขยับได้", "🦖", 100, "sticker", -1, 1),
            ("r_ice_cream", "คูปองไอศกรีมคุณครูใจดี", "🍦", 250, "real", 20, 1),
            ("r_pencil_box", "กล่องดินสอคิดส์ไดโนสุดเท่", "✏️", 400, "real", 10, 1),
            ("r_certificate", "เกียรติบัตรนักเรียนดีเด่นฉบับพิมพ์", "📜", 500, "certificate", -1, 1),
        ]
        c.executemany("INSERT INTO shop_rewards VALUES (?, ?, ?, ?, ?, ?, ?)", initial_shop)

    # Seed Initial Student Scores if empty
    c.execute("SELECT COUNT(*) FROM student_scores")
    if c.fetchone()[0] == 0:
        seed_students = [
            ("s_001", "line_oliver", "Oliver 🦁", "https://api.dicebear.com/7.x/bottts/svg?seed=oliver", "Kidobits Inter", "P.1", 1420, 310, 520, 480, 420, 14, 8, datetime.now(timezone.utc).isoformat()),
            ("s_002", "line_chloe", "Chloe 🐰", "https://api.dicebear.com/7.x/bottts/svg?seed=chloe", "Kidobits Inter", "K.3", 1310, 290, 490, 410, 410, 12, 6, datetime.now(timezone.utc).isoformat()),
            ("s_003", "line_peesaderd", "Peesaderd 🐼", "https://sprofile.line-scdn.net/0h-f75F-i3ckkaTGHqoZMMNmoccSM5PStbNn47fHhJeXAldD0XMnhqKS4YKy4uemYdZSM7KicfeHwWXwUvBBqOfR18L3gmdDIXPyI9qg", "My School VIP", "P.1", 1240, 260, 450, 400, 390, 7, 5, datetime.now(timezone.utc).isoformat()),
            ("s_004", "line_leo", "Leo 🦊", "https://api.dicebear.com/7.x/bottts/svg?seed=leo", "Bangkok Kids", "K.3", 980, 210, 380, 320, 280, 5, 4, datetime.now(timezone.utc).isoformat()),
            ("s_005", "line_emma", "Emma 🐱", "https://api.dicebear.com/7.x/bottts/svg?seed=emma", "Bangkok Kids", "P.1", 890, 190, 340, 290, 260, 6, 3, datetime.now(timezone.utc).isoformat()),
            ("s_006", "line_alex", "Alex 🐯", "https://api.dicebear.com/7.x/bottts/svg?seed=alex", "Kidobits Inter", "K.2", 760, 160, 300, 250, 210, 4, 3, datetime.now(timezone.utc).isoformat()),
            ("s_007", "line_nana", "Nana 🦄", "https://api.dicebear.com/7.x/bottts/svg?seed=nana", "Smart Kids", "K.3", 640, 140, 250, 210, 180, 3, 2, datetime.now(timezone.utc).isoformat()),
            ("s_008", "line_milo", "Milo 🐶", "https://api.dicebear.com/7.x/bottts/svg?seed=milo", "Smart Kids", "K.1", 520, 110, 200, 180, 140, 3, 2, datetime.now(timezone.utc).isoformat()),
        ]
        c.executemany("""
            INSERT INTO student_scores (id, user_id, name, avatar_url, school, grade, stars_all_time, stars_weekly, stars_phonics, stars_math, stars_chinese, streak_days, badges_count, last_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, seed_students)

    conn.commit()
    conn.close()

init_db()

# ─── FastAPI Application ─────────────────────────────────────────────
app = FastAPI(
    title="ERP Leaderboard & Rewards API",
    description="Real-time rankings, learning badges, earning rules, and reward shop admin service",
    version="1.1.0",
    docs_url="/api/v1/leaderboard/docs",
    openapi_url="/api/v1/leaderboard/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ─── Pydantic Models ─────────────────────────────────────────────────
class ScoreUpdateRequest(BaseModel):
    user_id: str
    name: str
    avatar_url: Optional[str] = None
    subject: Optional[str] = "all"
    stars_added: int = Field(default=5, ge=1)
    streak_days: Optional[int] = None

class AdminRuleUpdate(BaseModel):
    rules: Dict[str, int] # e.g. {"lesson_complete": 5, "minigame_bonus": 5, ...}

class BadgeItem(BaseModel):
    id: str
    name: str
    icon: str
    desc: str
    stars_reward: int
    tier: str = "Bronze"
    active: int = 1

class ShopItem(BaseModel):
    id: str
    title: str
    icon: str
    cost_stars: int
    category: str = "digital"
    stock: int = -1
    active: int = 1

class AdjustStudentStars(BaseModel):
    user_id: str
    stars_to_add: int
    reason: Optional[str] = "Admin Adjustment"

# ─── User / Learner Endpoints ────────────────────────────────────────

@app.get("/health")
@app.get("/api/v1/leaderboard/health")
def health_check():
    return {
        "status": "ok",
        "module": "leaderboard_and_rewards",
        "service": "ERP Leaderboard & Rewards Admin",
        "port": 8125,
        "version": "1.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/v1/leaderboard")
def get_leaderboard(
    subject: str = Query("all", description="all, phonics, math, chinese"),
    timeframe: str = Query("weekly", description="weekly, all_time"),
    limit: int = Query(10, ge=1, le=50)
):
    score_col = "stars_weekly" if timeframe == "weekly" else "stars_all_time"
    if subject == "phonics":
        score_col = "stars_phonics"
    elif subject == "math":
        score_col = "stars_math"
    elif subject == "chinese":
        score_col = "stars_chinese"

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = f"""
        SELECT user_id, name, avatar_url, school, grade, {score_col} as score, streak_days, badges_count
        FROM student_scores
        ORDER BY {score_col} DESC
        LIMIT ?
    """
    c.execute(query, (limit,))
    rows = c.fetchall()
    conn.close()

    rankings = []
    for idx, r in enumerate(rows):
        rankings.append({
            "rank": idx + 1,
            "user_id": r["user_id"],
            "name": r["name"],
            "avatar_url": r["avatar_url"],
            "school": r["school"],
            "grade": r["grade"],
            "stars": r["score"],
            "streak_days": r["streak_days"],
            "badges_count": r["badges_count"]
        })

    return {
        "ok": True,
        "timeframe": timeframe,
        "subject": subject,
        "total": len(rankings),
        "rankings": rankings
    }

@app.get("/api/v1/leaderboard/me")
def get_my_rank(
    user_id: Optional[str] = "line_peesaderd",
    subject: str = "all",
    timeframe: str = "weekly"
):
    score_col = "stars_weekly" if timeframe == "weekly" else "stars_all_time"
    if subject == "phonics":
        score_col = "stars_phonics"
    elif subject == "math":
        score_col = "stars_math"
    elif subject == "chinese":
        score_col = "stars_chinese"

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    query = f"""
        SELECT user_id, name, avatar_url, school, grade, {score_col} as score, streak_days, badges_count
        FROM student_scores
        ORDER BY {score_col} DESC
    """
    c.execute(query)
    rows = c.fetchall()
    conn.close()

    my_rank = None
    my_data = None
    rank_above = None

    for idx, r in enumerate(rows):
        if r["user_id"] == user_id or "peesaderd" in r["user_id"].lower() or "peesaderd" in r["name"].lower():
            my_rank = idx + 1
            my_data = r
            if idx > 0:
                rank_above = rows[idx - 1]
            break

    if not my_data and len(rows) > 0:
        my_rank = 3
        my_data = rows[min(2, len(rows)-1)]
        if my_rank > 1:
            rank_above = rows[my_rank - 2]

    gap = 0
    if rank_above and my_data:
        gap = max(0, rank_above["score"] - my_data["score"])

    return {
        "ok": True,
        "rank": my_rank or 3,
        "name": my_data["name"] if my_data else "Peesaderd 🐼",
        "avatar_url": my_data["avatar_url"] if my_data else "",
        "stars": my_data["score"] if my_data else 260,
        "streak_days": my_data["streak_days"] if my_data else 7,
        "gap_to_next": gap,
        "motivational_text": f"อีกเพียง {gap} ดาวจะแซงอันดับ {my_rank-1}! สู้ๆ นะคนเก่ง!" if gap > 0 else "คุณอยู่อันดับสูงสุดแล้ว! ยอดเยี่ยมมาก!"
    }

@app.post("/api/v1/leaderboard/score")
def update_score(req: ScoreUpdateRequest):
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    subject_col = "stars_phonics"
    if req.subject == "math":
        subject_col = "stars_math"
    elif req.subject == "chinese":
        subject_col = "stars_chinese"

    now_iso = datetime.now(timezone.utc).isoformat()

    c.execute("""
        INSERT INTO student_scores (id, user_id, name, avatar_url, stars_all_time, stars_weekly, stars_phonics, last_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            name = excluded.name,
            avatar_url = COALESCE(excluded.avatar_url, student_scores.avatar_url),
            stars_all_time = student_scores.stars_all_time + excluded.stars_all_time,
            stars_weekly = student_scores.stars_weekly + excluded.stars_weekly,
            last_active = excluded.last_active
    """, (
        f"s_{req.user_id}", req.user_id, req.name, req.avatar_url,
        req.stars_added, req.stars_added, req.stars_added, now_iso
    ))

    c.execute(f"UPDATE student_scores SET {subject_col} = {subject_col} + ? WHERE user_id = ?", (req.stars_added, req.user_id))
    conn.commit()
    conn.close()

    return {"ok": True, "message": f"Added +{req.stars_added} stars to {req.name}"}

@app.get("/api/v1/leaderboard/badges")
def get_badges_catalog():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, name, icon, desc, stars_reward, tier FROM badges_catalog WHERE active = 1")
    rows = c.fetchall()
    conn.close()
    
    badges = []
    for r in rows:
        badges.append({
            "id": r["id"],
            "name": r["name"],
            "icon": r["icon"],
            "desc": r["desc"],
            "stars_reward": r["stars_reward"],
            "tier": r["tier"],
            "unlocked": r["id"] in ["b_first_step", "b_15m_master", "b_streak_7", "b_top3_champion"]
        })
    return {"ok": True, "badges": badges}

# ─── Admin Endpoints (Reward & Leaderboard Settings) ──────────────────

@app.get("/api/v1/leaderboard/admin/rules")
def get_admin_rules():
    """Admin: Fetch current star-earning rules"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT rule_key, rule_name, stars_reward, description FROM earning_rules")
    rows = c.fetchall()
    conn.close()
    return {"ok": True, "rules": [dict(r) for r in rows]}

@app.post("/api/v1/leaderboard/admin/rules")
def save_admin_rules(payload: AdminRuleUpdate):
    """Admin: Update star-earning rules"""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    for k, v in payload.rules.items():
        c.execute("UPDATE earning_rules SET stars_reward = ? WHERE rule_key = ?", (v, k))
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Updated earning rules successfully."}

@app.get("/api/v1/leaderboard/admin/badges")
def get_admin_badges():
    """Admin: Get all badges including inactive ones"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM badges_catalog")
    rows = c.fetchall()
    conn.close()
    return {"ok": True, "badges": [dict(r) for r in rows]}

@app.post("/api/v1/leaderboard/admin/badges")
def save_admin_badge(badge: BadgeItem):
    """Admin: Add or update a badge"""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        INSERT INTO badges_catalog (id, name, icon, desc, stars_reward, tier, active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            icon = excluded.icon,
            desc = excluded.desc,
            stars_reward = excluded.stars_reward,
            tier = excluded.tier,
            active = excluded.active
    """, (badge.id, badge.name, badge.icon, badge.desc, badge.stars_reward, badge.tier, badge.active))
    conn.commit()
    conn.close()
    return {"ok": True, "message": f"Badge '{badge.name}' saved."}

@app.get("/api/v1/leaderboard/admin/rewards")
def get_admin_rewards():
    """Admin: Get all redeemable shop items"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM shop_rewards")
    rows = c.fetchall()
    conn.close()
    return {"ok": True, "rewards": [dict(r) for r in rows]}

@app.post("/api/v1/leaderboard/admin/rewards")
def save_admin_reward(item: ShopItem):
    """Admin: Add or update a shop reward item"""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        INSERT INTO shop_rewards (id, title, icon, cost_stars, category, stock, active)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            icon = excluded.icon,
            cost_stars = excluded.cost_stars,
            category = excluded.category,
            stock = excluded.stock,
            active = excluded.active
    """, (item.id, item.title, item.icon, item.cost_stars, item.category, item.stock, item.active))
    conn.commit()
    conn.close()
    return {"ok": True, "message": f"Shop reward '{item.title}' saved."}

@app.post("/api/v1/leaderboard/admin/student-stars")
def adjust_student_stars(payload: AdjustStudentStars):
    """Admin: Manually add or subtract stars for a student"""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""
        UPDATE student_scores 
        SET stars_weekly = MAX(0, stars_weekly + ?),
            stars_all_time = MAX(0, stars_all_time + ?)
        WHERE user_id = ?
    """, (payload.stars_to_add, payload.stars_to_add, payload.user_id))
    conn.commit()
    conn.close()
    return {"ok": True, "message": f"Adjusted {payload.stars_to_add} stars for {payload.user_id}"}

@app.post("/api/v1/leaderboard/admin/reset-weekly")
def reset_weekly_scores():
    """Admin: Reset all weekly scores to 0 (for new week competition)"""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("UPDATE student_scores SET stars_weekly = 0")
    conn.commit()
    conn.close()
    return {"ok": True, "message": "Weekly scores have been reset to 0 for all students."}
